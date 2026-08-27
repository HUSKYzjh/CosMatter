## Local Zotero metadata retrieval

Pass an explicit Zotero JSON export. The command reads only title, date, DOI and tags for ranking; it ignores abstracts, notes, attachment paths and PDF contents. Results use the normal candidate artifact but remain content-inaccessible, so they cannot bypass the source-map review gate.

    python -m cosmatter local-zotero-search --input C:\\path\\zotero-export.json --query BiFeO3 --top-k 20 --run-id bfo_local_baseline


## Frozen end-to-end agent benchmark

Use the explicitly synthetic fixture to regression-test the actual local retrieval ranker, reviewed fact contract, locator linkage, condition differential, and evidence-bound Research Gap generator:

    python -m cosmatter evaluate-agent-benchmark --fixture .\examples\frozen\bfo_agent_benchmark.json --run-id benchmark_001

The resulting `agent_benchmark.json` contains Precision@K, Recall@K, nDCG@K, reviewed-fact ID recall, locator accuracy, Gap evidence-boundary precision, and differing-field recall. These values are fixture-regression results only; they are not claims about the planned 90-paper corpus, external API quality, or scientific correctness.

## Structured research report

`build-report` now writes two local artifacts: the compact, browser-safe `mission_report.json` and `research_report.md`. The Markdown report is a review-gated work product: it lists accepted EvidenceCard IDs with document locators and conditions, reviewed material facts, comparison boundaries, and candidate Research Gaps. It does not expose full text, credentials, raw provider responses, or an autonomous scientific conclusion.

    python -m cosmatter build-report --run-id bfo_live_001

Review `research_report.md` alongside the cited source locators before sharing it outside the authorized local workspace.

## Multi-document material-fact fusion

Document-scoped source maps and material facts are stored by a SHA-256 filename derived from `document_id`; the original single-file artifacts remain readable for existing runs. After recording facts for more than one document, compare them with:

    python -m cosmatter fuse-material-facts --run-id bfo_live_001

The resulting `material_fact_fusion.json` groups facts by category, normalized field name, and normalized unit. A disagreement is flagged only when reported qualifier fields match; differing qualifiers yield `not_directly_comparable_differing_qualifiers`, not a scientific contradiction. All comparison outputs remain review artifacts, never autonomous conclusions or Research Gap approvals.

## Reviewed material facts

After a MinerU task is marked `done`, first run `audit-source-parse-receipts` and confirm that the task, document, source-URL digest, and final task state match hash-only MinerU receipts. Workflow readiness treats an unlinked or stale parse receipt as blocked. Then record a reviewer-selected source map. `draft-material-extraction` sends only those short excerpts to DeepSeek, and only after an explicit command. Its output is an untrusted local draft; it cannot enter an EvidenceCard, report conclusion, or browser bundle.

    python -m cosmatter draft-material-extraction --run-id bfo_live_001
    python -m cosmatter record-material-facts --run-id bfo_live_001 --input .\reviewed_material_facts.json

The reviewed JSON must reference the existing `document_id` and `segment_id` values. Each fact has one of six categories: `composition`, `structure`, `property`, `processing`, `experimental_condition`, or `simulation_method`; it carries reported and normalized value/unit fields plus scalar qualifiers. The persisted fact includes its source locator and a source-quote hash, not the quote itself. Invalid segment IDs, unsupported categories, nested qualifier payloads, and oversized selections are rejected.

## Evidence-bound Research Gap delivery

A Research Gap candidate is never a free-form finding. Generate it only after the run contains an accepted condition matrix, accepted verification decisions, and at least two accepted evidence cards with explicit differing condition fields. The sequence below keeps the candidate, report, and browser projection bound to the same accepted evidence set.

    python -m cosmatter generate-gap-candidates --run-id bfo_live_001
    python -m cosmatter build-report --run-id bfo_live_001
    python -m cosmatter audit-report-evidence --run-id bfo_live_001
    python -m cosmatter export-ui --run-id bfo_live_001

`generate-gap-candidates` writes `research_gap_candidates.json`. Every item remains `candidate_requires_human_review`, contains its evidence IDs, recorded conflict fields, a falsifiable hypothesis, and suggested validation. A persisted candidate also requires an executed counterevidence boundary. `build-report` loads this artifact when present and refuses a candidate that is not review-bound or that cites evidence outside the report's accepted evidence set. `audit-report-evidence` must run after report generation: workflow readiness marks the report complete only when its current audit proves the rendered document IDs, locators, fact references, comparisons, and Gap counterevidence boundaries. `export-ui` projects the resulting aggregate audit state to the Research Extension page without initiating a new mission, retrieval, or model call.

