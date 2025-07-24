# Abs2Paper

一个基于RAG(检索增强生成)的论文知识处理系统，支持论文信息提取、向量数据库存储与智能问答。

## 功能特点

- **知识提取**：自动从论文PDF中提取关键信息
  - 支持从PDF提取原始文本
  - 从文本中识别论文结构化组件（摘要、引言等章节）
  - 提取摘要、标题和关键词
  - 使用大语言模型自动标注主题
- **向量数据库**：使用Milvus进行高效的语义搜索
- **RAG问答**：基于检索到的相关内容生成精准回答
- **可扩展架构**：支持集成智能体框架

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/abs2paper.git
cd abs2paper

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 数据提取与存储

1. **论文知识提取**：

```bash
# 运行完整的提取流水线
python scripts/extract_knowledge.py --pdf_dir /path/to/pdfs --output_dir /path/to/output --api_key your_api_key
```

或分步骤运行：

```bash
# 从PDF提取原始文本
python -m abs2paper.extraction.text --input_dir /path/to/pdfs --output_dir /path/to/texts --config /path/to/config.json

# 从文本中提取结构化组件（章节）
python -m abs2paper.extraction.component --input_dir /path/to/texts --output_dir /path/to/components

# 提取摘要信息
python -m abs2paper.extraction.abstract --input_dir /path/to/texts --output_dir /path/to/abstracts

# 生成主题标签
python -m abs2paper.processing.labeling --input_dir /path/to/abstracts --output_dir /path/to/labels --api_key your_api_key
```

2. **存储到向量数据库**：

```bash
# 启动RAG机器人并选择存储功能
python scripts/rag_bot.py
```

### 问答系统

```python
from abs2paper.core.db_manager import MilvusManager
from abs2paper.rag.retriever import KnowledgeRetriever
from abs2paper.rag.generator import ResponseGenerator

# 初始化数据库管理器
db_manager = MilvusManager()

# 检索知识
retriever = KnowledgeRetriever(db_manager)
results = retriever.search("神经网络的应用")

# 生成回答
generator = ResponseGenerator()
response = generator.generate(results, "解释神经网络在医疗领域的应用")
print(response)
```

或直接使用命令行工具：

```bash
# 启动RAG机器人
python scripts/rag_bot.py

# 运行简单问答示例
python examples/simple_qa.py
```

## 项目结构

```
abs2paper/
├── config/                 # 配置文件
│   └── config.json         # 主配置文件 
├── data/                   # 数据目录
├── abs2paper/              # 核心代码包
│   ├── core/               # 核心功能
│   ├── extraction/         # 信息提取
│   │   ├── text.py         # 从PDF提取原始文本
│   │   ├── component.py    # 提取结构化组件（章节）
│   │   └── abstract.py     # 提取摘要和元数据
│   ├── processing/         # 数据处理
│   ├── rag/                # RAG功能
│   ├── agent/              # 智能体(未来)
│   ├── utils/              # 工具函数
│   └── cli/                # 命令行接口
├── scripts/                # 实用脚本
├── tests/                  # 测试代码
└── docs/                   # 文档
```

## 数据处理流程

```
PDF文档 → 文本提取(text.py) → 组件提取(component.py) → 摘要提取(abstract.py) → 主题标签 → 向量数据库 → 问答系统
```

## 许可证

MIT 