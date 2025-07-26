import os
import json
import logging
from typing import Dict, List, Optional, Tuple
import re
import copy
from pymilvus import FieldSchema, DataType

from abs2paper.utils.topic_manager import TopicManager
from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.db_client import MilvusClient

class PaperIngestor:
    """
    论文数据入库工具：将论文各部分文本及主题标签生成embedding后写入Milvus
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化PaperIngestor，加载配置、初始化主题管理器、LLMClient和MilvusClient
        Args:
            config_path: 配置文件路径，默认为项目config/config.json
        """
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 初始化工具类
        self.topic_manager = TopicManager()
        self.llm_client = LLMClient()
        
        # 读取数据库配置
        vector_db_config = self.config["vector_db"]          # 数据库连接配置
        self.embedding_dim = vector_db_config["embedding_dim"]    # 嵌入向量维度
        
        # 读取论文配置
        paper_config = self.config["paper"]
        self.section_names = paper_config["sections"]             # 论文部分名称列表
        self.section_name_en = paper_config["section_mapping_en"] # 部分英文名映射
        self.section_mapping = paper_config["chapter_mapping"]    # 章节映射表
        self.collection_fields_config = paper_config["collection_fields"] # 集合字段配置
        self.index_params = paper_config["index_params"]          # 索引参数
        
        # 初始化Milvus客户端
        db_config = {
            "host": vector_db_config["host"],         # 服务器地址
            "port": vector_db_config["port"],         # 服务端口
            "alias": vector_db_config["alias"],       # 连接别名
            "db_name": vector_db_config["db_name"]    # 数据库名称
        }
        self.db_client = MilvusClient(db_config)
        
        # 设置正则表达式模式
        self.roman_pattern = re.compile(r'^([IVX]+)\.\s+(.+)', re.IGNORECASE)     # 罗马数字章节名
        self.number_pattern = re.compile(r'^(\d+)(\.\d+)?\s+(.+)', re.IGNORECASE) # 数字章节名
        
        # 创建集合
        self._create_collections()

    def _load_config(self):
        """
        加载配置文件
        Returns:
            配置字典
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def _get_collection_name(self, section: str) -> str:
        """
        获取指定论文部分的Milvus集合名称
        Args:
            section: 论文部分中文名
        Returns:
            集合名称字符串
        """
        section_en = self.section_name_en[section]  # 获取英文名称
        return f"paper_{section_en}"
    
    def _create_field_schema(self) -> List[FieldSchema]:
        """
        根据配置创建字段模式列表
        Returns:
            字段模式列表
        """
        fields = []
        
        # 解析配置并创建字段模式
        for field_name, field_config in self.collection_fields_config.items():
            # 获取字段类型
            field_type = field_config["type"]
            data_type = getattr(DataType, field_type)
            
            # 处理参数
            kwargs = {}
            for key, value in field_config.items():
                if key == "type":
                    continue
                    
                # 处理变量替换
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    var_name = value[2:-1]
                    if var_name == "embedding_dim":
                        value = self.embedding_dim
                
                # 特殊处理数组元素类型
                if key == "element_type" and isinstance(value, str):
                    value = getattr(DataType, value)
                
                # 重命名element_max_length为max_length
                if key == "element_max_length":
                    kwargs["max_length"] = value
                else:
                    kwargs[key] = value
            
            # 创建字段模式
            field = FieldSchema(name=field_name, dtype=data_type, **kwargs)
            fields.append(field)
        
        return fields
    
    def _create_collections(self):
        """准备集合配置并调用db_client创建集合"""
        # 准备集合配置列表
        collection_configs = []
        fields = self._create_field_schema()
        
        # 为每个论文部分创建集合配置
        for section in self.section_names:
            collection_name = self._get_collection_name(section)
            collection_configs.append({
                "name": collection_name,                    # 集合名称
                "fields": fields,                           # 字段定义
                "description": f"Collection for paper {section}",  # 集合描述
                "index_field": "embedding",                 # 索引字段
                "index_params": self.index_params           # 索引参数
            })
        
        # 调用db_client创建集合
        self.db_client.create_collections(collection_configs)

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
        # 构建标签文件路径
        label_file = os.path.join(label_dir, f"{paper_id}.txt")
        topics = []
        
        # 如果文件不存在，尝试使用基本文件名
        if not os.path.exists(label_file):
            base_name = os.path.basename(paper_id)
            label_file = os.path.join(label_dir, f"{base_name}.txt")
        
        # 读取并解析标签文件
        if os.path.exists(label_file):
            with open(label_file, "r", encoding="utf-8") as lf:
                for line in lf:
                    if line.strip().startswith("故该论文的主题关键词总结为["):
                        topics = [x.strip() for x in line.split("[")[-1].split("]")[0].split(",") if x.strip()]
                        break
        
        return topics

    def _map_section_name(self, section_name: str) -> str:
        """
        将章节文件名映射到标准论文部分
        Args:
            section_name: 章节文件名
        Returns:
            映射后的标准部分名称
        """
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
        # 初始化各部分文本
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
            
            # 使用MilvusClient插入数据
            collection_name = self._get_collection_name(section)
            success = self.db_client.insert_data(collection_name, data)
            if success:
                logging.info(f"已入库: {paper_id} {section} ({len(chunks)} 个块)")
            return success
            
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
            try:
                has_txt = any(item.endswith('.txt') and os.path.isfile(os.path.join(dir_path, item)) 
                          for item in os.listdir(dir_path))
            except:
                return
            
            # 如果包含txt文件，认为是论文目录
            if has_txt:
                paper_id = os.path.basename(dir_path)
                paper_dirs.append((paper_id, dir_path))
                return
            
            # 如果是会议目录，更新current_conf
            if current_conf is None:
                current_conf = os.path.basename(dir_path)
            
            # 继续递归子目录
            try:
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    if os.path.isdir(item_path):
                        find_papers(item_path, current_conf)
            except:
                pass
        
        find_papers(root_dir)
        return paper_dirs

    def ingest(self, component_dir: Optional[str] = None, label_dir: Optional[str] = None):
        """
        批量读取论文分段和主题标签，生成embedding并写入Milvus。
        Args:
            component_dir: 论文分段目录，必须通过参数指定
            label_dir: 主题标签目录，必须通过参数指定
        """
        # 确保目录路径已提供
        if not component_dir or not label_dir:
            logging.error("必须提供组件目录和标签目录路径")
            return
        
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
    
    def search_papers(self, query_vector: List[float], section: Optional[str] = None,
                     top_n: int = 5, filter_expr: Optional[str] = None):
        """
        搜索相似论文段落
        Args:
            query_vector: 查询向量
            section: 指定搜索的论文部分，如果为None则搜索所有部分
            top_n: 返回的最大结果数
            filter_expr: 过滤表达式
        Returns:
            匹配结果列表
        """
        # 搜索参数
        params = {"metric_type": "L2", "params": {"nprobe": 10}}
        output_fields = ["text", "paper_id", "section", "topics"]
        
        if section:
            # 搜索指定部分
            collection_name = self._get_collection_name(section)
            return self.db_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                expr=filter_expr,
                output_fields=output_fields,
                top_n=top_n,
                params=params
            )
        else:
            # 搜索所有部分
            collection_names = [self._get_collection_name(sec) for sec in self.section_names]
            return self.db_client.search_multiple_collections(
                collection_names=collection_names,
                query_vector=query_vector,
                expr=filter_expr,
                output_fields=output_fields,
                top_n=top_n,
                params=params
            ) 