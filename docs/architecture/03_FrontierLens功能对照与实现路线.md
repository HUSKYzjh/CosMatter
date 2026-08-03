# FrontierLens 功能对照与 CosMatter 实现路线

本对照基于本地参考副本 `02_Reference/11_sciverse_frontier_lens` 的 README、用户指南、
架构决策和前后端实现，不把其 AI 会议论文语料覆盖、React 代码或配置方式直接复制到
材料文献智能体中。

| FrontierLens 实际能力 | CosMatter 适配 | 当前状态 | 关键差异与门禁 |
| --- | --- | --- | --- |
| 自然语言问题 → 有界检索计划 | `MissionBrief` → 人工批准 `FlightPlan` | 已实现 | LLM 草案始终是 `untrusted_draft`，不自动执行。 |
| 有界主题发现图 | 已批准主/反例查询的候选历史 | 已实现 | 候选只是元数据，不能成为科学证据。 |
| Research Guide / Learning Roadmap | `build-reading-guide` → `reading_guide.json` → Guided Cards | 已实现 | 仅排序已有候选与已接受证据；不含检索式、摘要、全文、分数或模型生成的结论。 |
| 论文卡片与 Paper Reading Guide | `paper.html` 候选导读、证据卡、`document_id + locator` | 基础实现 | 不加载全文；接入经授权的 MinerU 段落/页码工件后，才可提供论文级结构阅读。 |
| 三种边语义：内部关系、引用、相关建议 | 候选论文、证据、条件簇与未知项的五类关系 | 初版已实现 | 图例与检查器明确区分检索候选、出处、审核支持/反驳和待核查；后续再增加公开引用/相关工作边。 |
| provenance 回溯和段落高亮 | `EvidenceCard.provenance` | 已实现基础门禁 | 只保留短摘录和定位；全文查看必须由授权内容管线提供。 |
| 实时可取消进度 | UI `timeline` 的脱敏动作投影 | 已实现只读版 | 不是原始审计流；不含 actor、请求 ID、payload 或错误原文。 |
| 前端本地连接设置 | 上级受保护 `.env` + `env.txt` 模板 | 有意不采用 | 不将 API Key 放入浏览器、localStorage 或 UI 设置页。 |

## 已实现：有界阅读路线

`build-reading-guide --run-id <run_id>` 需要同一运行中已有：

1. 经人工批准且绑定该任务的 `flight_plan.json`；
2. 仅由批准查询产生的 `retrieval_candidates.json`；
3. 可选的已接受 `EvidenceCard` 与 `VerificationDecision`。

路线按如下顺序显示：已关联已接受证据的候选 → 主检索候选 → 反例检索候选。内容访问
状态始终独立标注；`metadata_only` 候选不可进入证据抽取。导出到 UI 的路线不携带查询文本
或原始评分。

## 下一批功能

1. **材料论文级阅读工作台**：经 MinerU 的授权解析结果产生段落、页码、图表与表格定位；
   前端只读取可显示的短片段并将“不精确匹配”显式标注。
2. **语义分类的材料关系星图**：将论文/候选、证据、条件、单位与实验/计算设置分别建模；
   边必须声明为出处、审核支持/反驳、条件归属或检索建议，禁止默认视为因果。
3. **受控关系扩展**：在 API 与数据许可明确后，基于 DOI、Crossref/OpenAlex 或 Sciverse
   的公开关系建立有界引用/相关工作边；保留未解析引用，不虚构节点。
4. **可取消的运行状态**：后端先定义无密钥、无请求体的任务状态摘要 API，再让 UI 轮询；
   不直接发布 `events.jsonl`。

## 不复制的设计

- FrontierLens 的 UI 本地配置页及其明文 `local.config.json` 存储方式；CosMatter 的密钥
  仅保留于受保护的上级 `.env`。
- 将一个特定 AI Paper Schema 语料的空结果解释为材料文献不存在。
- 将相似推荐边、图布局或未审核抽取自动宣称为材料科学事实。
