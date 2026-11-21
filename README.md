# CosMatter · 星际材料导航站

CosMatter 是用于材料计算与科学文献阅读的 DeepSeek Harness（DSH）插件组。可以从聊天里核对钙钛矿超胞配比、处理分子动力学（MD）结果，并从已审核的文献记录回到论文和图表。

## 在 DSH 中使用

使用图形工作台时，运行 `cosmatter preview-ui --solid --api --port 0` 并打开终端给出的地址。三个常用入口如下。

| 研究任务 | 工作台入口 | 可取得的结果 |
|---|---|---|
| 从多篇论文核对同一性质 | 打开本机运行 → 文献星图 → 跨文献证据对照 | 按性质、样品条件和审核状态筛选。表中保留已核对的数值、原单位、定位及待补的论文；有可复查的来源时可直接打开对应证据卡。可将全部匹配行导出为 CSV。 |
| 核算组分或 MD 电场响应 | DSH 插件 → 工具目录 → 授权类型选「本机计算」，展开工具 | 输入 Pb 分数可查看整数占位与带标号排列数。输入对称正负电场下的极化或应变均值可得纵向介电或逆压电响应。计算在浏览器完成，与 DSH 使用同一份公式。 |
| 接续其他运行的审核 | 首页 → 续航任务 → 跨任务待办；运行内也可在任务概览中查看 | 按优先级和运行 ID 查找，点运行链接可在新标签打开该任务，保留当前页面的输入。 |

在已安装本项目的环境中运行 `cosmatter repair-dsh-bundles`，再用 `cosmatter preview-ui --solid --api --port 0` 启动工作台。打开终端显示的本机地址，点击「DSH 插件」，按该页面的实际端口核验后复制启动命令。已有任务的启动命令会带上运行 ID。[安装和核验](docs/DSH_PLUGIN_GROUP_RELEASE_READINESS.zh-CN.md)

| 想做什么 | 给 DSH 的工具与输入 | 怎样解释结果 |
|---|---|---|
| 为 (PbₓSr₁₋ₓ)TiO₃ 的 8×8×8 超胞选组分 | `cosmatter_pst_occupancy_count`，传 `{"pb_fraction":"0.5"}` | 512 个 A 位中 Pb、Sr 各 256 个，带标号的占位排列数是 C(512,256)。输入 `"1/3"` 可查相邻可实现组分。 |
| 从正负电场的 MD 均值算纵向响应 | `cosmatter_md_field_response`，传 `{"axis":"z","mechanical_boundary":"fixed_stress","observable":"normal_strain","field_magnitude_V_per_m":1000000,"mean_at_minus_field":-0.00005,"mean_at_plus_field":0.00005}` | 这组合成输入的逆压电 d₃₃ 为 50 pm/V。求相对介电常数时选 `polarization_C_per_m2` 并输入对应极化均值。 |
| 从论文定位核对一个数值 | 在已有审核记录的运行调用 `cosmatter_accepted_evidence_search`，提供 `run_id`、论文 `doi` 和卡片保存的 `locator` | 核对返回的主张、样品条件和来源。打开对应证据链接复查原文位置。没有命中时，应先查该运行的收录与审核记录。 |

两项计算均可离线执行。有限差分估计要求正负电场同幅、同温、处于同一极化分支，逆压电测量还要求固定应力并允许应变弛豫。实际材料上的收敛性与不确定度需用不同场强、独立轨迹分别验证。[计算工具参数](plugins/dsh-cosmatter-research-plugin/README.md) · [文献阅读工具](plugins/dsh-cosmatter-graph-plugin/README.md)

### 在 Orca 工作树终端中使用

用安装了 CosMatter 的终端运行下列命令。占位计算会直接返回 JSON。查文献时，将运行 ID 和端口换成当前工作台的值，图号采用证据卡保存的标记。

```powershell
cosmatter dsh-calculate pst-occupancy --pb-fraction 1/3
cosmatter dsh-evidence --run-id YOUR_RUN --port 8765 --doi 10.1038/s41467-017-01361-2 --locator figure:5
```

