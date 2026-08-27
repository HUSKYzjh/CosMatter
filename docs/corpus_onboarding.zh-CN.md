# 从 Zotero 到可复现评测语料：90 篇 BiFeO3 的人工审核流程

本指南用于准备 CosMatter 的首个真实评测语料。先冻结经过人工审核、权限明确、可复跑的文献集合，再让后续检索、解析、知识抽取和人工评测共享同一边界。

默认目标为约 90 篇 BiFeO3 文献。`--top-k 90` 只表示生成 90 条候选元数据，不代表已获得 90 篇有效样本；最终数量以逐条审核后的冻结清单为准。

若手头只有学校授权的 PDF 文件夹，先可选地生成**文件名导航图**，方便人工盘点而不触及全文：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe .\scripts\build_local_paper_graph.py `
  --library-root "D:\private\authorized-bifeo3-pdf" `
  --output .\runs\bfo_local_filename_inventory\ui.json --max-papers 90
```

该命令只读 PDF 文件名和第一层集合目录，并将导航 JSON 写入被 Git 忽略的 `runs/`；它不读取 PDF 正文、不会建立正式语料清单，也不能用于检索/抽取性能声明。之后仍须从 Zotero 或人工书目审核获得 DOI、实际数据库来源、授权状态和纳入理由。

## 1. 创建任务

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "Why do phase-stability reports of BiFeO3 thin films differ under bounded conditions?" `
  --material BiFeO3 --property "phase stability" --scope "epitaxial thin films" `
  --run-id bfo_90_v1 --mission-id mission_bfo_90_v1
```

同一批语料的筛选、检索、解析、人工标注和评测应使用同一 run ID。

## 2. 导出 Zotero 元数据并生成审核模板

Zotero JSON 只作为一次性本地输入。CosMatter 只读取标题、年份、DOI、标签和稳定键，不读取、保存或上传 PDF、附件路径、笔记和摘要。

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter create-corpus-selection-template-from-zotero `
  --run-id bfo_90_v1 --input "D:\private\zotero-bifeo3.json" `
  --query "BiFeO3 epitaxial thin film phase stability" `
  --corpus-id bfo_90_v1 --top-k 90
```

输出为 `runs/bfo_90_v1/corpus_selection_template.json`。这只是待审核队列，不能用于全文解析或性能声明。

## 3. 人工逐条审核

复制模板为私有 JSON 文件。核对标题、DOI、研究对象、体系范围和访问权限，然后：

1. 将 `trust_status` 改为 `human_reviewed_corpus_selection_for_manifest`；
2. 将每条 `include_for_corpus` 改为 `true` 或 `false`；
3. 为每条填写非空 `review_reason`；
4. 不修改 `document_id`、`title`、`doi` 或 `candidate_fingerprint`。

## 4. DOI 去重与跨源对齐

冻结时系统会将 DOI 规范化为统一小写形式，并拒绝重复的规范 DOI。`doi:10.x/ABC` 与 `https://doi.org/10.x/abc` 视为同一篇论文，应先在 Zotero 中合并。

无 DOI 的条目仍可用于本地人工核对与解析，但不能仅依靠 DOI 规则与 Sciverse、Sci-Base 或其他外部检索结果自动对齐。不得用标题相似度或 LLM 判断替代 DOI 映射。

## 5. 冻结语料并进入评测

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter record-corpus-manifest-from-selection-review `
  --run-id bfo_90_v1 --input "D:\private\bfo_90_selection_reviewed.json"
.\.venv\Scripts\python.exe -m cosmatter seed-authorized-corpus-candidates --run-id bfo_90_v1
.\.venv\Scripts\python.exe -m cosmatter create-gold-standard-template --run-id bfo_90_v1
.\.venv\Scripts\python.exe -m cosmatter create-bibliographic-source-template --run-id bfo_90_v1
.\.venv\Scripts\python.exe -m cosmatter create-evaluation-run-record-template --run-id bfo_90_v1
```

冻结清单仅存储文献 ID、标题、规范 DOI 和授权访问边界；不含 PDF、路径、密钥、全文或摘要。后续性能指标仅能在人工金标完成后计算。

## 数据库来源与报告逐条可追溯性

