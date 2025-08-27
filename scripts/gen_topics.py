#!/usr/bin/env python3
"""
主题词生成和管理工具

提供完整的主题词生成、合并、更新流程
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
import re # Added for re.sub

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入相关模块
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.processing.topic_generator import TopicGenerator
from abs2paper.utils.llm_client import LLMClient

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_data_files():
    """重置处理数据文件，但保持topic.json的连续性"""
    try:
        # 获取项目根目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        
        # 加载配置
        config_path = os.path.join(project_root, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 从稳定的topic.json中加载现有主题作为基础
        topic_manager = TopicManager()
        current_topics_list = topic_manager.list_topics()  # 这返回一个列表
        
        # 重置gen_topic.json - 以topic.json中的稳定主题为起始点（但重置状态）
        gen_topic_data = {
            "topics": {},
            "version": "1.0.0", 
            "last_updated": datetime.now().isoformat(),
            "description": "存储阶段一询问大模型生成的主题词（待处理的主题词）"
        }
        
        # 将稳定主题复制为生成主题的起始点，但重置为pending状态
        if current_topics_list:
            for topic_info in current_topics_list:  # 遍历列表而不是字典的items()
                topic_id = topic_info["id"]
                gen_topic_data["topics"][topic_id] = {
                    "id": topic_id,
                    "name_zh": topic_info["name_zh"],
                    "name_en": topic_info["name_en"], 
                    "aliases": topic_info.get("aliases", []),
                    "status": "pending",  # 重置状态
                    "created_at": topic_info.get("created_at", datetime.now().isoformat())
                }
        
        # 保存gen_topic.json（重置）
        gen_topic_path = os.path.join(project_root, config["data_paths"]["gen_topic_json"]["path"].lstrip('/'))
        os.makedirs(os.path.dirname(gen_topic_path), exist_ok=True)
        with open(gen_topic_path, 'w', encoding='utf-8') as f:
            json.dump(gen_topic_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 已重置gen_topic.json（基于{len(current_topics_list)}个稳定主题）")
        return True
        
    except Exception as e:
        logger.error(f"重置数据文件时出错: {e}")
        return False

def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="主题词生成和管理工具")
    parser.add_argument('command', nargs='?', default='full', 
                       help='执行的命令：full(默认，执行完整流程), extract, generate_merge, update_topics, list')
    parser.add_argument('--no-reset', action='store_true', 
                       help='跳过数据文件重置（仅用于调试，正常情况下不建议使用）')
    args = parser.parse_args()
    
    try:
        # 获取项目根路径和配置
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(module_dir, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 默认情况下重置数据文件（除了topic.json），除非明确指定--no-reset
        if not args.no_reset and args.command in ['full', 'extract']:
            logger.info("开始重置数据文件（topic.json将保持不变作为稳定基础）")
            reset_data_files()
        else:
            if args.no_reset:
                logger.info("用户指定了--no-reset参数，跳过数据文件重置")
            else:
                logger.info("当前命令不需要重置数据文件")
        
        # 初始化主题管理器
        topic_manager = TopicManager()
        
        # 执行不同的命令
        if args.command == 'extract':
            # 从论文中生成主题词
            extract_from_papers(config, module_dir, topic_manager)
            
        elif args.command == 'generate_merge':
            # 生成主题合并建议
            generate_merge_suggestions(topic_manager)
            
        elif args.command == 'update_topics':
            # 根据合并建议更新主题词
            update_topics(topic_manager)
            
        elif args.command == 'list':
            # 列出所有主题词
            topic_manager.list_all_topics()
            
        elif args.command == 'full':
            # 执行完整流程
            logger.info("开始执行完整的主题生成、合并和更新流程")
            
            # 1. 从论文中生成主题词
            extract_from_papers(config, module_dir, topic_manager)
            
            # 2. 执行多轮合并循环
            execute_merge_cycles(topic_manager)
            
            logger.info("完整的主题生成、合并建议生成和更新流程已完成！")
    
    except Exception as e:
        logger.error(f"执行命令时出错: {str(e)}")
        sys.exit(1)

def extract_from_papers(config, module_dir, topic_manager):
    """从论文中生成主题词"""
    # 初始化LLM客户端和主题生成器
    llm_client = LLMClient()
    topic_generator = TopicGenerator(llm_client, topic_manager)
    
    # 获取输入路径
    abstract_path = config["data_paths"]["abstract_extract"]["path"].lstrip('/')
    input_dir = os.path.join(module_dir, abstract_path)
    
    # 生成主题
    paper_topics = topic_generator.generate_topics_from_file(input_dir)
    
    # 不再调用update_prompt_template，避免无法找到知识库部分的错误

def execute_merge_cycles(topic_manager):
    """执行多轮合并循环"""
    logger.info("开始执行多轮合并循环")
    
    # 重置merge_LLM_result文件，确保每次执行都是最新的合并建议
    topic_manager.reset_merge_llm_result()
    
    # 第一轮：从gen_topic.json到middle_topic.json
    logger.info("=== 第一轮合并：从gen_topic.json到middle_topic.json ===")
    generate_merge_suggestions(topic_manager, source="gen_topic")
    update_topics(topic_manager, target="middle_topic", source="gen_topic")
    
    # 第二轮：从middle_topic.json到middle_topic.json
    logger.info("=== 第二轮合并：从middle_topic.json到middle_topic.json ===")
    generate_merge_suggestions(topic_manager, source="middle_topic")
    update_topics(topic_manager, target="middle_topic", source="middle_topic")
    
    # 第三轮：从middle_topic.json到topic.json
    logger.info("=== 第三轮合并：从middle_topic.json到topic.json ===")
    generate_merge_suggestions(topic_manager, source="middle_topic")
    update_topics(topic_manager, target="topic", source="middle_topic")
    
    logger.info("多轮合并循环完成")

def generate_merge_suggestions(topic_manager, source="gen_topic"):
    """生成主题合并建议"""
    logger.info(f"开始生成合并建议（数据源：{source}）")
    
    # 初始化LLM客户端
    llm_client = LLMClient()
    
    # 根据源类型获取主题数据
    if source == "gen_topic":
        # 从gen_topic.json获取所有主题的详细信息
        topic_details = []
        gen_topics = topic_manager.load_generated_topics()
        
        # 将gen_topic.json中的主题转换为topic_details格式
        for gen_id, topic_data in gen_topics.items():
            # 将生成主题的格式转换为和topic_info一致
            topic_info = {
                "id": gen_id,
                "name_zh": topic_data.get("name_zh", ""),
                "name_en": topic_data.get("name_en", ""),
                "aliases": topic_data.get("aliases", []),
                "created_at": topic_data.get("created_at", datetime.now().isoformat())
            }
            
            # 如果有原始ID，则添加
            if "original_id" in topic_data:
                topic_info["original_id"] = topic_data["original_id"]
            
            topic_details.append(topic_info)
    
    elif source == "middle_topic":
        # 从middle_topic.json获取主题数据
        topic_details = []
        middle_topics = topic_manager.load_middle_topics()
        
        for mid_id, topic_data in middle_topics.items():
            topic_info = {
                "id": mid_id,
                "name_zh": topic_data.get("name_zh", ""),
                "name_en": topic_data.get("name_en", ""),
                "aliases": topic_data.get("aliases", []),
                "created_at": topic_data.get("created_at", datetime.now().isoformat())
            }
            topic_details.append(topic_info)
    
    else:
        logger.error(f"不支持的数据源类型：{source}")
        return
    
    # 按创建时间排序主题
    topic_details.sort(key=lambda x: x.get('created_at', ''))
    
    if not topic_details:
        logger.info("没有需要合并的主题")
        return []
    
    # 创建合并提示
    merge_prompt = topic_manager.create_merge_prompt(topic_details)
    
    # 调用LLM生成合并建议
    response = llm_client.get_completion(merge_prompt)
    
    # 保存大模型的原始响应
    topic_manager.save_merge_opinion(response)
    
    # 解析合并建议
    merge_suggestions = topic_manager.parse_merge_suggestions(response)
    
    if merge_suggestions:
        logger.info(f"生成了 {len(merge_suggestions)} 个合并建议")
        for source_id, target_id, merge_type in merge_suggestions:
            logger.debug(f"  {source_id} -> {target_id} ({merge_type})")
    else:
        logger.info("没有需要合并的主题")
        
    return merge_suggestions

def update_topics(topic_manager, target="topic", source="gen_topic"):
    """更新主题词"""
    logger.info(f"开始更新主题词（目标：{target}，来源：{source}）")
    
    # 初始化LLM客户端
    llm_client = LLMClient()
    
    # 执行主题更新
    success = topic_manager.update_topics_from_merge(llm_client, target=target, use_code_merge=True, source=source)
    
    if success:
        # 删除重复日志，TopicManager已经有详细的日志输出
        pass
    else:
        logger.error(f"更新主题到 {target} 失败")
    
    return success


if __name__ == "__main__":
    main() 