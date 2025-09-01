#!/usr/bin/env python3
"""
RAG机器人主程序，提供知识库构建和问答功能
"""

import os
import sys
import time
import json
from typing import List, Dict, Any, Optional, Union

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.db_client import MilvusClient
from retriever import KnowledgeRetriever
from generator import ResponseGenerator
# from abs2paper.extraction.text import extract_text_from_pdf


class MilvusManagerAdapter:
    """MilvusClient到MilvusManager接口的适配器"""
    
    def __init__(self, config_path: str = None):
        # 加载配置文件
        if config_path and os.path.exists(config_path):
            config_file = config_path
        else:
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config", "config.json"
            )
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 提取Milvus配置
        vector_db_config = config["vector_db"]
        db_config = {
            "host": vector_db_config["host"],
            "port": vector_db_config["port"],
            "alias": vector_db_config["alias"],
            "db_name": vector_db_config["db_name"]
        }
        
        self.client = MilvusClient(db_config)
        self.collections = {}
    
    def create_collections(self, sections: List[str]):
        """适配create_collections接口"""
        # 这里需要根据sections创建相应的集合
        # 由于接口差异较大，暂时跳过实现
        pass
    
    def store_data(self, data: Dict[str, Any]):
        """适配store_data接口"""
        # 这里需要适配数据存储接口
        pass
    
    def load_all_collections(self):
        """适配load_all_collections接口"""
        pass
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """适配get_collection_stats接口"""
        return {}


class EmbeddingGeneratorAdapter:
    """embedding生成器适配器"""
    
    def __init__(self, config_path: str = None):
        self.llm_client = LLMClient()
    
    def generate_embedding(self, text: str) -> List[float]:
        """生成单个文本的embedding"""
        embeddings = self.llm_client.get_embedding([text])
        return embeddings[0] if embeddings else []
    
    def chunk_text(self, text: str, paper_id: str) -> List[Dict[str, Any]]:
        """文本分块"""
        # 简单分块实现
        chunk_size = 500
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append({
                "content": text[i:i+chunk_size],
                "paper_id": paper_id
            })
        return chunks


def print_header():
    """打印程序头部信息"""
    print("\n" + "=" * 50)
    print("               论文RAG系统")
    print("=" * 50)


def print_menu():
    """打印主菜单"""
    print("\n请选择功能:")
    print("1. 存储知识")
    print("2. 问答系统")
    print("3. 退出")
    print("-" * 30)