修订版手册要求每条报告主张和 Research Gap 均可回溯至具体文献，并标明所用数据库。CosMatter 对此采用两个互补字段，二者不能互相替代：

1. `PaperCandidate.source`：该书目记录实际来自哪个数据库或本地授权库，例如 `OpenAlex`、`Crossref`、`Sciverse API`、`Sci-Base` 或 `Authorized local corpus manifest`；不得填“互联网”“AI”或未说明的“本地资料”。
2. `EvidenceCard.provenance.source`：该短证据的定位来源与解析边界，例如 `authorized PDF reviewed with MinerU` 或 `institutional PDF manually reviewed`；它必须与实际处理方式一致。

LaTeX 导出会把 `PaperCandidate.source` 写入“书目来源”列，并在 `.bib` 的 `howpublished` 中保留相同来源。导出前会拒绝缺失来源的已接受证据。每个实际使用的数据库/API 还必须在 `external_resource_disclosure.json` 中独立记录访问方式、版本/访问日期、条款和再分发边界；这一披露不能被候选记录中的一个来源名称代替。

建议在私有人工审查记录中固定以下映射，再开始抽取和评测：

| 实际来源 | `source` 建议值 | 何时可写入正式报告 |
| --- | --- | --- |
| OpenAlex 元数据 | `OpenAlex` | 仅元数据、书目和引用导航；不等于全文证据 |
| Crossref 元数据 | `Crossref` | 同上，可补 DOI/参考文献标识 |
| Sciverse / Sci-Base | `Sciverse API` / `Sci-Base` | 仅在实际授权调用并披露后 |
| Zotero 指向的学校授权全文 | `Authorized local corpus manifest` | 仅在人工确认访问授权后；全文不进入提交包 |

不要因为同一篇文献在多个数据库中可见而任意切换来源名称；应保留产生该候选记录的实际检索路径，并在跨源合并时保留 DOI 对齐和去重审计。

在完成正式评测前，把运行目录内的 `bibliographic_source_registry_template.json` 复制到**运行目录之外的私有位置**，逐条将 `bibliographic_source` 从 `unreviewed` 改为实际书目数据库/来源，例如 `OpenAlex`、`Crossref`、`Sciverse API`、`Sci-Base` 或 `School-authorized library metadata`。不得填写文件路径、URL、密钥或“AI”。人工审核完成后运行：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter audit-bibliographic-source-coverage `
  --run-id bfo_90_v1 --input "D:\private\bfo_90_bibliographic_sources_reviewed.json"
```

命令仅生成 `bibliographic_source_coverage.json`：覆盖数量、不同来源数量和私有登记表哈希；不会复制每篇的标题、DOI、来源标签或全文。`submission_truth_check: completed` 要求该覆盖审计显示全部冻结文献均已人工登记书目来源。

## 人工标注覆盖审计

在开始 `evaluate-human-retrieval` 前，对保存在本地的人工金标准副本运行：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter audit-human-annotation-coverage `
  --run-id bfo_90_v1 --input "D:\private\bfo_90_human_gold_reviewed.json"
```

输出 `human_annotation_coverage.json` 只显示已审/未审相关性数量与各类注释覆盖数量，不会复制标题、DOI、标签、定位、事实或全文。仅当 90 篇的相关性均已人工复核时，检索指标门禁才会打开；材料事实、证据定位和 Gap 仍须各自完成独立人工审核。
## 冻结计数与授权边界审计

在开始任何人工金标准标注或指标计算前，先生成仅含计数与哈希的冻结就绪审计：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter audit-frozen-corpus-readiness `
  --run-id bfo_90_v1 --expected-count 90
```

该工件只记录冻结数量、文献 ID 唯一性、DOI 覆盖率、授权边界与清单哈希；不读取 PDF、全文、路径、标题或任何评测结果。只有输出 `ready_for_private_human_annotation` 后，才可以把该清单作为本地人工标注的边界；这不是已完成 90 篇评测或得到性能指标的声明。
## 常见错误

- 将 Zotero 导出、附件路径或受限 PDF 提交到仓库；
- 将 `--top-k 90` 误写为已完成 90 篇评测；
- 同时纳入同一 DOI 的多个 Zotero 记录；
- 只保留支持预期结论的文献；
- 把 Research Gap 候选当作已证实的科学发现。
