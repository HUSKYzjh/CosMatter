# CosMatter UI JSON 契约（v1.0）

`cosmatter export-ui` 是 Python 运行时与静态浏览器页面之间的唯一数据边界。浏览器只读取由该命令导出的 JSON 文件，或由用户通过“导入 JSON 工件”明确选择的同格式文件；首版没有 HTTP API。

## 安全边界

- 不输出 `.env`、令牌、请求头、工具调用参数、完整审计事件或模型隐藏推理。
- 不输出 PDF、HTML 全文、缓存或未获准的长摘录。
- `evidence_cards` 只可含审核状态为 `accepted`、许可范围内的 `quote` 短摘录。首版导出器不从运行日志推断证据，因此默认是空数组。
- `mission_report` 只有通过发布门禁后才可填充；首版默认为 `null`。
- UI 只显示 `status.mission_state` 等摘要；可投影固定白名单动作形成 `timeline`，但不展示 `events.jsonl` 的 actor、event ID、payload、请求记录、查询文本或审核理由。

## 顶层结构

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-08-03T00:00:00+00:00",
  "mission": {"mission_id": "...", "question": "...", "material": "...", "property_name": "...", "scope": "...", "source_policy": "authorized"},
  "fleet_assignment": {"assignment_id": "...", "fleet_type": "route_diagnostics", "display_name_zh": "航道诊断舰队", "display_name_en": "Route Diagnostics Fleet", "mission_type": "literature_discrepancy", "reason": "...", "release_gate": "cross_check_review"},
  "status": {"mission_state": "INTAKE", "retry_count": 0, "retry_budget": 2, "return_reason": null},
  "stations": [{"station_type": "question_intake", "status": "active"}],
  "facilities": [{"facility_type": "trajectory_overlay", "status": "queued"}],
  "evidence_cards": [],
  "verification_decisions": [],
  "condition_matrix": [],
  "timeline": [{"station_type": "search_selection", "action": "主检索已完成", "state": "RETRIEVE", "occurred_at": "..."}],
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

未知的顶层字段应由前端忽略，缺失必填顶层字段则拒绝导入。公开演示夹具见 [`../../examples/ui-demo/route_diagnostics.json`](../../examples/ui-demo/route_diagnostics.json)。
