import os
import json
import logging
from typing import Dict, List, Optional, Any

from abs2paper.utils.db_client import MilvusClient

class SourceTextRetriever:
    """基于最相关总结的原文获取器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化原文获取器"""
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 读取数据库配置
        vector_db_config = self.config["vector_db"]
        db_config = {
            "host": vector_db_config["host"],
            "port": vector_db_config["port"],
            "alias": vector_db_config["alias"],
            "db_name": vector_db_config["db_name"]
        }
        self.db_client = MilvusClient(db_config)
        
        # 基于CONCLUDE_ASPECTS的原文章节需求映射
        self.paper_section_source_mapping = {
            "方法": ["方法"],
            "实验评价": ["实验评价"]
        }
        
        # 章节名称到collection的映射
        self.collection_mapping = {
            "引言": "paper_introduction",
            "相关工作": "paper_related_work", 
            "方法": "paper_methodology",
            "实验评价": "paper_experiments",
            "总结": "paper_conclusion"
        }
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _find_most_relevant_paper(self, relevant_summaries: Dict[str, List[Dict[str, Any]]], 
                                summary_types: List[str]) -> Optional[str]:
        """
        从指定类型的总结中找到最相关的论文ID
        
        Args:
            relevant_summaries: 检索到的相关总结
            summary_types: 要考虑的总结类型列表
        
        Returns:
            最相关论文的paper_id
        """
        best_paper_id = None
        best_score = float('inf')  # L2距离越小越好
        
        for summary_type in summary_types:
            if summary_type in relevant_summaries:
                summaries = relevant_summaries[summary_type]
                if summaries:  # 取第一个（最相关的）
                    top_summary = summaries[0]
                    score = top_summary.get('score', float('inf'))
                    if score < best_score:
                        best_score = score
                        best_paper_id = top_summary['paper_id']
        
        return best_paper_id
    
    def _get_complete_section_content(self, paper_id: str, section_name: str) -> List[str]:
        """
        获取论文指定章节的完整内容
        Args:
            paper_id: 论文ID
            section_name: 章节名称
        Returns:
            章节内容列表（多个chunks组合）
        """
        collection_name = self.collection_mapping.get(section_name)
        if not collection_name:
            logging.warning(f"未知的章节名称: {section_name}")
            return []
        
        try:
            # 构建查询过滤条件，支持两种格式的paper_id匹配
            # 1. 简化格式：如 "3688609"
            # 2. 完整格式：如 "ICS/2023/3577193.3593712_0"
            
            # 先尝试精确匹配简化格式
            query_filter = f"paper_id like '%/{paper_id}_%'"
            
            results = self.db_client.query(
                collection_name=collection_name,
                filter=query_filter,
                output_fields=["paper_id", "text"],
                limit=100
            )
            
            # 如果没有结果，尝试直接匹配（可能总结中的paper_id就是完整格式）
            if not results:
                query_filter = f"paper_id like '{paper_id}%'"
                results = self.db_client.query(
                    collection_name=collection_name,
                    filter=query_filter,
                    output_fields=["paper_id", "text"],
                    limit=100
                )
            
            # 如果还是没有结果，尝试包含匹配
            if not results:
                query_filter = f"paper_id like '%{paper_id}%'"
                results = self.db_client.query(
                    collection_name=collection_name,
                    filter=query_filter,
                    output_fields=["paper_id", "text"],
                    limit=100
                )
            
            if not results:
                logging.warning(f"未找到论文 {paper_id} 的 {section_name} 章节内容")
                return []
            
            # 按paper_id排序，确保chunks的顺序正确
            def extract_chunk_number(pid):
                """从paper_id中提取chunk编号"""
                try:
                    if '_' in pid:
                        return int(pid.split('_')[-1])
                    return 0
                except:
                    return 0
            
            sorted_results = sorted(results, key=lambda x: extract_chunk_number(x['paper_id']))
            
            # 提取文本内容
            section_content = []
            for result in sorted_results:
                text = result.get('text', '')
                if text:
                    section_content.append(text)
            
            logging.info(f"成功获取论文 {paper_id} 的 {section_name} 章节内容，共 {len(section_content)} 个chunks")
            return section_content
            
        except Exception as e:
            logging.error(f"获取章节内容失败: {paper_id}, {section_name}, 错误: {e}")
            return []
    
    def select_most_relevant_source_texts(self, relevant_summaries: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, List[str]]]:
        """
        基于最相关总结选择对应的原文章节
        
        策略：
        1. 对于"方法"上下文：选择Methodology总结中最相关的那个论文的完整"方法"章节
        2. 对于"实验评价"上下文：选择4个实验相关总结中最相关的那个论文的完整"实验评价"章节
        3. 不需要chunks选择，直接使用完整章节内容
        4. 最多只有2篇论文的原文（方法1篇+实验评价1篇）
        
        Args:
            relevant_summaries: 检索到的相关总结
        
        Returns:
            selected_source_texts: 选中的原文文本
        """
        logging.info("开始基于最相关总结选择原文章节")
        
        selected_source_texts = {}
        
        # 1. 选择最相关的Methodology论文的方法章节
        methodology_paper_id = self._find_most_relevant_paper(
            relevant_summaries, ["methodology"]
        )
        if methodology_paper_id:
            method_content = self._get_complete_section_content(
                methodology_paper_id, "方法"
            )
            if method_content:
                selected_source_texts[methodology_paper_id] = {
                    "方法": method_content
                }
                logging.info(f"选择论文 {methodology_paper_id} 的方法章节作为参考")
        
        # 2. 选择最相关的实验评价论文的实验评价章节
        experiment_paper_id = self._find_most_relevant_paper(
            relevant_summaries, ["expedesign", "baseline", "metric", "resultanalysis"]
        )
        if experiment_paper_id and experiment_paper_id != methodology_paper_id:
            experiment_content = self._get_complete_section_content(
                experiment_paper_id, "实验评价"
            )
            if experiment_content:
                selected_source_texts[experiment_paper_id] = {
                    "实验评价": experiment_content
                }
                logging.info(f"选择论文 {experiment_paper_id} 的实验评价章节作为参考")
        elif experiment_paper_id == methodology_paper_id:
            # 如果是同一篇论文，添加实验评价章节
            experiment_content = self._get_complete_section_content(
                experiment_paper_id, "实验评价"
            )
            if experiment_content:
                if methodology_paper_id in selected_source_texts:
                    selected_source_texts[methodology_paper_id]["实验评价"] = experiment_content
                else:
                    selected_source_texts[methodology_paper_id] = {
                        "实验评价": experiment_content
                    }
                logging.info(f"为论文 {methodology_paper_id} 添加实验评价章节")
        
        # 统计结果
        total_papers = len(selected_source_texts)
        total_sections = sum(len(sections) for sections in selected_source_texts.values())
        total_chunks = sum(
            len(chunks) for paper_sections in selected_source_texts.values()
            for chunks in paper_sections.values()
        )
        
        logging.info(f"原文选择完成：{total_papers} 篇论文，{total_sections} 个章节，{total_chunks} 个chunks")
        
        return selected_source_texts
    
    def get_source_text_statistics(self, selected_source_texts: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
        """获取原文选择统计信息"""
        stats = {
            "total_papers": len(selected_source_texts),
            "total_sections": sum(len(sections) for sections in selected_source_texts.values()),
            "total_chunks": sum(
                len(chunks) for paper_sections in selected_source_texts.values()
                for chunks in paper_sections.values()
            ),
            "paper_details": {}
        }
        
        for paper_id, sections in selected_source_texts.items():
            stats["paper_details"][paper_id] = {
                "sections": list(sections.keys()),
                "section_chunks": {section: len(chunks) for section, chunks in sections.items()},
                "total_chunks": sum(len(chunks) for chunks in sections.values())
            }
        
        return stats 