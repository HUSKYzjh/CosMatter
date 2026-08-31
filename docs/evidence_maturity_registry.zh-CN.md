# 证据成熟度登记表（数据库格式与证明标准）

本登记表不把“论文说过”误写成“已经证实”。它与 `EvidenceCard` 并存：前者管理一项主张从文献发现到独立复现的成熟度；后者只保存人工审核通过、可定位的单条证据。任何等级都不是科学真理、因果证明或普适结论。

## 四级证明标准

| 成熟度 | 可作出的有限陈述 | 最低记录要求 | 不能作出的陈述 |
| --- | --- | --- | --- |
| `literature_mentioned`（文献提及） | 某篇已识别文献讨论或报告该主张。 | 书目 ID、版本、独立性分组、筛选状态。 | 数据已核验、机制成立、结果可复现。 |
| `data_supported`（有数据支撑） | 人工核对过的原文定位、数值/图表和实验条件支持该主张，或一篇同等质量文献明确反驳它。 | 人工 Source Map、条件完整性、人审数据状态、支持/反驳立场。 | 跨材料、跨条件或跨实验室的泛化。 |
| `reproducibility_ready`（可复现） | 经人工检查，合成、样品、测试、分析和必要原始数据/合理缺失声明足以形成预注册复现实验。 | 完整协议/材料/测量状态、人审可复现性判断、预定义比较容差。 | 已由他人或本项目复现。 |
| `independently_reproduced`（已经复现） | 独立执行记录在预先定义条件和容差下与原主张一致。 | 不与原文支撑运行重复的独立运行 ID、容差内比较结果、人工复核和 `replicated` 状态。 | 自动等同于所有条件下成立，或把不复现/不确定结果称为“已经复现”。 |

自动试点仅可写入 `assessment_authority=delegated_automated_trial` 和 `source_map_status=automated_trial_only`；它的成熟度上限为 `literature_mentioned`。只有人工审核才能进入 `data_supported` 以上等级。

进入 `data_supported` 及其以上等级还必须至少有一条人工 Source Map、人工核对的数值/图表数据、完整条件和 `supports`、`contradicts` 或 `mixed` 立场。`not_replicated` 与 `inconclusive` 是必须保留的独立实验结果，但不能把主张升级为 `independently_reproduced`。

## 关系型数据库映射

| 表 | 主键 | 关键外键/字段 | 用途 |
| --- | --- | --- | --- |
| `research_claim` | `claim_id` | `question_id`, `maturity_level`, `assessment_authority` | 一条可证伪、限定条件的研究主张。 |
| `document_version` | `document_id + version` | DOI、预印本/作者稿/出版社版、许可和访问路线状态 | 区分同一研究的不同 PDF 版本，避免重复计数。 |
| `claim_support` | `support_id` | `claim_id`, `document_id`, `independence_group`, `source_map_status`, `data_status`, `conditions_status`, `stance` | 记录支持、反驳、混合、仅背景或边界反例关系；`boundary_counterexample` 是材料、工艺或条件不匹配的对照，不能直接当作矛盾。 |
| `reproducibility_assessment` | `claim_id` | 协议、材料、测量、原始数据状态 | 只记录是否达到复现实验准备条件。 |
| `independent_reproduction` | `reproduction_id` | `claim_id`, `independent_run_id`, `result_comparison`, `review_status` | 保存真正独立的复现实验结论。 |
| `access_route` | `route_id` | `document_id`, `route_type`, `probe_status`, `license_or_terms` | 仅记录元数据与状态；不保存校园密码、Cookie、代理 URL 或全文。 |

机器可读 JSON Schema 位于 [evidence_maturity_registry.schema.json](../src/cosmatter/schemas/evidence_maturity_registry.schema.json)，可直接执行的关系型表定义位于 [evidence_maturity_registry.sql](templates/evidence_maturity_registry.sql)，无第三方依赖的严格校验器位于 `src/cosmatter/evidence_maturity_registry.py`。DDL 可用于 SQLite 或 PostgreSQL；跨表的成熟度升级门禁（例如独立运行不得与原支撑运行相同）仍由严格校验器负责，不能只依赖数据库约束。敏感全文、会话 Cookie、校园 VPN/代理地址和令牌不得进入这些表。

