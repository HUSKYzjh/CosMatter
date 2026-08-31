# 私有 MinerU 文献库：从解析目录到可复跑评测语料

该流程把已获授权并私有解析的本地 Markdown 变为**人工可审核的候选清单**。它不是自动分类器，也不因为一篇文献已解析就将其视为 EvidenceCard、材料事实或评测样本。

适用的当前库为 `case-data/papers/MinerU_PrivateLibrary_20260818/private_library_catalog.json`：其中有 137 条解析完成的私有记录，两个来源组分别有 59 和 78 条；另有 1 个非 PDF 文件已跳过。所有数量只是目录盘点，不构成 BiFeO3 语料或实验结果。

## 1. 创建私有审核表

在 `CosMatter` 目录运行。输出必须放在**运行目录之外**的私有位置；不要提交至 Git。

```powershell
& .\.venv\Scripts\python.exe .\tools\private_library_review_bridge.py template `
  --catalog "..\..\case-data\papers\MinerU_PrivateLibrary_20260818\private_library_catalog.json" `
  --mission-id mission_bfo_90_v1 `
  --corpus-id bfo_90_v1 `
  --material "BiFeO3" `
  --query "BiFeO3 epitaxial thin film phase stability" `
  --output "D:\private\bfo_90_private_cohort_review.json"
```

这个表只包含文献 ID、暂定标题、来源组和 Markdown 哈希。它不含全文、摘录、绝对路径、API 密钥或 MinerU 结果 URL。

## 2. 人工审核每一条

逐条人工核对研究对象、题名、DOI、范围和学校授权边界。把审核表中的：

- `trust_status` 改为 `human_reviewed_private_library_cohort_selection`；
- 每个 `include_for_corpus`、`material_scope_match`、`access_authorized` 都改为 `true` 或 `false`；
- 每条填写非空 `review_reason`；
- 选中条目填写 `reviewed_title`；DOI 可为 `null`，但必须是人工查验后确实缺失，而非未检查。

不要改动 `document_id`、`provisional_title`、`source_group` 或 `markdown_sha256`。这一步应包含全部 137 条，不可只审核计划纳入的文献。

## 3. 冻结已审核的候选集合

```powershell
& .\.venv\Scripts\python.exe .\tools\private_library_review_bridge.py freeze `
  --catalog "..\..\case-data\papers\MinerU_PrivateLibrary_20260818\private_library_catalog.json" `
  --review "D:\private\bfo_90_private_cohort_reviewed.json" `
  --markdown-root "..\..\case-data\papers\MinerU_PrivateMarkdown_20260818" `
  --mission-id mission_bfo_90_v1 `
  --corpus-id bfo_90_v1 `
  --material "BiFeO3" `
  --query "BiFeO3 epitaxial thin film phase stability" `
  --output "D:\private\bfo_90_frozen_inputs"
```

输出：

- `corpus_selection_review.json`：无路径、可提交给 CosMatter CLI 的人工审核选择；
- `local_source_index.json`：含本机私有 Markdown 路径，仅供一次本地 BM25 查询，严禁进入 `runs/`、`ui.json`、运行包或仓库；
- `freeze_receipt.json`：只含计数与哈希的冻结回执。

工具会拒绝：未审核记录、未授权或范围不匹配的入选记录、重复 DOI、越出 Markdown 根目录的路径、缺失 Markdown，以及覆盖已有输出。

## 4. 写入任务并进行受控检索

先按 [语料入库指南](corpus_onboarding.zh-CN.md) 创建同一 `run-id` 的任务。随后：

```powershell
$env:PYTHONPATH = "src"
& .\.venv\Scripts\python.exe -m cosmatter record-corpus-manifest-from-selection-review `
  --run-id bfo_90_v1 `
  --input "D:\private\bfo_90_frozen_inputs\corpus_selection_review.json"
& .\.venv\Scripts\python.exe -m cosmatter execute-plan-local-corpus-query `
  --run-id bfo_90_v1 --query-index 0 `
  --index-path "D:\private\bfo_90_frozen_inputs\local_source_index.json"
```

最后一条命令只能在已有、已批准的本地检索计划上运行。它会在内存中读取所选 Markdown，并只把排序后的普通书目卡写入任务；不会把文本或绝对路径写入运行工件。

## 5. 证据与后续势函数任务的边界

本地检索命中只是候选文献。进入材料事实、冲突分析、Research Gap 或势函数训练计划前，仍必须从单篇私有 Markdown 中人工挑选有限来源定位，建立 Source Map，并经人工审核形成 EvidenceCard。真实 DFT、DP、MD、QMC 或势函数训练结果必须由受控外部执行记录导入；本库不能替代计算、也不能自动宣称其结果。
