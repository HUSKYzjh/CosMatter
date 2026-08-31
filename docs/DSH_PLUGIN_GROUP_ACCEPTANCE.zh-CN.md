# CosMatter DSH 插件组验收清单

本清单覆盖可复现的本地验收，不将其替代为真实案例发布批准。

## 已验证

| 验收项 | 证据 |
| --- | --- |
| 插件组可组合 | `plugins/dsh-plugin-group.json` 列出七个独立 bundle，`tests/test_dsh_plugin_group.py` 校验包名、patch、工具无重名与发布文件范围。 |
| 静态能力覆盖 | 清单的 `catalogue_coverage` 对 `default_cosmatter_plugin_catalogue()` 的全部 23 个描述符作唯一映射；已暴露项必须指向现有 bundle，其余项必须显式标为 Python/人工门禁边界。 |
| DSH 真实 profile 合成 | 隔离 profile `cosmatter-graph-test` 同时加载 mission、observability、policy、research、review、document 与 graph bundle；使用 `dsh --profile cosmatter-graph-test --dump-config` 复核。 |
| 一次安装 | 新建隔离 profile `cosmatter-group-smoke` 后，用单条 `dsh plugin --profile … add <七个本地包路径>` 命令安装；配置转储确认七个 bundle 均加载。 |
| DSH 卸载与恢复 | 已从该隔离 profile 实际 `remove @cosmatter/dsh-review-plugin`，配置转储不再含该 bundle；随后以本地路径重新 `add` 并复核七个 bundle 均加载。 |
| 外部调用幂等恢复 | `tests/test_external_dispatch.py` 与 `tests/test_local_api.py` 覆盖 callId 仅散列持久化、完成调用不二次 provider dispatch、未知结果拒绝同 callId 自动重放。 |
| 提供商故障恢复矩阵 | `tests/test_provider_fault_recovery.py` 用纯合成 adapter 覆盖 Sciverse 超时/401/429、DeepSeek 超时/畸形响应、MinerU 半成功畸形任务及重复轮询；未知 outcome 必须 fail closed。 |
| 运行时关系不变量 | `tests/test_runtime_invariants.py` 和 `cosmatter audit-runtime-invariants` 检查状态转移、授权—dispatch、receipt—结果、allowlist 工件 SHA-256 与 EvidenceCard—verification decision 关系；审计产物不含原始调用 ID、问题、URL、正文或密钥。 |
| 阶段契约投影 | `tests/test_stage_contract.py`、`LocalMissionApi.stage_contract` 与 observability bundle 的 `cosmatter_stage_contract` 对九个固定阶段投影完成条件、人工门、预期输出类别、当前计数和非执行恢复路线；模板、未知字段、问题/全文/URL 与任意恢复命令均被拒绝或不输出。 |
| 聚合运行遥测 | `tests/test_operational_telemetry.py`、`LocalMissionApi.operational_telemetry` 与 `cosmatter_operational_telemetry` 仅按 receipt/dispatch 状态汇总本地调用；成本/延迟只在已人工复核披露存在时转发，不能被当作账单、provider 性能或自动重试指令。 |
| 固定工作流 DAG | `configs/cosmatter_workflow_dag.json`、`tests/test_workflow_dag.py`、`LocalMissionApi.workflow_dag` 与 `cosmatter_workflow_dag` 共同验证九阶段严格线性依赖、最大并发固定为 1、descriptor/data-classification allowlist 和至多一个只读就绪阶段；DAG 不含问题、全文、URL、命令或执行授权，也没有调度器。 |
| 跨会话本地提醒 | `tests/test_reminder_board.py`、`LocalMissionApi.reminder_board` 与 `GET /api/reminder-board` 只投影最早未完成阶段、运行时注意、未知 outcome 和已到期操作待办；不读取待办正文，关闭会话不会执行或伪称执行任何工作。 |
| 公共发现边界核心 | `configs/public_candidate_discovery.json`、`tests/test_public_candidate_discovery.py` 与 `tests/test_public_pdf_candidate_cli.py` 校验无凭据 HTTPS、allowlist 域名、IP/私网/localhost 拒绝、重定向上限与循环拒绝。`execute-plan-public-arxiv-discovery` 只对批准检索式请求有界 Atom 元数据并登记默认不可读候选；`register-public-pdf-candidate` 只对显式 URL 做不落盘的有界 PDF probe。两者均不做网页搜索、HTML 解析、PDF 下载或自动导入。 |
| 受限 Artifact 契约 | `tests/test_artifact_contract.py` 与 `UiPreviewTests.test_artifact_routes_expose_only_fixed_approved_exports` 验证 `cosmatter.artifact/v1`：只能列出固定 ID 的已生成工件，报告需匹配审计，下载路由拒绝私有 PDF/任意路径，卡片仅含 SHA-256、时间、信任状态和固定路由。 |
| 项目决策记忆 | `tests/test_decision_memory.py` 验证 Markdown 为真相源、人工编辑后可重建索引、索引不复制正文，且论文/证据/DOI/PDF/MinerU 等科学内容术语被拒绝。 |
| 无 key 合成 replay | `fixtures/dsh_replay/*.session.jsonl` 与 `*.workspace.expected.json`、`tools/verify_dsh_synthetic_replay.py`、`tests/test_dsh_synthetic_replay.py` 覆盖真实本地授权/账本/筛选/图/Artifact 链路；篡改预期工件稳定失败，且输出不含 token、URL、正文或合成问题。 |
| 组合故障最小化实验室 | `tools/diagnose_dsh_plugin_combinations.py` 使用每 probe 独立临时 `DSH_HOME`、本地 bundle 和 `--dump-config`；`tests/test_dsh_combination_lab.py` 验证二 bundle 合成冲突收敛到 1-minimal 集，报告无路径或运行数据。 |
| Harness recipe | `configs/dsh_harness_recipe.json` 与 `tools/verify_dsh_harness_recipe.py` 一次执行兼容矩阵、市场快照 diff、第三方准入和合成 replay，输出版本/环境/本地耗时/安全边界/已知限制；`tests/test_dsh_harness_recipe.py` 覆盖无敏感输出和路径逃逸拒绝。 |
| 市场摄取防火墙 | `configs/dsh_market_snapshot.json` 只保留 `untrusted_discovery_only` 的公开候选；`dsh_market_snapshot.baseline.json` 与 `dsh_market_snapshot_review.json` 用候选 ID/计数/哈希绑定人工 diff 审阅。`tests/test_market_snapshot_review.py`、`tools/verify_dsh_market_snapshot_review.py`、`tests/test_dsh_plugin_admission.py` 和 `tools/verify_dsh_plugin_admission.py` 验证生产组仅含自有 allowlist、无第三方 spec、不引用市场快照且拒绝未经审阅的快照变更。 |
| 第三方卫生/准入 | `tools/audit_dsh_plugin_candidate.py` 与 `tests/test_plugin_hygiene.py` 对隔离候选的 install lifecycle、动态代码、进程、环境变量、网络和凭据风险出具不含路径/源码的静态报告；HIGH 风险直接阻断。 |
| 任务边界 | 任务 bundle 仅调用 `POST /api/missions`；它不含模型、检索、文件系统、计划批准或证据接受工具。 |
| 目录与策略边界 | policy bundle 只读取静态能力目录并创建非执行授权判断；即使判断为 `permitted`，它也不记录同意、不调用提供商或调度任何适配器。 |
| 受控调研 | research bundle 仅接受精确的任务范围同意：DeepSeek 草案须 `mission_scoped_egress_consent` + `deepseek_request_consent`，元数据检索须 `mission_scoped_egress_consent` + `metadata_provider_consent`。后端先记录授权回执，再调度；不支持全文、MinerU、候选筛选或证据接受。 |
| SciVerse SDK 边界 | Python 领域层使用官方 `sciverse==0.7.1` 的 `AgentToolsClient.semantic_search` 与 `read_content`；SDK 错误仅保留 HTTP 状态和请求 ID 摘要，不能泄露 token、正文或 URL。 |
| 人工筛选 | review bundle 仅读取候选的安全元数据投影，并要求人类为当前全部候选给出完整决定；它不调度提供商、全文或 MinerU，也不接受证据。 |
| 受控解析 | document bundle 必须同时满足候选上游 `is_content_accessible=true` 声明、或 Sciverse SDK 契约中表示全文 artifact 的非空 `doc_id`、或当前哈希内容确认，并完成完整人工 `include_for_fulltext` 筛选以及 `mission_scoped_egress_consent`、`mineru_file_consent`、`private_content_to_mineru`；显式 `is_content_accessible=false` 优先拒绝。它仅调度/轮询 MinerU 任务，返回值不含 URL、全文或解析输出。内容确认只能由筛选后、用户显式的本地读取命令创建，不属于 DSH 工具。 |
| 图边界 | 图 bundle 强制 `127.0.0.1`，拒绝敏感字段和超限响应；查询只读取已投影的已接受证据图。 |
| 已批准证据检索 | `cosmatter_accepted_evidence_search` 仅搜索已接受 evidence-card 的 claim、材料、属性、条件与来源定位；不索引原始 PDF、MinerU Markdown、Source Map 摘录或会话正文，返回不含 quote 的有界指针。 |
| 计划与审核 | 普通图草案、模型草案和人工确认具有独立状态，均明确不构成执行授权或证据接受。模型草案还要求 `mission_scoped_egress_consent` 与 `deepseek_request_consent`。 |
| 合成端到端 | `UiPreviewTests.test_synthetic_graph_plan_review_round_trip_stays_loopback_and_nonexecuting` 通过真实 loopback HTTP 验证构图、草案、人工确认，并断言不会生成 `flight_plan.json`。 |
| 跨运行时客户端 | `DshLoopbackClientTests.test_compiled_dsh_clients_call_real_python_loopback_api` 使用真实编译后的 mission、graph、policy TypeScript 客户端调用 Python loopback API；覆盖任务创建、图读取、目录读取和缺同意时的非执行拒绝。 |
| 发布包 | 每个 bundle 的 `npm pack --dry-run` 只包含编译产物、patch、README 与 manifest；不含 `node_modules`、测试、案例数据或凭据。 |

