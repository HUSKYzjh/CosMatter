# SciVerse 提供方契约与全文门禁

CosMatter 使用官方 Python SDK `sciverse==0.7.1`，通过
`AgentToolsClient` 调用，而不是自行维护 HTTP 鉴权与端点实现。

| CosMatter 操作 | 官方 SDK 方法 | 官方 REST 端点 | 边界 |
| --- | --- | --- | --- |
| 有界语义检索 | `semantic_search(query, top_k, mode="balanced")` | `POST /agentic-search` | 返回段落、`doc_id`、标题及定位；仅是候选，不是证据。 |
| 有界全文窗口 | `read_content(doc_id, offset, limit)` | `GET /content` | 仅在人工筛选和显式本地阅读命令后调用；窗口上限仍为 4,000 字符。 |
| 结构化元数据检索 | `search_papers(...)` | `POST /meta-search` | 后续可用于 DOI/年份/期刊过滤；不返回段落正文。 |
| 字段目录 | `list_catalog()` | `GET /meta-catalog` | 后续构建精确筛选器前使用。 |

SDK 自行处理 token、请求 ID、分页和官方请求格式；CosMatter 只保留任务范围
授权、候选审查、回执脱敏与证据门禁。

## `is_content_accessible` 的正确含义

官方 `semantic_search` 文档保证返回 `doc_id` 和正文片段，但不承诺每个命中都会
带 `is_content_accessible`。因此：

- 字段明确为 `true`：CosMatter 才把它视为上游提供的全文访问声明；
- 字段为 `false` 或缺失：不会自动读取 `/content`，也不能直接提交 MinerU；
- DOI、摘要、搜索片段或开放链接都不能替代该声明；
- HTTP 200 只说明检索成功，不能证明该 `doc_id` 有完整正文访问权。

这解释了当前试点：三次检索均成功，但 44 个候选均被上游显式标为不可访问，故
系统没有自动调用 `/content` 或 MinerU。

## 人工确认读取

官方文档不把该字段作为 `semantic_search` 的必有返回项，因此缺失或 `false` 不应被
篡改为 `true`。如人工完整筛选后仍需要核对一篇候选，可由用户在本地显式执行
`sciverse-read-context`，读取一个有界窗口到运行目录外的新 `.txt`/`.md` 审阅文件。

命令成功后仅在运行目录内写入 `content_access_confirmations.json`：任务 ID、当前
候选集指纹、文献 ID、回执 ID 和正文 SHA-256。该确认不保存正文、URL、token 或
请求 ID，也不构成科学证据；但它可作为当前未变更候选集的受控全文访问证明，使
该候选在后续人工确认来源和三项 MinerU 授权均满足时进入解析。候选历史一旦变化，
确认自动失效。

## 配置与验证

```powershell
Set-Location D:\CosMatter\development\CosMatter
.\.venv\Scripts\python.exe -m pip install -e .
sciverse auth status
```

SDK 按官方优先级解析 token：显式参数、`SCIVERSE_API_TOKEN`、
`~/.sciverse/credentials.json`。CosMatter 仍只读取受保护的工作区 `.env` 或显式
`COSMATTER_ENV_FILE`，不会把 token 返回给 UI、DSH 或运行工件。

## 后续修复方向

若某个账户持续只返回不可访问候选，应先完成 CosMatter 的人工筛选，再以
`sciverse-read-context` 或官方 CLI 的 `sciverse content <DOC_ID>` 对同一 `doc_id`
做人工、受控验证，并把请求 ID 交给 SciVerse 支持确认账号内容权限。不能通过修改
候选 JSON 或强制设置 `is_content_accessible=true` 绕过门禁。
