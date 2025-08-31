"""
组件提取模块，负责从XML文件中提取论文的结构化组件（章节、摘要等）
"""

import os
import re
import xml.etree.ElementTree as ET
import logging
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# 集中定义XML命名空间和正则表达式模式
NAMESPACES = {
    'tei': 'http://www.tei-c.org/ns/1.0',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

# 罗马数字模式
ROMAN_PATTERN = r'^([IVX]+)\.\s+(.+)'  # 匹配如 "I. INTRODUCTION" 并分组
# 数字章节模式（包括小节，如3.1）
NUMBER_PATTERN = r'^(\d+(\.\d+)?)'  # 匹配如 "3" 或 "3.1"


class ComponentExtractor:
    """论文组件提取器，负责从XML中提取结构化组件"""

    def __init__(self):
        """初始化组件提取器"""
        # 确定项目根目录
        module_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(module_dir))

        # 加载配置文件
        config_path = os.path.join(self.project_root, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            logger.info(f"已加载配置: {config_path}")

        # 获取路径配置
        data_paths = self.config["data_paths"]
        text_extract_path = data_paths["text_extract"]["path"].lstrip('/')
        component_extract_path = data_paths["component_extract"]["path"].lstrip(
            '/')

        # 固定的输入输出路径
        self.input_dir = os.path.abspath(
            os.path.join(
                self.project_root,
                text_extract_path))
        self.output_dir = os.path.abspath(os.path.join(
            self.project_root, component_extract_path))

        logger.info(f"📂 输入目录: {self.input_dir}")
        logger.info(f"📂 输出目录: {self.output_dir}")

        # 初始化状态变量
        self.reset_state()

    def reset_state(self):
        """重置处理状态"""
        # 存储提取的章节
        self.sections = {}
        # 存储章节层次结构
        self.section_hierarchy = {}
        # 存储子章节内容
        self.subsection_contents = {}
        # 记录章节按发现顺序的列表
        self.section_order = []
        # 记录每个章节的小节按发现顺序的列表
        self.subsection_order = {}
        # 跟踪当前章节状态
        self.current_main_section = None
        self.current_subsection = None

    def extract_text_without_refs(self, element):
        """
        完整提取元素中的文本内容，同时排除<ref>标签中的内容
        """
        if element is None:
            return ""
        
        # 使用递归方法提取文本，忽略ref标签内容
        def extract_text_recursive(elem):
            text_parts = []
            
            # 添加元素本身的文本（如果有）
            if elem.text and elem.text.strip():
                text_parts.append(elem.text.strip())
            
            # 处理所有子元素
            for child in elem:
                if child.tag.split('}')[-1] == 'ref':
                    # 对于ref标签，只保留其后的尾随文本
                    if child.tail and child.tail.strip():
                        text_parts.append(child.tail.strip())
                else:
                    # 对于非ref标签，递归提取其中的文本
                    child_text = extract_text_recursive(child)
                    if child_text:
                        text_parts.append(child_text)
                    
                    # 添加子元素后的尾随文本
                    if child.tail and child.tail.strip():
                        text_parts.append(child.tail.strip())
            
            return ' '.join(text_parts)
        
        return extract_text_recursive(element)

    def get_section_info(self, head_text, head_attrs):
        """
        解析章节标题信息
        
        Args:
            head_text: 标题文本
            head_attrs: 标题属性
            
        Returns:
            tuple: (is_section, section_number, section_title, is_subsection, main_section_number)
        """
        is_section = False
        section_number = None
        section_title = head_text if head_text else ""
        is_subsection = False
        main_section_number = None
        
        # 检查是否有n属性
        if 'n' in head_attrs:
            n_value = head_attrs['n']
            
            # 检查n是否为数字或带小数点的数字（如"3"或"3.1"）
            match = re.match(NUMBER_PATTERN, n_value)
            if match:
                is_section = True
                section_number = n_value
                
                # 判断是否为子章节（如3.1）
                if '.' in n_value:
                    is_subsection = True
                    main_section_number = n_value.split('.')[0]
                else:
                    main_section_number = n_value
            else:
                # 尝试将n转换为整数
                try:
                    int_value = int(n_value)
                    is_section = True
                    section_number = n_value
                    main_section_number = n_value
                except ValueError:
                    pass  # 不是有效的章节编号
        
        # 检查是否符合罗马数字格式
        elif head_text and re.match(ROMAN_PATTERN, head_text):
            # 提取罗马数字和标题内容
            match = re.match(ROMAN_PATTERN, head_text)
            is_section = True
            # 提取罗马数字作为章节编号
            section_number = match.group(1)
            # 提取标题内容（去掉罗马数字和点）
            section_title = match.group(2).strip()
            main_section_number = section_number
        
        return (is_section, section_number, section_title,
                is_subsection, main_section_number)

    def process_div_elements(self, div):
        """
        处理div元素中的头部和内容，适应章节层次结构
        """
        # 找到div中的head元素
        head = div.find('./tei:head', NAMESPACES)
        if head is not None:
            head_text = head.text.strip() if head.text else ""
            
            # 获取章节详细信息
            is_section, section_number, section_title, is_subsection, main_section_number = self.get_section_info(
                head_text, head.attrib)
            
            if is_section and section_number:
                # 根据不同情况构建标题
                if re.match(ROMAN_PATTERN, head_text):
                    # 如果是罗马数字标题格式，使用分离后的格式
                    full_title = f"{section_number}. {section_title}"
                else:
                    # 其他情况使用标准格式
                    full_title = f"{section_number} {section_title}" if section_title else section_number
                
                if is_subsection:
                    # 如果是小节（如3.1）
                    # 查找是否有对应的主章节
                    if main_section_number in self.section_hierarchy:
                        # 有主章节，使用主章节作为当前小节的父章节
                        main_section_title = self.section_hierarchy[main_section_number]
                        
                        # 初始化小节内容列表
                        if main_section_title not in self.subsection_contents:
                            self.subsection_contents[main_section_title] = {}
                        if main_section_title not in self.subsection_order:
                            self.subsection_order[main_section_title] = []
                        
                        if full_title not in self.subsection_contents[main_section_title]:
                            self.subsection_contents[main_section_title][full_title] = []
                            # 记录小节顺序
                            self.subsection_order[main_section_title].append(full_title)
                            
                        # 更新当前章节状态
                        self.current_main_section = main_section_title
                        self.current_subsection = full_title
                    else:
                        # 没有主章节，将小节升级为主章节
                        main_title = f"{main_section_number} {section_title}"
                        self.section_hierarchy[main_section_number] = main_title
                        
                        # 更新当前章节状态
                        self.current_main_section = main_title
                        self.current_subsection = None
                        
                        # 如果这个主章节不存在于sections中，创建它
                        if main_title not in self.sections:
                            self.sections[main_title] = []
                else:
                    # 如果是主章节（如3或III），创建新的章节条目
                    self.section_hierarchy[main_section_number] = full_title
                    
                    # 更新当前章节状态
                    self.current_main_section = full_title
                    self.current_subsection = None
                    
                    if full_title not in self.sections:
                        self.sections[full_title] = []
            elif self.current_main_section: # 注意：这里是elif，因为如果head是章节，就不应再作为普通小节标题处理
                # 如果不是章节标题（如A.、B.、2)等格式），且当前有主章节
                # 提取head的文本作为小节标题
                subsection_title = head.text.strip() if head and head.text else ""
                    
                if subsection_title: # 确保标题不为空
                    # 初始化小节内容列表
                    if self.current_main_section not in self.subsection_contents:
                        self.subsection_contents[self.current_main_section] = {}
                    if self.current_main_section not in self.subsection_order:
                        self.subsection_order[self.current_main_section] = []
                        
                    if subsection_title not in self.subsection_contents[self.current_main_section]:
                        self.subsection_contents[self.current_main_section][subsection_title] = []
                        # 记录小节顺序
                        self.subsection_order[self.current_main_section].append(subsection_title)
                        
                    # 更新当前小节
                    self.current_subsection = subsection_title
        
        # 处理div中的所有元素
        for elem in div:
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            # 跳过非命名空间中的元素
            if not elem.tag.startswith('{' + NAMESPACES['tei'] + '}'):
                continue
                
            # 如果遇到新的div，递归处理
            if tag == 'div':
                self.process_div_elements(elem)
                continue
            
            # 处理内容元素
            if tag in ['p', 'formula', 'figure', 'table']:
                # 如果没有当前章节，跳过
                if not self.current_main_section:
                    continue
                    
                # 提取不包含ref的段落内容
                text_content = self.extract_text_without_refs(elem)
                if text_content:
                    if self.current_subsection:
                        # 如果有当前小节，将内容添加到小节中
                        self.subsection_contents[self.current_main_section][self.current_subsection].append(text_content)
                    else:
                        # 否则，将内容添加到主章节中
                        self.sections[self.current_main_section].append(text_content)
        
    def extract_sections_from_xml(self, xml_path):
        """从TEI XML文件中提取章节内容"""
        try:
            # 重置状态
            self.reset_state()

            # 解析XML文件
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # 首先定位到<text xml:lang="en">/<body>
            text_elements = root.findall(
                ".//tei:text[@xml:lang='en']", NAMESPACES)
            
            if not text_elements:
                # 尝试查找任何语言的text元素
                text_elements = root.findall(".//tei:text", NAMESPACES)
            
            if not text_elements:
                logger.warning(f"在{xml_path}中未找到<text>元素")
                return {}, []
            
            for text_elem in text_elements:
                body_elem = text_elem.find("./tei:body", NAMESPACES)
                if body_elem is not None:
                    # 只处理<body>下的<div>元素
                    for div in body_elem.findall("./tei:div", NAMESPACES):
                        self.process_div_elements(div)

            # 从 section_hierarchy 中提取唯一的章节标题
            # 不再进行排序，使用原始顺序
            for num, title in self.section_hierarchy.items():
                if title not in self.section_order:
                    self.section_order.append(title)
            
            # 确保所有的章节都包含在section_order中
            for title in self.sections.keys():
                if title not in self.section_order:
                    self.section_order.append(title)
            
            # 合并每个章节的内容，同时添加标题和小节标题
            result = {}
            for section_title in self.section_order:
                content_parts = []
                
                # 添加章节标题作为第一行
                content_parts.append(section_title)
                
                # 添加章节主体内容
                if section_title in self.sections and self.sections[section_title]:
                    content_parts.append(
                        '\n'.join(self.sections[section_title]))
                
                # 添加小节内容（如果有）
                if section_title in self.subsection_contents:
                    # 使用记录的原始小节顺序
                    if section_title in self.subsection_order:
                        subsections = self.subsection_order[section_title]
                    else:
                        # 如果没有记录顺序，则使用字典的默认顺序
                        subsections = list(
                            self.subsection_contents[section_title].keys())
                    
                    # --- 修正开始 ---
                    # 在确保subsections变量已定义后再使用
                    # 将此循环的缩进调整到与上面的 if/else 对齐
                    for subsection in subsections:
                        # 添加小节标题
                        content_parts.append(subsection)
                        
                        # 添加小节内容
                        if self.subsection_contents[section_title][subsection]:
                            content_parts.append(
                                '\n'.join(
                                    self.subsection_contents[section_title][subsection]))
                    # --- 修正结束 ---
                
                # 合并所有内容部分
                result[section_title] = '\n'.join(content_parts)
            
            return result, self.section_order
        
        except Exception as e:
            logger.error(f"从{xml_path}提取内容时出错: {str(e)}")
            return {}, []

    def extract_components(self, xml_path, output_dir=None):
        """
        从XML文件中提取论文组件并保存
        
        Args:
            xml_path: XML文件路径
            output_dir: 输出目录，如果为None则使用实例默认输出目录
        
        Returns:
            Dict[str, str]: 按部分组织的文本字典，格式为 {部分名称: 文本内容}
        """
        # 使用实例默认值或指定值
        output_dir = output_dir or self.output_dir

        # 提取章节内容
        sections, section_order = self.extract_sections_from_xml(xml_path)
        
        if not sections:
            logger.warning(f"从{xml_path}中提取不到有效内容")
            return {}
        
        # 如果指定了输出目录，则保存提取的内容
        if output_dir:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存每个章节
            for section_title in section_order:
                if section_title in sections:
                    # 创建安全的文件名
                    safe_title = re.sub(r'[<>:"/\\|?*]', '_', section_title)
                    txt_filename = f"{safe_title}.txt"
                    output_file_path = os.path.join(output_dir, txt_filename)
                    
                    # 将内容保存到输出文件
                    with open(output_file_path, "w", encoding="utf-8") as f:
                        f.write(sections[section_title])
                    
                    logger.info(f"已从{os.path.basename(xml_path)}提取章节「{section_title}」并保存")
        
        return sections

    def process_dir(self, input_dir=None, output_dir=None):
        """
        处理目录中所有XML文件并提取组件
        
        Args:
            input_dir: XML文件目录，默认使用实例的input_dir
            output_dir: 输出目录，默认使用实例的output_dir
        
        Returns:
            int: 成功处理的文件数量
        """
        # 使用实例默认值或指定值
        input_dir = input_dir or self.input_dir
        output_dir = output_dir or self.output_dir

        # 重置成功计数
        self.success_count = 0
        total_files = 0
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 获取所有XML文件列表，先计数
        xml_files = list(Path(input_dir).glob("**/*.xml"))
        total_files = len(xml_files)
        logger.info(f"找到 {total_files} 个XML文件待处理")
        
        # 遍历输入目录中的所有XML文件
        for file in xml_files:
            try:
                # 创建相对路径保持目录结构
                rel_path = file.relative_to(input_dir)
                # 只保留.grobid前面的部分作为论文名
                pure_name = file.stem
                grobid_idx = pure_name.find('.grobid')
                if grobid_idx != -1:
                    pure_name = pure_name[:grobid_idx]
                file_output_dir = os.path.join(
                    output_dir, str(rel_path.parent), pure_name)
                # 提取并保存组件
                sections = self.extract_components(str(file), file_output_dir)
                if sections:
                    self.success_count += 1
                    logger.info(
                        f"成功处理: {file.name} [进度: {self.success_count}/{total_files}]")
                else:
                    logger.warning(f"未能提取内容: {file.name}")
            except Exception as e:
                logger.error(f"处理{file.name}时出错: {str(e)}")
        return self.success_count

    def extract(self):
        """
        从XML文件中提取组件的主要API函数，使用实例的默认路径

        Returns:
            bool: 处理是否成功
        """
        try:
            logger.info(f"开始提取论文组件")
            logger.info(f"📂 输入目录: {self.input_dir}")
            logger.info(f"📂 输出目录: {self.output_dir}")

            # 直接调用处理函数
            success_count = self.process_dir()

            # 打印详细的成功数量
            logger.info(f"✅ 组件提取完成，成功处理了 {success_count} 个文件")
            return success_count > 0
        except Exception as e:
            logger.error(f"提取组件时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        

def main():
    """主函数，用于单元测试和命令行运行"""
    parser = argparse.ArgumentParser(description="从XML文件中提取论文组件")
    parser.add_argument("--input_dir", type=str,
                        help="XML文件所在目录，默认使用预定义路径")
    parser.add_argument("--output_dir", type=str,
                        help="输出目录，默认使用预定义路径")

    args = parser.parse_args()
    
    # 初始化组件提取器
    extractor = ComponentExtractor()
    
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