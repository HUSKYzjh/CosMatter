import { FLEETS, type FleetRecord, type FleetStatus, type UiLocale } from "./fleetRegistry";
import type { ImportedBundle } from "./model";

const PARTICIPANT_FLEETS: Record<string, readonly string[]> = {
  LOCAL: ["pioneer"], INTAKE: ["pioneer"], NEED_SCOPE: ["pioneer"],
  PLAN: ["pioneer", "observatory"], RETRIEVE: ["observatory"], SELECT: ["observatory"],
  EXTRACT: ["observatory", "sentinel"], MAP: ["constellation"], HAZARD_SCAN: ["diagnostics", "sentinel"],
  VERIFY: ["sentinel"], HUMAN_REVIEW: ["sentinel"], REPORT: ["horizon", "diagnostics"],
};

export interface FleetMissionRole {
  missionState: string;
  participates: boolean;
  reasonZh: string;
  reasonEn: string;
  handoffZh: string;
  handoffEn: string;
}

const MISSION_ROLE_COPY: Record<string, Omit<FleetMissionRole, "missionState" | "participates">> = {
  LOCAL: { reasonZh: "等待研究者确认任务边界", reasonEn: "Waiting for the researcher to confirm the mission boundary", handoffZh: "确认任务简报", handoffEn: "Confirm the mission brief" },
  INTAKE: { reasonZh: "整理研究问题、对象与比较范围", reasonEn: "Organising the question, objects, and comparison scope", handoffZh: "任务简报", handoffEn: "Mission brief" },
  NEED_SCOPE: { reasonZh: "补齐可比较的研究边界", reasonEn: "Completing comparable research boundaries", handoffZh: "范围补充记录", handoffEn: "Scope-completion record" },
  PLAN: { reasonZh: "将已确认任务转为受控检索计划", reasonEn: "Turning the confirmed mission into a controlled retrieval plan", handoffZh: "已批准检索计划", handoffEn: "Approved retrieval plan" },
  RETRIEVE: { reasonZh: "在已批准来源内收集候选书目元数据", reasonEn: "Collecting candidate bibliographic metadata from approved sources", handoffZh: "候选文献清单", handoffEn: "Candidate literature list" },
  SELECT: { reasonZh: "记录候选文献的人工筛选决定", reasonEn: "Recording human screening decisions for candidate literature", handoffZh: "全文核对候选", handoffEn: "Full-text review candidates" },
  EXTRACT: { reasonZh: "把授权全文转为私有来源定位与材料事实", reasonEn: "Turning authorised full text into private source locations and material facts", handoffZh: "Source Map 与事实草稿", handoffEn: "Source Map and fact drafts" },
  MAP: { reasonZh: "组织论文、书目关系与已登记证据", reasonEn: "Organising papers, bibliographic relations, and registered evidence", handoffZh: "可审查文献子图", handoffEn: "Auditable literature subgraph" },
  HAZARD_SCAN: { reasonZh: "按已批准计划补充反例检索边界", reasonEn: "Completing the approved counterevidence-search boundary", handoffZh: "已执行反例边界", handoffEn: "Executed counterevidence boundary" },
  VERIFY: { reasonZh: "核对来源定位、条件字段与 EvidenceCard", reasonEn: "Verifying source locations, condition fields, and EvidenceCards", handoffZh: "已接受 EvidenceCard", handoffEn: "Accepted EvidenceCard" },
  HUMAN_REVIEW: { reasonZh: "等待研究者审核证据或候选结论", reasonEn: "Waiting for researcher review of evidence or candidate findings", handoffZh: "人工审核决定", handoffEn: "Human review decision" },
  REPORT: { reasonZh: "把已核验工件整理为带引用的调研报告", reasonEn: "Compiling verified artifacts into a cited research report", handoffZh: "结构化调研报告", handoffEn: "Structured research report" },
};

/** A local mission shell is ready for work, but it must never be displayed as executing. */
export function fleetRuntimeStatus(fleet: FleetRecord, bundle: ImportedBundle): FleetStatus {
  if (fleet.status === "framework_only") return "framework_only";
  const state = bundle.status?.missionState ?? "LOCAL";
  if (state === "LOCAL") return fleet.status === "active" ? "ready" : fleet.status;
  const active: Record<string, readonly string[]> = { pioneer: ["INTAKE", "NEED_SCOPE"], observatory: ["PLAN", "RETRIEVE", "SELECT", "EXTRACT"], constellation: ["MAP"], diagnostics: ["HAZARD_SCAN"], sentinel: ["VERIFY", "HUMAN_REVIEW"], horizon: ["REPORT"] };
  if (active[fleet.id]?.includes(state)) return fleet.id === "sentinel" && state === "HUMAN_REVIEW" ? "waiting_approval" : "active";
  return fleet.status === "active" ? "ready" : fleet.status;
}

/**
 * `active` is a stage-assignment projection, not proof that a provider, tool,
 * or sub-agent is executing.  The bridge uses this label while the catalogue
 * keeps its separate capability labels.
 */
export function fleetRuntimeLabel(status: FleetStatus, locale: UiLocale): string {
  if (status === "active") return locale === "zh" ? "当前编排" : "In current stage";
  if (status === "ready") return locale === "zh" ? "就绪" : "Ready";
  if (status === "waiting_approval") return locale === "zh" ? "等待批准" : "Awaiting approval";
  return locale === "zh" ? "仅框架" : "Framework only";
}

/** Keep the bridge focused on the stage-relevant fleet(s), not every installed capability. */
export function fleetParticipantsForMission(bundle: ImportedBundle): FleetRecord[] {
  const ids = PARTICIPANT_FLEETS[bundle.status?.missionState ?? "LOCAL"] ?? [];
  return ids.flatMap((id) => FLEETS.filter((fleet) => fleet.id === id));
}

/** Explain why a fleet appears now, or why it remains catalogue-only. */
export function fleetMissionRole(fleet: FleetRecord, bundle: ImportedBundle): FleetMissionRole {
  const missionState = bundle.status?.missionState ?? "LOCAL";
  const role = MISSION_ROLE_COPY[missionState] ?? MISSION_ROLE_COPY.LOCAL;
  const participates = (PARTICIPANT_FLEETS[missionState] ?? []).includes(fleet.id);
  if (participates) return { missionState, participates, ...role };
  return {
    missionState, participates: false,
    reasonZh: "当前阶段未分配该舰队；它仅作为可用能力保留在架构目录中。",
    reasonEn: "This fleet is not assigned to the current stage; it remains in the architecture catalogue as an available capability.",
    handoffZh: "无当前交接工件", handoffEn: "No current handoff artifact",
  };
}
