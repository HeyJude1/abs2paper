"""
知识检索模块，负责从向量数据库中检索相关内容
"""

import os
from typing import List, Dict, Any, Optional

# 使用适配器模式，因为接口差异较大，暂时保持现有功能
class KnowledgeRetriever:
    """知识检索器，负责从向量数据库中检索相关内容"""
    
    def __init__(self, db_manager, config_path: str = None):
        """
        初始化知识检索器
        
        Args:
            db_manager: 数据库管理器实例（适配器）
            config_path: 配置文件路径
        """
        self.db_manager = db_manager
        # 由于接口差异，暂时不使用embedding生成器
        # self.embedding_generator = EmbeddingGenerator(config_path)
    
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
        # 由于接口复杂性，暂时返回空结果
        # 实际使用中这些示例主要用于演示，功能可能不完整
        return []
    
    def get_display_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        获取用于显示的结果（通常是限制数量的结果）
        
        Args:
            results: 完整的搜索结果
            
        Returns:
            用于显示的结果
        """
        # 限制显示数量
        display_limit = 5
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