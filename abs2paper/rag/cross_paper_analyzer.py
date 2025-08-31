import os
import json
import logging
from typing import Dict, List, Optional, Any
from collections import Counter

from abs2paper.utils.llm_client import LLMClient

class CrossPaperAnalyzer:
    """跨论文同类型分析器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化跨论文分析器"""
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 初始化LLM客户端
        self.llm_client = LLMClient()
        
        # 需要进行跨论文分析的关键类型
        self.key_analysis_types = ['methodology', 'innovations', 'challenges', 'expedesign', 'metric']
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _extract_topic_clusters(self, summaries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """从总结中提取主题聚类"""
        topic_clusters = {}
        
        for summary in summaries:
            topics = summary.get("topics", [])
            for topic in topics:
                if topic not in topic_clusters:
                    topic_clusters[topic] = []
                topic_clusters[topic].append(summary)
        
        return topic_clusters
    
    def _identify_patterns(self, summaries: List[Dict[str, Any]], summary_type: str) -> List[str]:
        """识别同类型总结中的模式"""
        patterns = []
        
        # 基于主题分布识别模式
        all_topics = []
        for summary in summaries:
            all_topics.extend(summary.get("topics", []))
        
        if all_topics:
            topic_counter = Counter(all_topics)
            total_summaries = len(summaries)
            
            # 识别高频主题模式
            for topic, count in topic_counter.most_common(5):
                if count >= 2:  # 至少在2篇论文中出现
                    percentage = (count / total_summaries) * 100
                    patterns.append(f"{topic}在{count}/{total_summaries}篇论文中被提及({percentage:.1f}%)")
        
        return patterns
    
    def _extract_trends(self, summaries: List[Dict[str, Any]], summary_type: str) -> List[str]:
        """提取研究趋势"""
        trends = []
        
        # 基于关键词频率分析趋势
        all_texts = [summary.get("summary_text", "") for summary in summaries]
        combined_text = " ".join(all_texts)
        
        # 不同类型的关键趋势词
        trend_keywords = {
            "methodology": ["深度学习", "端到端", "注意力机制", "Transformer", "多模态", "自监督"],
            "innovations": ["注意力", "残差连接", "批量归一化", "dropout", "正则化", "优化"],
            "challenges": ["数据稀缺", "计算复杂度", "泛化能力", "过拟合", "标注成本", "实时性"],
            "expedesign": ["数据集", "基准测试", "评价指标", "实验设置", "对比实验", "消融实验"],
            "metric": ["准确率", "召回率", "F1分数", "AUC", "BLEU", "ROUGE"]
        }
        
        keywords = trend_keywords.get(summary_type, [])
        for keyword in keywords:
            if keyword in combined_text:
                count = combined_text.count(keyword)
                if count >= 2:
                    trends.append(f"{keyword}技术广泛应用")
        
        return trends
    
    def _identify_common_approaches(self, summaries: List[Dict[str, Any]], summary_type: str) -> List[str]:
        """识别常见方法"""
        approaches = []
        
        # 基于总结文本内容分析常见方法
        all_texts = [summary.get("summary_text", "") for summary in summaries]
        
        # 不同类型的常见方法关键词
        approach_keywords = {
            "methodology": ["基于深度学习", "端到端训练", "注意力机制", "多层感知机", "卷积神经网络"],
            "innovations": ["多头注意力", "残差连接", "批量归一化", "跳跃连接", "特征融合"],
            "expedesign": ["随机划分", "交叉验证", "网格搜索", "早停策略", "数据增强"]
        }
        
        keywords = approach_keywords.get(summary_type, [])
        for keyword in keywords:
            found_count = sum(1 for text in all_texts if keyword in text)
            if found_count >= 2:
                approaches.append(keyword)
        
        return approaches
    
    def _generate_analysis_summary(self, summaries: List[Dict[str, Any]], 
                                 summary_type: str, patterns: List[str], 
                                 trends: List[str]) -> str:
        """生成分析总结"""
        paper_count = len(summaries)
        unique_papers = len(set(summary.get("paper_id", "") for summary in summaries))
        
        summary_text = f"基于{unique_papers}篇论文的{summary_type}分析："
        
        if patterns:
            summary_text += f" 主要模式包括{', '.join(patterns[:3])}。"
        
        if trends:
            summary_text += f" 研究趋势显示{', '.join(trends[:3])}。"
        
        return summary_text
    
    def analyze_cross_paper_patterns(self, relevant_summaries: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        跨论文同类型分析
        
        Args:
            relevant_summaries: 从多类型检索获得的总结结果
            
        Returns:
            cross_paper_insights: 跨论文分析结果
        """
        logging.info("开始跨论文同类型分析")
        
        cross_paper_insights = {}
        
        # 对关键分析类型进行分析
        for summary_type in self.key_analysis_types:
            if summary_type in relevant_summaries:
                summaries = relevant_summaries[summary_type]
                
                if len(summaries) >= 2:  # 至少需要2个总结才能进行跨论文分析
                    logging.info(f"分析 {summary_type} 类型，共 {len(summaries)} 个总结")
                    
                    # 识别模式
                    patterns = self._identify_patterns(summaries, summary_type)
                    
                    # 提取趋势
                    trends = self._extract_trends(summaries, summary_type)
                    
                    # 识别常见方法
                    common_approaches = self._identify_common_approaches(summaries, summary_type)
                    
                    # 主题聚类
                    topic_clusters = self._extract_topic_clusters(summaries)
                    
                    # 生成分析总结
                    analysis_summary = self._generate_analysis_summary(
                        summaries, summary_type, patterns, trends
                    )
                    
                    # 构建分析结果
                    cross_paper_insights[summary_type] = {
                        "summaries": summaries,
                        "patterns": patterns,
                        "trends": trends,
                        "common_approaches": common_approaches,
                        "topic_clusters": topic_clusters,
                        "analysis_summary": analysis_summary
                    }
                    
                    logging.info(f"{summary_type} 分析完成：{len(patterns)} 个模式，{len(trends)} 个趋势")
                else:
                    logging.info(f"{summary_type} 类型总结数量不足，跳过分析")
        
        total_analyzed = len(cross_paper_insights)
        logging.info(f"跨论文同类型分析完成，共分析了 {total_analyzed} 种类型")
        
        return cross_paper_insights
    
    def get_analysis_statistics(self, cross_paper_insights: Dict[str, Any]) -> Dict[str, Any]:
        """获取分析统计信息"""
        stats = {
            "analyzed_types": len(cross_paper_insights),
            "total_patterns": sum(len(insight["patterns"]) for insight in cross_paper_insights.values()),
            "total_trends": sum(len(insight["trends"]) for insight in cross_paper_insights.values()),
            "total_approaches": sum(len(insight["common_approaches"]) for insight in cross_paper_insights.values()),
            "type_details": {}
        }
        
        for summary_type, insight in cross_paper_insights.items():
            stats["type_details"][summary_type] = {
                "summaries_count": len(insight["summaries"]),
                "patterns_count": len(insight["patterns"]),
                "trends_count": len(insight["trends"]),
                "approaches_count": len(insight["common_approaches"]),
                "topics_count": len(insight["topic_clusters"])
            }
        
        return stats 