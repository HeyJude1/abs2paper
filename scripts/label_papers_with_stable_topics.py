#!/usr/bin/env python3
"""
基于稳定主题词的论文标签处理脚本

调用labeling.py模块，使用稳定的topic.json主题词列表来为论文打标签。
输入：abs2paper/extraction/result/abstract_extract/目录中的txt文件
输出：abs2paper/extraction/result/label/目录中的标签结果
"""

import os
import sys
import argparse
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入标签处理模块
from abs2paper.processing.labeling import label_papers

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
    """主函数：调用labeling.py进行论文标签处理"""
    parser = argparse.ArgumentParser(description="基于稳定主题词为论文打标签")
    parser.add_argument("--input_dir", type=str, 
                       help="输入目录（默认为abs2paper/extraction/result/abstract_extract/）")
    parser.add_argument("--output_dir", type=str, 
                       help="输出目录（默认为abs2paper/extraction/result/label/）")
    
    args = parser.parse_args()
    
    try:
        logger.info("🚀 开始基于稳定主题词为论文打标签")
        
        # 调用labeling.py的label_papers函数
        success = label_papers(input_dir=args.input_dir, output_dir=args.output_dir)
        
        if success:
            logger.info("✅ 论文标签处理完成")
        else:
            logger.error("❌ 论文标签处理失败")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"处理过程中出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main() 