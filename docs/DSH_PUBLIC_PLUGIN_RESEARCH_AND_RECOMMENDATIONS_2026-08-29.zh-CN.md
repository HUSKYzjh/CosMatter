# 公开 DSH 插件调研与 CosMatter 改进建议

日期：2026-08-29
范围：公开可访问的 DeepSeek Harness（DSH）官方文档、官方源码说明、社区插件仓库和插件目录；**未安装、未执行、未信任任何第三方插件**。本文是工程决策材料，不是对任何社区项目的安全背书。

## 2026-11-20 补充调研：科研产品与 DSH 原生插件

### Orca 如何接入 CosMatter 的研究舰队

这里选用 Stably 的 Orca。它在同一界面组织多个 agent，各自可在独立 Git 工作树中运行。官方把 DeepSeek Harness 列为支持的终端 agent，并列出两个依赖包 `@deepseek-ai/dsh` 和社区提供的 `@deepseek-harness-tui/dsh-tui`。Orca 将多 worker 编排标为实验性。当前 PowerShell 找不到 `orca` 命令，这次核查覆盖官方协议、插件源码和 CosMatter 现有入口，三者在本机的联合运行仍待验证。[Orca 项目](https://github.com/stablyai/orca) · [终端支持表](https://github.com/stablyai/orca/blob/c4776883dc43bd26b07e1a3bfc4e9d6c90f3a866/docs/site/content/docs/agents/supported.mdx#L49) · [编排协议](https://orca.dev/docs/cli/orchestration)

| 可以采用的路线 | 给 CosMatter 带来的能力 | 当前适用条件 |
|---|---|---|
| Orca 打开 DSH，DSH 调用 CosMatter | 在 Orca 的终端里检查指定研究任务的进度和交付物。 | 优先验证这条路线。CosMatter 已有 `open-dsh-workbench --port … --surface tui --run-id …`，会针对当前工作台端口生成插件配置，并给观测工具绑定运行 ID。Orca 内置 DSH 入口使用自己的 TUI profile，可先在 Orca 普通终端运行现有 CosMatter 命令，单独核对工具读取的任务。[Orca 的 DSH 支持](https://orca.dev/docs/agents/supported) · [CosMatter 启动与绑定实现](../src/cosmatter/dsh_profile_status.py) |
| DSH 通过社区插件 `dsh-orca-agents` 派工给 Orca | 在 DSH 对话中创建工作树，交给 Orca 中的 agent 执行，完成后通知 DSH。 | 作者列出的环境为 Orca 1.4.193 和 DSH 0.1.5-rc.2，CosMatter 的基线是 0.2.2-rc.3。该插件按工作树观察 agent，有一个返回 done 就可能报告完成。文件枚举仅接受以 `/` 开头的路径，收到 Windows 盘符路径时会返回空列表。用于科研任务前需要验证回执归属及实际文件。[插件说明](https://github.com/aa2246740/dsh-orca-agents/blob/51b8b23e0b466ddf15b085d039c157e01d76dce8/README.md#L22-L31) · [完成判断和文件枚举](https://github.com/aa2246740/dsh-orca-agents/blob/51b8b23e0b466ddf15b085d039c157e01d76dce8/src/watch.ts#L9-L44) |
| 在 DSH 内协调或查看分工 | 官方 Agent Teams 可领取共享任务，更新时核对负责人和修订版本。社区插件 `dsh-task-dag` 可显示子会话、任务依赖和通信关系。 | DSH 方案可作为对照组。官方工具需要在根会话启用 Team 模式。`dsh-task-dag` 1.5.1 的包清单限定 DSH 低于 0.2.0，适合作为依赖图、节点详情和键盘交互的设计参考。[官方任务工具](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/team/tool-agent-team/README.md) · [DAG 交互](https://github.com/LeemanCheung/dsh-task-dag/tree/8fe407f525823091523cd31bc940342feb83b7d1) · [版本范围](https://github.com/LeemanCheung/dsh-task-dag/blob/8fe407f525823091523cd31bc940342feb83b7d1/package.json#L45-L52) |

#### 用两篇 BiFeO₃ 文献验收一次派工

选两篇有公开全文的论文，提出同一个问题：“样品是什么，用什么测量判据得到哪一种转变温度？”给每篇分配一个子任务。每份交付记录 DOI、PDF 版本、页码或图号、样品条件、转变类型、数值及单位。遇到只有摘要、只有转述、图中无法读数或全文未报告该指标的情形，交付中写明哪一项缺失。这样首页能直接展示两项具体工作，研究者也能判断两篇结果能否放到同一列比较。

| 验收情形 | 操作与通过条件 |
|---|---|
| 工作台绑定 | 在两个本地端口分别打开不同的合成任务，从 Orca 中按各自的端口和运行 ID 启动 DSH。两次状态读取都须返回对应任务，结果卡各自能回到原工作台。 |
| 重试和迟到结果 | 借用 Orca 的 `taskId` 和 `dispatchId`，分别标识核对哪篇论文、这是第几次派工。对同一篇派工两次，先收到第二次回执，再送达第一次并重复投递。当前状态只随有效尝试变更一次。历史记录可查看两次尝试及各自产物。[Orca 的完成与重试约定](https://orca.dev/docs/cli/orchestration) |
| 看板与证据 | 任务卡显示论文、执行者、当前尝试及交付物，点击后能回到相应页或图。当两篇收到完成回执而只有一篇具备可定位数据时，两项执行均可显示完成，证据层级按每条主张的原文和审核记录分别显示。CosMatter 已有产物哈希和执行回执，可直接用来交叉核对。[舰队阶段映射](../frontend/src/fleetRuntimeState.ts) · [执行回执](../src/cosmatter/harness_receipts.py) |

优先顺序是先验证两个端口的只读交接，再引入每次派工的标识和可点击的交付物。独立工作树适合放脚本和中间产物，同一公开 PDF 用内容哈希标识。两个 worker 核对同一份 PDF 仅产生两次核对记录，独立文献数仍为一篇。

### 科研产品与文献工具

本次从“BFO 实验条件能否回到原文”和“舰队各自交付什么”两个实际需求选项目。当前本机 DSH 版本为 `0.2.2-rc.3`。下表的第三方能力和版本来自作者文档及包清单。本轮未安装第三方插件，也未向这些服务发送文献或研究问题。

| 项目 | 作者提供的能力 | CosMatter 可直接对照的用例 |
|---|---|---|
| GeoResearch for DSH | 将文献、PDF 读取回执、主张、复现计划和审阅保存为可追溯记录。其支持矩阵指定 Windows x64 和带项目兼容补丁的 DSH `0.1.0-rc.5`。 | 最接近 CosMatter 的整体工作流。选一条 BFO 结构转变主张，从写作结果往回核对原文版本、实验条件与审阅决定。当前适合做架构对照。 [项目与兼容要求](https://github.com/georesearch-dsh/georesearch-dsh/tree/ff8a6556d382fe43639c67e5936f859fe3e7e63c) |
| Elicit | 从检索、筛选到提取表，支持查看每条筛选依据；点击提取表单元格可查看相应论文引文。 | 用“温度、单位、样品形态、测量判据”四列复核。每个数值都应能单独打开支撑它的原文位置。 [官方系统综述指南](https://support.elicit.com/en/articles/14759154-systematic-reviews-in-elicit) |
| PaperQA | 开源科学文档问答，检索证据后生成带出处的回答。 | 在相同 PDF 集合上比较出处能否支持回答中的数值与限定条件。 [作者仓库](https://github.com/Future-House/paper-qa) |
| ChemDataExtractor + Snowball | 作者从 108,181 篇论文自动抽取了 56,037 条材料与居里温度或奈尔温度记录，评估的精确率为 72%，召回率为 61%。 | 给 BFO 磁转变任务提供抽取基线。比较时逐条核对化学式、温标及测量判据，并把铁电或结构转变另列。上述统计覆盖整个数据集。 [剑桥论文及数据说明](https://www.repository.cam.ac.uk/items/8a346e06-20d5-463e-8f0f-98e590f2dc70) |
| AiiDA + aiida-lammps | 记录计算输入、输出及其来源；LAMMPS 插件支持分子动力学工作流，并能保存势场和轨迹。 | 对固定组分的 Pb/Sr 排列，把构型、势场、随机种子、采样协议与每次 MD 结果关联起来。性质由模拟给出，比较算法或复跑时可以取回同一组输入。它属于 AiiDA 生态。 [AiiDA 数据溯源](https://aiida.readthedocs.io/projects/aiida-core/en/stable/intro/index.html) · [LAMMPS 插件](https://aiida-lammps.readthedocs.io/en/latest/) |

| DSH 插件 | 接口及适用场景 | 已核对的版本边界 |
|---|---|---|
| Vncntvx/dsh-zotero | 从自己的 Zotero 库检索、读文献，在 DSH Web 文献面板查看引用并审批写入。适合设计“库中已有论文 → 已选摘录 → Source Map”的入口。 | `v1.2.0` 明确要求 DSH `>=0.2.2-rc.3 <0.3.0`、Node `>=24.15.0`，是本项目最值得先用公开 PDF 试验的版本。 [固定版本包清单](https://github.com/Vncntvx/dsh-zotero/blob/v1.2.0/package.json) |
| Cjrrrrrrrr/dsh-plugins 的 dsh-scholar | 综合多源书目检索、引用查询和 Unpaywall 开放 PDF 地址解析。适合在 SciVerse 已有元数据而全文不可用时查找开放版本。 | 子目录内有独立 Cordis 补丁和 DSH 工具依赖声明；实际取得 PDF、核对 DOI 和版本后，再计为全文成功。 [插件目录与清单](https://github.com/Cjrrrrrrrr/dsh-plugins/tree/9be158a6b51c24753efc894c88b2af1506946fc4/packages/dsh-scholar) |
| NanmiCoder/dsh-agent-teams | 组织多 Agent 团队、分配带依赖的任务，并在 Web 界面查看成员和任务进度。适合对照 CosMatter 舰队的分工、等待原因与交付物。 | `v0.1.31` 有独立兼容表，本机 rc.3 仍需单独验证。 [作者仓库](https://github.com/NanmiCoder/dsh-agent-teams/tree/v0.1.31) · [兼容矩阵](https://github.com/NanmiCoder/dsh-agent-teams/blob/v0.1.31/compatibility.json) |
| TYEclipse/dsh-chem | 按化学式求摩尔质量与元素质量分数，也可从给定的元素质量分数反算经验式。可用理想 BiFeO₃ 的整数化学式校核材料表中的计量换算。 | `v0.4.0` 提供已编译入口和 Cordis 补丁；其开发依赖使用 DSH SDK `0.1.0-rc.6`，本机 rc.3 的运行兼容性待测。 [工具定义](https://github.com/TYEclipse/dsh-chem/blob/v0.4.0/dist/tools.js) · [固定版本清单](https://github.com/TYEclipse/dsh-chem/blob/v0.4.0/package.json) |

检索时有两个同名 Zotero 项目。上表推荐评估的版本由 **Vncntvx** 发布；**kuangdang123** 的另一个包能读取批注、增改条目和移至回收站，声明版本为 `0.1.3`。需要独立 MCP 服务时，另有 **Zotero MCP**，含 PDF 注释提取和按工具组配置的接口。 [kuangdang123 的清单](https://github.com/kuangdang123/dsh-zotero/blob/84d2239c1c150ed477490f6e53d3b5afeb7aa25c/package.json) · [Zotero MCP](https://github.com/54yyyu/zotero-mcp)

本机 rc.3 的加载器先检查包清单里的 `engines.dsh`，未声明时逐一检查 DSH 工具依赖的版本范围。两种检查都包含预发布版本。按这段规则，kuangdang123 的 `v0.1.3` 和 Cjrrrrrrrr 的 `dsh-scholar 1.0.0` 均符合版本声明；本机加载和实际调用仍待验证。 [rc.3 主机判断逻辑](https://github.com/deepseek-ai/deepseek-harness/blob/38a6a5c965aa99ab525161efb7cc5cf1fe62fced/packages/boot/app-boot/src/plugin-compatibility.ts#L51-L79)

继续发现项目可从 DSH 官方市场索引规范入手，或使用按 GitHub 主题聚合的社区 Web 市场，再去作者仓库核对来源、版本与工具声明。 [DSH 官方市场文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/plugin-market.md) · [社区 Web 市场](https://github.com/bradeGithub/DSH-Plugins-Marketplace)

校园订阅可单独试一条本地交接路线。用户在已登录学校图书馆的浏览器打开有访问权的文章，Zotero Connector 保存可获取的 PDF 与书目信息，再将选定的附件从 CosMatter「文献入港」导入。校园认证留在浏览器；是否能取得附件取决于学校订阅和站点。此路线尚未用本校账号验证。 [Zotero 官方保存说明](https://www.zotero.org/support/adding_items_to_zotero#via_your_web_browser)

### 11 月 20 日实查的插件目录和发布包

本次直接查询两个公共 JSON 目录，按完整 npm 包名匹配。科研专题目录在 2026-11-20 00:00 UTC 生成，返回全部 15 项。原生格式的 Open Plugin Market 在查询时有 1,294 项。两个目录的收录范围不同，值得交叉检查。

| 发现渠道 | 实际命中 | 如何使用 |
|---|---|---|
| DSH Research 科研目录 | `dsh-kb-rag@1.6.8`、`dsh-ai4scholar@0.6.6`、`dsh-science-workbench@0.3.1`。当时未收录下列 EduWork 包。 | 可直接浏览网页。其 JSON 由社区插件 `dsh-research` 消费。[目录网站](https://dsh-research.com/en/plugins/) · [实查数据](https://dsh-research.com/v1/market.json) · [作者说明](https://github.com/dsh-research/dsh-research) |
| Open Plugin Market | `@eduwork/dsh-literature@0.1.7`。上述三个包在此次快照中均未命中。 | 支持自定义索引的 DSH 版本可在 Discover 中添加此 JSON。DeepSeek 提供索引规范，索引由社区维护。[原生索引](https://dshopen.org/index.json) · [官方使用指南](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/plugin-market.md) |

又从 npm 官方注册表逐个下载下列四个包，以及 `dsh-research@0.4.6` 和 `dsh-lit-search@0.2.2`。六个压缩包均通过注册表摘要校验，包内都含有自身 `dsh.bundle.patch` 指定的文件。将六份发布清单传给本机 DSH `0.2.2-rc.3` 的 `evaluatePluginCompatibility`，五份通过宿主版本检查。`dsh-lit-search@0.2.2` 被拒绝，因为它要求的 `@deepseek-ai/dsh-tools` 版本范围为 `^0.1.1-rc.1`。这项检查没有在用户的 profile 安装或启动第三方插件，也没有验证检索质量。[不兼容包的发布清单](https://registry.npmjs.org/dsh-lit-search/0.2.2)

| 候选 | 对 CosMatter 最值得试的地方 | 适用边界与作者来源 |
|---|---|---|
| **dsh-kb-rag 1.6.8** | 从已有 PDF 或本地 Zotero 附件中检索段落和图注，结果带物理页码、章节和 DOI。可对照 Source Map，检查一个 BFO 数值能否跳回正确的段落、样品和页。 | 要求 PDF 有文本层。DSH 自带的 Python 3.12.14 和 CosMatter 虚拟环境 3.14.7 均缺少 PyMuPDF、faiss-cpu、sentence-transformers；首次检索还需约 1.2 GB 模型。扫描件应单列测试 MinerU 路线。[作者仓库](https://github.com/Breeze136/dsh-kb-rag) · [发布清单](https://registry.npmjs.org/dsh-kb-rag/1.6.8) |
| **@eduwork/dsh-literature 0.1.7** | 跨 DBLP、arXiv 去重，保留发表版与预印本的区别，取得 BibTeX 和可用全文。适合为同一论文建立版本配对，再选定用于引证的 PDF。 | 当前检索源限于这两个数据库。对材料实验论文，需额外验证期刊覆盖。包要求 Node ≥24.18.0。[作者中文文档](https://github.com/ECNU/EduWork/blob/main/packages/dsh-literature/README.md) · [发布清单](https://registry.npmjs.org/@eduwork%2fdsh-literature/0.1.7) |
| **dsh-science-workbench 0.3.1** | 从图回看生成它的计算单元、参数、随机种子和输出哈希。Pb/Sr 构型项目可借此设计“构型 → MD 运行 → 性质 → 图”的追踪界面。 | 它提供计算记录和重跑交互。介电、压电结果仍需由实际 MD 任务产生，再比较重复运行的统计误差。[作者仓库](https://github.com/poplarity/dsh-science-workbench) · [发布清单](https://registry.npmjs.org/dsh-science-workbench/0.3.1) |
| **dsh-ai4scholar 0.6.6** | 多源发现、引文关系和 DOI 原文检索可作为 SciVerse 的独立对照。可观察第二条路线找到了哪些独立论文，以及哪些结果只增加了同文异版。 | 使用 AI4Scholar 服务，部分查询计费，另需该服务的密钥。此次没有调用服务。[作者仓库](https://github.com/literaf/dsh-ai4scholar) · [发布清单](https://registry.npmjs.org/dsh-ai4scholar/0.6.6) |

### 同类科研产品的对照实验

- **实验值取证。** Elicit 的提取表可以从单元格回看引文。ChemDataExtractor 的官方示例则将化合物与分散在另一段的熔点关联，并保留原始单位和归一化单位。对 BFO 可选有人工标注的公开 PDF，把材料、转变类型、数值、单位、样品和出处作为一条记录，分别统计取值正确率与出处正确率。文献未报告的条件单列为缺失。[Elicit 的系统综述界面](https://support.elicit.com/en/articles/14759154-systematic-reviews-in-elicit) · [ChemDataExtractor 抽取示例](https://cambridgemolecularengineering-chemdataextractor-development.readthedocs-hosted.com/en/latest/introduction/finding_records.html)
- **反例筛选。** ASReview LAB 会利用审阅者的相关性标注重新排序剩余题录。在同一批有金标的论文上，比较现有筛选路线和该排序找到第一篇反例所需的审阅数，以及前 20 篇中相关论文的召回率。[ASReview LAB 筛选界面](https://asreview.readthedocs.io/en/stable/lab/screening.html)
- **计算结果溯源。** Materials Project 可沿性质记录中的 `origins.task_id` 找到对应计算及所用泛函。Pb/Sr 试点可采用类似的标识关系，让任一性质返回实际 MD 输入、构型和轨迹，并保留重复采样的误差。[Materials Project 查询示例](https://docs.materialsproject.org/downloading-data/using-the-api/querying-data)

优先试点选 **dsh-kb-rag 的段落定位**。用至少两篇独立公开原始研究，预先标记包含数值、单位和实验判据的页或图注，并加入一篇只在引言提到温度的论文。比较同一问题在两条路线中返回的前三段是否覆盖标记位置，逐条记录错页、漏掉样品条件以及把转述当成独立测量的次数。这个试验能直接检验 CosMatter 当前最关心的证据质量。

### 材料实测曲线、跨论文比较与 DSH 插件

**Starrydata2（日本 NIMS）** 把一条实验曲线关联到论文、图号、样品、坐标轴、单位和测量条件，并提供可下载的坐标。它适合检查 CosMatter 能否从一条数值返回原图及对应样品。**Open Research Knowledge Graph（ORKG）** 则支持从 CSV 导入多篇论文、编辑对照表并保存草稿。可借鉴其列设计，将样品形态、制备工艺、测量频率、温度、原文位置和证据等级逐项并排展示。[Starrydata 录入流程](https://starrydata.nims.go.jp/hp/en/manual/register/) · [ORKG 比较表](https://academy.orkg.org/tutorials/comparison-tutorial-iii.html)

#### 用一张 BiFeO₃ 图检验样品是否会被混在一起

从 Starrydata 2026-11-20 固定发布下载介电项目的 papers、samples、curves 三份 CSV，逐个核对发布清单的 SHA-256。原论文 DOI 为 `10.1016/j.jeurceramsoc.2014.08.016`，论文 SID 为 `41149`。下表两条曲线都关联图 6（figure_id `63226`），成分都记录为 `BiFeO3`，备注均为 500 kHz、25–400 °C。表中列出各条数字化曲线最接近 298.15 K 的已收录坐标。[原论文](https://doi.org/10.1016/j.jeurceramsoc.2014.08.016) · [固定发布](https://github.com/starrydata/starrydata_datasets/releases/tag/data-20261120) · [固定校验清单](https://github.com/starrydata/starrydata_datasets/blob/c1735aa9d067e405ce6d27482f9c693055d6171e/docs/manifest.json)

| 样品及工艺 | sample_id | 该曲线点数 | 温度（K） | 介电常数实部 ε′ |
|---|---:|---:|---:|---:|
| (a) SPS，放电等离子烧结 | 96892 | 20 | 298.21 | 491.2 |
| (b) conventional method，常规烧结 | 96893 | 23 | 307.68 | 13.77 |

两条记录的 `figure_name` 都为 `6`，字母来自样品名称。两点相差 9.47 K，CSV 未给出测量误差。本次核验止于公开的数字化记录，原图逐点核对和独立实验复现仍待开展。CosMatter 可以用这两行验收“同文异样品”显示是否正确，统计独立论文时应计为一篇。[样品 CSV](https://github.com/starrydata/starrydata_datasets/releases/download/data-20261120/DielectricMaterials_samples.csv.gz) · [曲线 CSV](https://github.com/starrydata/starrydata_datasets/releases/download/data-20261120/DielectricMaterials_curves.csv.gz)

#### 两个可评估的 DSH 发布包与一个材料计算参照

| 候选 | 解决的问题 | 发行物和本机核验 |
|---|---|---|
| **dsh-refkeeper 0.1.5** | 从选定的 DSH 会话提取文献，按标题、作者、年份向 Crossref 等五个目录核对。结果不一致时保留待核记录，可导出 BibTeX 或 RIS。适合放在报告导出的书目核对步骤。对实验值的核对仍需逐项查看正文或图表。 | npm 包含 Cordis 补丁、主入口和 Web 客户端。本机 rc.3 宿主的版本检查通过。进行在线书目核对时会发出标识符或题名；注释还有单独的模型处理环节。[对应版本源码](https://github.com/ymwang92/dsh-refkeeper/tree/5cec2c0e0b9581840bf61db2d01004ff86bc99f6) · [npm 发布清单](https://registry.npmjs.org/dsh-refkeeper/0.1.5) |
| **@nashihang777/dsh-solids-world 1.0.1** | DSH Web 原生晶体面板，可在本地拖入 CIF、查看晶胞和原子标签。可用作 Pb/Sr 有序构型的目视核对入口，介电与压电性质仍由给定势场的 MD 输出。 | npm 包含 Cordis 补丁、主入口和 Web 客户端。本机 rc.3 宿主的版本检查通过，作者未声明具体 DSH 版本范围。512 个 A 位和部分占位的显示行为仍待验证。[固定版本使用说明](https://github.com/nashihang777/dsh-solids-world/tree/6b956c606aac585d3ed2a14c3e6ea50d365b590a) · [npm 发布清单](https://registry.npmjs.org/@nashihang777%2fdsh-solids-world/1.0.1) |
| **mat-dsh** | 材料计算的 DSH 插件族。将本地任务输入、Slurm 作业号、异步状态和回传的结果文件关联起来，可参考它为每个 Pb/Sr 构型保留独立的计算记录。作者列出了 Gaussian、VASP 和 xTB 的工作流。 | 作者的兼容基线是 DSH 0.1.0-rc.8。对固定版本的 `mat-tools` 清单运行本机 0.2.2-rc.3 的兼容检查，system-prompt、jobs、session 三项依赖均不匹配。适合作为架构参照。[作者架构](https://github.com/wangyp163/mat-dsh/tree/e1ae7773836251948d84238e345d28c67c5f541f) · [组件兼容说明](https://github.com/wangyp163/mat-dsh/blob/e1ae7773836251948d84238e345d28c67c5f541f/packages/mat-bundle/README.md) |

两个 npm 发布包均在内存中解包并按注册表的 SHA-512 校验。版本核验使用本机宿主导出的 `evaluatePluginCompatibility`，未安装或运行第三方代码。后续若评估可用性，Refkeeper 可用一组含错配 DOI 的公开书目检查其隔离和导出行为，Solids World 可用已知 Pb/Sr 占位的 CIF 对照原始坐标。[DSH rc.3 兼容判断源码](https://github.com/deepseek-ai/deepseek-harness/blob/38a6a5c965aa99ab525161efb7cc5cf1fe62fced/packages/boot/app-boot/src/plugin-compatibility.ts#L68-L93)

继续发现项目可用 DeepSeek 官网链接的 GitHub 主题页、DSH Research 的科研目录，以及独立社区的 DSH Marketplace。后者另有提供 `/store` 入口的 DSH 原生插件，npm 包名为 `dshmarketplace-plugin`。[官网社区入口](https://www.deepseek.com/zh/harness/) · [GitHub 主题页](https://github.com/topics/dsh-plugin) · [科研目录](https://dsh-research.com/en/plugins/) · [DSH Marketplace](https://dshmarketplace.dev/) · [市场插件源码](https://github.com/DshMarketPlace/dsh-plugins-store)

## 8 月初审结论摘要

CosMatter 当前的七个 DSH bundle 已覆盖任务建立、状态观测、策略、受同意约束的计划/元数据检索、候选筛选、MinerU 任务元数据和已接受证据图投影。它的优势是：Python 领域层仍是唯一事实来源，所有 DSH 包仅经 `127.0.0.1` 的受限投影访问，且不把私有全文、密钥或未核验内容暴露给模型。

公开生态最值得借鉴的不是直接接入某个大而全的插件，而是以下工程模式：

1. 对 Git 安装的 bundle 强制提交编译产物并做干净 profile 冒烟测试；
2. 对可能产生外部副作用的调用实行“可恢复但不自动重放”的幂等与审计设计；
3. 为安全的报告/图/状态投影提供类型化 Artifact 与 Web 呈现；
4. 把项目决策记忆与科学证据严格分库；
5. 若将来需要自动编排，坚持声明式、固定 DAG，不采纳模型生成脚本作为研究工作流执行面。

建议先做 P0 的发布兼容性和幂等恢复，再做 P1 的 Artifact/决策记忆/运行时不变量。暂不建议安装通用 MinerU、记忆、视觉或工作流社区插件到生产科研 profile。

当前仓库对这些建议的实现、验证证据与条件式保留范围见
[实施与证据审计](DSH_RECOMMENDATION_IMPLEMENTATION_AUDIT_2026-08-29.zh-CN.md)。该审计不将
工程验证升级为 provider SLA、第三方安全认证或科学证据接受。

## 已核对的 CosMatter 基线

依据 [插件组说明](../plugins/README.md) 与 [bundle 清单](../plugins/dsh-plugin-group.json)，当前组含七个本地 bundle：

| 能力 | 当前包 | 边界 |
| --- | --- | --- |
| 创建任务 | mission | 有界本地任务，不调用模型或提供商 |
| 流程状态 | observability | 仅阶段与计数的只读投影 |
| 策略 | policy | 静态目录与非执行授权判定 |
| 调研 | research | 精确任务范围同意后的不可信草案与元数据检索 |
| 筛选 | review | 候选元数据与人工筛选记录 |
| 文档 | document | 经筛选、授权后的 MinerU 任务提交/轮询元数据 |
| 图 | graph | 已接受证据的受限图投影、计划和审核请求 |

这正好把“研究数据/证据”与“自动化控制面”分开。后续改进不得削弱以下不变量：loopback only、无私有全文/凭据、授权不等于证据接受、外部调用须有持久化的明确任务范围同意、DSH 不输出解析正文。

## 公开生态观察

| 公开来源/能力 | 证据 | 对 CosMatter 的启发 | 是否直接接入 |
| --- | --- | --- | --- |
| DSH 官方架构 | 官方将模型、工具、技能、会话、沙箱、存储、循环、调度和 UI 都设计为可组合插件，并明确仍在 developer preview、接口会演化。见 [官方概览](https://www.deepseek.com/harness/en/) 与 [源码仓库](https://github.com/deepseek-ai/deepseek-harness)。 | 所有本地包都应有兼容性矩阵和升级门禁；不要把当前 `rc` API 当稳定 ABI。 | 已采用“独立 bundle + loopback 领域层”；需补发布门禁。 |
| Bundle 发布与 Git 安装 | 官方发布指南指出 Git 安装只获得源码，不会自动运行构建脚本；TypeScript bundle 缺失 `lib/` 会加载失败。见 [发布指南](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md)。 | 将提交的 `lib/`、`npm pack --dry-run`、干净 profile 安装/启动测试列为每个 bundle 的强制发布条件。 | 高优先级借鉴。 |
| 会话持久化检查点 | 官方 `dsh-session-checkpoint-policy` 在模型请求、顶层工具副作用和步骤边界前持久化；遇到“已记录调用但无结果”会标记 outcome unknown，而非自动重试。见 [README](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/session/session-checkpoint-policy/README.md)。 | 为 Sciverse、DeepSeek 与 MinerU 的 DSH 调用建立调用 ID、幂等键和恢复策略；未知结果必须人工/状态核验后续行。 | 高优先级借鉴；不需要直接加载该插件。 |
| 类型化 Artifact 与 Web 呈现 | 社区 [DSH Vision Toolkit](https://github.com/Anionex/dsh-vision-toolkit) 将工具结果做成结构化 schema、受控 credential、Artifact 与 Web 卡片；其 README 还提供可移植检查、打包和 profile 冒烟测试。 | CosMatter 可把已生成、非敏感的报告 PDF、图投影、运行包摘要做成受限 Artifact，而非只把 JSON 文本交给模型。 | 仅借鉴模式；不接入视觉能力。 |
| 可审计本地记忆 | 社区 [dsh-mneme](https://github.com/modusensus/dsh-mneme) 采用 SQLite 与可编辑 Markdown 镜像，并声明可使用本地 embedding。 | 可实现项目级“决策/运行记录记忆”，但必须与论文原文、材料事实、证据接受记录隔离。 | 仅借鉴数据主权和可编辑镜像；不安装。 |
| 工作流引擎 | 官方 workflow seam 支持脚本和子 agent；官方 worker-thread 实现明确说明 `node:vm` 不是安全边界，模型生成脚本具有与 bash 相同的信任前提。见 [工作流说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/workflow.md) 和 [worker-thread README](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/workflow/workflow-worker-thread/README.md)。 | 科研运行不应把模型生成脚本作为控制面；若要并行，只允许版本化、声明式的静态阶段 DAG。 | 不接入动态 workflow engine。 |
| 调度与会话参考 | 官方 `dsh-schedule` 说明提醒是 session-local：会话不活跃时任务只会 overdue；官方还提供受字节/数量限制的 session reference 配置。见 [工具目录](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-catalog.md) 与 [配置目录](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/config-catalog.md)。 | 可以做“提醒重新核验/报告更新”，但不能把它当可靠 cron，更不能自动触发付费或外部研究调用。 | P2，受限采用。 |
| 社区发现与风险 | 社区目录 [HackSing/dsh-plugins](https://github.com/HackSing/dsh-plugins) 明确称其是信息索引，不构成背书或安全审核；公开目录也列有通用 MinerU 等插件。 | 把第三方插件视为高权限代码：先静态审计、锁定提交/包哈希、临时 profile 测试，绝不把它直接接到私有文献和科研证据路径。 | 只作调研来源。 |

## GitHub 补充发现：可借鉴的工程模式

| 项目 | GitHub 可核验做法 | 对 CosMatter 的结论 |
| --- | --- | --- |
| [dsh-plugin-reducer](https://github.com/ArmyWas/dsh-plugin-reducer) | 在每次探测中使用新的临时 shadow `DSH_HOME`，不改真实 profile、不运行包管理器；用 delta debugging 找出导致失败的 1-minimal bundle 集，并输出脱敏报告。 | 借鉴“外置诊断 + 一次一套干净 profile + 脱敏报告”。它适合定位 DSH 组合故障，不能当作对插件安全性的证明。 |
| [dsh-poison-guard](https://github.com/zoahdev/dsh-poison-guard) 与其 [GitHub Action](https://github.com/zoahdev/dsh-poison-guard-action) | AST、反混淆和安装生命周期脚本扫描，可作为 CI 失败门槛；项目自己也明确静态分析不是安全保证。 | 把“安装脚本、动态代码、环境读取、隐蔽网络外发”作为自有 CI 的审计类别；扫描器本身也必须锁版本、审查后才可使用。 |
| [DSH 1024Store 讨论](https://github.com/deepseek-ai/deepseek-harness/discussions/1922) | 目录维护者强调：格式校验或收录不等于安全审查；建议机器可读兼容性、版本和安装构建信息。 | 进一步支持为 CosMatter 维护机器可读的 bundle 准入清单，而不是依赖 `dsh-plugin` topic、star 或目录标签。 |
| [dsh-task-notice-board](https://github.com/SLin-code/dsh-task-notice-board) | 将 Workspace → Task → Session 作为长期协作边界，向每个 session 提供有界任务快照和保留更新，而不是复制完整对话。 | 可借鉴“有界上下文 + 任务状态板”；CosMatter 只应显示运行、审核、失败和完成的控制面，不应将原文或证据内容放入跨 session 看板。 |
| [dsh-auth-gate](https://github.com/zephaniahwang94-cmyk/dsh-auth-gate) | 对 HTTP/WebSocket 做 fail-closed 身份验证和升级前防护；项目也注明依赖 DSH 内部 Web 接口，升级后需重测。 | 仅当 DSH Web 或本地 API 被反向代理、局域网或公网暴露时才考虑应用层认证；保持 loopback-only 时不引入额外复杂性。 |

这些都属于社区项目或讨论中的实现经验，非官方认证。它们只能用来完善本项目的设计与测试；不应被当成可直接安装到含 `.env`、私有全文或生产研究运行的信任来源。

## GitHub 市场与 Registry 对比

下表对比的是“市场/目录自身声明和其公开源码”，不是对其中任一插件的独立安全审计。数字、榜单和目录内容会变化，因此不以收录数量或 star 数作为推荐依据。

| 市场/目录 | 发现与验证方式 | 安装面 | 适合如何使用 | 对 CosMatter 的取舍 |
| --- | --- | --- | --- | --- |
| [DSH Plugin Directory](https://github.com/alexchenzl/dsh-plugin-directory) | GitHub issue 提交，自动检查公开包目录、`package.json` 与 `dsh.bundle.patch`；明确不运行插件或安装命令。 | 只展示作者文档中的命令。 | 作为“结构存在”的发现线索。 | 可查找候选；不能作为兼容性或安全证据。 |
| [Harness Registry](https://github.com/majiayu000/dsh-plugin-registry) | 合并 curated 目录与 GitHub topic 发现，验证 bundle manifest，发布 schema 化 JSON snapshot；README 标注 pre-release。 | 提供复制安装信息。 | 参考其公开 schema、健康门槛和 audit queue 设计。 | 不让生产 profile 读取其动态数据；如引用，只摄取固定快照并审计差异。 |
| [ydhrdh/dsh-marketplace](https://github.com/ydhrdh/dsh-marketplace) | 每个条目为 Git PR 审查的静态 JSON；宣称 `verified` 需维护者审阅与 CI。 | 复制 `dsh plugin add` 命令。 | 借鉴 PR 可审计的静态注册表。 | 推荐其“Git 中的静态 registry”模式，不需要安装市场 UI。 |
| [dsh-market](https://github.com/dsh-market/dsh-market) | DSH 内市场，实时拉取 curated JSON；限制来源、默认阻断 build scripts，并可更新/热切换。 | Web UI 会触发 profile 变更。 | 仅用于理解一键安装的风险与 UX。 | 不装入 CosMatter profile：市场本身具有安装、更新、patch 写入等高权限面，动态数据源也扩大了供应链。 |
| [dsh-subscribe](https://github.com/zoahdev/dsh-subscribe) | Web 订阅清单 + CLI 同步 + DSH 内搜索；有 registry snapshot 和 clean-profile CI 说明，也会处理 pnpm `allowBuilds`。 | 可批量同步、安装、更新与批准构建脚本。 | 借鉴“导出后审阅再执行”和干净 profile CI。 | 禁止批量 sync 到含私有数据 profile；只允许人工审阅的单包、固定版本准入。 |
| [dsh-plugin-market](https://github.com/NanmiCoder/dsh-plugin-market) | 抓取 manifest、patch、README、release 与 npm 信息；以确定性规则生成 trust tier 和唯一可执行 spec，模型摘要不影响安装。 | Web 端只提交 catalog ID，宿主再解析并校验 spec。 | 这是最值得借鉴的“展示数据与授权/执行数据分离”模式。 | 可复用为本地、只读准入工具：catalog ID → 自有 allowlist → 版本化 spec；但不采用其一键安装路径。 |

### 市场调研结论

1. **目录收录仅是发现，不是准入。** 即便可验证 `dsh.bundle.patch`，也只说明包形状符合 DSH 安装契约，无法证明代码、依赖、安装脚本、运行时网络行为或科研适用性。
2. **市场插件本身比普通工具更高风险。** 任何“安装、更新、卸载、热加载、写 profile patch、批准 build script”的 UI 都会获得改变 harness 组成的能力；它应比普通只读插件接受更严的审计。
3. **最可迁移的模式是可复核 registry，不是一键安装。** 本项目可维护一个随仓库版本化的 allowlist snapshot，保留来源、解析出的 package spec、commit/tarball 哈希、许可证、兼容性、扫描结论和批准记录。
4. **模型生成的摘要不可参与准入。** `dsh-plugin-market` 将模型摘要与决定安装的确定性规则分离；CosMatter 也应把任何模型分类/推荐严格限定为 display-only。
5. **动态 registry 的网络访问必须隔离。** 研究 profile 不应在启动或任务运行时查询外部市场；候选发现应在无 `.env` 的独立环境中完成，生成静态 review artifact 后才进入准入流程。

## 其他能力与应用场景调研

下面的项目均为公开源码中的设计参考；“可借鉴”不表示可跳过本项目既有的证据、授权和供应链门禁。

| 场景 | 公开实现/证据 | 可迁移模式 | CosMatter 决定 |
| --- | --- | --- | --- |
| **离线回归与真实装配测试** | DSH [测试策略](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/testing.md) 要求按单元、覆盖率、真实 API、录制快照、浏览器快照分层；[LLM replay](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/test-support/llm-replay/README.md) 以录制的 `session.jsonl` 在无 API key 下重放真实 agent。 | 仅 mock LLM/网络/时钟等不确定边界，其余使用真实 loader、工具注册、会话和持久化；对每个非平凡场景保存、审阅并重放 fixture。 | **应自建，P0。** 为七个 bundle 和“任务创建 → 检索 → 审核 → 受限导出”建立公开/合成 fixture。私有文献、`.env`、令牌、完整问题和真实 provider 响应一律不进入 replay。 |
| **研究检索与事实边界** | [dsh-academic-research](https://github.com/userInner/dsh-academic-research) 明确区分公开元数据、摘要与全文链接，并不把链接当成已读全文；其工具不接收凭据。 | 检索输出应携带来源状态与覆盖限制，且“发现链接”不能升级为“已阅读/已接受证据”。 | **仅借鉴边界，不安装。** 现有 Sciverse/source-map 流程优先；若增加公开元数据备用通道，必须使用独立只读 provider、产生 receipt，且仍需通过既有证据接受门禁。 |
| **项目笔记与可编辑记录** | [dsh-research-notes](https://github.com/fff122/dsh-research-notes) 将笔记保存为 workspace 内人可读 Markdown，并提供保存、搜索、导出；其 README 清楚限定写入目录。 | 人工可读源文件 + 可重建索引 + workspace containment。 | **可自建为 P1 决策记忆的实现细节。** 仅记录授权、运行偏好、失败原因和待办；不可写入论文原文、材料事实或“已接受证据”的替代副本。 |
| **受控 PDF 本地读取** | [dsh-pdf](https://github.com/sunshine-lang/dsh-pdf/blob/main/README.en.md) 用本地 PDF.js、逐页标记、文件/页数/字符上限及显式截断，并经 harness 文件系统边界读取。 | 所有原文读取应有文件、页和字符上限，输出保留定位，截断必须显式。 | **仅借鉴，默认不接入。** CosMatter 已以 MinerU 为解析路径；本地 PDF 工具至多作为离线诊断/抽样验证器，绝不把全文自动送给模型，也不绕过“筛选—同意—审核”链路。 |
| **受控本地检索/RAG** | [mindspace-dsh-local-rag](https://github.com/Spirtxiaoqi7/mindspace-dsh-local-rag) 采用按需 tool call 而非每轮 prompt 注入；声明来源、版本、会话隔离和不可信材料边界。 | “按需调用、固定结果上限、来源定位、检索材料不覆盖当前指令”优于无差别全文注入。 | **应做窄化版本，P1。** 仅索引已批准的 evidence card、引用摘要和脱敏报告；工具名可为 `search_accepted_evidence`。不索引原始 PDF、MinerU Markdown、未接受 source map 或会话原文。 |
| **公共网页/PDF 发现** | [dsh-browser-automation](https://github.com/acosmi/dsh-plugin/tree/main/plugins/dsh-browser-automation) 使用每会话临时浏览器 profile、无登录态、受限公网 egress、一次性写操作审批和有界语义快照。 | 将“寻找公开候选链接”与“登录网站/下载/解析/导入证据”拆成不同阶段；网页内容始终是不可信材料。 | **仅作 P2 的独立公共发现 broker 设计参考。** 无 cookie、无账号、严格域名 allowlist、仅返回 URL/标题/时间/摘要和 receipt；下载 PDF 或交给 MinerU 前仍需现有显式授权。当前不安装浏览器插件。 |
| **外部工具/MCP** | 官方 [MCP client](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md) 把外部 MCP 的工具暴露为 `mcp__<server>__<tool>`；官方也指出工具定义会增加每次请求 token，慢/故障服务器会影响启动，且不桥接 resources/prompts。 | 将每个外部能力视为有独立超时、凭据、网络与失败模式的工具边界，而不是“无成本连接器”。 | **P2 条件式。** 只有当现有 Python loopback 适配层无法满足且形成明确需求时，才开发本地 allowlist MCP façade；不把通用文件系统、浏览器、数据库或 GitHub MCP 直接接入含私有资料的研究 profile。 |
| **多运行控制与远程 relay** | [Harness Relay MCP](https://github.com/tonytanglab/deepseek-harness-relay-mcp) 可从外部 MCP agent 启动、等待、取消、重定向 DSH 运行，即使其默认 loopback 也需 bearer token、workspace 路由和持续兼容性维护。 | “持久 run identity + 状态查询 + 幂等恢复”值得借鉴。 | **当前拒绝安装。** CosMatter 可在本地看板实现只读 run/status 投影；不暴露 start/cancel/steer 的远程控制面。只有完成威胁建模、认证、审计和回归后才评估只读状态导出。 |
| **本地用量与隐私可视化** | [Harness Insights](https://github.com/mapan0424/deepseek-harness-insights) 仅汇总结构化 usage、provider/model、工具名和时间戳，不存会话正文、不读取 key、不上传数据。 | 先聚合结构化遥测，再考虑 UI；避免为了成本面板读取消息正文。 | **可借鉴，P2。** 仅展示 run 级调用次数、时延、模型名、缓存/成本估算和失败类别；不展示 prompt、摘要、来源 URL、任务 ID 或密钥。 |

### 场景调研结论

1. **最优先缺口是可重放验证，不是更多插件。** 现有受限链路只有在“无 key、无私有资料、真实装配”的回归测试下才能稳定演进。
2. **检索能力应按证据等级分库。** 可检索的“已批准证据卡”可提升跨运行效率；原始全文、未审核提取和模型记忆仍应隔离。
3. **公共网页发现可以补足 provider 覆盖，但不应改变数据边界。** 它只能产出不可信候选及其 receipt，不能直接生成事实或绕过人工阶段。
4. **MCP 和 relay 是控制面扩展，而非免费集成。** 它们会引入工具定义、子进程/网络、认证、超时和权限等新的运行边界；当前由 Python loopback 领域层承载更容易审计。

## 第二轮公开生态能力地图（只读发现）

本轮使用 GitHub 公开仓库页面与只读 API 查询候选的 README、许可证信号和仓库元数据；**没有 clone、安装、构建或执行任何第三方包**。所有新增条目也只记录在 `configs/dsh_market_snapshot.json`，状态均为 `untrusted_discovery_only`，不构成准入、兼容性结论或科学证据。

| 能力/场景 | 公开实现所声称的设计 | 对 CosMatter 可迁移的最小模式 | 决定与风险边界 |
| --- | --- | --- | --- |
| **固定来源的生态目录** | [Awesome DSH Plugins](https://github.com/coolbat/awesome-dsh-plugins) 以固定 commit 检查 bundle manifest、patch、许可和生命周期脚本，并把“已审阅”“暂缓”“排除”分开；其自动发现不会自动提升候选。 | 将本项目的市场 snapshot 后续演进为“候选队列 + 固定 commit + 可复核理由”，并保持候选不能自动进入 `third_party_admissions`。 | **P1 借鉴。** 目录的结构审阅不等于安全或运行时兼容；只接受人工固定的 snapshot diff。 |
| **隔离的 DSH 版本实验室** | [dsh-testsuite](https://github.com/cocofhu/dsh-testsuite) 使用预构建 DSH runtime 镜像、健康检查和短生命周期环境来测试不同版本/插件组合，也明确其控制面可注入 key 和预装 package。 | 在无密钥、无私有工作区的前提下，可为 release gate 另建短生命周期、网络默认关闭的兼容性实验室。 | **P2 条件式。** 不复用其模型预设/密钥注入、Docker socket、自动拉取镜像或 Kubernetes 控制面；这些都是超出当前本地测试的额外权限。 |
| **大规模自动发现与运行级探测** | [DSH Plugin Radar](https://github.com/AdamPlatin123/dsh-plugin-radar) 宣称按周期发现候选、生成快照并对候选作运行级测试。 | “目录是构建产物”可作为市场摄取的设计原则：发现、静态审阅、隔离兼容性、人工准入必须分层留痕。 | **仅作架构参考。** 运行通过不能证明插件安全；CosMatter 不拉取其动态目录、不采信其状态、更不运行其发现/探测基础设施。 |
| **发布物、兼容性与最小权限 profile** | [dsh-applications](https://github.com/sympoies/dsh-applications) 以协调的 release artifact、兼容性证据和最小权限 bot profile 分离公共包与私有部署绑定。 | 将“public recipe / immutable artifact / private binding”三层作为当前兼容性与 Harness recipe 的持续约束。 | **已部分自建，继续保持。** 不接入其 runtime adapter 或 profile；它仍是第三方 TypeScript 代码。 |
| **任务契约、完成证据与故障恢复** | [dsh-omni-router](https://github.com/qwe225380/dsh-omni-router) 用 Task Contract、evidence/freshness/acceptance coverage 与改变策略的恢复纪律约束“完成”宣称。 | 每个 CosMatter 阶段可进一步显示：允许的输入等级、完成断言、产物哈希、人工门、失败恢复分支。 | **P1 设计参考。** 当前不变量审计与 replay 已覆盖核心模式；绝不把模型自述、测试输出或插件标签单独当科学事实的证据。 |
| **形式化研究流程与证明义务** | [math-research-dsh](https://github.com/xsoc1/math-research-dsh) 将研究管理、工作流和 Lean 形式化审计拆分为独立 skill，并保留阶段交接和验证工件。 | 对材料研究可借鉴“claim contract”：每个可见主张显式声明证据等级、适用条件、可证伪检查和人工裁决。 | **P2 借鉴，非直接复用。** Lean 证明不等同于实验/文献结论正确；不安装该技能，也不把形式验证标签升级为材料事实。 |
| **领域科研工作台与知识治理** | [Kunpeng SmartBreed](https://github.com/LIYIN2/kunpeng-smartbreed) 面向育种科研，把文献问答、数据治理、分析输入门禁、审阅角色和知识撤销状态分开，并明示摘要不能当作已核对全文。 | 领域工作台应把“候选/已审核/撤销/推断”视觉和数据状态隔离；正式决策须落在审计轨迹上。 | **P2 产品参考。** 其领域知识库、登录、团队角色和研究数据均不进入 CosMatter；仅采纳通用治理边界。 |
| **免 key 公共网页搜索** | [dsh-web-search-free](https://github.com/sheep-programmer/dsh-web-search-free) 把查询转给第三方公共搜索/MCP 端点，并可通过 profile patch 切换 provider。 | 它反向验证了“免 key 不等于无外发或无隐私风险”：查询文本、返回材料与远程端点仍是外部数据边界。 | **明确不接入。** 公共候选发现只能作为未来独立 broker，且无登录态、限域、URL/摘要上限、receipt、明确下载/解析授权；不得由市场插件修改 research profile。 |

### 第二轮的应用优先级

1. **运行级阶段契约投影已落地。** 它建立在现有 runtime invariant、Artifact contract 和 replay 上，为每一步给出固定的“完成条件、人工门、预期输出、非执行恢复路线”和安全状态；不需要新 plugin 或外部模型，且不暴露审计细节。
2. **运行级聚合遥测与本地单运行看板已落地。** 侧栏只轮询 loopback 的阶段契约和遥测，显示下一阶段、人工门、固定恢复标签与聚合调用计数；成本与延迟只在已有人工复核披露时显示，不能估算配额、性能或触发重试。跨会话提醒仍是后续 P2。
3. **把生态发现升级为有固定来源的候选队列，而非更大的插件市场。** 先增加 snapshot 的 review diff/固定 commit 记录，再决定是否审计一个候选；不对动态目录或其“已测试”徽章赋予执行权。
4. **若以后需要扩大为团队研究工作台，先做本地角色/撤销/审计模型，再评估网络入口。** 不能反过来先接入 OAuth、SSH、webhook、群聊 relay、SFTP、自动更新或多租户平台。
5. **公共搜索只能解决候选发现，不解决证据。** 即使提供商匿名、免费或以 MCP 形式出现，也必须经外发同意、候选筛选、全文访问确认、Source Map 与人工接受门。

## 优先级改进建议

| 优先级 | 建议 | 预期收益 | 明确边界 | 可验收标准 |
| --- | --- | --- | --- | --- |
| P0 | **增加 DSH bundle 发布兼容性门禁**：建立 `dsh_compatibility.json`（已验证的 DSH/Node/包版本），CI 在全新 `DSH_HOME` 安装 tarball，并以 `dsh --dump-config` 和一条无外部调用的 loopback 工具请求冒烟。 | 防止 DSH preview 升级或 Git 安装缺 `lib/` 导致生产 profile 无法加载。 | 不从 GitHub `main` 直接安装；测试 profile 不读 `.env`、不调用提供商。 | 七个 tarball 都含 `lib/`/patch/README；干净 profile 7/7 加载；版本不匹配则失败且给出可读错误。 |
| P0 | **为外部任务传递 DSH `callId` 并做幂等恢复账本**：将 `exec.callId`（或等价稳定调用 ID）哈希化写入授权、provider receipt 和 MinerU 任务记录；为“调用已持久化、结果未知”增加只读状态核验与显式恢复命令。 | 崩溃/超时后避免重复上传 PDF、重复消耗 API 配额或误把未知结果当成功。 | 不自动重放外部副作用；恢复前须查询供应商状态或要求新的明确同意。 | 同一 callId 重试只得到同一本地记录；模拟断点产生 `unknown`，不会二次提交；恢复事件可审计。 |
| P0 | **第三方 bundle 准入清单与供应链审计**：记录来源 URL、提交/包哈希、许可、权限面、网络/文件/凭据触达、审计日期和隔离 profile 结果。 | 将“插件目录中的发现”转成可复核的准入决策。 | 目录、star 数、安装命令都不是信任凭证；未审计包不可进入有 `.env` 或私有文献的 profile。 | 新包无准入条目则 CI/安装脚本拒绝；审计表对每个包有责任人、复审期限和回滚命令。 |
| P0 | **安装前代码与依赖卫生检查**：在准入流程中分别检查生命周期脚本、混淆/动态执行、环境变量和网络外发，以及 lockfile、许可、非 registry 来源和声明/安装版本漂移。 | 提早发现 bundle 自身及其依赖图的高风险形态。 | 扫描结果只是风险信号，不能替代人工代码审查、最小权限 profile 或供应链固定。 | 每个候选包生成结构化报告；HIGH 风险或未解释的安装脚本阻断准入；审计基线变动必须复审。 |
| P0 | **只读市场摄取防火墙**：外部目录/市场仅作为独立环境里的候选来源，产出版本化 `market_snapshot`；生产 profile 只读取仓库内已批准 allowlist，绝不让市场 UI 或远程 JSON 直接改 profile。当前以冻结基线、脱敏 diff 指纹和人工复核记录约束每次快照变更。 | 获得生态发现能力，同时杜绝一键安装、动态 registry 和远程市场更新改变研究运行。 | snapshot 不含 `.env`、本地路径、会话、论文标题/原文；候选状态默认 `untrusted_discovery_only`；review 仅保存候选 ID、变更数量和哈希。 | 外部 registry 断网时生产 profile 行为不变；`verify_dsh_market_snapshot_review.py` 必须验证当前快照、基线和人工 diff 记录一致；任何未在 allowlist 的 spec 被拒绝。 |
| P0 | **分层、可重放的工作流验收包**：为七 bundle 组合及关键状态机编写合成/公开 `session.jsonl` fixture、`workspace.expected` 和真实 loader 烟测；以重放 LLM 替换真实 provider。 | 在不消耗 key、不发送资料的条件下，验证发布物、工具注册、持久化、授权门禁与失败恢复。 | 只记录经脱敏审查的输入/输出；mock 仅限 LLM、网络、时钟，禁止用模型自述作断言。 | 新增非平凡能力必须附 fixture；外部调用断网时全部 replay 通过；篡改 artifact、授权或状态机关系能稳定失败。 |
| P1 | **受限 Artifact/渲染契约**：为报告、状态摘要、图投影和已批准导出定义 `cosmatter.artifact/v1`，由 DSH Web 卡片显示标题、哈希、生成时间、信任状态和下载入口。 | 用户无需解析 JSON；报告链路更可观察。 | 仅 allowlist 的已生成文件；不提供原始 PDF、MinerU Markdown、source URL、密钥、未接受证据或任意路径读取。 | schema 拒绝未知字段；测试证明敏感字段不出现；前端只允许每个 artifact 的固定路由。 |
| P1 | **项目决策记忆（非科学记忆）**：采用 Markdown + JSON/SQLite 索引的双写模式，记录授权决定、失败原因、运行偏好、待办与已验证环境；每条含来源、过期时间和人工可编辑状态。 | 跨 session 延续工程上下文，降低重复配置与误操作。 | 不自动抽取/注入论文正文；不得成为事实、引用或证据接受的来源；默认本地、按 project 隔离。 | 删除/编辑 Markdown 可重建索引；事实报告中不会引用该库；检索结果带 `not_scientific_evidence`。 |
| P1 | **DSH 不变量 companion / 运行后审计**：参考官方 runtime invariant 模式，检查任务状态迁移、授权—receipt—结果配对、artifact 哈希和“证据接受必有人工决定”等关系。 | 让跨 bundle 的错误在加载/运行后立即暴露，不只依赖单元测试。 | companion 只读；发现异常应阻断后续敏感阶段，但不篡改原工件。 | 有意破坏每一类关系的 fixture 均失败；正常完整运行通过并生成不含敏感内容的审计摘要。 |
| P1 | **组合故障最小化实验室**：在自有测试工具中复制 shadow profile + 受控 probe 的思路，对七个 bundle 的任意组合运行 `--dump-config`、loopback 健康检查和无外部调用 fixture。 | 新增 bundle 或 DSH 升级出问题时，可得到最小可复现组合而非猜测。 | 实验室不得复制 `.env`、会话、私有文献或运行目录；probe 必须无外部调用。 | 造出二插件冲突 fixture 后能报告两者；产出的 JSON 不含绝对路径、token、问题文本或文献内容。 |
| P1 | **CosMatter Harness Recipe / 评测包**：将“七 bundle + 固定 DSH/Node 版本 + fixture + 断言 + 环境摘要”定义为版本化 recipe，记录质量、延迟、安全和兼容性结果。 | 避免把“插件能加载”误写成“该组合对科研工作流可靠”。 | 评测数据必须为合成/公开、无密钥 fixture；出版性或科研结论不从 recipe 分数推出。 | 每次版本升级生成可比较报告；报告注明 bundle、DSH、Node、OS、fixture 和已知限制。 |
| P1 | **已批准证据检索（非全文 RAG）**：把可搜索语料限定为已接受 evidence card、引用摘要与已发布的脱敏 artifact；按来源 ID、版本、接受状态和生成时间返回有界结果。 | 在不向模型持续塞入长上下文的情况下，复用已审核结论并保留可追溯性。 | 禁止摄取原始 PDF、MinerU Markdown、未接受 source-map、用户问题或会话正文；检索命中是线索，非新事实。 | 每条命中有 evidence ID/版本/定位；越权语料无法入库；删除或撤销接受状态后立即不可检索。 |
| P1 | **provider 故障注入与恢复矩阵**：对 Sciverse、DeepSeek、MinerU 的超时、401/429、半成功、重复回调、畸形响应和“已提交但结果未知”建立模拟 adapter。 | 防止将失败、重复提交或不完整解析误写为科研结论。 | 不调用真实 provider；不使用真实 token、任务 ID、论文或响应体。 | 每一种故障均产生预期 receipt/status；未知结果不会自动重放；恢复前必须执行只读状态核验。 |
| P2 | **会话内提醒与成本/配额可视化**：已实现只读 `operational_telemetry`、当前运行侧栏和跨会话本地 reminder board；后者只聚合最早未完成的人工门/阻断、运行时注意、未知外部结果与决策记忆中到期的待办，页面每次读取时才更新。 | 改善长任务操作体验，同时避免下游连锁阻断造成提醒风暴。 | DSH schedule 不是可靠 cron；提醒不是后台任务，不自动执行外部调用，也不把成本估算冒充账单。 | session 恢复后 overdue 状态可见；关闭会话不会伪称任务已执行；无 provider key 的本地运行也可查看零调用摘要。 |
| P2 | **声明式并行阶段执行器**：现已提交固定的版本化 JSON DAG 与 loopback 就绪投影：九阶段严格线性、最大并发固定为 1、允许 descriptor 与数据等级均在代码库内校验；它只声明依赖和至多一个“可就绪”阶段。真实调度、取消和跨会话执行尚未实现。 | 先让编排边界可审计，再评估是否有值得放开的受控并行。 | 不执行模型生成 JavaScript；DAG 不授予执行授权，外部边界仍走现有授权与人工门禁。 | 未在 allowlist 的阶段/依赖/工具、非串行依赖或并发值都会被拒绝；投影不含问题/全文/URL/命令；真实调度器进入后才验收取消与重放轨迹。 |
| P2 | **运行—任务—会话控制面看板**：当前单运行侧栏已按“下一阶段、等待人工、注意状态”显示由 allowlisted loopback 投影派生的脱敏状态；多运行/跨会话看板仍待后续需求确认。 | 让多运行并行时的操作状态可见。 | 只读、聚合、脱敏；不显示源文本、完整问题、URL、任务 ID、密钥或未接受事实。 | 无权限状态只能见计数；导航不触发执行；每个显示字段可追溯到 allowlisted 本地投影。 |
| P2（条件式） | **公共候选发现 broker**：已提交独立无凭据 HTTP 边界与版本化 allowlist：仅允许 HTTPS、明确域名、最多三次无循环重定向。`execute-plan-public-arxiv-discovery` 现可用已批准检索式调用 allowlisted arXiv Atom 元数据端点，`register-public-pdf-candidate` 可对显式提供的 allowlisted PDF 做五字节签名/媒体类型探测并登记可达性；不执行网页搜索、HTML 解析或自动下载。 | 当主 provider 覆盖不足时，可先以可审计边界准备受限发现能力。 | 无登录态、无 cookie、无正文持久化；Atom 候选默认不可读，URL 只在调用期间使用，运行内只记录哈希；MinerU 提交仍需筛选和明确授权。 | DNS/私网/IP/重定向越界请求 fail closed；Atom/XML、PDF probe 和候选工件均不泄露 URL；网页/HTML transport 进入前仍须覆盖断网和恶意 HTML fixture。 |
| P2（条件式） | **本地 allowlist MCP façade**：仅向 DSH 暴露少量自有、只读、明确 schema 的领域工具；每个工具固定超时、数据等级和审计字段。 | 将不可避免的外部扩展限制为可观测的单一边界。 | 不接入通用 filesystem、浏览器、GitHub、数据库或会话控制 MCP；默认不加载，凭据只由本地适配层读取。 | 未登记的 MCP server/tool 不能启动；工具故障不伪造成功；每次调用生成脱敏 receipt 且无正文/密钥外泄。 |
| P2（条件式） | **远程访问防护**：如果部署从 loopback 扩展到反向代理或局域网，增加 HTTP 和 WebSocket 的身份验证、CSRF/Origin 策略、TLS、限速与升级回归测试。 | 降低共享控制面暴露时的未授权访问风险。 | 当前 `127.0.0.1` 本地开发情形不引入远程入口；不要用本地 token 方案替代网络隔离。 | 任一未受保护的 HTTP/WebSocket 路由使启动失败；DSH 升级后执行全套远程入口回归。 |

## 推荐实施顺序

1. P0 的可重放验收包、发布兼容性、准入清单、依赖/代码卫生和只读市场摄取：先让已有七个 bundle 在无 key 的真实装配中可复核，避免 DSH 快速演化或社区包造成不可见风险。
2. P0 的幂等账本：在下次扩展任何外部调用前，完成稳定调用 ID、unknown-outcome 和显式恢复测试。
3. P1 的 provider 故障注入、recipe、组合故障实验室、Artifact 与不变量：让失败路径与成功路径同样可验证。
4. P1 的决策记忆和已批准证据检索：仅在明确的 project 数据目录中启用；先以人工编辑和可撤销记录为主，不开全文摄取。
5. P2 的看板、提醒、声明式 DAG、公共候选发现与 MCP façade：以纯本地、无 provider 的 fixture 验证后，再考虑受控外部链路；远程访问防护只在网络暴露时启用。

## 不建议采用的做法

- 不把通用社区 MinerU 插件接到当前私有文献路径：它会绕开当前“筛选—明确同意—仅任务元数据—人工证据门禁”的细粒度边界。
- 不把 `dsh-mneme` 或任何通用记忆插件直接当作科研事实库：它的记忆功能适合偏好与工程上下文，不能替代来源定位和证据核验。
- 不因 worker thread/`node:vm` 就视模型脚本为已隔离；官方文档明确不是安全沙箱。
- 不将 DSH session schedule 当作后台可靠调度器，也不允许它自动重跑有费用或私有内容的任务。
- 不以插件目录、下载量或 star 数代替源代码、许可证、网络权限和配置层审计。
- 不把“已批准证据检索”扩展为私有全文/会话全文 RAG：检索只应复用可撤销、可定位、已审核的证据卡与脱敏 artifact。
- 不因 MCP 是标准协议就连接通用 server；其进程、网络、工具定义、凭据与超时都是新的攻击面和运行依赖。
- 不对外暴露 DSH 的 start/cancel/steer 等控制面；本地只读 run 状态投影已足够覆盖当前研究工作流的可观察性。

## 来源与可复核性

- [DeepSeek Harness 官方概览](https://www.deepseek.com/harness/en/)（架构、developer preview 状态）
- [DeepSeek Harness 源码仓库](https://github.com/deepseek-ai/deepseek-harness)
- [官方 bundle 发布与 Git 安装指南](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md)
- [官方 session checkpoint policy](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/session/session-checkpoint-policy/README.md)
- [官方 workflow subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/workflow.md) 与 [worker-thread 安全边界](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/workflow/workflow-worker-thread/README.md)
- [官方 tool catalog（schedule）](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-catalog.md) 与 [config catalog](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/config-catalog.md)
- [官方 runtime diagnostics / invariants](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/runtime-diagnostics/invariants/README.md)
- [DSH Vision Toolkit](https://github.com/Anionex/dsh-vision-toolkit)（社区工程模式参考）
- [dsh-mneme](https://github.com/modusensus/dsh-mneme)（本地、可编辑记忆模式参考）
- [HackSing/dsh-plugins](https://github.com/HackSing/dsh-plugins)（发现目录，非安全背书）
- [dsh-plugin-reducer](https://github.com/ArmyWas/dsh-plugin-reducer)（shadow profile 与最小故障集模式）
- [dsh-poison-guard](https://github.com/zoahdev/dsh-poison-guard) 与 [GitHub Action](https://github.com/zoahdev/dsh-poison-guard-action)（安装前供应链扫描模式）
- [DSH 1024Store 讨论 #1922](https://github.com/deepseek-ai/deepseek-harness/discussions/1922)（目录元数据与安全边界讨论）
- [dsh-task-notice-board](https://github.com/SLin-code/dsh-task-notice-board)（有界任务—会话控制面模式）
- [dsh-auth-gate](https://github.com/zephaniahwang94-cmyk/dsh-auth-gate)（条件式远程访问防护模式）
- [DSH Plugin Directory](https://github.com/alexchenzl/dsh-plugin-directory)（结构校验型目录）
- [Harness Registry](https://github.com/majiayu000/dsh-plugin-registry)（manifest 校验与 schema snapshot）
- [ydhrdh/dsh-marketplace](https://github.com/ydhrdh/dsh-marketplace)（PR 可审计静态 registry）
- [dsh-market](https://github.com/dsh-market/dsh-market)（DSH 内一键市场的权限与动态目录风险参考）
- [dsh-subscribe](https://github.com/zoahdev/dsh-subscribe)（订阅同步、allowBuilds 与干净 profile 验证参考）
- [dsh-plugin-market](https://github.com/NanmiCoder/dsh-plugin-market)（确定性 install spec 与信任分级参考）
- [官方 DSH 测试策略](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/testing.md) 与 [LLM replay](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/test-support/llm-replay/README.md)（分层、真实装配、无 key 重放模式）
- [dsh-academic-research](https://github.com/userInner/dsh-academic-research)（公开元数据、全文链接与证据等级边界参考）
- [dsh-research-notes](https://github.com/fff122/dsh-research-notes)（workspace 内可编辑 Markdown 记录模式）
- [dsh-pdf](https://github.com/sunshine-lang/dsh-pdf/blob/main/README.en.md)（本地 PDF 有界读取模式）
- [mindspace-dsh-local-rag](https://github.com/Spirtxiaoqi7/mindspace-dsh-local-rag)（按需检索、来源定位与不可信材料边界）
- [dsh-browser-automation](https://github.com/acosmi/dsh-plugin/tree/main/plugins/dsh-browser-automation)（隔离公共浏览与 egress/审批模式）
- [官方 MCP client](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)（外部工具接入的超时、令牌与启动边界）
- [Harness Relay MCP](https://github.com/tonytanglab/deepseek-harness-relay-mcp)（外部运行控制面的复杂度与安全边界参考）
- [Harness Insights](https://github.com/mapan0424/deepseek-harness-insights)（仅结构化遥测的本地可视化模式）

外部项目均可能快速变化；实施前应重新核验其版本、提交、许可与安全策略。本文所有建议均以 CosMatter 当前本地 bundle 和领域门禁为主，不依赖第三方插件的持续可用性。
