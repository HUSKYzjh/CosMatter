# Authorized corpus and human gold standard

## Freeze the research questions before evaluating retrieval

The paper cohort and the research-question set are independent frozen inputs.
Create the built-in BFO proposal pack in a new local file:

```powershell
.\.venv\Scripts\python.exe -m cosmatter create-bfo-question-set-review-template `
  --question-set-id bfo-core-v1 --output .\private_bfo_question_review.json
```

Every proposal starts `unreviewed`. A human reviewer must choose `include` or
`exclude`, complete all five Boolean quality checks, and add a bounded reason.
After creating a dedicated evaluation mission whose material includes
`BiFeO3`, freeze the completed review:

```powershell
.\.venv\Scripts\python.exe -m cosmatter record-frozen-question-set `
  --run-id YOUR_RUN --input .\private_bfo_question_review.json
```

The command refuses blank, partial, duplicate, material-mismatched, or
quality-check-failing included questions. It writes an immutable
`frozen_question_set.json` plus a count/hash-only
`question_set_review_audit.json`; neither artifact is an evaluation result.
The review file remains the human-editable source and must not be replaced by a
test fixture or an automatically asserted review.

The Mission Definition page now includes a local **Human question-set review
desk** before any evidence or evaluation gate. Open it, explicitly select the
generated review JSON, and complete the decision, five checks, and review note
for every question. The attestation
control remains disabled until all questions are decided, every check is an
explicit Boolean, every note is nonempty, at least three questions are
included, and every included question passes all five checks. Any subsequent
edit clears the attestation. Without a complete review and an explicit
independent-review attestation, export preserves
`blank_human_question_set_review_not_frozen`; only a complete attested export
uses `human_reviewed_question_set_for_evaluation`.

This desk is only a browser-local editor: it makes no API request, never uploads
the selected file, cannot write into `runs`, and cannot freeze
a question set. Treat its export as input to the same
`record-frozen-question-set` command above. The CLI remains the authoritative
mission/material/schema gate and creates the immutable count/hash-bound pair.
The draft is temporarily copied to same-origin browser `sessionStorage` so a
page refresh or route change does not erase a long review. Attestation is never
persisted and must be confirmed again after restoration. Imported and restored
drafts are normalized back to the not-frozen trust state. The reviewer can clear
the session copy with a two-click confirmation; exporting a JSON remains the
only durable save.

This workflow prepares the real 90-paper BiFeO3 evaluation cohort without reading a PDF directory, collecting local paths, or redistributing institutional full text. The reviewer first creates a bibliography-only JSON selection with one stable document_id per authorized paper. The full Zotero-to-review path, including the private selection-template boundary, is in [the corpus-onboarding guide](corpus_onboarding.zh-CN.md).

Run `record-corpus-manifest` with a run ID and the reviewed selection JSON. Then use the single local preparation command below to write the count-only frozen-corpus audit plus blank gold-standard, bibliographic-source, and evaluation-run-record templates. Add `--seed-candidates` only when the reviewer explicitly wants the manifest papers copied into the unranked authorized-local candidate list for later source-map work.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter prepare-real-evaluation `
  --run-id YOUR_RUN --expected-count 90 --seed-candidates
```

This preparation command cannot create a human judgment or any metric. It does not open PDFs, local paths, annotations, provider data, or `.env`; its outputs are path-free templates and count-only audit data. Omitting `--seed-candidates` leaves any existing retrieval-candidate artifact untouched.

For a reproducible local retrieval baseline, create a separate private local_parsed_source_index JSON from the reviewed Markdown outputs. Each document_id and title must match the corpus manifest; paths exist only in this input file. Run local-parsed-corpus-search with the run ID, index path, query, and top-k. It reads Markdown locally, persists only ranked candidate metadata, and never writes paths or text into runs.

The resulting corpus_manifest.json contains bibliographic metadata and the access boundary only. human_gold_standard_template.json contains blank review slots for retrieval relevance, evidence location/correctness, material-fact correctness, condition comparability, and Research Gap evidence completeness. Neither file is an evaluation result.

For the planned 90-paper cohort, use exactly 90 unique document IDs after manual bibliographic verification. Keep the downloaded PDFs and source annotation notes local. Only reviewer-selected short excerpts may enter a source-map, and only after a completed authorized parsing task. No document path, attachment key, PDF bytes, API secret, or unrestricted full text belongs in either JSON file.

