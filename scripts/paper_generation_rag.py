#!/usr/bin/env python3
"""
论文生成RAG系统主脚本
基于用户需求，通过RAG流程生成完整论文
"""

import os
import sys
import argparse
import json
import logging
from typing import Dict, List, Optional, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abs2paper.rag.summary_retriever import SummaryRetriever
from abs2paper.rag.cross_paper_analyzer import CrossPaperAnalyzer
from abs2paper.rag.source_text_retriever import SourceTextRetriever
from abs2paper.rag.context_builder import ContextBuilder
from abs2paper.rag.paper_generator import PaperGenerator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PaperGenerationRAG:
    """论文生成RAG系统"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化RAG系统"""
        self.config_path = config_path
        
        # 初始化各个模块
        self.summary_retriever = SummaryRetriever(config_path)
        self.cross_paper_analyzer = CrossPaperAnalyzer(config_path)
        self.source_text_retriever = SourceTextRetriever(config_path)
        self.context_builder = ContextBuilder(config_path)
        self.paper_generator = PaperGenerator(config_path)
        
        # 存储中间结果
        self.relevant_summaries = {}
        self.cross_paper_insights = {}
        self.selected_source_texts = {}
        self.paper_section_contexts = {}
        self.generated_sections = {}
    
    def step1_retrieve_summaries(self, user_requirement: str, top_k_per_type: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        步骤1：多类型总结并行检索
        
        Args:
            user_requirement: 用户需求
            top_k_per_type: 每种类型返回的最大结果数
        
        Returns:
            relevant_summaries: 检索到的相关总结
        """
        logger.info("=" * 50)
        logger.info("步骤1：多类型总结并行检索")
        logger.info("=" * 50)
        
        self.relevant_summaries = self.summary_retriever.parallel_retrieve_summaries(
            user_requirement, top_k_per_type
        )
        
        # 输出统计信息
        stats = self.summary_retriever.get_retrieval_statistics(self.relevant_summaries)
        logger.info(f"检索统计：共检索到 {stats['total_summaries']} 个总结，涵盖 {stats['types_found']} 种类型")
        logger.info(f"涉及 {stats['unique_papers']} 篇不同论文")
        
        return self.relevant_summaries
    
    def step2_analyze_cross_paper(self) -> Dict[str, Any]:
        """
        步骤2：跨论文同类型分析
        
        Returns:
            cross_paper_insights: 跨论文分析结果
        """
        logger.info("=" * 50)
        logger.info("步骤2：跨论文同类型分析")
        logger.info("=" * 50)
        
        if not self.relevant_summaries:
            logger.error("未找到相关总结，请先执行步骤1")
            return {}
        
        self.cross_paper_insights = self.cross_paper_analyzer.analyze_cross_paper_patterns(
            self.relevant_summaries
        )
        
        # 输出统计信息
        stats = self.cross_paper_analyzer.get_analysis_statistics(self.cross_paper_insights)
        logger.info(f"分析统计：共分析了 {stats['analyzed_types']} 种类型")
        logger.info(f"识别出 {stats['total_patterns']} 个模式，{stats['total_trends']} 个趋势")
        
        return self.cross_paper_insights
    
    def step3_retrieve_source_texts(self) -> Dict[str, Dict[str, List[str]]]:
        """
        步骤3：根据总结获取对应原文章节
        
        Returns:
            selected_source_texts: 选中的原文文本
        """
        logger.info("=" * 50)
        logger.info("步骤3：根据总结获取对应原文章节")
        logger.info("=" * 50)
        
        if not self.relevant_summaries:
            logger.error("未找到相关总结，请先执行步骤1")
            return {}
        
        self.selected_source_texts = self.source_text_retriever.select_most_relevant_source_texts(
            self.relevant_summaries
        )
        
        # 输出统计信息
        stats = self.source_text_retriever.get_source_text_statistics(self.selected_source_texts)
        logger.info(f"原文统计：选择了 {stats['total_papers']} 篇论文的 {stats['total_sections']} 个章节")
        logger.info(f"共包含 {stats['total_chunks']} 个文本块")
        
        return self.selected_source_texts
    
    def step4_build_contexts(self) -> Dict[str, str]:
        """
        步骤4：按生成论文部分构建结构化RAG上下文
        
        Returns:
            paper_section_contexts: 各部分的结构化上下文
        """
        logger.info("=" * 50)
        logger.info("步骤4：按生成论文部分构建结构化RAG上下文")
        logger.info("=" * 50)
        
        if not self.relevant_summaries:
            logger.error("未找到相关总结，请先执行步骤1")
            return {}
        
        self.paper_section_contexts = self.context_builder.build_structured_contexts(
            self.relevant_summaries,
            self.cross_paper_insights,
            self.selected_source_texts
        )
        
        # 输出统计信息
        stats = self.context_builder.get_context_statistics(self.paper_section_contexts)
        logger.info(f"上下文统计：构建了 {stats['total_sections']} 个部分的上下文")
        logger.info(f"总长度 {stats['total_length']} 字符，平均长度 {stats['average_length']} 字符")
        
        return self.paper_section_contexts
    
    def step5_generate_paper(self, user_requirement: str) -> Dict[str, str]:
        """
        步骤5：顺序化论文生成流程
        
        Args:
            user_requirement: 用户需求
        
        Returns:
            generated_sections: 生成的论文各部分
        """
        logger.info("=" * 50)
        logger.info("步骤5：顺序化论文生成流程")
        logger.info("=" * 50)
        
        if not self.paper_section_contexts:
            logger.error("未找到结构化上下文，请先执行步骤4")
            return {}
        
        self.generated_sections = self.paper_generator.generate_paper_sequentially(
            self.paper_section_contexts,
            user_requirement
        )
        
        # 输出统计信息
        stats = self.paper_generator.get_generation_statistics(self.generated_sections)
        logger.info(f"生成统计：生成了 {stats['total_sections']} 个部分")
        logger.info(f"总长度 {stats['total_length']} 字符，平均长度 {stats['average_length']} 字符")
        
        return self.generated_sections
    
    def run_full_pipeline(self, user_requirement: str, output_file: Optional[str] = None) -> Dict[str, str]:
        """
        运行完整的论文生成流程
        
        Args:
            user_requirement: 用户需求
            output_file: 输出文件路径（可选）
        
        Returns:
            generated_sections: 生成的论文各部分
        """
        logger.info("🚀 开始完整的论文生成RAG流程")
        logger.info(f"用户需求：{user_requirement}")
        
        try:
            # 执行所有步骤
            self.step1_retrieve_summaries(user_requirement)
            self.step2_analyze_cross_paper()
            self.step3_retrieve_source_texts()
            self.step4_build_contexts()
            self.step5_generate_paper(user_requirement)
            
            # 保存结果
            if output_file and self.generated_sections:
                self.save_generated_paper(output_file)
            
            logger.info("🎉 论文生成RAG流程完成")
            return self.generated_sections
            
        except Exception as e:
            logger.error(f"论文生成流程出错：{e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    def save_generated_paper(self, output_file: str):
        """保存生成的论文到文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# 基于RAG生成的论文\n\n")
                
                for section_name in ["引言", "相关工作", "方法", "实验评价", "总结"]:
                    if section_name in self.generated_sections:
                        f.write(f"## {section_name}\n\n")
                        f.write(self.generated_sections[section_name])
                        f.write("\n\n")
            
            logger.info(f"论文已保存到：{output_file}")
            
        except Exception as e:
            logger.error(f"保存论文失败：{e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="论文生成RAG系统")
    parser.add_argument("requirement", nargs='?', help="用户需求（1-2句话描述要生成的论文）")
    parser.add_argument("--step", type=int, choices=[1, 2, 3, 4, 5], 
                       help="指定运行的步骤（1-5），不指定则运行完整流程")
    parser.add_argument("--output", type=str, help="输出文件路径")
    parser.add_argument("--config", type=str, help="配置文件路径")
    
    args = parser.parse_args()
    
    # 检查用户需求
    if not args.requirement and not args.step:
        print("错误：请提供用户需求")
        print("示例：python paper_generation_rag.py '基于深度学习的图像分类方法研究'")
        sys.exit(1)
    
    try:
        # 初始化RAG系统
        rag_system = PaperGenerationRAG(args.config)
        
        if args.step:
            # 运行指定步骤
            logger.info(f"运行步骤 {args.step}")
            
            if args.step == 1:
                if not args.requirement:
                    logger.error("步骤1需要用户需求参数")
                    sys.exit(1)
                result = rag_system.step1_retrieve_summaries(args.requirement)
            elif args.step == 2:
                result = rag_system.step2_analyze_cross_paper()
            elif args.step == 3:
                result = rag_system.step3_retrieve_source_texts()
            elif args.step == 4:
                result = rag_system.step4_build_contexts()
            elif args.step == 5:
                if not args.requirement:
                    logger.error("步骤5需要用户需求参数")
                    sys.exit(1)
                result = rag_system.step5_generate_paper(args.requirement)
            
            logger.info(f"步骤 {args.step} 执行完成")
            
        else:
            # 运行完整流程
            result = rag_system.run_full_pipeline(args.requirement, args.output)
            
            if result:
                logger.info("完整流程执行成功")
            else:
                logger.error("完整流程执行失败")
                sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("用户中断程序")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行出错：{e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 