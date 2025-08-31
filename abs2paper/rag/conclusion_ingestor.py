import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from pymilvus import FieldSchema, DataType

from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.db_client import MilvusClient
from abs2paper.utils.topic_manager import TopicManager

class ConclusionIngestor:
    """
    论文总结数据入库工具：将论文10个方面的总结生成embedding后写入Milvus
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化ConclusionIngestor，加载配置、初始化LLMClient和MilvusClient
        Args:
            config_path: 配置文件路径，默认为项目config/config.json
        """
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 初始化工具类
        self.llm_client = LLMClient()
        self.topic_manager = TopicManager()
        
        # 读取数据库配置
        vector_db_config = self.config["vector_db"]
        self.embedding_dim = vector_db_config["embedding_dim"]
        
        # 10个总结类型对应的collection名称
        self.summary_types = [
            "Background", "RelatedWork", "Challenges", "Innovations", 
            "Methodology", "ExpeDesign", "Baseline", "Metric", 
            "ResultAnalysis", "Conclusion"
        ]
        
        # 初始化Milvus客户端
        db_config = {
            "host": vector_db_config["host"],
            "port": vector_db_config["port"],
            "alias": vector_db_config["alias"],
            "db_name": vector_db_config["db_name"]
        }
        self.db_client = MilvusClient(db_config)
        
        # 创建总结集合
        self._create_summary_collections()

    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _get_summary_collection_name(self, summary_type: str) -> str:
        """获取总结类型对应的collection名称"""
        return f"summary_{summary_type.lower()}"
    
    def _create_summary_field_schema(self) -> List[FieldSchema]:
        """创建总结collection的字段模式"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="paper_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="summary_text", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="source_sections", dtype=DataType.ARRAY, 
                       max_capacity=5, element_type=DataType.VARCHAR, max_length=32),
            FieldSchema(name="topics", dtype=DataType.ARRAY, 
                       max_capacity=10, element_type=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        ]
        return fields
    
    def _create_summary_collections(self):
        """创建10个总结类型的collection"""
        collection_configs = []
        fields = self._create_summary_field_schema()
        
        # 为每个总结类型创建collection配置
        for summary_type in self.summary_types:
            collection_name = self._get_summary_collection_name(summary_type)
            collection_configs.append({
                "name": collection_name,
                "fields": fields,
                "description": f"Collection for {summary_type} summaries",
                "index_field": "embedding",
                "index_params": {
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                    "metric_type": "L2"
                }
            })
        
        # 调用db_client创建集合
        self.db_client.create_collections(collection_configs)

    def _load_paper_summary_metadata(self, paper_path: str) -> Optional[Dict]:
        """加载论文总结的元数据文件"""
        summary_file = os.path.join(paper_path, "summary.json")
        if not os.path.exists(summary_file):
            logging.warning(f"总结元数据文件不存在: {summary_file}")
            return None
        
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载总结元数据失败: {e}")
            return None
    
    def _load_summary_content(self, paper_path: str, summary_type: str) -> Optional[str]:
        """加载指定类型的总结内容"""
        summary_file = os.path.join(paper_path, f"{summary_type}.txt")
        if not os.path.exists(summary_file):
            logging.warning(f"总结文件不存在: {summary_file}")
            return None
        
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logging.error(f"加载总结内容失败: {e}")
            return None
    
    def _get_source_sections_from_conclude_aspects(self, summary_type: str) -> List[str]:
        """基于CONCLUDE_ASPECTS获取总结类型对应的源章节"""
        conclude_aspects = self.config["paper"]["conclude_aspects"]
        return conclude_aspects.get(summary_type, [])
    
    def _extract_topics_from_original_paper(self, paper_id: str) -> List[str]:
        """从标签文件中提取论文的主题标签"""
        # 从配置文件获取label目录路径
        data_paths = self.config["data_paths"]
        label_path = data_paths["label"]["path"].lstrip('/')
        label_dir = os.path.join(self.project_root, label_path)
        
        return self._extract_topics_from_file(paper_id, label_dir)
    
    def _extract_topics_from_file(self, paper_id: str, label_dir: str) -> List[str]:
        """
        从标签文件中提取主题关键词，支持嵌套目录结构查找
        Args:
            paper_id: 论文ID
            label_dir: 标签目录
        Returns:
            提取的主题关键词列表
        """
        topics = []
        
        # 尝试多种文件名格式
        possible_names = [
            paper_id,  # 完整的paper_id
            os.path.basename(paper_id),  # 只取文件名部分
            paper_id.replace('/', '_'),  # 替换路径分隔符
        ]
        
        # 在整个目录树中递归查找匹配的文件
        for root, dirs, files in os.walk(label_dir):
            for filename in files:
                if filename.endswith('.txt'):
                    # 去掉扩展名
                    base_filename = filename[:-4]
                    
                    # 检查是否匹配任一可能的名称
                    for possible_name in possible_names:
                        if base_filename == possible_name:
                            label_file = os.path.join(root, filename)
                            topics = self._read_topics_from_file(label_file)
                            if topics:  # 找到有效主题就返回
                                logging.info(f"论文 {paper_id} 找到标签文件: {label_file}")
                                return topics
        
        # 如果没有找到任何匹配的文件，记录详细信息用于调试
        logging.warning(f"论文 {paper_id} 未找到对应的标签文件，尝试过的名称: {possible_names}")
        return topics
    
    def _read_topics_from_file(self, label_file: str) -> List[str]:
        """
        从标签文件中读取主题关键词
        Args:
            label_file: 标签文件路径
        Returns:
            主题关键词列表
        """
        topics = []
        try:
            with open(label_file, "r", encoding="utf-8") as lf:
                content = lf.read()
                # 查找主题关键词行
                for line in content.split('\n'):
                    if "故该论文的主题关键词总结为[" in line:
                        # 提取括号内的内容
                        start_idx = line.find('[')
                        end_idx = line.find(']')
                        if start_idx != -1 and end_idx != -1:
                            topics_str = line[start_idx+1:end_idx]
                            topics = [x.strip() for x in topics_str.split(",") if x.strip()]
                        break
        except Exception as e:
            logging.error(f"读取标签文件 {label_file} 时出错: {e}")
        
        return topics
    
    def _process_single_summary(self, paper_id: str, summary_type: str, 
                              summary_content: str, topics: List[str]) -> bool:
        """处理单个总结，生成embedding并入库"""
        try:
            # 生成嵌入向量
            embedding = self.llm_client.get_embedding([summary_content])[0]
            
            # 获取源章节信息
            source_sections = self._get_source_sections_from_conclude_aspects(summary_type)
            
            # 构建插入数据
            data = [{
                "paper_id": paper_id,  # 不添加后缀，使用基础paper_id
                "summary_text": summary_content[:8192],  # 限制长度
                "source_sections": source_sections,
                "topics": topics,
                "embedding": embedding
            }]
            
            # 插入到对应的collection
            collection_name = self._get_summary_collection_name(summary_type)
            success = self.db_client.insert_data(collection_name, data)
            
            if success:
                logging.info(f"已入库: {paper_id} {summary_type} 总结")
            
            return success
            
        except Exception as e:
            logging.error(f"处理 {paper_id} 的 {summary_type} 总结时出错: {e}")
            return False
    
    def _process_single_paper_summaries(self, paper_id: str, paper_path: str) -> bool:
        """处理单篇论文的所有总结"""
        logging.info(f"处理论文总结: {paper_id}")
        
        # 加载总结元数据
        metadata = self._load_paper_summary_metadata(paper_path)
        if not metadata:
            return False
        
        # 提取论文主题
        topics = self._extract_topics_from_original_paper(paper_id)
        if not topics:
            logging.warning(f"论文 {paper_id} 无主题信息，使用空列表")
            topics = []
        
        # 主题名映射
        topic_names = []
        for topic_id in topics:
            topic_info = self.topic_manager.get_topic_info(topic_id)
            if topic_info:
                topic_names.append(f"{topic_info['name_zh']} ({topic_info['name_en']})")
        
        if topic_names:
            logging.info(f"论文 {paper_id} 主题标签: {topic_names}")
        else:
            logging.warning(f"论文 {paper_id} 无法获取有效的主题名称")
            topic_names = []
        
        # 处理每个总结类型
        success_count = 0
        completed_aspects = metadata.get("completed_aspects", [])
        
        for summary_type in completed_aspects:
            # 加载总结内容
            summary_content = self._load_summary_content(paper_path, summary_type)
            if not summary_content:
                continue
            
            # 处理并入库
            if self._process_single_summary(paper_id, summary_type, summary_content, topic_names):
                success_count += 1
        
        logging.info(f"论文 {paper_id} 成功处理 {success_count}/{len(completed_aspects)} 个总结")
        return success_count > 0
    
    def _find_summary_directories(self, root_dir: str) -> List[Tuple[str, str]]:
        """递归查找包含总结文件的目录"""
        summary_dirs = []
        
        def find_summaries(dir_path):
            try:
                # 检查是否包含summary.json文件
                summary_json = os.path.join(dir_path, "summary.json")
                if os.path.exists(summary_json):
                    paper_id = os.path.basename(dir_path)
                    summary_dirs.append((paper_id, dir_path))
                    return
                
                # 继续递归子目录
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    if os.path.isdir(item_path):
                        find_summaries(item_path)
            except:
                pass
        
        find_summaries(root_dir)
        return summary_dirs
    
    def ingest(self, conclude_result_dir: Optional[str] = None):
        """批量读取论文总结并写入Milvus"""
        # 使用配置中的路径或参数指定的路径
        if not conclude_result_dir:
            conclude_path = self.config["data_paths"]["conclude_result"]["path"].lstrip('/')
            conclude_result_dir = os.path.join(self.project_root, conclude_path)
        
        if not os.path.exists(conclude_result_dir):
            logging.error(f"总结目录不存在: {conclude_result_dir}")
            return
        
        logging.info(f"开始处理总结目录: {conclude_result_dir}")
        
        # 查找所有总结目录
        summary_directories = self._find_summary_directories(conclude_result_dir)
        logging.info(f"找到 {len(summary_directories)} 个总结目录")
        
        # 处理每个总结目录
        processed_count = 0
        for paper_id, paper_path in summary_directories:
            if self._process_single_paper_summaries(paper_id, paper_path):
                processed_count += 1
        
        logging.info(f"总结入库完成，共处理了 {processed_count} 篇论文的总结")
    
    def get_complete_section_content(self, paper_id: str, section_name: str) -> List[str]:
        """
        根据paper_id和章节名称获取完整的章节内容
        将chunks按顺序拼接成完整章节
        """
        # 根据章节名称确定要查询的collection
        collection_mapping = {
            "引言": "paper_introduction",
            "相关工作": "paper_related_work", 
            "方法": "paper_methodology",
            "实验评价": "paper_experiments",
            "总结": "paper_conclusion"
        }
        
        collection_name = collection_mapping.get(section_name)
        if not collection_name:
            logging.warning(f"未知的章节名称: {section_name}")
            return []
        
        try:
            # 查询所有匹配的chunks
            query_filter = f"paper_id like '{paper_id}_%'"
            
            results = self.db_client.query(
                collection_name=collection_name,
                filter=query_filter,
                output_fields=["paper_id", "text"],
                limit=100
            )
            
            if not results:
                logging.warning(f"未找到论文 {paper_id} 的 {section_name} 章节内容")
                return []
            
            # 按paper_id后缀排序，确保chunks顺序正确
            sorted_results = sorted(results, key=lambda x: int(x['paper_id'].split('_')[-1]))
            
            # 提取并拼接文本内容
            section_chunks = [result['text'] for result in sorted_results]
            
            logging.info(f"获取到论文 {paper_id} 的 {section_name} 章节，共 {len(section_chunks)} 个chunks")
            return section_chunks
            
        except Exception as e:
            logging.error(f"获取章节内容失败: {paper_id}, {section_name}, 错误: {e}")
            return [] 