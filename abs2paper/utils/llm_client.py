"""
LLM客户端工具，负责与SiliconFlow API交互
"""

import os
import requests
import json
import logging
import copy
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)

class LLMClient:
    """LLM客户端，封装SiliconFlow API调用"""
    
    def __init__(self):
        """初始化LLM客户端"""
        self.config = self._load_config()
        
        # 检查是否有API密钥
        if not self.config.get("llm", {}).get("api_key"):
            logger.warning("配置文件中未提供API密钥，将无法使用LLM服务")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        # 使用默认路径
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(module_dir))
        config_path = os.path.join(project_root, "config", "config.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"无法加载配置文件: {str(e)}")
                raise RuntimeError(f"无法加载配置文件: {str(e)}")
        else:
            logger.error(f"配置文件不存在: {config_path}")
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    def get_completion(self, prompt: str) -> Optional[str]:
        """
        向LLM发送请求并获取回复
        
        Args:
            prompt: 提示词
            
        Returns:
            LLM生成的回复文本，如果请求失败则返回None
        """
        if not self.config.get("llm", {}).get("api_key"):
            logger.error("未设置API密钥，无法调用LLM服务")
            return None
        
        try:
            return self._call_siliconflow_api(prompt)
        except Exception as e:
            logger.error(f"调用LLM服务失败: {str(e)}")
            return None
    
    def _call_siliconflow_api(self, prompt: str) -> str:
        """
        调用SiliconFlow API获取响应
        
        Args:
            prompt: 提示词
            
        Returns:
            API响应的文本内容
            
        Raises:
            ValueError: API返回数据不符合预期
            requests.exceptions.RequestException: API请求异常
        """
        llm_config = self.config.get("llm", {})
        request_config = llm_config.get("request", {})
        
        # 从配置中获取URL
        url = request_config.get("url", "https://api.siliconflow.cn/v1/chat/completions")
        
        # 从配置中获取payload并添加prompt
        payload = copy.deepcopy(request_config.get("payload", {}))
        payload["messages"] = [{"role": "user", "content": prompt}]
        
        # 从配置中获取headers并添加认证头
        headers = copy.deepcopy(request_config.get("headers", {}))
        headers["Authorization"] = f"Bearer {llm_config.get('api_key')}"
        
        # 从配置中获取超时时间
        timeout = llm_config.get("timeout", 60)
        
        # 发送请求
        response = requests.request("POST", url, json=payload, headers=headers, timeout=timeout)
        
        if response.status_code != 200:
            raise ValueError(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
        
        response_data = response.json()
        
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError(f"API返回数据不符合预期: {response_data}")
        
        return response_data["choices"][0]["message"]["content"] 

    def get_embedding(self, texts: list) -> list:
        """
        调用SiliconFlow embedding API获取文本嵌入向量，使用批处理方式
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        embedding_config = self.config.get("embedding", {})
        request_config = embedding_config.get("request", {})
        
        url = request_config.get("url", "https://api.siliconflow.cn/v1/embeddings")
        headers = copy.deepcopy(request_config.get("headers", {}))
        api_key = embedding_config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = embedding_config.get("timeout", 30)
        
        # 批处理大小，根据API限制设置
        batch_size = 32
        
        # 计算总批次数
        total_batches = (len(texts) + batch_size - 1) // batch_size
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            # 获取当前批次的文本
            batch_texts = texts[i:i+batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"处理第 {batch_num}/{total_batches} 批，包含 {len(batch_texts)} 个文本")
            
            try:
                payload = copy.deepcopy(request_config.get("payload", {}))
                payload["input"] = batch_texts
                
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    response_data = response.json()
                    batch_embeddings = [item["embedding"] for item in response_data["data"]]
                    all_embeddings.extend(batch_embeddings)
                else:
                    logger.error(f"Embedding API请求失败，状态码: {response.status_code}")
                    return []
                    
            except Exception as e:
                logger.error(f"获取embedding时出错: {str(e)}")
                return []
        
        return all_embeddings 