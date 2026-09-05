# DSH 公开插件调研建议：实施与证据审计

> 审计日期：2026-08-29
> 最近复验：2026-09-05
> 依据：[公开插件调研建议](DSH_PUBLIC_PLUGIN_RESEARCH_AND_RECOMMENDATIONS_2026-08-29.zh-CN.md)
> 范围：仓库内的工程控制面、合成验收与受控试点边界；不构成科学证据、真实 provider 可用性承诺或第三方插件安全认证。

## 判定规则

- **已实现且有验证**：存在版本化实现、对应测试或独立 verifier，且输出边界与建议一致。
- **部分实现/受限采用**：只实现建议的安全前置或只读投影；明确不将其解释为完整执行能力。
- **条件式保留**：建议依赖尚未出现的部署需求、明确的人类裁决或威胁建模，当前不应以“缺功能”为由扩大权限面。

## 推荐清单覆盖核对

以原建议表（P0/P1/P2 共 19 项）为准，本审计逐项映射到下文证据：P0 的 6 项和 P1 的 7 项均有版本化实现及本地验收；P2 的 6 项中，提醒、固定 DAG、单运行只读投影、公共候选发现与自有 loopback façade 是受限实现，远程访问防护因不存在网络暴露而有意保留。这里的“覆盖”表示建议已经被实现或以可审计的理由拒绝，**不**表示条件式功能已经获得生产执行授权。

## P0：发布、供应链与外部副作用

| 建议 | 当前状态 | 代码/验收证据 | 保留边界 |
| --- | --- | --- | --- |
| Bundle 发布兼容性门禁 | 已实现且有验证 | `configs/dsh_compatibility.json`、`tools/verify_dsh_plugin_release.py`、`tests/test_dsh_release_gate.py` | clean profile 仅安装本地 tarball、转储配置；不读 `.env`、不调 provider。 |
| 稳定 call ID、幂等账本与 unknown outcome | 已实现且有验证 | `src/cosmatter/external_dispatch.py`、`tests/test_external_dispatch.py`、`tests/test_provider_fault_recovery.py` | unknown 不会自动重放；恢复前只能查询状态或取得新的同意。 |
| 第三方 bundle 准入与卫生审计 | 已实现且有验证 | `configs/dsh_third_party_plugin_admissions.json`、`src/cosmatter/plugin_hygiene.py`、`tools/audit_dsh_plugin_candidate.py`、`tests/test_plugin_hygiene.py` | 当前生产 allowlist 的第三方数量为 0；静态扫描不是安全认证。 |
| 只读市场摄取防火墙 | 已实现且有验证 | `dsh_market_snapshot.json`、冻结 baseline、hash-bound review、`tools/verify_dsh_market_snapshot_review.py`、`tools/verify_dsh_plugin_admission.py`、`tests/test_market_snapshot_review.py` | 快照不提供可执行 spec，diff 不含 URL；生产 bundle 不读取市场快照。 |
| 分层可重放验收包 | 已实现且有验证 | `fixtures/dsh_replay/`、`tools/verify_dsh_synthetic_replay.py`、`tests/test_dsh_synthetic_replay.py` | 只用合成 fixture；仅 mock 网络适配器，不能替代人工审核。 |

## P1：工件、运行治理与组合可靠性

| 建议 | 当前状态 | 代码/验收证据 | 保留边界 |
| --- | --- | --- | --- |
| 受限 Artifact/渲染契约 | 已实现且有验证 | `src/cosmatter/artifact_contract.py`、`tests/test_artifact_contract.py`、`tests/test_ui_preview.py` | 固定 allowlist 路由；不提供 PDF、Markdown、URL 或任意路径读取。 |
| 项目决策记忆 | 已实现且有验证 | `src/cosmatter/decision_memory.py`、`tests/test_decision_memory.py` | 只存工程决定/待办；科学事实、DOI、PDF 与正文术语被拒绝。 |
| 运行后不变量审计 | 已实现且有验证 | `src/cosmatter/runtime_invariants.py`、`tests/test_runtime_invariants.py` | 只读审计；异常阻断敏感阶段，不修改原始工件。 |
| 组合故障最小化实验室 | 已实现且有验证 | `tools/diagnose_dsh_plugin_combinations.py`、`tests/test_dsh_combination_lab.py` | 每个 probe 使用临时 `DSH_HOME`；无 `.env`、运行数据或 provider 调用。 |
| Harness recipe/评测包 | 已实现且有验证 | `configs/dsh_harness_recipe.json`、`tools/verify_dsh_harness_recipe.py`、`tests/test_dsh_harness_recipe.py` | 汇总兼容矩阵、市场 diff、准入与 replay；本地耗时不等于 provider 性能。 |
| 已批准证据检索 | 已实现且有验证 | `src/cosmatter/accepted_evidence_search.py`、`tests/test_accepted_evidence_search.py` | 只索引已接受 evidence-card 的受限字段；不摄取 PDF、Markdown、Source Map 摘录或会话正文。 |
| Provider 故障注入与恢复矩阵 | 已实现且有验证 | `tests/test_provider_fault_recovery.py`、`tests/test_external_dispatch.py` | 不使用真实 token、任务 ID 或论文响应；unknown fail-closed。 |

