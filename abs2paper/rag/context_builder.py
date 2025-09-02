import os
import json
import logging
from typing import Dict, List, Optional, Any

class ContextBuilder:
    """结构化RAG上下文构建器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化上下文构建器"""
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 从配置文件读取映射关系和需求配置
        paper_section_summary_mapping_config = self.config["paper"]["paper_section_summary_mapping"]
        context_info_requirements_config = self.config["paper"]["context_info_requirements"]
        
        # 过滤掉以_开头的元数据字段
        self.paper_section_summary_mapping = {k: v for k, v in paper_section_summary_mapping_config.items() if not k.startswith('_')}
        self.context_info_requirements = {k: v for k, v in context_info_requirements_config.items() if not k.startswith('_')}
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _build_summary_context(self, paper_section: str, 
                              relevant_summaries: Dict[str, List[Dict[str, Any]]]) -> str:
        """构建总结信息上下文"""
        summary_types = self.paper_section_summary_mapping.get(paper_section, [])
        summary_context = []
        
        for summary_type in summary_types:
            summary_type_lower = summary_type.lower()
            if summary_type_lower in relevant_summaries:
                summaries = relevant_summaries[summary_type_lower][:3]  # 取前3个最相关的
                
                summary_context.append(f"### {summary_type} 总结")
                for i, summary in enumerate(summaries, 1):
                    summary_context.append(f"**总结{i}** (来源: {summary['paper_id']}):")
                    summary_context.append(summary['summary_text'][:500] + "..." if len(summary['summary_text']) > 500 else summary['summary_text'])
                    summary_context.append("")
        
        return "\n".join(summary_context)
    
    def _build_trends_context(self, paper_section: str, 
                             cross_paper_insights: Dict[str, Any]) -> str:
        """构建趋势信息上下文"""
        summary_types = self.paper_section_summary_mapping.get(paper_section, [])
        trends_context = []
        
        relevant_insights = {}
        for summary_type in summary_types:
            summary_type_lower = summary_type.lower()
            if summary_type_lower in cross_paper_insights:
                relevant_insights[summary_type] = cross_paper_insights[summary_type_lower]
        
        if relevant_insights:
            trends_context.append("### 研究趋势分析")
            
            for summary_type, insight in relevant_insights.items():
                if insight.get("trends") or insight.get("patterns"):
                    trends_context.append(f"**{summary_type} 趋势**:")
                    
                    # 添加趋势信息
                    if insight.get("trends"):
                        trends_context.append("- 技术趋势: " + ", ".join(insight["trends"][:3]))
                    
                    # 添加模式信息
                    if insight.get("patterns"):
                        trends_context.append("- 研究模式: " + ", ".join(insight["patterns"][:3]))
                    
                    trends_context.append("")
        
        return "\n".join(trends_context)
    
    def _build_source_text_context(self, paper_section: str, 
                                  selected_source_texts: Dict[str, Dict[str, List[str]]]) -> str:
        """构建原文信息上下文"""
        source_context = []
        
        # 根据论文部分确定需要的原文章节
        required_sections = {
            "方法": ["方法"],
            "实验评价": ["实验评价"]
        }
        
        sections_needed = required_sections.get(paper_section, [])
        
        if sections_needed and selected_source_texts:
            source_context.append("### 参考原文")
            
            for paper_id, sections in selected_source_texts.items():
                for section_name in sections_needed:
                    if section_name in sections:
                        chunks = sections[section_name]
                        source_context.append(f"**论文 {paper_id} - {section_name} 章节**:")
                        
                        # 只取前2个chunks，避免上下文过长
                        for i, chunk in enumerate(chunks[:2], 1):
                            truncated_chunk = chunk[:300] + "..." if len(chunk) > 300 else chunk
                            source_context.append(f"片段{i}: {truncated_chunk}")
                        
                        source_context.append("")
        
        return "\n".join(source_context)
    
    def build_structured_contexts(self, 
                                relevant_summaries: Dict[str, List[Dict[str, Any]]],
                                cross_paper_insights: Dict[str, Any],
                                selected_source_texts: Dict[str, Dict[str, List[str]]]) -> Dict[str, str]:
        """
        按生成论文部分构建结构化RAG上下文
        
        Args:
            relevant_summaries: 多类型总结检索结果
            cross_paper_insights: 跨论文分析结果
            selected_source_texts: 选中的原文文本
        
        Returns:
            paper_section_contexts: 各部分的结构化上下文
        """
        logging.info("开始构建结构化RAG上下文")
        
        paper_section_contexts = {}
        
        for paper_section in ["引言", "相关工作", "方法", "实验评价", "总结"]:
            logging.info(f"构建 {paper_section} 部分的上下文")
            
            # 简化的上下文内容
            context_parts = []
            
            # 获取该部分的信息需求
            requirements = self.context_info_requirements[paper_section]
            
            # 1. 添加总结信息
            if requirements["need_summaries"]:
                summary_context = self._build_summary_context(paper_section, relevant_summaries)
                if summary_context:
                    context_parts.append(summary_context)
                    context_parts.append("")
            
            # 2. 添加趋势信息
            if requirements["need_trends"]:
                trends_context = self._build_trends_context(paper_section, cross_paper_insights)
                if trends_context:
                    context_parts.append(trends_context)
                    context_parts.append("")
            
            # 3. 添加原文信息（仅对方法和实验评价部分）
            if requirements["need_source"]:
                source_context = self._build_source_text_context(paper_section, selected_source_texts)
                if source_context:
                    context_parts.append(source_context)
                    context_parts.append("")
            
            # 移除重复的写作要求，这些将在prompt模板中统一处理
            
            paper_section_contexts[paper_section] = "\n".join(context_parts)
            
            # 统计上下文长度
            context_length = len(paper_section_contexts[paper_section])
            logging.info(f"{paper_section} 部分上下文构建完成，长度: {context_length} 字符")
        
        total_contexts = len(paper_section_contexts)
        total_length = sum(len(context) for context in paper_section_contexts.values())
        logging.info(f"结构化RAG上下文构建完成，共 {total_contexts} 个部分，总长度: {total_length} 字符")
        
        return paper_section_contexts
    
    def get_context_statistics(self, paper_section_contexts: Dict[str, str]) -> Dict[str, Any]:
        """获取上下文统计信息"""
        stats = {
            "total_sections": len(paper_section_contexts),
            "total_length": sum(len(context) for context in paper_section_contexts.values()),
            "section_lengths": {section: len(context) for section, context in paper_section_contexts.items()},
            "average_length": 0
        }
        
        if stats["total_sections"] > 0:
            stats["average_length"] = stats["total_length"] // stats["total_sections"]
        
        return stats 