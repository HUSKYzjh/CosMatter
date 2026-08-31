# Frontier Lens 覆盖审计（2026-08）

本审计以本地 `case-data/references/11_sciverse_frontier_lens` 的架构、用户指南与
前端交互为参照，逐项以现有代码、工件与测试为证据。它不宣称 CosMatter
复制了 Frontier Lens；目标是将其文献探索思路安全地适配为材料科学证据工作流。

| 参考能力 | 当前 CosMatter 证据 | 判定 |
| --- | --- | --- |
| 有界发现图与不同边语义 | `reading_guide.py`、`network.js`，主/反例候选、出处、支持、反驳、待核查、引用参考、算法相关边均单独建模 | 已覆盖 |
| Research Guide / Roadmap | `build-reading-guide` 与 Guided Cards；测试 `test_reading_guide.py` | 已覆盖 |
| Paper Reading Guide | `paper.html`、`source_map.py`、`test_ui_source_map_projection.py`；最多 3 段/1000 字符的人工复核片段 | 已覆盖，但非全文阅读器 |
| provenance 到片段 | `source_map` 与 `ingestion.require_source_map_match`；测试拒绝改写或错定位引文 | 已覆盖 |
| 公开引用与相关工作关系 | `openalex.py`、`relation_expansion.py`、`network.js`；引用参考与算法相关边分离，均标为非科学证据 | 已覆盖 |
| 可取消进度 | `run_control.py`、`cancel-mission`、`run-status` 与受控外部调用门；测试 `test_run_control.py` | 已覆盖（协作式，而非中断在途同步请求） |
| 模型只基于闭合资料输出 | 批准计划、候选元数据、source-map、EvidenceCard 和审核决策均为独立工件；UI 只消费白名单投影 | 已覆盖 |

## 未覆盖或只完成基础设施的项

1. **材料特异关系模型**：已将已批准证据卡中的标量条件字段投影为实验/计算
   设置节点，并使用“报告条件，非因果”边连接。单位后缀随字段名保留；尚未
   建立完整材料单位本体或知识图谱。当前已对人工填写的已知数值单位做确定性一致性复核，
   但未知单位、文本量和跨文献可比性仍不自动推断。
2. **长期运行任务**：现有 CLI 是短同步调用；若引入队列或后台 worker，必须把
   取消令牌传入每个可中断边界，而不是仅保留本地取消标记。

这些项目仍是后续工作，不应在 README、演示或评审材料中描述为已经完成。