If no explicit accepted conflict exists, candidate generation fails instead of inventing a research direction. A report can still be built from accepted evidence alone; it will simply contain no Research Gap candidate IDs.

# CosMatter 受控运行手册

本手册描述从研究问题到可导入 UI 的本地工件流。所有命令均在
`CosMatter/` 目录、虚拟环境中运行。密钥只保存在上级项目根目录的 `../.env`（即`AIforResearch-材料科学Agent/.env`），该文件受保护、只读且不提交；不要把密钥、受限全文或浏览器凭据写进任何 JSON 工件。字段名见上级目录的 `../env.txt`。

## 0. 配置检查

```powershell
.\.venv\Scripts\python.exe -m cosmatter check-config
```

只有 `deepseek_configured` 和/或 `sciverse_configured` 为 `true` 时才会调用对应
服务。没有密钥时，冻结测试、UI 演示和所有本地门禁仍可运行。

## 1. 建立同一任务的身份与舰队

`create-mission` 和 `assign-fleet` 必须共享 `--run-id` 与 `--mission-id`：

```powershell
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "Why can phase reports differ across conditions?" `
  --material BiFeO3 --property "phase stability" --scope "epitaxial films" `
  --run-id bfo_live_001 --mission-id mission_bfo_live_001

.\.venv\Scripts\python.exe -m cosmatter assign-fleet `
  --question "Why can phase reports differ across conditions?" `
  --material BiFeO3 --property "phase stability" --scope "epitaxial films" `
  --run-id bfo_live_001 --mission-id mission_bfo_live_001
```

## 2. 生成草稿、人工审核并批准计划

有 DeepSeek 密钥时，草稿命令只生成 `research_plan_draft.json`，其内容不会自动
被执行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter draft-plan --run-id bfo_live_001
```

人工审核后，创建一个独立 JSON 文件，例如 `reviewed_plan.json`：

```json
{
  "subquestions": ["Which conditions differ?"],
  "queries": ["BiFeO3 epitaxial strain phase stability"],
  "counter_queries": ["BiFeO3 epitaxial phase contradictory thickness substrate"]
}
```

批准命令会检查上限（最多 5 个子问题、8 个查询、4 个反例查询、3 轮、20 篇候选）：

```powershell
.\.venv\Scripts\python.exe -m cosmatter approve-plan `
  --run-id bfo_live_001 --input .\reviewed_plan.json
```

此步写入 `flight_plan.json`；它才是可执行计划。

## 3. 从批准计划执行有界检索

有 Sciverse token 时，按查询索引执行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter execute-plan-query `
  --run-id bfo_live_001 --query-index 0

# 对批准计划中的反例查询使用同一受控通道
.\.venv\Scripts\python.exe -m cosmatter execute-plan-query `
  --run-id bfo_live_001 --query-index 0 --counter
```

两类检索均只接受已批准计划中的索引；审计记录查询类别与索引，不回显查询文本。该命令只保存 `retrieval_candidates.json` 中的元数据卡，不保存 API 原始响应、摘要或
全文。候选必须标记为可访问，后续才能作为证据来源。

在一个或多个批准查询已有候选后，可生成不含查询文本和评分的有界阅读路线：

```powershell
.\.venv\Scripts\python.exe -m cosmatter build-reading-guide --run-id bfo_live_001
```

## 4. 录入可定位证据并生成交付物

证据草稿由已获授权的内容提取流程产生，至少含有 `claim`、`stance`、材料、性质、
短摘录、`document_id + locator`、条件字段及 `evidence_id`。它必须来自本运行内可
访问的候选：

```powershell
.\.venv\Scripts\python.exe -m cosmatter ingest-evidence `
  --run-id bfo_live_001 --input .\evidence_draft.json

.\.venv\Scripts\python.exe -m cosmatter build-report --run-id bfo_live_001
.\.venv\Scripts\python.exe -m cosmatter export-ui --run-id bfo_live_001
```

`ingest-evidence` 会写入证据卡及不可变审核决策。`build-report` 仅使用已接受的证据
ID 生成清单式报告；`export-ui` 只投影许可范围内的短摘录与报告摘要。

## 5. 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m cosmatter evaluate-fixture `
  --fixture .\examples\frozen\bfo_route_diagnostics.json --run-id frozen_eval_001
