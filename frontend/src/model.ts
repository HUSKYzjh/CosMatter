export interface Mission {
  missionId: string;
  question: string;
  material: string;
  property: string;
  scope: string;
}

export interface EvidenceCard {
  evidenceId: string;
  claim: string;
  stance: string;
  conditions: Record<string, string | number | boolean | null>;
  quote: string;
  reviewStatus: "accepted";
  provenance: { documentId: string; locator: string; source: string; accessPolicy: string };
  isSynthetic: boolean;
}

export interface TimelineEntry { stationType: string; action: string; state: string; occurredAt: string; }
export interface ConditionMatrixRow { conditionCluster: string; supportingEvidenceIds: string[]; contradictingEvidenceIds: string[]; differingFields: string[]; unknowns: string[]; }
export interface RelationBundle { trustStatus: string; edgeCount: number; }

export interface ImportedBundle {
  schemaVersion: string;
  mission: Mission;
  source: "demo" | "local-file";
  fleet: { displayName: string; missionType: string; releaseGate: string } | null;
  status: { missionState: string; retryCount: number; retryBudget: number; returnReason: string | null } | null;
  stations: Array<{ stationType: string; status: string }>;
  facilities: Array<{ facilityType: string; status: string }>;
  evidenceCards: EvidenceCard[];
  conditionMatrix: ConditionMatrixRow[];
  timeline: TimelineEntry[];
  literatureRelations: RelationBundle | null;
  crossrefRelations: RelationBundle | null;
  report: { summary: string; limitations: string[]; nextSteps: string[] } | null;
}

type JsonObject = Record<string, unknown>;

function object(value: unknown, label: string): JsonObject {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object.`);
  return value as JsonObject;
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string.`);
  return value.trim();
}
function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim())).map((item) => item.trim()) : [];
}
function record(value: unknown): Record<string, string | number | boolean | null> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value as JsonObject).filter(([, item]) => item === null || ["string", "number", "boolean"].includes(typeof item))) as Record<string, string | number | boolean | null>;
}

function relation(value: unknown): RelationBundle | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as JsonObject;
  return { trustStatus: typeof raw.trust_status === "string" ? raw.trust_status : "unclassified", edgeCount: Array.isArray(raw.edges) ? raw.edges.length : 0 };
}

