#!/usr/bin/env python3
import os
import json
import logging
from abs2paper.rag.paper_ingestor import PaperIngestor

def main():
    # 确定项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # 固定的配置文件路径
    config_path = os.path.join(project_root, "config", "config.json")
    
    # 加载配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        logging.info(f"已加载配置: {config_path}")
    
    # 获取路径配置
    data_paths = config["data_paths"]
    
    # 从配置文件中读取组件目录和标签目录
    component_path = data_paths["component_extract"]["path"].lstrip('/')
    label_path = data_paths["label"]["path"].lstrip('/')
    
    component_dir = os.path.abspath(os.path.join(project_root, component_path))
    label_dir = os.path.abspath(os.path.join(project_root, label_path))
    
    logging.info(f"组件目录: {component_dir}")
    logging.info(f"标签目录: {label_dir}")
    
    # 初始化入库器并执行入库
    ingestor = PaperIngestor(config_path=config_path)
    ingestor.ingest(component_dir=component_dir, label_dir=label_dir)

if __name__ == "__main__":
    main() 