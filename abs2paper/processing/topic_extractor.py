"""
论文主题提取模块

本模块实现两阶段主题提取流程：
1. 从论文摘要中提取初步主题
2. 整合和合并提取的主题
"""

import os
import re
import json
import logging
from typing import List, Dict, Tuple, Any, Optional, Set
from datetime import datetime

# 导入主题管理器
from abs2paper.utils.topic_manager import TopicManager, Topic

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TopicExtractor:
    """
    论文主题提取器，实现两阶段主题提取流程
    """
    
    def __init__(self, llm_client, topic_manager: Optional[TopicManager] = None):
        """
        初始化主题提取器
        
        Args:
            llm_client: LLM客户端，用于调用大模型
            topic_manager: 主题管理器，如果为None则创建新实例
        """
        self.llm_client = llm_client
        self.topic_manager = topic_manager or TopicManager()
    
    def extract_initial_topics(self, abstracts: List[Tuple[str, str]]) -> List[Tuple[str, List[str]]]:
        """
        从多篇论文摘要中提取初步主题词
        
        Args:
            abstracts: 论文摘要列表，格式为[(论文ID, 摘要文本)]
            
        Returns:
            extracted_topics: 提取的主题词列表，格式为[(论文ID, [主题ID])]
        """
        extracted_topics = []
        
        # 获取当前有效的主题词列表
        topic_list = self.topic_manager.generate_topic_list_text()
        
        # 构建提示模板
        prompt_template = """
请分析以下论文摘要，给出与之相关的主题关键词。
仅从以下主题关键词中选择：
{topic_list}

论文摘要：
{abstract}

请输出相关的主题ID，格式为[ID1, ID2, ...]：
        """
        
        logger.info(f"开始从 {len(abstracts)} 篇论文摘要中提取主题")
        
        # 处理每篇论文
        for paper_id, abstract in abstracts:
            logger.info(f"提取论文 {paper_id} 的主题")
            
            try:
                # 构建完整提示
                prompt = prompt_template.format(
                    topic_list=topic_list,
                    abstract=abstract
                )
                
                # 调用LLM
                response = self.llm_client.get_completion(prompt)
                
                # 解析响应，提取主题ID
                topic_ids = self._parse_topic_ids(response)
                
                if topic_ids:
                    logger.info(f"论文 {paper_id} 的主题: {topic_ids}")
                    extracted_topics.append((paper_id, topic_ids))
                else:
                    logger.warning(f"无法从论文 {paper_id} 中提取主题")
                    
            except Exception as e:
                logger.error(f"提取论文 {paper_id} 的主题时出错: {e}")
        
        logger.info(f"已从 {len(extracted_topics)} 篇论文中提取主题")
        return extracted_topics
    
    def _parse_topic_ids(self, response: str) -> List[str]:
        """
        从模型响应中解析主题ID
        
        Args:
            response: 模型响应文本
            
        Returns:
            主题ID列表
        """
        # 尝试匹配方括号中的内容
        match = re.search(r'\[(.*?)\]', response)
        if match:
            # 提取所有数字
            topic_ids = re.findall(r'\d+', match.group(1))
            return topic_ids
        
        # 如果没有匹配到方括号，尝试直接提取数字
        topic_ids = re.findall(r'\d+', response)
        return topic_ids
    
    def consolidate_topics(self, extracted_topics: List[Tuple[str, List[str]]]) -> List[Tuple[str, List[str]]]:
        """
        整合和合并所有提取的主题
        
        Args:
            extracted_topics: 初步提取的主题词，格式为[(论文ID, [主题ID])]
            
        Returns:
            consolidated_topics: 整合后的主题词，格式为[(论文ID, [主题ID])]
        """
        if not extracted_topics:
            logger.warning("没有提供任何主题进行整合")
            return []
        
        # 收集所有出现的主题ID
        all_topic_ids = set()
        for _, topics in extracted_topics:
            all_topic_ids.update(topics)
        
        if not all_topic_ids:
            logger.warning("没有发现任何主题ID")
            return extracted_topics
        
        logger.info(f"开始整合 {len(all_topic_ids)} 个主题: {all_topic_ids}")
        
        # 获取所有主题的详细信息
        topic_details = []
        for topic_id in all_topic_ids:
            topic_info = self.topic_manager.get_topic_info(topic_id)
            if topic_info:
                topic_details.append(topic_info)
        
        # 按创建时间排序主题（早期创建的主题优先）
        topic_details.sort(key=lambda x: x.get('created_at', ''))
        
        # 如果只有一个主题，无需合并
        if len(topic_details) <= 1:
            logger.info("只有一个主题，无需合并")
            return extracted_topics
        
        # 构建主题合并提示
        merge_prompt = self._create_merge_prompt(topic_details)
        
        try:
            # 调用LLM获取合并建议
            merge_response = self.llm_client.get_completion(merge_prompt)
            
            # 解析合并建议
            merge_suggestions = self._parse_merge_suggestions(merge_response)
            
            logger.info(f"解析到 {len(merge_suggestions)} 个合并建议")
            
            # 执行合并操作
            for source_id, target_id in merge_suggestions:
                logger.info(f"合并主题 {source_id} 到 {target_id}")
                self.topic_manager.merge_topics(source_id, target_id)
            
            # 更新所有论文的主题映射
            updated_topics = []
            for paper_id, topics in extracted_topics:
                # 获取每个主题的有效ID
                effective_topics = [self.topic_manager.get_effective_topic_id(t) for t in topics]
                # 去重
                effective_topics = list(set(effective_topics))
                updated_topics.append((paper_id, effective_topics))
            
            logger.info(f"主题整合完成，更新了 {len(updated_topics)} 篇论文的主题")
            return updated_topics
            
        except Exception as e:
            logger.error(f"整合主题时出错: {e}")
            return extracted_topics
    
    def _create_merge_prompt(self, topic_details: List[Dict[str, Any]]) -> str:
        """
        创建主题合并提示
        
        Args:
            topic_details: 主题详细信息列表
            
        Returns:
            合并提示文本
        """
        # 生成主题列表文本
        topic_list = []
        for topic in topic_details:
            topic_list.append(f"{topic['id']}. {topic['name_zh']}（{topic['name_en']}）")
        
        topic_list_text = "\n".join(topic_list)
        
        # 构建提示模板
        prompt = f"""
我有以下主题关键词（按重要性排序）：
{topic_list_text}

请分析这些主题词，识别相似或重复的概念，建议将哪些主题合并。
合并时，应该将后创建的主题合并到先创建的主题中，保持原有的主题体系。

请按照以下规则给出合并建议：
1. 如果两个主题完全相同或高度相似，应该合并
2. 如果一个主题是另一个主题的子集或特例，应该合并
3. 避免创建过于宽泛的主题

回复格式为：合并[待合并ID]->[目标ID]，例如"合并5->3"表示将主题5合并到主题3中。
每行一个合并建议，如果没有需要合并的主题，请回答"无需合并"。
        """
        
        return prompt
    
    # 这一块需要修改，因为模型可能会返回多个合并建议，需要解析出所有的合并建议
    # 对于prompt需要进行回复的格式进行要求，才能进行字符匹配。
    def _parse_merge_suggestions(self, response: str) -> List[Tuple[str, str]]:
        """
        解析合并建议
        
        Args:
            response: 模型响应文本
            
        Returns:
            合并建议列表，格式为[(源主题ID, 目标主题ID)]
        """
        merge_suggestions = []
        
        # 检查是否无需合并
        if "无需合并" in response:
            logger.info("模型建议无需合并主题")
            return merge_suggestions
        
        # 匹配所有"合并X->Y"模式
        pattern = r'合并\s*(\d+)\s*->\s*(\d+)'
        matches = re.findall(pattern, response)
        
        for source, target in matches:
            merge_suggestions.append((source, target))
        
        # 如果没有找到标准格式，尝试直接提取数字对
        if not merge_suggestions:
            # 查找形如 "5->3" 的模式
            alt_pattern = r'(\d+)\s*->\s*(\d+)'
            alt_matches = re.findall(alt_pattern, response)
            
            for source, target in alt_matches:
                merge_suggestions.append((source, target))
        
        return merge_suggestions
    
    def process_abstracts(self, abstracts: List[Tuple[str, str]]) -> Dict[str, List[str]]:
        """
        处理论文摘要，提取并整合主题（完整流程）
        
        Args:
            abstracts: 论文摘要列表，格式为[(论文ID, 摘要文本)]
            
        Returns:
            paper_topics: 论文主题词字典，格式为{论文ID: [主题ID]}
        """
        logger.info("开始完整的主题提取流程")
        
        # 第一阶段：初步提取主题
        extracted_topics = self.extract_initial_topics(abstracts)
        
        # 第二阶段：整合和合并主题
        consolidated_topics = self.consolidate_topics(extracted_topics)
        
        # 转换为字典格式
        paper_topics = {paper_id: topics for paper_id, topics in consolidated_topics}
        
        logger.info(f"主题提取完成，处理了 {len(paper_topics)} 篇论文")
        return paper_topics
    
    def extract_topics_from_file(self, abstract_dir: str) -> Dict[str, List[str]]:
        """
        从文件中提取论文主题
        
        Args:
            abstract_dir: 论文摘要文件目录
            
        Returns:
            paper_topics: 论文主题词字典，格式为{论文ID: [主题ID]}
        """
        abstracts = []
        
        # 读取目录中的所有文件
        for filename in os.listdir(abstract_dir):
            if filename.endswith(".txt"):
                paper_id = os.path.splitext(filename)[0]
                
                try:
                    with open(os.path.join(abstract_dir, filename), 'r', encoding='utf-8') as f:
                        abstract = f.read().strip()
                    
                    if abstract:
                        abstracts.append((paper_id, abstract))
                        
                except Exception as e:
                    logger.error(f"读取文件 {filename} 失败: {e}")
        
        # 处理论文摘要
        return self.process_abstracts(abstracts)
    
    def save_paper_topics(self, paper_topics: Dict[str, List[str]], output_dir: str) -> bool:
        """
        保存论文主题到文件
        
        Args:
            paper_topics: 论文主题词字典，格式为{论文ID: [主题ID]}
            output_dir: 输出目录，路径是/data/mjs/project/abs2paper/output/paper_topics
            
        Returns:
            是否保存成功
        """
        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存每篇论文的主题
            for paper_id, topics in paper_topics.items():
                output_file = os.path.join(output_dir, f"{paper_id}.txt")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    # 获取主题词的中文和英文名称
                    topic_texts = []
                    for topic_id in topics:
                        topic_info = self.topic_manager.get_topic_info(topic_id)
                        if topic_info:
                            topic_texts.append(f"{topic_id}. {topic_info['name_zh']}（{topic_info['name_en']}）")
                    
                    # 构建输出文本
                    output_text = "\n".join(topic_texts)
                    f.write(f"{paper_id}:\n{output_text}\n\n故该论文的主题关键词总结为[{','.join(topics)}]。")
            
            # 保存汇总结果
            summary_file = os.path.join(output_dir, "paper_topics_summary.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "paper_topics": paper_topics,
                    "timestamp": datetime.now().isoformat(),
                    "topic_count": len(self.topic_manager.topics)
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存 {len(paper_topics)} 篇论文的主题到 {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"保存论文主题失败: {e}")
            return False 