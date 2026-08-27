# 未可信材料事实候选预览

`draft-material-extraction` 仍先保存模型的原始本地草案。若草案同时满足以下条件，CosMatter 会额外生成文档级 `material_extraction_candidates/*.json`：

1. 输出为严格 JSON，且只含当前 `document_id` 和 `facts`；
2. 每条候选包含成分、结构、性质、工艺、实验条件或模拟方法中的一个允许类别；
3. 每条候选引用当前人工选定 source-map 中的 `segment_id`；
4. 数值、单位、限定条件和字段长度均符合候选工件边界。

候选工件补入 source-map 的定位符和引文哈希，但不保存原文引文。其信任状态固定为：

`untrusted_llm_structured_material_fact_candidates_not_evidence`

它不会被事实融合、Gap 生成、报告生成或 UI 导出读取。只有人工将候选核对、修订后，通过 `record-material-facts` 写入 `material_facts/*.json`，才成为可比较的已复核材料事实。
