#!/usr/bin/env python3
import argparse
import sys
import os
from abs2paper.rag.paper_ingestor import PaperIngestor

def main():
    parser = argparse.ArgumentParser(description="批量将论文各部分及主题标签写入向量数据库")
    parser.add_argument('--component_dir', type=str, default=None, help='component_extract目录')
    parser.add_argument('--label_dir', type=str, default=None, help='label目录')
    parser.add_argument('--config', type=str, default=None, help='config.json路径')
    args = parser.parse_args()
    ingestor = PaperIngestor(config_path=args.config)
    ingestor.ingest(component_dir=args.component_dir, label_dir=args.label_dir)

if __name__ == "__main__":
    main() 