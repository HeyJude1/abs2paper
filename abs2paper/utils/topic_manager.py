"""
主题词管理模块

本模块提供主题词的管理、更新和合并功能。
主要功能：
1. 维护主题词列表和映射关系
2. 支持添加、更新和合并主题词
3. 提供主题词持久化存储
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any, Union

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        # 确定配置文件路径
        if config_file is None:
            module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(module_dir)
            self.config_file = os.path.join(project_root, "config", "topics.json")
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        else:
            self.config_file = config_file
        
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
            # 如果配置文件不存在，尝试初始化默认主题词
            if not os.path.exists(self.config_file):
                logger.info(f"配置文件 {self.config_file} 不存在，初始化默认主题词")
                self._initialize_default_topics()
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
            # 如果加载失败，尝试初始化默认主题词
            self._initialize_default_topics()
            return False
    
    def _initialize_default_topics(self) -> None:
        """初始化默认主题词（基于prompt_kb.txt中的关键词）"""
        default_topics = [
            {"id": "1", "name_zh": "高性能计算", "name_en": "High Performance Computing"},
            {"id": "2", "name_zh": "并行编程", "name_en": "Parallel Programming"},
            {"id": "3", "name_zh": "代码优化技术", "name_en": "Code Optimization Techniques"},
            {"id": "4", "name_zh": "编译器优化", "name_en": "Compiler Optimization"},
            {"id": "5", "name_zh": "自动化代码生成", "name_en": "Automated Code Generation"},
            {"id": "6", "name_zh": "GPU编程与加速", "name_en": "GPU Programming and Acceleration"},
            {"id": "7", "name_zh": "内存管理优化", "name_en": "Memory Management Optimization"},
            {"id": "8", "name_zh": "异构计算架构", "name_en": "Heterogeneous Computing Architectures"},
            {"id": "9", "name_zh": "编译器中间表示优化", "name_en": "Compiler Intermediate Representation Optimization"},
            {"id": "10", "name_zh": "机器学习", "name_en": "Machine Learning"},
            {"id": "11", "name_zh": "人工智能", "name_en": "Artificial Intelligence"}
        ]
        
        # 清空现有主题词
        self.topics = {}
        self.topic_mapping = {}
        
        # 添加默认主题词
        for topic_data in default_topics:
            topic = Topic(
                id=topic_data["id"],
                name_zh=topic_data["name_zh"],
                name_en=topic_data["name_en"]
            )
            self.topics[topic.id] = topic
        
        # 保存到配置文件
        self.save_topics()
        
        logger.info(f"已初始化 {len(self.topics)} 个默认主题词")
    
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
            
            logger.info(f"成功保存 {len(self.topics)} 个主题词到 {self.config_file}")
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
        
        logger.info(f"已添加新主题词: {topic}")
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
    
    def merge_topics(self, source_id: str, target_id: str) -> bool:
        """
        合并主题词（将source合并到target）
        
        Args:
            source_id: 源主题ID
            target_id: 目标主题ID
            
        Returns:
            是否成功合并
        """
        # 检查ID是否存在
        if source_id not in self.topics:
            logger.warning(f"源主题词ID {source_id} 不存在，无法合并")
            return False
        
        if target_id not in self.topics:
            logger.warning(f"目标主题词ID {target_id} 不存在，无法合并")
            return False
        
        # 检查是否尝试合并到自身
        if source_id == target_id:
            logger.warning(f"源主题和目标主题相同 ({source_id})，无需合并")
            return False
        
        # 检查是否创建循环引用
        # 这一块可以在prompt中声明是序号靠后的主题词合并到序号靠前的主题词，所以不需要检查循环引用
        current_id = target_id
        while current_id in self.topic_mapping:
            current_id = self.topic_mapping[current_id]
            if current_id == source_id:
                logger.warning(f"检测到循环引用，无法合并 {source_id} 到 {target_id}")
                return False
        
        # 获取源主题和目标主题
        source_topic = self.topics[source_id]
        target_topic = self.topics[target_id]
        
        # 更新映射关系
        self.topic_mapping[source_id] = target_id
        
        # 更新源主题的parent_id
        source_topic.parent_id = target_id
        
        # 合并别名（去重）
        target_topic.aliases = list(set(target_topic.aliases + source_topic.aliases + [source_topic.name_zh, source_topic.name_en]))
        
        # 递归更新任何指向源主题的映射
        for old_id, new_id in list(self.topic_mapping.items()):
            if new_id == source_id:
                self.topic_mapping[old_id] = target_id
        
        # 保存更新
        self.save_topics()
        
        logger.info(f"已合并主题词 {source_id} 到 {target_id}")
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