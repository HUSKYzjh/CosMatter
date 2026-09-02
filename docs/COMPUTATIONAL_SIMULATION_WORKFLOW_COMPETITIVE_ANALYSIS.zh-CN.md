# 自动化／半自动化计算模拟科研工作流：竞品分析与 CosMatter 提升路线

> 调研日期：2026-09-02  
> 范围：材料与原子尺度计算中的工作流编排、计算资源调度、可追溯性与主动学习；不将文献检索、通用 LLM Agent 或实验室机器人单独视作同类产品。  
> 证据方法：只采用项目官方文档或官方主页描述能力；“未提及”不等于该项目绝对不具备该能力。

## 结论先行

CosMatter 不应与 AiiDA、atomate2、DP-GEN 竞争“谁能更快批量提交 DFT 作业”。这些项目已在各自层面深耕执行器、调度器或势函数主动学习。CosMatter 的合理定位是**证据驱动的计算研究控制面（research control plane）**：把文献中已审核的条件、矛盾、可证伪假设与计算协议连接到一个被人工批准的计算活动，并把其结果严格回链到输入、软件环境、收敛判据和结论边界。

当前仓库已具备这个方向的起点：`MissionBrief`、`EvidenceCard`、人工门禁、计划型势函数基准、外部结果导入比较和审计工件；但 DFT、势函数训练与 MD 舰队仍明确是 `framework_only`，本机配置也刻意禁止调度、轮询和命令模板。因此，近期目标应是建立可复跑、默认不执行的“计算活动契约”，再通过一个受限适配器接入成熟执行后端，而不是直接开放任意 shell、SSH 或 HPC 提交。

## 1. 当前 CosMatter 基线

| 已有能力 | 当前证据 | 对计算工作流的意义 | 尚缺少的环节 |
|---|---|---|---|
| 文献证据与人工审核链 | `Source Map → EvidenceCard → conflict/gap`，有来源定位、条件字段与审计门禁 | 可让一个模拟假设追溯到具体、限定条件下的文献主张 | 尚未定义“哪一张 EvidenceCard 支持哪一个模拟输入/假设”的正式关系 |
| 任务与计划工件 | 任务状态机、舰队契约、`dft_mission_plan` / `training_plan` / `md_protocol` 的框架 | 可作为研究意图和人工批准的入口 | 没有统一的 `SimulationCampaign`、输入清单、运行实例和重试状态机 |
| 势函数公平比较 | 生成域内／边界／域外的确定性测试计划；只导入已批准的外部结果摘要 | 已避免把单点误差误写为泛化能力 | 尚无训练数据冻结、结构生成、执行器适配和模型版本/产物谱系 |
| 运行安全边界 | `machine_config` 只允许 `plan_only`，执行容量为零，拒绝队列、路径、凭据和命令模板 | 正确避免无授权的 HPC 与商业软件调用 | 需要可审核的、独立于 `.env` 的执行配置与批准流程 |

依据：[舰桥舰队架构](architecture/08_舰桥舰队架构与FrontierLens吸收.md)、[势函数框架测试](competition_submission_2026_08.zh-CN.md)、[`machine_config.py`](../src/cosmatter/machine_config.py)。

## 2. 代表性竞品／参照系

