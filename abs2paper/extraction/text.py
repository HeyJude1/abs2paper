"""
文本提取模块，负责从PDF文件中提取原始文本
"""
from grobid_client.grobid_client import GrobidClient
import os
import sys
import argparse
import logging
import json

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 为保持与extract_knowledge.py兼容，提供简单的提取函数
def extract_text():
    """
    从PDF文件中提取文本的API函数，使用固定的默认路径和配置
    
    Returns:
        bool: 处理是否成功
    """
    try:
        # 确定项目根目录
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(module_dir))
        
        # 设置固定的输入输出路径
        input_dir = os.path.abspath(os.path.join(project_root, "data", "raw", "paper_kb"))
        output_dir = os.path.abspath(os.path.join(module_dir, "result", "text_extract"))
        
        # 使用固定的配置文件路径(从当前模块目录加载)
        # 原代码
        # config_path = os.path.join(project_root, "config", "config.json")
        # 新代码
        config_path = os.path.join(module_dir, "config.json")
            
        # 确保配置文件存在
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return False
            
        # 读取配置文件
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}")
            return False
            
        # 原代码
        # # 获取grobid配置
        # if 'grobid' not in config:
        #     logger.error("配置文件中缺少grobid配置部分")
        #     return False
        #     
        # # 获取grobid配置
        # grobid_config = config['grobid']
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 原代码
        # # 使用配置初始化客户端
        # client = GrobidClient(grobid_config)
        
        # 新代码 - 使用配置文件路径初始化客户端，而不是配置对象
        client = GrobidClient(config_path=config_path)
        
        logger.info(f"🚀 开始处理PDF文件")
        logger.info(f"📄 使用配置文件: {config_path}")
        
        # 新代码
        logger.info(f"🖥️ GROBID服务器: {config.get('grobid_server', 'http://localhost:8070')}")
        logger.info(f"📂 输入目录: {input_dir}")
        logger.info(f"📂 输出目录: {output_dir}")

        
        # 批量处理PDF文件
        client.process(
            service="processFulltextDocument",
            input_path=input_dir,
            output=output_dir,
            consolidate_citations=False,
            tei_coordinates=True,  # 使用坐标信息
            force=False,
            n=20,  # 使用配置中的批处理大小
            verbose=True
        )
        
        logger.info("✅ PDF处理完成")
        return True
        
    except ImportError:
        logger.error("未找到grobid_client模块。请确保已安装grobid-client-python。")
        logger.error("可通过pip install grobid-client-python安装")
        return False
    except Exception as e:
        logger.error(f"处理PDF文件时出错: {str(e)}")
        return False


def main():
    """主函数，用于单元测试和命令行运行"""
    parser = argparse.ArgumentParser(description="从PDF文件中提取文本")
    
    args = parser.parse_args()
    
    # 执行提取
    success = extract_text()
    
    # 根据执行结果设置退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 