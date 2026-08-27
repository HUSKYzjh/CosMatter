export type UiLocale = "zh" | "en";
export type FleetStatus = "active" | "ready" | "waiting_approval" | "framework_only";

export interface FleetTool {
  id: string;
  zh: string;
  en: string;
  detailZh: string;
  detailEn: string;
  status: FleetStatus;
}
export interface Shuttle {
  id: string;
  zh: string;
  en: string;
  taskZh: string;
  taskEn: string;
}
export interface FleetShip {
  id: string;
  zh: string;
  en: string;
  hullZh: string;
  hullEn: string;
  count: number;
  workZh: string;
  workEn: string;
  tools: FleetTool[];
  shuttles?: Shuttle[];
}
export interface FleetRecord {
  id: string;
  zh: string;
  en: string;
  purposeZh: string;
  purposeEn: string;
  status: FleetStatus;
  flagshipId: string;
  ships: FleetShip[];
  bridgeOutputs: string[];
}

const tool = (id: string, zh: string, en: string, detailZh: string, detailEn: string, status: FleetStatus = "ready"): FleetTool => ({ id, zh, en, detailZh, detailEn, status });
const shuttle = (id: string, zh: string, en: string, taskZh: string, taskEn: string): Shuttle => ({ id, zh, en, taskZh, taskEn });
const ship = (id: string, zh: string, en: string, hullZh: string, hullEn: string, count: number, workZh: string, workEn: string, tools: FleetTool[], shuttles?: Shuttle[]): FleetShip => ({ id, zh, en, hullZh, hullEn, count, workZh, workEn, tools, shuttles });

