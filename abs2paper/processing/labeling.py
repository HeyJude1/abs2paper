"""
论文标签处理模块，负责分析论文摘要并标记主题
"""

import os
import json
import re
import logging
import argparse
from typing import Dict, Any, List, Optional, Tuple, Union
import sys

# 导入LLM客户端
from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.topic_manager import TopicManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PaperLabeler:
    """论文标签生成器，负责分析论文并生成主题标签"""
    
    def __init__(self, topic_manager: Optional[TopicManager] = None):
        """
        初始化论文标签生成器
        
        Args:
            topic_manager: 可选的主题管理器实例
        """
        # 确定项目根目录
        module_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(module_dir))
        
        # 加载配置文件
        config_path = os.path.join(self.project_root, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            logger.info(f"已加载配置: {config_path}")
        
        # 创建LLM客户端
        self.llm_client = LLMClient()
        
        # 加载提示词模板
        self.prompt_template = self._load_prompt_template()
        
        # 获取路径配置
        data_paths = self.config["data_paths"]
        abstract_extract_path = data_paths["abstract_extract"]["path"].lstrip('/')
        label_path = data_paths["label"]["path"].lstrip('/')
        
        # 固定的输入输出路径
        self.input_dir = os.path.join(self.project_root, abstract_extract_path)
        self.output_dir = os.path.join(self.project_root, label_path)
        
        # 确保目录存在
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"输入目录: {self.input_dir}")
        logger.info(f"输出目录: {self.output_dir}")
        
        # 初始化或使用传入的主题管理器
        self.topic_manager = topic_manager or TopicManager()
    
    def _load_prompt_template(self) -> str:
        """
        加载提示词模板
            
        Returns:
            提示词模板文本
            
        Raises:
            FileNotFoundError: 如果提示词模板文件不存在
        """
        # 从配置中读取提示词模板路径
        prompt_kb_path = self.config["data_paths"]["prompt_kb"]["path"].lstrip('/')
        prompt_path = os.path.join(self.project_root, prompt_kb_path)
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            template = f.read().strip()
            logger.info(f"✅ 已加载提示词模板: {prompt_path}")
            return template
    
    def extract_keywords_array(self, response: str) -> str:
        """
        从模型回复中提取关键词数组，参考label_paper_ori.py的实现
        
        Args:
            response: 模型回复文本
            
        Returns:
            提取的关键词数组文本
        """
        # 使用更灵活的正则表达式，匹配多种可能的模式
        # 1. 尝试匹配"(故)该论文的主题关键词总结为[...]"的模式
        match = re.search(r"(?:故)?该论文的主题关键词总结为\[(.*?)\]", response)
        if match:
            return match.group(1).strip()
            
        # 2. 尝试匹配任何包含"关键词总结为[...]"的模式
        match = re.search(r"关键词总结为\[(.*?)\]", response)
        if match:
            return match.group(1).strip()
            
        # 3. 尝试直接匹配任何方括号内容 [...] 作为备用
        match = re.search(r"\[(.*?)\]", response)
        if match:
            return match.group(1).strip()
            
        # 如果没有匹配到，直接返回原文本
        return response.strip()
    
    def update_prompt_with_topics(self, prompt: str) -> str:
        """
        使用最新的主题列表更新提示词模板
        
        Args:
            prompt: 原始提示词
            
        Returns:
            更新后的提示词
        """
        # 生成主题词列表文本
        topic_list = self.topic_manager.generate_topic_list_text()
        
        # 查找知识库部分并替换
        pattern = r"##知识库：.*?(?=##|$)"
        replacement = self.topic_manager.generate_prompt_kb_text()
        
        # 尝试替换
        updated_prompt = re.sub(pattern, replacement, prompt, flags=re.DOTALL)
        
        # 如果没有成功替换，保留原提示词
        if updated_prompt == prompt:
            logger.warning("无法在提示词中找到知识库部分进行替换")
            return prompt
            
        return updated_prompt
    
    def process_paper_file(self, file_path: str, result_list: Optional[List] = None) -> bool:
        """
        处理单个论文文件并获取主题标签
        
        Args:
            file_path: 论文文件路径
            result_list: 可选，用于收集所有结果的列表
            
        Returns:
            处理是否成功
        """
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 检查结果文件是否已存在
        paper_name = os.path.basename(file_path)
        output_file_path = os.path.join(self.output_dir, paper_name)
        
        # 如果之前已经生成过结果则跳过处理
        if os.path.exists(output_file_path):
            logger.info(f"⏭️ 结果已存在，跳过处理: {paper_name}")
            
            # 如果需要收集结果，读取已有文件内容
            if result_list is not None:
                try:
                    with open(output_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # 移除前面的文件名部分
                        response_part = content.split(':', 1)[1].strip() if ':' in content else content
                        self._add_paper_result(paper_name, response_part, result_list)
                except Exception as e:
                    logger.warning(f"⚠️ 读取已有结果失败: {e}")
            return True
        
        # 读取论文内容
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                paper_content = f.read().strip()
        except Exception as e:
            logger.error(f"❌ 读取文件失败 {file_path}: {str(e)}")
            return False
        
        # 使用最新的主题列表更新提示词
        current_prompt = self.update_prompt_with_topics(self.prompt_template)
        
        # 构建完整的提示词
        full_prompt = f"{current_prompt}\n\n{paper_content}"
        
        # 调用LLM
        logger.info(f"🔄 正在处理论文: {paper_name}")
        response = self.llm_client.get_completion(full_prompt)
        
        if response:
            # 保存结果
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(f"{paper_name}:\n{response}")
            logger.info(f"📄 结果已保存至: {output_file_path}")
            
            # 如果需要收集结果，添加到列表
            if result_list is not None:
                self._add_paper_result(paper_name, response, result_list)
            
            return True
        else:
            logger.error(f"❌ 获取论文标签失败: {paper_name}")
            return False
    
    def process_directory(self, rel_path: str = "", result_list: Optional[List] = None) -> Tuple[int, int, List]:
        """
        处理目录中的所有TXT文件及其子目录
        
        Args:
            rel_path: 相对路径，用于保持目录结构
            result_list: 可选，用于收集所有结果的列表
            
        Returns:
            成功处理的文件数、总文件数和结果列表的元组
        """
        if result_list is None:
            result_list = []
            
        success_count = 0
        total_count = 0
        
        # 完整的输入目录路径
        input_dir = self.input_dir
        if rel_path:
            input_dir = os.path.join(input_dir, rel_path)
            
        # 确保目录存在
        if not os.path.exists(input_dir):
            logger.warning(f"⚠️ 目录不存在: {input_dir}")
            return success_count, total_count, result_list
        
        # 遍历目录中的所有项目
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            
            # 如果是目录，则递归处理
            if os.path.isdir(item_path):
                new_rel_path = os.path.join(rel_path, item) if rel_path else item
                sub_success, sub_total, result_list = self.process_directory(new_rel_path, result_list)
                success_count += sub_success
                total_count += sub_total
            
            # 如果是TXT文件，则处理它
            elif item.endswith(".txt"):
                total_count += 1
                if self.process_paper_file(item_path, result_list):
                    success_count += 1
        
        return success_count, total_count, result_list
    
    def _add_paper_result(self, paper_name: str, labels: str, result_list: List) -> List:
        """
        将论文结果添加到结果列表
        
        Args:
            paper_name: 论文文件名
            labels: 标签文本
            result_list: 结果列表
            
        Returns:
            更新后的结果列表
        """
        # 清理标签文本
        clean_labels = labels.strip()
        
        # 尝试提取关键词数组
        keywords_array = self.extract_keywords_array(clean_labels)
        
        # 添加到结果列表
        result_list.append({
            "paper": paper_name,
            "labels": keywords_array
        })
        
        return result_list
    
    def save_results(self, result_list: List) -> Dict[str, int]:
        """
        保存汇总结果和关键词统计
        
        Args:
            result_list: 结果列表
            
        Returns:
            关键词计数字典
        """
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 保存完整结果
        results_file = os.path.join(self.output_dir, "paper_labels_results.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(result_list, f, ensure_ascii=False, indent=2)
        
        # 提取所有关键词并计数
        keyword_counts = {}
        for paper_result in result_list:
            # 尝试按逗号或其他分隔符分割标签
            labels_text = paper_result.get("labels", "")
            
            # 如果包含数字和逗号，可能是关键词数组格式
            if re.search(r'\d+,\s*\d+', labels_text):
                labels = re.findall(r'\d+', labels_text)
            else:
                labels = labels_text.replace("，", ",").split(",")
            
            for label in labels:
                label = label.strip()
                if label:
                    keyword_counts[label] = keyword_counts.get(label, 0) + 1
        
        # 按计数排序
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 保存关键词统计
        keywords_file = os.path.join(self.output_dir, "keyword_counts.json")
        with open(keywords_file, "w", encoding="utf-8") as f:
            json.dump(dict(sorted_keywords), f, ensure_ascii=False, indent=2)
        
        logger.info(f"📊 汇总结果已保存至 {results_file}")
        logger.info(f"📊 关键词统计已保存至 {keywords_file}")
        
        return dict(sorted_keywords)


def label_papers(input_dir: str = None, output_dir: str = None) -> bool:
    """
    处理目录中的所有论文并生成标签
    Args:
        input_dir: 输入目录，如果提供则覆盖默认路径
        output_dir: 输出目录，如果提供则覆盖默认路径
    Returns:
        处理是否成功（至少成功处理一个文件）
    """
    try:
        # 初始化论文标签生成器
        labeler = PaperLabeler()
        
        # 如果提供了自定义路径，则使用自定义路径
        if input_dir:
            labeler.input_dir = input_dir
        if output_dir:
            labeler.output_dir = output_dir
            
        # 确保输出目录存在
        os.makedirs(labeler.output_dir, exist_ok=True)
        
        # 处理所有论文
        logger.info(f"🚀 开始处理论文，源目录: {labeler.input_dir}")
        success_count, total_count, all_paper_results = labeler.process_directory()
        
        # 保存汇总结果
        if all_paper_results:
            keyword_counts = labeler.save_results(all_paper_results)
            logger.info(f"📊 关键词统计完成，共 {len(keyword_counts)} 个关键词")
            
        logger.info(f"🎉 处理完成！成功处理 {success_count}/{total_count} 个文件。")
        logger.info(f"结果已保存至 {labeler.output_dir}")
        
        # 如果至少有一个文件成功处理，则认为操作成功
        return success_count > 0
    except Exception as e:
        logger.error(f"处理论文标签时出错: {str(e)}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="处理论文摘要并生成主题标签")
    
    args = parser.parse_args()
    
    label_papers()


if __name__ == "__main__":
    main()
