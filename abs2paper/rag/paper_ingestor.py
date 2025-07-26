import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.utils.llm_client import LLMClient
import re

class PaperIngestor:
    """
    论文数据入库工具：将论文各部分文本及主题标签生成embedding后写入Milvus
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化PaperIngestor，加载配置、连接Milvus、初始化主题管理器和LLMClient。
        Args:
            config_path: 配置文件路径，默认为项目config/config.json
        """
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        self.embedding_config = self.config.get("embedding", {})
        self.vector_db_config = self.config.get("vector_db", {})
        self.topic_manager = TopicManager()
        self.llm_client = LLMClient()
        
        # 设置Milvus连接参数
        self.milvus_host = self.vector_db_config.get("host", "192.168.70.174")
        self.milvus_port = self.vector_db_config.get("port", "19530")
        self.milvus_alias = "paper_db"
        self.db_name = self.vector_db_config.get("db_name", "abs2paper")
        
        # 初始化集合引用存储
        self.collections = {}
        self.collections_loaded = False
        
        self.section_names = ["引言", "相关工作", "方法", "实验评价", "总结"]
        self.section_name_en = {
            "引言": "introduction",
            "相关工作": "related_work",
            "方法": "methodology",
            "实验评价": "experiments",
            "总结": "conclusion"
        }
        
        # 章节名称映射表，将文件名映射到预定义的部分
        self.section_mapping = {
            "introduction": "引言",
            "related work": "相关工作",
            "method": "方法",
            "methodology": "方法",
            "approach": "方法",
            "design": "方法",
            "implementation": "方法",
            "evaluation": "实验评价",
            "experiments": "实验评价",
            "experimental": "实验评价",
            "results": "实验评价",
            "conclusion": "总结",
            "conclusions": "总结",
            "future work": "总结",
            "summary": "总结"
        }
        
        # 罗马数字章节名正则表达式
        self.roman_pattern = re.compile(r'^([IVX]+)\.\s+(.+)', re.IGNORECASE)
        
        # 数字章节名正则表达式
        self.number_pattern = re.compile(r'^(\d+)(\.\d+)?\s+(.+)', re.IGNORECASE)
        
        self.embedding_dim = self.embedding_config.get("request", {}).get("payload", {}).get("embedding_dim", 1024)
        
        # 连接到Milvus向量数据库
        self._connect_to_milvus()
        # 创建或获取所有集合
        self._create_collections()

    def _load_config(self):
        """
        加载配置文件
        Returns:
            配置字典
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _connect_to_milvus(self):
        """
        连接到Milvus向量数据库
        """
        try:
            logging.info(f"正在连接到Milvus服务: {self.milvus_host}:{self.milvus_port}，数据库: {self.db_name}")
            connections.connect(
                alias=self.milvus_alias,
                host=self.milvus_host,
                port=self.milvus_port,
                db_name=self.db_name
            )
            logging.info("✅ Milvus连接成功")
        except Exception as e:
            logging.error(f"⚠️ 连接Milvus失败: {str(e)}")
            raise

    def _create_collections(self):
        """创建所有需要的集合"""
        logging.info("创建和准备集合...")
        
        for section in self.section_names:
            collection_name = self.get_collection_name(section)
            
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="paper_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="topics", dtype=DataType.ARRAY, max_capacity=10, element_type=DataType.VARCHAR, max_length=128),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
            ]
            schema = CollectionSchema(fields, f"Collection for {section}")
            
            try:
                # 检查集合是否存在
                has_collection = utility.has_collection(collection_name, using=self.milvus_alias)
                
                if has_collection:
                    logging.info(f"集合 '{collection_name}' 已存在，直接获取")
                    collection = Collection(name=collection_name, using=self.milvus_alias)
                else:
                    logging.info(f"创建新集合: '{collection_name}'")
                    collection = Collection(name=collection_name, schema=schema, using=self.milvus_alias)
                
                # 检查索引
                try:
                    has_index = False
                    index_info = collection.index()
                    if index_info:
                        has_index = True
                except Exception:
                    has_index = False
                
                if not has_index:
                    logging.info(f"为集合 '{collection_name}' 创建索引...")
                    index_params = {"index_type": "IVF_FLAT", "params": {"nlist": 128}, "metric_type": "L2"}
                    collection.create_index(field_name="embedding", index_params=index_params)
                
                # 存储集合引用
                self.collections[section] = collection
                
            except Exception as e:
                logging.error(f"创建或准备集合 '{collection_name}' 失败: {e}")

    def get_collection_name(self, section: str) -> str:
        """
        获取指定论文部分的Milvus集合名称
        Args:
            section: 论文部分中文名
        Returns:
            集合名称字符串
        """
        section_en = self.section_name_en.get(section, "other")
        return f"paper_{section_en}"

    def ensure_collection(self, section: str):
        """
        确保指定论文部分的Milvus集合存在，不存在则创建
        Args:
            section: 论文部分中文名
        Returns:
            Collection对象
        """
        # 如果已经有引用，直接返回
        if section in self.collections:
            return self.collections[section]
            
        collection_name = self.get_collection_name(section)
        try:
            # 检查集合是否存在
            if utility.has_collection(collection_name, using=self.milvus_alias):
                collection = Collection(name=collection_name, using=self.milvus_alias)
            else:
                # 创建新集合
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="paper_id", dtype=DataType.VARCHAR, max_length=128),
                    FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=32),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                    FieldSchema(name="topics", dtype=DataType.ARRAY, max_capacity=10, element_type=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
                ]
                schema = CollectionSchema(fields, f"Collection for {section}")
                collection = Collection(name=collection_name, schema=schema, using=self.milvus_alias)
                
                # 创建索引
                index_params = {"index_type": "IVF_FLAT", "params": {"nlist": 128}, "metric_type": "L2"}
                collection.create_index(field_name="embedding", index_params=index_params)
            
            # 存储引用
            self.collections[section] = collection
            return collection
            
        except Exception as e:
            logging.error(f"确保集合 {collection_name} 存在时出错: {e}")
            raise

    def split_text(self, text: str, chunk_size: int = 300, overlap_size: int = 50) -> List[str]:
        """
        按指定chunk_size和overlap_size将文本分割成块，确保上下文连贯性
        
        参数:
            text: 待切分的文本
            chunk_size: 每个块的最大大小（字符数）
            overlap_size: 块之间的重叠大小（字符数）
            
        返回:
            文本块列表
        """
        # 确保nltk的punkt分词器已下载
        try:
            from nltk.tokenize import sent_tokenize
            try:
                sentences = sent_tokenize(text)
            except:
                import nltk
                nltk.download('punkt')
                sentences = sent_tokenize(text)
        except ImportError:
            # 如果没有nltk，使用简单的规则分割
            sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # 将文本分割成句子
        sentences = [s.strip() for s in sentences if s.strip()]
        chunks = []
        i = 0
        
        while i < len(sentences):
            chunk = sentences[i]
            overlap = ''
            prev_len = 0
            prev = i - 1
            # 向前计算重叠部分
            while prev >= 0 and len(sentences[prev]) + len(overlap) <= overlap_size:
                overlap = sentences[prev] + ' ' + overlap
                prev -= 1
            chunk = overlap + chunk if overlap else chunk
            
            next_idx = i + 1
            # 向后计算当前chunk
            while next_idx < len(sentences) and len(chunk) + len(sentences[next_idx]) <= chunk_size:
                chunk = chunk + ' ' + sentences[next_idx]
                next_idx += 1
            
            chunks.append(chunk)
            i = next_idx
        
        return chunks

    def _extract_topics_from_file(self, paper_id: str, label_dir: str) -> List[str]:
        """
        从标签文件中提取主题关键词
        Args:
            paper_id: 论文ID
            label_dir: 标签目录
        Returns:
            提取的主题关键词列表
        """
        # 读取标签
        label_file = os.path.join(label_dir, f"{paper_id}.txt")
        topics = []
        
        if not os.path.exists(label_file):
            # 尝试查找不带路径的文件名匹配
            base_name = os.path.basename(paper_id)
            label_file = os.path.join(label_dir, f"{base_name}.txt")
        
        if os.path.exists(label_file):
            with open(label_file, "r", encoding="utf-8") as lf:
                for line in lf:
                    if line.strip().startswith("故该论文的主题关键词总结为["):
                        topics = [x.strip() for x in line.split("[")[-1].split("]")[0].split(",") if x.strip()]
                        break
        
        return topics

    def _map_section_name(self, section_name: str) -> str:
        """
        将章节文件名映射到标准论文部分，参考milvus_paper.py的实现
        Args:
            section_name: 章节文件名
        Returns:
            映射后的标准部分名称
        """
        # 移除数字前缀和扩展名
        # 标准化文件名
        section_title = section_name.lower()
        
        # 尝试匹配罗马数字格式
        roman_match = self.roman_pattern.match(section_name)
        if roman_match:
            section_title = roman_match.group(2).lower()
        
        # 尝试匹配数字格式
        number_match = self.number_pattern.match(section_name)
        if number_match:
            section_title = number_match.group(3).lower()
        
        # 尝试匹配标准部分
        for keyword, target_section in self.section_mapping.items():
            # 比较宽泛的匹配
            if keyword in section_title or section_title in keyword:
                return target_section
        
        # 默认返回方法部分，因为有些论文可能使用项目名称作为方法部分
        return "方法"

    def _process_paper_sections(self, paper_path: str) -> Dict[str, str]:
        """
        处理论文目录中的所有章节文件
        Args:
            paper_path: 论文目录路径
        Returns:
            按标准部分组织的文本字典
        """
        section_texts = {section: "" for section in self.section_names}
        
        # 遍历论文目录下的所有txt文件（章节）
        for section_file in os.listdir(paper_path):
            if not section_file.endswith(".txt"):
                continue
            
            section_file_path = os.path.join(paper_path, section_file)
            section_name = section_file[:-4]  # 去掉.txt后缀
            
            # 读取章节内容
            with open(section_file_path, "r", encoding="utf-8") as f:
                section_content = f.read()
            
            # 映射章节名到标准部分
            mapped_section = self._map_section_name(section_name)
            
            # 将内容添加到对应部分
            section_texts[mapped_section] += section_content + "\n\n"
        
        return section_texts

    def _process_section_chunks(self, paper_id: str, section: str, text: str, topic_names: List[str]) -> bool:
        """
        处理单个论文部分，分块并入库
        Args:
            paper_id: 论文ID
            section: 部分名称
            text: 部分内容
            topic_names: 主题名称列表
        Returns:
            处理是否成功
        """
        try:
            collection = self.collections.get(section)
            if not collection:
                collection = self.ensure_collection(section)
            
            # 将文本切分成小块
            chunks = self.split_text(text, chunk_size=500, overlap_size=100)
            logging.info(f"将论文 {paper_id} 的 {section} 部分切分为 {len(chunks)} 个块")
            
            # 生成嵌入向量（批量处理）
            embeddings = self.llm_client.get_embedding(chunks)
            
            # 构建插入数据（每个chunk一条记录）
            data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                data.append({
                    "paper_id": f"{paper_id}_{i}",  # 添加块编号
                    "section": section,
                    "text": chunk[:8000],  # 限制文本长度
                    "topics": topic_names,
                    "embedding": embedding
                })
            
            # 批量插入数据
            if data:
                collection.insert(data)
                logging.info(f"已入库: {paper_id} {section} ({len(chunks)} 个块)")
            
            return True
        except Exception as e:
            logging.error(f"处理论文 {paper_id} 的 {section} 部分时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _process_single_paper(self, paper_id: str, paper_path: str, label_dir: str) -> bool:
        """
        处理单个论文的所有部分
        Args:
            paper_id: 论文ID
            paper_path: 论文路径
            label_dir: 标签目录
        Returns:
            是否成功处理
        """
        logging.info(f"处理论文: {paper_id}")
        
        # 提取主题标签
        topics = self._extract_topics_from_file(paper_id, label_dir)
        if not topics:
            logging.warning(f"论文 {paper_id} 无法提取主题关键词，跳过处理")
            return False
        
        # 主题名映射
        topic_names = []
        for topic_id in topics:
            topic_info = self.topic_manager.get_topic_info(topic_id)
            if topic_info:
                topic_names.append(f"{topic_info['name_zh']} ({topic_info['name_en']})")
        
        # 按章节组织的文本内容
        section_texts = self._process_paper_sections(paper_path)
        
        # 对于每个部分，如果有内容，则创建embedding并写入向量数据库
        has_content = False
        for section, text in section_texts.items():
            if not text.strip():
                continue
            
            has_content = True
            self._process_section_chunks(paper_id, section, text, topic_names)
        
        return has_content

    def _find_paper_directories(self, root_dir: str) -> List[Tuple[str, str]]:
        """
        递归查找包含txt文件的论文目录
        Args:
            root_dir: 起始目录
        Returns:
            包含(论文ID, 论文目录路径)的元组列表
        """
        paper_dirs = []
        
        def find_papers(dir_path, current_conf=None):
            # 检查是否为叶子目录(包含txt文件)
            has_txt = any(item.endswith('.txt') and os.path.isfile(os.path.join(dir_path, item)) 
                          for item in os.listdir(dir_path))
            
            # 如果包含txt文件，认为是论文目录
            if has_txt:
                paper_id = os.path.basename(dir_path)
                paper_dirs.append((paper_id, dir_path))
                return
            
            # 如果是会议目录，更新current_conf
            if current_conf is None:
                current_conf = os.path.basename(dir_path)
            
            # 继续递归子目录
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    find_papers(item_path, current_conf)
        
        find_papers(root_dir)
        return paper_dirs

    def ingest(self, component_dir: Optional[str] = None, label_dir: Optional[str] = None):
        """
        批量读取论文分段和主题标签，生成embedding并写入Milvus。
        Args:
            component_dir: 论文分段目录，默认为项目abs2paper/extraction/result/component_extract
            label_dir: 主题标签目录，默认为项目abs2paper/extraction/result/label
        """
        component_dir = component_dir or os.path.join(self.project_root, "abs2paper", "extraction", "result", "component_extract")
        label_dir = label_dir or os.path.join(self.project_root, "abs2paper", "extraction", "result", "label")
        
        logging.info(f"开始处理论文目录: {component_dir}")
        logging.info(f"标签目录: {label_dir}")
        
        # 保存处理的论文计数
        processed_count = 0
        
        try:
            # 使用递归查找所有论文目录
            paper_directories = self._find_paper_directories(component_dir)
            logging.info(f"找到 {len(paper_directories)} 个论文目录")
            
            # 处理每个论文目录
            for paper_id, paper_path in paper_directories:
                if self._process_single_paper(paper_id, paper_path, label_dir):
                    processed_count += 1
            
            logging.info(f"数据入库完成，共处理了 {processed_count} 篇论文")
        except Exception as e:
            logging.error(f"处理论文数据时出现错误: {str(e)}")
            import traceback
            logging.error(traceback.format_exc()) 