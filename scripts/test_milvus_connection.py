#!/usr/bin/env python3
import os
import sys
import json
import logging
from pymilvus import connections, utility

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到系统路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def load_config():
    """加载配置文件"""
    config_path = os.path.join(project_root, "config", "config.json")
    logger.info(f"加载配置文件: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}

def test_milvus_connection():
    """测试Milvus连接"""
    # 加载配置
    config = load_config()
    vector_db_config = config.get("vector_db", {})
    
    # 获取连接参数
    host = vector_db_config.get("host", "192.168.70.174")
    port = vector_db_config.get("port", "19530")
    db_name = vector_db_config.get("db_name", "abs2paper")
    
    logger.info(f"连接参数: host={host}, port={port}, db_name={db_name}")
    
    # 尝试连接
    try:
        logger.info("尝试连接到Milvus...")
        connections.connect(alias="test_conn", host=host, port=port)
        logger.info("✅ 基本连接成功")
        
        # 尝试访问/创建数据库
        logger.info("检查数据库列表...")
        db_list = utility.list_database()
        logger.info(f"可用数据库: {db_list}")
        
        if db_name in db_list:
            logger.info(f"数据库 {db_name} 已存在")
        else:
            logger.info(f"创建数据库 {db_name}")
            utility.create_database(db_name)
            logger.info(f"✅ 成功创建数据库 {db_name}")
        
        # 连接到特定数据库
        connections.disconnect("test_conn")
        connections.connect(alias="test_conn", host=host, port=port, db_name=db_name)
        logger.info(f"✅ 成功连接到数据库 {db_name}")
        
        # 列出集合
        logger.info("列出集合...")
        collections = utility.list_collections()
        logger.info(f"集合列表: {collections}")
        
        return True
    except Exception as e:
        logger.error(f"Milvus连接测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # 断开连接
        try:
            connections.disconnect("test_conn")
            logger.info("已断开连接")
        except:
            pass

def main():
    logger.info("==== Milvus连接测试 ====")
    success = test_milvus_connection()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 