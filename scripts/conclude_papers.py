#!/usr/bin/env python3
"""
论文总结主脚本
用于运行论文10个方面的总结分析
"""

import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from abs2paper.processing.section_conclude import main

if __name__ == "__main__":
    main() 