Orca 可以分配工作树和跟踪尝试。CosMatter 返回计算的输入、单位或证据卡链接，供协调者核对。若工作树没有单独安装 CosMatter，可用原安装目录的 `.venv\Scripts\cosmatter.exe` 执行上述命令。[Orca 分工、命令和验收记录](docs/DSH_PUBLIC_PLUGIN_RESEARCH_AND_RECOMMENDATIONS_2026-08-29.zh-CN.md#orca-如何接入-cosmatter-的研究舰队)

已有跨文献对照表时，可从「文献星图 → 跨文献证据对照 → 导出 Orca 核验任务」下载当前筛选的任务单。每篇论文对应一项任务，同篇命中的证据卡归入同一项。任务说明提供本机读取地址，要求返回原单位、定位或具体缺口。确认要交给哪一个 Orca Run 后，再在协调终端创建任务。[导入任务单](docs/DSH_PUBLIC_PLUGIN_RESEARCH_AND_RECOMMENDATIONS_2026-08-29.zh-CN.md#从跨文献对照表导入-orca-任务)

当前 M1.2 已实现：

- `MissionBrief`、`EvidenceCard`、`FlightPlan` 等可序列化数据契约；
- 受控任务状态机与拒绝非法状态跳转；
- 追加式 JSONL 黑匣子日志（不写入密钥）；
- Sciverse 适配器的配置、重试、限流和权限检查边界；
- 无密钥可运行的 `check-config`、`create-mission`、`assign-fleet`、`export-ui` 与 `demo-flow` 命令；
- 五支舰队的可校验 YAML 配置；调度中心只选择一支主舰队，并记录分派理由与所需设施；
- 静态 HTML 舰桥：只导入已脱敏的本地 UI JSON，不调用浏览器网络接口。

## 初赛提交与复现

2026 年 8 月赛制要求初赛同时提供源代码与 PDF/LaTeX 文献调研报告。提交步骤、资源披露、引用审计和势函数框架测试的边界见 [`docs/competition_submission_2026_08.zh-CN.md`](docs/competition_submission_2026_08.zh-CN.md)。

- 初赛报告源：`python -m cosmatter export-latex-report --run-id YOUR_RUN --compile`；
- 可复现默认参数：[`configs/reproducibility.example.json`](configs/reproducibility.example.json)；
- 开源许可证：MIT（仅覆盖本仓库代码与文档，不授予第三方数据或 API 内容的再分发权限）。
- 数据与安全边界：[数据治理](docs/data-governance.md)、[评测规范](docs/evaluation.md)、[安全政策](SECURITY.md)。
- 进阶势函数边界框架：计划、人工执行协议、外部汇总结果比较与待批准的边界加密任务；不会自行提交外部计算。
- 引用与贡献：[CITATION.cff](CITATION.cff)、[CONTRIBUTING.md](CONTRIBUTING.md)；修订要求的逐项映射见 [docs/competition_requirement_traceability.zh-CN.md](docs/competition_requirement_traceability.zh-CN.md)。

材料证据、检索评分、DSH 启用和 MD 计划的已知问题、修复状态与验收顺序见[全项目审查与优化方案](docs/PROJECT_OPTIMIZATION_REVIEW_2026-11-19.zh-CN.md)。

## 快速开始

在 PowerShell 中（推荐在独立虚拟环境内）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\cosmatter.ps1 check-config
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "为什么两篇论文对 BiFeO3 应变相变有不同结论？" `
  --material "BiFeO3" `
  --property "phase stability" `
  --scope "epitaxial thin films" `
  --run-id bfo_ui_demo `
  --mission-id mission_bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter assign-fleet `
  --question "为什么两篇论文对 BiFeO3 应变相变有不同结论？" `
  --material "BiFeO3" `
  --property "phase stability" `
  --scope "epitaxial thin films" `
  --run-id bfo_ui_demo `
  --mission-id mission_bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter export-ui --run-id bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter demo-flow --run-id demo_cosmatter_001
```

`create-mission` 与 `assign-fleet` 需要在同一运行目录使用相同的 `--mission-id`，这样 `export-ui` 才能验证两个工件确实属于同一任务。`check-config` 仅报告配置项是否存在，绝不回显令牌。标准工作区布局下，运行时只读开发环境根目录的 `../.env`（即 `development/.env`）；该文件受保护、不会被编辑或提交。字段模板位于相邻的 `../AIforResearch-Materials-Agent-Workspace/env.txt`。案例运行工件写入 `../../case-data/runtime/runs/<run_id>/events.jsonl`，私有缓存写入 `../../case-data/runtime/private/`；它们均不提交到版本控制。

## 全量验收测试

从任意新开的 PowerShell 进入项目根目录后运行：

```powershell
.\scripts\acceptance.ps1
```

安装完成后，新开的 PowerShell 只需进入仓库根目录并使用 `.\cosmatter.ps1 <command>`；该启动器固定使用仓库 `.venv`，避免系统 Python 找不到 `cosmatter`。上面的长写法仍然等价。启动器不会读取或输出任何凭据；配置仍由 Python 进程按下述规则加载。

候选筛选完成后，可对最多 12 条已纳入候选做冲突安全的 DOI 补全，再重建阅读路线：

```powershell
.\cosmatter.ps1 enrich-screened-metadata --run-id YOUR_RUN
.\cosmatter.ps1 build-reading-guide --run-id YOUR_RUN
.\cosmatter.ps1 export-ui --run-id YOUR_RUN
```

补全只接受规范化标题精确一致且年份相容的 Crossref/OpenAlex 记录；多个 DOI 命中会保留为 `conflict`，不会模糊合并或改写原始候选。schema 1.4 阅读路线把当前候选按 `exact_material`、`mechanism_analogue`、`algorithm` 三个元数据轨道组织；新版 FlightPlan 可把每个主查询索引唯一绑定到一轨并冻结逐轨最低候选数，默认目标为 4/3/4。路线在可用时至少保留 1 条 `counterevidence_only`，并显式报告逐轨 `shortfall`；它不会猜测或自动执行补充查询。当任务明确禁止性质代理模型时，代理模型论文只能作为反证候选。路线还显示规范化 DOI、允许列表内的入选信号，以及 `provider_advertised` / `confirmed` / `failed_or_expired` / `metadata_only` 正文状态；只有与当前候选指纹绑定的成功读取才显示为 `confirmed`。这些轨道是确定性题名/任务边界启发式，不是相关性判断或性质预测；筛选、元数据和访问状态仍不等于科学证据。

候选身份另有一个不改写检索历史的对账层。先建立 `cosmatter.candidate-duplicate-queue/v1`；完全一致的规范化 DOI 可自动建立 canonical/alias，只有题名相同、DOI 不完整或 DOI 冲突时只能进入人工待对账队列：

```powershell
.\cosmatter.ps1 build-candidate-duplicate-queue --run-id YOUR_RUN
.\cosmatter.ps1 create-candidate-duplicate-review-template --run-id YOUR_RUN --output D:\private-review\candidate-duplicates.json
# 在私有环境完成全部待审组、改为 human_reviewed_candidate_duplicate_identity_decisions 后：
.\cosmatter.ps1 record-candidate-duplicate-reconciliation --run-id YOUR_RUN --input D:\private-review\candidate-duplicates.json
.\cosmatter.ps1 export-ui --run-id YOUR_RUN
```

人工决定只能是 `same_work`、`distinct_works` 或 `unresolved`，并须使用固定理由码。模板不复制题名；运行内对账只保存候选 ID、状态、哈希绑定与计数修订史。标题相同从不自动认定为同一文献，对账结果也不是科学证据。

如需可选地补全当前全部候选，而不仅是已纳入全文的候选，可显式追加 `--all-candidates`。每次仍最多处理 12 条，重复同一命令会按候选顺序跳过当前指纹下已记录项并继续；已有 DOI 的候选不会再次发送标题。累计工件只追加新文献记录，不会让后续批次覆盖既有解析或冲突，输出的 `remaining_document_count` 与 `complete` 可用于断点验收。

已确认的本地 Sciverse 上下文可用 `prepare-sciverse-context-review` 生成运行目录外的私有待审池。该步骤会复核回执、文献、offset、内容哈希和字符数，不调用网络；输出仍不是 Source Map 或证据。随后可创建不含原文的人工选段模板，并用 `record-sciverse-context-source-map` 将经哈希复核的精确短段落写成 Source Map；受委托自动试点必须显式加开关，且其 Source Map 不能进入正式材料事实链。

Sciverse 正文窗口参数由 `cosmatter.operation-parameter-contracts/v1` 单一契约定义：offset 不小于 0，limit 为 200–4000，默认 2000。CLI 在参数解析期应用该范围；本地 API 能力快照与 MCP 的 `cosmatter_get_operation_parameter_contracts` 只读返回同一契约，不执行提供商调用，也不授予浏览器或 Agent 全文写盘权限。

参数解析期的 Sciverse 窗口拒绝会以 `cosmatter.validation-rejection/v1` 追加到既有运行的本地安全账本，并由 `cosmatter.operational-telemetry/v2` 按命令类别和固定原因码汇总。账本不记录参数值、路径、查询、文献标识或正文；前端与 DSH 只读投影只显示类别、次数及是否需要注意，不据此自动重试。

PST 的 MD-only 构型搜索目前只开放“计划 + 合成算法回归”两步。先用显式 reviewed JSON 冻结组分、势场/协议哈希、目标、预算、失败与停止规则，再运行不调用 MD、网络或外部模型的同预算消融：

```powershell
.\cosmatter.ps1 create-pst-configuration-search-plan --run-id YOUR_RUN --input D:\private-review\pst-search-plan.json
.\cosmatter.ps1 run-pst-synthetic-ablation --run-id YOUR_RUN
```

计划工件始终为 `execution_authorized = false`；合成回归默认比较均匀随机、固定基数 EDA、短程有序引导和 MRMT，使用 3 个冻结搜索种子、每组 48 个唯一构型。所有方法的 `property_prediction_count = 0`，输出明确不是 PST 介电/压电证据。真实 MD 回执、晋级和 Pareto 验证尚未接入，不能由此命令启动。

该入口依次执行 Python 测试、前端类型检查与测试、DSH 发布/回放/配方门禁、七个本地 DSH 包测试和 `npm pack --dry-run`，最后检查 Git 空白错误。它不读取 `.env`，不调用任何提供商。如需指定解释器，可传入 `-Python C:\Python314\python.exe`；仅检查 Python 套件时可运行 `.\scripts\test-all.ps1`。完整通过时，最后单独输出 `OK - CosMatter full local acceptance passed.`。

若需保存验收收据，请显式指定一个新 JSON 文件：

```powershell
.\scripts\acceptance.ps1 -ReportPath D:\safe-local-folder\cosmatter-acceptance.json
```

收据只包含固定步骤名、通过/失败状态、耗时、起止时间和是否启用了严格 DSH 步骤；不包含命令、路径、测试日志、问题、URL、全文、提供商响应或凭据。默认拒绝覆盖已有收据；仅在明确需要替换时才附加 `-OverwriteReport`。

验收收据使用 schema `1.1`，并附带对全部固定字段的 SHA-256 内容绑定。验证脚本兼容 Windows PowerShell 5 和 PowerShell 7，可离线验证且不会输出收据路径或原始内容：

```powershell
.\scripts\verify-acceptance-receipt.ps1 -Path D:\safe-local-folder\cosmatter-acceptance.json
```

## 本机只读界面预览

优先使用仅绑定 `127.0.0.1` 的 Solid 预览服务。它只服务前端静态文件，且仅在明确给出 `-RunId` 时暴露该运行已经导出的脱敏 `/ui.json`：

```powershell
.\scripts\start-solid-preview.ps1 -RunId bfo_ui_demo
```

脚本与 Python 运行时使用相同的数据根目录规则：优先 `COSMATTER_DATA_ROOT`，否则使用工作区 `case-data/runtime`，最后才回退到独立仓库的本地目录。它不会列出运行目录、读取 `.env`、暴露事件日志、私有缓存或任意路径。

不要附加 `-Api`，除非是在明确授权的本地受控任务会话中需要写入 API；`-Api` 会启用独立的 allowlisted 本机任务接口，因此不属于只读预览模式。页面初始显示合成演示数据；用户仍可显式选择 [`examples/ui-demo/route_diagnostics.json`](examples/ui-demo/route_diagnostics.json) 进行浏览器内导入。

UI JSON 的字段、安全边界和扩展顺序见 [UI JSON 契约](docs/architecture/01_UI_JSON契约.md)。

静态舰桥现分为任务舰桥、研究工作流、星图网络、论文导读和研究拓展五页，并提供深色、浅色、护眼主题；页面只消费用户选择的本地 JSON 工件。见 [舰桥多页面 UI 设计](docs/architecture/02_舰桥多页面UI设计.md)。

## 当前边界

`SciverseAdapter` 使用官方 `sciverse` Python SDK 的有界 `semantic_search` 与 `read_content` 调用。上游可访问声明与本次成功读取被明确分开；成功只保存内容哈希、回执 ID 和 UTC 确认时间，失败只保存安全原因码。候选仍须通过筛选和 Source Map 才能进入证据链。详见 [SciVerse 提供方契约](docs/SCIVERSE_PROVIDER_CONTRACT.zh-CN.md)。当前仓库仍处于证据优先基础设施阶段：不会把没有原文定位的文本当作科学事实，也不会在首版执行任意代码或提交外部计算。

后续架构、舰队专用设施、数据治理与 GitHub 发布边界见 [项目结构与后续路线图](docs/architecture/00_项目结构与后续路线图.md)。
