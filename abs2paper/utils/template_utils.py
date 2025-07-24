"""
模板处理工具模块，提供占位符替换等通用功能
"""

from typing import Dict, Any, Mapping


def replace_placeholders(obj: Any, replacements: Dict[str, str]) -> Any:
    """
    递归替换对象中的占位符
    
    Args:
        obj: 要处理的对象(字典、列表、字符串等)
        replacements: 替换映射，键为占位符，值为替换内容
        
    Returns:
        处理后的对象
    """
    if isinstance(obj, dict):
        return {k: replace_placeholders(v, replacements) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_placeholders(item, replacements) for item in obj]
    elif isinstance(obj, str):
        result = obj
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result
    else:
        return obj


def create_llm_replacements(prompt: str, api_key: str) -> Dict[str, str]:
    """
    创建LLM API调用所需的替换映射
    
    Args:
        prompt: 提示词
        api_key: API密钥
        
    Returns:
        替换映射字典
    """
    return {
        "${prompt}": prompt,
        "${api_key}": api_key
    } 