After annotation, report real metrics only with the frozen manifest identifier, annotation date, evaluator, model/prompt version, retrieval candidate universe, and a failure-case log. The synthetic benchmark in examples/frozen remains a regression test and is not evidence of 90-paper performance. Its generated records include a SHA-256 of the fixture bytes, so same-named fixture edits cannot be silently compared as the same regression input; this hash identifies only the synthetic fixture content and contains no paper text, DOI, path, or credential.

## Browser-local corpus relevance review desk

The Mission Definition page includes a separate **Human corpus relevance review
desk** for the document-level `retrieval_relevance` field. Explicitly select the
CLI-generated `human_gold_standard_template.json`. You may then select the
matching `corpus_manifest.json` to display each title and DOI while reviewing;
the manifest is accepted only when its mission ID, corpus ID, document count,
and complete document-ID set exactly match the gold template. No title or DOI
is used to infer a label.

The desk supports local search, relevance filters, and pages of 25 records for
the planned 90-paper cohort. It edits only `retrieval_relevance` and preserves
the evidence, material-fact, comparison, and Gap annotation arrays without
rendering or interpreting them. The reviewed state remains unavailable until
every record is labelled and at least one record is strictly `relevant`. A
separate independent-review checkbox is then required. Any label change or
session restoration clears that checkbox.

The desk never calls an API, reads PDF or Markdown content, writes to `runs`, or
persists the independent-review declaration. Its same-origin `sessionStorage`
copy is only crash/route-change protection. An incomplete or unattested export
retains `blank_human_annotation_template_not_evaluation_result`; only a
complete, explicitly attested export uses
`human_reviewed_gold_standard_for_evaluation`. Invalid imports do not replace
the active draft, and clearing the session copy requires two clicks.

Use the exported JSON as input to both `audit-human-annotation-coverage` and
`evaluate-human-retrieval`. The CLI remains authoritative: it rechecks the
schema, frozen identity, all document IDs, relevance completeness, and trust
status. Browser export does not itself create a metric or establish that a
human actually read a paper.


## Annotation coverage gate

Before calculating any real metric, audit the private `human_gold_standard` file against the frozen manifest:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter audit-human-annotation-coverage `
  --run-id YOUR_RUN --input .\private_reviewed_gold.json
```

`human_annotation_coverage.json` contains only aggregate counts: frozen document count, relevance-status counts, and the number of documents with nonempty evidence/fact/comparison/Gap annotation lists. It does not copy titles, DOIs, document-level labels, facts, locators, quotations, reviewer identity, or local paths. The retrieval gate becomes `ready_for_human_retrieval_evaluation` only when every frozen document has a reviewed relevance state; this alone does not validate material-fact, evidence-quality, or Gap assessments.
## Human-reviewed retrieval metrics

After every frozen-corpus document has been reviewed, copy the generated
human_gold_standard_template JSON, change its trust_status to
human_reviewed_gold_standard_for_evaluation, and replace every unreviewed
retrieval_relevance with relevant, partially_relevant, or not_relevant. The
evaluated file must contain every manifest document exactly once. Keep the
generated `annotation_instructions` object unchanged; the coverage audit and
retrieval evaluator consume the same reviewed file schema.

Run evaluate-human-retrieval with the reviewed file, the saved search-history
index, and K. The result contains strict Precision@K and Recall@K (only
relevant counts as a strict hit) plus graded nDCG@K (relevant gain 2,
partially_relevant gain 1). It does not contain per-paper relevance labels,
paths, source text, or prompts. A blank template is rejected rather than
reported as a measurement.


## Same-boundary retrieval route comparison

For a real comparison of keyword, semantic, hybrid retrieval, ordinary RAG, or a multi-Agent retrieval route, each route must first produce its own `human_retrieval_evaluation.json` from the same frozen manifest and the same reviewed relevance gold. Copy only those aggregate evaluation payloads into a private file based on `docs/templates/human_retrieval_route_comparison.template.json`; give every route a clear stable identifier and choose exactly one baseline route.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter compare-human-retrieval-routes `
  --run-id YOUR_RUN --input .\reviewed_retrieval_routes.json
```

