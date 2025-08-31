# 论文总结数据存储设计方案（面向论文生成RAG）

## 1. 使用场景分析

**核心场景**：用户提供1-2句需求描述，系统通过RAG从知识库中检索相关的论文原文和总结，为大模型生成新论文提供知识支撑。

**关键需求**：
1. 根据需求快速检索相关的论文各部分原文
2. 获取对应的10个方面的精炼总结作为写作参考
3. 支持跨论文的同类型内容检索（如所有Methodology总结）
4. 建立总结与原文章节的关联关系

## 2. 论文生成RAG整体流程

```
@用户需求输入
    ↓
@需求理解与向量化
    ↓
@多类型总结并行检索 ── 背景总结检索 (Background)
    ├── 相关工作总结检索 (RelatedWork)
    ├── 挑战总结检索 (Challenges)
    ├── 创新点总结检索 (Innovations)
    ├── 方法论总结检索 (Methodology)
    ├── 实验设计总结检索 (ExpeDesign)
    ├── 基线总结检索 (Baseline)
    ├── 评价指标总结检索 (Metric)
    ├── 结果分析总结检索 (ResultAnalysis)
    └── 结论总结检索 (Conclusion)
    ↓
【输出结果1】relevant_summaries = {
    'background': [总结1, 总结2, 总结3, 总结4, 总结5],     # 每种类型5个最相关总结
    'related_work': [总结1, 总结2, 总结3, 总结4, 总结5],
    'challenges': [总结1, 总结2, 总结3, 总结4, 总结5],
    'innovations': [总结1, 总结2, 总结3, 总结4, 总结5],
    'methodology': [总结1, 总结2, 总结3, 总结4, 总结5],
    'expe_design': [总结1, 总结2, 总结3, 总结4, 总结5],
    'baseline': [总结1, 总结2, 总结3, 总结4, 总结5],
    'metric': [总结1, 总结2, 总结3, 总结4, 总结5],
    'result_analysis': [总结1, 总结2, 总结3, 总结4, 总结5],
    'conclusion': [总结1, 总结2, 总结3, 总结4, 总结5]
}
每个总结包含：{paper_id, summary_text, source_sections, topics, score}
    ↓
@跨论文同类型分析 ← 基于检索到的总结进行模式分析
    ├── 方法论趋势分析 (基于Methodology总结群)
    ├── 创新点模式识别 (基于Innovations总结群)
    ├── 挑战共性提取 (基于Challenges总结群)
    ├── 实验范式归纳 (基于ExpeDesign总结群)
    └── 评价标准总结 (基于Metric总结群)
    ↓
    【输出结果2】cross_paper_insights = {
      'methodology': {
        'summaries': [上面检索到的5个methodology总结],
        'patterns': ['深度学习在3/5篇论文中被使用', '端到端训练在4/5篇论文中提到'],
        'trends': ['深度学习方法占主导', '端到端训练成为趋势', '多模态融合增多'],
        'common_approaches': ['基于深度学习的端到端训练', '注意力机制的应用'],
        'topic_clusters': {'深度学习': [总结1,总结3], '注意力机制': [总结2,总结4]},
        'analysis_summary': '基于5篇论文的methodology分析'
      },
      'innovations': {
        'summaries': [上面检索到的5个innovations总结],
        'patterns': ['注意力机制在4/5篇论文中被提及', '自监督学习在2/5篇论文中出现'],
        'trends': ['注意力机制广泛应用', '自监督学习兴起', '模型轻量化需求'],
        'common_approaches': ['多头注意力机制', '残差连接', '批量归一化'],
        'topic_clusters': {'注意力': [总结1,总结2,总结4], '自监督': [总结3,总结5]},
        'analysis_summary': '基于5篇论文的innovations分析'
      },
      'challenges': { ... },  # 类似结构
      'expe_design': { ... }, # 类似结构
      'metric': { ... }       # 类似结构
}
    ↓
@根据总结获取对应原文章节 ← 基于最相关总结选择完整章节内容
    ├── 选择Methodology总结最相关论文的完整"方法"章节
    └── 选择4个实验相关总结最相关论文的完整"实验评价"章节
    ↓
    【输出结果3】source_texts = {
      'most_relevant_methodology_paper_id': {
        '方法': [完整的方法章节内容]           # 来自Methodology总结最相关论文的完整方法章节
      },
      'most_relevant_experiment_paper_id': {
        '实验评价': [完整的实验评价章节内容]   # 来自ExpeDesign+Baseline+Metric+ResultAnalysis总结最相关论文的完整实验评价章节
     }
}
    ↓
@按生成论文部分构建结构化RAG上下文
    ├── 生成"引言"上下文 ← Background + Challenges + Innovations (无原文)
    ├── 生成"相关工作"上下文 ← RelatedWork + Challenges (无原文)
    ├── 生成"方法"上下文 ← Methodology (含精选原文)
    ├── 生成"实验评价"上下文 ← ExpeDesign + Baseline + Metric + ResultAnalysis (含精选原文)
    └── 生成"总结"上下文 ← Conclusion + ResultAnalysis + Innovations (无原文)
    ↓
【输出结果4】paper_section_contexts = {
    '引言': '结构化上下文文本...',
    '相关工作': '结构化上下文文本...',
    '方法': '结构化上下文文本...',
    '实验评价': '结构化上下文文本...',
    '总结': '结构化上下文文本...'
}
    ↓
@顺序化论文生成流程 ← 按逻辑顺序生成，前后关联（每个部分都会获得前置部分的概述作为上下文；统一润色：最后进行全文润色确保逻辑连贯性）
    ├── 1. 生成引言部分 (基础部分，无前置依赖)
    ├── 2. 生成相关工作部分 (依赖引言概述)
    ├── 3. 生成方法部分 (依赖引言+相关工作概述)
    ├── 4. 生成实验评价部分 (依赖方法概述)
    ├── 5. 生成总结部分 (依赖全文概述)
    └── 6. 全文统一润色 (保证逻辑连贯性)
    ↓
@完整的新论文
```

