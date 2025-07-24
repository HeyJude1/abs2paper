"""
主题词向量数据库同步模块

本模块提供主题词变更与向量数据库的同步功能，支持以下操作：
1. 将主题词变更同步到向量数据库
2. 更新已有论文的主题词标记
3. 维护主题词映射表
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

# 导入主题管理器
from abs2paper.utils.topic_manager import TopicManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VectorDBSynchronizer:
    """向量数据库同步器，负责将主题词变更同步到向量数据库"""
    
    def __init__(self, topic_manager: TopicManager, host: str = 'localhost', port: str = '19530', 
                 db_name: str = 'abs2paper'):
        """
        初始化向量数据库同步器
        
        Args:
            topic_manager: 主题管理器实例
            host: Milvus服务器地址，默认为localhost
            port: Milvus服务器端口，默认为19530
            db_name: 数据库名称，默认为abs2paper
        """
        self.topic_manager = topic_manager
        self.host = host
        self.port = port
        self.alias = 'paper_db'
        self.db_name = db_name
        
        # 标准论文部分映射表（英文名称）
        self.section_name_en = {
            "引言": "introduction",
            "相关工作": "related_work",
            "方法": "methodology",
            "实验评价": "experiments",
            "总结": "conclusion"
        }
        
        # 集合缓存
        self.collections = {}
        self.collections_loaded = False
        
        # 连接到Milvus服务
        self._connect_to_milvus()
    
    def _connect_to_milvus(self) -> bool:
        """
        连接到Milvus服务器
        
        Returns:
            是否连接成功
        """
        try:
            logger.info(f"正在连接到Milvus服务: {self.host}:{self.port}")
            connections.connect(alias=self.alias, host=self.host, port=self.port, db_name=self.db_name)
            
            # 检查连接是否成功
            if utility.has_collection('topic_mappings'):
                logger.info("成功连接到Milvus服务器")
                return True
            else:
                # 尝试创建主题映射集合
                self._setup_topic_mapping_collection()
                return True
                
        except Exception as e:
            logger.error(f"连接到Milvus服务器失败: {e}")
            return False
    
    def _setup_topic_mapping_collection(self) -> Optional[Collection]:
        """
        设置主题词映射集合
        
        Returns:
            创建的集合，如果失败则返回None
        """
        try:
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="old_topic_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="new_topic_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="updated_at", dtype=DataType.VARCHAR, max_length=64)
            ]
            
            schema = CollectionSchema(fields, "topic_mappings collection")
            
            # 检查集合是否已存在
            if utility.has_collection('topic_mappings'):
                logger.info("主题映射集合已存在")
                collection = Collection(name='topic_mappings')
            else:
                logger.info("创建主题映射集合")
                collection = Collection(name='topic_mappings', schema=schema)
            
            return collection
            
        except Exception as e:
            logger.error(f"设置主题映射集合失败: {e}")
            return None
    
    def get_collection_name(self, section: str) -> str:
        """
        生成有效的集合名称（使用英文名称）
        
        Args:
            section: 论文部分名称
            
        Returns:
            有效的集合名称
        """
        section_en = self.section_name_en.get(section, "other")
        return f"paper_{section_en}"
    
    def _load_collections(self) -> bool:
        """
        加载所有集合
        
        Returns:
            是否成功加载
        """
        try:
            # 清空集合缓存
            self.collections = {}
            
            # 对每个标准部分，尝试获取集合
            for section in self.section_name_en.keys():
                collection_name = self.get_collection_name(section)
                
                # 检查集合是否存在
                if utility.has_collection(collection_name):
                    collection = Collection(name=collection_name)
                    self.collections[section] = collection
                    logger.info(f"已加载集合: {collection_name}")
                else:
                    logger.warning(f"集合不存在: {collection_name}")
            
            if self.collections:
                self.collections_loaded = True
                logger.info(f"成功加载 {len(self.collections)} 个集合")
                return True
            else:
                logger.warning("没有找到任何论文集合")
                return False
                
        except Exception as e:
            logger.error(f"加载集合失败: {e}")
            return False
    
    def load_all_collections(self) -> bool:
        """
        加载所有集合到内存中
        
        Returns:
            是否成功加载
        """
        if self.collections_loaded:
            logger.info("集合已经加载到内存")
            return True
        
        # 先加载集合
        if not self._load_collections():
            return False
        
        # 将集合加载到内存
        try:
            logger.info("正在加载所有集合到内存...")
            count = 0
            
            for section, collection in self.collections.items():
                collection.load()
                count += 1
            
            logger.info(f"成功加载 {count} 个集合到内存")
            return True
            
        except Exception as e:
            logger.error(f"将集合加载到内存失败: {e}")
            return False
    
    def search_by_topic_id(self, topic_id: str) -> List[Dict[str, Any]]:
        """
        搜索具有特定主题ID的所有论文
        
        Args:
            topic_id: 主题ID
            
        Returns:
            匹配的论文列表
        """
        # 确保集合已加载
        if not self.collections_loaded:
            self.load_all_collections()
        
        # 获取主题详细信息
        topic_info = self.topic_manager.get_topic_info(topic_id)
        if not topic_info:
            logger.warning(f"主题 {topic_id} 不存在")
            return []
        
        topic_name = f"{topic_info['name_zh']} ({topic_info['name_en']})"
        
        results = []
        
        # 在每个集合中搜索
        for section, collection in self.collections.items():
            try:
                # 构建查询表达式（使用ARRAY包含）
                expr = f'array_contains(topics, "{topic_name}")'
                
                # 执行查询
                output_fields = ["text", "paper_id", "section", "topics"]
                search_results = collection.query(
                    expr=expr,
                    output_fields=output_fields,
                    limit=1000
                )
                
                # 添加到结果列表
                for item in search_results:
                    results.append({
                        "paper_id": item.get("paper_id"),
                        "section": item.get("section"),
                        "topics": item.get("topics", [])
                    })
                    
            except Exception as e:
                logger.error(f"在集合 {section} 中搜索主题 {topic_id} 失败: {e}")
        
        logger.info(f"找到 {len(results)} 个包含主题 {topic_id} 的记录")
        return results
    
    def update_paper_topics(self, paper_id: str, section: str, topics: List[str]) -> bool:
        """
        更新论文的主题词
        
        Args:
            paper_id: 论文ID
            section: 论文部分
            topics: 新的主题词列表
            
        Returns:
            是否成功更新
        """
        # 确保集合已加载
        if not self.collections_loaded:
            self.load_all_collections()
        
        # 检查部分是否有效
        if section not in self.collections:
            logger.warning(f"无效的论文部分: {section}")
            return False
        
        collection = self.collections[section]
        
        try:
            # 构建查询表达式
            expr = f'paper_id == "{paper_id}" && section == "{section}"'
            
            # 执行查询
            results = collection.query(expr=expr, output_fields=["id"])
            
            if not results:
                logger.warning(f"未找到论文 {paper_id} 的 {section} 部分")
                return False
            
            # 将主题ID转换为主题名称
            topic_names = []
            for topic_id in topics:
                topic_info = self.topic_manager.get_topic_info(topic_id)
                if topic_info:
                    topic_name = f"{topic_info['name_zh']} ({topic_info['name_en']})"
                    topic_names.append(topic_name)
            
            # 更新所有匹配的记录
            for item in results:
                entity_id = item.get("id")
                collection.update(
                    expr=f"id == {entity_id}",
                    data={"topics": topic_names}
                )
            
            logger.info(f"已更新论文 {paper_id} 的 {section} 部分，共 {len(results)} 个记录")
            return True
            
        except Exception as e:
            logger.error(f"更新论文 {paper_id} 的主题词失败: {e}")
            return False
    
    def _update_papers_with_topic(self, old_topic_id: str, new_topic_id: str) -> int:
        """
        更新具有特定主题的所有论文
        
        Args:
            old_topic_id: 旧主题ID
            new_topic_id: 新主题ID
            
        Returns:
            更新的记录数量
        """
        # 搜索具有旧主题ID的所有论文
        papers = self.search_by_topic_id(old_topic_id)
        if not papers:
            logger.info(f"没有找到包含主题 {old_topic_id} 的论文")
            return 0
        
        # 获取新旧主题的详细信息
        old_topic = self.topic_manager.get_topic_info(old_topic_id)
        new_topic = self.topic_manager.get_topic_info(new_topic_id)
        
        if not old_topic or not new_topic:
            logger.error(f"获取主题信息失败，old_topic: {old_topic}, new_topic: {new_topic}")
            return 0
        
        # 旧主题名称
        old_topic_name = f"{old_topic['name_zh']} ({old_topic['name_en']})"
        # 新主题名称
        new_topic_name = f"{new_topic['name_zh']} ({new_topic['name_en']})"
        
        # 更新计数
        update_count = 0
        
        # 对每篇论文进行更新
        for paper in papers:
            paper_id = paper.get("paper_id")
            section = paper.get("section")
            topics = paper.get("topics", [])
            
            # 替换旧主题为新主题
            updated_topics = []
            for topic in topics:
                if topic == old_topic_name:
                    # 只有在新主题尚未存在时才添加
                    if new_topic_name not in updated_topics:
                        updated_topics.append(new_topic_name)
                else:
                    updated_topics.append(topic)
            
            # 更新论文的主题
            if self.update_paper_topics(paper_id, section, updated_topics):
                update_count += 1
        
        logger.info(f"已将主题 {old_topic_id} 更新为 {new_topic_id}，共 {update_count}/{len(papers)} 个记录")
        return update_count
    
    def synchronize_topics(self) -> bool:
        """
        同步主题词变更到向量数据库
        
        Returns:
            是否成功同步
        """
        # 获取所有主题词变更
        topic_changes = self.topic_manager.get_topic_changes()
        if not topic_changes:
            logger.info("没有主题词变更需要同步")
            return True
        
        logger.info(f"开始同步 {len(topic_changes)} 个主题词变更")
        
        # 首先更新主题映射集合
        mapping_collection = self._setup_topic_mapping_collection()
        if not mapping_collection:
            logger.error("无法获取主题映射集合")
            return False
        
        # 添加主题映射记录
        from datetime import datetime
        updated_at = datetime.now().isoformat()
        
        try:
            # 准备映射数据
            mapping_data = []
            for old_id, new_id in topic_changes.items():
                mapping_data.append({
                    "old_topic_id": old_id,
                    "new_topic_id": new_id,
                    "updated_at": updated_at
                })
            
            # 插入映射记录
            if mapping_data:
                mapping_collection.insert(mapping_data)
                logger.info(f"已添加 {len(mapping_data)} 条主题映射记录")
        except Exception as e:
            logger.error(f"添加主题映射记录失败: {e}")
        
        # 更新论文主题词
        success_count = 0
        for old_id, new_id in topic_changes.items():
            try:
                update_count = self._update_papers_with_topic(old_id, new_id)
                if update_count > 0:
                    success_count += 1
            except Exception as e:
                logger.error(f"更新主题 {old_id}->{new_id} 的论文失败: {e}")
        
        logger.info(f"成功同步 {success_count}/{len(topic_changes)} 个主题词变更")
        return success_count == len(topic_changes)


# 简单测试函数
def main():
    """测试函数"""
    # 创建主题管理器
    topic_manager = TopicManager()
    
    # 创建向量数据库同步器
    synchronizer = VectorDBSynchronizer(topic_manager)
    
    # 加载集合
    synchronizer.load_all_collections()
    
    # 同步主题词
    synchronizer.synchronize_topics()


if __name__ == "__main__":
    main() 