#!/usr/bin/env python3
"""
主题词提取工具

从论文摘要中提取主题词，并对主题进行整合和管理。
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Optional
import re # Added missing import for re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入相关模块
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.processing.topic_extractor import TopicExtractor
from abs2paper.utils.llm_client import LLMClient

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def extract_topics(input_dir: str, output_dir: str, config_file: Optional[str] = None) -> bool:
    """
    从论文摘要中提取主题词
    
    Args:
        input_dir: 论文摘要目录
        output_dir: 输出目录
        config_file: 主题配置文件路径，可选
        
    Returns:
        是否成功提取主题词
    """
    logger.info(f"开始从论文摘要中提取主题词")
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"输出目录: {output_dir}")
    
    try:
        # 初始化LLM客户端
        llm_client = LLMClient()
        
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 初始化主题提取器
        topic_extractor = TopicExtractor(llm_client, topic_manager)
        
        # 提取主题词
        paper_topics = topic_extractor.extract_topics_from_file(input_dir)
        
        # 保存结果
        if not paper_topics:
            logger.warning("未提取到任何主题词")
            return False
        
        # 保存主题词结果
        success = topic_extractor.save_paper_topics(paper_topics, output_dir)
        
        if success:
            logger.info(f"主题提取完成，结果已保存到 {output_dir}")
        else:
            logger.error("保存主题词结果失败")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"提取主题词时出错: {str(e)}")
        return False


def add_topic(name_zh: str, name_en: str, aliases: Optional[List[str]] = None, 
              config_file: Optional[str] = None) -> bool:
    """
    添加新主题词
    
    Args:
        name_zh: 中文名称
        name_en: 英文名称
        aliases: 别名列表，可选
        config_file: 主题配置文件路径，可选
        
    Returns:
        是否成功添加
    """
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 获取最大ID
        max_id = 0
        for topic in topic_manager.topics.values():
            try:
                topic_id = int(topic.id)
                if topic_id > max_id:
                    max_id = topic_id
            except ValueError:
                pass
        
        # 生成新ID
        new_id = str(max_id + 1)
        
        # 添加新主题词
        success = topic_manager.add_topic(new_id, name_zh, name_en, aliases)
        
        if success:
            logger.info(f"已添加新主题词 {new_id}. {name_zh} ({name_en})")
        else:
            logger.error("添加主题词失败")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"添加主题词时出错: {str(e)}")
        return False


def merge_topics(source_id: str, target_id: str, config_file: Optional[str] = None) -> bool:
    """
    合并主题词
    
    Args:
        source_id: 源主题ID
        target_id: 目标主题ID
        config_file: 主题配置文件路径，可选
        
    Returns:
        是否成功合并
    """
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 检查主题ID是否存在
        if source_id not in topic_manager.topics:
            logger.error(f"源主题ID {source_id} 不存在")
            return False
        
        if target_id not in topic_manager.topics:
            logger.error(f"目标主题ID {target_id} 不存在")
            return False
        
        # 合并主题词
        success = topic_manager.merge_topics(source_id, target_id)
        
        if success:
            source_topic = topic_manager.topics[source_id]
            target_topic = topic_manager.topics[target_id]
            logger.info(f"已将主题 {source_id}. {source_topic.name_zh} 合并到 {target_id}. {target_topic.name_zh}")
        else:
            logger.error("合并主题词失败")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"合并主题词时出错: {str(e)}")
        return False


def list_topics(config_file: Optional[str] = None) -> bool:
    """
    列出所有主题词
    
    Args:
        config_file: 主题配置文件路径，可选
        
    Returns:
        是否成功列出
    """
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 获取所有主题词
        topics = topic_manager.list_topics()
        
        if not topics:
            logger.warning("没有找到任何主题词")
            return True
        
        # 打印主题词列表
        print("\n当前主题词列表:")
        print("=" * 60)
        print(f"{'ID':<5} {'中文名称':<20} {'英文名称':<30} {'合并到':<10}")
        print("-" * 60)
        
        for topic in sorted(topics, key=lambda x: x['id']):
            id_str = topic['id']
            name_zh = topic['name_zh']
            name_en = topic['name_en']
            parent_id = topic['parent_id'] if topic['parent_id'] else ""
            
            print(f"{id_str:<5} {name_zh:<20} {name_en:<30} {parent_id:<10}")
        
        print("=" * 60)
        print(f"总计: {len(topics)} 个主题词")
        
        # 打印映射关系
        if topic_manager.topic_mapping:
            print("\n主题映射关系:")
            print("=" * 30)
            print(f"{'旧ID':<5} -> {'新ID':<5}")
            print("-" * 30)
            
            for old_id, new_id in topic_manager.topic_mapping.items():
                print(f"{old_id:<5} -> {new_id:<5}")
            
            print("=" * 30)
            print(f"总计: {len(topic_manager.topic_mapping)} 个映射")
        
        return True
        
    except Exception as e:
        logger.error(f"列出主题词时出错: {str(e)}")
        return False


def update_prompt(config_file: Optional[str] = None) -> bool:
    """
    更新提示词模板
    
    Args:
        config_file: 主题配置文件路径，可选
        
    Returns:
        是否成功更新
    """
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 获取提示词模板路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(project_root, "data", "prompt_kb.txt")
        
        # 读取原始提示词
        with open(prompt_path, 'r', encoding='utf-8') as f:
            original_prompt = f.read()
        
        # 生成主题词列表文本
        pattern = r"##知识库：.*?(?=##|$)"
        replacement = topic_manager.generate_prompt_kb_text()
        
        # 替换提示词中的知识库部分
        updated_prompt = re.sub(pattern, replacement, original_prompt, flags=re.DOTALL)
        
        # 如果没有成功替换，报错
        if updated_prompt == original_prompt:
            logger.warning("无法在提示词中找到知识库部分进行替换")
            return False
        
        # 备份原始提示词
        backup_path = os.path.join(project_root, "data", "prompt_kb.txt.bak")
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_prompt)
        
        # 保存更新后的提示词
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(updated_prompt)
        
        logger.info(f"已更新提示词模板 {prompt_path}")
        logger.info(f"原始提示词已备份到 {backup_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"更新提示词模板时出错: {str(e)}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="主题词提取和管理工具")
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # extract子命令
    extract_parser = subparsers.add_parser('extract', help='从论文摘要中提取主题词')
    extract_parser.add_argument('--input', type=str, required=True, help='论文摘要目录')
    extract_parser.add_argument('--output', type=str, required=True, help='输出目录')
    extract_parser.add_argument('--config', type=str, help='主题配置文件路径')
    
    # add子命令
    add_parser = subparsers.add_parser('add', help='添加新主题词')
    add_parser.add_argument('--name_zh', type=str, required=True, help='中文名称')
    add_parser.add_argument('--name_en', type=str, required=True, help='英文名称')
    add_parser.add_argument('--aliases', type=str, help='别名，以逗号分隔')
    add_parser.add_argument('--config', type=str, help='主题配置文件路径')
    
    # merge子命令
    merge_parser = subparsers.add_parser('merge', help='合并主题词')
    merge_parser.add_argument('--source', type=str, required=True, help='源主题ID')
    merge_parser.add_argument('--target', type=str, required=True, help='目标主题ID')
    merge_parser.add_argument('--config', type=str, help='主题配置文件路径')
    
    # list子命令
    list_parser = subparsers.add_parser('list', help='列出所有主题词')
    list_parser.add_argument('--config', type=str, help='主题配置文件路径')
    
    # update_prompt子命令
    update_prompt_parser = subparsers.add_parser('update_prompt', help='更新提示词模板')
    update_prompt_parser.add_argument('--config', type=str, help='主题配置文件路径')
    
    args = parser.parse_args()
    
    if args.command == 'extract':
        success = extract_topics(args.input, args.output, args.config)
    elif args.command == 'add':
        aliases = args.aliases.split(',') if args.aliases else None
        success = add_topic(args.name_zh, args.name_en, aliases, args.config)
    elif args.command == 'merge':
        success = merge_topics(args.source, args.target, args.config)
    elif args.command == 'list':
        success = list_topics(args.config)
    elif args.command == 'update_prompt':
        success = update_prompt(args.config)
    else:
        parser.print_help()
        return
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main() 