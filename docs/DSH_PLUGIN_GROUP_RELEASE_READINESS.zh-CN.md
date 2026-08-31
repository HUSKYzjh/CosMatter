# CosMatter DSH 插件组：兼容性、升级与发布就绪度

> 状态：本地开发/隔离 profile 已验收；**尚未批准公开发布**。
> 更新：2026-08-29。

本文件是 `plugins/dsh-plugin-group.json` 的运行与发布补充。CosMatter 的
Python 领域层仍是任务、来源、人工门禁和审计的唯一真相源；DSH bundle 只经
`127.0.0.1` 调用允许的本地 API。

## 已验证兼容组合

| 项目 | 已验证版本/范围 | 证据 |
| --- | --- | --- |
| Python | 3.14.7 | 后端单元与跨运行时测试。 |
| Node.js | v24.19.0 | 七个 bundle 的 TypeScript 构建与 Node 测试。 |
| npm | 11.17.0 | 每个独立 bundle 的锁文件、构建和 `npm pack --dry-run`。 |
| SciVerse Python SDK | 0.7.1 | `AgentToolsClient` 适配器单测、editable 安装与 loopback 调研回归。 |
| DSH CLI | 0.1.0-rc.7 | 隔离 profile `cosmatter-graph-test` 的配置转储。 |
| Cordis | 4.0.1 | 每个 bundle 的 peer/dev dependency 锁定。 |
| `@deepseek-ai/dsh-tools` | 0.0.1-rc.1 | 每个 bundle 的 peer/dev dependency 锁定。 |

| bundle | DSH 工具 | 外部能力与不可越过的边界 |
| --- | --- | --- |
| `@cosmatter/dsh-mission-plugin` | `cosmatter_mission_create` | 仅建立本地任务与 fleet 分派。 |
| `@cosmatter/dsh-observability-plugin` | `cosmatter_workflow_status`、`cosmatter_artifact_manifest` | 只读流程状态与固定 allowlist Artifact 卡片；只返回标题、SHA-256、生成时间、信任状态和固定下载路由，不读任意路径、PDF、MinerU Markdown 或 provider 内容。 |
| `@cosmatter/dsh-policy-plugin` | `cosmatter_plugin_catalogue`、`cosmatter_plugin_authorization_plan` | 只读目录与非执行授权判断。 |
| `@cosmatter/dsh-research-plugin` | `cosmatter_research_plan_draft`、`cosmatter_research_plan_approve`、`cosmatter_research_query_execute` | DeepSeek 草案与元数据检索均须精确的任务范围同意并由后端先写入授权回执；不处理全文、MinerU 或证据接受。 |
| `@cosmatter/dsh-review-plugin` | `cosmatter_candidate_screening_template`、`cosmatter_candidate_screening_record` | 只读候选安全元数据，并为全部当前候选记录完整人工筛选决定；不调用提供商或接受证据。 |
| `@cosmatter/dsh-document-plugin` | `cosmatter_mineru_source_submit`、`cosmatter_mineru_task_poll` | 只有候选上游全文访问声明或当前哈希内容确认、完整人工筛选和三项精确同意均满足时才调度 MinerU；只返回任务状态，不返回 URL、全文或解析输出。 |
| `@cosmatter/dsh-graph-plugin` | `cosmatter_graph_query`、`cosmatter_accepted_evidence_search`、`cosmatter_graph_plan`、`cosmatter_graph_review_request` | 只读已接受证据图和有界 evidence-card 检索、待审计划及审核请求。 |

所有 bundle 拒绝非 loopback URL、用户名/密码 URL、凭据和私有全文字段。授权仅允许命名调度；不等于证据接受或科学结论。

`plugins/dsh-plugin-group.json` 中的 `catalogue_coverage` 是发行范围的权威
边界：它对 Python 静态目录的每个描述符给出唯一决定。`exposed` 表示仅以所列
bundle 的受限工具形式可用；`python_or_human_boundary` 表示仍在 Python 领域层或
人工门禁中执行，不能因 DSH 安装而绕过审核、读取私有资料或启动外部计算。

## 安装、验证与升级

先在隔离 profile 安装，不修改默认 profile。可将七个本地包作为同一条 pnpm/DSH
`add` 命令的参数一次安装：

```powershell
Set-Location D:\CosMatter\development\CosMatter
dsh plugin --profile cosmatter-graph-test add .\plugins\dsh-cosmatter-mission-plugin .\plugins\dsh-cosmatter-observability-plugin .\plugins\dsh-cosmatter-policy-plugin .\plugins\dsh-cosmatter-research-plugin .\plugins\dsh-cosmatter-review-plugin .\plugins\dsh-cosmatter-document-plugin .\plugins\dsh-cosmatter-graph-plugin
dsh --profile cosmatter-graph-test --dump-config
```

