#!/usr/bin/env python3
"""
主题词提取工具启动器

本脚本作为主题词提取和管理的命令行入口。
所有核心功能都在abs2paper.processing.topic_extractor模块中实现。
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入相关模块
from abs2paper.utils.topic_manager import TopicManager
from abs2paper.utils.llm_client import LLMClient
from abs2paper.processing.topic_extractor import TopicExtractor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def reset_data_files():
    """重置topic.json、gen_topic.json和merge_opinion.json文件"""
    try:
        # 获取文件路径
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(module_dir, "config", "config.json")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 获取topic.json路径
        topic_json_path = config["data_paths"]["topic_json"]["path"].lstrip('/')
        topic_json_file = os.path.join(module_dir, topic_json_path)
        
        # 获取topic_ori.json路径（原始模板文件位于与topic.json同目录）
        topic_ori_file = os.path.join(os.path.dirname(topic_json_file), "topic_ori.json")
        
        # 从topic_ori.json读取初始内容
        if os.path.exists(topic_ori_file):
            with open(topic_ori_file, 'r', encoding='utf-8') as f:
                initial_topic_data = json.load(f)
                
            # 复制到topic.json
            os.makedirs(os.path.dirname(topic_json_file), exist_ok=True)
            with open(topic_json_file, 'w', encoding='utf-8') as f:
                json.dump(initial_topic_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已从{os.path.basename(topic_ori_file)}复制内容到topic.json，重置为初始状态")
        else:
            logger.warning(f"未找到模板文件{topic_ori_file}，无法重置topic.json")
            return False
        
        # 获取gen_topic.json路径
        gen_topic_path = config["data_paths"]["gen_topic_json"]["path"].lstrip('/')
        gen_topic_file = os.path.join(module_dir, gen_topic_path)
        
        # 将初始topic复制到gen_topic.json中
        gen_topic_data = {
            "topics": initial_topic_data.get("topics", {}),
            "version": "1.0.0",
            "last_updated": datetime.now().isoformat(),
            "description": "存储阶段一询问大模型生成的主题词（待处理的主题词）"
        }
        
        # 为topics中的所有主题添加status属性
        for topic_id, topic_info in gen_topic_data["topics"].items():
            topic_info["status"] = "pending"
        
        # 保存gen_topic.json
        os.makedirs(os.path.dirname(gen_topic_file), exist_ok=True)
        with open(gen_topic_file, 'w', encoding='utf-8') as f:
            json.dump(gen_topic_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"已重置gen_topic.json，复制了初始主题")
        
        # 获取merge_opinion.json路径
        merge_opinion_path = config["data_paths"]["merge_opinion"]["path"].lstrip('/')
        merge_opinion_file = os.path.join(module_dir, merge_opinion_path)
        
        # 重置merge_opinion.json
        empty_merge_opinion = {
            "merge_suggestions": [],
            "raw_response": "",
            "last_updated": datetime.now().isoformat(),
            "description": "存储大模型生成的主题词合并建议"
        }
        
        # 保存重置后的文件
        os.makedirs(os.path.dirname(merge_opinion_file), exist_ok=True)
        with open(merge_opinion_file, 'w', encoding='utf-8') as f:
            json.dump(empty_merge_opinion, f, ensure_ascii=False, indent=2)
            
        logger.info("已重置merge_opinion.json")
        return True
        
    except Exception as e:
        logger.error(f"重置数据文件失败: {e}")
        logger.exception(e)
        return False

def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="主题词提取和管理工具")
    parser.add_argument('command', nargs='?', default='full', 
                       help='执行的命令：full(默认，执行完整流程), extract, generate_merge, update_topics, list')
    parser.add_argument('--no-reset', action='store_true', 
                       help='不重置数据文件（gen_topic.json和merge_opinion.json）')
    args = parser.parse_args()
    
    try:
        # 获取项目根路径和配置
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(module_dir, "config", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 除非指定--no-reset，否则重置数据文件
        if not args.no_reset and args.command in ['full', 'extract']:
            reset_data_files()
        
        # 初始化主题管理器
        topic_manager = TopicManager()
        
        # 执行不同的命令
        if args.command == 'extract':
            # 从论文中提取主题词
            extract_from_papers(config, module_dir, topic_manager)
            
        elif args.command == 'generate_merge':
            # 生成主题合并建议
            generate_merge_suggestions(topic_manager)
            
        elif args.command == 'update_topics':
            # 根据合并建议更新主题词
            update_topics(topic_manager)
            
        elif args.command == 'list':
            # 列出所有主题词
            topic_manager.list_all_topics()
            
        elif args.command == 'full':
            # 执行完整流程
            logger.info("开始执行完整的主题提取、合并和更新流程")
            
            # 1. 从论文中提取主题词
            extract_from_papers(config, module_dir, topic_manager)
            
            # 2. 生成主题合并建议
            generate_merge_suggestions(topic_manager)
            
            # 3. 根据合并建议更新主题词
            update_topics(topic_manager)
            
            logger.info("完整的主题提取、合并建议生成和更新流程已完成！")
    
    except Exception as e:
        logger.error(f"执行命令时出错: {str(e)}")
        sys.exit(1)

def extract_from_papers(config, module_dir, topic_manager):
    """从论文中提取主题词"""
    logger.info("开始从论文中提取主题词")
    
    # 初始化LLM客户端和主题提取器
    llm_client = LLMClient()
    topic_extractor = TopicExtractor(llm_client, topic_manager)
    
    # 获取输入路径
    abstract_path = config["data_paths"]["abstract_extract"]["path"].lstrip('/')
    input_dir = os.path.join(module_dir, abstract_path)
    
    # 提取主题
    logger.info(f"开始从 {input_dir} 提取主题")
    paper_topics = topic_extractor.extract_topics_from_file(input_dir)
    logger.info(f"主题提取完成，处理了 {len(paper_topics)} 篇论文")
    
    # 不再调用update_prompt_template，避免无法找到知识库部分的错误

def generate_merge_suggestions(topic_manager):
    """生成主题合并建议"""
    logger.info("开始生成主题合并建议")
    
    # 初始化LLM客户端
    llm_client = LLMClient()
    
    # 从gen_topic.json获取所有主题的详细信息
    topic_details = []
    gen_topics = topic_manager.load_generated_topics()
    
    # 将gen_topic.json中的主题转换为topic_details格式
    for gen_id, topic_data in gen_topics.items():
        # 将生成主题的格式转换为和topic_info一致
        topic_info = {
            "id": gen_id,
            "name_zh": topic_data.get("name_zh", ""),
            "name_en": topic_data.get("name_en", ""),
            "aliases": topic_data.get("aliases", []),
            "created_at": topic_data.get("created_at", datetime.now().isoformat())
        }
        
        # 如果有原始ID，则添加
        if "original_id" in topic_data:
            topic_info["original_id"] = topic_data["original_id"]
        
        topic_details.append(topic_info)
    
    # 按创建时间排序主题
    topic_details.sort(key=lambda x: x.get('created_at', ''))
    
    logger.info(f"准备生成合并建议，共有 {len(topic_details)} 个主题")
    
    # 定义输出目录路径
    output_dir = os.path.join(
        os.path.dirname(topic_manager.merge_opinion_file), 
        "output"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存原始主题词列表到merge_ori文件
    merge_ori_path = os.path.join(output_dir, "merge_ori")
    topic_list = []
    for topic in topic_details:
        topic_list.append(f"{topic['id']}. {topic['name_zh']}，Keywords: {topic['name_en']}")
    topic_list_text = "\n".join(topic_list)
    
    with open(merge_ori_path, 'w', encoding='utf-8') as f:
        f.write(topic_list_text)
    logger.info(f"已保存原始主题词列表到 {merge_ori_path}")
    
    # 创建主题合并提示并调用LLM
    merge_prompt = topic_manager.create_merge_prompt(topic_details)
    merge_response = llm_client.get_completion(merge_prompt)
    
    # 保存LLM原始响应到指定的output目录
    merge_llm_result_path = os.path.join(output_dir, "merge_LLM_result")
    with open(merge_llm_result_path, 'w', encoding='utf-8') as f:
        f.write(merge_response)
    logger.info(f"已保存LLM原始响应到 {merge_llm_result_path}")
    
    # 保存合并建议并解析
    topic_manager.save_merge_opinion(merge_response)
    merge_suggestions = topic_manager.parse_merge_suggestions(merge_response)
    
    if merge_suggestions:
        logger.info(f"解析到 {len(merge_suggestions)} 个合并建议")
    else:
        logger.info("没有需要合并的主题")
        
def update_topics(topic_manager):
    """根据合并建议更新主题词"""
    logger.info("开始更新主题词")
    llm_client = LLMClient()
    
    # 使用一个新的功能来将gen_topic.json中的主题覆盖到topic.json
    success = topic_manager.update_topics_from_gen_topic(llm_client)
    
    if success:
        logger.info("成功更新主题词")
        topic_manager.list_all_topics()
        
        # 不再清空gen_topic.json，保留原始内容
        logger.info("保留gen_topic.json中的原始主题词")
    else:
        logger.info("没有更新主题词")


if __name__ == "__main__":
    main() 