export function readBundle(value: unknown, source: ImportedBundle["source"] = "local-file"): ImportedBundle {
  const root = object(value, "UI JSON");
  const rawMission = object(root.mission, "mission");
  const mission: Mission = {
    missionId: text(rawMission.mission_id, "mission.mission_id"),
    question: text(rawMission.question, "mission.question"),
    material: text(rawMission.material, "mission.material"),
    property: text(rawMission.property_name, "mission.property_name"),
    scope: text(rawMission.scope, "mission.scope"),
  };
  const rawFleet = root.fleet_assignment && typeof root.fleet_assignment === "object" && !Array.isArray(root.fleet_assignment) ? root.fleet_assignment as JsonObject : null;
  const rawStatus = root.status && typeof root.status === "object" && !Array.isArray(root.status) ? root.status as JsonObject : null;
  const evidenceCards = Array.isArray(root.evidence_cards) ? root.evidence_cards.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const item = entry as JsonObject;
    const provenance = item.provenance && typeof item.provenance === "object" && !Array.isArray(item.provenance) ? item.provenance as JsonObject : null;
    if (item.review_status !== "accepted" || !provenance || typeof item.evidence_id !== "string" || typeof item.claim !== "string" || typeof item.quote !== "string") return [];
    return [{ evidenceId: item.evidence_id, claim: item.claim, stance: typeof item.stance === "string" ? item.stance : "context", conditions: record(item.conditions), quote: item.quote, reviewStatus: "accepted" as const, provenance: { documentId: typeof provenance.document_id === "string" ? provenance.document_id : "unknown", locator: typeof provenance.locator === "string" ? provenance.locator : "unknown", source: typeof provenance.source === "string" ? provenance.source : "unknown", accessPolicy: typeof provenance.access_policy === "string" ? provenance.access_policy : "unknown" }, isSynthetic: item.is_synthetic === true }];
  }) : [];
  const conditionMatrix = Array.isArray(root.condition_matrix) ? root.condition_matrix.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const row = entry as JsonObject;
    if (typeof row.condition_cluster !== "string") return [];
    return [{ conditionCluster: row.condition_cluster, supportingEvidenceIds: textList(row.supporting_evidence_ids), contradictingEvidenceIds: textList(row.contradicting_evidence_ids), differingFields: textList(row.differing_fields), unknowns: textList(row.unknowns) }];
  }) : [];
  return {
    schemaVersion: typeof root.schema_version === "string" ? root.schema_version : "unknown",
    mission, source,
    fleet: rawFleet ? { displayName: typeof rawFleet.display_name_zh === "string" ? rawFleet.display_name_zh : typeof rawFleet.display_name_en === "string" ? rawFleet.display_name_en : "Unclassified fleet", missionType: typeof rawFleet.mission_type === "string" ? rawFleet.mission_type : "unknown", releaseGate: typeof rawFleet.release_gate === "string" ? rawFleet.release_gate : "unknown" } : null,
    status: rawStatus ? { missionState: typeof rawStatus.mission_state === "string" ? rawStatus.mission_state : "unknown", retryCount: typeof rawStatus.retry_count === "number" ? rawStatus.retry_count : 0, retryBudget: typeof rawStatus.retry_budget === "number" ? rawStatus.retry_budget : 0, returnReason: typeof rawStatus.return_reason === "string" ? rawStatus.return_reason : null } : null,
    stations: Array.isArray(root.stations) ? root.stations.flatMap((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && typeof (entry as JsonObject).station_type === "string" ? [{ stationType: (entry as JsonObject).station_type as string, status: typeof (entry as JsonObject).status === "string" ? (entry as JsonObject).status as string : "unknown" }] : []) : [],
    facilities: Array.isArray(root.facilities) ? root.facilities.flatMap((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && typeof (entry as JsonObject).facility_type === "string" ? [{ facilityType: (entry as JsonObject).facility_type as string, status: typeof (entry as JsonObject).status === "string" ? (entry as JsonObject).status as string : "unknown" }] : []) : [],
    evidenceCards, conditionMatrix,
    timeline: Array.isArray(root.timeline) ? root.timeline.flatMap((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && typeof (entry as JsonObject).station_type === "string" && typeof (entry as JsonObject).action === "string" ? [{ stationType: (entry as JsonObject).station_type as string, action: (entry as JsonObject).action as string, state: typeof (entry as JsonObject).state === "string" ? (entry as JsonObject).state as string : "unknown", occurredAt: typeof (entry as JsonObject).occurred_at === "string" ? (entry as JsonObject).occurred_at as string : "" }] : []) : [],
    literatureRelations: relation(root.literature_relations), crossrefRelations: relation(root.crossref_relations),
    report: root.mission_report && typeof root.mission_report === "object" && !Array.isArray(root.mission_report) && typeof (root.mission_report as JsonObject).summary === "string" ? { summary: (root.mission_report as JsonObject).summary as string, limitations: textList((root.mission_report as JsonObject).limitations), nextSteps: textList((root.mission_report as JsonObject).next_steps) } : null,
  };
}

export const demoBundle: ImportedBundle = readBundle({ schema_version: "1.0", mission: { mission_id: "mission_demo_bfo", question: "Why do bounded thin-film studies disagree about phase stability?", material: "BiFeO3", property_name: "phase stability", scope: "epitaxial thin films" }, fleet_assignment: { display_name_en: "Route Diagnostics Fleet", mission_type: "literature_discrepancy", release_gate: "cross_check_review" }, status: { mission_state: "INTAKE", retry_count: 0, retry_budget: 2, return_reason: null }, stations: [{ station_type: "question_intake", status: "active" }], facilities: [], evidence_cards: [], condition_matrix: [], timeline: [] }, "demo");