## 本地验收命令

完整本地验收可从项目根目录直接运行；结束行固定为 `OK - CosMatter full local acceptance passed.`：

```powershell
.\scripts\acceptance.ps1
```

下列命令保留为逐项诊断入口：

```powershell
Set-Location D:\CosMatter\development\CosMatter
$env:PATH = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64;$env:PATH"
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_release.py
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_release.py --profile-smoke
.\.venv\Scripts\python.exe tools\verify_dsh_synthetic_replay.py
.\.venv\Scripts\python.exe tools\verify_dsh_harness_recipe.py
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_admission.py
.\.venv\Scripts\python.exe -m unittest tests.test_provider_fault_recovery tests.test_runtime_invariants -q

Set-Location frontend
npm run check
npm test

Set-Location ..\plugins\dsh-cosmatter-mission-plugin
npm test
npm pack --dry-run

Set-Location ..\dsh-cosmatter-policy-plugin
npm test
npm pack --dry-run

Set-Location ..\dsh-cosmatter-research-plugin
npm test
npm pack --dry-run

Set-Location ..\dsh-cosmatter-review-plugin
npm test
npm pack --dry-run

Set-Location ..\dsh-cosmatter-document-plugin
npm test
npm pack --dry-run

Set-Location ..\dsh-cosmatter-graph-plugin
npm test
npm pack --dry-run
```

## 未替代的人工门槛

真实案例试点仍需：案例范围授权、人工审核者、对错误边/来源缺失/UI 可理解性的人工记录，以及明确的发布批准。未满足这些条件时，插件组仅可作为本地开发和合成验收版本使用。
