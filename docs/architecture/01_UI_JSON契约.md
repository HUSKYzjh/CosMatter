# CosMatter UI JSON 契约（v1.0）

`cosmatter export-ui` 是 Python 运行时与浏览器页面之间的唯一数据边界。浏览器只读取由该命令导出的 JSON 文件、用户通过“导入 JSON 工件”明确选择的同格式文件，或 `preview-ui --solid --run-id <run_id>` 在 `127.0.0.1` 上暴露的该单一 `/ui.json`。后者不是通用 HTTP API：不附加 `--api` 时所有 `/api` 写入请求均被拒绝；带写能力的本机任务 API 必须显式启用并遵守独立授权门禁。

## 安全边界

- 不输出 `.env`、令牌、请求头、工具调用参数、完整审计事件或模型隐藏推理。
- 不输出 PDF、HTML 全文、缓存或未获准的长摘录。
- `evidence_cards` 只可含审核状态为 `accepted`、许可范围内的 `quote` 短摘录。首版导出器不从运行日志推断证据，因此默认是空数组。
- `mission_report` 只有通过发布门禁后才可填充；首版默认为 `null`。
- `delegated_test_boundary=true` 表示该运行带有永久受托技术试跑标记；此时导出器只保留任务和候选书目元数据，证据卡、来源片段、材料事实、条件矩阵、报告、评测与发布资格一律不投影。单个旧工件上的 `human_reviewed` 标签不能覆盖运行级边界。
- UI 只显示 `status.mission_state` 等摘要；可投影固定白名单动作形成 `timeline`，但不展示 `events.jsonl` 的 actor、event ID、payload、请求记录、查询文本或审核理由。

## 顶层结构

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-08-03T00:00:00+00:00",
  "delegated_test_boundary": false,
  "mission": {"mission_id": "...", "question": "...", "material": "...", "property_name": "...", "scope": "...", "source_policy": "authorized"},
  "fleet_assignment": {"assignment_id": "...", "fleet_type": "route_diagnostics", "display_name_zh": "航道诊断舰队", "display_name_en": "Route Diagnostics Fleet", "mission_type": "literature_discrepancy", "reason": "...", "release_gate": "cross_check_review"},
  "status": {"mission_state": "INTAKE", "retry_count": 0, "retry_budget": 2, "return_reason": null},
  "stations": [{"station_type": "question_intake", "status": "active"}],
  "facilities": [{"facility_type": "trajectory_overlay", "status": "queued"}],
  "evidence_cards": [],
  "verification_decisions": [],
  "condition_matrix": [],
  "timeline": [{"station_type": "search_selection", "action": "主检索已完成", "state": "RETRIEVE", "occurred_at": "..."}],
  "research_guide": {"trust_status": "derived_from_approved_artifacts", "items": []},
  "mission_report": null
}
```

`mission` 和 `fleet_assignment` 来自已验证的 `MissionBrief` 与 `FleetAssignment`。导出器会重新解析这两个工件，拒绝缺字段、非法枚举值和不一致的 `mission_id`。

## 可扩展字段

后续设施可以填充下列字段，但必须先经过对应门禁：

- `evidence_cards[]`：`evidence_id`、`claim`、`stance`、`conditions`、`review_status`、`provenance.document_id`、`provenance.locator`、许可范围内的 `quote`。
- `verification_decisions[]`：证据卡审核结论、缺失条件与拒绝原因。
- `condition_matrix[]`：条件簇、支持/反驳证据 ID 与未知项；布局不能被表述为因果结论。
- `mission_report`：已批准的结论、局限及下一步验证建议。
- `timeline[]`：仅含固定动作标签、工位、状态和发生时间的脱敏摘要；不能携带原始审计字段。
- `research_guide`：从已批准计划、候选历史和已接受证据导出的有界阅读路线；不含查询文本、评分、摘要或全文。

未知的顶层字段应由前端忽略，缺失必填顶层字段则拒绝导入。公开演示夹具见 [`../../examples/ui-demo/route_diagnostics.json`](../../examples/ui-demo/route_diagnostics.json)。

## Literature graph extension

`literature_graph` is a bounded navigation projection for the Graph page. It contains only allowlisted node and edge metadata:

- nodes: mission, candidate-paper metadata, accepted-evidence markers, OpenAlex/Crossref relation targets, and reviewer-recorded paper entities;
- edges: retrieval candidate, source provenance, citation/reference metadata, and reviewed paper-structure relations;
- never included: provider tokens, queries, ranking scores, raw responses, abstracts/full text, audit events, review reasons, or hidden reasoning.

Every node and edge carries a `trust_status`. Retrieval and bibliographic relations are navigation metadata, not scientific evidence or causal statements. The frontend caps imported graphs at 96 nodes and 144 edges.
