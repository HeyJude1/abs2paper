#!/usr/bin/env python3
import os
import sys
import json
import logging
import argparse
from abs2paper.rag.conclusion_ingestor import ConclusionIngestor

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    setup_logging()
    
    # 添加参数解析
    parser = argparse.ArgumentParser(description="将论文总结数据入库到Milvus")
    parser.add_argument("--conclude-dir", type=str, help="总结目录路径，覆盖配置文件中的路径")
    parser.add_argument("--config", type=str, help="配置文件路径")
    args = parser.parse_args()
    
    # 确定项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # 确定配置文件路径
    config_path = args.config or os.path.join(project_root, "config", "config.json")
    
    if not os.path.exists(config_path):
        logging.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    # 加载配置文件
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logging.info(f"已加载配置: {config_path}")
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        sys.exit(1)
    
    # 获取总结目录路径
    if args.conclude_dir:
        conclude_result_dir = os.path.abspath(args.conclude_dir)
        logging.info(f"使用指定的总结目录: {conclude_result_dir}")
    else:
        # 从配置文件中读取总结目录
        data_paths = config["data_paths"]
        conclude_path = data_paths["conclude_result"]["path"].lstrip('/')
        conclude_result_dir = os.path.abspath(os.path.join(project_root, conclude_path))
        logging.info(f"使用配置文件中的总结目录: {conclude_result_dir}")
    
    # 检查目录是否存在
    if not os.path.exists(conclude_result_dir):
        logging.error(f"总结目录不存在: {conclude_result_dir}")
        sys.exit(1)
    
    try:
        # 初始化入库器并执行入库
        logging.info("初始化ConclusionIngestor...")
        ingestor = ConclusionIngestor(config_path=config_path)
        
        logging.info("开始执行总结数据入库...")
        ingestor.ingest(conclude_result_dir=conclude_result_dir)
        
        logging.info("总结数据入库完成!")
        
    except Exception as e:
        logging.error(f"入库过程中发生错误: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 