The command rejects any mixture of mission ID, corpus ID, K, relevant/partially-relevant gold population, or identity-resolution policy. Its resulting `human_retrieval_route_comparison.json` contains only P@K, R@K, nDCG@K, aggregate DOI-resolution diagnostics, and deltas to the declared baseline; it does not contain a title, query, relevance label, prompt, source location, private path, or provider response. Route labels must be factual (for example, `keyword_bm25`, `semantic_embedding`, `hybrid_reranked`, `single_agent`, `multi_agent`) and must not imply a method that was not actually run.
## Review-gated material fact metrics

Use the separate human_reviewed_material_fact_gold template to annotate expected
composition, structure, property, processing, experimental-condition, and
simulation-method facts. The gold contains normalized value, normalized unit,
and source locator, but never unrestricted quotation text. It must cover every
frozen corpus paper; papers with no expected facts use an empty expected_facts
array.

Run evaluate-human-material-facts with the reviewed file. The resulting
Precision, Recall, and F1 are explicitly for the review-gated end-to-end fact
pipeline, not a raw LLM extraction benchmark. unit_match_accuracy is calculated
only for predicted facts whose document, category, name, normalized value, and
locator align with a gold fact. The artifact contains aggregate counts and
metrics, not fact labels or source content.


## Human expert review of Research Gap candidates

After generate-gap-candidates has produced evidence-bound candidates, run
create-gap-review-template. It emits one blank assessment slot for every
current candidate ID. An expert reviewer changes the trust status to
human_expert_reviewed_gap_assessment_for_evaluation and completes approval,
novelty rating from 1 to 5, actionability rating from 1 to 5, and evidence
completeness for every candidate.

The reviewer must also confirm whether the executed approved counterevidence
search has been inspected, then select one bounded novelty-search outcome:
no direct match in bounded search, related prior work found, or inconclusive.
The first outcome never asserts global novelty or the absence of literature; it
only records the result of the frozen, auditable search boundary. An expert
cannot approve a candidate without recording the counterevidence review.

evaluate-human-gaps rejects incomplete, blank, stale, or mismatched reviews.
Its aggregate output reports expert approval rate, mean novelty rating, mean
actionability rating, evidence completeness, counterevidence-review coverage,
and the distribution of the bounded novelty-search outcomes. The output does
not repeat Gap prose, evidence IDs, reviewer identity, or any source text.
These metrics are human-expert assessment of evidence-bound candidates, not an
automated novelty claim.

## Safe UI projection

`export-ui` exposes only these aggregate, human-reviewed metrics to the
Research Extension page: retrieval P@K, R@K and nDCG; review-gated material
fact precision, recall, F1 and unit-match accuracy; and expert Gap approval,
novelty, actionability and evidence-completeness summaries. It never exports a
corpus identifier, paper-level label, source path, quotation, prompt, reviewer
identity or full-text-derived field. When an evaluation artifact is absent, the
UI says that no human-reviewed evaluation is available; it does not display a
zero score or imply a failed measurement.

The same page shows a frozen-question-set prerequisite only when both
`frozen_question_set.json` and `question_set_review_audit.json` pass their
mission, hash, count, evidence-level, and gate checks. The browser receives only
reviewed/included/excluded totals and the four evidence-level counts. It never
receives the question-set ID, question text, reviewer note, or hashes, and the
ready state explicitly means question-level evaluation may begin—not that any
metric has been generated.

The local question-set review desk is intentionally separate from this safe
aggregate projection and from the Research Extension evidence gate. It is an
opt-in private editing surface available during task definition, while the
ordinary imported UI bundle continues to expose aggregate readiness only.

## Human evidence-quality review

After accepted EvidenceCards have been created, run
`create-evidence-quality-review-template`. The template contains only evidence
ID, document ID, source locator, and predicted stance; it deliberately excludes
claims, quotations, full text, provider payloads, and reviewer identity. A
reviewer verifies each locator/citation and whether the recorded condition set is
complete; predicted contradiction cards also receive a contradiction-label
judgment.

Set the template trust status to
`human_reviewed_evidence_quality_assessment_for_evaluation`, complete every
required Boolean, then run `evaluate-human-evidence-quality --input REVIEW.json`.
The aggregate contains citation precision, condition completeness, and
contradiction precision. These are human-review metrics for the current
accepted-evidence set; they do not establish the scientific truth of a claim or
the absence of other literature.


## 提交前的统一运行记录