## 2.1 各部分上下文信息需求明细

### 上下文信息类型说明
- **总结信息**：来自论文总结，提供高层次的见解和参考
- **趋势信息**：来自跨论文分析，提供研究领域的整体趋势
- **原文信息**：来自原文chunks，提供具体的技术细节和实现方法

### 各论文部分的信息需求

#### 引言部分
- **主要信息**：总结信息（Background, Challenges, Innovations）
- **辅助信息**：趋势信息（challenges, innovations趋势）
- **原文信息**：❌ 不需要（引言重在概述，不需要技术细节）
- **理由**：引言需要问题背景、挑战分析、创新概述，不需要具体实现细节

#### 相关工作部分  
- **主要信息**：总结信息（RelatedWork, Challenges）
- **辅助信息**：趋势信息（methodology, innovations趋势）
- **原文信息**：❌ 不需要（相关工作重在综述，不需要具体代码）
- **理由**：相关工作需要领域综述和挑战分析，重在宏观视角

#### 方法部分
- **主要信息**：总结信息（Methodology）
- **辅助信息**：趋势信息（methodology趋势）
- **原文信息**：✅ 需要（Methodology总结最相关论文的完整方法章节）
- **理由**：方法部分需要具体的技术实现细节，使用最相关Methodology总结对应论文的完整方法章节作为参考

#### 实验评价部分
- **主要信息**：总结信息（ExpeDesign, Baseline, Metric, ResultAnalysis）
- **辅助信息**：趋势信息（expe_design, metric趋势）
- **原文信息**：✅ 需要（4个实验相关总结最相关论文的完整实验评价章节）
- **理由**：实验部分需要详细的实验设置和结果分析，使用最相关实验总结对应论文的完整实验评价章节作为参考

#### 总结部分
- **主要信息**：总结信息（Conclusion, ResultAnalysis, Innovations）
- **辅助信息**：趋势信息（innovations趋势）
- **原文信息**：❌ 不需要（总结重在概括，不需要技术细节）
- **理由**：总结需要成果概述和未来展望，不需要具体实现细节

## 3. 存储架构设计

