"""
提示词构建模块，负责构建不同场景的提示词
"""

import os
import json
from typing import List, Dict, Any, Optional

class PromptBuilder:
    """提示词构建器，用于生成不同场景的提示词"""
    
    def __init__(self, config_path: str = None):
        """
        初始化提示词构建器
        
        Args:
            config_path: 配置文件路径，默认使用项目配置
        """
        self.templates = self._load_templates(config_path)
    
    def _load_templates(self, config_path: str = None) -> Dict[str, str]:
        """加载提示词模板"""
        templates = {
            "qa": self._get_qa_template(),
            "summary": self._get_summary_template(),
            "translation": self._get_translation_template(),
            "comparison": self._get_comparison_template()
        }
        
        # 如果有外部配置的模板，加载它们
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    custom_templates = json.load(f)
                templates.update(custom_templates)
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载自定义模板失败: {str(e)}")
        
        return templates
    
    def _get_qa_template(self) -> str:
        """问答提示词模板"""
        return """你是一个专业的学术顾问，帮助用户回答关于论文的问题。

请基于以下检索到的内容来回答用户的问题。如果检索内容无法回答问题，请明确说明。

### 检索到的内容：

{{retrieved_content}}

### 用户问题：

{{query}}

### 指令：

1. 根据检索内容提供准确且有深度的回答
2. 引用检索内容中的具体信息，说明来自哪个文档
3. 如果检索内容不足以回答问题，清楚地说明这一点
4. 保持客观学术风格，避免主观判断
5. 回答必须是中文

### 你的回答：
"""
    
    def _get_summary_template(self) -> str:
        """摘要提示词模板"""
        return """你是一个专业的学术顾问，擅长总结论文内容。

请基于以下检索到的内容，提供一份全面的摘要。

### 检索到的内容：

{{retrieved_content}}

### 指令：

1. 提供一个500字左右的摘要，涵盖主要观点和结论
2. 保持客观学术风格，避免主观判断
3. 突出论文的创新点和研究价值
4. 包含论文的研究方法和主要发现
5. 摘要必须是中文

### 你的摘要：
"""
    
    def _get_translation_template(self) -> str:
        """翻译提示词模板"""
        return """你是一个专业的学术翻译，擅长翻译学术文献。

请将以下检索到的英文内容翻译成中文。

### 原文内容：

{{retrieved_content}}

### 指令：

1. 提供准确的中文翻译
2. 保持学术风格和专业术语的准确性
3. 维持原文的段落结构
4. 保留引用和参考文献的原始信息
5. 对于专业术语，可以在括号中保留英文原文

### 你的翻译：
"""
    
    def _get_comparison_template(self) -> str:
        """比较提示词模板"""
        return """你是一个专业的学术顾问，擅长比较不同论文或观点。

请基于以下检索到的内容，比较不同的观点或方法。

### 检索到的内容：

{{retrieved_content}}

### 比较主题：

{{query}}

### 指令：

1. 系统性地比较检索内容中的不同观点或方法
2. 分析各个观点/方法的优缺点
3. 指出它们的共同点和差异
4. 客观评估各观点/方法的适用场景
5. 回答必须是中文

### 你的比较分析：
"""
    
    def build_qa_prompt(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        构建问答提示词
        
        Args:
            results: 检索到的知识结果
            query: 用户查询
            
        Returns:
            构建的提示词
        """
        retrieved_content = self._format_retrieved_content(results)
        return self.templates["qa"].replace("{{retrieved_content}}", retrieved_content).replace("{{query}}", query)
    
    def build_summary_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        构建摘要提示词
        
        Args:
            results: 检索到的知识结果
            
        Returns:
            构建的提示词
        """
        retrieved_content = self._format_retrieved_content(results)
        return self.templates["summary"].replace("{{retrieved_content}}", retrieved_content)
    
    def build_translation_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        构建翻译提示词
        
        Args:
            results: 检索到的知识结果
            
        Returns:
            构建的提示词
        """
        retrieved_content = self._format_retrieved_content(results)
        return self.templates["translation"].replace("{{retrieved_content}}", retrieved_content)
    
    def build_comparison_prompt(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        构建比较提示词
        
        Args:
            results: 检索到的知识结果
            query: 比较主题
            
        Returns:
            构建的提示词
        """
        retrieved_content = self._format_retrieved_content(results)
        return self.templates["comparison"].replace("{{retrieved_content}}", retrieved_content).replace("{{query}}", query)
    
    def _format_retrieved_content(self, results: List[Dict[str, Any]]) -> str:
        """
        格式化检索到的内容
        
        Args:
            results: 检索到的知识结果
            
        Returns:
            格式化后的内容字符串
        """
        content = ""
        for i, result in enumerate(results):
            content += f"【文档{i+1}】\n"
            content += f"来源：{result['source']}\n"
            content += f"部分：{result['section']}\n"
            content += f"内容：{result['content']}\n\n"
        
        return content 