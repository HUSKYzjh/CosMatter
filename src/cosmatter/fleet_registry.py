"""Fleet-scale operating model for CosMatter.

This registry describes the *organisation* of specialised fleets. It is kept
separate from the evidence-workflow FleetType enum: a mission may activate more
than one division, but scientific claims still flow through evidence gates.
DFT, DP-potential and MD divisions are framework-only until an approved adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class FleetReadiness(str, Enum):
    ACTIVE = "active"
    READY = "ready"
    WAITING_APPROVAL = "waiting_approval"
    FRAMEWORK_ONLY = "framework_only"


@dataclass(frozen=True)
class ToolAgentSpec:
    tool_id: str
    name_zh: str
    name_en: str
    purpose_zh: str
    input_contract: str
    output_contract: str
    readiness: FleetReadiness


@dataclass(frozen=True)
class ShuttleSpec:
    shuttle_id: str
    name_zh: str
    name_en: str
    micro_task_zh: str
    return_to_flagship: bool = True


@dataclass(frozen=True)
class ShipSpec:
    ship_id: str
    name_zh: str
    name_en: str
    hull: str
    count: int
    function_zh: str
    tools: tuple[ToolAgentSpec, ...]
    shuttles: tuple[ShuttleSpec, ...] = ()


@dataclass(frozen=True)
class FleetChannel:
    sender_ship_id: str
    recipient_ship_id: str
    payload_contract: str
    gate_zh: str


@dataclass(frozen=True)
class FleetDivisionSpec:
    fleet_id: str
    name_zh: str
    name_en: str
    purpose_zh: str
    readiness: FleetReadiness
    flagship_id: str
    ships: tuple[ShipSpec, ...]
    channels: tuple[FleetChannel, ...]
    bridge_outputs: tuple[str, ...]

    def __post_init__(self) -> None:
        ids = {ship.ship_id for ship in self.ships}
        if self.flagship_id not in ids:
            raise ValueError(f"{self.fleet_id}: flagship must be a registered ship")
        if len(ids) != len(self.ships):
            raise ValueError(f"{self.fleet_id}: duplicate ship id")
        if any(ship.count < 1 for ship in self.ships):
            raise ValueError(f"{self.fleet_id}: ship count must be positive")
        if any(
            channel.sender_ship_id not in ids or channel.recipient_ship_id not in ids
            for channel in self.channels
        ):
            raise ValueError(f"{self.fleet_id}: channel references an unknown ship")
        if any(
            self.flagship_id not in (channel.sender_ship_id, channel.recipient_ship_id)
            for channel in self.channels
        ):
            raise ValueError(f"{self.fleet_id}: every internal channel must involve flagship")


def _tool(tool_id: str, zh: str, en: str, purpose: str, inputs: str, outputs: str,
          readiness: FleetReadiness = FleetReadiness.READY) -> ToolAgentSpec:
    return ToolAgentSpec(tool_id, zh, en, purpose, inputs, outputs, readiness)


def _shuttle(shuttle_id: str, zh: str, en: str, task: str) -> ShuttleSpec:
    return ShuttleSpec(shuttle_id, zh, en, task)


def _ship(ship_id: str, zh: str, en: str, hull: str, count: int, function: str,
          *tools: ToolAgentSpec, shuttles: tuple[ShuttleSpec, ...] = ()) -> ShipSpec:
    return ShipSpec(ship_id, zh, en, hull, count, function, tuple(tools), shuttles)


def _channels(flagship_id: str, *ship_ids: str) -> tuple[FleetChannel, ...]:
    result: list[FleetChannel] = []
    for ship_id in ship_ids:
        result.extend((
            FleetChannel(ship_id, flagship_id, "typed status + artifact references", "旗舰校验输入与权限"),
            FleetChannel(flagship_id, ship_id, "approved task packet", "仅派发已批准子任务"),
        ))
    return tuple(result)


def fleet_registry() -> tuple[FleetDivisionSpec, ...]:
    """Return the canonical, human-readable fleet catalogue (ten divisions)."""
    return (
        FleetDivisionSpec(
            "pioneer", "开拓舰队", "Pioneer Fleet", "从零建设本地文献库、数据集清单、工作目录与可复现语料冻结。",
            FleetReadiness.ACTIVE, "dawn",
            (
                _ship("dawn", "曙光号", "Dawn", "旗舰 / command carrier", 1, "批准语料范围、分配建库任务并向舰桥提交清单。",
                      _tool("mission_beacon", "信标", "Mission Beacon", "维护当前待办、任务优先级和人工批准点。", "任务简报", "待办与批准状态", FleetReadiness.ACTIVE)),
                _ship("archive", "方舟号", "Ark", "档案运输舰", 2, "导入授权本地 PDF、Zotero 条目和数据集元数据。",
                      _tool("dockmaster", "泊位管理员", "Dockmaster", "建立本地文献库、数据集与工作目录清单。", "授权来源清单", "语料登记与校验清单", FleetReadiness.ACTIVE),
                      _tool("manifest", "货舱清单仪", "Cargo Manifest", "计算文件哈希、访问边界和冻结版本。", "本地文件元数据", "不含全文的清单"),
                      shuttles=(_shuttle("intake_pod", "接驳舱", "Intake Pod", "登记单个文件或条目。"),)),
                _ship("prospector", "矿脉号", "Prospector", "巡检护卫舰", 1, "发现缺失元数据和新增文献线索。",
                      _tool("mining_drone", "采矿无人机", "Mining Drone", "按已批准计划定期检查新增元数据；默认不联网执行。", "批准检索计划", "候选更新回执"),
                      shuttles=(_shuttle("duplicate_probe", "去重探针", "Duplicate Probe", "处理单个 DOI 或标题去重。"),)),
            ),
            _channels("dawn", "archive", "prospector"),
            ("corpus_manifest", "dataset_registry", "workspace_inventory"),
        ),
        FleetDivisionSpec(
            "constellation", "群星舰队", "Constellation Fleet", "构建结构化数据库、分析脚本与受证据约束的隐藏关系候选。",
            FleetReadiness.READY, "weaver",
            (
                _ship("weaver", "织网号", "Weaver", "旗舰 / data command", 1, "统一模式、批准关系类型并协调数据质量。",
                      _tool("schema_beacon", "模式信标", "Schema Beacon", "管理字段字典、版本与兼容性。", "结构化工件", "模式变更记录")),
                _ship("cartographer", "星图号", "Cartographer", "图谱测绘舰", 2, "把已审查事实和来源映射为关系工件。",
                      _tool("constellation_array", "星图阵列", "Constellation Array", "构建关系数据库/知识图谱投影。", "已接受 EvidenceCard", "带来源边的关系图"),
                      _tool("relation_reconciler", "引力校准仪", "Relation Reconciler", "要求人工核对跨源标识映射。", "关系候选", "审核后映射")),
                _ship("analyst", "暗潮号", "Undertow", "分析巡洋舰", 1, "运行可复现统计、覆盖和条件差异分析。",
                      _tool("dark_matter_analyser", "暗物质分析仪", "Dark Matter Analyser", "从明确字段寻找可解释的共现、缺失与分组。", "规范化事实", "分析脚本输出"),
                      _tool("script_foundry", "脚本铸造厂", "Script Foundry", "生成并锁定数据分析脚本配置。", "分析任务", "可复跑脚本清单"),
                      shuttles=(_shuttle("field_probe", "字段探针", "Field Probe", "检查一个字段的空值、单位或分布。"),)),
            ),
            _channels("weaver", "cartographer", "analyst"),
            ("knowledge_graph_projection", "analysis_run_record", "relation_review_queue"),
        ),
        FleetDivisionSpec(
            "observatory", "天体观测舰队", "Observatory Fleet", "执行受控文献检索、筛选、解析任务创建和材料事实草案。",
            FleetReadiness.ACTIVE, "aperture",
            (
                _ship("aperture", "光阑号", "Aperture", "旗舰 / survey command", 1, "把批准计划拆成检索、筛选和读取任务。",
                      _tool("survey_scheduler", "巡天调度仪", "Survey Scheduler", "生成有上限的检索批次。", "批准 FlightPlan", "检索任务包", FleetReadiness.ACTIVE)),
                _ship("spectrometer", "光谱号", "Spectrometer", "文献勘测舰", 3, "收集候选条目并维持筛选理由。",
                      _tool("celestial_observatory", "天体观察仪", "Celestial Observatory", "分析候选文献的元数据、主题和可比范围。", "候选记录", "筛选草案", FleetReadiness.ACTIVE),
                      _tool("citation_array", "引文阵列", "Citation Array", "开展 DOI 去重和受限引文扩展。", "候选 DOI", "去重候选与回执")),
                _ship("librarian", "书页号", "Leaf", "解析支援舰", 2, "创建授权 MinerU 解析任务与来源映射草案。",
                      _tool("source_locator", "来源定位器", "Source Locator", "把人工复核短片段锚定到页面、段落或表格。", "解析回执", "source-map"),
                      _tool("mineru_gate", "解析闸门", "MinerU Gate", "记录解析权限、回执与失败，不保存无边界全文。", "授权文件任务", "parse receipt"),
                      shuttles=(_shuttle("locator_shuttle", "定位穿梭机", "Locator Shuttle", "核对单个引用位置。"),)),
            ),
            _channels("aperture", "spectrometer", "librarian"),
            ("candidate_screening", "parse_receipts", "source_maps", "material_fact_drafts"),
        ),
        FleetDivisionSpec(
            "sentinel", "证据哨戒舰队", "Evidence Sentinel Fleet", "核验来源、单位、条件、反例边界和发布前证据覆盖。",
            FleetReadiness.ACTIVE, "vigil",
            (
                _ship("vigil", "警戒号", "Vigil", "旗舰 / verification command", 1, "控制证据释放门禁，拒绝无定位结论。",
                      _tool("release_beacon", "放行信标", "Release Beacon", "跟踪 EvidenceCard 审查状态。", "证据草案", "接受/退回决定", FleetReadiness.ACTIVE)),
                _ship("calibrator", "标尺号", "Calibrator", "校准护卫舰", 2, "对齐单位、条件与测试协议。",
                      _tool("condition_differential", "条件差分仪", "Condition Differential", "识别不可直接比较的样品与测量条件。", "材料事实", "条件矩阵", FleetReadiness.ACTIVE),
                      _tool("unit_normalizer", "单位归一器", "Unit Normalizer", "记录显式换算规则和原始数值。", "原始量纲", "规范化记录")),
                _ship("counter", "反证号", "Counterpoint", "反例巡逻舰", 1, "执行批准的反例检索并保存边界。",
                      _tool("counterevidence_detector", "反证探测器", "Counterevidence Detector", "记录已执行反例检索的查询与结果范围。", "反例任务", "counterevidence record", FleetReadiness.ACTIVE),
                      shuttles=(_shuttle("citation_probe", "引用探针", "Citation Probe", "复查单条证据的来源映射。"),)),
            ),
            _channels("vigil", "calibrator", "counter"),
            ("accepted_evidence_cards", "normalization_records", "counterevidence_records", "audit_summary"),
        ),
        FleetDivisionSpec(
            "diagnostics", "航路诊断舰队", "Route Diagnostics Fleet", "解释跨文献冲突、条件分歧、信息缺失和需返回的检索路线。",
            FleetReadiness.ACTIVE, "compass",
            (
                _ship("compass", "罗盘号", "Compass", "旗舰 / diagnostics command", 1, "组织冲突调查，向舰桥提交需要补检的路线。",
                      _tool("return_vector", "返航矢量仪", "Return Vector", "把未解决问题转成受控回退任务。", "冲突候选", "返航计划", FleetReadiness.ACTIVE)),
                _ship("differential", "分歧号", "Differential", "条件诊断舰", 2, "寻找造成不同结论的显式变量。",
                      _tool("conflict_matrix", "冲突矩阵", "Conflict Matrix", "将结论与条件字段并排比较。", "EvidenceCard", "冲突解释候选", FleetReadiness.ACTIVE),
                      _tool("blind_spot_scan", "盲区扫描仪", "Blind-spot Scanner", "标注未报告变量和覆盖空洞。", "结构化字段", "缺失记录")),
                _ship("relay", "回声号", "Echo", "联络护卫舰", 1, "把经过核验的补检需求交给观测舰队。",
                      _tool("handoff_codec", "交接编码器", "Handoff Codec", "验证跨舰队工件清单。", "接受工件 ID", "交接包")),
            ),
            _channels("compass", "differential", "relay"),
            ("conflict_matrix", "missingness_register", "approved_return_plan"),
        ),
        FleetDivisionSpec(
            "horizon", "地平线探索舰队", "Horizon Exploration Fleet", "从已核验冲突与缺失生成可证伪的 Research Gap 和验证路线。",
            FleetReadiness.READY, "farpoint",
            (
                _ship("farpoint", "远点号", "Farpoint", "旗舰 / gap command", 1, "确保 Gap 仅从已批准证据、缺失和反例边界提出。",
                      _tool("hypothesis_triage", "假设分诊器", "Hypothesis Triage", "区分事实、推论和待验证假设。", "核验工件", "Gap 审查队列")),
                _ship("scanner", "地平线号", "Horizon", "远距扫描舰", 2, "组合变量、识别覆盖缺口与验证机会。",
                      _tool("variable_combination_scan", "变量组合扫描仪", "Variable Combination Scanner", "检查变量组合是否真正缺失。", "条件矩阵", "缺失组合"),
                      _tool("novelty_boundary", "新颖性边界仪", "Novelty Boundary", "记录反例检索覆盖，不声称绝对新颖。", "反例回执", "新颖性边界")),
                _ship("trial", "证伪号", "Falsifier", "任务设计舰", 1, "把候选转化为可执行的实验或计算验证设计。",
                      _tool("falsification_monitor", "证伪监视器", "Falsification Monitor", "给出支持/推翻假设的判据。", "Gap 候选", "验证判据"),
                      shuttles=(_shuttle("gap_probe", "缺口探针", "Gap Probe", "核对单条 Gap 的证据完整性。"),)),
            ),
            _channels("farpoint", "scanner", "trial"),
            ("gap_candidates", "validation_routes", "human_review_queue"),
        ),
        FleetDivisionSpec(
            "synthesis", "合成路线舰队", "Synthesis Mission Fleet", "为文献驱动的候选设计实验验证任务；只输出计划，不自动执行实验。",
            FleetReadiness.READY, "foundry",
            (
                _ship("foundry", "铸炉号", "Foundry", "旗舰 / experiment command", 1, "批准实验范围、资源约束与安全审查。",
                      _tool("experiment_beacon", "实验信标", "Experiment Beacon", "登记实验任务、依赖和人工批准。", "验证建议", "实验任务卡")),
                _ship("protocol", "谱系号", "Protocol", "工艺设计舰", 2, "形成可审查的制备、表征和对照方案。",
                      _tool("experiment_mission_design", "实验任务设计器", "Experiment Mission Designer", "将 Gap 转为可执行但未运行的实验方案。", "Gap 候选", "实验计划"),
                      _tool("safety_gate", "安全闸门", "Safety Gate", "提示需由实验室人员确认的风险与权限。", "实验计划", "审核待办")),
                _ship("metrology", "量测号", "Metrology", "表征支援舰", 1, "规划验证指标和数据记录格式。",
                      _tool("measurement_schema", "量测模式仪", "Measurement Schema", "定义测量字段、单位和质量控制。", "实验计划", "数据记录模板")),
            ),
            _channels("foundry", "protocol", "metrology"),
            ("experiment_mission_plan", "measurement_schema", "approval_requirements"),
        ),
        FleetDivisionSpec(
            "dft", "量子远征舰队", "Quantum Expedition Fleet", "DFT 计算的未来框架：任务设计、输入清单、资源与结果审计；未接入计算引擎。",
            FleetReadiness.FRAMEWORK_ONLY, "orbital",
            (
                _ship("orbital", "轨道号", "Orbital", "旗舰 / DFT command", 1, "协调 DFT 任务卡和人工资源批准。",
                      _tool("dft_beacon", "量子信标", "DFT Beacon", "维护 DFT 任务依赖与停止条件。", "计算任务卡", "执行前清单", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("basis", "基组号", "Basis", "输入准备舰", 2, "准备结构、赝势、参数和收敛测试的工件契约。",
                      _tool("input_foundry", "输入铸造厂", "Input Foundry", "生成待人工确认的输入模板，不提交作业。", "结构与参数", "输入清单", FleetReadiness.FRAMEWORK_ONLY),
                      _tool("convergence_scope", "收敛观测仪", "Convergence Scope", "定义 k 点、截断能和阈值的记录字段。", "DFT 计划", "收敛协议", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("auditor", "本征号", "Eigen", "结果审计舰", 1, "规划能量、力和结构结果的可追溯审计。",
                      _tool("calculation_receipt", "计算回执器", "Calculation Receipt", "未来记录作业版本、输入哈希和输出摘要。", "作业回执", "审计记录", FleetReadiness.FRAMEWORK_ONLY)),
            ),
            _channels("orbital", "basis", "auditor"),
            ("dft_mission_plan", "dft_input_manifest", "calculation_receipt"),
        ),
        FleetDivisionSpec(
            "potential", "势场训练舰队", "Potential Training Fleet", "DP 势函数训练的未来框架：数据策展、训练计划、验证协议和模型谱系；未启动训练。",
            FleetReadiness.FRAMEWORK_ONLY, "kepler",
            (
                _ship("kepler", "开普勒号", "Kepler", "旗舰 / potential command", 1, "管理 DP 数据、训练与验证的审计门禁。",
                      _tool("potential_beacon", "势场信标", "Potential Beacon", "维护数据版本、训练阶段和人工批准。", "训练简报", "训练计划", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("curator", "晶格号", "Lattice", "数据策展舰", 2, "定义构型、能量、力、应力与覆盖范围的契约。",
                      _tool("dataset_curator", "构型策展器", "Dataset Curator", "建立训练/验证/测试划分记录。", "计算数据清单", "数据谱系", FleetReadiness.FRAMEWORK_ONLY),
                      _tool("coverage_radar", "覆盖雷达", "Coverage Radar", "标注相、温压、缺陷和应变覆盖。", "数据谱系", "覆盖报告", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("trainer", "势垒号", "Barrier", "训练巡洋舰", 1, "规划 DP 训练、验证和不确定性触发。",
                      _tool("training_foundry", "训练铸造厂", "Training Foundry", "生成不执行的训练配置模板。", "已批准数据版本", "训练配置", FleetReadiness.FRAMEWORK_ONLY),
                      _tool("model_lineage", "模型谱系仪", "Model Lineage", "未来记录模型、超参数与评测关系。", "训练回执", "模型谱系", FleetReadiness.FRAMEWORK_ONLY),
                      shuttles=(_shuttle("structure_probe", "构型探针", "Structure Probe", "检查一个构型条目的完整性。"),)),
            ),
            _channels("kepler", "curator", "trainer"),
            ("potential_dataset_manifest", "training_plan", "model_lineage_record"),
        ),
        FleetDivisionSpec(
            "dynamics", "动力学巡航舰队", "Dynamics Cruise Fleet", "MD 计算的未来框架：体系构建、积分协议、采样分析和轨迹审计；未接入 MD 引擎。",
            FleetReadiness.FRAMEWORK_ONLY, "voyager",
            (
                _ship("voyager", "旅行者号", "Voyager", "旗舰 / MD command", 1, "协调 MD 任务、资源门禁和可复跑协议。",
                      _tool("md_beacon", "动力学信标", "MD Beacon", "登记体系、阶段与停止条件。", "MD 任务卡", "运行前清单", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("cell", "晶胞号", "Cell", "体系构建舰", 2, "准备结构、力场、边界和初始条件契约。",
                      _tool("system_builder", "体系构建器", "System Builder", "生成待确认的体系构建清单。", "结构与参数", "体系清单", FleetReadiness.FRAMEWORK_ONLY),
                      _tool("protocol_console", "积分协议台", "Protocol Console", "记录系综、时间步、温压控制与采样频率。", "MD 计划", "协议记录", FleetReadiness.FRAMEWORK_ONLY)),
                _ship("wake", "尾迹号", "Wake", "轨迹分析舰", 1, "定义轨迹分析和不确定性报告的未来接口。",
                      _tool("trajectory_observatory", "轨迹观测台", "Trajectory Observatory", "规划 RDF、扩散、极化等分析字段。", "轨迹摘要", "分析清单", FleetReadiness.FRAMEWORK_ONLY),
                      _tool("stability_watch", "稳定性监视器", "Stability Watch", "未来标记漂移、未平衡与异常采样。", "运行回执", "稳定性报告", FleetReadiness.FRAMEWORK_ONLY)),
            ),
            _channels("voyager", "cell", "wake"),
            ("md_system_manifest", "md_protocol", "trajectory_analysis_plan"),
        ),
    )


def fleet_by_id(fleet_id: str) -> FleetDivisionSpec:
    for fleet in fleet_registry():
        if fleet.fleet_id == fleet_id:
            return fleet
    raise KeyError(f"unknown fleet {fleet_id!r}")


def museum_catalog() -> dict[str, tuple[object, ...]]:
    fleets = fleet_registry()
    ships = tuple(ship for fleet in fleets for ship in fleet.ships)
    tools = tuple(tool for ship in ships for tool in ship.tools)
    shuttles = tuple(shuttle for ship in ships for shuttle in ship.shuttles)
    return {"fleets": fleets, "ships": ships, "tools": tools, "shuttles": shuttles}


def bridge_allowed_outputs(fleet_id: str) -> tuple[str, ...]:
    return fleet_by_id(fleet_id).bridge_outputs


def all_channels_are_flagship_mediated(fleets: Iterable[FleetDivisionSpec] | None = None) -> bool:
    return all(
        fleet.flagship_id in (channel.sender_ship_id, channel.recipient_ship_id)
        for fleet in (fleet_registry() if fleets is None else fleets)
        for channel in fleet.channels
    )
