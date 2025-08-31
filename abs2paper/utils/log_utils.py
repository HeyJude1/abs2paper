"""
日志工具模块，提供日志管理和markdown保存功能
"""

import os
import io
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class DualHandler(logging.Handler):
    """双重日志处理器，同时输出到控制台和字符串缓冲区"""
    
    def __init__(self, stream_handler: logging.Handler, string_buffer: io.StringIO):
        """
        初始化双重处理器
        
        Args:
            stream_handler: 流处理器（控制台输出）
            string_buffer: 字符串缓冲区
        """
        super().__init__()
        self.stream_handler = stream_handler
        self.string_buffer = string_buffer
    
    def emit(self, record):
        """发送日志记录"""
        # 输出到控制台
        self.stream_handler.emit(record)
        # 保存到字符串缓冲区
        log_entry = self.format(record)
        self.string_buffer.write(log_entry + '\n')


class LogMarkdownSaver:
    """日志markdown保存器"""
    
    def __init__(self, output_dir: str, log_buffer: io.StringIO):
        """
        初始化markdown保存器
        
        Args:
            output_dir: 输出目录
            log_buffer: 日志缓冲区
        """
        self.output_dir = output_dir
        self.log_buffer = log_buffer
        
        # 只有在输出目录不为空时才创建目录
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
    
    def save_log_to_markdown(self, 
                           title: str = "处理日志",
                           config_info: Optional[Dict[str, Any]] = None,
                           summary_info: Optional[str] = None) -> bool:
        """
        将控制台输出保存为markdown文件
        
        Args:
            title: markdown文档标题
            config_info: 配置信息字典
            summary_info: 总结信息
            
        Returns:
            是否保存成功
        """
        try:
            # 检查输出目录是否已设置
            if not self.output_dir:
                logging.error("❌ 输出目录未设置，无法保存日志")
                return False
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"log_{timestamp}.md"
            log_filepath = os.path.join(self.output_dir, log_filename)
            
            # 获取日志内容
            log_content = self.log_buffer.getvalue()
            
            # 构建markdown内容
            markdown_content = f"""# {title}

## 处理时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
            
            # 添加配置信息（如果提供）
            if config_info:
                markdown_content += "\n## 配置信息\n"
                for key, value in config_info.items():
                    markdown_content += f"- **{key}**: {value}\n"
            
            # 添加处理日志
            markdown_content += f"""
## 处理日志

```
{log_content}
```
"""
            
            # 添加总结信息（如果提供）
            if summary_info:
                markdown_content += f"""
## 总结
{summary_info}
"""
            
            # 保存markdown文件
            with open(log_filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 使用标准的logging而不是logger实例
            logging.info(f"📝 处理日志已保存至: {log_filepath}")
            return True
            
        except Exception as e:
            logging.error(f"❌ 保存日志时出错: {e}")
            return False


def setup_dual_logging(log_level: int = logging.INFO) -> tuple[io.StringIO, LogMarkdownSaver]:
    """
    设置双重日志系统
    
    Args:
        log_level: 日志级别
        
    Returns:
        (log_buffer, markdown_saver): 日志缓冲区和markdown保存器的元组
    """
    # 创建字符串缓冲区和流处理器
    log_buffer = io.StringIO()
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 为流处理器设置格式化器
    stream_handler.setFormatter(formatter)
    
    # 创建双重处理器
    dual_handler = DualHandler(stream_handler, log_buffer)
    dual_handler.setFormatter(formatter)
    
    # 清除现有的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置日志配置
    root_logger.setLevel(log_level)
    root_logger.addHandler(dual_handler)
    
    # 创建markdown保存器（暂时不指定输出目录，后续可以更新）
    markdown_saver = LogMarkdownSaver("", log_buffer)
    
    return log_buffer, markdown_saver


def update_markdown_saver_output_dir(markdown_saver: LogMarkdownSaver, output_dir: str):
    """
    更新markdown保存器的输出目录
    
    Args:
        markdown_saver: markdown保存器实例
        output_dir: 新的输出目录
    """
    markdown_saver.output_dir = output_dir
    os.makedirs(output_dir, exist_ok=True) 