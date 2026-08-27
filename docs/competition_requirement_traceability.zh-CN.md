# 赛道三修订要求—CosMatter 追溯表

本文把 `GOAI_赛道三_手册修订对照表_0811.docx` 中与 CosMatter 初赛和后续进阶实施直接相关的要求，映射到仓库工件、检查命令和当前真实性状态。它是提交前核查表，不能替代赛事原文。

| 修订要求 | CosMatter 工件 / 命令 | 当前状态与边界 |
| --- | --- | --- |
| 初赛提交可运行训练/推理源代码；随机种子和关键参数可查 | `pyproject.toml`、`REPRODUCIBILITY.md`、`requirements.lock`、`configs/reproducibility.example.json`、`check-submission-readiness`、`build-submission-source-bundle` | 已实现源码白名单包和机器检查：Python/前端源码与测试、前端锁文件、Python/Node 版本、随机种子、关键参数范围、外部资源版本/访问日期字段均须存在；外部运行参数仍须在真实 run 中记录，示例配置不构成实验记录。 |
| 提交 PDF、LaTeX 源、参考文献且引用一一对应 | `export-latex-report --run-id RUN --compile` | 已实现；仅导出已接受、可定位 EvidenceCard，生成 `main.pdf`、`.tex`、`.bib` 和 `citation_audit.json`。 |
| 事实、Gap 可回溯至文献与数据来源 | `EvidenceCard`、`source_map`、`verification_decisions`、LaTeX “书目来源”列、`bibliographic_source_coverage.json` | 代码门禁已实现；每条进入报告的卡片要求来源定位、人工接受状态及非空书目来源。真实完成评测还要求冻结语料的私有书目来源登记表全覆盖，运行目录只保存脱敏覆盖数量、来源类别数和哈希。原文真实性仍须人工逐条核对。 |
| 公开可访问材料数据库可用，须披露来源与访问 | `external_resource_disclosure.json`、`record-external-resource-disclosure` | 已实现结构校验，拒绝密钥和私有路径；真实访问日期、版本、许可和费用仍待实际运行后填写。 |
| 结果可复现、过程可检查、可持续扩展 | `events.jsonl`、`submission_execution_manifest.json`、`workflow_readiness.json`、`.cosmatter-run.json` | 基础架构和审计索引已实现。不得将导入的 UI 预览 JSON 误写为可执行 run。 |
| 真实检索基线的同边界量化比较 | `compare-human-retrieval-routes`、`human_retrieval_route_comparison.json` | 已实现只比较同一任务、冻结语料、人工金标准、K 和 DOI 映射策略的聚合 P@K/R@K/nDCG；真实路线运行与人工标注尚未完成，不能使用模板或测试数据声明效果。 |
| 90 篇人工标注覆盖与评测前门禁 | `audit-human-annotation-coverage`、`human_annotation_coverage.json` | 已实现只读本地金标准、只输出聚合覆盖数量的审计；仅全部相关性标注完成时开放检索评测，不能以覆盖审计替代真实指标。 |
| 90 篇真实语料的冻结、授权与 DOI 覆盖审计 | `audit-frozen-corpus-readiness --run-id RUN --expected-count 90`、`frozen_corpus_readiness.json` | 已实现只含计数、唯一性、DOI 覆盖、访问边界与清单哈希的审计门禁；不读取 PDF 或全文，也不代表已完成真实性能评测。 |
| 检索、抽取、证据、Gap 的真实评测 | `docs/real_corpus_evaluation.md`、90 篇语料清单/人工金标准模板 | 评测协议已就绪；尚未有可对外声明的 90 篇真实指标，提交时必须以实际产生的聚合工件为准。 |
| 结果核验与过程可检查性 | `real_corpus_evaluation_run_record.json`、`frozen_corpus_readiness.json`、`human_annotation_coverage.json`、`bibliographic_source_coverage.json`、`evaluation_failure_case_log.json`、`evaluation_api_cost_latency.json` | 已实现只接受聚合失败类别/计数/处置，以及服务商级请求数、费用和延迟的脱敏审计工件；`completed` 真实评测声明除工件存在外，还必须核验四类指标摘要的 schema、任务/语料身份、信任状态和数值范围，并绑定同一份清单哈希、已冻结语料审计、零未审相关性标注及全量书目来源覆盖。真实运行仍待完成。 |
| 新增开源贡献评价 | `LICENSE`、`CITATION.cff`、`CONTRIBUTING.md`、源码白名单包 | 代码与文档已按 MIT 计划准备。公开仓库地址、发布日期和第三方资产复核待团队发布时确认。 |
| 经典 MC 量化对照（修订路线 B 新增范围） | `create-ising-benchmark-plan --repetitions N`、`run-ising-benchmark`、`propose-ising-followups`、`docs/classical_ising_benchmark_20260814.zh-CN.md` | 已执行一份有限二维 Ising Metropolis/Wolff/Swendsen–Wang 对照记录；每个温度×算法按独立种子重复，输出自相关、有效样本率、本地耗时的均值/离散度及相对同温度 Metropolis 的比值。结果严格限定为本机有限模型实现；QMC 未实现，不得声称完成。 |
| 势函数结果的公平比较披露 | `measurement_environment`（硬件类别、设备、并行度、数值精度、计时范围） | 已纳入外部执行协议；缺少该项时拒绝记录协议。模型速度只在相同任务坐标、参考方法及已披露计时范围内可比较。 |
| 进阶势函数 / 模拟路线需量化对照与能力边界 | `create-potential-benchmark-plan`、`create-potential-execution-protocol-template`、`record-potential-execution-protocol`、`evaluate-potential-benchmark`、`propose-potential-followups` | 已实现“种子化多点计划（每区默认 3 点）—人工执行协议—外部结果导入—按训练域内/近边界/域外聚合误差—按具体任务×模型弱点局部加密”的框架；每行必须声明原子数，同一任务的模型行必须共享原子数和参考能量，模型排序使用 eV/atom 能量误差、力 RMSE、同任务壁钟时间。主动任务以每原子能量误差、力 RMSE、壁钟时间的词典序选择锚点，并绑定触发坐标与人工批准门禁。协议绑定模型版本、单位与结构生成边界。未执行 DFT/DP/MD/MC/QMC，不得把框架输出作为性能数据。 |

