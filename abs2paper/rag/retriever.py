"""
知识检索模块，负责从向量数据库中检索相关内容
"""

import os
from typing import List, Dict, Any, Optional

from abs2paper.core.db_manager import MilvusManager
from abs2paper.core.embedding import EmbeddingGenerator

class KnowledgeRetriever:
    """知识检索器，负责从向量数据库中检索相关内容"""
    
    def __init__(self, db_manager: Optional[MilvusManager] = None, config_path: str = None):
        """
        初始化知识检索器
        
        Args:
            db_manager: 数据库管理器实例，如果不提供则创建新实例
            config_path: 配置文件路径
        """
        self.db_manager = db_manager if db_manager else MilvusManager(config_path)
        self.embedding_generator = EmbeddingGenerator(config_path)
    
    def search(self, 
              query: str, 
              topic: Optional[str] = None,
              sections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        搜索与查询相关的知识
        
        Args:
            query: 查询文本
            topic: 可选的主题过滤条件
            sections: 要搜索的论文部分，如果不提供则搜索所有部分
            
        Returns:
            搜索结果列表
        """
        # 生成查询嵌入
        query_embedding = self.embedding_generator.generate_embedding(query)
        
        # 从数据库中检索相关内容
        results = self.db_manager.search(
            query_embedding=query_embedding,
            topic=topic,
            sections=sections
        )
        
        return results
    
    def get_display_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        获取用于显示的结果（通常是限制数量的结果）
        
        Args:
            results: 完整的搜索结果
            
        Returns:
            用于显示的结果
        """
        # 使用配置的显示限制来截取结果
        display_limit = self.db_manager.display_limit
        return results[:display_limit]
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """
        格式化单个搜索结果为可读字符串
        
        Args:
            result: 搜索结果
            
        Returns:
            格式化的字符串
        """
        return (f"来源: {result['source']}\n"
                f"部分: {result['section']}\n"
                f"主题: {', '.join(result['topics'])}\n"
                f"距离: {result['distance']:.4f}\n"
                f"内容: {result['content'][:200]}...\n")
    
    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """
        格式化多个搜索结果为可读字符串
        
        Args:
            results: 搜索结果列表
            
        Returns:
            格式化的字符串
        """
        if not results:
            return "未找到相关内容"
        
        formatted = []
        for i, result in enumerate(results):
            formatted.append(f"【结果 {i+1}】\n{self.format_result(result)}")
        
        return "\n".join(formatted) 