## P2：受限采用与有意保留

| 建议 | 当前状态 | 代码/验收证据 | 保留边界 |
| --- | --- | --- | --- |
| 提醒与成本/配额可视化 | 部分实现/受限采用 | `operational_telemetry.py`、`reminder_board.py`、`tests/test_operational_telemetry.py`、`tests/test_reminder_board.py` | 仅聚合计数、注意状态和已有人工披露；不估算账单、不自动调度。 |
| 声明式并行阶段执行器 | 部分实现/受限采用 | `configs/cosmatter_workflow_dag.json`、`workflow_dag.py`、`tests/test_workflow_dag.py` | 固定九阶段线性 DAG、最大并发 1；没有调度器、取消器或执行授权。 |
| 多运行控制面看板 | 部分实现/受限采用 | loopback `stage_contract`、`operational_telemetry`、`reminder_board` 投影及其 API/UI 测试 | 仅单运行与本地聚合；不暴露远程 start/cancel/steer 控制面。 |
| 公共候选发现 broker | 部分实现/受限采用 | `public_candidate_discovery.py`、`execute-plan-public-arxiv-discovery`、`register-public-pdf-candidate`、`tests/test_public_candidate_discovery.py`、`tests/test_public_pdf_candidate_cli.py` | Atom 检索仅产生默认不可读元数据候选；transport 层禁用环境代理、逐跳校验 allowlist，并将同一份 DNS 公网解析结果用于 TCP 连接，拒绝越界跳转或私网/非公网解析；PDF probe 不下载全文；不支持网页/HTML 爬取或自动 MinerU 提交。 |
| 本地 allowlist MCP façade | 部分实现/受限采用 | 七个 `@cosmatter/*` loopback bundle、`plugins/dsh-plugin-group.json`、`tests/test_dsh_loopback_clients.py` | 不接入通用 filesystem、浏览器、GitHub、数据库或外部 MCP server。 |
| 远程访问防护 | 条件式保留 | 当前 `127.0.0.1` 固定 loopback 策略与 bundle release tests | 未部署反向代理/局域网入口，因此不引入 OAuth、WebSocket relay 或本地 token 伪边界；若网络暴露，必须先做威胁建模和独立回归。 |

## 受控外部链路试点证据

以下试点仅证明接口与审计边界可运行，**不**证明任何论文结论：

1. Sciverse SDK 的非空 `doc_id` 已按其官方语义映射为可受控读取的内容路由；显式 `is_content_accessible=false` 仍优先拒绝。真实 BFO 运行完成了有界上下文读取，正文位于 run 外私有审阅文件。
2. allowlisted arXiv Atom 查询已用已批准 BFO 检索式产生默认不可读候选；候选收据审计和敏感工件扫描未发现 URL/正文泄漏。
3. MinerU 已完成单篇受筛选公开来源的任务、hash-only receipt 审计和私有 Markdown/候选池准备。未自动记录 Source Map、材料事实或接受科学证据。

## 当前发布验证

发布前的无 provider 校验入口是：

```powershell
.\.venv\Scripts\python.exe tools\verify_dsh_harness_recipe.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

2026-09-05 从新 PowerShell 终端执行统一入口 `scripts/acceptance.ps1`：Harness recipe 四项检查、7 个 DSH bundle 的测试与 dry-run 打包、579 项 Python 测试、前端类型检查以及 95 个文件中的 322 项前端测试均通过，最后输出 `OK - CosMatter full local acceptance passed.`。浏览器 E2E 另行复跑为 16 项通过。测试中 UI 负路径产生的 `ResourceWarning` 不表示失败，仍应在后续 Python/测试运行时升级时复核。

## 不应由本审计推导的结论

- 不应将候选、模型草案、受控全文读取、MinerU 解析或私有候选池当作已接受证据。
- 不应将全量测试通过解释为真实 provider SLA、费用、第三方包安全性或材料结论正确。
- 不应因路线图中仍列有条件式 P2 项而把远程控制、自动执行、网页爬取或绕过人工 Source Map 门禁纳入当前范围。
- 2026-08-29 的一次无凭据 arXiv Atom smoke test 在 10 秒上游时限内未响应，按设计 fail-closed；这不构成连接边界失效，也不应被解释为 arXiv 或本 broker 的可用性 SLA。
