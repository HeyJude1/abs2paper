#!/usr/bin/env python3
"""
简单问答示例，展示如何使用abs2paper进行问答
"""

import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abs2paper.core.db_manager import MilvusManager
from abs2paper.rag.retriever import KnowledgeRetriever
from abs2paper.rag.generator import ResponseGenerator


def simple_qa_example():
    """简单问答示例函数"""
    print("=" * 50)
    print("      简单论文问答示例")
    print("=" * 50)
    
    # 初始化数据库管理器
    print("\n初始化数据库连接...")
    db_manager = MilvusManager()
    
    # 加载所有集合
    print("加载所有知识库集合...")
    db_manager.load_all_collections()
    
    # 初始化检索器和生成器
    retriever = KnowledgeRetriever(db_manager)
    generator = ResponseGenerator()
    
    # 显示统计信息
    stats = db_manager.get_collection_stats()
    if stats:
        print("\n数据库统计信息:")
        for section, info in stats.items():
            print(f"- {section}: {info['entity_count']} 条记录")
    else:
        print("\n警告：未找到任何集合，请确保已存储知识！")
        return
    
    # 进行问答
    while True:
        print("\n" + "-" * 50)
        query = input("\n请输入问题(输入'退出'结束): ")
        
        if query.lower() in ['退出', 'exit', 'quit']:
            print("\n感谢使用！再见！")
            break
        
        # 检索知识
        print("\n正在检索相关知识...")
        start_time = time.time()
        results = retriever.search(query)
        search_time = time.time() - start_time
        
        # 显示搜索结果
        if results:
            display_results = retriever.get_display_results(results)
            print(f"\n找到 {len(results)} 条相关内容，显示前 {len(display_results)} 条:")
            
            for i, result in enumerate(display_results):
                print(f"\n【结果 {i+1}】")
                print(f"来源: {result['source']}")
                print(f"部分: {result['section']}")
                print(f"距离: {result['distance']:.4f}")
                print(f"内容: {result['content'][:150]}...")
            
            print(f"\n检索用时: {search_time:.2f}秒")
            
            # 生成回答
            print("\n正在生成回答...")
            start_time = time.time()
            response = generator.generate(results, query)
            generate_time = time.time() - start_time
            
            print("\n回答:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            print(f"生成用时: {generate_time:.2f}秒")
        else:
            print("未找到相关内容，请尝试其他问题！")


if __name__ == "__main__":
    try:
        simple_qa_example()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()