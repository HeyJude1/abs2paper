#!/usr/bin/env python3
"""
主题词提取工具启动器

本脚本作为主题词提取和管理的命令行入口。
所有核心功能都在abs2paper.processing.topic_extractor模块中实现。
"""

import os
import sys
import argparse
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入相关模块
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.utils.llm_client import LLMClient
from abs2paper.processing.topic_extractor import TopicExtractor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="主题词提取和管理工具")
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # extract子命令 - 提取主题词
    extract_parser = subparsers.add_parser('extract', help='从论文摘要中提取主题词')
    extract_parser.add_argument('--input', type=str, required=True, help='论文摘要目录')
    extract_parser.add_argument('--output', type=str, required=True, help='输出目录')
    extract_parser.add_argument('--config', type=str, help='主题配置文件路径')
    extract_parser.add_argument('--initial-topic', type=str, help='初始主题词，如"代码生成"，将作为起点添加到主题列表中')
    
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
    
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(args.config if hasattr(args, 'config') else None)
        
        if args.command == 'extract':
            # 流程编排：
            # 1. 如果提供了初始主题词，添加到主题列表
            if args.initial_topic:
                logger.info(f"添加初始主题词: {args.initial_topic}")
                topic_manager.add_initial_topic(args.initial_topic)
            
            # 2. 初始化LLM客户端和主题提取器
            llm_client = LLMClient()
            topic_extractor = TopicExtractor(llm_client, topic_manager)
            
            # 3. 提取主题
            paper_topics = topic_extractor.extract_topics_from_file(args.input)
            
            # 4. 保存结果
            success = topic_extractor.save_paper_topics(paper_topics, args.output)
            
            # 5. 更新提示词模板和显示结果
            if success:
                topic_manager.update_prompt_template()
                logger.info("最终主题词列表：")
                topic_manager.list_all_topics()
        
        elif args.command == 'add':
            # 添加新主题词
            aliases = args.aliases.split(',') if args.aliases else None
            max_id = 0
            for topic in topic_manager.topics.values():
                try:
                    topic_id = int(topic.id)
                    if topic_id > max_id:
                        max_id = topic_id
                except ValueError:
                    pass
            new_id = str(max_id + 1)
            success = topic_manager.add_topic(new_id, args.name_zh, args.name_en, aliases)
            if success:
                logger.info(f"成功添加主题 {new_id}. {args.name_zh} ({args.name_en})")
            else:
                logger.error(f"添加主题失败")
                sys.exit(1)
        
        elif args.command == 'merge':
            # 合并主题词
            success = topic_manager.merge_topics(args.source, args.target)
            if success:
                logger.info(f"成功合并主题 {args.source} 到 {args.target}")
            else:
                logger.error(f"合并主题失败")
                sys.exit(1)
        
        elif args.command == 'list':
            # 列出所有主题词
            topic_manager.list_all_topics()
        
        elif args.command == 'update_prompt':
            # 更新提示词模板
            success = topic_manager.update_prompt_template()
            if success:
                logger.info("提示词模板更新成功")
            else:
                logger.error("提示词模板更新失败")
                sys.exit(1)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"执行命令时出错: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 