| 平台 | 自动化重心与官方证据 | 强项 | 对 CosMatter 的启示 | 不宜直接照搬的部分 |
|---|---|---|---|---|
| [AiiDA](https://aiida.readthedocs.io/projects/aiida-core/en/stable/intro/index.html) | 面向多代码、本地/远程计算的流程引擎；自动记录输入、输出、元数据和过程图，并有检查点与图查询。[数据/过程图语义](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/provenance/concepts.html)区分计算、工作流及其输入/创建/返回/调用关系；官方调度器插件覆盖 SLURM、PBS 等。 | 最成熟的计算谱系与恢复模型；适合作为真实计算回执的权威后端。 | 采用其“数据节点—计算节点—工作流节点”的谱系思想；CosMatter 应存**外部 AiiDA process UUID 与不可变摘要**，而非复制其数据库。 | 不把 AiiDA 的数据库或远程账户直接暴露给浏览器/DSH；不让文献 Agent 直接创建 `CalcJob`。 |
| [atomate2 + jobflow](https://materialsproject.github.io/atomate2/user/index.html) | atomate2 用 `Maker` 组合 `Job` / `Flow`，覆盖结构弛豫、能带、弹性、声子、输运等材料工作流；其[安装架构](https://materialsproject.github.io/atomate2/user/install.html)把输入生成、`custodian` 错误处理、jobflow 和远程/HPC 管理分层。jobflow 支持可组合、动态工作流及本地/队列执行。 | 可复用的材料计算配方、输入集版本化、错误恢复与常见性质流程覆盖。 | 为第一批“配方引用”选择 atomate2：CosMatter 记录 `recipe_id`、Maker 配置摘要、结构/赝势/输入哈希、版本与收敛规则；不自己重写 VASP 流程。 | VASP 许可证、赝势权限、MongoDB/集群配置均由团队执行环境负责，不能假定用户拥有。 |
| [pyiron](https://pyiron.org/) | Python IDE 将 DFT、LAMMPS 等作业对象化；同一结构可切换后端，通过 server/queue 扩展到 HPC，表格化聚合结果。其[工作流教程](https://workshop.pyiron.org/DPG-tutorial-2025/01_introduction.html)用函数节点构图、可视化与执行。 | 对交互式研究者友好；“作业—数据管理—HPC 扩展—分析”在一个开发环境中连贯。 | 前端应借鉴它的“先展示输入、资源、状态、结果，再允许运行”的可见性；为每次执行显示协议、预计资源、取消和失败原因。 | 不将 notebook 的临时状态当作正式证据或长期谱系；CosMatter 的结论门禁必须独立于界面。 |
| [SimStack](https://simstack.readthedocs.io/en/latest/index.html) | 基于 SSH 客户端/服务端，使用可复用的 WaNo 组件组装多尺度流程，并提供 DFT 收敛测试等教程。 | 面向跨尺度与 HPC 协议迁移，强调可复用、可复现、可转移。 | 将“收敛测试”和“协议包”提升为一等工件：参数扫描、停止阈值、失败分类与版本固定都应可审计。 | 不把 SSH 可达性视作执行授权；校内账号只属于经过批准的执行配置，不应进入项目 `.env` 或前端。 |
| [Mat3ra](https://docs.mat3ra.com/reference/workflows/overview/) | 商业云平台将材料、工作流和作业分开；有可编辑工作流库、输入模板化、UI/CLI/API 与云/集群计算。其[作业界面流程](https://docs.mat3ra.com/getting-started/run-first-simulation/web-interface/)是“材料 → 工作流 → 计算资源 → 提交/跟踪/结果”。 | 降低首次计算的界面门槛；模板库、结构化参数与计算资源选择直观。 | CosMatter 的“计算活动”界面可采用同样的显式三元组，但在其前增加“证据与假设”层、在其后增加“人工结论审查”层。 | 不把云端执行、账户资源和其工作流库作为本地默认依赖；商业平台的运行事实不能仅凭 UI 截图导入。 |
| [DP-GEN / DPGEN2](https://docs.deepmodeling.com/projects/dpgen/en/latest/run/overview-of-the-run-process.html) | 面向深度势函数并发学习：训练→探索→选择→第一性原理标注循环；DPGEN2 将训练、探索、选择、标注建模为工作流图，并输出探索报告与数据增量。 | 把不确定度/模型偏差转成“下一批高价值标注”的闭环；有明确的迭代记录与恢复模型。 | CosMatter 的势函数舰队应吸收“选择理由、候选/准确/失败计数、数据增量、终止准则”这些工件，而不是只生成下一批任务文本。 | 在数据集许可、结构去重、标签协议、模型不确定度校准和计算预算均经人工审核前，不能启动主动学习循环。 |
| [ASE](https://docs.ase-lib.org/) | 提供 `Atoms`、Calculator 与优化/MD/分析工具，统一连接多种原子模拟代码；它是轻量集成层而非完整调度/谱系平台。 | 低耦合、广泛的计算器抽象，适合作为结构和轻量后处理的互操作层。 | 把结构、单位、计算器和结果的最小互操作格式设计为适配器边界，可优先支持 ASE-compatible 结构摘要。 | ASE 本身不能替代执行批准、队列审计、长任务恢复或科学结论审核。 |

### 共同模式与关键空白

1. **成熟执行层已经存在。** AiiDA、jobflow/FireWorks、SimStack、Mat3ra 都将作业、资源和状态管理作为核心能力；因此 CosMatter 的首个执行集成应复用一个成熟后端。
2. **材料配方与主动学习是两条不同路径。** atomate2 擅长固定/可组合的性质配方；DP-GEN 擅长训练—探索—标注循环。二者都需要被放在一个更高层、可解释的研究问题和证据边界内。
3. **计算谱系不等于科学论证。** AiiDA 能证明某输出由哪些输入和过程产生，但不能证明它回答了哪篇论文的争议、是否满足适用条件、或能否推广。CosMatter 应承担后半段。
4. **“全自动”需要显式预算与停机条件。** 主动学习和队列执行会放大成本与错误；没有最大作业数、核时/GPU 时预算、失败阈值、收敛/退出标准和人工复核点，就不应称作受控自动化。

## 3. 建议的产品定位：Evidence-to-Simulation Campaign

新增的核心对象不是“计算按钮”，而是一份不可变的 `SimulationCampaign`：

```text
已审核 EvidenceCard / 冲突矩阵
      ↓（人工选择可验证假设）
SimulationHypothesis
      ↓（人工批准协议与资源上限）
SimulationProtocol + ExecutionProfile
      ↓（生成而不运行）
InputManifest + CampaignPlan
      ↓（仅批准的适配器可执行）
ExternalRunReceipt + ResultSummary
      ↓（数值/收敛/谱系校验）
ReviewedSimulationEvidence
      ↓（人工判断是否支持、反驳或不确定）
EvidenceCard / 报告中的限定性结论
```

每一跳都必须保留稳定 ID、输入/输出哈希、软件与配置版本、范围、审批人/时间和失败状态。只导入允许公开或团队有权保留的**摘要与哈希**；原始轨迹、波函数、商业软件日志、队列脚本、私有结构路径与凭据仍在执行环境。

### 最小契约（建议 v1）

| 工件 | 必填字段 | 阻止的错误 |
|---|---|---|
| `simulation_hypothesis.json` | EvidenceCard ID、反例、变量、对照、预期可观测量、失败判据 | 从未审核文本直接生成计算结论 |
| `simulation_protocol.json` | 引擎/版本/许可证声明、方法、结构来源摘要、参数/收敛规范、单位、预算、停止条件 | “跑了 VASP/MD”但不知道具体方法与允许成本 |
| `input_manifest.json` | 每个结构/输入的内容哈希、来源许可、配方/计算器版本、生成器版本 | 输入文件被静默改动，或私有路径泄漏到运行工件 |
| `execution_profile.json` | 适配器类型、允许的引擎与配方、资源上限、允许的队列别名、轮询/重试策略、批准回执 | 任意 shell/SSH/队列提交；将校园账号当作应用密钥 |
| `external_run_receipt.json` | 外部 run ID、状态时间线、输入/输出摘要哈希、退出码分类、消耗资源、环境摘要 | 只凭“成功”文字或截图导入结果 |
| `reviewed_simulation_evidence.json` | 结果摘要、收敛检查、适用域、与假设的关系（支持/反驳/不确定）、审核人 | 数值结果被自动升级成一般性材料结论 |

## 4. 分阶段提升路线

### P0：计算活动契约与 UI 门禁（优先，2–3 周）

- 实现上述六类 JSON Schema/Pydantic 模型、版本迁移、哈希绑定、拒绝测试与脱敏导出。
- 将现有 `dft_mission_plan`、`training_plan`、`md_protocol` 映射为 `SimulationCampaign` 的计划阶段；保留当前 `framework_only`，不启用调度。
- 在舰桥新增“证据 → 假设 → 协议 → 待批准执行”的可视化，明确显示缺失字段、预算和不能继续的原因。
- 验收：合成 fixture 可端到端生成计划与 UI 投影；没有经过批准的 `ExecutionProfile` 时，任何执行 API 均返回拒绝且不启动子进程/网络请求。

#### P0 实现记录（2026-09）

- `SimulationCampaign v1.1` 会迁移旧版计划，并以严格的结构化校验器绑定六类契约：假设、协议、输入清单、执行配置、外部运行回执与已审核模拟证据。计划阶段只持久化前四类；后两类仅定义 schema，留待 P1 的只读导入使用。
- 批准会重新生成由上游内容派生的 ID 与哈希，任何私有路径、令牌/凭据、命令模板、未绑定输入、DFT/GPU 作业预算或伪造回执都会被拒绝。
- `approve-simulation-campaign` 只写入本地的“已批准、仅计划”工件。新增 `execute-simulation-campaign` 明确返回拒绝（退出码 `3`），不会启动子进程、网络请求、AiiDA、HPC、VASP、MD 或训练任务。
- 前端投影显示 `证据 → 假设 → 协议 → 执行已阻止`、零预算、缺失字段与不能继续的理由；它只接收脱敏后的契约摘要。
- 完整验收通过：`scripts/acceptance.ps1` 的 Python 551 项和前端 307 项测试均通过，最终输出 `OK - CosMatter full local acceptance passed.`

### P1：只读结果导入与谱系审计（优先，2–4 周）

- 扩展既有外部势函数结果导入为通用 `external_run_receipt` 导入器，先支持原子能/力、结构弛豫和 MD 聚合统计三类**摘要**。
- 加入收敛/完整性检查：任务覆盖、单位、结构/输入哈希、参考方法、版本、非有限值、超预算和失败分类。
- 使模拟结果只能成为“待审核模拟证据”；报告必须同时显示适用条件、执行协议和不确定性，而非只显示数值。
- 验收：篡改任一输入/输出摘要、错配任务、缺失收敛字段或未经审核的结果均阻止进入 EvidenceCard/报告。

#### P1 实现记录（2026-09，首批）

- `import-simulation-run-receipt` 仅读取用户提供的 JSON 摘要；它严格绑定已批准计划的输入清单与协议哈希，支持能量/力、弛豫和 MD 聚合统计三类结果。
- `review-simulation-run-receipt` 需要显式的人类审核，保存为 `human_reviewed_pending_evidencecard_gate`；没有任何命令会把它自动升级为 EvidenceCard 或报告结论。
- UI 只显示结果类别、收敛状态、与假设的关系、适用边界与不确定性。运行 ID、哈希、路径、原始数值和原始工件不进入浏览器投影。

### P2：AiiDA 优先的受限执行适配器（中期，4–6 周）

- 选择 AiiDA 作为首个真正执行后端，理由是其过程谱系、检查点与调度器抽象最契合 CosMatter 的审计模型；最初只允许团队审核过的一个代码插件与一个“弛豫 → 静态性质”模板。
- 适配器只接收已批准 `InputManifest`、`ExecutionProfile` 与协议 ID；提交后仅存外部 process UUID、脱敏状态、资源摘要和哈希，不直接复制 AiiDA 数据库、远程目录或凭据。
- 队列配置使用受控的机器端 profile/别名；**校园账号用于研究者在 AiiDA/HPC 端的认证，不应写进 CosMatter `.env`、前端或 run 工件。**
- 验收：本地模拟 AiiDA 客户端覆盖批准、提交、轮询、取消、重试与断点恢复；在隔离试点中只允许一项低成本公开结构任务，且可由外部 UUID 回溯完整运行谱系。

### P3：atomate2 配方与 DP-GEN 专项循环（后期，按需）

- 用 atomate2/ASE 适配器引入可引用的材料配方，而不是在 CosMatter 内重写输入生成与 VASP 错误处理；逐步支持弹性、声子、缺陷或指定 DFT/MD 流程。
- 仅在 P1 的数据谱系与 P2 的执行预算成熟后，接入 DP-GEN/DPGEN2 风格的主动学习。每一轮必须冻结训练集、模型版本、选择阈值、候选数/失败数和预算；“模型偏差”只能触发待批准标签任务。
- 验收：主动学习循环能在合成数据上暂停、恢复、重放并解释每个被选择构型的规则；真实循环另需独立的数据许可、环境、预算和人工批准。

## 5. 技术决策与取舍

| 决策 | 建议 | 原因 |
|---|---|---|
| 首个执行后端 | AiiDA 适配器，而非自建 SSH/Slurm 提交 | 复用谱系、调度器与恢复能力，减少安全面 |
| 首个材料配方来源 | atomate2 / ASE 作为外部 recipe/calculator 生态 | 用成熟的输入与错误处理，而不是复制 VASP 专用逻辑 |
| 主动学习 | P3 后再接 DP-GEN/DPGEN2 | 主动学习会放大数据、队列和预算风险，须先有数据谱系与停机机制 |
| 存储策略 | CosMatter 存链路 ID、规范化摘要、哈希和审核状态；后端持有原始作业数据 | 与现有私有全文/路径隔离原则一致，也避免重复保存大文件 |
| 自动化等级 | `plan_only` → `approved_import` → `approved_submit` → `bounded_iteration` | 每升一级都需要新契约、测试、资源预算和负责人，授权不等于执行 |

## 6. 下一个可执行迭代

建议立即创建一个 **“Simulation Campaign v1（不执行）”** 功能分支，范围严格限定为：

1. `SimulationHypothesis`、`SimulationProtocol`、`InputManifest`、`ExecutionProfile`、`ExternalRunReceipt`、`ReviewedSimulationEvidence` 的模型与 schema；
2. 从一个已审核、合成 EvidenceCard fixture 到计划与前端投影的端到端测试；
3. 默认拒绝的 `approve-simulation-campaign` CLI，只写批准回执，不连接 AiiDA、HPC、VASP、MD 或模型训练；
4. 一个篡改/越权回归集，证明未批准 profile、私有路径、命令模板、缺失哈希、超预算和错配结果均被拒绝。

完成这一步后，团队才有足够清晰的对象边界来决定：优先投入 AiiDA + atomate2 的 DFT 试点，还是优先投入 DP-GEN 的势函数数据闭环。当前产品与研究风险判断更支持前者：先以一条小规模、可回溯的 DFT 配方打通证据到计算的链路，再扩展到高成本的主动学习。

## 7. 官方资料索引

- AiiDA： [介绍](https://aiida.readthedocs.io/projects/aiida-core/en/stable/intro/index.html)、[谱系概念](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/provenance/concepts.html)、[调度器](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/schedulers.html)
- Materials Project 生态： [atomate2](https://materialsproject.github.io/atomate2/user/index.html)、[atomate2 安装与组件](https://materialsproject.github.io/atomate2/user/install.html)、[jobflow](https://materialsproject.github.io/jobflow/)、[jobflow + FireWorks](https://materialsproject.github.io/jobflow/tutorials/8-fireworks)
- pyiron： [主页](https://pyiron.org/)、[工作流教程](https://workshop.pyiron.org/DPG-tutorial-2025/01_introduction.html)
- SimStack： [官方文档](https://simstack.readthedocs.io/en/latest/index.html)
- Mat3ra： [工作流概览](https://docs.mat3ra.com/reference/workflows/overview/)、[网页提交与跟踪](https://docs.mat3ra.com/getting-started/run-first-simulation/web-interface/)
- DeepModeling： [DP-GEN 运行流程](https://docs.deepmodeling.com/projects/dpgen/en/latest/run/overview-of-the-run-process.html)、[DPGEN2 开发者指南](https://docs.deepmodeling.com/projects/dpgen2/en/stable/developer.html)
- ASE： [官方文档](https://docs.ase-lib.org/)