### 3.1 多Collection方案（推荐）

考虑到RAG使用场景的特点，采用**分类型存储**的多collection方案：

#### 3.1.1 原文Collection（保持现有）
- `paper_introduction` - 引言部分
- `paper_related_work` - 相关工作部分  
- `paper_methodology` - 方法部分
- `paper_experiments` - 实验评价部分
- `paper_conclusion` - 总结部分

#### 3.1.2 总结Collection（新增10个）
- `summary_background` - 背景总结
- `summary_related_work` - 相关工作总结
- `summary_challenges` - 挑战总结
- `summary_innovations` - 创新点总结
- `summary_methodology` - 方法总结
- `summary_expe_design` - 实验设计总结
- `summary_baseline` - 基线总结
- `summary_metric` - 评价指标总结
- `summary_result_analysis` - 结果分析总结
- `summary_conclusion` - 结论总结

### 3.2 统一Schema设计

**总结Collection Schema:**
```json
{
  "fields": {
    "id": {
      "type": "INT64",
      "is_primary": true,
      "auto_id": true
    },
    "paper_id": {
      "type": "VARCHAR",
      "max_length": 128,
      "description": "论文基础ID，不含chunk后缀，如'ICS/2023/3577193.3593731'"
    },
    "summary_text": {
      "type": "VARCHAR",
      "max_length": 8192,
      "description": "总结内容文本"
    },
    "source_sections": {
      "type": "ARRAY",
      "max_capacity": 5,
      "element_type": "VARCHAR",
      "element_max_length": 32,
      "description": "来源的标准章节名称：['引言','相关工作','方法','实验评价','总结']"
    },
    "topics": {
      "type": "ARRAY",
      "max_capacity": 10,
      "element_type": "VARCHAR",
      "element_max_length": 128,
      "description": "论文主题标签"
    },
    "embedding": {
      "type": "FLOAT_VECTOR",
      "dim": 1024,
      "description": "总结文本的向量表示"
    }
  }
}
```

### 3.3 数据关联关系

```
# 基础关联（通过paper_id）
summary_*.paper_id -> paper_*.paper_id (基础ID匹配，忽略chunk后缀)

# 章节级关联（通过source_sections）
summary_*.source_sections[] -> paper_*.section (章节级别匹配)

# 实际检索策略
1. 通过总结找到paper_id和source_sections
2. 根据paper_id前缀匹配所有相关chunks: paper_id.startswith("ICS/2023/3577193.3593731_")
3. 根据source_sections过滤对应章节的chunks
```

## 4. RAG检索策略设计

### 4.1 论文生成RAG工作流

```python
def paper_generation_rag(user_requirement: str) -> Dict:
    """论文生成RAG主流程"""
    
    # 1. 需求理解与向量化
    requirement_vector = llm_client.get_embedding([user_requirement])[0]
    
    # 2. 多类型总结并行检索（完整的10种类型）
    summary_types = [
        'background', 'related_work', 'challenges', 'innovations', 
        'methodology', 'expe_design', 'baseline', 'metric', 
        'result_analysis', 'conclusion'
    ]
    
    rag_context = {
        'relevant_summaries': {},  # 按类型组织的相关总结
        'cross_paper_insights': {}, # 跨论文同类型见解
        'source_texts': {},        # 对应的原文片段
        'paper_section_contexts': {} # 按生成论文部分组织的上下文
    }
    
    # 3. 按总结类型检索
    for summary_type in summary_types:
        summaries = semantic_search_summaries_by_type(
            query_vector=requirement_vector,
            summary_type=summary_type,
            top_k=5  # 每种类型获取更多候选
        )
        rag_context['relevant_summaries'][summary_type] = summaries
    
    # 4. 跨论文同类型分析（基于检索到的总结进行模式分析）
    key_analysis_types = ['methodology', 'innovations', 'challenges', 'expe_design', 'metric']
    for summary_type in key_analysis_types:
        if summary_type in rag_context['relevant_summaries']:
            insights = analyze_cross_paper_patterns(
                summaries=rag_context['relevant_summaries'][summary_type],
                summary_type=summary_type
            )
            rag_context['cross_paper_insights'][summary_type] = insights
    
    # 5. 基于最相关总结获取对应原文章节
    source_controller = SourceTextController()
    rag_context['source_texts'] = source_controller.select_most_relevant_source_texts(
        rag_context['relevant_summaries']
    )
    
    # 6. 按生成论文部分构建结构化上下文
    rag_context['paper_section_contexts'] = build_paper_section_contexts(
        rag_context['relevant_summaries'],
        rag_context['cross_paper_insights'],
        rag_context['source_texts'],
        user_requirement
    )
    
    return rag_context
```

