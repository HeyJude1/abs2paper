import os
import json
import logging
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from abs2paper.utils.llm_client import LLMClient
from abs2paper.utils.db_client import MilvusClient

class SummaryRetriever:
    """多类型总结并行检索器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化总结检索器"""
        # 设置项目根目录和配置文件路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = config_path or os.path.join(self.project_root, "config", "config.json")
        self.config = self._load_config()
        
        # 初始化工具类
        self.llm_client = LLMClient()
        
        # 读取数据库配置
        vector_db_config = self.config["vector_db"]
        db_config = {
            "host": vector_db_config["host"],
            "port": vector_db_config["port"],
            "alias": vector_db_config["alias"],
            "db_name": vector_db_config["db_name"]
        }
        self.db_client = MilvusClient(db_config)
        
        # 10个总结类型
        self.summary_types = [
            "background", "relatedwork", "challenges", "innovations", 
            "methodology", "expedesign", "baseline", "metric", 
            "resultanalysis", "conclusion"
        ]
    
    def _load_config(self):
        """加载配置文件"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _get_summary_collection_name(self, summary_type: str) -> str:
        """获取总结类型对应的collection名称"""
        return f"summary_{summary_type.lower()}"
    
    def _search_single_summary_type(self, query_embedding: List[float], 
                                   summary_type: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索单个类型的总结"""
        try:
            collection_name = self._get_summary_collection_name(summary_type)
            
            # 搜索参数
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            output_fields = ["paper_id", "summary_text", "source_sections", "topics"]
            
            # 执行搜索
            results = self.db_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                output_fields=output_fields,
                top_n=top_k,
                params=search_params
            )
            
            # 处理搜索结果
            processed_results = []
            if results and len(results) > 0:
                for hit in results:  # results是字典列表
                    processed_results.append({
                        "paper_id": hit.get("paper_id"),
                        "summary_text": hit.get("summary_text"),
                        "source_sections": hit.get("source_sections", []),
                        "topics": hit.get("topics", []),
                        "score": float(hit.get("score", 0)),
                        "summary_type": summary_type
                    })
            
            logging.info(f"检索到 {len(processed_results)} 个 {summary_type} 类型的总结")
            return processed_results
            
        except Exception as e:
            logging.error(f"检索 {summary_type} 总结时出错: {e}")
            return []
    
    def parallel_retrieve_summaries(self, user_requirement: str, 
                                  top_k_per_type: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        多类型总结并行检索
        
        Args:
            user_requirement: 用户需求文本
            top_k_per_type: 每种类型返回的最大结果数
            
        Returns:
            relevant_summaries: 按类型组织的检索结果
        """
        logging.info(f"开始多类型总结并行检索，用户需求: {user_requirement}")
        
        # 生成查询向量
        query_embedding = self.llm_client.get_embedding([user_requirement])[0]
        
        # 并行检索所有类型的总结
        relevant_summaries = {}
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 提交所有检索任务
            future_to_type = {
                executor.submit(self._search_single_summary_type, query_embedding, summary_type, top_k_per_type): summary_type
                for summary_type in self.summary_types
            }
            
            # 收集结果
            for future in as_completed(future_to_type):
                summary_type = future_to_type[future]
                try:
                    results = future.result()
                    if results:  # 只保存有结果的类型
                        relevant_summaries[summary_type] = results
                except Exception as e:
                    logging.error(f"检索 {summary_type} 时出错: {e}")
        
        # 统计结果
        total_results = sum(len(results) for results in relevant_summaries.values())
        logging.info(f"多类型总结并行检索完成，共检索到 {total_results} 个结果，涵盖 {len(relevant_summaries)} 种类型")
        
        return relevant_summaries
    
    def get_retrieval_statistics(self, relevant_summaries: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """获取检索统计信息"""
        stats = {
            "total_summaries": sum(len(results) for results in relevant_summaries.values()),
            "types_found": len(relevant_summaries),
            "type_counts": {summary_type: len(results) for summary_type, results in relevant_summaries.items()},
            "unique_papers": len(set(
                summary["paper_id"] 
                for results in relevant_summaries.values() 
                for summary in results
            )),
            "average_score_by_type": {}
        }
        
        # 计算每种类型的平均得分
        for summary_type, results in relevant_summaries.items():
            if results:
                avg_score = sum(summary["score"] for summary in results) / len(results)
                stats["average_score_by_type"][summary_type] = avg_score
        
        return stats 