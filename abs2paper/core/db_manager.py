"""
数据库管理模块，负责与Milvus向量数据库的交互
"""

import os
import json
import time
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple

from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection, utility
)

class MilvusManager:
    """Milvus向量数据库管理类"""
    
    def __init__(self, config_path: str = None):
        """
        初始化Milvus数据库管理器
        
        Args:
            config_path: 配置文件路径，默认使用项目配置
        """
        self.config = self._load_config(config_path)
        self.uri = self.config["database"]["uri"]
        self.collection_prefix = self.config["database"]["collection_prefix"]
        self.dimension = self.config["embedding"]["dimension"]
        self.search_limit = self.config["database"]["search_limit"]
        self.display_limit = self.config["database"]["display_limit"]
        
        self._connect_to_milvus()
        self._collections = {}
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
                
        # 使用默认配置
        default_config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "default.json"
        )
        
        # 尝试加载local.json配置（如果存在）
        local_config_path = os.path.join(
            os.path.dirname(default_config_path),
            "local.json"
        )
        
        with open(default_config_path, 'r') as f:
            config = json.load(f)
            
        # 合并本地配置（如果存在）
        if os.path.exists(local_config_path):
            with open(local_config_path, 'r') as f:
                local_config = json.load(f)
                self._merge_configs(config, local_config)
                
        return config
    
    def _merge_configs(self, base_config: Dict, override_config: Dict) -> None:
        """合并配置，将override_config合并到base_config"""
        for key, value in override_config.items():
            if isinstance(value, dict) and key in base_config and isinstance(base_config[key], dict):
                self._merge_configs(base_config[key], value)
            else:
                base_config[key] = value
    
    def _connect_to_milvus(self) -> None:
        """连接到Milvus服务器"""
        connections.connect("default", uri=self.uri)
        print(f"Connected to Milvus server at {self.uri}")
    
    def create_collection(self, section: str) -> Collection:
        """
        创建集合（如果不存在）
        
        Args:
            section: 论文部分（用于命名集合）
            
        Returns:
            创建的集合对象
        """
        collection_name = f"{self.collection_prefix}{section}"
        
        # 检查集合是否已存在
        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            collection.load()
            self._collections[section] = collection
            print(f"Collection {collection_name} already exists, loaded")
            return collection
        
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="paper_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="topics", dtype=DataType.ARRAY, dtype_params={'element_type': DataType.VARCHAR, 'max_capacity': 20}),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        
        # 创建集合
        schema = CollectionSchema(fields)
        collection = Collection(collection_name, schema)
        
        # 创建索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64}
        }
        collection.create_index("embedding", index_params)
        collection.load()
        
        self._collections[section] = collection
        print(f"Created collection {collection_name}")
        return collection
    
    def create_collections(self, sections: List[str]) -> None:
        """为多个部分创建集合"""
        for section in sections:
            self.create_collection(section)
    
    def store_data(self, data: Dict[str, Any]) -> None:
        """
        存储数据到向量数据库
        
        Args:
            data: 包含以下字段的数据字典:
                section: 论文部分
                paper_id: 论文ID
                content: 文本内容
                topics: 主题列表
                source: 来源
                embedding: 向量嵌入
        """
        section = data["section"]
        
        # 确保集合已创建
        if section not in self._collections:
            self.create_collection(section)
        
        collection = self._collections[section]
        
        # 准备插入数据
        insert_data = {
            "paper_id": [data["paper_id"]],
            "content": [data["content"]],
            "topics": [data["topics"]],
            "source": [data["source"]],
            "section": [data["section"]],
            "embedding": [data["embedding"]]
        }
        
        # 插入数据
        collection.insert(insert_data)
        print(f"Inserted data into {collection.name}")
    
    def search(self, 
              query_embedding: List[float], 
              topic: Optional[str] = None,
              sections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        在向量数据库中搜索
        
        Args:
            query_embedding: 查询向量
            topic: 可选的主题过滤条件
            sections: 要搜索的部分，默认搜索所有已创建的集合
            
        Returns:
            搜索结果列表
        """
        sections = sections or list(self._collections.keys())
        all_results = []
        
        for section in sections:
            if section not in self._collections:
                print(f"Collection for section '{section}' not found, skipping")
                continue
                
            collection = self._collections[section]
            
            # 构建搜索表达式
            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 64}
            }
            
            expr = None
            if topic:
                expr = f"array_contains(topics, '{topic}')"
            
            # 执行搜索
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=self.search_limit,
                expr=expr,
                output_fields=["paper_id", "content", "topics", "source", "section"]
            )
            
            # 处理搜索结果
            for hits in results:
                for hit in hits:
                    result = {
                        "id": hit.id,
                        "distance": hit.distance,
                        "paper_id": hit.entity.get("paper_id"),
                        "content": hit.entity.get("content"),
                        "topics": hit.entity.get("topics"),
                        "source": hit.entity.get("source"),
                        "section": hit.entity.get("section")
                    }
                    all_results.append(result)
        
        # 按距离排序
        all_results.sort(key=lambda x: x["distance"], reverse=True)
        
        # 去除重复内容
        unique_results = []
        seen_contents = set()
        
        for result in all_results:
            content_key = (result["content"], result["source"], result["section"])
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_results.append(result)
        
        return unique_results[:self.search_limit]
    
    def load_all_collections(self) -> None:
        """加载所有可用的集合到内存"""
        collections = utility.list_collections()
        prefix_len = len(self.collection_prefix)
        
        for collection_name in collections:
            if collection_name.startswith(self.collection_prefix):
                section = collection_name[prefix_len:]
                collection = Collection(collection_name)
                collection.load()
                self._collections[section] = collection
                print(f"Loaded collection {collection_name}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取所有集合的统计信息"""
        stats = {}
        
        for section, collection in self._collections.items():
            stats[section] = {
                "name": collection.name,
                "entity_count": collection.num_entities,
                "in_memory": collection.is_loaded
            }
            
        return stats 