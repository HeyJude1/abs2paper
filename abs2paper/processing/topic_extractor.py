"""
论文主题提取模块

本模块实现两阶段主题提取流程：
1. 从论文摘要中提取初步主题
2. 整合和合并提取的主题

同时支持整个两阶段工作流：
1. 阶段一：从论文摘要中初次提取和整合主题词，形成稳定主题列表
2. 阶段二：使用稳定主题列表重新为论文分配主题
"""

import os
import re
import json
import logging
from typing import List, Dict, Tuple, Any, Optional, Set
from datetime import datetime

# 导入主题管理器
from abs2paper.utils.topic_manager import TopicManager, Topic
# from abs2paper.processing.labeling import PaperLabeler

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
        
        # 加载提示词模板
        prompt_template = self._load_prompt_template()
        
        logger.info(f"开始从 {len(abstracts)} 篇论文摘要中提取主题")
        
        # 处理每篇论文
        for paper_id, abstract in abstracts:
            logger.info(f"提取论文 {paper_id} 的主题")
            
            try:
                # 构建完整提示
                prompt = prompt_template.replace("{abstract}", abstract)
                
                # 调用LLM
                response = self.llm_client.get_completion(prompt)
                
                # 解析响应，提取主题ID和新主题
                topic_ids, new_topics = self._parse_topics_response(response)
                
                # 收集主题信息用于日志
                known_topics_count = len(topic_ids)
                new_topics_count = len(new_topics)
                
                # 获取匹配到的主题名称，用于日志
                matched_topic_info = []
                if topic_ids:
                    for topic_id in topic_ids:
                        if topic_id in self.topic_manager.topics:
                            topic = self.topic_manager.topics[topic_id]
                            matched_topic_info.append(f"{topic_id}.{topic.name_zh}")
                
                # 记录匹配和新增主题数量
                logger.info(f"匹配{known_topics_count}个已有主题，得到{new_topics_count}个新主题")
                
                # 如果有新主题，立即保存到gen_topic.json
                if new_topics:
                    logger.debug(f"新主题词: {new_topics}")
                    
                    # 立即保存新主题词到gen_topic.json
                    self._save_generated_topics(new_topics)
                
                if topic_ids or new_topics:
                    extracted_topics.append((paper_id, topic_ids))
                else:
                    logger.warning(f"无法从论文 {paper_id} 中提取任何主题")
                    
            except Exception as e:
                logger.error(f"提取论文 {paper_id} 的主题时出错: {e}")
                logger.exception(e)
        
        logger.info(f"已从 {len(extracted_topics)} 篇论文中提取主题")
        return extracted_topics
    
    def _load_prompt_template(self) -> str:
        """
        加载提示词模板
        
        Returns:
            prompt_template: 提示词模板
        """
        try:
            # 获取项目根目录
            module_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(module_dir))
            
            # 获取配置文件路径
            config_path = os.path.join(project_root, "config", "config.json")
            
            # 读取配置文件获取提示词路径
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            generate_topic_path = os.path.join(project_root, config["data_paths"]["generate_topic"]["path"].lstrip('/'))
            
            # 读取提示词模板
            with open(generate_topic_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
                logger.info(f"已加载提示词模板: {generate_topic_path}")
                
            return prompt_template
            
        except Exception as e:
            logger.error(f"加载提示词模板时出错: {e}")
            raise
            
    def _save_generated_topics(self, new_topics: List[str]) -> bool:
        """
        保存生成的主题词到gen_topic.json
        
        Args:
            new_topics: 新生成的主题词列表
            
        Returns:
            是否成功保存
        """
        if not new_topics:
            logger.info("没有新生成的主题词需要保存")
            return True
            
        try:
            # 加载现有的生成主题词
            generated_topics = self.topic_manager.load_generated_topics()
            
            # 加载topic.json中的主题，获取最大ID作为起始点
            # 这样生成的ID会从topic.json的最大ID+1开始
            max_id = 0
            for topic in self.topic_manager.topics.values():
                try:
                    topic_id = int(topic.id)
                    max_id = max(max_id, topic_id)
                except ValueError:
                    pass
            
            # 检查gen_topic.json中是否有更大的ID
            for topic_id in generated_topics:
                try:
                    id_num = int(topic_id)
                    max_id = max(max_id, id_num)
                except ValueError:
                    pass
            
            # 为新主题词分配连续的ID
            next_id = max_id + 1
            for topic in new_topics:
                # 检查是否已存在
                exists = False
                for topic_data in generated_topics.values():
                    if (topic_data.get("name_zh") == topic) or (topic in topic_data.get("aliases", [])):
                        exists = True
                        break
                
                if not exists:
                    # 直接使用纯数字ID
                    temp_id = str(next_id)
                    next_id += 1
                    
                    # 解析主题名称，提取中文和英文部分
                    name_zh = topic
                    name_en = topic
                    
                    if '，' in topic or ',' in topic:
                        parts = re.split(r'[,，]', topic)
                        name_zh = parts[0].strip()
                        
                        # 尝试查找英文部分
                        for part in parts[1:]:
                            if "Keywords:" in part or "keywords:" in part:
                                name_en = part.split(':', 1)[1].strip() if ':' in part else part.strip()
                                break
                        
                        # 如果没有找到英文部分，使用最后一个部分
                        if name_en == topic:
                            name_en = parts[-1].strip()
                    
                    # 移除主题名称中的前缀数字和点
                    # 例如 "1. 高性能计算" -> "高性能计算"
                    name_zh = re.sub(r'^\d+\.\s*', '', name_zh)
                    
                    # 添加到生成主题词字典
                    generated_topics[temp_id] = {
                        "id": temp_id,
                        "name_zh": name_zh,
                        "name_en": name_en,
                        "aliases": [],
                        "status": "pending", # pending表示待处理
                        "created_at": datetime.now().isoformat()
                    }
                    
                    logger.info(f"添加新生成的主题词: {temp_id}. {name_zh} ({name_en})")
            
            # 保存更新后的生成主题词
            return self.topic_manager.save_generated_topics(generated_topics)
            
        except Exception as e:
            logger.error(f"保存生成的主题词失败: {e}")
            return False
    
    def _parse_topics_response(self, response: str) -> Tuple[List[str], List[str]]:
        """
        解析模型响应，提取主题ID和新主题
        
        Args:
            response: 模型响应文本
            
        Returns:
            (topic_ids, new_topics): 主题ID列表和新主题列表
        """
        topic_ids = set()  # 使用集合去重
        new_topics = set()  # 使用集合去重
        
        # 如果响应为None（可能因网络问题），直接返回空结果
        if response is None:
            logger.warning("收到空响应（可能是网络问题），无法提取主题")
            return [], []
        
        # 记录原始响应，便于调试
        logger.debug(f"原始LLM响应: {response}")
        
        # 分析不同类型的主题
        known_topics_matched = []
        new_topics_added = []
        
        # 将响应分成多个部分，便于处理
        parts = response.split("匹配的主题词：")
        
        # 如果找到"匹配的主题词："标记
        if len(parts) > 1:
            matched_part = parts[1]
            # 进一步分割，获取匹配主题和新添加主题的部分
            sub_parts = matched_part.split("新添加的主题词：")
            
            # 处理匹配的主题词部分
            matched_topics_text = sub_parts[0].strip()
            for line in matched_topics_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # 检查是否是已有主题词格式：数字.中文关键词，Keywords: English Keywords
                if line[0].isdigit() and '.' in line.split(' ')[0]:
                    id_part = line.split('.')[0].strip()
                    if id_part.isdigit() and id_part in self.topic_manager.topics:
                        topic_ids.add(id_part)
                        topic_name = self.topic_manager.topics[id_part].name_zh
                        known_topics_matched.append(f"{id_part}.{topic_name}")
            
            # 如果有新添加的主题词部分
            if len(sub_parts) > 1:
                new_topics_text = sub_parts[1].strip()
                for line in new_topics_text.split('\n'):
                    line = line.strip()
                    if not line and "新添加的主题词：" not in line:
                        continue
                        
                    # 检查是否是新的主题词格式
                    if "，Keywords:" in line or ", Keywords:" in line:
                        # 移除主题名称中的前缀数字和点 (例如 "1. 高性能计算" -> "高性能计算")
                        cleaned_line = re.sub(r'^\d+\.\s*', '', line)
                        new_topics.add(cleaned_line)
                        new_topics_added.append(cleaned_line)
        
        # 直接查找"新添加的主题词："标记
        for line in response.split('\n'):
            line = line.strip()
            
            # 跳过空行或已处理的行
            if not line:
                continue
            
            # 如果是"新添加的主题词："标记行
            if "新添加的主题词：" in line:
                continue
                
            # 如果是一个完整的主题词格式（包含Keywords）
            if ("，Keywords:" in line or ", Keywords:" in line):
                # 检查这不是匹配的主题词（不以数字和点开头）
                if not (line[0].isdigit() and '.' in line.split(' ')[0]):
                    # 移除主题名称中的前缀数字和点
                    cleaned_line = re.sub(r'^\d+\.\s*', '', line)
                    if cleaned_line not in new_topics:
                        new_topics.add(cleaned_line)
                        new_topics_added.append(cleaned_line)
        
        # 输出解析结果统计
        if known_topics_matched:
            logger.debug(f"匹配到 {len(known_topics_matched)} 个已有主题: {', '.join(known_topics_matched)}")
        else:
            logger.debug(f"未匹配到任何已有主题")
            
        if new_topics_added:
            logger.debug(f"添加了 {len(new_topics_added)} 个新主题: {', '.join(new_topics_added)}")
        
        # 如果没有找到任何主题，记录警告并尝试其他格式
        if not topic_ids and not new_topics:
            logger.warning(f"使用标准格式无法从LLM响应中提取任何主题，尝试其他格式...")
            
            # 尝试更广泛地匹配新主题词
            # 查找所有可能是"中文关键词，Keywords: English Keywords"格式的行
            keyword_pattern = r'([^，,:]+)[，,](?:\s*Keywords:|\s*keywords:)\s*([^\n]+)'
            for match in re.finditer(keyword_pattern, response, re.IGNORECASE):
                # 获取中文部分
                zh_part = match.group(1).strip()
                # 移除前缀数字和点
                zh_part = re.sub(r'^\d+\.\s*', '', zh_part)
                # 获取英文部分
                en_part = match.group(2).strip()
                
                # 组合成完整的主题词格式
                topic = f"{zh_part}，Keywords: {en_part}"
                if topic not in new_topics:
                    new_topics.add(topic)
                    new_topics_added.append(topic)
        
        # 如果仍然没有找到任何主题，尝试使用更宽松的匹配方法
        if not topic_ids and not new_topics:
            logger.warning(f"仍然无法提取任何主题，尝试使用更宽松的匹配...")
            
            # 查找可能的中文主题词，不要求Keywords格式
            potential_topics = []
            for line in response.split('\n'):
                line = line.strip()
                if line and ',' not in line and '，' not in line and len(line) <= 20:
                    # 移除前缀数字和点
                    line = re.sub(r'^\d+\.\s*', '', line)
                    potential_topics.append(f"{line}，Keywords: {line}")
            
            if potential_topics:
                for topic in potential_topics:
                    if topic not in new_topics:
                        new_topics.add(topic)
                        new_topics_added.append(topic)
                logger.debug(f"通过宽松匹配添加了 {len(potential_topics)} 个新主题")
        
        # 将集合转换回列表
        return list(topic_ids), list(new_topics)

    def process_abstracts(self, abstracts: List[Tuple[str, str]]) -> Dict[str, List[str]]:
        """
        处理论文摘要，提取并整合主题（完整流程）
        
        Args:
            abstracts: 论文摘要列表，格式为[(论文ID, 摘要文本)]
            
        Returns:
            paper_topics: 论文主题词字典，格式为{论文ID: [主题ID]}
        """
        # 第一阶段：初步提取主题
        extracted_topics = self.extract_initial_topics(abstracts)
        
        # 转换为字典格式
        paper_topics = {paper_id: topics for paper_id, topics in extracted_topics}
        
        # 不再执行后续的整合和合并操作，这些应该由extract_topics.py调用topic_manager来完成
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
        
        # 递归遍历目录查找所有.txt文件
        for root, dirs, files in os.walk(abstract_dir):
            for filename in files:
                if filename.endswith(".txt"):
                    file_path = os.path.join(root, filename)
                    paper_id = os.path.splitext(filename)[0]
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            abstract = f.read().strip()
                        
                        if abstract:
                            abstracts.append((paper_id, abstract))
                            # 删除冗余日志输出
                            # logger.info(f"已读取摘要: {file_path}")
                    
                    except Exception as e:
                        logger.error(f"读取文件 {file_path} 失败: {e}")
        
        logger.info(f"总共找到 {len(abstracts)} 篇论文摘要")
        
        # 处理论文摘要
        return self.process_abstracts(abstracts)
    
    def save_paper_topics(self, paper_topics: Dict[str, List[str]], output_dir: str) -> bool:
        """
        保存论文主题到文件
        
        Args:
            paper_topics: 论文主题词字典，格式为{论文ID: [主题ID]}
            output_dir: 输出目录，默认路径是/abs2paper/processing/data/output/paper_topics
            
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
            
    def add_initial_topic(self, initial_topic: str) -> str:
        """
        添加初始主题词
        
        Args:
            initial_topic: 初始主题词，如"代码生成"
            
        Returns:
            新主题ID
        """
        # 直接调用topic_manager的方法
        return self.topic_manager.add_initial_topic(initial_topic) 