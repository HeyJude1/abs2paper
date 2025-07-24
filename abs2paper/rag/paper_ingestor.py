import os
import json
import logging
from typing import Dict, List, Optional
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
        self.milvus_host = self.vector_db_config.get("host", "192.168.70.174")  # 使用配置或默认值
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
                FieldSchema(name="topics", dtype=DataType.ARRAY, max_capacity=10, element_type=DataType.VARCHAR, max_length=64),
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

    def ingest(self, component_dir: Optional[str] = None, label_dir: Optional[str] = None):
        """
        批量读取论文分段和主题标签，生成embedding并写入Milvus。
        Args:
            component_dir: 论文分段目录，默认为项目abs2paper/extraction/result/component_extract
            label_dir: 主题标签目录，默认为项目abs2paper/extraction/result/label
        """
        component_dir = component_dir or os.path.join(self.project_root, "abs2paper", "extraction", "result", "component_extract")
        label_dir = label_dir or os.path.join(self.project_root, "abs2paper", "extraction", "result", "label")
        
        # 章节名称映射表，将文件名映射到预定义的部分
        section_mapping = {
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
        roman_pattern = re.compile(r'^([IVX]+)\.\s+(.+)', re.IGNORECASE)
        
        # 数字章节名正则表达式
        number_pattern = re.compile(r'^(\d+)(\.\d+)?\s+(.+)', re.IGNORECASE)
        
        logging.info(f"开始处理论文目录: {component_dir}")
        logging.info(f"标签目录: {label_dir}")
        
        # 保存处理的论文计数
        processed_count = 0
        
        try:
            # 遍历所有会议目录
            for conf_name in os.listdir(component_dir):
                conf_path = os.path.join(component_dir, conf_name)
                if not os.path.isdir(conf_path):
                    continue
                
                logging.info(f"处理会议: {conf_name}")
                
                # 遍历会议下的年份目录
                for year_dir in os.listdir(conf_path):
                    year_path = os.path.join(conf_path, year_dir)
                    if not os.path.isdir(year_path):
                        continue
                    
                    logging.info(f"处理年份: {year_dir}")
                    
                    # 遍历年份目录下的论文目录
                    for paper_dir in os.listdir(year_path):
                        paper_path = os.path.join(year_path, paper_dir)
                        if not os.path.isdir(paper_path):
                            continue
                        
                        paper_id = paper_dir
                        logging.info(f"处理论文: {paper_id}")
                        
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
                        
                        # 按章节组织的文本内容
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
                            
                            # 提取章节标题，去除罗马数字或数字前缀
                            section_title = section_name.lower()
                            
                            # 尝试匹配罗马数字格式
                            roman_match = roman_pattern.match(section_name)
                            if roman_match:
                                section_title = roman_match.group(2).lower()
                            
                            # 尝试匹配数字格式
                            number_match = number_pattern.match(section_name)
                            if number_match:
                                section_title = number_match.group(3).lower()
                            
                            # 根据章节标题映射到预定义部分
                            mapped_section = None
                            for keyword, target_section in section_mapping.items():
                                if keyword in section_title:
                                    mapped_section = target_section
                                    break
                            
                            # 如果找不到映射，尝试使用一些启发式规则
                            if mapped_section is None:
                                if "i." in section_title or "1." in section_title or "introduction" in section_title:
                                    mapped_section = "引言"
                                elif "ii." in section_title or "2." in section_title or "background" in section_title or "related" in section_title:
                                    mapped_section = "相关工作"
                                elif "iii." in section_title or "3." in section_title or "method" in section_title or "approach" in section_title:
                                    mapped_section = "方法"
                                elif "iv." in section_title or "v." in section_title or "4." in section_title or "5." in section_title or "evaluation" in section_title or "experiment" in section_title:
                                    mapped_section = "实验评价"
                                elif "vi." in section_title or "vii." in section_title or "6." in section_title or "7." in section_title or "conclusion" in section_title or "summary" in section_title:
                                    mapped_section = "总结"
                                else:
                                    # 默认为方法部分
                                    mapped_section = "方法"
                            
                            # 将内容添加到对应部分
                            if mapped_section:
                                section_texts[mapped_section] += section_content + "\n\n"
                        
                        # 对于每个部分，如果有内容，则创建embedding并写入向量数据库
                        has_content = False
                        for section, text in section_texts.items():
                            if not text.strip():
                                continue
                            
                            has_content = True
                            try:
                                collection = self.collections.get(section)
                                if not collection:
                                    collection = self.ensure_collection(section)
                                
                                # 生成embedding
                                embedding = self.llm_client.get_embedding([text])[0]
                                
                                # 主题名映射
                                topic_names = []
                                for topic_id in topics:
                                    topic_info = self.topic_manager.get_topic_info(topic_id)
                                    if topic_info:
                                        topic_names.append(f"{topic_info['name_zh']} ({topic_info['name_en']})")
                                
                                # 插入数据
                                data = {
                                    "paper_id": paper_id,
                                    "section": section,
                                    "text": text[:8000],  # 限制文本长度，避免超出字段限制
                                    "topics": topic_names,
                                    "embedding": embedding
                                }
                                collection.insert([data])
                                logging.info(f"已入库: {paper_id} {section}")
                            except Exception as e:
                                logging.error(f"处理论文 {paper_id} 的 {section} 部分时出错: {str(e)}")
                        
                        if has_content:
                            processed_count += 1
            
            logging.info(f"数据入库完成，共处理了 {processed_count} 篇论文")
        except Exception as e:
            logging.error(f"处理论文数据时出现错误: {str(e)}")
            import traceback
            logging.error(traceback.format_exc()) 