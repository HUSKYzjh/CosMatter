# 文献候选筛选门禁

检索返回的是候选题录，不是相关性结论。CosMatter 在检索与全文解析之间增加人工可审计的筛选工件：

```text
检索候选历史
  -> create-candidate-screening-template
  -> 人工逐项纳入 / 排除 / 待补元数据
  -> record-candidate-screening
  -> mineru-submit-url
```

`candidate_screening_template.json` 为当前扁平候选集中的每一篇文献创建一个空槽位。审核结果必须覆盖当前全部候选，且每个 `document_id` 只能出现一次：

- `include_for_fulltext`：只允许使用材料、性质、范围、方法、主证据或反证据等正向理由；
- `exclude`：只允许使用对象/性质超出范围、综述或协议、重复版本、元数据不足等排除理由；
- `needs_metadata_review`：只允许使用 `not_enough_metadata`。

完成审核后的 `candidate_screening.json` 不保存标题、查询词、摘要、全文或人工自由文本，仅保存文献标识、决定和标准化理由代码。它与当前候选集合严格匹配；任意新增检索结果都会使旧筛选失效，必须重新审核。

`mineru-submit-url` 现在要求目标文献同时满足：来自本次候选集、当前候选历史中的上游全文路由声明或哈希内容确认、在当前筛选工件中被标记为 `include_for_fulltext`。Sciverse 的语义检索命中若带有非空 `doc_id`，按其 SDK 契约表示存在可由 `read_content` 使用的全文 artifact；显式 `is_content_accessible=false` 仍优先拒绝。因此外部 PDF 解析不会绕过“检索—筛选—人工批准”的链路。

当 Sciverse 命中既没有非空 `doc_id`，又未给出明确可读声明，或明确返回 `is_content_accessible=false` 时，不能改写候选 JSON。完成完整人工筛选后，用户可显式以 `sciverse-read-context` 将一个有界正文窗口写到运行目录外的审阅文件；成功读取只会在运行内留下与候选集指纹绑定的 `document_id`、回执 ID 和正文 SHA-256 确认。确认不保存正文或 URL，候选历史变化即失效。
