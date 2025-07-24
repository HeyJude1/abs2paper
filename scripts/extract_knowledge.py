#!/usr/bin/env python3
"""
知识提取集成脚本，集成所有提取步骤，提供完整的论文知识提取流程
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, List, Set

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入类而不是函数
from abs2paper.extraction.text import extract_text
from abs2paper.extraction.component import ComponentExtractor
from abs2paper.extraction.abstract import AbstractExtractor
from abs2paper.processing.labeling import PaperLabeler

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_extraction_pipeline(steps: Optional[Set[int]] = None) -> bool:
    """
    运行论文知识提取管道
    Args:
        steps: 要执行的步骤集合，如{1, 2, 3, 4}。None表示执行所有步骤。
    Returns:
        执行是否成功
    """
    # 如果未指定步骤，默认执行所有步骤
    if steps is None:
        steps = {1, 2, 3, 4}
    success = True
    
    # 1. 原始文本提取：从PDF提取XML文件
    if 1 in steps:
        logger.info("=========== 步骤1: 原始文本提取 ===========")
        if not extract_text():
            logger.error("文本提取失败")
            success = False
    
    # 2. 组件提取：从文本提取结构化组件
    if 2 in steps and success:
        logger.info("=========== 步骤2: 组件提取 ===========")
        component_extractor = ComponentExtractor()
        if not component_extractor.extract():
            logger.error("组件提取失败")
            success = False
    
    # 3. 摘要提取：从XML提取摘要、标题和关键词
    if 3 in steps and success:
        logger.info("=========== 步骤3: 摘要提取 ===========")
        abstract_extractor = AbstractExtractor()
        if not abstract_extractor.extract():
            logger.error("摘要提取失败")
            success = False
    
    # 4. 标签处理：使用LLM对论文进行分类
    if 4 in steps and success:
        logger.info("=========== 步骤4: 标签处理 ===========")
        labeler = PaperLabeler()
        logger.info(f"🚀 开始处理论文，源目录: {labeler.input_dir}")
        success_count, total_count, all_paper_results = labeler.process_directory()
        if all_paper_results:
            keyword_counts = labeler.save_results(all_paper_results)
            logger.info(f"📊 关键词统计完成，共 {len(keyword_counts)} 个关键词")
            logger.info(f"🎉 处理完成！成功处理 {success_count}/{total_count} 个文件。")
            logger.info(f"✅ 标签处理完成，输出到 {labeler.output_dir}")
        else:
            logger.error("标签处理失败")
            success = False

    if success:
        logger.info("✅ 知识提取管道执行完成")
    else:
        logger.warning("⚠️ 知识提取管道执行过程中出现错误")
    return success


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行论文知识提取管道")
    
    # 添加步骤选择参数
    parser.add_argument("--steps", type=int, nargs='+', 
                      help="指定要执行的步骤，可选1-4，例如: --steps 1 3 4")
    
    args = parser.parse_args()
    
    # 解析要执行的步骤
    steps = None
    if args.steps:
        steps = set(args.steps)
        # 验证步骤有效性
        for step in steps:
            if step < 1 or step > 4:
                logger.error(f"无效的步骤 {step}，步骤必须是1-4之间的数字")
                sys.exit(1)
        logger.info(f"将执行指定步骤: {sorted(list(steps))}")
    else:
        logger.info("将执行全部步骤: [1, 2, 3, 4]")
    
    # 执行管道
    success = run_extraction_pipeline(steps)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main() 