## 提交前的最短闭环

```powershell
# 1. 真实 run 的证据与报告已经人工核验后
.\.venv\Scripts\python.exe -m cosmatter export-latex-report --run-id YOUR_RUN --compile
.\.venv\Scripts\python.exe -m cosmatter record-external-resource-disclosure --run-id YOUR_RUN --input .\reviewed_resources.json
.\.venv\Scripts\python.exe -m cosmatter check-submission-readiness --run-id YOUR_RUN

# 2. 仅在全部机器检查通过时生成最终包
.\.venv\Scripts\python.exe -m cosmatter build-final-submission-package --run-id YOUR_RUN
```

最后仍需由团队完成三项人工核验：引用与原文定位真实性、第三方服务和数据再分发合规性、以及所有结果与赛事 AI 辅助规定的一致性。
## 当前提交状态（2026-08-14）

- 代码、前端、测试、源码白名单包、LaTeX/PDF 导出器、引用结构审计、资源披露校验及最终包门禁已实现并通过自动化回归；
- 势函数路线已具备确定性覆盖内/近边界/分布外计划、模型与参考协议披露、外部结果导入比较和待批准的主动边界加密任务；
- **尚未完成且不能在初赛稿中声称完成**：真实 90 篇 BiFeO3 语料的人工标注与指标、真实 MinerU/Sciverse/API 调用记录、已人工接受的 EvidenceCard 报告、真实势函数/DFT/DP/MD/QMC 计算对比及公开仓库发布。有限二维经典 Ising MC 对照已执行，但不替代这些材料体系计算或 QMC。

因此，当前可提交“代码与方案/可行性验证”材料；只有在真实 run 满足 `check-submission-readiness --run-id` 后，`build-final-submission-package` 才会生成带报告的最终提交包。
