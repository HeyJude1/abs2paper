#!/usr/bin/env python3
"""
论文生成RAG系统主脚本
基于用户需求，通过RAG流程生成完整论文
"""

import os
import sys
import json
import argparse
import glob
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from abs2paper.rag.summary_retriever import SummaryRetriever
from abs2paper.rag.cross_paper_analyzer import CrossPaperAnalyzer
from abs2paper.rag.source_text_retriever import SourceTextRetriever
from abs2paper.rag.context_builder import ContextBuilder
from abs2paper.rag.paper_generator import PaperGenerator

# 全局时间戳
global_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

def convert_to_serializable(obj):
    """将不可序列化的对象转换为可序列化格式"""
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        # 处理列表或类似列表的对象（如RepeatedScalarContainer）
        try:
            return list(obj)
        except:
            return str(obj)
    elif hasattr(obj, '__dict__'):
        # 处理复杂对象
        return obj.__dict__
    else:
        return obj

def serialize_data(data):
    """递归处理数据，确保所有内容都可以JSON序列化"""
    import json
    
    try:
        # 尝试直接序列化，如果可以则返回
        json.dumps(data)
        return data
    except TypeError:
        pass
    
    if isinstance(data, dict):
        return {key: serialize_data(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return [serialize_data(item) for item in data]
    elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
        # 处理RepeatedScalarContainer等protobuf类型
        try:
            return [serialize_data(item) for item in data]
        except:
            return str(data)
    elif hasattr(data, '__dict__'):
        # 处理复杂对象
        return serialize_data(data.__dict__)
    else:
        # 对于其他类型，尝试转换为基本类型
        try:
            return str(data)
        except:
            return None

def save_json_and_txt(data: Dict[str, Any], json_path: str, txt_path: str, 
                      text_extract_func=None):
    """保存JSON和TXT文件的通用函数"""
    # 序列化数据
    serializable_data = serialize_data(data)
    
    # 保存JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, ensure_ascii=False, indent=2)
    
    # 保存TXT
    if text_extract_func:
        text_content = text_extract_func(data)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

def extract_summaries_text(data: Dict[str, Any]) -> str:
    """从步骤1结果中提取总结文本"""
    text_lines = []
    text_lines.append(f"用户需求：{data.get('user_requirement', '')}\n")
    text_lines.append("=" * 80 + "\n")
    
    relevant_summaries = data.get('relevant_summaries', {})
    for summary_type, summaries in relevant_summaries.items():
        text_lines.append(f"【{summary_type.upper()} 类型总结】\n")
        text_lines.append("-" * 50 + "\n")
        
        for i, summary in enumerate(summaries):
            text_lines.append(f"总结 {i+1}：\n")
            text_lines.append(f"论文ID：{summary.get('paper_id', '')}\n")
            text_lines.append(f"相关度得分：{summary.get('score', 0):.4f}\n")
            text_lines.append(f"来源章节：{', '.join(summary.get('source_sections', []))}\n")
            text_lines.append(f"主题标签：{', '.join(summary.get('topics', []))}\n")
            text_lines.append("总结内容：\n")
            text_lines.append(summary.get('summary_text', '') + "\n")
            text_lines.append("\n" + "~" * 30 + "\n")
        
        text_lines.append("\n" + "=" * 80 + "\n")
    
    return "".join(text_lines)

def extract_analysis_text(data: Dict[str, Any]) -> str:
    """从步骤2结果中提取分析文本"""
    text_lines = []
    text_lines.append("跨论文同类型分析结果\n")
    text_lines.append("=" * 80 + "\n")
    
    cross_paper_analysis = data.get('cross_paper_analysis', {})
    for analysis_type, analysis_data in cross_paper_analysis.items():
        text_lines.append(f"【{analysis_type.upper()} 分析】\n")
        text_lines.append("-" * 50 + "\n")
        
        # 分析总结
        if 'summary' in analysis_data:
            text_lines.append("📊 分析总结：\n")
            text_lines.append(f"{analysis_data['summary']}\n\n")
        
        # 发展趋势
        if 'trends' in analysis_data:
            text_lines.append("📈 发展趋势：\n")
            trends = analysis_data['trends']
            if isinstance(trends, list):
                for i, trend in enumerate(trends, 1):
                    text_lines.append(f"  {i}. {str(trend)}\n")
            else:
                text_lines.append(f"  • {str(trends)}\n")
            text_lines.append("\n")
        
        # 常见方法
        if 'common_approaches' in analysis_data:
            text_lines.append("🔧 常见方法：\n")
            approaches = analysis_data['common_approaches']
            if isinstance(approaches, list):
                for i, approach in enumerate(approaches, 1):
                    text_lines.append(f"  {i}. {str(approach)}\n")
            else:
                text_lines.append(f"  • {str(approaches)}\n")
            text_lines.append("\n")
        
        # 发现的模式 
        if 'patterns' in analysis_data:
            text_lines.append("🔍 发现的模式：\n")
            patterns = analysis_data['patterns']
            if isinstance(patterns, list):
                for i, pattern in enumerate(patterns[:5], 1):  # 只显示前5个最重要的模式
                    text_lines.append(f"  {i}. {str(pattern)}\n")
            else:
                text_lines.append(f"  • {str(patterns)}\n")
            text_lines.append("\n")
        
        # 主题聚类（简化显示）
        if 'topic_clusters' in analysis_data:
            text_lines.append("📚 主要研究主题：\n")
            clusters = analysis_data['topic_clusters']
            if isinstance(clusters, dict):
                # 过滤和整理聚类结果，只显示有意义的聚类
                meaningful_clusters = {}
                for cluster_name, papers in clusters.items():
                    # 过滤掉单字符或无意义的聚类名
                    if len(cluster_name) > 2 and cluster_name not in ['[', "'", ' ', '(', ')', ',', '-']:
                        if isinstance(papers, list) and len(papers) >= 2:  # 至少2篇论文的聚类才有意义
                            if isinstance(papers[0], dict):
                                paper_count = len(set(p.get('paper_id', str(p)) for p in papers))
                            else:
                                paper_count = len(set(str(p) for p in papers))
                            meaningful_clusters[cluster_name] = paper_count
                
                # 按论文数量排序，显示前10个
                sorted_clusters = sorted(meaningful_clusters.items(), key=lambda x: x[1], reverse=True)[:10]
                for i, (topic, count) in enumerate(sorted_clusters, 1):
                    text_lines.append(f"  {i}. {topic}（{count}篇论文涉及）\n")
            text_lines.append("\n")
        
        text_lines.append("=" * 80 + "\n")
    
    return "".join(text_lines)

def extract_source_texts_text(data: Dict[str, Any]) -> str:
    """从步骤3结果中提取源文本"""
    text_lines = []
    text_lines.append("选定的最相关原文章节\n")
    text_lines.append("=" * 80 + "\n")
    
    selected_source_texts = data.get('selected_source_texts', {})
    for paper_id, sections in selected_source_texts.items():
        text_lines.append(f"【论文 {paper_id}】\n")
        text_lines.append("-" * 50 + "\n")
        
        for section_name, section_content in sections.items():
            text_lines.append(f">>> {section_name} 章节 <<<\n")
            if isinstance(section_content, list):
                text_lines.append("".join(section_content) + "\n")
            else:
                text_lines.append(str(section_content) + "\n")
            text_lines.append("\n" + "~" * 30 + "\n")
        
        text_lines.append("=" * 80 + "\n")
    
    return "".join(text_lines)

def extract_contexts_text(data: Dict[str, Any]) -> str:
    """从步骤4结果中提取结构化上下文文本"""
    text_lines = []
    text_lines.append("结构化RAG上下文\n")
    text_lines.append("=" * 80 + "\n")
    
    # 处理完整的structured_contexts数据
    if 'structured_contexts' in data:
        structured_contexts = data['structured_contexts']
        for section_name, context in structured_contexts.items():
            text_lines.append(f"【{section_name} 部分的上下文】\n")
            text_lines.append("-" * 50 + "\n")
            if isinstance(context, str) and context.strip():
                text_lines.append(context + "\n\n")
            else:
                text_lines.append("(上下文内容为空)\n\n")
            text_lines.append("=" * 80 + "\n")
    
    # 处理单个section的数据
    elif 'section_name' in data and 'context' in data:
        section_name = data['section_name']
        context = data['context']
        context_length = data.get('context_length', 0)
        
        text_lines.append(f"【{section_name} 部分的上下文】\n")
        text_lines.append("-" * 50 + "\n")
        text_lines.append(f"上下文长度：{context_length} 字符\n\n")
        
        if isinstance(context, str) and context.strip():
            text_lines.append("上下文内容：\n")
            text_lines.append(context + "\n\n")
        else:
            text_lines.append("(上下文内容为空)\n\n")
    
    # 处理旧格式的数据（向后兼容）
    else:
        for section_name, context_data in data.items():
            if isinstance(context_data, dict):
                text_lines.append(f"【{section_name} 部分的上下文】\n")
                text_lines.append("-" * 50 + "\n")
                
                # 总结信息
                if 'summary_info' in context_data:
                    text_lines.append("📋 相关总结信息：\n")
                    for summary_type, summaries in context_data['summary_info'].items():
                        text_lines.append(f"  {summary_type}：\n")
                        for summary in summaries:
                            paper_id = summary.get('paper_id', '')
                            summary_text = summary.get('summary_text', '')
                            text_lines.append(f"    - {paper_id}: {summary_text[:200]}...\n")
                        text_lines.append("\n")
                
                # 趋势信息
                if 'trend_info' in context_data:
                    text_lines.append("📈 趋势分析：\n")
                    text_lines.append(context_data['trend_info'] + "\n\n")
                
                # 原文信息
                if 'source_text_info' in context_data:
                    text_lines.append("📄 相关原文：\n")
                    text_lines.append(context_data['source_text_info'] + "\n\n")
                
                text_lines.append("=" * 80 + "\n")
            elif isinstance(context_data, str) and context_data.strip():
                text_lines.append(f"【{section_name} 部分的上下文】\n")
                text_lines.append("-" * 50 + "\n")
                text_lines.append(context_data + "\n\n")
                text_lines.append("=" * 80 + "\n")
    
    return "".join(text_lines)

def step1_retrieve_summaries(user_requirement: str) -> Dict[str, Any]:
    """步骤1：多类型总结并行检索"""
    print(f"🔄 步骤1：多类型总结并行检索...")
    print(f"📝 用户需求：{user_requirement}")
    
    retriever = SummaryRetriever()
    relevant_summaries = retriever.parallel_retrieve_summaries(
        user_requirement=user_requirement,
        top_k_per_type=5
    )
    
    # 获取统计信息
    stats = retriever.get_retrieval_statistics(relevant_summaries)
    
    result = {
        "user_requirement": user_requirement,
        "top_k_per_type": 5,
        "relevant_summaries": relevant_summaries,
        "statistics": stats
    }
    
    # 保存结果到step1目录
    data_dir = os.path.join(project_root, "abs2paper", "rag", "data")
    step1_dir = os.path.join(data_dir, "step1_summaries")
    os.makedirs(step1_dir, exist_ok=True)
    
    json_path = os.path.join(step1_dir, f"{global_timestamp}_summaries_retrieval.json")
    txt_path = os.path.join(step1_dir, f"{global_timestamp}_summaries_retrieval.txt")
    
    save_json_and_txt(result, json_path, txt_path, extract_summaries_text)
    
    print(f"✅ 步骤1完成！共检索到 {stats['total_summaries']} 个总结，涵盖 {stats['types_found']} 种类型")
    print(f"📊 统计：{stats['type_counts']}")
    print(f"📁 结果已保存到：{json_path}")
    print(f"📄 文本版本：{txt_path}")
    
    return result

def step2_analyze_cross_paper() -> Dict[str, Any]:
    """步骤2：跨论文同类型分析"""
    print(f"🔄 步骤2：跨论文同类型分析...")
    
    # 加载步骤1的结果
    data_dir = os.path.join(project_root, "abs2paper", "rag", "data")
    step1_file = os.path.join(data_dir, "step1_summaries", f"{global_timestamp}_summaries_retrieval.json")
    
    if not os.path.exists(step1_file):
        # 查找最新的step1文件
        step1_files = glob.glob(os.path.join(data_dir, "step1_summaries", "*_summaries_retrieval.json"))
        if step1_files:
            step1_file = max(step1_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤1结果：{os.path.basename(step1_file)}")
        else:
            raise FileNotFoundError("未找到步骤1的结果文件，请先运行步骤1")
    
    with open(step1_file, 'r', encoding='utf-8') as f:
        step1_result = json.load(f)
    
    analyzer = CrossPaperAnalyzer()
    cross_paper_analysis = analyzer.analyze_cross_paper_patterns(
        step1_result['relevant_summaries']
    )
    
    result = {
        "cross_paper_analysis": cross_paper_analysis,
        "input_summaries_count": sum(len(summaries) for summaries in step1_result['relevant_summaries'].values())
    }
    
    # 保存结果到step2目录
    step2_dir = os.path.join(data_dir, "step2_analysis")
    os.makedirs(step2_dir, exist_ok=True)
    
    json_path = os.path.join(step2_dir, f"{global_timestamp}_cross_paper_analysis.json")
    txt_path = os.path.join(step2_dir, f"{global_timestamp}_cross_paper_analysis.txt")
    
    save_json_and_txt(result, json_path, txt_path, extract_analysis_text)
    
    print(f"✅ 步骤2完成！分析了 {len(cross_paper_analysis)} 种总结类型的跨论文模式")
    print(f"📁 结果已保存到：{json_path}")
    print(f"📄 文本版本：{txt_path}")
    
    return result

def step3_select_source_texts() -> Dict[str, Any]:
    """步骤3：根据总结获取对应原文章节"""
    print(f"🔄 步骤3：根据总结获取对应原文章节...")
    
    # 加载步骤1的结果
    data_dir = os.path.join(project_root, "abs2paper", "rag", "data")
    step1_file = os.path.join(data_dir, "step1_summaries", f"{global_timestamp}_summaries_retrieval.json")
    
    if not os.path.exists(step1_file):
        step1_files = glob.glob(os.path.join(data_dir, "step1_summaries", "*_summaries_retrieval.json"))
        if step1_files:
            step1_file = max(step1_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤1结果：{os.path.basename(step1_file)}")
        else:
            raise FileNotFoundError("未找到步骤1的结果文件，请先运行步骤1")
    
    with open(step1_file, 'r', encoding='utf-8') as f:
        step1_result = json.load(f)
    
    retriever = SourceTextRetriever()
    selected_source_texts = retriever.select_most_relevant_source_texts(
        step1_result['relevant_summaries']
    )
    
    # 获取统计信息
    total_papers = len(selected_source_texts)
    total_sections = sum(len(sections) for sections in selected_source_texts.values())
    total_chunks = sum(
        len(content) if isinstance(content, list) else 1
        for sections in selected_source_texts.values()
        for content in sections.values()
    )
    
    result = {
        "selected_source_texts": selected_source_texts,
        "statistics": {
            "total_papers": total_papers,
            "total_sections": total_sections,
            "total_chunks": total_chunks,
            "paper_details": {
                paper_id: {
                    "sections": list(sections.keys()),
                    "section_count": len(sections)
                }
                for paper_id, sections in selected_source_texts.items()
            }
        }
    }
    
    # 保存结果到step3目录
    step3_dir = os.path.join(data_dir, "step3_source_texts")
    os.makedirs(step3_dir, exist_ok=True)
    
    json_path = os.path.join(step3_dir, f"{global_timestamp}_source_texts_selection.json")
    txt_path = os.path.join(step3_dir, f"{global_timestamp}_source_texts_selection.txt")
    
    save_json_and_txt(result, json_path, txt_path, extract_source_texts_text)
    
    print(f"✅ 步骤3完成！选择了 {total_papers} 篇论文的 {total_sections} 个章节")
    print(f"📁 结果已保存到：{json_path}")
    print(f"📄 文本版本：{txt_path}")
    
    return result

def step4_build_contexts() -> Dict[str, Any]:
    """步骤4：按生成论文部分构建结构化RAG上下文"""
    print(f"🔄 步骤4：按生成论文部分构建结构化RAG上下文...")
    
    data_dir = os.path.join(project_root, "abs2paper", "rag", "data")
    
    # 加载前面步骤的结果
    step1_file = os.path.join(data_dir, "step1_summaries", f"{global_timestamp}_summaries_retrieval.json")
    step2_file = os.path.join(data_dir, "step2_analysis", f"{global_timestamp}_cross_paper_analysis.json")
    step3_file = os.path.join(data_dir, "step3_source_texts", f"{global_timestamp}_source_texts_selection.json")
    
    # 如果找不到当前时间戳的文件，查找最新的文件
    if not os.path.exists(step1_file):
        step1_files = glob.glob(os.path.join(data_dir, "step1_summaries", "*_summaries_retrieval.json"))
        if step1_files:
            step1_file = max(step1_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤1文件：{os.path.basename(step1_file)}")
        else:
            raise FileNotFoundError("未找到步骤1的结果文件，请先运行步骤1")
    
    if not os.path.exists(step2_file):
        step2_files = glob.glob(os.path.join(data_dir, "step2_analysis", "*_cross_paper_analysis.json"))
        if step2_files:
            step2_file = max(step2_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤2文件：{os.path.basename(step2_file)}")
        else:
            raise FileNotFoundError("未找到步骤2的结果文件，请先运行步骤2")
    
    if not os.path.exists(step3_file):
        step3_files = glob.glob(os.path.join(data_dir, "step3_source_texts", "*_source_texts_selection.json"))
        if step3_files:
            step3_file = max(step3_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤3文件：{os.path.basename(step3_file)}")
        else:
            raise FileNotFoundError("未找到步骤3的结果文件，请先运行步骤3")
    
    # 加载数据
    with open(step1_file, 'r', encoding='utf-8') as f:
        step1_result = json.load(f)
    with open(step2_file, 'r', encoding='utf-8') as f:
        step2_result = json.load(f)
    with open(step3_file, 'r', encoding='utf-8') as f:
        step3_result = json.load(f)
    
    builder = ContextBuilder()
    structured_contexts = builder.build_structured_contexts(
        relevant_summaries=step1_result['relevant_summaries'],
        cross_paper_insights=step2_result['cross_paper_analysis'],
        selected_source_texts=step3_result['selected_source_texts']
    )
    
    result = {
        "structured_contexts": structured_contexts,
        "context_sections": list(structured_contexts.keys()),
        "total_contexts": len(structured_contexts)
    }
    
    # 保存结果到step4目录
    step4_dir = os.path.join(data_dir, "step4_contexts")
    os.makedirs(step4_dir, exist_ok=True)
    
    # 保存完整的结构化上下文
    json_path = os.path.join(step4_dir, f"{global_timestamp}_structured_contexts.json")
    txt_path = os.path.join(step4_dir, f"{global_timestamp}_structured_contexts.txt")
    
    save_json_and_txt(result, json_path, txt_path, extract_contexts_text)
    
    # 为每个部分单独保存上下文
    for section_name, context in structured_contexts.items():
        section_json_path = os.path.join(step4_dir, f"{global_timestamp}_context_{section_name}.json")
        section_txt_path = os.path.join(step4_dir, f"{global_timestamp}_context_{section_name}.txt")
        
        # 构建包含完整信息的section数据
        section_data = {
            "section_name": section_name,
            "context": context,
            "context_length": len(context) if isinstance(context, str) else len(str(context))
        }
        
        save_json_and_txt(section_data, section_json_path, section_txt_path, extract_contexts_text)
    
    print(f"✅ 步骤4完成！构建了 {len(structured_contexts)} 个部分的结构化上下文")
    print(f"📁 结果已保存到：{json_path}")
    print(f"📄 文本版本：{txt_path}")
    
    return result

def step5_generate_paper(user_requirement: str) -> Dict[str, Any]:
    """步骤5：顺序化论文生成流程"""
    print(f"🔄 步骤5：顺序化论文生成流程...")
    if user_requirement:
        print(f"📝 用户需求：{user_requirement}")
    else:
        print(f"📝 基于前面步骤结果生成论文")
    
    data_dir = os.path.join(project_root, "abs2paper", "rag", "data")
    
    # 加载步骤4的结果
    step4_file = os.path.join(data_dir, "step4_contexts", f"{global_timestamp}_structured_contexts.json")
    
    if not os.path.exists(step4_file):
        step4_files = glob.glob(os.path.join(data_dir, "step4_contexts", "*_structured_contexts.json"))
        if step4_files:
            step4_file = max(step4_files, key=os.path.getctime)
            print(f"📁 使用最新的步骤4结果：{os.path.basename(step4_file)}")
        else:
            raise FileNotFoundError("未找到步骤4的结果文件，请先运行步骤4")
    
    with open(step4_file, 'r', encoding='utf-8') as f:
        step4_result = json.load(f)
    
    # 如果用户需求为空，尝试从之前的步骤中获取
    if not user_requirement:
        # 尝试从步骤1结果中获取用户需求
        step1_files = glob.glob(os.path.join(data_dir, "step1_summaries", "*_summaries_retrieval.json"))
        if step1_files:
            step1_file = max(step1_files, key=os.path.getctime)
            with open(step1_file, 'r', encoding='utf-8') as f:
                step1_result = json.load(f)
                user_requirement = step1_result.get('user_requirement', '基于深度学习的研究')
    
    generator = PaperGenerator()
    generated_sections = generator.generate_paper_sequentially(
        paper_section_contexts=step4_result['structured_contexts'],
        user_requirement=user_requirement
    )
    
    # 获取统计信息
    stats = generator.get_generation_statistics(generated_sections)
    
    # 构建完整的论文数据结构
    generated_paper = {
        "title": "基于RAG的论文生成",
        "user_requirement": user_requirement,
        "sections": generated_sections,
        "statistics": stats,
        "generation_timestamp": global_timestamp
    }
    
    # 保存结果到step5目录
    step5_dir = os.path.join(data_dir, "step5_generated")
    os.makedirs(step5_dir, exist_ok=True)
    
    # 保存完整论文
    json_path = os.path.join(step5_dir, f"{global_timestamp}_generated_paper.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(generated_paper, f, ensure_ascii=False, indent=2)
    
    # 为每个部分单独保存
    for section, content in generated_sections.items():
        section_json_path = os.path.join(step5_dir, f"{global_timestamp}_generated_{section}.json")
        section_txt_path = os.path.join(step5_dir, f"{global_timestamp}_generated_{section}.txt")
        
        section_data = {section: content}
        with open(section_json_path, 'w', encoding='utf-8') as f:
            json.dump(section_data, f, ensure_ascii=False, indent=2)
        
        with open(section_txt_path, 'w', encoding='utf-8') as f:
            f.write(f"【{section}】\n")
            f.write("=" * 80 + "\n")
            f.write(content + "\n")
    
    print(f"✅ 步骤5完成！生成了完整论文，包含 {len(generated_sections)} 个部分")
    print(f"📁 结果已保存到：{json_path}")
    
    return generated_paper

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='论文生成 RAG 系统')
    parser.add_argument('user_requirement', nargs='?', help='用户需求描述（步骤5必需）')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='运行指定步骤')
    parser.add_argument('--output', help='输出文件名（仅对步骤5生效）')
    args = parser.parse_args()

    # 创建时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 设置paperGen输出目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paper_gen_dir = os.path.join(script_dir, "paperGen")
    os.makedirs(paper_gen_dir, exist_ok=True)
    
    try:
        if args.step:
            # 运行指定步骤
            if args.step == 1:
                if not args.user_requirement:
                    print("❌ 错误：步骤1需要用户需求参数")
                    sys.exit(1)
                step1_retrieve_summaries(args.user_requirement)
            elif args.step == 2:
                step2_analyze_cross_paper()
            elif args.step == 3:
                step3_select_source_texts()
            elif args.step == 4:
                step4_build_contexts()
            elif args.step == 5:
                # 步骤5不再需要用户需求参数，直接基于前面步骤的结果生成论文
                generated_paper = step5_generate_paper("")
                
                # 生成最终的markdown文件并保存到paperGen目录，使用默认命名
                final_output_name = f"generated_paper_{timestamp}.md"
                final_output_path = os.path.join(paper_gen_dir, final_output_name)
                
                # 生成markdown内容
                markdown_content = f"""# {generated_paper.get('title', '基于RAG的论文生成')}

> **生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}  
> **基于RAG系统生成**

---

"""
                
                # 按照顺序添加各个部分
                section_order = ['引言', '相关工作', '方法', '实验评价', '总结']
                for section in section_order:
                    if section in generated_paper.get('sections', {}):
                        markdown_content += f"## {section}\n\n{generated_paper['sections'][section]}\n\n---\n\n"
                
                # 添加生成统计信息
                if 'statistics' in generated_paper:
                    markdown_content += "## 生成统计信息\n\n"
                    stats = generated_paper['statistics']
                    markdown_content += f"- **总字数**: {stats.get('total_words', 'N/A')}\n"
                    markdown_content += f"- **生成时间**: {stats.get('generation_time', 'N/A')}\n"
                    markdown_content += f"- **使用的论文数量**: {stats.get('papers_used', 'N/A')}\n"
                
                # 保存最终markdown文件
                with open(final_output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                print(f"🎉 论文生成完成！")
                print(f"📄 最终论文已保存到：{final_output_path}")
        
        else:
            # 运行完整流程
            if not args.user_requirement:
                print("❌ 错误：请提供用户需求")
                print("示例：python gen_paper.py '基于深度学习的图像分类方法研究'")
                sys.exit(1)
            
            print("🚀 开始运行完整的论文生成 RAG 流程...")
            
            # 执行所有步骤
            step1_retrieve_summaries(args.user_requirement)
            step2_analyze_cross_paper()
            step3_select_source_texts()
            step4_build_contexts()
            generated_paper = step5_generate_paper(args.user_requirement)
            
            # 生成最终输出
            final_output_name = args.output if args.output else f"generated_paper_{timestamp}.md"
            if args.output:
                # 如果用户指定了输出文件名，处理格式
                if not final_output_name.endswith('.md'):
                    final_output_name = final_output_name + f"_{timestamp}.md"
                else:
                    # 在.md前添加时间戳
                    final_output_name = final_output_name.replace('.md', f'_{timestamp}.md')
                
            final_output_path = os.path.join(paper_gen_dir, final_output_name)
            
            # 生成markdown内容（同上）
            markdown_content = f"""# {generated_paper.get('title', '基于RAG的论文生成')}

> **生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}  
> **用户需求**: {args.user_requirement}

---

"""
            
            section_order = ['引言', '相关工作', '方法', '实验评价', '总结']
            for section in section_order:
                if section in generated_paper.get('sections', {}):
                    markdown_content += f"## {section}\n\n{generated_paper['sections'][section]}\n\n---\n\n"
            
            if 'statistics' in generated_paper:
                markdown_content += "## 生成统计信息\n\n"
                stats = generated_paper['statistics']
                markdown_content += f"- **总字数**: {stats.get('total_words', 'N/A')}\n"
                markdown_content += f"- **生成时间**: {stats.get('generation_time', 'N/A')}\n"
                markdown_content += f"- **使用的论文数量**: {stats.get('papers_used', 'N/A')}\n"
            
            with open(final_output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"🎉 完整 RAG 流程执行完成！")
            print(f"📄 最终论文已保存到：{final_output_path}")
            
    except Exception as e:
        print(f"❌ 执行过程中出现错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 