#!/usr/bin/env python3
"""
项目初始化脚本，用于创建所有必要的目录结构
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def create_directory_structure(base_dir: str, verbose: bool = False):
    """
    在给定的目录下创建项目所需的目录结构
    
    Args:
        base_dir: 项目根目录
        verbose: 是否显示详细信息
    """
    # 确保基础目录存在
    base_path = Path(base_dir)
    base_path.mkdir(exist_ok=True)
    
    # 定义目录结构
    directories = [
        # 数据目录
        "data",
        "data/raw",
        "data/processed",
        
        # 输出目录
        "output",
        "output/text_extract",
        "output/component_extract",
        "output/abstract_extract",
        "output/labeled_results",
        
        # 模型目录
        "models",
        
        # 临时文件
        "temp",
        
        # 示例和测试数据
        "examples/data",
    ]
    
    # 创建目录
    created = 0
    for directory in directories:
        dir_path = base_path / directory
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            if verbose:
                logger.info(f"创建目录: {dir_path}")
            created += 1
        elif verbose:
            logger.info(f"目录已存在: {dir_path}")
    
    logger.info(f"成功创建 {created} 个目录")
    
    # 如果没有config/config.json，创建一个默认配置文件
    config_file = base_path / "config/config.json"
    if not config_file.exists():
        config_dir = base_path / "config"
        config_dir.mkdir(exist_ok=True)
        
        default_config = """
{
    "database": {
        "host": "localhost",
        "port": "19530"
    },
    "embedding": {
        "provider": "siliconflow",
        "model": "text-embedding-ada-002",
        "dimension": 1536,
        "chunk_size": 1000,
        "chunk_overlap": 200
    },
    "llm": {
        "provider": "siliconflow",
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.7,
        "top_p": 0.7
    },
    "grobid": {
        "server": "localhost",
        "port": "8070",
        "batch_size": 1000,
        "sleep_time": 5,
        "timeout": 60,
        "coordinates": ["persName", "figure", "ref", "biblStruct", "formula"]
    },
    "paths": {
        "raw_data": "data/raw",
        "processed_data": "data/processed",
        "embeddings": "data/embeddings",
        "prompt_templates": "config/prompts"
    }
}
"""
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(default_config.strip())
        logger.info(f"创建默认配置文件: {config_file}")
    
    logger.info("项目初始化完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="初始化项目目录结构")
    parser.add_argument("--base_dir", type=str, default=".",
                      help="项目根目录，默认为当前目录")
    parser.add_argument("--verbose", action="store_true",
                      help="显示详细信息")
    
    args = parser.parse_args()
    
    create_directory_structure(args.base_dir, args.verbose)


if __name__ == "__main__":
    main() 