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

# 为保持与extract_component.py兼容，提供简单的提取函数
def extract_text():
    """
    从PDF文件中提取文本的API函数，使用固定的默认路径和配置
    
    Returns:
        bool: 处理是否成功
    """
    try:
        # 确定项目根目录和模块目录
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(module_dir))
        
        # 加载项目配置文件(用于路径配置)
        project_config_path = os.path.join(project_root, "config", "config.json")
        if not os.path.exists(project_config_path):
            logger.error(f"项目配置文件不存在: {project_config_path}")
            return False
            
        try:
            with open(project_config_path, 'r', encoding='utf-8') as f:
                project_config = json.load(f)
                logger.info(f"已加载项目配置文件: {project_config_path}")
        except Exception as e:
            logger.error(f"读取项目配置文件失败: {str(e)}")
            return False
            
        # 获取Grobid本地配置文件路径(用于初始化GrobidClient)
        grobid_config_path = os.path.join(module_dir, "config.json")
        if not os.path.exists(grobid_config_path):
            logger.error(f"Grobid配置文件不存在: {grobid_config_path}")
            return False
            
        logger.info(f"将使用Grobid配置文件: {grobid_config_path}")
        
        # 从配置中读取路径
        data_paths = project_config["data_paths"]
        raw_papers_path = data_paths["raw_papers"]["path"].lstrip('/')
        text_extract_path = data_paths["text_extract"]["path"].lstrip('/')
        
        # 构建完整路径
        input_dir = os.path.abspath(os.path.join(project_root, raw_papers_path))
        output_dir = os.path.abspath(os.path.join(project_root, text_extract_path))
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用本地配置文件初始化Grobid客户端
        client = GrobidClient(config_path=grobid_config_path)
        
        logger.info(f"🚀 开始处理PDF文件")
        logger.info(f"📄 使用Grobid配置: {grobid_config_path}")
        
        # 读取Grobid配置以供日志输出
        try:
            with open(grobid_config_path, 'r', encoding='utf-8') as f:
                grobid_config = json.load(f)
                grobid_server = grobid_config.get('grobid_server', 'http://localhost:8070')
        except Exception:
            grobid_server = "http://localhost:8070" # 默认值
        
        # 日志输出Grobid服务器和路径信息
        logger.info(f"🖥️ GROBID服务器: {grobid_server}")
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