优先使用命令生成的 `real_corpus_evaluation_run_record_template.json`；`docs/templates/real_corpus_evaluation_run_record.template.json` 仅作字段对照。它们本身不是指标结果，也不应填写估计值。完成真实运行后，填写执行日期、代码版本、实际服务/模型与四类人工审阅状态；失败案例与 API 成本/延迟必须分别写入对应的聚合工件，不能塞回运行记录。

提交前至少核对以下事项：

1. `corpus_manifest` 的 `document_id` 数量应与本次声明的冻结数量一致（首轮计划为 90 篇），且全部来自已授权的内部核对范围；
2. 四类人工审阅文件均覆盖其适用对象，`trust_status` 已从空白模板改为对应的 `human_reviewed` 状态；
3. 每一个已声明指标都有同一 `run` 中生成的聚合工件；未完成的指标必须保留为 `not_generated`，而不能写为零或估计值；
4. `failure_case_log` 只写聚合问题类型和修复状态，不复制受限全文、PDF 路径、密钥、服务原始响应或个人身份信息；
5. 将运行记录、submission execution manifest、workflow readiness、来源审计和报告审计一起交由团队核对真实性。


## Machine-validated evaluation run record

After `corpus_manifest.json` is frozen, run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter create-evaluation-run-record-template --run-id YOUR_RUN
```

This writes `real_corpus_evaluation_run_record_template.json`, bound to the
mission ID, corpus ID, manifest document count, frozen question-set ID, frozen
question count, and question-set content hash. The command fails closed when
the validated `frozen_question_set.json` / `question_set_review_audit.json`
pair is absent or inconsistent. It is an empty human
disclosure record, not an evaluation result. Copy it to a private reviewed JSON
file only after the real run. Complete the execution date, code revision,
service/model and human-review disclosures, then save it with:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter record-evaluation-run-record --run-id YOUR_RUN --input REVIEWED_RECORD.json
```

The command rejects a mismatched mission/corpus/count and rejects every metric
marked `generated` unless its matching aggregate artifact exists in the same
run. A `completed` submission truth check additionally requires all four human
metric artifacts, recorded failure-case/API cost records, a matching
`frozen_corpus_readiness.json`, and a fully reviewed
`human_annotation_coverage.json`. The latter must show zero unreviewed
relevance labels for exactly the frozen corpus. In a completed record all four
`human_review_disclosure` values must be `completed`. It never reads local PDF
paths, full text, provider payloads, or environment secrets.

A completed final-submission package includes both validated frozen
question-set files alongside the aggregate evaluation artifacts. The frozen
file contains only the included, reviewed research questions and their declared
scope/evidence level; free-form reviewer notes remain outside the package.

## Machine-validated operational disclosures

A completed real-corpus evaluation must also save two separate aggregate-only records. These records are not metric results and must not contain a document identifier, title, DOI, locator, quotation, full text, local path, credential, provider request ID, URL, prompt, or raw provider response.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter record-evaluation-failure-case-log `
  --run-id YOUR_RUN --input .\reviewed_failure_case_log.json
.\.venv\Scripts\python.exe -m cosmatter record-evaluation-api-cost-latency `
  --run-id YOUR_RUN --input .\reviewed_api_cost_latency.json
```

Start from `docs/templates/evaluation_failure_case_log.template.json` and `docs/templates/evaluation_api_cost_latency.template.json`. Failure cases use a bounded category, aggregate count and resolution state. Provider reporting is limited to aggregate request counts, currency, total cost and median/p95 latency. When the reviewed run record declares either status as `recorded`, CosMatter verifies that the matching artifact exists, matches the frozen mission/corpus identity and satisfies the safe schema; a `completed` truth check requires both.


## Cross-source frozen-corpus identity rule

A reviewed gold label belongs to a frozen corpus `document_id`. Retrieval
providers do not need to use that same identifier: a Sciverse, OpenAlex,
Sci-Base, or local-library candidate may map to the frozen document only when
its normalized DOI exactly matches one unique normalized DOI in the frozen
manifest. CosMatter never maps by title, author, year, abstract similarity, or
LLM judgment.

`evaluate-human-retrieval` reports the raw retrieved count, the unique resolved
count, the number resolved by DOI, and duplicate DOI aliases, alongside P@K,
Recall@K, and nDCG@K. An unmapped provider record stops the controlled
frozen-corpus evaluation rather than being silently treated as relevant or
ignored. This makes route comparisons auditable while preserving the boundary:
a 90-paper corpus evaluates retrieval within that declared cohort, not coverage
of all published literature.
