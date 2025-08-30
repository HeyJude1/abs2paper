# 论文章节总结功能说明

## 功能概述

`section_conclude.py` 是一个用于对学术论文进行10个关键方面总结的工具。它能够自动读取论文的各个章节，并使用大模型生成针对性的总结报告。

## 总结的10个方面

根据图片表格，系统会对每篇论文进行以下10个方面的总结：

| 序号 | 总结方面 | 英文名称 | 所需章节 |
|------|----------|----------|----------|
| 1 | 问题背景 | Background | 引言 |
| 2 | 相关工作 | RelatedWork | 相关工作 |
| 3 | 挑战或难点 | Challenges | 引言 + 相关工作 |
| 4 | 创新点 | Innovations | 引言 + 总结 |
| 5 | 文章方法概述 | Methodology | 方法 + 引言 |
| 6 | 实验设计思路 | ExpeDesign | 实验评价 |
| 7 | Baseline选取 | Baseline | 实验评价 + 相关工作 |
| 8 | 度量指标选取 | Metric | 实验评价 |
| 9 | 实验结果分析 | ResultAnalysis | 实验评价 + 总结 |
| 10 | 结论和展望 | Conclusion | 总结 |

## 目录结构

```
abs2paper/
├── data/
│   ├── conclude_prompt/          # 总结提示词目录
│   │   ├── Background_prompt     # 问题背景提示词
│   │   ├── RelatedWork_prompt    # 相关工作提示词
│   │   ├── Challenges_prompt     # 挑战难点提示词
│   │   ├── Innovations_prompt    # 创新点提示词
│   │   ├── Methodology_prompt    # 方法概述提示词
│   │   ├── ExpeDesign_prompt     # 实验设计提示词
│   │   ├── Baseline_prompt       # Baseline选取提示词
│   │   ├── Metric_prompt         # 度量指标提示词
│   │   ├── ResultAnalysis_prompt # 结果分析提示词
│   │   └── Conclusion_prompt     # 结论展望提示词
│   └── conclude_result/          # 总结结果输出目录
├── abs2paper/
│   ├── extraction/result/component_extract/  # 输入：论文章节文件
│   └── processing/
│       └── section_conclude.py  # 主要功能模块
└── scripts/
    └── conclude_papers.py        # 执行脚本
```

## 使用方法

### 1. 使用脚本执行

```bash
# 使用默认路径处理所有论文
python scripts/conclude_papers.py

# 使用自定义输入目录
python scripts/conclude_papers.py --input_dir /path/to/component_extract

# 使用自定义输出目录
python scripts/conclude_papers.py --output_dir /path/to/conclude_result
```

### 2. 直接调用模块

```bash
# 使用模块方式执行
python -m abs2paper.processing.section_conclude

# 带参数执行
python -m abs2paper.processing.section_conclude --input_dir /custom/path --output_dir /custom/output
```

### 3. 在代码中使用

```python
from abs2paper.processing.section_conclude import SectionConcluder

# 创建总结器实例
concluder = SectionConcluder()

# 处理所有论文
success = concluder.conclude_all_papers()

# 处理单篇论文
paper_path = "/path/to/paper/directory"
results = concluder.conclude_paper(paper_path)

# 保存结果
concluder.save_results(results, "conference/year/paper_name")
```

## 输入要求

1. **论文章节文件**: 需要事先通过 `component.py` 提取论文的各个章节
2. **文件格式**: 每个章节保存为独立的 `.txt` 文件
3. **目录结构**: 按照 `会议名/年份/论文ID/` 的格式组织

示例输入结构：
```
component_extract/
└── ICS/
    └── 2023/
        └── 3577193.3593710/
            ├── 1 INTRODUCTION.txt
            ├── 2 MOTIVATION.txt
            ├── 4 DESIGN AND IMPLEMENTATION.txt
            ├── 5 EVALUATION.txt
            ├── 6 RELATED WORK.txt
            └── 7 CONCLUSION.txt
```

## 输出结果

系统会在 `conclude_result` 目录下生成对应的总结文件：

```
conclude_result/
└── ICS/
    └── 2023/
        └── 3577193.3593710/
            ├── Background.txt        # 问题背景总结
            ├── RelatedWork.txt       # 相关工作总结
            ├── Challenges.txt        # 挑战难点总结
            ├── Innovations.txt       # 创新点总结
            ├── Methodology.txt       # 方法概述总结
            ├── ExpeDesign.txt        # 实验设计总结
            ├── Baseline.txt          # Baseline选取总结
            ├── Metric.txt            # 度量指标总结
            ├── ResultAnalysis.txt    # 结果分析总结
            ├── Conclusion.txt        # 结论展望总结
            └── summary.json          # 总结完成情况统计
```

## 关键特性

1. **智能章节匹配**: 自动将论文的实际章节标题匹配到标准的5个部分
2. **灵活的提示词系统**: 每个总结方面使用独立的提示词文件
3. **多章节组合**: 支持将多个章节内容组合用于单个方面的总结
4. **增量处理**: 自动跳过已经处理过的论文，支持断点续传
5. **详细日志**: 提供完整的处理日志和错误信息
6. **结果统计**: 生成处理完成情况的详细统计

## 配置说明

系统使用 `config/config.json` 中的以下配置：

```json
{
  "paper": {
    "chapter_mapping": {
      "introduction": "引言",
      "related work": "相关工作", 
      "methodology": "方法",
      "experiments": "实验评价",
      "conclusion": "总结"
    }
  },
  "data_paths": {
    "component_extract": {
      "path": "/abs2paper/extraction/result/component_extract"
    }
  }
}
```

## 注意事项

1. **提示词文件**: 确保 `conclude_prompt` 目录下的所有提示词文件都已正确配置
2. **LLM配置**: 确保 `config.json` 中的LLM API配置正确
3. **章节匹配**: 如果论文章节标题特殊，可能需要扩展 `chapter_mapping` 配置
4. **存储空间**: 大量论文处理会产生大量输出文件，注意存储空间

## 故障排除

1. **章节匹配失败**: 检查 `chapter_mapping` 配置，添加新的章节标题映射
2. **提示词加载失败**: 确认 `conclude_prompt` 目录下所有文件都存在且有内容
3. **LLM调用失败**: 检查API密钥和网络连接
4. **权限错误**: 确保对输出目录有写权限

## 扩展开发

要添加新的总结方面：

1. 在 `CONCLUDE_ASPECTS` 中添加新的条目
2. 在 `conclude_prompt` 目录下创建对应的提示词文件
3. 根据需要修改章节映射关系

要支持新的章节类型：

1. 在 `config.json` 的 `chapter_mapping` 中添加映射
2. 在 `CONCLUDE_ASPECTS` 中引用新的章节类型 