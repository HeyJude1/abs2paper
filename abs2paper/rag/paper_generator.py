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
        
        # 加载论文生成提示词
        self.paper_prompts = self._load_paper_prompts()
        
        # 论文部分生成顺序和依赖关系
        self.generation_order = [
            {
                "section": "引言",
                "dependencies": [],
                "context_sources": ["Background", "Challenges", "Innovations"],
                "include_source_text": False,
                "previous_context_needed": False
            },
            {
                "section": "相关工作", 
                "dependencies": ["引言"],
                "context_sources": ["RelatedWork", "Challenges"],
                "include_source_text": False,
                "previous_context_needed": True,
                "previous_context_type": "概述"  # 只需要引言的概述
            },
            {
                "section": "方法",
                "dependencies": ["引言", "相关工作"],
                "context_sources": ["Methodology"],
                "include_source_text": True,
                "previous_context_needed": True,
                "previous_context_type": "概述"  # 需要引言+相关工作的概述
            },
            {
                "section": "实验评价",
                "dependencies": ["方法"],
                "context_sources": ["ExpeDesign", "Baseline", "Metric", "ResultAnalysis"],
                "include_source_text": True,
                "previous_context_needed": True,
                "previous_context_type": "详细"  # 需要方法的详细内容
            },
            {
                "section": "总结",
                "dependencies": ["引言", "相关工作", "方法", "实验评价"],
                "context_sources": ["Conclusion", "ResultAnalysis", "Innovations"],
                "include_source_text": False,
                "previous_context_needed": True,
                "previous_context_type": "概述"  # 需要全文概述
            }
        ]
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_paper_prompts(self) -> Dict[str, str]:
        """加载论文生成提示词"""
        paper_prompts = {}
        
        # 5个论文部分对应的prompt文件
        section_prompts = {
            "引言": "Introduction_prompt",
            "相关工作": "RelatedWork_prompt", 
            "方法": "Methodology_prompt",
            "实验评价": "Experiments_prompt",
            "总结": "Conclusion_prompt"
        }
        
        for section, prompt_file in section_prompts.items():
            prompt_path = os.path.join(self.paper_prompt_dir, prompt_file)
            
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_content = f.read().strip()
                    if prompt_content:
                        paper_prompts[section] = prompt_content
                        logging.info(f"✅ 已加载 {section} 生成提示词")
                    else:
                        logging.warning(f"⚠️ {section} 提示词文件为空: {prompt_path}")
            
            except FileNotFoundError:
                logging.error(f"❌ 未找到 {section} 提示词文件: {prompt_path}")
            except Exception as e:
                logging.error(f"❌ 加载 {section} 提示词时出错: {e}")
        
        logging.info(f"📝 总共加载了 {len(paper_prompts)} 个论文生成提示词")
        return paper_prompts
    
    def _generate_section_content(self, section_name: str, 
                                context: str, 
                                user_requirement: str) -> str:
        """生成特定部分的内容"""
        # 使用加载的提示词模板
        if section_name not in self.paper_prompts:
            logging.error(f"未找到 {section_name} 的提示词模板")
            # 使用默认提示词
            prompt = f"""
请根据以下上下文生成论文的{section_name}部分：

{context}

用户需求：{user_requirement}

要求：
1. 内容要与用户需求"{user_requirement}"高度相关
2. 保持学术论文的规范格式
3. 确保逻辑清晰，表达准确
4. 字数控制在800-1200字之间
5. 使用规范的学术写作格式
"""
        else:
            # 使用加载的提示词模板
            base_prompt = self.paper_prompts[section_name]
            prompt = f"{base_prompt}\n\n{context}"
        
        return self.llm_client.get_completion(prompt)
    
    def _generate_section_summary(self, section_name: str, content: str) -> str:
        """生成部分内容的概述，供后续部分使用"""
        prompt = f"""
请为以下论文{section_name}部分生成一个150字左右的概述，突出关键点：

{content}

要求：
1. 概述要简洁明了，突出核心内容
2. 为后续部分提供必要的逻辑衔接信息
3. 避免过于详细的技术细节
"""
        
        return self.llm_client.get_completion(prompt)
    
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
        
        polish_prompt = f"""
请对以下论文各部分进行整体润色，确保逻辑连贯性：

用户需求：{user_requirement}

请重点关注：
1. 各部分之间的逻辑连接和过渡
2. 术语使用的一致性  
3. 表达的流畅性和学术规范性
4. 避免内容重复和矛盾
5. 确保论文整体结构的完整性

请分别返回润色后的各部分内容，保持以下格式：

## 引言
[润色后的引言内容]

## 相关工作
[润色后的相关工作内容]

## 方法
[润色后的方法内容]

## 实验评价
[润色后的实验评价内容]

## 总结
[润色后的总结内容]

原始内容：
{self._format_sections_for_polish(sections)}
"""
        
        polished_content = self.llm_client.get_completion(polish_prompt)
        
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