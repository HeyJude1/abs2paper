#!/usr/bin/env python3
"""
主题词向量数据库同步工具

将主题词变更同步到向量数据库，更新已有论文的主题词标记。
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入相关模块
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.rag.topic_synchronizer import VectorDBSynchronizer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def sync_topics_to_db(config_file: Optional[str] = None, host: Optional[str] = None, 
                     port: Optional[str] = None, db_name: Optional[str] = None) -> bool:
    """
    将主题词变更同步到向量数据库
    
    Args:
        config_file: 主题配置文件路径，可选
        host: 数据库主机地址，可选
        port: 数据库端口，可选
        db_name: 数据库名称，可选
        
    Returns:
        是否成功同步
    """
    try:
        # 初始化主题管理器
        topic_manager = TopicManager(config_file)
        
        # 获取主题词变更
        topic_changes = topic_manager.get_topic_changes()
        if not topic_changes:
            logger.info("没有主题词变更需要同步")
            return True
        
        logger.info(f"发现 {len(topic_changes)} 个主题词变更需要同步")
        
        # 读取配置文件
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 使用配置文件中的数据库设置（如果未提供参数）
            vector_db_config = config.get("vector_db", {})
            host = host or vector_db_config.get("host", "localhost")
            port = port or vector_db_config.get("port", "19530")
            db_name = db_name or vector_db_config.get("db_name", "abs2paper")
        except Exception as e:
            logger.warning(f"读取配置文件失败: {str(e)}，将使用默认设置")
        
        # 初始化向量数据库同步器
        logger.info(f"连接到向量数据库: {host}:{port}/{db_name}")
        synchronizer = VectorDBSynchronizer(topic_manager, host, port, db_name)
        
        # 加载集合
        logger.info("加载集合...")
        if not synchronizer.load_all_collections():
            logger.error("加载集合失败")
            return False
        
        # 同步主题词变更
        logger.info("开始同步主题词变更...")
        success = synchronizer.synchronize_topics()
        
        if success:
            logger.info("同步成功")
        else:
            logger.error("同步失败")
        
        return success
        
    except Exception as e:
        logger.error(f"同步主题词变更时出错: {str(e)}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="将主题词变更同步到向量数据库")
    
    parser.add_argument("--config", type=str, help="主题配置文件路径")
    parser.add_argument("--host", type=str, help="数据库主机地址")
    parser.add_argument("--port", type=str, help="数据库端口")
    parser.add_argument("--db", type=str, help="数据库名称")
    
    args = parser.parse_args()
    
    success = sync_topics_to_db(args.config, args.host, args.port, args.db)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main() 