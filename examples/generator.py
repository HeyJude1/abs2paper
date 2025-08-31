"""
回答生成模块，负责根据检索到的内容生成回答
"""

import os
from typing import List, Dict, Any, Optional

from abs2paper.core.llm_client import LLMClient

class ResponseGenerator:
    """回答生成器，负责根据检索到的内容生成回答"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, config_path: str = None):
        """
        初始化回答生成器
        
        Args:
            llm_client: LLM客户端实例，如果不提供则创建新实例
            config_path: 配置文件路径
        """
        self.llm_client = llm_client if llm_client else LLMClient(config_path)
    
    def generate(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        根据检索结果生成回答
        
        Args:
            results: 检索到的知识结果
            query: 用户查询
            
        Returns:
            生成的回答
        """
        # 构建提示词
        prompt = self._build_prompt(results, query)
        
        # 保存提示词用于调试
        self.llm_client.save_prompt(prompt)
        
        # 生成回答
        response = self.llm_client.generate_response(prompt)
        
        return response
    
    def _build_prompt(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        构建提示词
        
        Args:
            results: 检索到的知识结果
            query: 用户查询
            
        Returns:
            构建的提示词
        """
        prompt = "你是一个专业的学术顾问，帮助用户回答关于论文的问题。\n\n"
        prompt += "请基于以下检索到的内容来回答用户的问题。如果检索内容无法回答问题，请明确说明。\n\n"
        
        # 添加检索到的内容
        prompt += "### 检索到的内容：\n\n"
        
        for i, result in enumerate(results):
            prompt += f"【文档{i+1}】\n"
            prompt += f"来源：{result['source']}\n"
            prompt += f"部分：{result['section']}\n"
            prompt += f"内容：{result['content']}\n\n"
        
        # 添加用户问题
        prompt += f"### 用户问题：\n\n{query}\n\n"
        
        # 添加回答指令
        prompt += "### 指令：\n\n"
        prompt += "1. 根据检索内容提供准确且有深度的回答\n"
        prompt += "2. 引用检索内容中的具体信息，说明来自哪个文档\n"
        prompt += "3. 如果检索内容不足以回答问题，清楚地说明这一点\n"
        prompt += "4. 保持客观学术风格，避免主观判断\n"
        prompt += "5. 回答必须是中文\n\n"
        
        prompt += "### 你的回答：\n"
        
        return prompt 