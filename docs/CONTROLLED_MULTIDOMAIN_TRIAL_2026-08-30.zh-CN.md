# 受控多方向文献链路试点（2026-08-30）

## 目的与边界

本试点验证 CosMatter 的真实外部链路，而非形成可用科研结论。用户已授权 Sciverse、公开 PDF 路由、MinerU 和 DeepSeek 的受控试运行；所有输出仍是 `delegated_automated_trial_*_not_scientific_evidence`，不属于人工筛选、正式材料事实、EvidenceCard、融合结果、报告或提交材料。

## 已完成的三条运行

| 运行 ID | 研究问题方向 | 实际全文路线 | 自动审核结果 |
| --- | --- | --- | --- |
| `trial_sodium_ion_cathode_20260830` | P2 钠离子层状正极的锂/阳离子取代、工作电压窗和循环稳定性 | Sciverse 检索/读取 → OSTI 公开 PDF → MinerU | 3 条：1 条直接支持，2 条需限定 |
| `trial_perovskite_photocatalyst_20260830` | SrTiO3 可见光产氢的活化与稳定性 | Sciverse 检索/读取 → arXiv 公开预印本 → MinerU | 3 条均为直接支持 |
| `trial_high_entropy_alloy_20260830` | CrCoNi 高熵合金的低温强塑性 | Sciverse 检索/读取 → arXiv 公开预印本 → MinerU | 4 条：3 条直接支持，1 条需限定 |

每条运行均完成：计划、主检索和反例检索、候选收敛、受控全文访问、MinerU 回执与私有 Markdown、私有候选池、哈希绑定 Source Map、逐条自动事实审核。

## 第二轮扩展（同日）

| 方向 | 新增路线 | 实际结果 | 当前全文数 |
| --- | --- | --- | ---: |
| P2 钠离子正极 | OSTI：四价 Ti/Si 取代研究 | PDF 探测、MinerU、Source Map 与自动审核完成；新增 2 条直接支持、1 条需限定的自动审核记录。 | 2 |
| SrTiO3 光催化 | MDPI 论文版与静态资源版；OSTI 水分解 Primer | 两个 MDPI URL 均 HTTP 403；一个 OSTI 候选不是 PDF；另一篇 OSTI Primer 通过 PDF 探测、MinerU、Source Map 与自动审核，新增 2 条直接支持、1 条需限定。 | 2 |
| FCC 高熵合金 | arXiv：CrCoNi/CrMnFeCoNi 在 20 K 的断裂韧性；Semantic Scholar 的开放获取镜像：Fe-rich SLM 中熵合金 | 三条 PDF 均完成探测、MinerU、Source Map 与自动审核；新增 Fe-rich/SLM/77 K 的作者集合不重叠边界反例（不是 CrCoNi 复现）。 | 3 |

作者名集合的元数据比对显示：P2 的两条受控全文和 SrTiO3 的两条受控全文各自无作者重叠；高熵合金的两条 CrCoNi 预印本存在作者重叠，新增 Fe-rich SLM 文献则与它们作者集合不重叠。它们仍都不是人工完成的机构、样品来源、共享数据或 PDF 版本独立性核查；更不是独立复现实验。因此三条方向均仍未达到“多独立研究组 + 匹配条件”的稳健性门槛。

## 已验证的失败处理

- 光催化剂的 Wiley PDF 与高熵合金的 ScienceDirect PDF 返回 HTTP 403；系统没有把失败伪装为已读取，也没有反复重试。
- 运行随后改走允许列表内可访问的 arXiv 公开预印本。PDF 和 Markdown 均只保留在运行目录外的私有区；运行工件只保留任务回执、哈希、文献标识和最小 Source Map。
- 三个运行的 MinerU 回执覆盖率均为 1.0；候选来源审计、敏感信息审计和运行关系审计均通过。

## 本轮修复

1. 增加独立的“受委托自动试点”筛选、内容访问、Source Map 和事实审核工件；必须显式使用试点命令或开关，不能隐式降级人工门禁。
2. 自动 Source Map 仅能从私有候选池中的精确 `segment_id` 生成，且和摘录 SHA-256 绑定。
3. 正式 `material_fact_review_template` 已有回归测试：它会拒绝自动试点 Source Map，防止自动审核结果进入正式证据链。
4. 公开 PDF 探测对 403 等上游失败保持失败关闭；允许选择另一个经允许列表验证的公开来源。

## 尚待完成的正式研究步骤

1. 人工复核每条试点的候选纳入理由、PDF 版本、原文定位和 Source Map 摘录。
2. 在人工 Source Map 上填写材料事实审核表；然后才可创建 EvidenceCard、条件归一化、跨文献融合和报告。
3. 对每个研究问题扩充多个独立来源，并把反例检索纳入同一比较矩阵；当前 P2 和 SrTiO3 各有两条受控全文、高熵合金有三条，但尚未完成人审版本/独立性/条件比较，不能用于稳健性或新颖性判断。
4. 如需投稿或对外结论，补充授权与版本记录、人工事实复核、证据质量审核和报告证据审计。

## 校园访问与 DSH 的边界

DSH 可以配置模型提供商的 API 凭据，或使用某些提供商的原生认证；它不是校园图书馆的 SSO/OpenAthens/EZproxy 客户端，不能也不应保存校园用户名、密码、浏览器 Cookie、VPN 或代理 URL。若学校提供合规的、面向程序的模型网关，用户可按学校条款将**专用 API 凭据**配置为 DSH provider；这与访问出版社全文是两件事。受限论文应由用户在正常浏览器中完成校园登录和许可确认，再人工下载到私有区并进行人工审核；不得把会话凭据交给 Agent、写进 `.env` 或让 DSH 自动绕过访问控制。

## 参考的工程模式

借鉴 [Sciverse Frontier Lens](https://github.com/Shannon4Science/sciverse-frontier-lens) 的接口与运维说明：区分来源能力和模型派生、保留有类型的上游错误、对暂态失败采取有界重试而不以模型补写来源。CosMatter 只吸收这些工程边界，不复用其数据、服务凭据或代码路径。
