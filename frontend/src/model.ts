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
export interface LiteratureGraphNode {
  nodeId: string;
  kind: string;
  label: string;
  trustStatus: string;
  source?: string;
  publicationYear?: number | null;
  isContentAccessible?: boolean;
  entityKind?: string;
}
export interface LiteratureGraphEdge { sourceId: string; targetId: string; edgeType: string; relationSource: string; trustStatus: string; }
export interface LiteratureGraph { trustStatus: string; nodes: LiteratureGraphNode[]; edges: LiteratureGraphEdge[]; }

export interface ImportedBundle {
  schemaVersion: string;
  mission: Mission;
  source: "demo" | "local-file" | "loopback";
  fleet: { displayName: string; missionType: string; releaseGate: string } | null;
  status: { missionState: string; retryCount: number; retryBudget: number; returnReason: string | null } | null;
  stations: Array<{ stationType: string; status: string }>;
  facilities: Array<{ facilityType: string; status: string }>;
  evidenceCards: EvidenceCard[];
  conditionMatrix: ConditionMatrixRow[];
  timeline: TimelineEntry[];
  literatureRelations: RelationBundle | null;
  crossrefRelations: RelationBundle | null;
  literatureGraph: LiteratureGraph;
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

function literatureGraph(value: unknown): LiteratureGraph {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return { trustStatus: "unavailable", nodes: [], edges: [] };
  const raw = value as JsonObject;
  const nodeValues = Array.isArray(raw.nodes) ? raw.nodes : [];
  const nodes = nodeValues.flatMap((entry) => {
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) return [];
    const node = entry as JsonObject;
    if (typeof node.node_id !== "string" || !node.node_id || typeof node.kind !== "string" || !node.kind || typeof node.label !== "string" || !node.label || typeof node.trust_status !== "string" || !node.trust_status) return [];
    return [{
      nodeId: node.node_id.slice(0, 300), kind: node.kind.slice(0, 80), label: node.label.slice(0, 500), trustStatus: node.trust_status.slice(0, 160),
      source: typeof node.source === "string" ? node.source.slice(0, 120) : undefined,
      publicationYear: typeof node.publication_year === "number" ? node.publication_year : null,
      isContentAccessible: typeof node.is_content_accessible === "boolean" ? node.is_content_accessible : undefined,
      entityKind: typeof node.entity_kind === "string" ? node.entity_kind.slice(0, 80) : undefined,
    }];
  }).slice(0, 96);
  const nodeIds = new Set(nodes.map((node) => node.nodeId));
  const edgeValues = Array.isArray(raw.edges) ? raw.edges : [];
  const edges = edgeValues.flatMap((entry) => {
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) return [];
    const edge = entry as JsonObject;
    if (typeof edge.source_id !== "string" || typeof edge.target_id !== "string" || typeof edge.edge_type !== "string" || typeof edge.relation_source !== "string" || typeof edge.trust_status !== "string" || !nodeIds.has(edge.source_id) || !nodeIds.has(edge.target_id)) return [];
    return [{ sourceId: edge.source_id, targetId: edge.target_id, edgeType: edge.edge_type.slice(0, 80), relationSource: edge.relation_source.slice(0, 80), trustStatus: edge.trust_status.slice(0, 160) }];
  }).slice(0, 144);
  return { trustStatus: typeof raw.trust_status === "string" ? raw.trust_status.slice(0, 160) : "unclassified", nodes, edges };
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
    literatureRelations: relation(root.literature_relations), crossrefRelations: relation(root.crossref_relations), literatureGraph: literatureGraph(root.literature_graph),
    report: root.mission_report && typeof root.mission_report === "object" && !Array.isArray(root.mission_report) && typeof (root.mission_report as JsonObject).summary === "string" ? { summary: (root.mission_report as JsonObject).summary as string, limitations: textList((root.mission_report as JsonObject).limitations), nextSteps: textList((root.mission_report as JsonObject).next_steps) } : null,
  };
}

const demoLiteratureGraph = (() => {
  const paperTitles = [
    "Illustrative record 01: epitaxial strain survey", "Illustrative record 02: thickness-dependent phase map", "Illustrative record 03: substrate boundary comparison", "Illustrative record 04: oxygen vacancy reporting", "Illustrative record 05: diffraction assignment", "Illustrative record 06: microscopy contrast", "Illustrative record 07: electrical switching protocol", "Illustrative record 08: growth pressure sensitivity", "Illustrative record 09: interface chemistry", "Illustrative record 10: domain configuration", "Illustrative record 11: temperature-dependent stability", "Illustrative record 12: superlattice constraint", "Illustrative record 13: annealing history", "Illustrative record 14: elastic boundary condition", "Illustrative record 15: defect-mediated response", "Illustrative record 16: reciprocal-space mapping", "Illustrative record 17: cross-study condition table", "Illustrative record 18: finite-size limitation", "Illustrative record 19: measurement geometry", "Illustrative record 20: reporting uncertainty"
  ];
  const papers = paperTitles.map((title, index) => ({ node_id: `paper:demo-${index + 1}`, kind: "candidate_paper", label: title, trust_status: "synthetic_demo_candidate_not_scientific_evidence", source: "synthetic demo", publication_year: 2012 + (index % 14), is_content_accessible: false }));
  const evidence = Array.from({ length: 4 }, (_, index) => ({ node_id: `evidence:demo-${index + 1}`, kind: "accepted_evidence", label: `Synthetic review placeholder ${index + 1}`, trust_status: "synthetic_demo_review_marker" }));
  const references = Array.from({ length: 8 }, (_, index) => ({ node_id: `reference:demo-${index + 1}`, kind: index % 2 ? "crossref_work" : "openalex_work", label: `Synthetic relation target ${index + 1}`, trust_status: "synthetic_demo_metadata_relation", source: index % 2 ? "Crossref" : "OpenAlex" }));
  return {
    trust_status: "synthetic_demo_navigation_only_not_literature_evidence",
    nodes: [{ node_id: "mission:demo", kind: "mission", label: "BiFeO3 / phase stability", trust_status: "mission_navigation" }, ...papers, ...evidence, ...references],
    edges: [
      ...papers.map((paper) => ({ source_id: "mission:demo", target_id: paper.node_id, edge_type: "retrieval_candidate", relation_source: "synthetic demo", trust_status: "synthetic_demo_candidate_not_scientific_evidence" })),
      ...evidence.map((item, index) => ({ source_id: papers[index].node_id, target_id: item.node_id, edge_type: "source_provenance", relation_source: "synthetic demo", trust_status: "synthetic_demo_review_marker" })),
      ...papers.map((paper, index) => ({ source_id: paper.node_id, target_id: references[index % references.length].node_id, edge_type: index % 2 ? "crossref_reference" : "citation_reference", relation_source: index % 2 ? "Crossref" : "OpenAlex", trust_status: "synthetic_demo_metadata_relation" })),
    ],
  };
})();
export const demoBundle: ImportedBundle = readBundle({ schema_version: "1.0", mission: { mission_id: "mission_demo_bfo", question: "Why do bounded thin-film studies disagree about phase stability?", material: "BiFeO3", property_name: "phase stability", scope: "epitaxial thin films" }, fleet_assignment: { display_name_en: "Route Diagnostics Fleet", mission_type: "literature_discrepancy", release_gate: "cross_check_review" }, status: { mission_state: "INTAKE", retry_count: 0, retry_budget: 2, return_reason: null }, stations: [{ station_type: "question_intake", status: "active" }], facilities: [], evidence_cards: [], condition_matrix: [], timeline: [], literature_graph: demoLiteratureGraph }, "demo");