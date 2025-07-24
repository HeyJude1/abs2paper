"""
嵌入生成模块，负责文本向量化
"""

import os
import json
import time
import requests
import numpy as np
from typing import List, Dict, Any, Union, Optional

class EmbeddingGenerator:
    """负责生成文本的向量嵌入"""
    
    def __init__(self, config_path: str = None):
        """
        初始化嵌入生成器
        
        Args:
            config_path: 配置文件路径，默认使用项目配置
        """
        self.config = self._load_config(config_path)
        self.embedding_model = self.config["embedding"]["model"]
        self.chunk_size = self.config["embedding"]["chunk_size"]
        self.chunk_overlap = self.config["embedding"]["chunk_overlap"]
    
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
        
        with open(default_config_path, 'r') as f:
            config = json.load(f)
            
        # 尝试加载local.json配置（如果存在）
        local_config_path = os.path.join(
            os.path.dirname(default_config_path),
            "local.json"
        )
        
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
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        生成文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入
        """
        if self.embedding_model == "siliconflow":
            return self._get_embeddings_remote(text)
        else:
            return self._get_embeddings_local(text)
    
    def _get_embeddings_remote(self, text: str) -> List[float]:
        """
        使用SiliconFlow API生成嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入
        """
        api_url = "https://api.siliconflow.cn/v1/embeddings"
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY环境变量未设置")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sf-embedding-2",
            "input": text
        }
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(api_url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                embedding = result["data"][0]["embedding"]
                return embedding
                
            except (requests.exceptions.RequestException, KeyError) as e:
                if attempt < max_retries - 1:
                    print(f"尝试获取嵌入时出错，{retry_delay}秒后重试: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"获取嵌入失败: {str(e)}")
                    # 返回空向量作为备用
                    return [0.0] * self.config["embedding"]["dimension"]
    
    def _get_embeddings_local(self, text: str) -> List[float]:
        """
        使用本地模型生成嵌入（需要安装相关依赖）
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入
        """
        # 这里应该实现本地模型的嵌入生成
        # 目前作为占位符，实际项目中应实现本地模型调用
        print("警告：本地嵌入生成未实现，返回随机向量")
        return list(np.random.randn(self.config["embedding"]["dimension"]))
    
    def chunk_text(self, text: str, paper_id: str) -> List[Dict[str, Any]]:
        """
        将长文本分割成块以便处理
        
        Args:
            text: 长文本内容
            paper_id: 论文ID
            
        Returns:
            包含文本块和元数据的字典列表
        """
        if len(text) <= self.chunk_size:
            return [{
                "content": text,
                "paper_id": paper_id
            }]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # 确定块的结束位置
            end = start + self.chunk_size
            
            # 如果不是最后一块，尝试在一个完整的句子结束处断开
            if end < len(text):
                # 在块大小范围内寻找句号、问号或感叹号作为断点
                for i in range(end-1, start, -1):
                    if text[i] in ['.', '?', '!', '。', '？', '！'] and i+1 < len(text) and text[i+1] in [' ', '\n', '\t']:
                        end = i + 1
                        break
            else:
                end = min(end, len(text))
            
            chunks.append({
                "content": text[start:end],
                "paper_id": paper_id
            })
            
            # 下一块的起始位置（考虑重叠）
            start = end - self.chunk_overlap
        
        return chunks 