export const FLEETS: FleetRecord[] = [
  {
    id: "pioneer", zh: "开拓舰队", en: "Pioneer Fleet", status: "active", flagshipId: "dawn",
    purposeZh: "从零建设本地文献库、数据集清单、工作目录与可复现语料冻结。",
    purposeEn: "Build the local literature library, dataset register, workspace inventory, and frozen reproducible corpus.",
    bridgeOutputs: ["corpus_manifest", "dataset_registry", "workspace_inventory"],
    ships: [
      ship("dawn", "曙光号", "Dawn", "旗舰", "Flagship", 1, "批准语料范围、分配建库任务并向舰桥提交清单。", "Approves corpus scope, assigns library work, and reports manifests to the bridge.", [tool("mission_beacon", "信标", "Mission Beacon", "维护待办、优先级和人工批准点。", "Maintains todos, priorities, and human approval gates.", "active")]),
      ship("archive", "方舟号", "Ark", "档案运输舰", "Archive carrier", 2, "登记授权本地 PDF、Zotero 条目和数据集元数据。", "Registers authorised local PDFs, Zotero entries, and dataset metadata.", [tool("dockmaster", "泊位管理员", "Dockmaster", "建立本地文献库和工作目录清单。", "Builds the local library and workspace inventory.", "active"), tool("manifest", "货舱清单仪", "Cargo Manifest", "保存哈希、访问边界和冻结版本。", "Records hashes, access boundaries, and frozen versions.")], [shuttle("intake_pod", "接驳舱", "Intake Pod", "登记一个文件或条目。", "Registers one file or entry.")]),
      ship("prospector", "矿脉号", "Prospector", "巡检护卫舰", "Prospecting escort", 1, "发现缺失元数据和新增文献线索。", "Finds missing metadata and newly available literature leads.", [tool("mining_drone", "采矿无人机", "Mining Drone", "只按批准计划周期性检查新增元数据；默认不联网执行。", "Checks new metadata only under an approved plan; never runs network work by default.")], [shuttle("duplicate_probe", "去重探针", "Duplicate Probe", "处理一个 DOI 或标题去重。", "Deduplicates one DOI or title.")]),
    ],
  },
  {
    id: "constellation", zh: "群星舰队", en: "Constellation Fleet", status: "ready", flagshipId: "weaver",
    purposeZh: "构建结构化数据库、分析脚本与受证据约束的隐藏关系候选。",
    purposeEn: "Build structured stores, analysis scripts, and evidence-bounded latent-relation candidates.",
    bridgeOutputs: ["knowledge_graph_projection", "analysis_run_record", "relation_review_queue"],
    ships: [
      ship("weaver", "织网号", "Weaver", "旗舰", "Flagship", 1, "统一模式、批准关系类型并协调数据质量。", "Owns schemas, relation types, and data-quality routing.", [tool("schema_beacon", "模式信标", "Schema Beacon", "管理字段字典、版本与兼容性。", "Manages field dictionaries, versions, and compatibility.")]),
      ship("cartographer", "星图号", "Cartographer", "图谱测绘舰", "Graph surveyor", 2, "把已审查事实和来源映射为关系工件。", "Maps reviewed facts and sources into relation artifacts.", [tool("constellation_array", "星图阵列", "Constellation Array", "构建带来源边的知识图谱投影。", "Builds knowledge-graph projections with provenance edges."), tool("relation_reconciler", "引力校准仪", "Relation Reconciler", "要求人工核对跨源标识映射。", "Requires human review of cross-source identifier mappings.")]),
      ship("analyst", "暗潮号", "Undertow", "分析巡洋舰", "Analysis cruiser", 1, "运行可复现统计、覆盖和条件差异分析。", "Runs reproducible statistics, coverage, and condition-difference analysis.", [tool("dark_matter_analyser", "暗物质分析仪", "Dark Matter Analyser", "寻找可解释的共现、缺失与分组。", "Finds explainable co-occurrence, missingness, and groups."), tool("script_foundry", "脚本铸造厂", "Script Foundry", "锁定分析脚本和配置。", "Freezes analysis scripts and configuration.")], [shuttle("field_probe", "字段探针", "Field Probe", "检查一个字段的空值、单位或分布。", "Inspects one field for nulls, units, or distribution.")]),
    ],
  },
  {
    id: "observatory", zh: "天体观测舰队", en: "Observatory Fleet", status: "active", flagshipId: "aperture",
    purposeZh: "执行受控文献检索、筛选、解析任务创建和材料事实草案。",
    purposeEn: "Run controlled retrieval, screening, parse-task creation, and material-fact drafts.",
    bridgeOutputs: ["candidate_screening", "parse_receipts", "source_maps", "material_fact_drafts"],
    ships: [
      ship("aperture", "光阑号", "Aperture", "旗舰", "Flagship", 1, "将批准计划拆成检索、筛选和阅读任务。", "Breaks an approved plan into retrieval, screening, and reading tasks.", [tool("survey_scheduler", "巡天调度仪", "Survey Scheduler", "生成有上限的检索批次。", "Creates bounded retrieval batches.", "active")]),
      ship("spectrometer", "光谱号", "Spectrometer", "文献勘测舰", "Literature surveyor", 3, "收集候选条目并维持筛选理由。", "Collects candidate records and preserves screening reasons.", [tool("celestial_observatory", "天体观察仪", "Celestial Observatory", "分析候选文献元数据、主题与可比范围。", "Analyses candidate metadata, topics, and comparable scope.", "active"), tool("citation_array", "引文阵列", "Citation Array", "执行 DOI 去重和受限引文扩展。", "Performs DOI deduplication and bounded citation expansion.")]),
      ship("librarian", "书页号", "Leaf", "解析支援舰", "Parsing support", 2, "创建授权 MinerU 解析任务与来源映射草案。", "Creates authorised MinerU parse tasks and source-map drafts.", [tool("source_locator", "来源定位器", "Source Locator", "把人工复核短片段锚定到页面、段落或表格。", "Anchors human-reviewed short excerpts to pages, paragraphs, or tables."), tool("mineru_gate", "解析闸门", "MinerU Gate", "记录解析权限、回执和失败，不保存无边界全文。", "Records permission, receipts, and failures without retaining unbounded full text.")], [shuttle("locator_shuttle", "定位穿梭机", "Locator Shuttle", "核对一个引用位置。", "Checks one evidence location.")]),
    ],
  },
  {
    id: "sentinel", zh: "证据哨戒舰队", en: "Evidence Sentinel Fleet", status: "active", flagshipId: "vigil",
    purposeZh: "核验来源、单位、条件、反例边界和发布前证据覆盖。",
    purposeEn: "Verify provenance, units, conditions, counter-evidence boundaries, and pre-release coverage.",
    bridgeOutputs: ["accepted_evidence_cards", "normalization_records", "counterevidence_records", "audit_summary"],
    ships: [
      ship("vigil", "警戒号", "Vigil", "旗舰", "Flagship", 1, "控制证据释放门禁，拒绝无定位结论。", "Controls evidence release gates and rejects claims without locators.", [tool("release_beacon", "放行信标", "Release Beacon", "跟踪 EvidenceCard 审查状态。", "Tracks EvidenceCard review state.", "active")]),
      ship("calibrator", "标尺号", "Calibrator", "校准护卫舰", "Calibration escort", 2, "对齐单位、条件与测试协议。", "Aligns units, conditions, and measurement protocols.", [tool("condition_differential", "条件差分仪", "Condition Differential", "识别不可直接比较的样品和测量条件。", "Identifies samples and measurements that are not directly comparable.", "active"), tool("unit_normalizer", "单位归一器", "Unit Normalizer", "记录显式换算和原始数值。", "Records explicit conversions and original values.")]),
      ship("counter", "反证号", "Counterpoint", "反例巡逻舰", "Counter-evidence patrol", 1, "执行批准的反例检索并保存边界。", "Executes approved counter-evidence searches and preserves their boundary.", [tool("counterevidence_detector", "反证探测器", "Counterevidence Detector", "记录反例检索的查询与结果范围。", "Records queries and result scope for counter-evidence retrieval.", "active")], [shuttle("citation_probe", "引用探针", "Citation Probe", "复查一条证据的来源映射。", "Rechecks one evidence provenance link.")]),
    ],
  },
  {
    id: "diagnostics", zh: "航路诊断舰队", en: "Route Diagnostics Fleet", status: "active", flagshipId: "compass",
    purposeZh: "解释跨文献冲突、条件分歧、信息缺失和需返回的检索路线。",
    purposeEn: "Explain cross-paper conflicts, condition divergence, missing information, and return retrieval routes.",
    bridgeOutputs: ["conflict_matrix", "missingness_register", "approved_return_plan"],
    ships: [
      ship("compass", "罗盘号", "Compass", "旗舰", "Flagship", 1, "组织冲突调查，向舰桥提交需要补检的路线。", "Organises conflict inquiries and submits validated return routes.", [tool("return_vector", "返航矢量仪", "Return Vector", "把未解决问题转成受控回退任务。", "Turns unresolved questions into controlled return tasks.", "active")]),
      ship("differential", "分歧号", "Differential", "条件诊断舰", "Condition diagnostic", 2, "寻找造成不同结论的显式变量。", "Finds explicit variables that drive divergent conclusions.", [tool("conflict_matrix", "冲突矩阵", "Conflict Matrix", "将结论与条件字段并排比较。", "Compares conclusions beside their condition fields.", "active"), tool("blind_spot_scan", "盲区扫描仪", "Blind-spot Scanner", "标记未报告变量和覆盖空洞。", "Marks unreported variables and coverage gaps.")]),
      ship("relay", "回声号", "Echo", "联络护卫舰", "Relay escort", 1, "把核验后的补检需求交给观测舰队。", "Hands verified retrieval needs to the observatory.", [tool("handoff_codec", "交接编码器", "Handoff Codec", "验证跨舰队工件清单。", "Validates cross-fleet artifact manifests.")]),
    ],
  },
  {
    id: "horizon", zh: "地平线探索舰队", en: "Horizon Exploration Fleet", status: "ready", flagshipId: "farpoint",
    purposeZh: "从已核验冲突与缺失生成可证伪的 Research Gap 和验证路线。",
    purposeEn: "Turn verified conflicts and gaps into falsifiable Research Gap candidates and validation routes.",
    bridgeOutputs: ["gap_candidates", "validation_routes", "human_review_queue"],
    ships: [
      ship("farpoint", "远点号", "Farpoint", "旗舰", "Flagship", 1, "确保 Gap 只从批准证据、缺失和反例边界提出。", "Ensures gaps arise only from approved evidence, missingness, and counter-evidence bounds.", [tool("hypothesis_triage", "假设分诊器", "Hypothesis Triage", "区分事实、推论和待验证假设。", "Separates fact, inference, and testable hypothesis.")]),
      ship("scanner", "地平线号", "Horizon", "远距扫描舰", "Far-range scanner", 2, "组合变量、识别覆盖缺口和验证机会。", "Combines variables to identify coverage gaps and validation opportunities.", [tool("variable_combination_scan", "变量组合扫描仪", "Variable Combination Scanner", "检查变量组合是否真正缺失。", "Checks whether a variable combination is truly missing."), tool("novelty_boundary", "新颖性边界仪", "Novelty Boundary", "记录反例检索覆盖，不声称绝对新颖。", "Records counter-search coverage without claiming absolute novelty.")]),
      ship("trial", "证伪号", "Falsifier", "任务设计舰", "Validation designer", 1, "把候选转为实验或计算验证设计。", "Turns candidates into experimental or computational validation designs.", [tool("falsification_monitor", "证伪监视器", "Falsification Monitor", "给出支持或推翻假设的判据。", "Defines criteria that support or falsify a hypothesis.")], [shuttle("gap_probe", "缺口探针", "Gap Probe", "核对一条 Gap 的证据完整性。", "Checks evidence completeness for one gap.")]),
    ],
  },
  {
    id: "synthesis", zh: "合成路线舰队", en: "Synthesis Mission Fleet", status: "ready", flagshipId: "foundry",
    purposeZh: "为文献驱动的候选设计实验验证任务；只输出计划，不自动执行实验。",
    purposeEn: "Design experimental validation missions from evidence-bounded candidates; plan only, never autonomously execute experiments.",
    bridgeOutputs: ["experiment_mission_plan", "measurement_schema", "approval_requirements"],
    ships: [
      ship("foundry", "铸炉号", "Foundry", "旗舰", "Flagship", 1, "批准实验范围、资源约束与安全审查。", "Approves experiment scope, resources, and safety review.", [tool("experiment_beacon", "实验信标", "Experiment Beacon", "登记实验依赖和人工批准。", "Registers experimental dependencies and human approvals.")]),
      ship("protocol", "谱系号", "Protocol", "工艺设计舰", "Protocol designer", 2, "形成可审查的制备、表征和对照方案。", "Forms reviewable synthesis, characterisation, and control plans.", [tool("experiment_mission_design", "实验任务设计器", "Experiment Mission Designer", "将 Gap 转为不执行的实验方案。", "Turns a gap into a non-executing experimental plan."), tool("safety_gate", "安全闸门", "Safety Gate", "提示需由实验室确认的风险和权限。", "Flags risks and permissions for laboratory confirmation.")]),
      ship("metrology", "量测号", "Metrology", "表征支援舰", "Metrology support", 1, "规划验证指标和数据记录格式。", "Plans validation metrics and data-recording formats.", [tool("measurement_schema", "量测模式仪", "Measurement Schema", "定义测量字段、单位和质量控制。", "Defines measurement fields, units, and quality controls.")]),
    ],
  },
  {
    id: "dft", zh: "量子远征舰队", en: "Quantum Expedition Fleet", status: "framework_only", flagshipId: "orbital",
    purposeZh: "DFT 计算的未来框架：任务设计、输入清单、资源与结果审计；尚未接入计算引擎。",
    purposeEn: "Future DFT framework: mission design, input manifests, resource gates, and results audit; no execution engine is connected.",
    bridgeOutputs: ["dft_mission_plan", "dft_input_manifest", "calculation_receipt"],
    ships: [
      ship("orbital", "轨道号", "Orbital", "旗舰", "Flagship", 1, "协调 DFT 任务卡和人工资源批准。", "Coordinates DFT task cards and human resource approval.", [tool("dft_beacon", "量子信标", "DFT Beacon", "维护 DFT 任务依赖与停止条件。", "Maintains DFT task dependencies and stop conditions.", "framework_only")]),
      ship("basis", "基组号", "Basis", "输入准备舰", "Input preparation", 2, "准备结构、赝势、参数和收敛测试契约。", "Prepares contracts for structures, pseudopotentials, parameters, and convergence tests.", [tool("input_foundry", "输入铸造厂", "Input Foundry", "生成待确认输入模板，不提交作业。", "Generates reviewable input templates without submitting jobs.", "framework_only"), tool("convergence_scope", "收敛观测仪", "Convergence Scope", "定义收敛记录字段。", "Defines convergence-record fields.", "framework_only")]),
      ship("auditor", "本征号", "Eigen", "结果审计舰", "Results auditor", 1, "规划能量、力和结构结果的可追溯审计。", "Plans provenance audit for energy, force, and structure results.", [tool("calculation_receipt", "计算回执器", "Calculation Receipt", "未来记录输入哈希、作业版本和输出摘要。", "Will record input hashes, job versions, and output summaries.", "framework_only")]),
    ],
  },
  {
    id: "potential", zh: "势场训练舰队", en: "Potential Training Fleet", status: "framework_only", flagshipId: "kepler",
    purposeZh: "DP 势函数训练的未来框架：数据策展、训练计划、验证协议和模型谱系；尚未启动训练。",
    purposeEn: "Future DP-potential framework: data curation, training plans, validation protocol, and model lineage; no training has started.",
    bridgeOutputs: ["potential_dataset_manifest", "training_plan", "model_lineage_record"],
    ships: [
      ship("kepler", "开普勒号", "Kepler", "旗舰", "Flagship", 1, "管理 DP 数据、训练与验证的审计门禁。", "Manages audit gates for DP data, training, and validation.", [tool("potential_beacon", "势场信标", "Potential Beacon", "维护数据版本、训练阶段和人工批准。", "Maintains data versions, training phases, and approvals.", "framework_only")]),
      ship("curator", "晶格号", "Lattice", "数据策展舰", "Data curator", 2, "定义构型、能量、力、应力与覆盖范围契约。", "Defines contracts for structures, energy, forces, stresses, and coverage.", [tool("dataset_curator", "构型策展器", "Dataset Curator", "建立训练/验证/测试划分记录。", "Builds train/validation/test split records.", "framework_only"), tool("coverage_radar", "覆盖雷达", "Coverage Radar", "标记相、温压、缺陷与应变覆盖。", "Marks phase, temperature-pressure, defect, and strain coverage.", "framework_only")]),
      ship("trainer", "势垒号", "Barrier", "训练巡洋舰", "Training cruiser", 1, "规划 DP 训练、验证和不确定性触发。", "Plans DP training, validation, and uncertainty triggers.", [tool("training_foundry", "训练铸造厂", "Training Foundry", "生成不执行的训练配置模板。", "Generates non-executing training configuration templates.", "framework_only"), tool("model_lineage", "模型谱系仪", "Model Lineage", "未来记录模型、超参数与评测关系。", "Will record model, hyperparameter, and evaluation lineage.", "framework_only")], [shuttle("structure_probe", "构型探针", "Structure Probe", "检查一个构型条目完整性。", "Checks completeness of one structure record.")]),
    ],
  },
  {
    id: "dynamics", zh: "动力学巡航舰队", en: "Dynamics Cruise Fleet", status: "framework_only", flagshipId: "voyager",
    purposeZh: "MD 计算的未来框架：体系构建、积分协议、采样分析和轨迹审计；尚未接入 MD 引擎。",
    purposeEn: "Future MD framework: system building, integration protocol, sampling analysis, and trajectory audit; no MD engine is connected.",
    bridgeOutputs: ["md_system_manifest", "md_protocol", "trajectory_analysis_plan"],
    ships: [
      ship("voyager", "旅行者号", "Voyager", "旗舰", "Flagship", 1, "协调 MD 任务、资源门禁和可复跑协议。", "Coordinates MD tasks, resource gates, and reproducible protocols.", [tool("md_beacon", "动力学信标", "MD Beacon", "登记体系、阶段和停止条件。", "Registers systems, phases, and stop conditions.", "framework_only")]),
      ship("cell", "晶胞号", "Cell", "体系构建舰", "System builder", 2, "准备结构、力场、边界和初始条件契约。", "Prepares contracts for structures, force fields, boundaries, and initial conditions.", [tool("system_builder", "体系构建器", "System Builder", "生成待确认的体系构建清单。", "Generates a reviewable system-build manifest.", "framework_only"), tool("protocol_console", "积分协议台", "Protocol Console", "记录系综、时间步、温压控制和采样频率。", "Records ensemble, timestep, controls, and sampling frequency.", "framework_only")]),
      ship("wake", "尾迹号", "Wake", "轨迹分析舰", "Trajectory analysis", 1, "定义轨迹分析和不确定性报告的未来接口。", "Defines future interfaces for trajectory analysis and uncertainty reports.", [tool("trajectory_observatory", "轨迹观测台", "Trajectory Observatory", "规划 RDF、扩散、极化等分析字段。", "Plans fields for RDF, diffusion, polarisation, and related analysis.", "framework_only"), tool("stability_watch", "稳定性监视器", "Stability Watch", "未来标记漂移、未平衡和异常采样。", "Will flag drift, non-equilibration, and anomalous sampling.", "framework_only")]),
    ],
  },
];

export const label = (item: { zh: string; en: string }, locale: UiLocale) => locale === "zh" ? item.zh : item.en;
export const statusLabel = (status: FleetStatus, locale: UiLocale) => {
  const labels: Record<FleetStatus, [string, string]> = {
    active: ["运行中", "Active"], ready: ["就绪", "Ready"], waiting_approval: ["等待批准", "Awaiting approval"], framework_only: ["仅框架", "Framework only"],
  };
  return labels[status][locale === "zh" ? 0 : 1];
};
export const fleetChannels = (fleet: FleetRecord) => fleet.ships.filter((ship) => ship.id !== fleet.flagshipId).flatMap((ship) => [
  { from: ship.id, to: fleet.flagshipId, direction: "in" as const },
  { from: fleet.flagshipId, to: ship.id, direction: "out" as const },
]);
