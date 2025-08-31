#!/usr/bin/env python3
"""
论文总结主脚本
用于运行论文10个方面的总结分析
包含两个阶段：
1. 智能章节匹配（section_match）
2. 论文总结（section_conclude）
"""

import sys
import os
import argparse
import logging

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from abs2paper.processing.section_match import SectionMatcher
from abs2paper.processing.section_conclude import SectionConcluder

def main():
    """主函数：执行完整的论文总结流程"""
    parser = argparse.ArgumentParser(description="完整的论文总结流程（章节匹配 + 内容总结）")
    parser.add_argument("--input_dir", type=str, help="输入目录，覆盖默认的component_extract路径")
    parser.add_argument("--output_dir", type=str, help="输出目录，覆盖默认的conclude_result路径")
    parser.add_argument("--skip-section-match", action="store_true", help="跳过第一阶段章节匹配，直接进行总结")
    parser.add_argument("--only-section-match", action="store_true", help="只执行第一阶段章节匹配，跳过第二阶段总结")
    parser.add_argument("--force", action="store_true", help="自动覆盖已存在的结果，不询问用户")
    
    args = parser.parse_args()
    
    try:
        if args.force:
            print("📋 强制模式：将自动覆盖所有已存在的结果")
            logging.info("📋 强制模式：将自动覆盖所有已存在的结果")
        else:
            print("📋 注意：运行过程中会检查已存在的结果，并询问是否重新生成")
            logging.info("📋 注意：运行过程中会检查已存在的结果，并询问是否重新生成")
        
        # 第一阶段：智能章节匹配
        if not args.skip_section_match:
            print("🚀 第一阶段：开始智能章节匹配...")
            logging.info("🚀 第一阶段：开始智能章节匹配...")
            
            # 创建章节匹配器
            matcher = SectionMatcher(force_overwrite=args.force)
            
            # 如果提供了自定义输入路径，则更新
            if args.input_dir:
                matcher.input_dir = os.path.abspath(args.input_dir)
                logging.info(f"使用自定义输入目录: {matcher.input_dir}")
            
            # 执行章节匹配
            match_success = matcher.match_all_papers()
            
            if not match_success:
                print("❌ 第一阶段章节匹配失败，退出")
                logging.error("❌ 第一阶段章节匹配失败，退出")
                sys.exit(1)
            
            print("✅ 第一阶段章节匹配完成")
            logging.info("✅ 第一阶段章节匹配完成")
            
            # 如果只执行第一阶段，则在此退出
            if args.only_section_match:
                print("🎉 第一阶段章节匹配完成，已退出（仅执行第一阶段）")
                logging.info("🎉 第一阶段章节匹配完成，已退出（仅执行第一阶段）")
                sys.exit(0)
        else:
            print("⏭️ 跳过第一阶段章节匹配")
            logging.info("⏭️ 跳过第一阶段章节匹配")
        
        # 第二阶段：论文内容总结
        print("📝 第二阶段：开始论文内容总结...")
        logging.info("📝 第二阶段：开始论文内容总结...")
        
        # 创建总结器
        concluder = SectionConcluder(force_overwrite=args.force)
        
        # 如果提供了自定义路径，则更新
        if args.input_dir:
            concluder.input_dir = os.path.abspath(args.input_dir)
            logging.info(f"使用自定义输入目录: {concluder.input_dir}")
        
        if args.output_dir:
            concluder.conclude_result_dir = os.path.abspath(args.output_dir)
            os.makedirs(concluder.conclude_result_dir, exist_ok=True)
            logging.info(f"使用自定义输出目录: {concluder.conclude_result_dir}")
        
        # 执行总结
        conclude_success = concluder.conclude_all_papers()
        
        if conclude_success:
            print("🎉 论文总结流程全部完成！")
            logging.info("🎉 论文总结流程全部完成！")
            sys.exit(0)
        else:
            print("❌ 第二阶段论文总结失败")
            logging.error("❌ 第二阶段论文总结失败")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ 论文总结流程出现严重错误: {e}")
        logging.error(f"❌ 论文总结流程出现严重错误: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 