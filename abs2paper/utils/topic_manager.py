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
            
            # 转换为更详细的格式，包含合并类型
            detailed_suggestions = []
            for source, target, merge_type in merge_suggestions:
                detailed_suggestions.append({
                    "source": source,
                    "target": target,
                    "type": merge_type,
                    "description": "更新并合并" if merge_type == "update_merge" else "合并"
                })
            
            # 准备数据
            data = {
                "merge_suggestions": detailed_suggestions,
                "raw_response": merge_suggestions_text,
                "last_updated": datetime.now().isoformat(),
                "description": "存储大模型生成的主题词合并建议，包含合并类型信息"
            }
            
            # 保存到文件
            with open(self.merge_opinion_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存合并建议")
            return True
            
        except Exception as e:
            logger.error(f"保存合并建议失败: {e}")
            return False

    def parse_merge_suggestions(self, response: str) -> List[Tuple[str, str, str]]:
        """
        解析合并建议
        
        Args:
            response: 模型响应文本
            
        Returns:
            合并建议列表，格式为[(源主题ID, 目标主题ID, 合并类型)]
            合并类型: "merge" 表示普通合并, "update_merge" 表示更新并合并
        """
        merge_suggestions = []
        
        # 检查是否无需合并
        if "无需合并" in response:
            logger.info("模型建议无需合并主题")
            return merge_suggestions
        
        # 1. 匹配"更新并合并"格式 - 优先处理
        update_pattern = r'更新并合并\s*(\d+)\s*[-–]>\s*(\d+)'
        update_matches = re.findall(update_pattern, response)
        for source, target in update_matches:
            if (source, target, "update_merge") not in merge_suggestions:
                merge_suggestions.append((source, target, "update_merge"))
        
        # 2. 匹配标准格式: "合并 X -> Y" (排除更新并合并)
        pattern1 = r'(?<!更新并)合并\s*(\d+)\s*[-–]>\s*(\d+)'
        matches1 = re.findall(pattern1, response)
        for source, target in matches1:
            # 检查是否已经被更新并合并处理过
            if not any(s == source and t == target for s, t, _ in merge_suggestions):
                merge_suggestions.append((source, target, "merge"))
        
        # 3. 匹配带序号的合并格式: "数字.合并 X -> Y"
        pattern2 = r'\d+\.?\s*合并\s*(\d+)\s*[-–]>\s*(\d+)'
        matches2 = re.findall(pattern2, response)
        for source, target in matches2:
            # 检查上下文是否包含"更新并"
            context_start = max(0, response.find(f'{source}') - 10)
            context_end = min(len(response), response.find(f'{target}') + 10)
            context = response[context_start:context_end]
            
            if "更新并" in context:
                merge_type = "update_merge"
            else:
                merge_type = "merge"
            
            if not any(s == source and t == target for s, t, _ in merge_suggestions):
                merge_suggestions.append((source, target, merge_type))
        
        # 4. 匹配层级关系格式: "合并X->Y,理由..."
        pattern3 = r'合并\s*(\d+)\s*[-–]>\s*(\d+)[,，]'
        matches3 = re.findall(pattern3, response)
        for source, target in matches3:
            if not any(s == source and t == target for s, t, _ in merge_suggestions):
                merge_suggestions.append((source, target, "merge"))
                
        # 5. 匹配不带"合并"的格式: "X->Y"
        pattern4 = r'(\d+)\s*[-–]>\s*(\d+)'
        matches4 = re.findall(pattern4, response)
        for source, target in matches4:
            # 只有在没有被其他模式匹配的情况下才添加
            if not any(s == source and t == target for s, t, _ in merge_suggestions):
                # 检查上下文是否包含"更新"字样
                context_pattern = rf'更新[^。]*{source}\s*[-–]>\s*{target}'
                if re.search(context_pattern, response):
                    merge_suggestions.append((source, target, "update_merge"))
                else:
                    merge_suggestions.append((source, target, "merge"))
                
        # 6. 匹配特殊格式: "数字.合并数字->数字"(无空格)
        pattern5 = r'\d+\.合并(\d+)[-–]>(\d+)'
        matches5 = re.findall(pattern5, response)
        for source, target in matches5:
            if not any(s == source and t == target for s, t, _ in merge_suggestions):
                merge_suggestions.append((source, target, "merge"))
        
        logger.debug(f"解析到的合并建议: {merge_suggestions}")
        return merge_suggestions

    def create_merge_prompt(self, topic_details: List[Dict[str, Any]]) -> str:
        """
        创建主题合并提示
        
        Args:
            topic_details: 主题详细信息列表
            
        Returns:
            构建好的提示词
        """
        try:
            # 获取项目根目录
            module_dir = os.path.dirname(os.path.abspath(__file__))  # abs2paper/utils
            project_root = os.path.dirname(os.path.dirname(module_dir))  # abs2paper根目录
            
            # 读取配置文件获取提示词路径
            config_path = os.path.join(project_root, "config", "config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            merge_topic_path = os.path.join(project_root, config["data_paths"]["merge_topic"]["path"].lstrip('/'))
            
            # 读取合并主题提示模板
            with open(merge_topic_path, 'r', encoding='utf-8') as f:
                merge_prompt_template = f.read()
            
            # 构建主题列表文本
            topic_list_text = ""
            for topic in topic_details:
                # 移除主题名称中可能存在的前缀数字
                name_zh = re.sub(r'^\d+\.\s*', '', topic['name_zh'])
                topic_list_text += f"{topic['id']}. {name_zh}，Keywords: {topic['name_en']}\n"
            
            # 替换模板中的占位符
            merge_prompt = merge_prompt_template.replace("{topic_list_text}", topic_list_text)
            
            logger.info("已创建主题合并提示")
            return merge_prompt
            
        except Exception as e:
            logger.error(f"创建主题合并提示时出错: {e}")
            raise

    def extract_merge_suggestions(self) -> List[Tuple[str, str, str]]:
        """
        从LLM响应文件中提取合并建议
        
        Returns:
            List[Tuple[str, str, str]]: 合并建议列表，每个元组为(源ID, 目标ID, 合并类型)
        """
        try:
            # 定义输出目录路径
            output_dir = os.path.join(
                os.path.dirname(self.merge_opinion_file), 
                "output"
            )
            merge_llm_result_path = os.path.join(output_dir, "merge_LLM_result")
            
            if not os.path.exists(merge_llm_result_path):
                logger.warning(f"未找到LLM响应文件: {merge_llm_result_path}")
                return []
            
            with open(merge_llm_result_path, 'r', encoding='utf-8') as f:
                response = f.read()
            
            merge_suggestions = self.parse_merge_suggestions(response)
            logger.info(f"从LLM响应文件成功提取 {len(merge_suggestions)} 个合并建议")
            return merge_suggestions
            
        except Exception as e:
            logger.error(f"提取合并建议失败: {e}")
            return []

    def load_middle_topics(self) -> Dict[str, Dict[str, Any]]:
        """
        加载middle_topic.json中的主题词（中间合并过程的主题词）
        
        Returns:
            Dict[str, Dict[str, Any]]: 主题词ID到主题词信息的映射
        """
        try:
            # 获取middle_topic.json路径（与topic.json在同一目录）
            middle_topic_file = os.path.join(os.path.dirname(self.config_file), "middle_topic.json")
            
            if os.path.exists(middle_topic_file):
                with open(middle_topic_file, 'r', encoding='utf-8') as f:
                    middle_data = json.load(f)
                
                topics = middle_data.get("topics", {})
                
                # 检查topics数量 - 第一轮时没有主题是正常的，不需要日志输出
                if topics:
                    logger.info(f"成功加载 {len(topics)} 个中间主题词")
                
                return topics
            else:
                # 第一轮时不存在middle_topic.json是正常的，不需要警告
                logger.debug(f"middle_topic.json文件不存在（第一轮处理时正常）")
                return {}
        
        except Exception as e:
            logger.error(f"加载中间主题词时出错: {e}")
            return {}

    def save_middle_topics(self, topics: Dict[str, Any]) -> bool:
        """
        保存主题词到middle_topic.json
        
        Args:
            topics: 要保存的主题词字典
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 获取middle_topic.json路径（与topic.json在同一目录）
            middle_topic_file = os.path.join(os.path.dirname(self.config_file), "middle_topic.json")
            
            # 构造完整的数据结构
            middle_data = {
                "topics": topics,
                "mappings": {},
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat(),
                "description": "存储中间合并过程的主题词"
            }
            
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(middle_topic_file), exist_ok=True)
            
            # 保存文件
            with open(middle_topic_file, 'w', encoding='utf-8') as f:
                json.dump(middle_data, f, ensure_ascii=False, indent=2)
            
            # 删除重复的日志输出，只在_finalize_merge_to_middle中输出
            logger.debug(f"保存 {len(topics)} 个主题词到middle_topic.json")
            return True
        
        except Exception as e:
            logger.error(f"保存中间主题词失败: {e}")
            logger.exception(e)
            return False

    def _finalize_merge_to_topic_json(self, source_topics: Dict[str, Any]) -> bool:
        """
        完成第二阶段合并，将结果保存到topic.json
        
        Args:
            source_topics: 已经完成第一阶段合并操作的主题词
            
        Returns:
            bool: 是否成功完成合并
        """
        try:
            # 创建一个新的topics字典
            new_topics = {}
            
            # 从ID 1开始分配新ID
            next_id = 1
            
            # 记录源主题ID到新ID的映射
            id_map = {}
            
            # 处理所有未被合并的主题
            for old_id, topic in source_topics.items():
                # 检查merged字段而不是status字段
                if not topic.get("merged", False):
                    # 分配新ID
                    new_id = str(next_id)
                    next_id += 1
                    
                    # 记录映射关系
                    id_map[old_id] = new_id
                    
                    # 添加新主题
                    new_topics[new_id] = Topic(
                        id=new_id,
                        name_zh=topic.get("name_zh", ""),
                        name_en=topic.get("name_en", ""),
                        aliases=topic.get("aliases", []),
                        created_at=topic.get("created_at", datetime.now().isoformat())
                    )
                    
                    logger.debug(f"添加到topic.json: {new_id}: {topic.get('name_zh')}")
            
            # 更新topics和mappings
            self.topics = new_topics
            self.topic_mapping = {}
            
            # 保存结果到topic.json
            success = self.save_topics()
            
            if success:
                logger.info(f"第二阶段完成：成功更新 {len(new_topics)} 个主题到topic.json")
                return True
            else:
                logger.error("保存更新的主题失败")
                return False
        
        except Exception as e:
            logger.error(f"完成第二阶段合并到topic.json失败: {e}")
            logger.exception(e)
            return False

    def _finalize_merge_to_middle(self, source_topics: Dict[str, Any]) -> bool:
        """
        完成第二阶段合并，将结果保存到middle_topic.json
        
        Args:
            source_topics: 已经完成第一阶段合并操作的主题词
            
        Returns:
            bool: 是否成功完成合并
        """
        try:
            # 创建一个新的topics字典
            new_topics = {}
            
            # 从ID 1开始分配新ID
            next_id = 1
            
            # 记录源主题ID到新ID的映射
            id_map = {}
            
            # 处理所有未被合并的主题
            for old_id, topic in source_topics.items():
                # 检查merged字段而不是status字段
                if not topic.get("merged", False):
                    # 分配新ID
                    new_id = str(next_id)
                    next_id += 1
                    
                    # 记录映射关系
                    id_map[old_id] = new_id
                    
                    # 添加新主题，保持middle_topic的格式
                    new_topics[new_id] = {
                        "id": new_id,
                        "name_zh": topic.get("name_zh", ""),
                        "name_en": topic.get("name_en", ""),
                        "aliases": topic.get("aliases", []),
                        "created_at": topic.get("created_at", datetime.now().isoformat()),
                        "status": "pending"  # middle_topic使用status字段
                    }
                    
                    logger.debug(f"添加到middle_topic.json: {new_id}: {topic.get('name_zh')}")
            
            # 保存结果到middle_topic.json
            success = self.save_middle_topics(new_topics)
            
            if success:
                logger.info(f"成功更新 {len(new_topics)} 个主题到middle_topic.json")
                return True
            else:
                logger.error("保存中间主题失败")
                return False
        
        except Exception as e:
            logger.error(f"完成第二阶段合并到middle_topic.json失败: {e}")
            logger.exception(e)
            return False

    def update_topics_from_merge(self, llm_client, target: str = "topic", use_code_merge: bool = True) -> bool:
        """
        根据合并建议更新主题词（支持指定目标文件：topic.json或middle_topic.json）
        
        Args:
            llm_client: LLM客户端，用于调用大模型
            target: 目标文件，可以是"topic"或"middle_topic"
            use_code_merge: 是否使用代码合并（True）或LLM合并（False）
            
        Returns:
            bool: 是否成功更新
        """
        try:
            if use_code_merge:
                logger.info(f"使用代码合并方法，目标: {target}")
                
                # 根据target参数获取源主题数据
                source_topics = None
                if target == "middle_topic":
                    # 如果目标是middle_topic，先看middle_topic.json是否存在数据
                    source_topics = self.load_middle_topics()
                    # 如果middle_topic为空，则从gen_topic.json获取数据
                    if not source_topics:
                        source_topics = self.load_generated_topics()
                elif target == "topic":
                    # 如果目标是topic.json，先从middle_topic.json获取数据
                    source_topics = self.load_middle_topics()
                    # 如果middle_topic为空，则从gen_topic.json获取数据
                    if not source_topics:
                        source_topics = self.load_generated_topics()
                else:
                    # 其他情况下，从gen_topic.json获取数据
                    source_topics = self.load_generated_topics()
                
                if not source_topics:
                    logger.warning(f"源主题数据为空，无法进行合并")
                    return False
                
                # 获取合并建议
                merge_suggestions = self.extract_merge_suggestions()
                if not merge_suggestions:
                    # 当没有合并建议时，直接复制主题（第一轮时正常情况）
                    if target == "middle_topic":
                        return self.save_middle_topics(source_topics)
                    else:
                        return self._finalize_merge_to_topic_json(source_topics)
                
                logger.info(f"开始执行两阶段合并操作，共 {len(merge_suggestions)} 个合并建议")
                
                # 第一阶段：设置合并状态和执行交换操作
                for source_id, target_id, merge_type in merge_suggestions:
                    if source_id in source_topics and target_id in source_topics:
                        if merge_type == "merge":
                            # 普通合并：将源主题合并到目标主题
                            target_topic = source_topics[target_id]
                            source_topic = source_topics[source_id]
                            
                            # 将源主题的别名添加到目标主题
                            if "aliases" not in target_topic:
                                target_topic["aliases"] = []
                            target_topic["aliases"].extend([source_topic["name_zh"], source_topic["name_en"]])
                            target_topic["aliases"] = list(set(target_topic["aliases"]))  # 去重
                            
                            # 标记源主题为已合并
                            source_topics[source_id]["merged"] = True
                            source_topics[source_id]["status"] = "merged"
                            source_topics[source_id]["merged_to"] = target_id
                            
                            logger.debug(f"普通合并: {source_id}({source_topic['name_zh']}) -> {target_id}({target_topic['name_zh']})")
                            
                        elif merge_type == "update_merge":
                            # 更新并合并：交换内容后合并
                            source_topic = source_topics[source_id]
                            target_topic = source_topics[target_id]
                            
                            logger.debug(f"更新并合并前: {source_id}号={source_topic['name_zh']}, {target_id}号={target_topic['name_zh']}")
                            
                            # 交换内容：将源主题的内容复制到目标位置，目标主题的内容保存到源位置
                            original_target_content = {
                                "name_zh": target_topic["name_zh"],
                                "name_en": target_topic["name_en"],
                                "aliases": target_topic.get("aliases", []).copy()
                            }
                            
                            # 将源主题的内容复制到目标位置
                            target_topic["name_zh"] = source_topic["name_zh"]
                            target_topic["name_en"] = source_topic["name_en"]
                            target_topic["aliases"] = source_topic.get("aliases", []).copy()
                            
                            # 将原目标内容复制到源位置
                            source_topic["name_zh"] = original_target_content["name_zh"]
                            source_topic["name_en"] = original_target_content["name_en"]
                            source_topic["aliases"] = original_target_content["aliases"]
                            
                            # 标记原目标内容（现在在源位置）为已合并
                            source_topics[source_id]["merged"] = True
                            source_topics[source_id]["status"] = "merged"
                            source_topics[source_id]["merged_to"] = target_id
                            
                            logger.debug(f"更新并合并后: {source_id}号={source_topic['name_zh']}(已标记为合并), {target_id}号={target_topic['name_zh']}")
                
                # 保存第一阶段的结果，确保合并状态被记录
                if target == "middle_topic":
                    self.save_middle_topics(source_topics)
                elif target == "topic":
                    # 对于第三轮合并，数据来源是middle_topic，所以保存回middle_topic
                    self.save_middle_topics(source_topics)
                else:
                    # 其他情况保存到gen_topic
                    self.save_generated_topics(source_topics)
                
                # 第二阶段：根据目标类型，进行最终处理
                if target == "middle_topic":
                    # 将结果保存到middle_topic.json，重新编号
                    return self._finalize_merge_to_middle(source_topics)
                else:
                    # 将结果保存到topic.json，重新编号
                    return self._finalize_merge_to_topic_json(source_topics)
            else:
                # 保留原有的LLM合并方法
                logger.info("使用LLM合并方法处理主题")
                return self._update_topics_with_llm(llm_client)
                
        except Exception as e:
            logger.error(f"更新主题失败: {e}")
            logger.exception(e)
            return False 