#!/usr/bin/env python3
import os
import sys
import logging

# 添加项目根目录到系统路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from abs2paper.utils.topic_manager import TopicManager

def main():
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 显示项目根目录和预期的topics.json路径
    config_path = os.path.join(project_root, "config", "topics.json")
    logger.info(f"项目根目录: {project_root}")
    logger.info(f"预期的topics.json路径: {config_path}")
    
    # 检查config目录是否存在
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        logger.info(f"配置目录 {config_dir} 不存在，将创建")
    
    # 初始化TopicManager
    logger.info("初始化TopicManager...")
    manager = TopicManager()
    
    # 检查topics.json是否存在
    if os.path.exists(config_path):
        logger.info(f"topics.json存在于 {config_path}")
        logger.info(f"文件大小: {os.path.getsize(config_path)} 字节")
    else:
        logger.error(f"topics.json不存在于 {config_path}")
    
    # 获取所有主题词
    topics = manager.list_topics()
    logger.info(f"共加载了 {len(topics)} 个主题词")
    
    # 显示主题词列表
    for topic in topics:
        logger.info(f"ID: {topic['id']}, 中文: {topic['name_zh']}, 英文: {topic['name_en']}")
    
    # 生成主题词列表文本
    topic_list_text = manager.generate_topic_list_text()
    logger.info("生成的主题词列表文本:")
    logger.info(topic_list_text)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 