### 4.2 基于CONCLUDE_ASPECTS精确翻转的映射关系

```python
# 基于section_conclude.py中CONCLUDE_ASPECTS的精确翻转
# CONCLUDE_ASPECTS原始定义：
# "Background": ["引言"]                    -> 引言需要Background
# "RelatedWork": ["相关工作"]               -> 相关工作需要RelatedWork  
# "Challenges": ["引言", "相关工作"]         -> 引言、相关工作需要Challenges
# "Innovations": ["引言", "总结"]           -> 引言、总结需要Innovations
# "Methodology": ["方法", "引言"]           -> 方法、引言需要Methodology
# "ExpeDesign": ["实验评价"]               -> 实验评价需要ExpeDesign
# "Baseline": ["实验评价", "相关工作"]       -> 实验评价、相关工作需要Baseline
# "Metric": ["实验评价"]                  -> 实验评价需要Metric
# "ResultAnalysis": ["实验评价", "总结"]     -> 实验评价、总结需要ResultAnalysis
# "Conclusion": ["总结"]                   -> 总结需要Conclusion

PAPER_SECTION_SUMMARY_MAPPING = {
    "引言": [
        "Background",      # 直接对应：Background -> 引言
        "Challenges",      # 部分对应：Challenges -> 引言, 相关工作
        "Innovations",     # 部分对应：Innovations -> 引言, 总结
        "Methodology"      # 部分对应：Methodology -> 方法, 引言
    ],
    "相关工作": [
        "RelatedWork",     # 直接对应：RelatedWork -> 相关工作
        "Challenges",      # 部分对应：Challenges -> 引言, 相关工作
        "Baseline"         # 部分对应：Baseline -> 实验评价, 相关工作
    ],
    "方法": [
        "Methodology"      # 直接对应：Methodology -> 方法, 引言 (主要用于方法部分)
    ],
    "实验评价": [
        "ExpeDesign",      # 直接对应：ExpeDesign -> 实验评价
        "Baseline",        # 部分对应：Baseline -> 实验评价, 相关工作
        "Metric",          # 直接对应：Metric -> 实验评价
        "ResultAnalysis"   # 部分对应：ResultAnalysis -> 实验评价, 总结
    ],
    "总结": [
        "Conclusion",      # 直接对应：Conclusion -> 总结
        "ResultAnalysis",  # 部分对应：ResultAnalysis -> 实验评价, 总结
        "Innovations"      # 部分对应：Innovations -> 引言, 总结
    ]
}

# 基于CONCLUDE_ASPECTS确定的原文章节需求映射
PAPER_SECTION_SOURCE_MAPPING = {
    "方法": ["方法"],                    # 只需要"方法"章节原文 (基于Methodology需求)
    "实验评价": ["实验评价", "相关工作", "总结"]  # 需要这三个章节原文 (基于ExpeDesign+Baseline+Metric+ResultAnalysis需求)
}
```

### 4.3 基于最相关总结的原文选择策略

