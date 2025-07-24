"""
LLM客户端模块，负责与语言模型API通信
"""

import os
import json
import time
import requests
import subprocess
from typing import Dict, Any, List, Optional, Union

class LLMClient:
    """LLM客户端类，用于与不同的LLM提供商通信"""
    
    def __init__(self, config_path: str = None):
        """
        初始化LLM客户端
        
        Args:
            config_path: 配置文件路径，默认使用项目配置
        """
        self.config = self._load_config(config_path)
        self.provider = self.config["llm"]["provider"]
        self.model = self.config["llm"]["model"]
        self.temperature = self.config["llm"]["temperature"]
        self.max_tokens = self.config["llm"]["max_tokens"]
        self.timeout = self.config["llm"]["timeout"]
    
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
    
    def generate_response(self, prompt: str) -> str:
        """
        根据提示生成响应
        
        Args:
            prompt: 输入提示
            
        Returns:
            LLM生成的响应
        """
        if self.provider == "siliconflow":
            return self._generate_siliconflow(prompt)
        elif self.provider == "ollama":
            return self._generate_ollama(prompt)
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")
    
    def _generate_siliconflow(self, prompt: str) -> str:
        """
        使用SiliconFlow API生成响应
        
        Args:
            prompt: 输入提示
            
        Returns:
            生成的响应
        """
        api_url = "https://api.siliconflow.cn/v1/chat/completions"
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY环境变量未设置")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    api_url, 
                    headers=headers, 
                    json=data, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                message = result["choices"][0]["message"]["content"]
                return message
                
            except (requests.exceptions.RequestException, KeyError, IndexError) as e:
                if attempt < max_retries - 1:
                    print(f"尝试获取响应时出错，{retry_delay}秒后重试: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    error_message = f"获取响应失败: {str(e)}"
                    print(error_message)
                    return f"发生错误: {error_message}"
    
    def _generate_ollama(self, prompt: str) -> str:
        """
        使用本地Ollama生成响应
        
        Args:
            prompt: 输入提示
            
        Returns:
            生成的响应
        """
        try:
            command = [
                "curl", "-s",
                "http://localhost:11434/api/generate",
                "-d", json.dumps({
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": self.temperature,
                })
            ]
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=self.timeout)
            
            if process.returncode != 0:
                error_message = f"Ollama请求失败: {stderr.decode('utf-8')}"
                print(error_message)
                return f"发生错误: {error_message}"
            
            response = json.loads(stdout)
            return response.get("response", "无响应")
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
            error_message = f"Ollama请求异常: {str(e)}"
            print(error_message)
            return f"发生错误: {error_message}"
            
    def save_prompt(self, prompt: str, path: str = None) -> None:
        """
        保存提示到文件，用于调试和审查
        
        Args:
            prompt: 提示内容
            path: 保存路径，如果不提供则使用默认路径
        """
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "prompt"
            )
            
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # 添加时间戳
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        with open(f"{path}_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(prompt) 