"""
论文章节智能匹配模块，负责使用LLM将论文的实际章节标题映射到标准章节类别
"""

import os
import json
import logging
import sys
import argparse
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# 导入LLM客户端和日志工具
from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.log_utils import setup_dual_logging, update_markdown_saver_output_dir

# 设置双重日志系统
log_buffer, markdown_saver = setup_dual_logging()
logger = logging.getLogger(__name__)


class SectionMatcher:
    """论文章节智能匹配器，使用LLM进行章节标题到标准类别的映射"""
    
    # 标准章节类别列表
    STANDARD_SECTIONS = ["引言", "相关工作", "方法", "实验评价", "总结"]
    
    def __init__(self, force_overwrite=False):
        """初始化章节匹配器"""
        self.force_overwrite = force_overwrite
        
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
        
        # 获取路径配置
        data_paths = self.config["data_paths"]
        component_extract_path = data_paths["component_extract"]["path"].lstrip('/')
        section_prompt_path = data_paths["section_prompt"]["path"].lstrip('/')
        
        # 设置输入输出路径
        self.input_dir = os.path.join(self.project_root, component_extract_path)
        self.section_prompt_dir = os.path.join(self.project_root, section_prompt_path)
        self.section_match_dir = os.path.join(self.project_root, "abs2paper", "processing", "data", "section_match")
        
        # 确保目录存在
        os.makedirs(self.section_match_dir, exist_ok=True)
        
        # 更新markdown保存器的输出目录
        update_markdown_saver_output_dir(markdown_saver, self.section_match_dir)
        
        logger.info(f"📂 输入目录: {self.input_dir}")
        logger.info(f"📂 提示词目录: {self.section_prompt_dir}")
        logger.info(f"📂 输出目录: {self.section_match_dir}")
        
        # 加载章节匹配提示词
        self.section_prompt = self._load_section_prompt()
    
    def _load_section_prompt(self) -> str:
        """
        加载章节匹配提示词
        
        Returns:
            section_prompt: 章节匹配提示词
        """
        prompt_file = os.path.join(self.section_prompt_dir, "section_prompt")
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
                logger.info(f"✅ 已加载章节匹配提示词: {prompt_file}")
                return prompt_content
        except FileNotFoundError:
            logger.error(f"❌ 未找到章节匹配提示词文件: {prompt_file}")
            raise
        except Exception as e:
            logger.error(f"❌ 加载章节匹配提示词时出错: {e}")
            raise
    
    def _extract_section_titles(self, paper_dir: str) -> List[str]:
        """
        从论文目录中提取所有章节标题
        
        Args:
            paper_dir: 论文目录路径
            
        Returns:
            section_titles: 章节标题列表
        """
        section_titles = []
        
        if not os.path.exists(paper_dir):
            logger.warning(f"⚠️ 论文目录不存在: {paper_dir}")
            return section_titles
        
        # 遍历论文目录中的所有txt文件
        for filename in os.listdir(paper_dir):
            if filename.endswith('.txt'):
                # 从文件名中提取章节标题（去掉.txt后缀）
                section_title = filename[:-4]
                section_titles.append(section_title)
        
        logger.debug(f"📄 提取到 {len(section_titles)} 个章节标题")
        return section_titles
    
    def _match_sections_with_llm(self, section_titles: List[str]) -> Dict[str, str]:
        """
        使用LLM匹配章节标题到标准类别
        
        Args:
            section_titles: 章节标题列表
            
        Returns:
            section_mapping: 章节映射字典 {章节标题: 标准类别}
        """
        if not section_titles:
            logger.warning("⚠️ 没有章节标题需要匹配")
            return {}
        
        # 构建完整提示词
        titles_text = "\n".join(section_titles)
        full_prompt = f"{self.section_prompt}\n\n{titles_text}"
        
        # 调用LLM
        logger.info(f"🔄 正在使用LLM匹配 {len(section_titles)} 个章节标题")
        try:
            response = self.llm_client.get_completion(full_prompt)
            
            if response:
                logger.info(f"✅ LLM章节匹配完成")
                return self._parse_llm_response(response, section_titles)
            else:
                logger.error(f"❌ LLM章节匹配失败：返回空结果")
                return {}
                
        except Exception as e:
            logger.error(f"❌ LLM章节匹配时出错: {e}")
            return {}
    
    def _parse_llm_response(self, response: str, section_titles: List[str]) -> Dict[str, str]:
        """
        解析LLM响应，提取章节映射关系
        
        Args:
            response: LLM响应文本
            section_titles: 原始章节标题列表
            
        Returns:
            section_mapping: 章节映射字典
        """
        section_mapping = {}
        
        # 解析响应中的映射关系
        for line in response.split('\n'):
            line = line.strip()
            if not line or '->' not in line:
                continue
            
            try:
                # 分割章节标题和标准类别
                parts = line.split('->')
                if len(parts) == 2:
                    section_title = parts[0].strip()
                    standard_section = parts[1].strip()
                    
                    # 验证标准类别是否有效
                    if standard_section in self.STANDARD_SECTIONS:
                        section_mapping[section_title] = standard_section
                        logger.debug(f"📝 匹配: {section_title} -> {standard_section}")
                    else:
                        logger.warning(f"⚠️ 未知的标准类别: {standard_section}，将 {section_title} 归类为'方法'")
                        section_mapping[section_title] = "方法"
            
            except Exception as e:
                logger.error(f"❌ 解析映射行时出错: {line}, 错误: {e}")
        
        # 检查是否有遗漏的章节标题，使用默认映射
        for title in section_titles:
            if title not in section_mapping:
                logger.warning(f"⚠️ 章节 '{title}' 未在LLM响应中找到匹配，默认归类为'方法'")
                section_mapping[title] = "方法"
        
        logger.info(f"📊 成功匹配 {len(section_mapping)} 个章节标题")
        return section_mapping
    
    # def _create_fallback_mapping(self, section_titles: List[str]) -> Dict[str, str]:
    #     """
    #     创建备用映射（当LLM失败时使用）
    #     
    #     Args:
    #         section_titles: 章节标题列表
    #         
    #     Returns:
    #         section_mapping: 备用章节映射字典
    #     """
    #     logger.warning("⚠️ 使用备用章节映射策略")
    #     section_mapping = {}
    #     
    #     for title in section_titles:
    #         # 简单的关键词匹配作为备用
    #         title_lower = title.lower()
    #         
    #         if any(keyword in title_lower for keyword in ['introduction', 'background', 'preliminary']):
    #             section_mapping[title] = "引言"
    #         elif any(keyword in title_lower for keyword in ['related', 'literature', 'survey']):
    #             section_mapping[title] = "相关工作"
    #         elif any(keyword in title_lower for keyword in ['evaluation', 'experiment', 'result', 'performance']):
    #             section_mapping[title] = "实验评价"
    #         elif any(keyword in title_lower for keyword in ['conclusion', 'discussion', 'future']):
    #             section_mapping[title] = "总结"
    #         else:
    #             section_mapping[title] = "方法"  # 默认分类
    #     
    #     return section_mapping
    
    def _should_process_paper(self, paper_rel_path: str) -> bool:
        """
        判断是否应该处理该论文
        
        Args:
            paper_rel_path: 论文相对路径
            
        Returns:
            是否应该处理该论文
        """
        # 检查是否已经处理过
        output_dir = os.path.join(self.section_match_dir, paper_rel_path)
        mapping_file = os.path.join(output_dir, "section_mapping.json")
        
        if not os.path.exists(mapping_file):
            # 没有结果文件，需要处理
            return True
        
        # 有结果文件，根据强制模式判断
        if self.force_overwrite:
            logger.info(f"🔄 强制模式：重新生成 {paper_rel_path}")
            return True
        else:
            logger.info(f"⏭️ 跳过已存在结果: {paper_rel_path}")
            return False
    
    def match_paper_sections(self, paper_path: str) -> Dict[str, str]:
        """
        匹配单篇论文的章节
        
        Args:
            paper_path: 论文目录路径
            
        Returns:
            section_mapping: 章节映射字典
        """
        # 提取章节标题
        section_titles = self._extract_section_titles(paper_path)
        
        if not section_titles:
            logger.error(f"❌ 无法从论文目录中提取章节标题: {paper_path}")
            return {}
        
        # 使用LLM进行匹配
        section_mapping = self._match_sections_with_llm(section_titles)
        
        return section_mapping
    
    def save_section_mapping(self, section_mapping: Dict[str, str], paper_rel_path: str) -> bool:
        """
        保存章节映射结果
        
        Args:
            section_mapping: 章节映射字典
            paper_rel_path: 论文相对路径（如 "ICS/2023/paper_name"）
            
        Returns:
            是否保存成功
        """
        try:
            # 创建输出目录结构
            output_dir = os.path.join(self.section_match_dir, paper_rel_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存章节映射结果为JSON文件
            mapping_file = os.path.join(output_dir, "section_mapping.json")
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "paper_path": paper_rel_path,
                    "section_mapping": section_mapping,
                    "standard_sections": self.STANDARD_SECTIONS,
                    "total_sections": len(section_mapping)
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📁 章节映射已保存至: {mapping_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存章节映射时出错: {e}")
            return False
    
    def process_directory(self, rel_path: str = "") -> Tuple[int, int]:
        """
        处理目录中的所有论文
        
        Args:
            rel_path: 相对路径，用于保持目录结构
            
        Returns:
            (success_count, total_count): 成功处理的论文数和总论文数
        """
        success_count = 0
        total_count = 0
        
        # 完整的输入目录路径
        input_dir = self.input_dir
        if rel_path:
            input_dir = os.path.join(input_dir, rel_path)
        
        if not os.path.exists(input_dir):
            logger.warning(f"⚠️ 目录不存在: {input_dir}")
            return success_count, total_count
        
        # 遍历目录
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            
            # 如果是目录
            if os.path.isdir(item_path):
                # 检查是否是论文目录（包含.txt文件）
                txt_files = [f for f in os.listdir(item_path) if f.endswith('.txt')]
                
                if txt_files:
                    # 这是一个论文目录
                    total_count += 1
                    paper_rel_path = os.path.join(rel_path, item) if rel_path else item
                    
                    logger.info(f"🔍 处理论文: {paper_rel_path}")
                    
                    # 检查是否应该处理该论文
                    if self._should_process_paper(paper_rel_path):
                        # 匹配论文章节
                        section_mapping = self.match_paper_sections(item_path)
                        
                        if section_mapping:
                            # 保存结果
                            if self.save_section_mapping(section_mapping, paper_rel_path):
                                success_count += 1
                            else:
                                logger.error(f"❌ 保存章节映射失败: {paper_rel_path}")
                        else:
                            logger.error(f"❌ 章节匹配失败: {paper_rel_path}")
                    else:
                        # 如果跳过，则计入成功处理
                        success_count += 1
                        logger.info(f"⏭️ 跳过已存在结果: {paper_rel_path}")
                
                else:
                    # 这是一个中间目录，递归处理
                    new_rel_path = os.path.join(rel_path, item) if rel_path else item
                    sub_success, sub_total = self.process_directory(new_rel_path)
                    success_count += sub_success
                    total_count += sub_total
        
        return success_count, total_count
    
    def match_all_papers(self) -> bool:
        """
        处理所有论文并生成章节映射
        
        Returns:
            处理是否成功
        """
        try:
            logger.info(f"🚀 开始处理所有论文，源目录: {self.input_dir}")
            if self.force_overwrite:
                logger.info(f"🔄 强制模式：将重新生成所有论文的章节匹配结果")
            else:
                logger.info(f"⏭️ 默认模式：将跳过已存在的结果，只处理新论文")
            
            # 检查输入目录是否存在
            if not os.path.exists(self.input_dir):
                logger.error(f"❌ 输入目录不存在: {self.input_dir}")
                return False
            
            # 检查是否有可用的提示词
            if not self.section_prompt:
                logger.error(f"❌ 未加载章节匹配提示词")
                return False
            
            # 处理所有论文
            success_count, total_count = self.process_directory()
            
            logger.info(f"🎉 处理完成！成功处理 {success_count}/{total_count} 篇论文")
            logger.info(f"📁 结果已保存至: {self.section_match_dir}")
            
            # 保存处理日志到markdown文件
            config_info = {
                "输入目录": self.input_dir,
                "提示词目录": self.section_prompt_dir,
                "输出目录": self.section_match_dir,
                "标准章节类别": self.STANDARD_SECTIONS
            }
            summary_info = f"处理完成，成功处理 {success_count}/{total_count} 篇论文。详细结果请查看 `{self.section_match_dir}` 目录下的各论文章节映射文件。"
            
            markdown_saver.save_log_to_markdown(
                title="论文章节智能匹配处理日志",
                config_info=config_info,
                summary_info=summary_info
            )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ 处理论文章节匹配时出现严重错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 即使出错也尝试保存日志
            config_info = {
                "输入目录": getattr(self, 'input_dir', '未知'),
                "提示词目录": getattr(self, 'section_prompt_dir', '未知'),
                "输出目录": getattr(self, 'section_match_dir', '未知')
            }
            summary_info = f"处理过程中出现错误: {e}"
            
            markdown_saver.save_log_to_markdown(
                title="论文章节智能匹配处理日志（错误）",
                config_info=config_info,
                summary_info=summary_info
            )
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能匹配论文章节标题到标准类别")
    parser.add_argument("--input_dir", type=str, help="输入目录，覆盖默认的component_extract路径")
    parser.add_argument("--output_dir", type=str, help="输出目录，覆盖默认的section_match路径")
    
    args = parser.parse_args()
    
    # 创建章节匹配器
    matcher = SectionMatcher()
    
    # 如果提供了自定义路径，则更新
    if args.input_dir:
        matcher.input_dir = os.path.abspath(args.input_dir)
        logger.info(f"使用自定义输入目录: {matcher.input_dir}")
    
    if args.output_dir:
        matcher.section_match_dir = os.path.abspath(args.output_dir)
        os.makedirs(matcher.section_match_dir, exist_ok=True)
        logger.info(f"使用自定义输出目录: {matcher.section_match_dir}")
    
    # 执行章节匹配
    success = matcher.match_all_papers()
    
    # 根据执行结果设置退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 