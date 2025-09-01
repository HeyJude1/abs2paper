"""
论文章节总结模块，负责对论文的10个关键方面进行总结
"""

import os
import json
import logging
import sys
import argparse
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# 导入LLM客户端和日志工具
from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.log_utils import setup_dual_logging, update_markdown_saver_output_dir

# 设置双重日志系统
log_buffer, markdown_saver = setup_dual_logging()
logger = logging.getLogger(__name__)


class SectionConcluder:
    """论文章节总结器，负责对论文的10个关键方面进行总结"""
    
    def __init__(self, force_overwrite=False):
        """初始化论文章节总结器"""
        self.force_overwrite = force_overwrite
        
        # 确定项目根目录
        module_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(module_dir))
        
        # 加载配置文件
        config_path = os.path.join(self.project_root, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            logger.info(f"已加载配置: {config_path}")
        
        # 从配置文件读取CONCLUDE_ASPECTS
        conclude_aspects_config = self.config["paper"]["conclude_aspects"]
        # 过滤掉以_开头的元数据字段
        self.CONCLUDE_ASPECTS = {k: v for k, v in conclude_aspects_config.items() if not k.startswith('_')}
        
        # 创建LLM客户端
        self.llm_client = LLMClient()
        
        # 获取路径配置
        data_paths = self.config["data_paths"]
        component_extract_path = data_paths["component_extract"]["path"].lstrip('/')
        conclude_prompt_path = data_paths["conclude_prompt"]["path"].lstrip('/')
        
        # 设置输入输出路径
        self.input_dir = os.path.join(self.project_root, component_extract_path)
        self.conclude_prompt_dir = os.path.join(self.project_root, conclude_prompt_path)
        self.conclude_result_dir = os.path.join(self.project_root, "abs2paper", "processing", "data", "conclude_result")
        
        # 确保目录存在
        os.makedirs(self.conclude_result_dir, exist_ok=True)
        
        # 更新markdown保存器的输出目录
        update_markdown_saver_output_dir(markdown_saver, self.conclude_result_dir)
        
        logger.info(f"📂 输入目录: {self.input_dir}")
        logger.info(f"📂 提示词目录: {self.conclude_prompt_dir}")
        logger.info(f"📂 输出目录: {self.conclude_result_dir}")
        
        # 注释掉人工设置的章节映射，改用LLM智能匹配结果
        # self.section_mapping = self.config["paper"]["chapter_mapping"]
        
        # 设置章节匹配结果目录
        self.section_match_dir = os.path.join(self.project_root, "abs2paper", "processing", "data", "section_match")
        
        # 加载所有总结提示词
        self.conclude_prompts = self._load_conclude_prompts()
    
    def _load_conclude_prompts(self) -> Dict[str, str]:
        """
        加载所有总结提示词
        
        Returns:
            conclude_prompts: 总结提示词字典
        """
        conclude_prompts = {}
        
        for aspect in self.CONCLUDE_ASPECTS.keys():
            prompt_file = os.path.join(self.conclude_prompt_dir, f"{aspect}_prompt")
            
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_content = f.read().strip()
                    if prompt_content:
                        conclude_prompts[aspect] = prompt_content
                        logger.info(f"✅ 已加载 {aspect} 提示词")
                    else:
                        logger.warning(f"⚠️ {aspect} 提示词文件为空: {prompt_file}")
            
            except FileNotFoundError:
                logger.error(f"❌ 未找到 {aspect} 提示词文件: {prompt_file}")
            except Exception as e:
                logger.error(f"❌ 加载 {aspect} 提示词时出错: {e}")
        
        logger.info(f"📝 总共加载了 {len(conclude_prompts)} 个总结提示词")
        return conclude_prompts
    
    def _load_section_mapping(self, paper_rel_path: str) -> Dict[str, str]:
        """
        从第一阶段的结果中加载章节映射关系
        
        Args:
            paper_rel_path: 论文相对路径（如 "ICS/2023/paper_name"）
            
        Returns:
            section_mapping: 章节映射字典 {章节标题: 标准类别}
        """
        mapping_file = os.path.join(self.section_match_dir, paper_rel_path, "section_mapping.json")
        
        if not os.path.exists(mapping_file):
            logger.error(f"❌ 未找到章节映射文件: {mapping_file}，请先运行第一阶段章节匹配")
            return {}
        
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                section_mapping = mapping_data.get("section_mapping", {})
                logger.info(f"✅ 已加载章节映射: {len(section_mapping)} 个章节")
                return section_mapping
        except Exception as e:
            logger.error(f"❌ 加载章节映射文件失败: {e}")
            return {}
    
    # def _create_fallback_section_mapping(self, paper_rel_path: str) -> Dict[str, str]:
    #     """
    #     当无法加载章节映射时，创建备用映射（基于原有逻辑）
    #     
    #     Args:
    #         paper_rel_path: 论文相对路径
    #         
    #     Returns:
    #         section_mapping: 备用章节映射字典
    #     """
    #     logger.warning(f"⚠️ 为论文 {paper_rel_path} 创建备用章节映射")
    #     
    #     # 从component_extract目录获取章节标题
    #     paper_dir = os.path.join(self.input_dir, paper_rel_path)
    #     section_mapping = {}
    #     
    #     if os.path.exists(paper_dir):
    #         for filename in os.listdir(paper_dir):
    #             if filename.endswith('.txt'):
    #                 section_title = filename[:-4]
    #                 # 使用简化的匹配逻辑
    #                 standard_section = self._match_section_to_standard_fallback(section_title)
    #                 section_mapping[section_title] = standard_section
    #     
    #     return section_mapping
    # 
    # def _match_section_to_standard_fallback(self, section_title: str) -> str:
    #     """
    #     备用的章节匹配方法（基于原有逻辑）
    #     
    #     Args:
    #         section_title: 实际的章节标题
    #         
    #     Returns:
    #         匹配到的标准章节名称
    #     """
    #     # 转换为小写并去除数字和符号
    #     cleaned_title = section_title.lower().strip()
    #     
    #     # 移除章节编号（如"1 INTRODUCTION" -> "introduction"）
    #     import re
    #     cleaned_title = re.sub(r'^\d+\.?\s*', '', cleaned_title)
    #     cleaned_title = re.sub(r'[^\w\s]', ' ', cleaned_title).strip()
    #     
    #     # 使用配置中的章节映射进行匹配
    #     chapter_mapping = self.config["paper"]["chapter_mapping"]
    #     
    #     # 尝试直接匹配
    #     for key, standard_section in chapter_mapping.items():
    #         if key.lower() in cleaned_title or cleaned_title in key.lower():
    #             return standard_section
    #     
    #     # 如果没有直接匹配，尝试部分匹配
    #     for key, standard_section in chapter_mapping.items():
    #         key_words = key.lower().split()
    #         title_words = cleaned_title.split()
    #         
    #         # 如果有关键词匹配
    #         if any(word in title_words for word in key_words):
    #             return standard_section
    #     
    #     # 默认返回"方法"部分
    #     logger.warning(f"⚠️ 无法匹配章节 '{section_title}'，默认归类为'方法'部分")
    #     return "方法"
    
    def _read_paper_sections_with_mapping(self, paper_dir: str, section_mapping: Dict[str, str]) -> Dict[str, str]:
        """
        使用章节映射读取论文的所有章节内容
        
        Args:
            paper_dir: 论文目录路径
            section_mapping: 章节映射字典 {章节标题: 标准类别}
            
        Returns:
            sections: 标准章节名称到内容的映射
        """
        sections = {}
        
        if not os.path.exists(paper_dir):
            logger.warning(f"⚠️ 论文目录不存在: {paper_dir}")
            return sections
        
        # 遍历论文目录中的所有txt文件
        for filename in os.listdir(paper_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(paper_dir, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    # 从文件名中提取章节标题（去掉.txt后缀）
                    section_title = filename[:-4]
                    
                    # 从映射中获取标准章节
                    standard_section = section_mapping.get(section_title, "方法")  # 默认为"方法"
                    
                    if content:
                        # 如果已有该标准章节，则追加内容
                        if standard_section in sections:
                            sections[standard_section] += f"\n\n{content}"
                        else:
                            sections[standard_section] = content
                        
                        logger.debug(f"📄 {section_title} -> {standard_section}")
                
                except Exception as e:
                    logger.error(f"❌ 读取文件 {file_path} 时出错: {e}")
        
        logger.info(f"📚 成功读取 {len(sections)} 个标准章节")
        return sections
    
    def _build_prompt_with_sections(self, aspect: str, paper_sections: Dict[str, str]) -> Optional[str]:
        """
        构建包含相关章节内容的完整提示词
        
        Args:
            aspect: 总结方面
            paper_sections: 论文章节内容
            
        Returns:
            完整的提示词，如果无法构建则返回None
        """
        if aspect not in self.conclude_prompts:
            logger.error(f"❌ 未找到 {aspect} 的提示词")
            return None
        
        base_prompt = self.conclude_prompts[aspect]
        required_sections = self.CONCLUDE_ASPECTS.get(aspect, [])
        
        # 收集需要的章节内容
        section_contents = []
        for section_name in required_sections:
            if section_name in paper_sections:
                section_contents.append(f"## {section_name.title()}\n{paper_sections[section_name]}")
            else:
                logger.warning(f"⚠️ 论文缺少 {section_name} 章节，{aspect} 总结可能不完整")
        
        if not section_contents:
            logger.warning(f"⚠️ 没有找到 {aspect} 所需的任何章节内容")
            return None
        
        # 拼接提示词和章节内容
        combined_sections = "\n\n".join(section_contents)
        full_prompt = f"{base_prompt}\n\n## 论文内容\n\n{combined_sections}"
        
        return full_prompt
    
    def _conclude_aspect(self, aspect: str, paper_sections: Dict[str, str]) -> Optional[str]:
        """
        对论文的某个方面进行总结
        
        Args:
            aspect: 总结方面
            paper_sections: 论文章节内容
            
        Returns:
            总结结果，如果失败则返回None
        """
        # 构建完整提示词
        full_prompt = self._build_prompt_with_sections(aspect, paper_sections)
        
        if not full_prompt:
            return None
        
        # 调用LLM
        logger.info(f"🔄 正在总结: {aspect}")
        try:
            response = self.llm_client.get_completion(full_prompt)
            
            if response:
                logger.info(f"✅ {aspect} 总结完成")
                return response
            else:
                logger.error(f"❌ {aspect} 总结失败：LLM返回空结果")
                return None
                
        except Exception as e:
            logger.error(f"❌ {aspect} 总结时出错: {e}")
            return None
    
    def conclude_paper(self, paper_path: str, paper_rel_path: str) -> Dict[str, str]:
        """
        对单篇论文进行10个方面的总结
        
        Args:
            paper_path: 论文目录路径
            paper_rel_path: 论文相对路径（用于加载章节映射）
            
        Returns:
            results: 总结结果字典 {aspect: result}
        """
        results = {}
        
        # 从第一阶段结果中加载章节映射
        section_mapping = self._load_section_mapping(paper_rel_path)
        
        if not section_mapping:
            logger.error(f"❌ 无法加载章节映射: {paper_rel_path}")
            return results
        
        # 使用章节映射读取论文章节
        paper_sections = self._read_paper_sections_with_mapping(paper_path, section_mapping)
        
        if not paper_sections:
            logger.error(f"❌ 无法读取论文章节: {paper_path}")
            return results
        
        # 对每个方面进行总结
        for aspect in self.CONCLUDE_ASPECTS.keys():
            result = self._conclude_aspect(aspect, paper_sections)
            if result:
                results[aspect] = result
        
        logger.info(f"📊 论文总结完成，成功总结了 {len(results)}/10 个方面")
        return results
    
    def save_results(self, results: Dict[str, str], paper_rel_path: str) -> bool:
        """
        保存总结结果
        
        Args:
            results: 总结结果字典
            paper_rel_path: 论文相对路径（如 "ICS/2023/paper_name"）
            
        Returns:
            是否保存成功
        """
        try:
            # 创建输出目录结构
            output_dir = os.path.join(self.conclude_result_dir, paper_rel_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存每个方面的总结结果
            for aspect, result in results.items():
                output_file = os.path.join(output_dir, f"{aspect}.txt")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                
                logger.debug(f"💾 已保存 {aspect} 总结: {output_file}")
            
            # 保存汇总的JSON文件
            summary_file = os.path.join(output_dir, "summary.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "paper_path": paper_rel_path,
                    "aspects_completed": len(results),
                    "total_aspects": len(self.CONCLUDE_ASPECTS),
                    "completed_aspects": list(results.keys()),
                    "missing_aspects": [aspect for aspect in self.CONCLUDE_ASPECTS.keys() if aspect not in results]
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📁 总结结果已保存至: {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")
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
                    
                    # 检查是否已经处理过，询问用户是否重新生成
                    output_dir = os.path.join(self.conclude_result_dir, paper_rel_path)
                    summary_file = os.path.join(output_dir, "summary.json")
                    
                    skip_paper = False
                    if os.path.exists(summary_file):
                        logger.info(f"📄 论文已有结果: {paper_rel_path}")
                        
                        if self.force_overwrite:
                            logger.info(f"🔄 强制模式：自动重新生成: {paper_rel_path}")
                        else:
                            while True:
                                user_input = input(f"是否重新生成该论文的总结? (yes/no): ").strip().lower()
                                if user_input in ['yes', 'y']:
                                    logger.info(f"🔄 用户选择重新生成: {paper_rel_path}")
                                    break
                                elif user_input in ['no', 'n']:
                                    logger.info(f"⏭️ 用户选择跳过: {paper_rel_path}")
                                    success_count += 1
                                    skip_paper = True
                                    break
                                else:
                                    print("请输入 yes 或 no")
                    
                    if skip_paper:
                        continue
                    
                    # 总结论文
                    results = self.conclude_paper(item_path, paper_rel_path)
                    
                    if results:
                        # 保存结果
                        if self.save_results(results, paper_rel_path):
                            success_count += 1
                        else:
                            logger.error(f"❌ 保存论文总结失败: {paper_rel_path}")
                    else:
                        logger.error(f"❌ 论文总结失败: {paper_rel_path}")
                
                else:
                    # 这是一个中间目录，递归处理
                    new_rel_path = os.path.join(rel_path, item) if rel_path else item
                    sub_success, sub_total = self.process_directory(new_rel_path)
                    success_count += sub_success
                    total_count += sub_total
        
        return success_count, total_count
    
    def conclude_all_papers(self) -> bool:
        """
        处理所有论文并生成总结
        
        Returns:
            处理是否成功
        """
        try:
            logger.info(f"🚀 开始处理所有论文，源目录: {self.input_dir}")
            logger.info(f"📋 发现已存在结果时将询问用户是否重新生成")
            
            # 检查输入目录是否存在
            if not os.path.exists(self.input_dir):
                logger.error(f"❌ 输入目录不存在: {self.input_dir}")
                return False
            
            # 检查是否有可用的提示词
            if not self.conclude_prompts:
                logger.error(f"❌ 未加载任何总结提示词")
                return False
            
            # 处理所有论文
            success_count, total_count = self.process_directory()
            
            logger.info(f"🎉 处理完成！成功处理 {success_count}/{total_count} 篇论文")
            logger.info(f"📁 结果已保存至: {self.conclude_result_dir}")
            
            # 保存处理日志到markdown文件
            config_info = {
                "输入目录": self.input_dir,
                "提示词目录": self.conclude_prompt_dir,
                "输出目录": self.conclude_result_dir,
                "已加载提示词数量": len(self.conclude_prompts)
            }
            summary_info = f"处理完成，详细结果请查看 `{self.conclude_result_dir}` 目录下的各论文总结文件。"
            
            markdown_saver.save_log_to_markdown(
                title="论文章节总结处理日志",
                config_info=config_info,
                summary_info=summary_info
            )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ 处理论文总结时出现严重错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 即使出错也尝试保存日志
            config_info = {
                "输入目录": getattr(self, 'input_dir', '未知'),
                "提示词目录": getattr(self, 'conclude_prompt_dir', '未知'),
                "输出目录": getattr(self, 'conclude_result_dir', '未知'),
                "已加载提示词数量": len(getattr(self, 'conclude_prompts', {}))
            }
            summary_info = f"处理过程中出现错误: {e}"
            
            markdown_saver.save_log_to_markdown(
                title="论文章节总结处理日志（错误）",
                config_info=config_info,
                summary_info=summary_info
            )
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="对论文进行10个方面的总结")
    parser.add_argument("--input_dir", type=str, help="输入目录，覆盖默认的component_extract路径")
    parser.add_argument("--output_dir", type=str, help="输出目录，覆盖默认的conclude_result路径")
    
    args = parser.parse_args()
    
    # 创建总结器
    concluder = SectionConcluder()
    
    # 如果提供了自定义路径，则更新
    if args.input_dir:
        concluder.input_dir = os.path.abspath(args.input_dir)
        logger.info(f"使用自定义输入目录: {concluder.input_dir}")
    
    if args.output_dir:
        concluder.conclude_result_dir = os.path.abspath(args.output_dir)
        os.makedirs(concluder.conclude_result_dir, exist_ok=True)
        logger.info(f"使用自定义输出目录: {concluder.conclude_result_dir}")
    
    # 执行总结
    success = concluder.conclude_all_papers()
    
    # 根据执行结果设置退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 