```

`runs/` 是本地运行数据，已被 Git 忽略。提交前确认其中没有被误加入暂存区。

## Evidence-quality human review

Use an independent reviewer to check the current accepted EvidenceCards without
copying paper text into the assessment. The following commands create a narrow
template and write only aggregate metrics back to the run:

    python -m cosmatter create-evidence-quality-review-template --run-id bfo_live_001
    python -m cosmatter evaluate-human-evidence-quality --run-id bfo_live_001 --input .\reviewed_evidence_quality.json

The input must retain the exact current evidence IDs, document IDs, locators and
predicted stances. For every evidence item, record citation/locator correctness
and condition completeness; for a predicted contradiction, also record whether
the contradiction label is correct. The persisted result reports only evidence
count, predicted-contradiction count, citation precision, condition completeness
and contradiction precision. It contains no paper text, quote, reviewer identity
or per-item decision.

## Approved local parsed-corpus retrieval

Use the same approved Flight Plan query list for a reviewer-selected local
Markdown corpus (for example, a permitted Sci-Base subset that has been parsed
and reviewed locally). This route requires a recorded authorized corpus manifest
and a transient path-bearing index; the index and Markdown text never enter the
run artifacts.

    python -m cosmatter execute-plan-local-corpus-query --run-id bfo_live_001 --index .\private_local_index.json --query-index 0
    python -m cosmatter execute-plan-local-corpus-query --run-id bfo_live_001 --index .\private_local_index.json --query-index 0 --counter

The command accepts only an index into the already approved primary or
counterevidence query list, uses the plan's paper limit, appends metadata-only
candidates to the same retrieval history as Sciverse, and records query kind,
index, count, and the local-source boundary in the audit log. It does not invent
an external API receipt for local work. This makes hybrid retrieval comparable
while preserving the distinction between a local authorized corpus baseline and
external Sciverse coverage.

## Workflow readiness and evaluation gates

`audit-workflow-readiness` now has a final `evaluation` stage. It does not make
a scientific or quality claim; it reports which human-reviewed metric families
are applicable to the current artifacts and whether their aggregate result files
are valid. An accepted-evidence set requires the evidence-quality review; a
recorded authorized corpus plus completed retrieval requires retrieval review;
reviewed facts and Gap candidates respectively require their matching human
review artifacts.

A missing applicable result is `waiting_human_review`, while a malformed or
wrong-mission result is `blocked`. This prevents a completed report from being
misread as a verified evaluation. Run it without triggering providers:

    python -m cosmatter audit-workflow-readiness --run-id bfo_live_001

## Research Gap mission boundary

A Research Gap candidate is scoped to one Mission Brief. Generation uses only
accepted verification decisions from that same mission, and every cited
EvidenceCard must match the mission material and property. The persisted
candidate schema requires distinct evidence IDs, at least one explicit
condition conflict or evidence-missing reason, and at least one proposed
validation action.

Both report construction and UI export independently reject a candidate that
has a foreign material/property, is not marked `candidate_requires_human_review`,
uses duplicate or absent identifiers, or cites evidence outside the current
mission's accepted evidence set. A displayed Gap therefore remains a
review-required hypothesis, never a validated material-science conclusion.

## DOI-aware candidate deduplication

Each candidate retains an optional normalized DOI in addition to its provider
`document_id`. Candidate history merges only exact DOI aliases or exact document
IDs; it never fuzzy-matches title or year. The chosen representative prefers a
content-accessible route, while every contributing provider/query origin remains
attached with its original document identifier. The retained `deduplication`
object reports the identity method and merged counts. Candidate-screening
fingerprints include this metadata, so a change in bibliographic identity or
merge outcome requires a fresh human screening review.

## Material-fact source-map integrity gate

Before fact fusion, report delivery, report auditing, or browser export,
CosMatter reloads every reviewed material-fact artifact and its document-scoped
source map. Each fact must retain the same document ID, segment ID, locator,
and short-excerpt SHA-256 as its currently reviewed source-map segment. Missing,
modified, or orphaned source maps stop the operation instead of allowing a
structured fact to be shown or compared. This is an integrity check on
provenance links, not an assessment of scientific correctness.

## Evidence-chain hard gates

For an EvidenceCard to enter a report or UI bundle, the candidate must have a
current human screening decision of `include_for_fulltext`, and the card's
short quote plus locator must exactly match a reviewed source-map segment for
the same document. `record-source-map` repeats the screening check, so a
manually written parse-task ledger cannot bypass literature selection. Missing
or stale screening, a missing map, or a mismatched quote/locator stops evidence
ingestion and delivery. These gates establish workflow provenance; they do not
replace a human judgment of scientific correctness.
