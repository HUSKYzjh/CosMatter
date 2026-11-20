# CosMatter graph plugin for DeepSeek Harness

This is an independent DeepSeek Harness bundle. It exposes four tools:

- `cosmatter_graph_query` reads a previously projected graph through the loopback-only CosMatter API.
- `cosmatter_accepted_evidence_search` searches within one run by keyword, exact evidence ID, document ID with an exact locator, or paper DOI with an optional locator. Results show each accepted card's claim and recorded location. A card with a verified local source mapping also has a reader link. **Copy DSH command** in the reader reopens that exact card.
- `cosmatter_graph_plan` writes an untrusted, non-executing graph-inspection draft for selected existing nodes.
- `cosmatter_graph_review_request` submits a pending human-review request; it cannot accept evidence or modify the graph.

The bundle accepts only `http://127.0.0.1` endpoints. It validates the complete
`cosmatter.graph-snapshot/v1` response and rejects raw quotations, private paths,
credentials, unreviewed evidence, and oversized responses. Graph projection is
performed explicitly by CosMatter (`cosmatter_project_accepted_evidence_graph`
through MCP or `POST /api/runs/<run_id>/graph/project`) before this bundle can read
`GET /api/runs/<run_id>/graph`.

Build and test locally:

```powershell
npm install
npm test
```

After the DeepSeek Harness CLI is installed, add this checkout to a profile:

```powershell
dsh plugin --profile cosmatter add D:\CosMatter\development\CosMatter\plugins\dsh-cosmatter-graph-plugin
```

The `dsh.bundle` manifest activates `cordis.patch.yml`. The plugin follows the
standard `apply(ctx)` shape and declares `inject = ['tools']`; tool registrations
and event effects are scoped to Cordis lifecycle cleanup.

## 按论文和图号读证据

启动本地 CosMatter API 并将插件安装到 DSH 的 `tui` profile 后，在 PowerShell 中把 `<run_id>` 换成工作台显示的运行 ID。第一个命令列出该运行中已记录相同 DOI 的审核卡，第二个命令按位置精确筛选。实际使用时，请复制第一步返回的完整 `locator`。如服务监听其他端口，追加 `--port` 和端口号。

```powershell
cosmatter dsh-evidence --run-id '<run_id>' --doi '10.1038/s41467-017-01361-2'
cosmatter dsh-evidence --run-id '<run_id>' --doi '10.1038/s41467-017-01361-2' --locator 'figure:5'
```

在 DSH 对话中也可以用相同的 `run_id`、`doi`、`locator` 调用 `cosmatter_accepted_evidence_search`。命令行最多展示 12 张卡，`matched_count` 给出匹配总数。零命中表示本次运行的已审核卡中没有符合条件的 DOI 和定位。已有卡若未记录 DOI，可以按原有 `document_id` 和 `locator` 查找。`review_status: accepted` 记录本地审核决定；实验是否已复现需另查复现记录。

**BFO 阅读实例。** Gomez 等在 2017 年发表的论文中，对一片 400 nm 的 BiFeO₃ 薄膜做直接压电力显微测量。图 5b、5c 对应两个扫描方向，图 5d 给出积分所用的曲线。正文分别报告 45 ± 6 和 40 ± 6 pC/N，给出的平均纵向压电系数为 43 ± 6 pC/N。2016 年预印本摘要写的是 46 ± 7 pC/N；整理资料时应记录所读版本，这两项属于同一工作。[发表版图 5](https://pmc.ncbi.nlm.nih.gov/articles/PMC5653648/#Fig5) · [预印本](https://arxiv.org/abs/1609.04250)

仓库中的这条 BFO 数值标为 `literature_mentioned`，尚无已审核的 Source Map。原生 DSH 集成检查用临时运行中的合成卡和测试审核决定验证检索与链接。[BFO 候选记录](../../examples/frozen/bfo_expanded_literature_observation_candidates_v2.json)