## 运行工件与只读界面

审核后的登记表可显式绑定到一个本地任务；此命令不联网，也不会修改原始输入文件：

```powershell
python -m cosmatter.cli record-evidence-maturity-registry --run-id <run_id> --input <reviewed_registry.json>
python -m cosmatter.cli export-ui --run-id <run_id>
```

写入前，`question_id` 必须匹配该任务的 `mission_id`，每条支撑记录必须通过候选与同一任务 Source Map 的链接审计。运行目录会同时保存登记表和仅含计数、稳定 ID 与 SHA-256 绑定值的审计收据。导出界面会重新执行链接审计；登记表或收据任一项被修改、缺失或失配时，界面只显示“登记表未通过交付校验”，不会显示任何成熟度升级。浏览器也会再次比较导入登记表的 `question_id` 与 UI 任务 ID，跨任务登记表一律拒绝。

通过“导入 JSON 文件”打开的包只在浏览器中进行结构、交付标记和任务 ID 检查；浏览器不会重新读取私有 Source Map 或重算链接审计。因此，手工导入文件中的 `accepted` 仅是该导出包的声明，不是当前浏览器独立作出的核验。要取得当前链接审计结论，应通过本机 loopback 服务重新导出对应运行；界面会明确区分这两种状态。

该命令还要求任务在写入前通过当前的敏感工件扫描，并在写入后刷新该扫描收据；因此提交执行清单不会把过期的“清洁”扫描状态当作新登记表的证明。

登记表会拒绝 URL、授权头、密钥标记与常见私有路径出现在可显示的主张或限制文字中；原文摘录、下载链接和凭据仍必须留在既有的私有边界之外。

运行的 `submission_execution_manifest.json` 会以文件名、字节数和 SHA-256 同时列出这两个工件；该执行清单不复制登记表内容，也不把登记表本身提升为科学结论。

本地“运行包续航”会保留同一对已哈希绑定的工件，但不携带 Source Map 原文片段。恢复到仍保留原始受控运行的本机时，UI 会重新审计链接；若没有可用的原始链接，登记表保持拒绝态而不会被降级为未登记或被自动信任。

## 三条当前试点的成熟度判定

| 方向 | 当前受控全文 | 自动审核 | 可登记成熟度 | 缺口 |
| --- | ---: | ---: | --- | --- |
| P2 钠离子正极 | 2 | 6 条（2 个受控全文各 3 条） | `literature_mentioned` | 作者集合元数据不重叠，但仍需人工核验版本、定位/数据、机构和共享数据关系。 |
| SrTiO3 光催化 | 2 | 6 条（arXiv 研究 + OSTI Primer） | `literature_mentioned` | 作者集合元数据不重叠；Primer 不是实验复现，仍需人工核验稳定性测试、牺牲剂/共催化剂和光源条件。 |
| FCC 高熵合金 | 3 | 10 条（两篇 CrCoNi 预印本 + Fe-rich SLM 边界反例） | `literature_mentioned` | 两篇 CrCoNi 预印本有作者重叠；新增文献仅是作者集合不重叠的材料/工艺边界反例，仍需匹配成分/热处理的独立研究。 |

这些判定刻意保守：试点的“直接支持”只表示自动审核与已选摘录的文字匹配，并非人工数据核验。

本轮真实运行的私有登记实例保存在未纳入版本库的私有数据根目录；本公开文档不记录其本机路径、文件名或运行日期。P2 和 SrTiO3 各纳入 3 个候选（2 个受控 PDF/MinerU/自动 Source Map，另 1 个仅有 Sciverse 内容访问）；高熵合金纳入 4 个候选（3 个受控全文，其中 1 个为 `boundary_counterexample`，另 1 个仅有 Sciverse 内容访问）。全部停留在 `literature_mentioned`。相应链接审计的聚合结果为：3 条主张、10 条支撑记录、7 个自动 Source Map、3 个仅上下文候选，零链接错误。
