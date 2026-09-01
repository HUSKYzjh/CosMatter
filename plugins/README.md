# CosMatter DSH 插件组

CosMatter 的 Python 领域层仍是任务工件、证据门禁和审计记录的唯一
真相源。下面的包只通过 `127.0.0.1` loopback API 访问该领域层；它们不
直接读取资料目录、密钥或私有全文。

| 包 | DSH 工具 | 自动化边界 |
| --- | --- | --- |
| `dsh-cosmatter-mission-plugin` | `cosmatter_mission_create` | 仅创建有界本地任务；无模型、检索、证据接受或计划批准。 |
| `dsh-cosmatter-observability-plugin` | `cosmatter_workflow_status` | 只读返回下一阶段及各阶段计数；不读取来源内容、不调度提供商、不写入工件或改变审核/同意状态。 |
| `dsh-cosmatter-policy-plugin` | `cosmatter_plugin_catalogue`、`cosmatter_plugin_authorization_plan` | 只读能力目录和非执行授权边界判断；不记录同意、不调度适配器。 |
| `dsh-cosmatter-research-plugin` | `cosmatter_research_plan_draft`、`cosmatter_research_plan_approve`、`cosmatter_research_query_execute` | 仅在工具调用提供精确、任务范围同意时，由 loopback 后端生成不可信 DeepSeek 计划草案或执行已批准的元数据检索；不读取全文、不调用 MinerU、不接受证据。 |
| `dsh-cosmatter-review-plugin` | `cosmatter_candidate_screening_template`、`cosmatter_candidate_screening_record` | 只读候选元数据并记录完整人工筛选；不调用提供商、不调度全文或 MinerU、不接受证据。 |
| `dsh-cosmatter-document-plugin` | `cosmatter_mineru_source_submit`、`cosmatter_mineru_task_poll` | 仅在候选已有上游全文访问声明或当前哈希确认、完整人工筛选和三项精确授权后调度/轮询 MinerU；只返回任务元数据，不返回 URL、解析正文或证据。 |
| `dsh-cosmatter-graph-plugin` | `cosmatter_graph_query`、`cosmatter_accepted_evidence_search`、`cosmatter_graph_plan`、`cosmatter_graph_review_request` | 已接受证据的只读图投影与有界检索；计划与审核请求始终待人工处理。 |

为避免影响默认 profile，先使用单独 profile。DSH 将 `plugin` 参数转交给 pnpm，
因此可在一条命令中直接安装全部七个 bundle：

在安装前先确认本机的受支持组合；`pnpm` 缺失时，`dsh plugin add` 会在初始化
profile 后停止，而不是降级到 npm。当前兼容矩阵固定为 DSH `0.1.0-rc.7`、Node
`24.19.0`、npm `11.17.0`、pnpm `11.22.0`：

```powershell
dsh --version
node --version
npm --version
pnpm --version
```

如需一次性检查版本、发布物和干净 profile（不读取 `.env`，不调用任何 provider），在
仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe tools\verify_dsh_plugin_release.py --profile-smoke
```

```powershell
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-mission-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-observability-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-policy-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-research-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-review-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-document-plugin D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-graph-plugin
dsh --profile cosmatter-graph-test --dump-config
```

如需逐个替换、调试或回滚，可分别安装本地包：

```powershell
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-mission-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-observability-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-policy-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-research-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-review-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-document-plugin
dsh plugin --profile cosmatter-graph-test add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-graph-plugin
dsh --profile cosmatter-graph-test --dump-config
```

`cosmatter-core` 和 `potential-scope` 目前仍是 Python 侧的静态契约/领域
模块，不应被误认为已经可安装的 DSH bundle。新增 DSH 包必须先通过各自
的 TypeScript 生命周期测试和 Python 领域边界测试。

`dsh-plugin-group.json` 的 `catalogue_coverage` 是完整静态能力目录的强制
映射：标为 `exposed` 的项目已由相应 bundle 暴露；标为
`python_or_human_boundary` 的项目明确保留在 Python 领域层或人工门禁，不能因
安装插件组而被隐式调度或接受为证据。