升级一个 bundle 前，先在其目录执行 `npm test` 与 `npm pack --dry-run`；再替换该
profile 中的本地链接并重新转储配置。升级后至少运行：

```powershell
Set-Location D:\CosMatter\development\CosMatter
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest tests.test_dsh_plugin_group tests.test_dsh_loopback_clients -q
```

只有在新 bundle 的 `apply(ctx)` 测试、真实 loopback 客户端测试和 profile
配置转储都通过时，才可把它列为该 profile 的可用能力。DSH/Cordis 属于预发布
兼容面；变更 `@deepseek-ai/cordis` 或 `@deepseek-ai/dsh-tools` 主/预发布版本
时必须重新执行上述全套验证，不能仅依赖 TypeScript 编译成功。

## 回滚

移除一个 bundle 只影响指定 profile：

```powershell
dsh plugin --profile cosmatter-graph-test remove @cosmatter/dsh-research-plugin
dsh --profile cosmatter-graph-test --dump-config
```

需要恢复时，用同一 bundle 的已验证本地路径重新 `add`，再运行 bundle 测试和
`tests.test_dsh_loopback_clients`。不要通过编辑 Python 运行工件、复制 token、
绕过来源门禁或强制设置候选的 `is_content_accessible` 来“回滚”外部调研状态。

2026-08-28 已对 `@cosmatter/dsh-review-plugin` 在隔离 profile 实测上述路径：
移除后配置转储不含该 bundle；从本地路径恢复后，mission、observability、policy、
research、review、document 与 graph 七个 bundle 均重新出现在转储中。

## 外部调用恢复门禁

research 与 document bundle 会把 DSH 工具执行上下文的 `callId` 传给 loopback
领域层。领域层只在 `external_dispatch_ledger.json` 中存储该 ID 的 SHA-256、受限
请求形状的 SHA-256、状态和 provider receipt 引用：绝不写入原始 `callId`、URL、
令牌、问题、正文或 provider response。

- 同一 `callId` 的已完成调用仅返回已有本地安全结果，不再次请求 DeepSeek、
  SciVerse 或 MinerU。
- provider 边界报错后状态为 `unknown`；同一 `callId` 的自动重放被拒绝。只有
  明确的新调用才能在人工核验后继续，MinerU 优先使用只读轮询核验既有任务。
- 该账本是外部副作用恢复证据，不是科学证据、授权本身或事实接受记录。

## 运行时不变量与故障恢复验收

`cosmatter audit-runtime-invariants --run-id <run_id>` 是只读 companion：它不调用
provider、不读取或输出正文，仅检查事件状态迁移、DSH 授权回执与外调账本匹配、
完成外调的 receipt/本地结果配对、证据卡与不可重复 verification decision 的一一
关系，以及 allowlist 工件的 SHA-256。输出 `runtime_invariant_audit.json` 只包含
计数、固定文件名和哈希；`unknown` 或未终结 dispatch 会令审计不通过，等待单独的
人工核验和新的明确调用，而不是自动重放。

`tests/test_provider_fault_recovery.py` 使用完全合成的 Sciverse、DeepSeek 与
MinerU adapter 覆盖超时、401、429、畸形/半成功任务结果及重复轮询。它不需要
token、真实任务 ID、论文、URL 或网络；所有这类不确定结果必须留下 `unknown`，
同一 `callId` 重试被拒绝。

## 受限 Artifact/渲染契约

`cosmatter_artifact_manifest` 与 `GET /api/runs/<run_id>/artifacts` 使用严格的
`cosmatter.artifact/v1` schema。可列出的只有已生成并通过相应门禁的
`ui_bundle`、已接受证据图、工作流摘要、运行时审计，以及具备
`report_evidence_audit.json` 的报告清单/结构化报告。每张卡只含标题、内容类型、
SHA-256、生成时间、信任状态与 `/api/runs/<run_id>/artifacts/<artifact_id>` 固定
下载路由。它不接受文件名或路径参数，且不会列出 PDF、MinerU Markdown、source
map、provider receipt、原始 evidence card、来源 URL 或密钥。

## 项目决策记忆（不进入 DSH 科研语料）

详见 [项目决策记忆说明](PROJECT_DECISION_MEMORY.zh-CN.md)。它以本地可编辑 Markdown
为真相源、以不含正文的 JSON 索引供工程恢复使用；只接受授权、环境、故障恢复、
偏好和待办等非科学项目记录。该目录不进入 Git、run、报告、Artifact 允许下载面或
accepted-evidence 检索，也没有 DSH 工具入口。

