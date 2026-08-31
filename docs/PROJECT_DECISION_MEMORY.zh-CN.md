# CosMatter 项目决策记忆（非科学证据）

`project_decision_memory/` 是本地项目运行数据的一部分，默认位于
`COSMATTER_DATA_ROOT`（或标准 `case-data/runtime`）下，不进入 Git、mission run、
报告、UI 导出、Artifact 下载或已批准证据检索。

它只能记录五类工程上下文：授权决定、已验证环境、故障恢复、运行偏好和待办。每条
记录以人工可编辑的 Markdown 为真相源，`decision_memory_index.json` 只是可重建的
元数据索引，索引不复制正文。论文、证据、claim、引用、DOI、PDF、MinerU、原文和
摘录词汇会被拒绝，因此不能把这里当作文献笔记或科学事实来源。

```powershell
Set-Location D:\CosMatter\development\CosMatter

# 输入严格 JSON，字段为 id/category/status/source/created_at/expires_on/title/body。
.\.venv\Scripts\cosmatter.exe record-decision-memory --input .\decision.json

# 人工编辑或删除 Markdown 后，重建索引；列表也绝不返回正文。
.\.venv\Scripts\cosmatter.exe rebuild-decision-memory
.\.venv\Scripts\cosmatter.exe list-decision-memory
```

`trust_status` 始终是
`project_operational_memory_not_scientific_evidence_or_report_source`。它明确不构成
授权本身、provider receipt、证据接受或科研结论。
