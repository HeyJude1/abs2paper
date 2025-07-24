# abs2paper API 文档

## 核心模块 API

### MilvusManager

```python
from abs2paper.core.db_manager import MilvusManager

# 初始化
db_manager = MilvusManager(config_path=None)

# 创建集合
collection = db_manager.create_collection(section="abstract")

# 创建多个集合
db_manager.create_collections(sections=["abstract", "introduction", "conclusion"])

# 存储数据
data = {
    "section": "abstract",
    "paper_id": "paper123",
    "content": "这是论文摘要内容",
    "topics": ["机器学习", "自然语言处理"],
    "source": "paper.pdf",
    "embedding": [0.1, 0.2, ..., 0.5]  # 向量嵌入
}
db_manager.store_data(data)

# 搜索
results = db_manager.search(
    query_embedding=[0.1, 0.2, ..., 0.5],
    topic="机器学习",  # 可选
    sections=["abstract", "introduction"]  # 可选
)

# 加载所有集合到内存
db_manager.load_all_collections()

# 获取集合统计信息
stats = db_manager.get_collection_stats()
```

### EmbeddingGenerator

```python
from abs2paper.core.embedding import EmbeddingGenerator

# 初始化
embedding_generator = EmbeddingGenerator(config_path=None)

# 生成嵌入
embedding = embedding_generator.generate_embedding("这是需要向量化的文本")

# 文本分块
chunks = embedding_generator.chunk_text(
    text="这是一段很长的文本，需要分块处理...",
    paper_id="paper123"
)
```

### LLMClient

```python
from abs2paper.core.llm_client import LLMClient

# 初始化
llm_client = LLMClient(config_path=None)

# 生成响应
response = llm_client.generate_response("根据以下内容回答问题...")

# 保存提示词
llm_client.save_prompt("提示词内容", path=None)
```

## RAG 模块 API

### KnowledgeRetriever

```python
from abs2paper.rag.retriever import KnowledgeRetriever
from abs2paper.core.db_manager import MilvusManager

# 初始化
db_manager = MilvusManager()
retriever = KnowledgeRetriever(db_manager, config_path=None)

# 搜索
results = retriever.search(
    query="神经网络如何工作？",
    topic="深度学习",  # 可选
    sections=None  # 可选，默认搜索所有部分
)

# 获取用于显示的结果
display_results = retriever.get_display_results(results)

# 格式化单个结果
formatted_result = retriever.format_result(results[0])

# 格式化多个结果
formatted_results = retriever.format_results(results)
```

### ResponseGenerator

```python
from abs2paper.rag.generator import ResponseGenerator
from abs2paper.core.llm_client import LLMClient

# 初始化
llm_client = LLMClient()
generator = ResponseGenerator(llm_client, config_path=None)

# 生成回答
response = generator.generate(
    results=[...],  # 检索结果列表
    query="神经网络如何工作？"
)
```

### PromptBuilder

```python
from abs2paper.rag.prompt_builder import PromptBuilder

# 初始化
prompt_builder = PromptBuilder(config_path=None)

# 构建问答提示词
qa_prompt = prompt_builder.build_qa_prompt(
    results=[...],  # 检索结果列表
    query="神经网络如何工作？"
)

# 构建摘要提示词
summary_prompt = prompt_builder.build_summary_prompt(results=[...])

# 构建翻译提示词
translation_prompt = prompt_builder.build_translation_prompt(results=[...])

# 构建比较提示词
comparison_prompt = prompt_builder.build_comparison_prompt(
    results=[...],
    query="比较CNN和RNN的异同"
)
```

## 提取模块 API

### 文本提取

```python
from abs2paper.extraction.text import extract_text_from_pdf, extract_sections

# 从PDF提取文本
sections = extract_text_from_pdf("path/to/paper.pdf")

# 从文本提取结构化部分
sections = extract_sections("完整的文本内容")

# 清理文本
from abs2paper.extraction.text import clean_text
clean_text = clean_text("需要清理的文本")

# 提取图表信息
from abs2paper.extraction.text import extract_figures_and_tables
import fitz  # PyMuPDF
doc = fitz.open("path/to/paper.pdf")
figures_and_tables = extract_figures_and_tables(doc)
```

## 命令行工具

### RAG机器人

```bash
# 运行RAG机器人
python scripts/rag_bot.py
```

### 简单问答示例

```bash
# 运行简单问答示例
python examples/simple_qa.py
```

## 配置说明

系统配置文件位于 `config/default.json`，可以通过以下方式自定义：

1. 修改默认配置文件
2. 创建 `config/local.json` 文件进行覆盖
3. 在代码中传递自定义配置路径

配置项说明：

| 配置项 | 描述 | 默认值 |
|-------|------|--------|
| database.uri | Milvus服务器地址 | localhost:19530 |
| database.collection_prefix | 集合名称前缀 | paper_ |
| database.search_limit | 搜索返回的最大结果数 | 10 |
| database.display_limit | 显示的最大结果数 | 5 |
| embedding.model | 嵌入模型 | siliconflow |
| embedding.dimension | 嵌入维度 | 1024 |
| embedding.chunk_size | 文本分块大小 | 500 |
| embedding.chunk_overlap | 文本分块重叠大小 | 50 |
| llm.provider | LLM提供商 | siliconflow |
| llm.model | LLM模型 | mixtral-8x7b |
| llm.temperature | 温度参数 | 0.7 |
| llm.max_tokens | 最大生成token数 | 1000 |
| llm.timeout | 超时时间(秒) | 60 | 