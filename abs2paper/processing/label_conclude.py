"""
结论处理模块，负责处理和汇总论文处理结果
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import sys

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def add_paper_result(paper_name: str, result: str, results_list: Optional[List] = None) -> List[Dict[str, str]]:
    """
    将论文结果添加到结果列表
    
    Args:
        paper_name: 论文名称
        result: 标签结果
        results_list: 已有的结果列表，如果为None则创建新列表
        
    Returns:
        更新后的结果列表
    """
    if results_list is None:
        results_list = []
    
    results_list.append({
        "paper": paper_name,
        "labels": result.strip()
    })
    
    return results_list


def save_results(results_list: List[Dict[str, str]], output_dir: str) -> Dict[str, int]:
    """
    保存结果到文件并进行关键词统计
    
    Args:
        results_list: 结果列表
        output_dir: 输出目录
        
    Returns:
        关键词计数字典
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存完整结果
    results_file = os.path.join(output_dir, "paper_labels_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results_list, f, ensure_ascii=False, indent=2)
    logger.info(f"📊 论文标签结果已保存至 {results_file}")
    
    # 提取关键词并计数
    keyword_counts = extract_keywords_count(results_list)
    
    # 保存关键词统计
    keywords_file = os.path.join(output_dir, "keyword_counts.json")
    with open(keywords_file, "w", encoding="utf-8") as f:
        json.dump(keyword_counts, f, ensure_ascii=False, indent=2)
    logger.info(f"📊 关键词统计已保存至 {keywords_file}")
    
    return keyword_counts


def extract_keywords_count(results_list: List[Dict[str, str]]) -> Dict[str, int]:
    """
    从结果列表中提取关键词并统计
    
    Args:
        results_list: 结果列表
        
    Returns:
        关键词计数字典
    """
    keyword_counts = {}
    
    for result in results_list:
        labels = result.get("labels", "").split("，")
        for label in labels:
            label = label.strip()
            if label:
                keyword_counts[label] = keyword_counts.get(label, 0) + 1
    
    # 按计数排序
    sorted_counts = dict(sorted(
        keyword_counts.items(), 
        key=lambda x: x[1], 
        reverse=True
    ))
    
    return sorted_counts


def generate_keywords_summary(keyword_counts: Dict[str, int], threshold: int = 3) -> str:
    """
    根据关键词统计生成摘要报告
    
    Args:
        keyword_counts: 关键词计数字典
        threshold: 最小出现次数阈值
        
    Returns:
        摘要报告文本
    """
    filtered_keywords = {k: v for k, v in keyword_counts.items() if v >= threshold}
    total_papers = sum(keyword_counts.values()) // max(len(keyword_counts), 1)
    
    report = []
    report.append(f"# 论文关键词分析报告")
    report.append(f"\n## 基本统计")
    report.append(f"- 总论文数: {total_papers}")
    report.append(f"- 唯一关键词数: {len(keyword_counts)}")
    report.append(f"- 出现{threshold}次以上的关键词: {len(filtered_keywords)}")
    
    report.append(f"\n## 热门关键词 (出现{threshold}次以上)")
    report.append(f"| 关键词 | 出现次数 | 占比 |")
    report.append(f"|--------|----------|------|")
    
    for keyword, count in filtered_keywords.items():
        percentage = count / total_papers * 100
        report.append(f"| {keyword} | {count} | {percentage:.1f}% |")
    
    return "\n".join(report)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="处理论文标签结果并生成汇总")
    parser.add_argument("--results_dir", type=str, required=True,
                      help="包含论文标签结果的目录")
    parser.add_argument("--threshold", type=int, default=3,
                      help="关键词最小出现次数阈值")
    
    args = parser.parse_args()
    
    # 加载结果
    results_file = os.path.join(args.results_dir, "paper_labels_results.json")
    if not os.path.exists(results_file):
        logger.error(f"结果文件不存在: {results_file}")
        return
    
    with open(results_file, "r", encoding="utf-8") as f:
        results_list = json.load(f)
    
    # 提取关键词并计数
    keyword_counts = extract_keywords_count(results_list)
    
    # 生成摘要报告
    report = generate_keywords_summary(keyword_counts, args.threshold)
    
    # 保存报告
    report_file = os.path.join(args.results_dir, "keywords_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"📊 关键词分析报告已保存至 {report_file}")


if __name__ == "__main__":
    main()
