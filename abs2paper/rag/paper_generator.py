import os
import json
import logging
from typing import Dict, List, Optional, Any

from abs2paper.utils.llm_client import LLMClient

class PaperGenerator:
    """顺序化论文生成器 - 解决逻辑连贯性问题"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化论文生成器"""
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 初始化LLM客户端
        self.llm_client = LLMClient()
        
        # 获取paper_prompt路径
        data_paths = self.config["data_paths"]
        paper_prompt_path = data_paths["paper_prompt"]["path"].lstrip('/')
        self.paper_prompt_dir = os.path.join(self.project_root, paper_prompt_path)
        
        # 从配置加载生成顺序和提示词映射
        paper_config = self.config["paper"]
        self.generation_order = paper_config["generation_order"]["steps"]
        self.prompt_files = paper_config["prompt_files"]
        
        # 加载所有论文生成提示词
        self.paper_prompts = self._load_all_prompts()
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_all_prompts(self) -> Dict[str, str]:
        """加载所有论文生成相关的提示词"""
        all_prompts = {}
        
        # 加载章节生成提示词
        for section, prompt_file in self.prompt_files["section_prompts"].items():
            prompt_path = os.path.join(self.paper_prompt_dir, prompt_file)
            prompt_content = self._load_single_prompt(prompt_path, f"{section}生成")
            if prompt_content:
                all_prompts[f"section_{section}"] = prompt_content
        
        # 加载工具提示词
        for tool_name, prompt_file in self.prompt_files["utility_prompts"].items():
            prompt_path = os.path.join(self.paper_prompt_dir, prompt_file)
            prompt_content = self._load_single_prompt(prompt_path, tool_name)
            if prompt_content:
                all_prompts[tool_name] = prompt_content
        
        logging.info(f"📝 总共加载了 {len(all_prompts)} 个论文生成提示词")
        return all_prompts
    
    def _load_single_prompt(self, prompt_path: str, prompt_name: str) -> Optional[str]:
        """加载单个提示词文件"""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
                if prompt_content:
                    logging.info(f"✅ 已加载 {prompt_name} 提示词")
                    return prompt_content
                else:
                    logging.warning(f"⚠️ {prompt_name} 提示词文件为空: {prompt_path}")
                    return None
        
        except FileNotFoundError:
            logging.error(f"❌ 未找到 {prompt_name} 提示词文件: {prompt_path}")
            return None
        except Exception as e:
            logging.error(f"❌ 加载 {prompt_name} 提示词时出错: {e}")
            return None
    
    def _generate_section_content(self, section_name: str, 
                                context: str, 
                                user_requirement: str) -> str:
        """生成特定部分的内容"""
        # 使用配置中的提示词
        prompt_key = f"section_{section_name}"
        if prompt_key not in self.paper_prompts:
            error_msg = f"未找到 {section_name} 的提示词模板，请检查配置文件和提示词文件"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        # 构建完整的提示词
        base_prompt = self.paper_prompts[prompt_key]
        full_prompt = f"{base_prompt}\n\n{context}"
        
        return self.llm_client.get_completion(full_prompt)
    
    def _generate_section_summary(self, section_name: str, content: str) -> str:
        """生成部分内容的概述，供后续部分使用"""
        if "section_summary" not in self.paper_prompts:
            error_msg = "未找到章节概述生成提示词，请检查配置文件和SectionSummary_prompt文件"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        # 构建完整的提示词
        base_prompt = self.paper_prompts["section_summary"]
        full_prompt = f"{base_prompt}\n\n{content}"
        
        return self.llm_client.get_completion(full_prompt)
    
    def _build_full_context_for_section(self, section_name: str,
                                       base_context: str,
                                       previous_sections: Dict[str, str],
                                       section_summaries: Dict[str, str],
                                       step_config: Dict,
                                       user_requirement: str) -> str:
        """为当前部分构建包含前置依赖的完整上下文"""
        
        context_parts = [
            f"# 生成论文{section_name}部分",
            f"**用户需求**: {user_requirement}",
            ""
        ]
        
        # 添加前置部分的上下文（如果需要）
        if step_config.get("previous_context_needed", False):
            context_parts.append("## 已生成的前置部分")
            
            for dep_section in step_config["dependencies"]:
                if dep_section in section_summaries:
                    context_parts.append(f"### {dep_section}部分概述")
                    context_parts.append(section_summaries[dep_section])
                    context_parts.append("")
        
        # 添加基础RAG上下文
        context_parts.append("## 参考资料")
        context_parts.append(base_context)
        
        # 添加写作指导
        context_parts.extend([
            "",
            "## 写作要求",
            f"1. 确保与前面已生成的部分在逻辑上连贯",
            f"2. 避免与前面部分内容重复",
            f"3. 保持学术论文的严谨性和专业性",
            f"4. 字数控制在800-1200字之间",
            f"5. 使用规范的学术写作格式"
        ])
        
        return "\n".join(context_parts)
    
    def _polish_entire_paper(self, sections: Dict[str, str], 
                           user_requirement: str) -> Dict[str, str]:
        """对整篇论文进行统一润色，确保逻辑连贯性"""
        
        if "paper_polish" not in self.paper_prompts:
            error_msg = "未找到论文润色提示词，请检查配置文件和PaperPolish_prompt文件"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        # 构建完整的提示词
        base_prompt = self.paper_prompts["paper_polish"]
        formatted_sections = self._format_sections_for_polish(sections)
        full_prompt = f"{base_prompt}\n\n原始内容：\n{formatted_sections}"
        
        polished_content = self.llm_client.get_completion(full_prompt)
        
        # 解析润色后的内容
        polished_sections = self._parse_polished_content(polished_content)
        
        return polished_sections if polished_sections else sections
    
    def _format_sections_for_polish(self, sections: Dict[str, str]) -> str:
        """格式化各部分内容用于润色"""
        formatted_content = []
        for section_name in ["引言", "相关工作", "方法", "实验评价", "总结"]:
            if section_name in sections:
                formatted_content.append(f"## {section_name}")
                formatted_content.append(sections[section_name])
                formatted_content.append("")
        
        return "\n".join(formatted_content)
    
    def _parse_polished_content(self, content: str) -> Dict[str, str]:
        """解析润色后的内容，分割成各个部分"""
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            if line.startswith('## '):
                # 保存前一个部分
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新部分
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # 保存最后一个部分
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def generate_paper_sequentially(self, paper_section_contexts: Dict[str, str],
                                   user_requirement: str) -> Dict[str, str]:
        """
        按顺序生成论文各部分，保持逻辑连贯性
        
        流程：
        1. 按依赖顺序生成各部分
        2. 每生成一部分就提取概述供后续使用
        3. 最后统一润色保证整体连贯性
        
        Args:
            paper_section_contexts: 各部分的RAG上下文
            user_requirement: 用户需求
        
        Returns:
            生成的论文各部分内容
        """
        logging.info("开始顺序化论文生成流程")
        
        generated_sections = {}
        section_summaries = {}  # 存储各部分的概述，供后续部分使用
        
        for step in self.generation_order:
            section_name = step["section"]
            logging.info(f"🔄 生成论文{section_name}部分...")
            
            # 构建当前部分的完整上下文
            full_context = self._build_full_context_for_section(
                section_name=section_name,
                base_context=paper_section_contexts[section_name],
                previous_sections=generated_sections,
                section_summaries=section_summaries,
                step_config=step,
                user_requirement=user_requirement
            )
            
            # 生成当前部分
            generated_content = self._generate_section_content(
                section_name=section_name,
                context=full_context,
                user_requirement=user_requirement
            )
            
            generated_sections[section_name] = generated_content
            logging.info(f"✅ {section_name}部分生成完成")
            
            # 生成当前部分的概述，供后续部分使用
            section_summary = self._generate_section_summary(
                section_name, generated_content
            )
            section_summaries[section_name] = section_summary
        
        # 最后进行全文统一润色
        logging.info("🎨 开始全文统一润色...")
        polished_sections = self._polish_entire_paper(
            generated_sections, user_requirement
        )
        logging.info("✅ 论文生成完成")
        
        return polished_sections
    
    def get_generation_statistics(self, generated_sections: Dict[str, str]) -> Dict[str, Any]:
        """获取生成统计信息"""
        stats = {
            "total_sections": len(generated_sections),
            "total_length": sum(len(content) for content in generated_sections.values()),
            "section_lengths": {section: len(content) for section, content in generated_sections.items()},
            "average_length": 0,
            "sections_generated": list(generated_sections.keys())
        }
        
        if stats["total_sections"] > 0:
            stats["average_length"] = stats["total_length"] // stats["total_sections"]
        
        return stats 