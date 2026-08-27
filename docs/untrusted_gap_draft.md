# 受控 Research-Gap 假设草案

`draft-gap-hypotheses` 是“假设生成”步骤的受控实现。它只在以下门禁均已通过后调用 DeepSeek：

1. 存在人工批准的 `flight_plan.json`；
2. 每一条已批准的反证检索式都已出现在 `retrieval_candidates.json` 的执行历史中；
3. 存在由已定位、已复核证据形成的 `condition_matrix.json`。

传给模型的是任务边界、条件分歧字段和 EvidenceCard 标识符；不传论文全文、原文引文、URL、凭证或服务响应。模型输出写入本地 `research_gap_draft.json`，其信任状态固定为 `untrusted_llm_research_gap_draft_not_a_candidate_or_finding`。

该文件只供人工阅读和后续检索设计使用：

- 不被 `generate-gap-candidates` 读取；
- 不被 `build-report` 或 UI 导出读取；
- 不能作为文献事实、Research Gap 候选或科学结论；
- 不会将草案正文写入 CLI 输出或审计事件。

正式的 `research_gap_candidates.json` 仍由条件分歧、已接受 EvidenceCard、反证检索执行记录和人工复核共同约束。每一项正式候选必须重新绑定证据，并进入专家评估，才可出现在报告中。
