import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

class MilvusClient:
    """通用Milvus向量数据库客户端，处理与向量数据库的所有交互"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化Milvus数据库客户端
        Args:
            config: 配置字典，包含host、port、db_name等参数
        """
        self.config = config or {}
        
        # 从配置中读取Milvus连接参数
        self.host = self.config["host"]           # Milvus服务器地址
        self.port = self.config["port"]           # Milvus服务端口
        self.alias = self.config["alias"]         # 连接别名
        self.db_name = self.config["db_name"]     # 数据库名称
        
        # 初始化集合引用存储
        self.collections = {}
        
        # 连接到Milvus向量数据库
        self._connect_to_milvus()
    
    def _connect_to_milvus(self):
        """连接到Milvus向量数据库"""
        try:
            logging.info(f"正在连接到Milvus服务: {self.host}:{self.port}，数据库: {self.db_name}")
            connections.connect(
                alias=self.alias,
                host=self.host,
                port=self.port,
                db_name=self.db_name
            )
            logging.info("✅ Milvus连接成功")
        except Exception as e:
            logging.error(f"⚠️ 连接Milvus失败: {str(e)}")
            raise
    
    def create_collection(self, collection_name: str, fields: List[FieldSchema], description: str = ""):
        """
        创建单个集合
        Args:
            collection_name: 集合名称
            fields: 字段定义列表
            description: 集合描述
        Returns:
            Collection对象
        """
        try:
            # 检查集合是否存在
            has_collection = utility.has_collection(collection_name, using=self.alias)
            
            if has_collection:
                logging.info(f"集合 '{collection_name}' 已存在，直接获取")
                collection = Collection(name=collection_name, using=self.alias)
            else:
                logging.info(f"创建新集合: '{collection_name}'")
                schema = CollectionSchema(fields, description or f"Collection {collection_name}")
                collection = Collection(name=collection_name, schema=schema, using=self.alias)
            
            # 检查索引
            has_index = False
            try:
                index_info = collection.index()
                has_index = bool(index_info)
            except Exception:
                pass
            
            # 存储集合引用
            self.collections[collection_name] = collection
            return collection
            
        except Exception as e:
            logging.error(f"创建或获取集合 '{collection_name}' 失败: {e}")
            raise
    
    def create_collections(self, collection_configs: List[Dict[str, Any]]):
        """
        批量创建集合
        Args:
            collection_configs: 集合配置列表，每个配置包含name、fields和可选的description
        """
        logging.info("创建和准备集合...")
        
        for config in collection_configs:
            # 获取集合配置
            collection_name = config["name"]              # 集合名称
            fields = config["fields"]                     # 字段定义
            description = config.get("description", "")   # 集合描述
            
            # 创建集合
            collection = self.create_collection(collection_name, fields, description)
            
            # 检查是否需要创建索引
            if "index_field" in config and collection:
                try:
                    has_index = False
                    try:
                        has_index = bool(collection.index())
                    except Exception:
                        pass
                    
                    if not has_index:
                        index_field = config["index_field"]           # 索引字段名
                        index_params = config.get("index_params")     # 索引参数
                        
                        logging.info(f"为集合 '{collection_name}' 创建索引...")
                        collection.create_index(field_name=index_field, index_params=index_params)
                except Exception as e:
                    logging.error(f"为集合 '{collection_name}' 创建索引失败: {e}")
    
    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """
        获取指定名称的集合
        Args:
            collection_name: 集合名称
        Returns:
            Collection对象，如果不存在则返回None
        """
        # 如果已经有引用，直接返回
        if collection_name in self.collections:
            return self.collections[collection_name]
            
        try:
            # 检查集合是否存在
            if utility.has_collection(collection_name, using=self.alias):
                collection = Collection(name=collection_name, using=self.alias)
                self.collections[collection_name] = collection
                return collection
            else:
                logging.warning(f"集合 '{collection_name}' 不存在")
                return None
        except Exception as e:
            logging.error(f"获取集合 '{collection_name}' 时出错: {e}")
            return None
    
    def ensure_collection(self, collection_name: str, fields: List[FieldSchema], 
                          description: str = "", index_field: str = None, 
                          index_params: Dict = None) -> Collection:
        """
        确保指定名称的集合存在，不存在则创建
        Args:
            collection_name: 集合名称
            fields: 字段定义列表
            description: 集合描述
            index_field: 需要建索引的字段名
            index_params: 索引参数
        Returns:
            Collection对象
        """
        try:
            collection = self.get_collection(collection_name)
            
            if not collection:
                # 创建新集合
                schema = CollectionSchema(fields, description or f"Collection {collection_name}")
                collection = Collection(name=collection_name, schema=schema, using=self.alias)
                self.collections[collection_name] = collection
                
                # 创建索引
                if index_field:
                    collection.create_index(field_name=index_field, index_params=index_params)
            
            return collection
            
        except Exception as e:
            logging.error(f"确保集合 {collection_name} 存在时出错: {e}")
            raise
    
    def load_collections(self, collection_names: List[str] = None):
        """
        加载指定集合到内存中，如果不指定则加载所有集合
        Args:
            collection_names: 要加载的集合名称列表，为None时加载所有集合
        """
        if not collection_names:
            collection_names = list(self.collections.keys())
        
        logging.info("正在加载集合到内存...")
        count = 0
        for name in collection_names:
            try:
                if name in self.collections:
                    self.collections[name].load()
                    count += 1
                else:
                    logging.warning(f"集合 '{name}' 不在已知集合列表中")
            except Exception as e:
                logging.error(f"加载集合 '{name}' 失败: {e}")
        
        logging.info(f"✅ 成功加载 {count} 个集合到内存")
    
    def insert_data(self, collection_name: str, data: List[Dict[str, Any]]) -> bool:
        """
        向指定集合中插入数据
        Args:
            collection_name: 集合名称
            data: 要插入的数据列表
        Returns:
            是否成功插入
        """
        try:
            collection = self.get_collection(collection_name)
            if not collection:
                logging.error(f"集合 '{collection_name}' 不存在，无法插入数据")
                return False
                
            if data:
                collection.insert(data)
                logging.info(f"成功向集合 '{collection_name}' 插入 {len(data)} 条数据")
            return True
        except Exception as e:
            logging.error(f"向集合 '{collection_name}' 插入数据时出错: {str(e)}")
            return False
    
    def search(self, collection_name: str, query_vector: List[float], 
              expr: Optional[str] = None, output_fields: List[str] = None,
              top_n: int = 5, params: Dict = None) -> List[Dict]:
        """
        在指定集合中搜索相似向量
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            expr: 过滤表达式
            output_fields: 返回的字段列表
            top_n: 返回的最大结果数
            params: 搜索参数
        Returns:
            匹配结果列表
        """
        collection = self.get_collection(collection_name)
        if not collection:
            logging.error(f"集合 '{collection_name}' 不存在，无法搜索")
            return []
            
        # 设置搜索参数
        search_params = params or {"metric_type": "L2", "params": {"nprobe": 10}}
        output_fields = output_fields or []
        results = []
        
        try:
            # 执行向量搜索
            search_results = collection.search(
                data=[query_vector],
                anns_field="embedding",  # 向量字段名称
                param=search_params,
                limit=top_n,
                expr=expr,
                output_fields=output_fields
            )
            
            # 处理结果
            for hit in search_results[0]:
                result = {"score": hit.score}
                for field in output_fields:
                    result[field] = hit.entity.get(field)
                results.append(result)
            
        except Exception as e:
            logging.error(f"搜索集合 '{collection_name}' 失败: {e}")
        
        return results
    
    def search_multiple_collections(self, collection_names: List[str], query_vector: List[float],
                                   expr: Optional[str] = None, output_fields: List[str] = None,
                                   top_n: int = 5, params: Dict = None) -> List[Dict]:
        """
        在多个集合中搜索相似向量
        Args:
            collection_names: 集合名称列表
            query_vector: 查询向量
            expr: 过滤表达式
            output_fields: 返回的字段列表
            top_n: 返回的最大结果数
            params: 搜索参数
        Returns:
            匹配结果列表
        """
        all_results = []
        
        # 在每个集合中搜索
        for name in collection_names:
            try:
                results = self.search(
                    collection_name=name,
                    query_vector=query_vector,
                    expr=expr,
                    output_fields=output_fields,
                    top_n=top_n,
                    params=params
                )
                
                # 添加集合来源信息
                for result in results:
                    result["collection"] = name
                    all_results.append(result)
                
            except Exception as e:
                logging.error(f"搜索集合 '{name}' 失败: {e}")
        
        # 根据分数排序结果
        all_results.sort(key=lambda x: x["score"])
        return all_results[:top_n]
        
    def list_collections(self) -> List[str]:
        """
        列出当前数据库中的所有集合名称
        Returns:
            集合名称列表
        """
        try:
            return utility.list_collections(using=self.alias)
        except Exception as e:
            logging.error(f"列出集合失败: {e}")
            return []
            
    def drop_collection(self, collection_name: str) -> bool:
        """
        删除指定的集合
        Args:
            collection_name: 集合名称
        Returns:
            是否成功删除
        """
        try:
            if utility.has_collection(collection_name, using=self.alias):
                utility.drop_collection(collection_name, using=self.alias)
                if collection_name in self.collections:
                    del self.collections[collection_name]
                logging.info(f"已删除集合 '{collection_name}'")
                return True
            else:
                logging.warning(f"集合 '{collection_name}' 不存在，无需删除")
                return False
        except Exception as e:
            logging.error(f"删除集合 '{collection_name}' 失败: {e}")
            return False 