## 无 key 合成 replay 验收包

`fixtures/dsh_replay/synthetic_review_gated_workflow.session.jsonl` 是公开合成的
有序步骤，`*.workspace.expected.json` 是独立的结果断言。运行
`tools/verify_dsh_synthetic_replay.py` 时，只 fake Sciverse 网络适配器，其他仍走真实
Loopback 领域层：任务创建、计划批准、显式同意、幂等账本、候选筛选、已接受证据图和
`cosmatter.artifact/v1`。执行不读取 `.env`、不调用 provider，输出也不含合成问题、
token、URL、任务 ID、正文或 provider response。

```powershell
Set-Location D:\CosMatter\development\CosMatter
.\.venv\Scripts\python.exe tools\verify_dsh_synthetic_replay.py
```

`tests/test_dsh_synthetic_replay.py` 还会把 `workspace.expected` 篡改为错误候选数，
确认 replay fail closed 而不回显 fixture 内容；编译后 DSH client 的真实 HTTP 装配仍
由 `tests/test_dsh_loopback_clients.py` 覆盖。

## 阶段契约投影（只读、非执行）

`cosmatter_stage_contract` 经 observability bundle 调用
`GET /api/runs/<run_id>/stage-contract`，为九个固定阶段返回：完成条件符号、人工门、
预期输出类别、非执行恢复路线、当前计数与 `runtime_safety` 二值信号。它不复制运行时
不变量审计细节，也不包含问题、候选、URL、全文、来源摘录、provider 内容或密钥。

恢复路线仅是固定的展示标签，不能授予同意、重新调用 provider、修改任务或接受证据。
Python 和编译后的 TypeScript client 都对完整固定模板进行校验；未知字段或篡改的恢复
路线会被拒绝。

## 固定工作流 DAG（只读、非调度）

`cosmatter_workflow_dag` 调用 `GET /api/runs/<run_id>/workflow-dag`，读取受版本控制的
九阶段线性声明：每阶段只依赖前一阶段，`max_concurrency` 固定为 `1`，并只显示预登记的
descriptor、数据等级和执行类别。返回的 `eligible_stages` 至多有一个元素，且只表示本地
工件就绪；它绝不等同于同意、调度、provider dispatch、retry 或任何后台任务。

Python 与编译后的 TypeScript client 均拒绝未知字段、非线性依赖、未知 descriptor、并发值
变化和“调度器”状态变化。该能力还没有受控执行器、取消队列或跨会话任务恢复功能。

## 聚合运行遥测（只读、非账单）

`cosmatter_operational_telemetry` 经 observability bundle 调用
`GET /api/runs/<run_id>/operational-telemetry`。它把本地已验证的 provider receipt
按 provider、操作和 HTTP 结果类别计数；把外部 dispatch 按完成、未完成和未知结果计数；
仅在已存在人工复核的 `evaluation_api_cost_latency.json` 时投影其聚合成本/延迟。

它不估算价格、延迟、配额或缓存命中，不把本地计时冒充 provider 性能，也不输出 request
ID、摘要、query hash、问题、URL、任务 ID、路径、全文、provider payload 或密钥。未知/未完成
dispatch 是安全注意信号，不能触发自动 retry。

## 跨会话本地提醒（只读、非调度）

`GET /api/reminder-board` 只返回运行 ID、最早未完成阶段的门禁类别、运行时注意、未知
external outcome 以及决策记忆中已到期 todo 的固定行动标签；它不读 Markdown 正文，也不
输出问题、来源、全文、URL、任务 ID 或密钥。工作台每 30 秒在本地读取时刷新该面板。
关闭页面或会话不会造成任何任务执行；`overdue` 只表示下次观察时发现的到期事项。

以 `?api=local` 打开工作台时，侧栏每 10 秒只读取阶段契约和聚合遥测，并显示下一阶段、
人工门、固定恢复标签、注意状态和聚合调用数。该面板没有重试、授权、解析或检索按钮；轮询
失败只显示“正在读取”，不会改变运行或暗示 provider 状态。

## 组合故障实验室与 Harness recipe

`tools/diagnose_dsh_plugin_combinations.py` 对所选 bundle（或 `--all-pairs`）在每次
新建的临时 `DSH_HOME` 中只执行本地 bundle 的安装与 `--dump-config`；不加载 `.env`、
不启动 API、provider 或会话。失败时，它以 delta-debugging 给出 1-minimal 的包名集，
报告中没有绝对路径、问题、文献、token 或运行工件。

```powershell
.\.venv\Scripts\python.exe tools\diagnose_dsh_plugin_combinations.py --packages @cosmatter/dsh-mission-plugin,@cosmatter/dsh-observability-plugin
.\.venv\Scripts\python.exe tools\diagnose_dsh_plugin_combinations.py --all-pairs
```

