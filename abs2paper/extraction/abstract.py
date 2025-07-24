"""
摘要提取模块，负责从XML文件中提取论文标题、关键词和摘要
"""

import os
import sys
import logging
import argparse
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class AbstractExtractor:
    """论文摘要提取器，负责从XML中提取标题、关键词和摘要"""
    
    # 集中定义XML命名空间
    NAMESPACES = {
        'tei': 'http://www.tei-c.org/ns/1.0',
        'xml': 'http://www.w3.org/XML/1998/namespace'
    }
    
    def __init__(self):
        """初始化摘要提取器"""
        # 集中配置默认路径
        module_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 固定的输入输出路径
        self.input_dir = os.path.abspath(os.path.join(module_dir, "result", "text_extract"))
        self.output_dir = os.path.abspath(os.path.join(module_dir, "result", "abstract_extract"))
        
        # 处理计数
        self.success_count = 0
        self.total_count = 0
    
    def extract_abstract_from_xml(self, xml_path: str) -> Optional[str]:
        """
        从TEI XML文件中提取标题、关键词和摘要
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            提取的内容文本，如果提取失败则返回None
        """
        try:
            # 解析XML文件
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # 提取论文标题 <title level="a" type="main">
            title_elem = root.find('.//tei:title[@level="a"][@type="main"]', self.NAMESPACES)
            title = title_elem.text if title_elem is not None and title_elem.text else "未找到标题"
            
            # 提取关键词 <term>
            keywords = []
            for term in root.findall('.//tei:term', self.NAMESPACES):
                if term.text:
                    keywords.append(term.text)
            keywords_text = "，".join(keywords) if keywords else "未找到关键词"
            
            # 提取摘要 <p> in <abstract>
            abstract_text = ""
            abstract_elem = root.find('.//tei:abstract', self.NAMESPACES)
            if abstract_elem is not None:
                p_elements = abstract_elem.findall('.//tei:p', self.NAMESPACES)
                abstract_parts = []
                for p in p_elements:
                    if p.text:
                        abstract_parts.append(p.text.strip())
                abstract_text = "\n".join(abstract_parts)
            
            if not abstract_text:
                abstract_text = "未找到摘要"
            
            # 组合提取的内容
            content = f"论文标题：{title}\n\n关键词：{keywords_text}\n\n摘要：{abstract_text}"
            return content
            
        except Exception as e:
            logger.error(f"从{xml_path}提取内容时出错: {str(e)}")
            return None
    
    def process_directory(self, input_dir: str = None, output_dir: str = None, rel_path: str = "") -> bool:
        """
        处理目录及其子目录中的所有XML文件
        
        Args:
            input_dir: 输入目录路径，默认使用实例的input_dir
            output_dir: 输出目录路径，默认使用实例的output_dir
            rel_path: 相对路径，用于保持目录结构
            
        Returns:
            处理是否成功
        """
        # 使用实例默认值或指定值
        input_dir = input_dir or self.input_dir
        output_dir = output_dir or self.output_dir
        
        # 重置计数器
        self.success_count = 0
        self.total_count = 0
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # 遍历目录及子目录
            for root, dirs, files in os.walk(input_dir):
                # 计算相对路径，用于保持目录结构
                curr_rel_path = os.path.relpath(root, input_dir) if root != input_dir else ""
                if rel_path:
                    curr_rel_path = os.path.join(rel_path, curr_rel_path)
                
                # 处理所有XML文件
                for file in files:
                    if file.endswith(".grobid.tei.xml"):
                        xml_path = os.path.join(root, file)
                        self.total_count += 1
                        
                        try:
                            # 提取内容
                            content = self.extract_abstract_from_xml(xml_path)
                            
                            if content:
                                # 创建对应的输出目录
                                full_output_dir = os.path.join(output_dir, curr_rel_path)
                                os.makedirs(full_output_dir, exist_ok=True)
                                
                                # 创建输出文件路径，保持原文件名但更改扩展名为.txt
                                base_name = file.replace('.grobid.tei.xml', '')
                                txt_filename = base_name + ".txt"
                                output_file_path = os.path.join(full_output_dir, txt_filename)
                                
                                # 将内容保存到输出文件
                                with open(output_file_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                
                                logger.info(f"✅ 已从{file}提取内容并保存到{output_file_path}")
                                self.success_count += 1
                            else:
                                logger.warning(f"❌ 在{file}中未找到内容")
                        except Exception as e:
                            logger.error(f"❌ 处理{xml_path}时出错: {str(e)}")
        
        except Exception as e:
            logger.error(f"❌ 处理目录{input_dir}时出错: {str(e)}")
        
        return self.success_count > 0
    
    def extract(self) -> bool:
        """
        从XML文件中提取摘要的主要API函数，使用实例的默认路径
        
        Returns:
            处理是否成功（至少成功处理一个文件）
        """
        try:
            logger.info(f"🚀 开始提取论文摘要")
            logger.info(f"📂 输入目录: {self.input_dir}")
            logger.info(f"📂 输出目录: {self.output_dir}")
            
            # 处理所有文件
            success = self.process_directory()
            
            # 打印摘要
            logger.info(f"🎉 处理完成!")
            logger.info(f"📊 成功处理了{self.success_count}/{self.total_count}个XML文件")
            logger.info(f"📄 结果保存到{self.output_dir}")
            
            return success
            
        except Exception as e:
            logger.error(f"提取摘要时出错: {str(e)}")
            return False


def main():
    """主函数，用于单元测试和命令行运行"""
    parser = argparse.ArgumentParser(description="从TEI XML文件中提取摘要、标题和关键词")
    parser.add_argument("--input_dir", type=str,
                      help="输入目录，包含TEI XML文件，默认使用预定义路径")
    parser.add_argument("--output_dir", type=str,
                      help="输出目录，用于保存提取的内容，默认使用预定义路径")
    
    args = parser.parse_args()
    
    # 初始化摘要提取器
    extractor = AbstractExtractor()
    
    # 如果提供了自定义路径，则更新
    if args.input_dir:
        extractor.input_dir = os.path.abspath(args.input_dir)
    if args.output_dir:
        extractor.output_dir = os.path.abspath(args.output_dir)
    
    # 执行提取
    success = extractor.extract()
    
    # 根据执行结果设置退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