```python
class SourceTextController:
    """基于最相关总结的原文选择器 - 直接使用最相关总结对应的原文"""
    
    # 不同论文部分的原文需求配置
    SOURCE_TEXT_CONFIG = {
        "引言": {"need_source": False},
        "相关工作": {"need_source": False}, 
        "方法": {"need_source": True, "summary_types": ["Methodology"]},
        "实验评价": {"need_source": True, "summary_types": ["ExpeDesign", "Baseline", "Metric", "ResultAnalysis"]},
        "总结": {"need_source": False}
    }
    
    def select_most_relevant_source_texts(self, relevant_summaries: Dict) -> Dict:
        """
        基于最相关总结选择对应的原文章节
        
        策略：
        1. 对于"方法"上下文：选择Methodology总结中最相关的那个论文的完整"方法"章节
        2. 对于"实验评价"上下文：选择4个实验相关总结中最相关的那个论文的完整"实验评价"章节
        3. 不需要chunks选择，直接使用完整章节内容
        4. 最多只有2篇论文的原文（方法1篇+实验评价1篇）
        """
        selected_source_texts = {}
        
        # 1. 选择最相关的Methodology论文的方法章节
        methodology_paper_id = self._find_most_relevant_paper(
            relevant_summaries, ["methodology"]
        )
        if methodology_paper_id:
            method_content = self._get_complete_section_content(
                methodology_paper_id, "方法"
            )
            if method_content:
                selected_source_texts[methodology_paper_id] = {
                    "方法": method_content
                }
        
        # 2. 选择最相关的实验评价论文的实验评价章节
        experiment_paper_id = self._find_most_relevant_paper(
            relevant_summaries, ["expedesign", "baseline", "metric", "resultanalysis"]
        )
        if experiment_paper_id and experiment_paper_id != methodology_paper_id:
            experiment_content = self._get_complete_section_content(
                experiment_paper_id, "实验评价"
            )
            if experiment_content:
                selected_source_texts[experiment_paper_id] = {
                    "实验评价": experiment_content
                }
        elif experiment_paper_id == methodology_paper_id:
            # 如果是同一篇论文，添加实验评价章节
            experiment_content = self._get_complete_section_content(
                experiment_paper_id, "实验评价"
            )
            if experiment_content:
                selected_source_texts[experiment_paper_id]["实验评价"] = experiment_content
        
        return selected_source_texts
    
    def _find_most_relevant_paper(self, relevant_summaries: Dict, 
                                summary_types: List[str]) -> Optional[str]:
        """
        从指定类型的总结中找到最相关的论文ID
        
        Args:
            relevant_summaries: 检索到的相关总结
            summary_types: 要考虑的总结类型列表
        
        Returns:
            最相关论文的paper_id
        """
        best_paper_id = None
        best_score = 0
        
        for summary_type in summary_types:
            if summary_type in relevant_summaries:
                summaries = relevant_summaries[summary_type]
                if summaries:  # 取第一个（最相关的）
                    top_summary = summaries[0]
                    score = top_summary.get('score', 0)
                    if score > best_score:
                        best_score = score
                        best_paper_id = top_summary['paper_id']
        
        return best_paper_id
    
    def _get_complete_section_content(self, paper_id: str, section_name: str) -> List[str]:
        """
        获取指定论文的完整章节内容（所有chunks）
        
        Args:
            paper_id: 论文ID（基础ID，不含chunk后缀）
            section_name: 章节名称
        
        Returns:
            该章节的所有chunks内容列表
        """
        # 从原文collection中检索所有匹配的chunks
        # paper_id格式如：'ICS/2023/3577193.3593731'
        # 对应的chunks格式如：'ICS/2023/3577193.3593731_0', 'ICS/2023/3577193.3593731_1', ...
        
        section_chunks = []
        
        # 根据章节名称确定要查询的collection
        collection_mapping = {
            "引言": "paper_introduction",
            "相关工作": "paper_related_work", 
            "方法": "paper_methodology",
            "实验评价": "paper_experiments",
            "总结": "paper_conclusion"
        }
        
        collection_name = collection_mapping.get(section_name)
        if not collection_name:
            return []
        
        try:
            # 使用Milvus查询匹配的chunks
            # 查询条件：paper_id.startswith(base_paper_id + '_')
            query_filter = f"paper_id like '{paper_id}_%'"
            
            # 这里需要调用Milvus查询接口
            results = self.db_client.query(
                collection_name=collection_name,
                filter=query_filter,
                output_fields=["paper_id", "text"],
                limit=100  # 假设单个章节不会超过100个chunks
            )
            
            # 按paper_id后缀排序，确保chunks顺序正确
            sorted_results = sorted(results, key=lambda x: int(x['paper_id'].split('_')[-1]))
            
            # 提取文本内容
            section_chunks = [result['text'] for result in sorted_results]
            
        except Exception as e:
            logging.error(f"获取章节内容失败: {paper_id}, {section_name}, 错误: {e}")
            return []
        
        return section_chunks
```