`configs/dsh_harness_recipe.json` 固定七 bundle 的兼容矩阵、市场快照 diff、第三方
准入和合成 replay；`tools/verify_dsh_harness_recipe.py` 产生可比较但不带科研分数的
报告，包含 OS、Python、Node、DSH、局部校验耗时、安全边界与已知限制：

```powershell
.\.venv\Scripts\python.exe tools\verify_dsh_harness_recipe.py
```

它不把本地耗时冒充 provider 延迟，也不从合成 fixture 推出科研质量或真实 provider
可用性。

## 第三方 bundle 准入与市场摄取防火墙

`configs/dsh_market_snapshot.json` 只是人工审阅过的公开发现快照：所有候选均为
`untrusted_discovery_only`，没有可执行安装规范，且不含 `.env`、本地路径、会话、
论文或运行数据。生产 bundle 只读取
`configs/dsh_third_party_plugin_admissions.json`；当前 allowlist 仅允许仓库自有的
`@cosmatter/*` 七包，第三方数量为零。快照断网或变动都不能影响 profile。

快照自身的变更也不能静默通过：`configs/dsh_market_snapshot.baseline.json` 保存冻结基线，
`configs/dsh_market_snapshot_review.json` 只保存基线/当前 SHA-256、候选变更数量、变更
指纹、日期和审阅者；不复制 URL 或候选正文。每次修改快照后必须人工更新该审阅记录，并运行：

```powershell
.\.venv\Scripts\python.exe tools\verify_dsh_market_snapshot_review.py
```

未来引入第三方包前，必须先在隔离目录运行：

```powershell
.\.venv\Scripts\python.exe tools\audit_dsh_plugin_candidate.py --candidate-dir <staged-candidate-dir>
```

该命令不安装或执行候选；只报告生命周期脚本、动态执行、进程启动、环境变量、网络
外发和凭据引用等静态风险信号，报告不回显源代码或绝对路径。任何 HIGH 风险均阻断
准入。人工准入记录还必须包含 pin 的源码提交、包 SHA-256、许可、权限审计、责任人、
复审过期日与回滚说明。随后运行：

```powershell
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_admission.py
```

它会拒绝未批准的第三方 production spec、未经当前 diff 审阅的市场快照，以及任何自有
production bundle 引用市场快照。

## 试点状态与发布门禁

已执行的隔离运行 `e2e_sciverse_deepseek_v4_flash_20260828` 记录了：

- DeepSeek `deepseek-v4-flash` 仅生成 `untrusted_draft`；执行计划来自单独的
  有界批准输入。
- Sciverse 主检索两次、反例检索一次；回执汇总为
  `sciverse:agentic_search=3`，去重后 44 个候选。
- 所有 44 个候选均由上游标为 `is_content_accessible=false`。因此全文端点和
  MinerU 没有被调用；就绪度正确停在 `next_stage=screening`。

这证明元数据检索、回执、脱敏 UI 投影和全文门禁可工作；它**不**证明 Sciverse
全文、MinerU 解析、Source Map、EvidenceCard 或公开发布已验收。完成真实发布前
仍需要一个具有上游全文访问声明或成功的显式哈希内容确认的候选、人工完整筛选、
授权全文来源、人工证据审核，以及脱敏的性能/费用/失败模式记录。

## 发布前命令

```powershell
Set-Location D:\CosMatter\development\CosMatter
$env:PATH = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64;$env:PATH"
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -q

# 无 key 的版本矩阵与发布文件门禁；第二条会在临时 DSH_HOME 中
# 打包七个 tarball、安装到干净 profile 并检查 --dump-config。
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_release.py
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_release.py --profile-smoke
.\.venv\Scripts\python.exe tools\verify_dsh_synthetic_replay.py
.\.venv\Scripts\python.exe tools\verify_dsh_harness_recipe.py
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_admission.py

# 对一个已经存在的本地 run 额外执行；false 是安全阻断信号，不能用重放消除。
.\.venv\Scripts\cosmatter.exe audit-runtime-invariants --run-id <run_id>

Set-Location frontend
npm run check
npm test

Set-Location ..
& 'C:\Program Files\Git\cmd\git.exe' -c safe.directory='D:/CosMatter/development/CosMatter' diff --check
```

各 bundle 的 `npm pack --dry-run` 必须确认只发布其 `lib`、`README.md` 和
`cordis.patch.yml` 等 allowlist 文件；根 `.gitignore` 也会忽略
`plugins/*/node_modules/` 与生成的 `src/*.egg-info/`。
