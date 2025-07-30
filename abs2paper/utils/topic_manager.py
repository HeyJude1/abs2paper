#!/usr/bin/env python3
"""
主题词管理工具

提供主题词的添加、修改、合并等功能，以及主题词的序列化和反序列化功能。
"""

import os
import json
import re
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union

# 获取日志记录器
logger = logging.getLogger(__name__)

class Topic:
    """主题词类，表示一个主题关键词及其属性"""
    
    def __init__(self, id: str, name_zh: str, name_en: str, aliases: Optional[List[str]] = None, 
                 parent_id: Optional[str] = None, created_at: Optional[str] = None):
        """
        初始化主题词
        
        Args:
            id: 主题ID，如"1"
            name_zh: 中文名称
            name_en: 英文名称
            aliases: 别名列表，可选
            parent_id: 父主题ID（用于处理合并关系），可选
            created_at: 创建时间，格式为ISO字符串，可选（默认为当前时间）
        """
        self.id = id
        self.name_zh = name_zh
        self.name_en = name_en
        self.aliases = aliases or []
        self.parent_id = parent_id
        
        # 如果没有提供创建时间，使用当前时间
        if created_at is None:
            self.created_at = datetime.now().isoformat()
        else:
            self.created_at = created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将主题词转换为字典格式，用于序列化
        
        Returns:
            主题词的字典表示
        """
        return {
            "id": self.id,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
            "aliases": self.aliases,
            "parent_id": self.parent_id,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Topic':
        """
        从字典创建主题词实例
        
        Args:
            data: 主题词的字典表示
            
        Returns:
            主题词实例
        """
        return cls(
            id=data["id"],
            name_zh=data["name_zh"],
            name_en=data["name_en"],
            aliases=data.get("aliases", []),
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at")
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"Topic(id={self.id}, name_zh={self.name_zh}, name_en={self.name_en})"

class TopicManager:
    """主题词管理器，负责管理、更新和合并主题词"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化主题词管理器
        
        Args:
            config_file: 配置文件路径，可选（默认为项目根目录下的topics.json）
        """
        # 获取项目根目录和配置路径
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.dirname(module_dir)
        
        # 加载项目配置
        config_path = os.path.join(self.project_root, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # 确定主题配置文件路径
        if config_file is None:
            topic_json_path = self.config["data_paths"]["topic_json"]["path"].lstrip('/')
            self.config_file = os.path.join(self.project_root, topic_json_path)
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        else:
            self.config_file = config_file
        
        # 确定生成主题配置文件路径
        gen_topic_json_path = self.config["data_paths"]["gen_topic_json"]["path"].lstrip('/')
        self.gen_topic_file = os.path.join(self.project_root, gen_topic_json_path)
        
        # 确定合并意见文件路径
        merge_opinion_path = self.config["data_paths"]["merge_opinion"]["path"].lstrip('/')
        self.merge_opinion_file = os.path.join(self.project_root, merge_opinion_path)
        
        # 初始化主题词字典和映射关系
        self.topics: Dict[str, Topic] = {}  # {id: Topic}
        self.topic_mapping: Dict[str, str] = {}  # {旧ID: 新ID}
        
        # 加载主题词
        self.load_topics()
        
        # 如果是新创建的配置，立即保存一次以确保文件存在
        if not os.path.exists(self.config_file):
            self.save_topics()
    
    def load_topics(self) -> bool:
        """
        从配置文件加载主题词
        
        Returns:
            是否成功加载
        """
        try:
            # 如果配置文件不存在，创建一个空的主题词字典
            if not os.path.exists(self.config_file):
                logger.warning(f"主题词配置文件 {self.config_file} 不存在，创建空主题词列表")
                self.topics = {}
                self.topic_mapping = {}
                return True
            
            # 读取配置文件
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载主题词
            if "topics" in data:
                for topic_data in data["topics"].values():
                    topic = Topic.from_dict(topic_data)
                    self.topics[topic.id] = topic
            
            # 加载映射关系
            if "mappings" in data:
                self.topic_mapping = data["mappings"]
            
            logger.info(f"成功加载 {len(self.topics)} 个主题词和 {len(self.topic_mapping)} 个映射关系")
            return True
            
        except Exception as e:
            logger.error(f"加载主题词失败: {e}")
            # 如果加载失败，初始化空主题词列表
            self.topics = {}
            self.topic_mapping = {}
            return False
    
    def save_topics(self) -> bool:
        """
        保存主题词到配置文件
        
        Returns:
            是否成功保存
        """
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # 准备数据
            data = {
                "topics": {topic.id: topic.to_dict() for topic in self.topics.values()},
                "mappings": self.topic_mapping,
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat()
            }
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"成功保存 {len(self.topics)} 个主题词到 {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存主题词失败: {e}")
            return False
    
    def add_topic(self, id: str, name_zh: str, name_en: str, aliases: Optional[List[str]] = None) -> bool:
        """
        添加新主题词
        
        Args:
            id: 主题ID
            name_zh: 中文名称
            name_en: 英文名称
            aliases: 别名列表，可选
            
        Returns:
            是否成功添加
        """
        # 检查ID是否已存在
        if id in self.topics:
            logger.warning(f"主题词ID {id} 已存在，无法添加")
            return False
        
        # 创建新主题词
        topic = Topic(id=id, name_zh=name_zh, name_en=name_en, aliases=aliases)
        self.topics[id] = topic
        
        # 保存更新
        self.save_topics()
        
        logger.debug(f"已添加新主题词: {topic}")
        return True
    
    def update_topic(self, id: str, name_zh: Optional[str] = None, 
                    name_en: Optional[str] = None, aliases: Optional[List[str]] = None) -> bool:
        """
        更新主题词
        
        Args:
            id: 主题ID
            name_zh: 中文名称，可选
            name_en: 英文名称，可选
            aliases: 别名列表，可选
            
        Returns:
            是否成功更新
        """
        # 检查ID是否存在
        if id not in self.topics:
            logger.warning(f"主题词ID {id} 不存在，无法更新")
            return False
        
        # 获取现有主题词
        topic = self.topics[id]
        
        # 更新字段
        if name_zh is not None:
            topic.name_zh = name_zh
        
        if name_en is not None:
            topic.name_en = name_en
        
        if aliases is not None:
            topic.aliases = aliases
        
        # 保存更新
        self.save_topics()
        
        logger.info(f"已更新主题词: {topic}")
        return True
    
    def get_effective_topic_id(self, topic_id: str) -> str:
        """
        获取主题词的有效ID（考虑映射关系）
        
        Args:
            topic_id: 主题词ID
            
        Returns:
            有效的主题词ID
        """
        current_id = topic_id
        visited = set()
        
        # 沿着映射关系追踪，直到找到最终ID或检测到循环
        while current_id in self.topic_mapping:
            # 检测循环引用
            if current_id in visited:
                logger.warning(f"检测到循环引用: {current_id}，中断追踪")
                break
            
            visited.add(current_id)
            current_id = self.topic_mapping[current_id]
        
        return current_id
    
    def get_topic_info(self, topic_id: str) -> Optional[Dict[str, Any]]:
        """
        获取主题词信息
        
        Args:
            topic_id: 主题词ID
            
        Returns:
            主题词信息字典，如果不存在则返回None
        """
        # 获取有效ID
        effective_id = self.get_effective_topic_id(topic_id)
        
        # 获取主题词
        if effective_id in self.topics:
            return self.topics[effective_id].to_dict()
        else:
            return None
    
    def get_topic_changes(self) -> Dict[str, str]:
        """
        获取主题词变更映射
        
        Returns:
            主题词变更映射字典 {旧ID: 新ID}
        """
        return self.topic_mapping.copy()
    
    def list_topics(self) -> List[Dict[str, Any]]:
        """
        列出所有主题词
        
        Returns:
            主题词列表
        """
        return [topic.to_dict() for topic in self.topics.values()]
    
    def get_topic_by_name(self, name: str, lang: str = 'zh') -> Optional[Topic]:
        """
        根据名称查找主题词
        
        Args:
            name: 主题词名称
            lang: 语言，'zh'表示中文，'en'表示英文
            
        Returns:
            匹配的主题词，如果不存在则返回None
        """
        name_lower = name.lower()
        
        for topic in self.topics.values():
            # 检查主题名称
            if lang == 'zh' and topic.name_zh.lower() == name_lower:
                return topic
            
            if lang == 'en' and topic.name_en.lower() == name_lower:
                return topic
            
            # 检查别名
            if name_lower in [alias.lower() for alias in topic.aliases]:
                return topic
        
        return None
    
    def generate_topic_list_text(self) -> str:
        """
        生成主题词列表文本，用于提示模板
        
        Returns:
            主题词列表文本
        """
        topic_texts = []
        
        for topic in self.topics.values():
            # 检查该主题是否被合并到其他主题
            if topic.id in self.topic_mapping:
                continue
                
            topic_texts.append(f"{topic.id}. {topic.name_zh}，Keywords: {topic.name_en}")
        
        return "\n".join(topic_texts)
    
    def generate_prompt_kb_text(self) -> str:
        """
        生成知识库提示文本，用于更新prompt_kb.txt
        
        Returns:
            知识库提示文本
        """
        header = "##知识库：以下是与高性能、编译、代码优化和人工智能相关的论文内容主题关键词及其英文翻译，其结构是序号+中文关键词+英文关键词Keywords："
        
        topic_list = self.generate_topic_list_text()
        
        return f"{header}\n{topic_list}"
        
    def list_all_topics(self) -> bool:
        """
        打印所有主题词列表，包括映射关系
        
        Returns:
            是否成功列出
        """
        try:
            # 获取所有主题词
            topics = self.list_topics()
            
            if not topics:
                logger.warning("没有找到任何主题词")
                return True
            
            # 仅记录简短的主题数量信息
            logger.info(f"主题词总计: {len(topics)} 个")
            if self.topic_mapping:
                logger.info(f"主题映射关系: {len(self.topic_mapping)} 个")
            
            # 详细内容以DEBUG级别日志记录
            if logger.isEnabledFor(logging.DEBUG):
                # 打印主题词列表（仅在DEBUG模式下）
                logger.debug("\n当前主题词列表:")
                logger.debug("=" * 60)
                logger.debug(f"{'ID':<5} {'中文名称':<20} {'英文名称':<30} {'合并到':<10}")
                logger.debug("-" * 60)
                
                for topic in sorted(topics, key=lambda x: x['id']):
                    id_str = topic['id']
                    name_zh = topic['name_zh']
                    name_en = topic['name_en']
                    parent_id = topic['parent_id'] if topic['parent_id'] else ""
                    
                    logger.debug(f"{id_str:<5} {name_zh:<20} {name_en:<30} {parent_id:<10}")
                
                logger.debug("=" * 60)
                
                # 打印映射关系（仅在DEBUG模式下）
                if self.topic_mapping:
                    logger.debug("\n主题映射关系:")
                    logger.debug("=" * 30)
                    logger.debug(f"{'旧ID':<5} -> {'新ID':<5}")
                    logger.debug("-" * 30)
                    
                    for old_id, new_id in self.topic_mapping.items():
                        logger.debug(f"{old_id:<5} -> {new_id:<5}")
                    
                    logger.debug("=" * 30)
            
            return True
            
        except Exception as e:
            logger.error(f"列出主题词时出错: {str(e)}")
            return False
            
    def add_initial_topic(self, initial_topic: str) -> str:
        """
        添加初始主题词
        
        Args:
            initial_topic: 初始主题词，如"代码生成"
            
        Returns:
            新主题ID
        """
        logger.info(f"添加初始主题词: {initial_topic}")
        
        # 获取最大ID
        max_id = 0
        for topic in self.topics.values():
            try:
                topic_id = int(topic.id)
                if topic_id > max_id:
                    max_id = topic_id
            except ValueError:
                pass
        
        # 生成新ID
        new_id = str(max_id + 1)
        
        # 判断是否是英文
        is_english = all(c.isalpha() or c.isspace() or c == '-' for c in initial_topic)
        
        # 添加初始主题词
        if is_english:
            name_en = initial_topic
            name_zh = initial_topic  # 需要翻译功能，但我们移除翻译相关代码以保持专注
        else:
            name_zh = initial_topic
            name_en = initial_topic if initial_topic.isascii() else "Code Generation"
            
        # 添加初始主题词
        success = self.add_topic(
            id=new_id, 
            name_zh=name_zh, 
            name_en=name_en
        )
        
        if success:
            logger.info(f"已添加初始主题词，ID: {new_id}")
        else:
            logger.error(f"添加初始主题词失败: {initial_topic}")
            
        return new_id
        
    def update_prompt_template(self, config: Optional[Dict] = None) -> bool:
        """
        更新提示词模板
        
        Args:
            config: 配置信息字典，如果为None则自动加载
            
        Returns:
            是否成功更新
        """
        try:
            # 获取提示词模板路径
            if config is None:
                module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                project_root = os.path.dirname(module_dir)
                config_path = os.path.join(project_root, "config", "config.json")
                
                # 读取配置文件获取提示词路径
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 从配置中获取路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # 使用get_topic而不是prompt_kb
            prompt_kb_path = os.path.join(project_root, config["data_paths"]["get_topic"]["path"].lstrip('/'))
            
            # 读取原始提示词
            with open(prompt_kb_path, 'r', encoding='utf-8') as f:
                original_prompt = f.read()
            
            # 生成主题词列表文本
            pattern = r"##知识库：.*?(?=##|$)"
            replacement = self.generate_prompt_kb_text()
            
            # 替换提示词中的知识库部分
            updated_prompt = re.sub(pattern, replacement, original_prompt, flags=re.DOTALL)
            
            # 如果没有成功替换，报错
            if updated_prompt == original_prompt:
                logger.warning("无法在提示词中找到知识库部分进行替换")
                return False
            
            # 备份原始提示词
            backup_path = f"{prompt_kb_path}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_prompt)
            
            # 保存更新后的提示词
            with open(prompt_kb_path, 'w', encoding='utf-8') as f:
                f.write(updated_prompt)
            
            logger.info(f"已更新提示词模板 {prompt_kb_path}")
            logger.info(f"原始提示词已备份到 {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"更新提示词模板时出错: {str(e)}")
            return False
            
    def consolidate_topics(self, extracted_topics: List[Tuple[str, List[str]]], llm_client) -> List[Tuple[str, List[str]]]:
        """
        整合和合并所有提取的主题
        
        Args:
            extracted_topics: 初步提取的主题词，格式为[(论文ID, [主题ID])]
            llm_client: LLM客户端，用于调用大模型
            
        Returns:
            consolidated_topics: 整合后的主题词，格式为[(论文ID, [主题ID])]
        """
        if not extracted_topics:
            logger.warning("没有提供任何主题进行整合")
            return []
        
        # 从gen_topic.json获取主题详细信息，而不是topic.json
        gen_topics = self.load_generated_topics()
        
        # 如果gen_topics为空，则无需整合
        if not gen_topics:
            logger.warning("gen_topic.json中没有主题，无需整合")
            return extracted_topics
        
        # 直接使用gen_topic.json中的所有主题，忽略extracted_topics中的主题ID
        logger.info(f"加载了 {len(gen_topics)} 个主题用于整合")
        
        # 收集所有主题的详细信息
        topic_details = []
        
        # 将gen_topic.json中的主题转换为topic_details格式
        for gen_id, topic_data in gen_topics.items():
            topic_info = {
                "id": gen_id,
                "name_zh": topic_data.get("name_zh", ""),
                "name_en": topic_data.get("name_en", ""),
                "aliases": topic_data.get("aliases", []),
                "created_at": topic_data.get("created_at", datetime.now().isoformat())
            }
            topic_details.append(topic_info)
        
        # 按创建时间排序主题（早期创建的主题优先）
        topic_details.sort(key=lambda x: x.get('created_at', ''))
        
        # 如果只有一个主题，无需合并
        if len(topic_details) <= 1:
            logger.info("只有一个主题，无需合并")
            return extracted_topics
        
        # 创建主题合并提示
        merge_prompt = self.create_merge_prompt(topic_details)
        
        try:
            # 定义output目录路径
            output_dir = os.path.join(
                os.path.dirname(self.merge_opinion_file), 
                "output"
            )
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存原始主题词列表到merge_ori文件
            merge_ori_path = os.path.join(output_dir, "merge_ori")
            try:
                # 生成原始主题词列表文本
                topic_list = []
                for topic in topic_details:
                    # 使用纯数字ID，不添加gen_前缀
                    topic_list.append(f"{topic['id']}. {topic['name_zh']}，Keywords: {topic['name_en']}")
                topic_list_text = "\n".join(topic_list)
                
                with open(merge_ori_path, 'w', encoding='utf-8') as f:
                    f.write(topic_list_text)
                logger.info("已保存原始主题词列表")
            except Exception as e:
                logger.error(f"保存原始主题词列表失败: {e}")
            
            # 调用LLM获取合并建议
            merge_response = llm_client.get_completion(merge_prompt)
            
            # 保存合并建议
            self.save_merge_opinion(merge_response)
            
            # 保存原始LLM响应到指定的output目录
            merge_llm_result_path = os.path.join(output_dir, "merge_LLM_result")
            try:
                with open(merge_llm_result_path, 'w', encoding='utf-8') as f:
                    f.write(merge_response)
                logger.info("已保存LLM原始响应")
            except Exception as e:
                logger.error(f"保存LLM原始响应失败: {e}")
            
            # 解析合并建议
            merge_suggestions = self.parse_merge_suggestions(merge_response)
            logger.info(f"解析到 {len(merge_suggestions)} 个合并建议")
            
            # 返回原始论文主题，不更新映射
            # 不再调用update_topics_with_suggestions，避免重复处理
            return extracted_topics
            
        except Exception as e:
            logger.error(f"整合主题时出错: {e}")
            return extracted_topics
        
    def add_new_topic(self, topic_name: str) -> str:
        """
        添加新主题
        
        Args:
            topic_name: 主题名称，格式为"中文名称，Keywords: 英文名称"
            
        Returns:
            新主题ID
        """
        # 获取最大ID
        max_id = 0
        for topic in self.topics.values():
            try:
                topic_id = int(topic.id)
                if topic_id > max_id:
                    max_id = topic_id
            except ValueError:
                pass
        
        # 生成新ID
        new_id = str(max_id + 1)
        
        # 解析主题名称，提取中文和英文部分
        if '，' in topic_name or ',' in topic_name:
            parts = re.split(r'[,，]', topic_name)
            name_zh = parts[0].strip()
            
            # 尝试查找英文部分
            name_en = ""
            for part in parts[1:]:
                if "Keywords:" in part or "keywords:" in part:
                    name_en = part.split(':', 1)[1].strip() if ':' in part else part.strip()
                    break
            
            # 如果没有找到英文部分，使用最后一个部分
            if not name_en:
                name_en = parts[-1].strip()
        else:
            # 没有明确分隔，使用原名称
            name_zh = topic_name
            name_en = topic_name
        
        # 添加新主题
        success = self.add_topic(new_id, name_zh, name_en)
        
        if success:
            logger.debug(f"已添加新主题: {new_id}. {name_zh} ({name_en})")
        else:
            logger.error(f"添加主题 {topic_name} 失败")
        
        return new_id 

    def save_generated_topics(self, generated_topics: Dict[str, Dict[str, Any]]) -> bool:
        """
        保存生成的主题词到gen_topic.json
        
        Args:
            generated_topics: 生成的主题词字典 {id: 主题数据}
            
        Returns:
            是否成功保存
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.gen_topic_file), exist_ok=True)
            
            # 准备数据
            data = {
                "topics": generated_topics,
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat(),
                "description": "存储阶段一询问大模型生成的主题词（待处理的主题词）"
            }
            
            # 保存到文件
            with open(self.gen_topic_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 简化日志消息
            logger.info("成功保存生成的主题词")
            return True
            
        except Exception as e:
            logger.error(f"保存生成主题词失败: {e}")
            return False
    
    def load_generated_topics(self) -> Dict[str, Dict[str, Any]]:
        """
        从gen_topic.json加载生成的主题词
        
        Returns:
            生成的主题词字典 {id: 主题数据}
        """
        generated_topics = {}
        
        try:
            # 如果文件不存在，返回空字典
            if not os.path.exists(self.gen_topic_file):
                return generated_topics
            
            # 读取文件
            with open(self.gen_topic_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载主题词
            if "topics" in data:
                generated_topics = data["topics"]
                if generated_topics:
                    logger.debug(f"加载了 {len(generated_topics)} 个生成的主题词")
            
            return generated_topics
            
        except Exception as e:
            logger.error(f"加载生成主题词失败: {e}")
            return {} 

    def save_merge_opinion(self, response: str) -> bool:
        """
        保存大模型返回的合并建议到merge_opinion.json
        
        Args:
            response: 大模型返回的响应文本
            
        Returns:
            是否成功保存
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.merge_opinion_file), exist_ok=True)
            
            # 提取"合并建议"部分
            merge_suggestions_text = ""
            if "合并建议" in response:
                # 从"合并建议"开始截取
                merge_suggestions_text = response[response.find("合并建议"):]
            else:
                # 如果没有明确的标识，使用整个响应
                merge_suggestions_text = response
            
            # 解析合并建议
            merge_suggestions = self.parse_merge_suggestions(response)
            
            # 准备数据
            data = {
                "merge_suggestions": merge_suggestions,
                "raw_response": merge_suggestions_text,
                "last_updated": datetime.now().isoformat(),
                "description": "存储大模型生成的主题词合并建议"
            }
            
            # 保存到文件
            with open(self.merge_opinion_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存合并建议")
            return True
            
        except Exception as e:
            logger.error(f"保存合并建议失败: {e}")
            return False

    def parse_merge_suggestions(self, response: str) -> List[Tuple[str, str]]:
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
        
        # 匹配各种可能的合并格式
        # 1. 匹配标准格式: "合并 X -> Y"
        pattern1 = r'合并\s*(\d+)\s*[-–]>\s*(\d+)'
        matches1 = re.findall(pattern1, response)
        for source, target in matches1:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
        
        # 2. 匹配带序号的合并格式: "数字.合并 X -> Y" 或 "数字. 合并 X -> Y"
        pattern2 = r'\d+\.?\s*合并\s*(\d+)\s*[-–]>\s*(\d+)'
        matches2 = re.findall(pattern2, response)
        for source, target in matches2:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
        
        # 3. 匹配层级关系格式: "合并X->Y,理由..."
        pattern3 = r'合并\s*(\d+)\s*[-–]>\s*(\d+)[,，]'
        matches3 = re.findall(pattern3, response)
        for source, target in matches3:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
                
        # 4. 匹配不带"合并"的格式: "X->Y"
        pattern4 = r'(\d+)\s*[-–]>\s*(\d+)'
        matches4 = re.findall(pattern4, response)
        for source, target in matches4:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
        
        # 5. 匹配"更新并合并"格式
        update_pattern = r'更新并合并\s*(\d+)\s*[-–]>\s*(\d+)'
        update_matches = re.findall(update_pattern, response)
        for source, target in update_matches:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
                
        # 6. 匹配特殊格式: "数字.合并数字->数字"(无空格)
        pattern5 = r'\d+\.合并(\d+)[-–]>(\d+)'
        matches5 = re.findall(pattern5, response)
        for source, target in matches5:
            if (source, target) not in merge_suggestions:
                merge_suggestions.append((source, target))
        
        logger.debug(f"解析到的合并建议: {merge_suggestions}")
        return merge_suggestions

    def create_merge_prompt(self, topic_details: List[Dict[str, Any]]) -> str:
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
        
        # 获取merge_topic提示模板路径
        merge_topic_path = os.path.join(
            self.project_root, 
            self.config["data_paths"]["merge_topic"]["path"].lstrip('/')
        )
        
        # 读取提示模板
        with open(merge_topic_path, 'r', encoding='utf-8') as f:
            merge_prompt_template = f.read()
        
        # 填充模板
        merge_prompt = merge_prompt_template.format(topic_list_text=topic_list_text)
        
        return merge_prompt

    def extract_merge_suggestions(self) -> List[Tuple[str, str, bool]]:
        """
        从merge_LLM_result文件提取合并建议
        
        Returns:
            合并建议列表，格式为[(源主题ID, 目标主题ID, 是否是概念精炼合并)]
        """
        try:
            # 直接从output/merge_LLM_result文件读取
            output_dir = os.path.join(os.path.dirname(self.merge_opinion_file), "output")
            merge_llm_result_path = os.path.join(output_dir, "merge_LLM_result")
            
            # 读取原始LLM响应
            with open(merge_llm_result_path, 'r', encoding='utf-8') as f:
                raw_response = f.read()
            
            # 使用parse_merge_suggestions方法来解析
            raw_suggestions = self.parse_merge_suggestions(raw_response)
            
            # 将解析结果转换为所需的格式
            suggestions = []
            for source, target in raw_suggestions:
                # 判断是否是概念精炼合并
                is_refinement = bool(re.search(rf'更新并合并\s*{source}\s*->\s*{target}', raw_response))
                suggestions.append((source, target, is_refinement))
            
            logger.info(f"从LLM响应文件成功提取 {len(suggestions)} 个合并建议")
            return suggestions
            
        except Exception as e:
            logger.error(f"提取合并建议失败: {e}")
            return []

    def update_topics_from_gen_topic(self, llm_client) -> bool:
        """
        将gen_topic.json中的主题覆盖更新到topic.json
        
        这个方法实现新的工作流：
        1. 先根据合并建议处理gen_topic.json中的主题关系
        2. 然后将处理好的主题覆盖更新到topic.json
        
        Args:
            llm_client: LLM客户端，用于调用大模型
            
        Returns:
            是否成功更新
        """
        try:
            # 1. 先处理合并建议，更新gen_topic.json内部的关系
            merge_suggestions = self.extract_merge_suggestions()
            
            if merge_suggestions:
                logger.info(f"处理 {len(merge_suggestions)} 个合并建议")
                # 加载所有gen_topic中的主题
                gen_topics = self.load_generated_topics()
                
                # 执行合并操作（仅在gen_topic内部）
                for source, target, is_refinement in merge_suggestions:
                    # 确保source和target都在gen_topic中
                    if source in gen_topics and target in gen_topics:
                        source_topic = gen_topics[source]
                        target_topic = gen_topics[target]
                        
                        logger.debug(f"合并 {source}({source_topic.get('name_zh', '')}) -> {target}({target_topic.get('name_zh', '')})")
                        
                        # 更新target_topic的别名列表，加入source_topic的名称
                        if "aliases" not in target_topic:
                            target_topic["aliases"] = []
                        
                        # 添加source的名称到target的别名中（如果不存在）
                        source_name_zh = source_topic.get("name_zh", "")
                        source_name_en = source_topic.get("name_en", "")
                        
                        if source_name_zh and source_name_zh not in target_topic["aliases"]:
                            target_topic["aliases"].append(source_name_zh)
                        
                        if source_name_en and source_name_en not in target_topic["aliases"]:
                            target_topic["aliases"].append(source_name_en)
                        
                        # 添加source的别名到target的别名中
                        for alias in source_topic.get("aliases", []):
                            if alias not in target_topic["aliases"]:
                                target_topic["aliases"].append(alias)
                        
                        # 标记source被合并到target
                        source_topic["merged_to"] = target
                        source_topic["status"] = "merged"
                
                # 保存更新后的gen_topics
                self.save_generated_topics(gen_topics)
            
            # 2. 将处理后的gen_topic覆盖更新到topic.json
            # 加载gen_topic.json中的所有主题
            gen_topics = self.load_generated_topics()
            
            # 创建一个新的topics字典
            new_topics = {}
            
            # 不保留原有mapping关系，全部重新生成
            mappings = {}
            
            # 从ID 1开始分配新ID
            next_id = 1
            
            # 记录gen_topic.json中主题ID到topic.json中ID的映射
            gen_to_topic_id_map = {}
            
            # 处理所有未被合并的主题，不区分来源
            for gen_id, gen_topic in gen_topics.items():
                if not gen_topic.get("status") == "merged":
                    # 分配新ID
                    new_id = str(next_id)
                    next_id += 1
                    
                    # 记录映射关系
                    gen_to_topic_id_map[gen_id] = new_id
                    
                    # 添加新主题
                    new_topics[new_id] = Topic(
                        id=new_id,
                        name_zh=gen_topic.get("name_zh", ""),
                        name_en=gen_topic.get("name_en", ""),
                        aliases=gen_topic.get("aliases", []),
                        created_at=gen_topic.get("created_at")
                    )
                    
                    logger.debug(f"添加主题 {new_id}: {gen_topic.get('name_zh')}")
            
            # 最后处理被合并的主题，更新映射关系
            for gen_id, gen_topic in gen_topics.items():
                if gen_topic.get("status") == "merged" and "merged_to" in gen_topic:
                    target_gen_id = gen_topic["merged_to"]
                    
                    # 检查原始ID和目标ID是否已经映射到topic.json
                    if gen_id in gen_to_topic_id_map and target_gen_id in gen_to_topic_id_map:
                        source_topic_id = gen_to_topic_id_map[gen_id]
                        target_topic_id = gen_to_topic_id_map[target_gen_id]
                        
                        # 更新映射关系
                        mappings[source_topic_id] = target_topic_id
                        logger.debug(f"更新主题映射: {source_topic_id} -> {target_topic_id}")
            
            # 更新topics和mappings
            self.topics = new_topics
            self.topic_mapping = mappings
            
            # 保存更新
            success = self.save_topics()
            
            if success:
                logger.info(f"成功更新 {len(new_topics)} 个主题到topic.json")
                return True
            else:
                logger.error("保存更新的主题失败")
                return False
                
        except Exception as e:
            logger.error(f"更新主题失败: {e}")
            logger.exception(e)
            return False