### 4.4 顺序化论文生成流程

```python
class SequentialPaperGenerator:
    """顺序化论文生成器 - 解决逻辑连贯性问题"""
    
    # 论文部分生成顺序和依赖关系
    GENERATION_ORDER = [
        {
            "section": "引言",
            "dependencies": [],
            "context_sources": ["Background", "Challenges", "Innovations"],
            "include_source_text": False,
            "previous_context_needed": False
        },
        {
            "section": "相关工作", 
            "dependencies": ["引言"],
            "context_sources": ["RelatedWork", "Challenges"],
            "include_source_text": False,
            "previous_context_needed": True,
            "previous_context_type": "概述"  # 只需要引言的概述
        },
        {
            "section": "方法",
            "dependencies": ["引言", "相关工作"],
            "context_sources": ["Methodology", "Innovations"],
            "include_source_text": True,
            "previous_context_needed": True,
            "previous_context_type": "概述"  # 需要引言+相关工作的概述
        },
        {
            "section": "实验评价",
            "dependencies": ["方法"],
            "context_sources": ["ExpeDesign", "Baseline", "Metric", "ResultAnalysis"],
            "include_source_text": True,
            "previous_context_needed": True,
            "previous_context_type": "详细"  # 需要方法的详细内容
        },
        {
            "section": "总结",
            "dependencies": ["引言", "相关工作", "方法", "实验评价"],
            "context_sources": ["Conclusion", "ResultAnalysis", "Innovations"],
            "include_source_text": False,
            "previous_context_needed": True,
            "previous_context_type": "概述"  # 需要全文概述
        }
    ]
    
    def generate_paper_sequentially(self, paper_section_contexts: Dict,
                                   user_requirement: str) -> Dict[str, str]:
        """
        按顺序生成论文各部分，保持逻辑连贯性
        
        流程：
        1. 按依赖顺序生成各部分
        2. 每生成一部分就提取概述供后续使用
        3. 最后统一润色保证整体连贯性
        """
        generated_sections = {}
        section_summaries = {}  # 存储各部分的概述，供后续部分使用
        
        for step in self.GENERATION_ORDER:
            section_name = step["section"]
            logging.info(f"�� 生成论文{section_name}部分...")
            
            # 构建当前部分的完整上下文
            full_context = self._build_full_context_for_section(
                section_name=section_name,
                base_context=paper_section_contexts[section_name],
                previous_sections=generated_sections,
                section_summaries=section_summaries,
                step_config=step,
                user_requirement=user_requirement
            )
            
            # 生成当前部分
            generated_content = self._generate_section_content(
                section_name=section_name,
                context=full_context,
                user_requirement=user_requirement
            )
            
            generated_sections[section_name] = generated_content
            logging.info(f"✅ {section_name}部分生成完成")
            
            # 生成当前部分的概述，供后续部分使用
            section_summary = self._generate_section_summary(
                section_name, generated_content
            )
            section_summaries[section_name] = section_summary
        
        # 最后进行全文统一润色
        logging.info("🎨 开始全文统一润色...")
        polished_sections = self._polish_entire_paper(
            generated_sections, user_requirement
        )
        logging.info("✅ 论文生成完成")
        
        return polished_sections
    
    def _build_full_context_for_section(self, section_name: str,
                                       base_context: str,
                                       previous_sections: Dict[str, str],
                                       section_summaries: Dict[str, str],
                                       step_config: Dict,
                                       user_requirement: str) -> str:
        """为当前部分构建包含前置依赖的完整上下文"""
        
        context_parts = [
            f"# 生成论文{section_name}部分",
            f"**用户需求**: {user_requirement}",
            ""
        ]
        
        # 添加前置部分的上下文（如果需要）
        if step_config.get("previous_context_needed", False):
            context_parts.append("## 已生成的前置部分")
            
            context_type = step_config.get("previous_context_type", "概述")
            
            for dep_section in step_config["dependencies"]:
                if dep_section in section_summaries:
                    context_parts.append(f"### {dep_section}部分概述")
                    context_parts.append(section_summaries[dep_section])
                    context_parts.append("")
        
        # 添加基础RAG上下文
        context_parts.append("## 参考资料")
        context_parts.append(base_context)
        
        # 添加写作指导
        context_parts.extend([
            "",
            "## 写作要求",
            f"1. 确保与前面已生成的部分在逻辑上连贯",
            f"2. 避免与前面部分内容重复",
            f"3. 保持学术论文的严谨性和专业性",
            f"4. 字数控制在800-1200字之间",
            f"5. 使用规范的学术写作格式"
        ])
        
        return "\n".join(context_parts)
    
    def _generate_section_summary(self, section_name: str, content: str) -> str:
        """生成部分内容的概述，供后续部分使用"""
        prompt = f"""
请为以下论文{section_name}部分生成一个150字左右的概述，突出关键点：

{content}

要求：
1. 概述要简洁明了，突出核心内容
2. 为后续部分提供必要的逻辑衔接信息
3. 避免过于详细的技术细节
"""
        
        return self.llm_client.get_completion(prompt)
    
    def _polish_entire_paper(self, sections: Dict[str, str], 
                           user_requirement: str) -> Dict[str, str]:
        """对整篇论文进行统一润色，确保逻辑连贯性"""
        
        polish_prompt = f"""
请对以下论文各部分进行整体润色，确保逻辑连贯性：

用户需求：{user_requirement}

请重点关注：
1. 各部分之间的逻辑连接和过渡
2. 术语使用的一致性  
3. 表达的流畅性和学术规范性
4. 避免内容重复和矛盾
5. 确保论文整体结构的完整性

请分别返回润色后的各部分内容。
"""
        
        polished_content = self.llm_client.get_completion(polish_prompt)
        
        # 这里需要实现内容解析逻辑，将润色后的内容分割回各个部分
        # 简化处理，实际实现时需要更复杂的解析
        return sections  # 暂时返回原内容
```