class RagBot:
    """RAG机器人，集成知识库构建和问答功能"""
    
    def __init__(self, config_path: str = None):
        """
        初始化RAG机器人
        
        Args:
            config_path: 配置文件路径
        """
        self.db_manager = MilvusManagerAdapter(config_path)
        self.embedding_generator = EmbeddingGeneratorAdapter(config_path)
        self.knowledge_retriever = KnowledgeRetriever(self.db_manager, config_path)
        self.response_generator = ResponseGenerator(None, config_path)
        self.config_path = config_path
    
    def run(self):
        """运行RAG机器人主程序"""
        print_header()
        
        while True:
            print_menu()
            choice = input("请输入选项编号: ")
            
            if choice == '1':
                self.store_knowledge()
            elif choice == '2':
                self.qa_system()
            elif choice == '3':
                print("感谢使用！再见！")
                break
            else:
                print("无效的选项，请重新输入！")
    
    def store_knowledge(self):
        """存储知识到向量数据库"""
        print("\n" + "=" * 50)
        print("               知识存储模式")
        print("=" * 50)
        
        # 获取PDF文件路径
        pdf_path = input("\n请输入PDF文件路径: ")
        if not os.path.exists(pdf_path):
            print(f"错误: 文件 '{pdf_path}' 不存在！")
            return
            
        # 获取论文ID
        paper_id = input("请输入论文ID: ")
        if not paper_id:
            paper_id = os.path.basename(pdf_path).replace('.pdf', '')
            print(f"使用默认论文ID: {paper_id}")
        
        # 获取主题
        topics_str = input("请输入论文主题(多个主题用逗号分隔): ")
        topics = [topic.strip() for topic in topics_str.split(',') if topic.strip()]
        
        print("\n开始处理PDF文件...")
        
        # 提取文本内容
        try:
            # text_sections = extract_text_from_pdf(pdf_path)
            # 临时替代实现：读取文本文件
            print("注意：PDF提取功能暂时不可用，请提供预处理的文本文件")
            return
        except Exception as e:
            print(f"提取文本时出错: {str(e)}")
            return
        
        # 创建集合
        sections = list(text_sections.keys())
        self.db_manager.create_collections(sections)
        
        # 存储每个部分的内容
        total_chunks = 0
        for section, content in text_sections.items():
            # 分块处理长文本
            chunks = self.embedding_generator.chunk_text(content, paper_id)
            total_chunks += len(chunks)
            
            for i, chunk in enumerate(chunks):
                # 生成嵌入向量
                embedding = self.embedding_generator.generate_embedding(chunk["content"])
                
                # 构建存储数据
                store_data = {
                    "paper_id": chunk["paper_id"],
                    "content": chunk["content"],
                    "topics": topics,
                    "source": os.path.basename(pdf_path),
                    "section": section,
                    "embedding": embedding
                }
                
                # 存储到数据库
                self.db_manager.store_data(store_data)
                print(f"已存储 {section} 部分的第 {i+1}/{len(chunks)} 块")
        
        print(f"\n处理完成！共存储了 {total_chunks} 个文本块到 {len(sections)} 个集合中")
    
    def qa_system(self):
        """问答系统主程序"""
        print("\n" + "=" * 50)
        print("               问答系统模式")
        print("=" * 50)
        
        # 加载所有集合到内存
        print("\n加载所有集合到内存...")
        self.db_manager.load_all_collections()
        
        # 显示集合统计信息
        stats = self.db_manager.get_collection_stats()
        if stats:
            print("\n数据库统计信息:")
            for section, info in stats.items():
                print(f"- {section}: {info['entity_count']} 条记录")
        else:
            print("警告: 没有找到任何集合，请先存储知识！")
            return
        
        # 问答循环
        print("\n开始问答，输入'退出'结束会话并返回主菜单")
        
        while True:
            # 获取用户问题
            query = input("\n请输入问题: ")
            if query.lower() in ['退出', 'quit', 'exit']:
                break
                
            # 获取可选的主题过滤条件
            topic = input("主题过滤(可选): ")
            if not topic.strip():
                topic = None
            
            # 搜索知识
            print("\n正在检索相关知识...")
            start_time = time.time()
            results = self.knowledge_retriever.search(query, topic)
            search_time = time.time() - start_time
            
            if not results:
                print("未找到相关内容，请尝试其他问题或移除主题过滤")
                continue
                
            # 显示搜索结果（仅显示部分）
            display_results = self.knowledge_retriever.get_display_results(results)
            print(f"\n找到 {len(results)} 条相关内容，显示前 {len(display_results)} 条:")
            for i, result in enumerate(display_results):
                print(f"\n【结果 {i+1}】")
                print(f"来源: {result['source']}")
                print(f"部分: {result['section']}")
                print(f"距离: {result['distance']:.4f}")
                print(f"内容: {result['content'][:100]}...")
            
            print(f"\n检索用时: {search_time:.2f}秒")
            
            # 生成回答
            print("\n正在生成回答...")
            start_time = time.time()
            response = self.response_generator.generate(results, query)
            generate_time = time.time() - start_time
            
            print("\n回答:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            print(f"生成用时: {generate_time:.2f}秒")


def main():
    """主函数"""
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "config.json"
        )
        
        bot = RagBot(config_path)
        bot.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 