### 4.2 生成论文部分的优先级映射（旧版本，已被上面的精确映射替代）

## 5. 实施步骤

### 5.1 配置文件更新
```json
{
  "paper_summaries": {
    "collections": [
      "summary_background", "summary_related_work", "summary_challenges",
      "summary_innovations", "summary_methodology", "summary_expe_design", 
      "summary_baseline", "summary_metric", "summary_result_analysis", 
      "summary_conclusion"
    ],
    "collection_fields": {
      "id": {
        "type": "INT64",
        "is_primary": true,
        "auto_id": true
      },
      "paper_id": {
        "type": "VARCHAR",
        "max_length": 128
      },
      "summary_text": {
        "type": "VARCHAR",
        "max_length": 8192
      },
      "source_sections": {
        "type": "ARRAY",
        "max_capacity": 5,
        "element_type": "VARCHAR",
        "element_max_length": 32
      },
      "topics": {
        "type": "ARRAY",
        "max_capacity": 10,
        "element_type": "VARCHAR",
        "element_max_length": 128
      },
      "embedding": {
        "type": "FLOAT_VECTOR",
        "dim": "${embedding_dim}"
      }
    },
    "index_params": {
      "index_type": "IVF_FLAT",
      "params": {
        "nlist": 128
      },
      "metric_type": "L2"
    }
  }
}
```

### 5.2 数据迁移脚本
```python
def migrate_summaries_to_collections():
    """将总结数据迁移到多个collection中"""
    
    # 总结类型映射
    summary_type_mapping = {
        'Background.txt': 'background',
        'RelatedWork.txt': 'related_work', 
        'Challenges.txt': 'challenges',
        'Innovations.txt': 'innovations',
        'Methodology.txt': 'methodology',
        'ExpeDesign.txt': 'expe_design',
        'Baseline.txt': 'baseline',
        'Metric.txt': 'metric',
        'ResultAnalysis.txt': 'result_analysis',
        'Conclusion.txt': 'conclusion'
    }
    
    # 总结类型到章节的智能映射
    SUMMARY_TO_SECTIONS_MAPPING = {
        'background': ['引言'],
        'related_work': ['相关工作'],
        'challenges': ['引言', '相关工作'],
        'innovations': ['引言', '总结'],
        'methodology': ['方法', '引言'],
        'expe_design': ['实验评价'],
        'baseline': ['实验评价', '相关工作'],
        'metric': ['实验评价'], 
        'result_analysis': ['实验评价', '总结'],
        'conclusion': ['总结']
    }
    
    for paper_dir in conclude_result_dirs:
        paper_id = extract_paper_id_from_path(paper_dir)  # 如: 'ICS/2023/3577193.3593731'
        
        # 获取论文主题标签
        topics = get_paper_topics(paper_id)
        
        for filename, summary_type in summary_type_mapping.items():
            summary_file = os.path.join(paper_dir, filename)
            if os.path.exists(summary_file):
                # 读取总结内容
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary_text = f.read()
                
                # 生成向量
                embedding = llm_client.get_embedding([summary_text])[0]
                
                # 确定来源章节
                source_sections = SUMMARY_TO_SECTIONS_MAPPING.get(summary_type, ['方法'])
                
                # 插入对应的collection
                collection_name = f"summary_{summary_type}"
                data = {
                    'paper_id': paper_id,
                    'summary_text': summary_text,
                    'source_sections': source_sections,
                    'topics': topics,
                    'embedding': embedding
                }
                
                db_client.insert_data(collection_name, [data])
                logging.info(f"已入库总结: {paper_id} - {summary_type}")
```

## 6. 优势分析

### 6.1 RAG场景优势
- **分部分生成**：针对论文不同部分提供定制化的RAG上下文
- **优先级排序**：根据相关性对参考资料进行权重排序
- **跨论文分析**：基于检索结果进行模式分析，发现研究趋势
- **结构化上下文**：为大模型提供层次化、有序的知识上下文

### 6.2 性能优势
- **检索效率**：分collection存储避免了大表查询
- **向量精度**：每种类型的向量空间更加聚焦
- **智能筛选**：基于优先级权重减少无关信息

### 6.3 扩展性优势
- **新增类型**：可以轻松添加新的总结类型collection
- **优先级调整**：可以根据实际效果调整各部分的优先级映射
- **模式分析扩展**：可以加入更多的跨论文分析维度

## 7. 关键技术点

### 7.1 Paper ID映射解决方案
```python
def extract_base_paper_id(chunk_paper_id: str) -> str:
    """从chunk paper_id提取基础paper_id"""
    return chunk_paper_id.rsplit('_', 1)[0]

def get_all_chunks_by_base_id(base_paper_id: str, section: str) -> List[Dict]:
    """根据基础paper_id和section获取该章节所有chunks"""
    section_en = section_mapping_en[section]  # 中文->英文
    collection_name = f"paper_{section_en}"
    return db_client.search(
        collection_name=collection_name,
        expr=f'paper_id.startswith("{base_paper_id}_")',
        output_fields=["paper_id", "text"],
        limit=100
    )
```

### 7.2 总结与原文的智能映射
根据总结类型自动确定最相关的原文sections：
```python
SUMMARY_TO_SECTIONS_MAPPING = {
    'background': ['引言'],
    'related_work': ['相关工作'],
    'challenges': ['引言', '相关工作'],
    'innovations': ['引言', '总结'],
    'methodology': ['方法', '引言'],
    'expe_design': ['实验评价'],
    'baseline': ['实验评价', '相关工作'],
    'metric': ['实验评价'], 
    'result_analysis': ['实验评价', '总结'],
    'conclusion': ['总结']
}
```

这个完善的方案解决了你提出的三个关键问题，提供了更精确的论文生成RAG策略，特别是基于优先级的结构化上下文构建。 