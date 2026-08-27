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
export interface MaterialFact { factId: string; segmentId: string; category: string; name: string; value: string | number | null; unit: string | null; normalizedValue: string | number | null; normalizedUnit: string | null; qualifiers: Record<string, string | number | boolean | null>; locator: string; }

export interface GapCounterevidenceBoundary {
  status: string;
  approvedQueryCount: number;
  executedQueryCount: number;
}

export interface ResearchGapCandidate {
  gapId: string;
  problemDescription: string;
  evidenceIds: string[];
  conflictOrMissingEvidence: string[];
  noveltyStatus: string;
  actionability: string;
  falsifiableHypothesis: string;
  suggestedValidation: string[];
  evidenceCompleteness: number;
  reviewStatus: "candidate_requires_human_review";
  /** Omitted only for legacy display-only candidates; never enough for completion. */
  counterevidenceBoundary?: GapCounterevidenceBoundary | null;
}
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
export interface EvaluationSummary {
  evidenceQuality: { evidenceCount: number; predictedContradictionCount: number; citationPrecision: number; conditionCompleteness: number; contradictionPrecision: number } | null;
  retrieval: { k: number; retrievedCount: number; goldRelevantCount: number; precisionAtK: number; recallAtK: number; ndcgAtK: number } | null;
  materialFacts: { goldFactCount: number; reviewedFactCount: number; precision: number; recall: number; f1: number; unitMatchAccuracy: number } | null;
  researchGaps: { candidateCount: number; expertApprovalRate: number; meanNoveltyRating: number; meanActionabilityRating: number; evidenceCompletenessRate: number; counterevidenceReviewRate: number; boundedNoDirectMatchRate: number; relatedPriorWorkFoundRate: number; inconclusiveNoveltySearchRate: number } | null;
}
export interface SubmissionReadinessSummary {
  frozenCorpus: { expectedDocumentCount: number; frozenDocumentCount: number; expectedCountMatched: boolean; documentIdUniquenessValid: boolean; doiPresentCount: number; doiMissingCount: number; authorizedAccessBoundaryValid: boolean; evaluationGate: string } | null;
  humanAnnotation: { frozenDocumentCount: number; annotationFileStatus: string; relevanceCounts: { unreviewed: number; relevant: number; partiallyRelevant: number; notRelevant: number }; documentsWithEvidenceAnnotations: number; documentsWithMaterialFactAnnotations: number; documentsWithComparisonAnnotations: number; documentsWithGapAnnotations: number; relevanceEvaluationGate: string } | null;
  bibliographicSource: { frozenDocumentCount: number; documentsWithReviewedBibliographicSource: number; distinctBibliographicSourceCount: number; bibliographicSourceCoverageGate: string } | null;
}
export interface AuditSummary {
  counterevidence: { state: "plan_not_approved" | "awaiting_counterevidence_execution" | "ready"; plannedQueryCount: number; executedQueryCount: number };
  reportEvidence: { acceptedEvidenceCount: number; manifestCoverage: number; gapEvidenceCoverage: number; structuredReportIdentifierCoverage: number; acceptedEvidenceLocatorRenderedCoverage: number; executedGapCounterevidenceBoundaryCount: number; gapCounterevidenceBoundaryRenderedCoverage: number } | null;
  evidenceProvenance: { acceptedEvidenceCount: number; exactSourceMapMatchCount: number; manualLocatorOnlyCount: number; exactSourceMapMatchRate: number } | null;
  sciverseAgenticSearchCount: number;
  submissionReadiness: SubmissionReadinessSummary;
  evaluation: EvaluationSummary;
}

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
  researchGapCandidates: ResearchGapCandidate[];
  materialFacts: { documentId: string; trustStatus: string; facts: MaterialFact[] } | null;
  sourceMapSummary: { documentCount: number; segmentCount: number; documentIds: string[] };
  materialFactSummary: { documentCount: number; factCount: number };
  auditSummary: AuditSummary;
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

function gapCounterevidenceBoundary(value: unknown): GapCounterevidenceBoundary | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as JsonObject;
  const status = raw.status;
  const approved = raw.approved_query_count;
  const executed = raw.executed_query_count;
  const queryHashes = raw.query_sha256;
  const historyHash = raw.candidate_history_sha256;
  const fingerprint = (item: unknown): item is string => typeof item === "string" && /^[0-9a-f]{64}$/.test(item);
  if (
    status !== "all_approved_counterevidence_queries_recorded"
    || typeof approved !== "number" || !Number.isSafeInteger(approved) || approved < 1
    || typeof executed !== "number" || executed !== approved
    || !Array.isArray(queryHashes) || queryHashes.length !== approved || !queryHashes.every(fingerprint)
    || !fingerprint(historyHash)
  ) return null;
  return { status, approvedQueryCount: approved, executedQueryCount: executed };
}

function reviewedSummary(value: unknown, countKey: string): { documentCount: number; recordCount: number; documentIds: string[] } {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return { documentCount: 0, recordCount: 0, documentIds: [] };
  const raw = value as JsonObject;
  const documentCount = typeof raw.document_count === "number" && Number.isSafeInteger(raw.document_count) && raw.document_count >= 0 ? raw.document_count : 0;
  const recordCount = typeof raw[countKey] === "number" && Number.isSafeInteger(raw[countKey]) && raw[countKey] >= 0 ? raw[countKey] : 0;
  return { documentCount, recordCount, documentIds: textList(raw.document_ids).slice(0, 256) };
}

function auditCount(value: unknown): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : 0;
}
function auditRate(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0;
}
function auditFlag(value: unknown): boolean { return value === true; }
function auditText(value: unknown): string { return typeof value === "string" ? value.slice(0, 160) : "unavailable"; }
function evaluationSummary(value: unknown): EvaluationSummary {
  const root = value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
  const evidenceQuality = root.evidence_quality && typeof root.evidence_quality === "object" && !Array.isArray(root.evidence_quality) ? root.evidence_quality as JsonObject : null;
  const retrieval = root.retrieval && typeof root.retrieval === "object" && !Array.isArray(root.retrieval) ? root.retrieval as JsonObject : null;
  const materialFacts = root.material_facts && typeof root.material_facts === "object" && !Array.isArray(root.material_facts) ? root.material_facts as JsonObject : null;
  const researchGaps = root.research_gaps && typeof root.research_gaps === "object" && !Array.isArray(root.research_gaps) ? root.research_gaps as JsonObject : null;
  return {
    evidenceQuality: evidenceQuality ? {
      evidenceCount: auditCount(evidenceQuality.evidence_count), predictedContradictionCount: auditCount(evidenceQuality.predicted_contradiction_count),
      citationPrecision: auditRate(evidenceQuality.citation_precision), conditionCompleteness: auditRate(evidenceQuality.condition_completeness),
      contradictionPrecision: auditRate(evidenceQuality.contradiction_precision),
    } : null,
    retrieval: retrieval ? {
      k: auditCount(retrieval.k), retrievedCount: auditCount(retrieval.retrieved_count),
      goldRelevantCount: auditCount(retrieval.gold_relevant_count), precisionAtK: auditRate(retrieval.precision_at_k),
      recallAtK: auditRate(retrieval.recall_at_k), ndcgAtK: auditRate(retrieval.ndcg_at_k),
    } : null,
    materialFacts: materialFacts ? {
      goldFactCount: auditCount(materialFacts.gold_fact_count), reviewedFactCount: auditCount(materialFacts.reviewed_fact_count),
      precision: auditRate(materialFacts.precision), recall: auditRate(materialFacts.recall),
      f1: auditRate(materialFacts.f1), unitMatchAccuracy: auditRate(materialFacts.unit_match_accuracy),
    } : null,
    researchGaps: researchGaps ? {
      candidateCount: auditCount(researchGaps.candidate_count), expertApprovalRate: auditRate(researchGaps.expert_approval_rate),
      meanNoveltyRating: typeof researchGaps.mean_novelty_rating === "number" && Number.isFinite(researchGaps.mean_novelty_rating) && researchGaps.mean_novelty_rating >= 1 && researchGaps.mean_novelty_rating <= 5 ? researchGaps.mean_novelty_rating : 0,
      meanActionabilityRating: typeof researchGaps.mean_actionability_rating === "number" && Number.isFinite(researchGaps.mean_actionability_rating) && researchGaps.mean_actionability_rating >= 1 && researchGaps.mean_actionability_rating <= 5 ? researchGaps.mean_actionability_rating : 0,
      evidenceCompletenessRate: auditRate(researchGaps.evidence_completeness_rate),
      counterevidenceReviewRate: auditRate(researchGaps.counterevidence_review_rate),
      boundedNoDirectMatchRate: auditRate(researchGaps.bounded_no_direct_match_rate),
      relatedPriorWorkFoundRate: auditRate(researchGaps.related_prior_work_found_rate),
      inconclusiveNoveltySearchRate: auditRate(researchGaps.inconclusive_novelty_search_rate),
    } : null,
  };
}

function submissionReadiness(value: unknown): SubmissionReadinessSummary {
  const root = value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
  const frozen = root.frozen_corpus && typeof root.frozen_corpus === "object" && !Array.isArray(root.frozen_corpus) ? root.frozen_corpus as JsonObject : null;
  const annotation = root.human_annotation && typeof root.human_annotation === "object" && !Array.isArray(root.human_annotation) ? root.human_annotation as JsonObject : null;
  const bibliography = root.bibliographic_source && typeof root.bibliographic_source === "object" && !Array.isArray(root.bibliographic_source) ? root.bibliographic_source as JsonObject : null;
  const relevance = annotation?.relevance_counts && typeof annotation.relevance_counts === "object" && !Array.isArray(annotation.relevance_counts) ? annotation.relevance_counts as JsonObject : null;
  return {
    frozenCorpus: frozen ? {
      expectedDocumentCount: auditCount(frozen.expected_document_count), frozenDocumentCount: auditCount(frozen.frozen_document_count),
      expectedCountMatched: auditFlag(frozen.expected_count_matched), documentIdUniquenessValid: auditFlag(frozen.document_id_uniqueness_valid),
      doiPresentCount: auditCount(frozen.doi_present_count), doiMissingCount: auditCount(frozen.doi_missing_count),
      authorizedAccessBoundaryValid: auditFlag(frozen.authorized_access_boundary_valid), evaluationGate: auditText(frozen.evaluation_gate),
    } : null,
    humanAnnotation: annotation ? {
      frozenDocumentCount: auditCount(annotation.frozen_document_count), annotationFileStatus: auditText(annotation.annotation_file_status),
      relevanceCounts: { unreviewed: auditCount(relevance?.unreviewed), relevant: auditCount(relevance?.relevant), partiallyRelevant: auditCount(relevance?.partially_relevant), notRelevant: auditCount(relevance?.not_relevant) },
      documentsWithEvidenceAnnotations: auditCount(annotation.documents_with_evidence_annotations), documentsWithMaterialFactAnnotations: auditCount(annotation.documents_with_material_fact_annotations),
      documentsWithComparisonAnnotations: auditCount(annotation.documents_with_comparison_annotations), documentsWithGapAnnotations: auditCount(annotation.documents_with_gap_annotations),
      relevanceEvaluationGate: auditText(annotation.relevance_evaluation_gate),
    } : null,
    bibliographicSource: bibliography ? {
      frozenDocumentCount: auditCount(bibliography.frozen_document_count), documentsWithReviewedBibliographicSource: auditCount(bibliography.documents_with_reviewed_bibliographic_source),
      distinctBibliographicSourceCount: auditCount(bibliography.distinct_bibliographic_source_count), bibliographicSourceCoverageGate: auditText(bibliography.bibliographic_source_coverage_gate),
    } : null,
  };
}

function auditSummary(value: unknown): AuditSummary {
  const root = value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
  const counterevidenceRaw = root.counterevidence && typeof root.counterevidence === "object" && !Array.isArray(root.counterevidence) ? root.counterevidence as JsonObject : null;
  const counterevidenceState = counterevidenceRaw?.state === "ready" || counterevidenceRaw?.state === "awaiting_counterevidence_execution" ? counterevidenceRaw.state : "plan_not_approved";
  const reportRaw = root.report_evidence && typeof root.report_evidence === "object" && !Array.isArray(root.report_evidence) ? root.report_evidence as JsonObject : null;
  const provenanceRaw = root.evidence_provenance && typeof root.evidence_provenance === "object" && !Array.isArray(root.evidence_provenance) ? root.evidence_provenance as JsonObject : null;
  const externalRaw = root.external_retrieval && typeof root.external_retrieval === "object" && !Array.isArray(root.external_retrieval) ? root.external_retrieval as JsonObject : null;
  return {
    counterevidence: { state: counterevidenceState, plannedQueryCount: auditCount(counterevidenceRaw?.planned_query_count), executedQueryCount: auditCount(counterevidenceRaw?.executed_query_count) },
    reportEvidence: reportRaw ? { acceptedEvidenceCount: auditCount(reportRaw.accepted_evidence_count), manifestCoverage: auditRate(reportRaw.manifest_coverage), gapEvidenceCoverage: auditRate(reportRaw.gap_evidence_coverage), structuredReportIdentifierCoverage: auditRate(reportRaw.structured_report_identifier_coverage), acceptedEvidenceLocatorRenderedCoverage: auditRate(reportRaw.accepted_evidence_locator_rendered_coverage), executedGapCounterevidenceBoundaryCount: auditCount(reportRaw.executed_gap_counterevidence_boundary_count), gapCounterevidenceBoundaryRenderedCoverage: auditRate(reportRaw.gap_counterevidence_boundary_rendered_coverage) } : null,
    evidenceProvenance: provenanceRaw ? { acceptedEvidenceCount: auditCount(provenanceRaw.accepted_evidence_count), exactSourceMapMatchCount: auditCount(provenanceRaw.exact_source_map_match_count), manualLocatorOnlyCount: auditCount(provenanceRaw.manual_locator_only_count), exactSourceMapMatchRate: auditRate(provenanceRaw.exact_source_map_match_rate) } : null,
    sciverseAgenticSearchCount: externalRaw ? auditCount(externalRaw.sciverse_agentic_search_count) : 0,
    submissionReadiness: submissionReadiness(root.submission_readiness),
    evaluation: evaluationSummary(root.evaluation),
  };
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
  const researchGapCandidates = Array.isArray(root.research_gap_candidates) ? root.research_gap_candidates.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const candidate = entry as JsonObject;
    const completeness = candidate.evidence_completeness;
    const counterevidenceBoundary = gapCounterevidenceBoundary(candidate.counterevidence_boundary);
    if (candidate.review_status !== "candidate_requires_human_review" || typeof candidate.gap_id !== "string" || !candidate.gap_id || typeof candidate.problem_description !== "string" || !candidate.problem_description || typeof candidate.novelty_status !== "string" || !candidate.novelty_status || typeof candidate.actionability !== "string" || !candidate.actionability || typeof candidate.falsifiable_hypothesis !== "string" || !candidate.falsifiable_hypothesis || typeof completeness !== "number" || !Number.isFinite(completeness) || completeness < 0 || completeness > 1) return [];
    const evidenceIds = textList(candidate.evidence_ids);
    const conflictOrMissingEvidence = textList(candidate.conflict_or_missing_evidence);
    const suggestedValidation = textList(candidate.suggested_validation);
    if (evidenceIds.length < 2 || new Set(evidenceIds).size !== evidenceIds.length || !conflictOrMissingEvidence.length || !suggestedValidation.length) return [];
    return [{ gapId: candidate.gap_id.slice(0, 160), problemDescription: candidate.problem_description.slice(0, 1200), evidenceIds: evidenceIds.slice(0, 24), conflictOrMissingEvidence: conflictOrMissingEvidence.slice(0, 24), noveltyStatus: candidate.novelty_status.slice(0, 180), actionability: candidate.actionability.slice(0, 800), falsifiableHypothesis: candidate.falsifiable_hypothesis.slice(0, 1000), suggestedValidation: suggestedValidation.slice(0, 12), evidenceCompleteness: completeness, reviewStatus: "candidate_requires_human_review" as const, counterevidenceBoundary }];
  }).slice(0, 24) : [];
  const rawMaterialFacts = root.material_facts && typeof root.material_facts === "object" && !Array.isArray(root.material_facts) ? root.material_facts as JsonObject : null;
  const materialFacts = rawMaterialFacts && typeof rawMaterialFacts.document_id === "string" && typeof rawMaterialFacts.trust_status === "string" && Array.isArray(rawMaterialFacts.facts) ? {
    documentId: rawMaterialFacts.document_id.slice(0, 300), trustStatus: rawMaterialFacts.trust_status.slice(0, 200),
    facts: rawMaterialFacts.facts.flatMap((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
      const fact = entry as JsonObject;
      const value = fact.value; const normalizedValue = fact.normalized_value;
      if (typeof fact.fact_id !== "string" || typeof fact.segment_id !== "string" || typeof fact.category !== "string" || typeof fact.name !== "string" || typeof fact.locator !== "string" || (value !== null && !["string", "number"].includes(typeof value)) || (normalizedValue !== null && !["string", "number"].includes(typeof normalizedValue))) return [];
      const qualifiers = record(fact.qualifiers);
      return [{ factId: fact.fact_id.slice(0, 160), segmentId: fact.segment_id.slice(0, 160), category: fact.category.slice(0, 80), name: fact.name.slice(0, 200), value: value as string | number | null, unit: typeof fact.unit === "string" ? fact.unit.slice(0, 80) : null, normalizedValue: normalizedValue as string | number | null, normalizedUnit: typeof fact.normalized_unit === "string" ? fact.normalized_unit.slice(0, 80) : null, qualifiers, locator: fact.locator.slice(0, 300) }];
    }).slice(0, 48),
  } : null;
  return {
    schemaVersion: typeof root.schema_version === "string" ? root.schema_version : "unknown",
    mission, source,
    fleet: rawFleet ? { displayName: typeof rawFleet.display_name_zh === "string" ? rawFleet.display_name_zh : typeof rawFleet.display_name_en === "string" ? rawFleet.display_name_en : "Unclassified fleet", missionType: typeof rawFleet.mission_type === "string" ? rawFleet.mission_type : "unknown", releaseGate: typeof rawFleet.release_gate === "string" ? rawFleet.release_gate : "unknown" } : null,
    status: rawStatus ? { missionState: typeof rawStatus.mission_state === "string" ? rawStatus.mission_state : "unknown", retryCount: typeof rawStatus.retry_count === "number" ? rawStatus.retry_count : 0, retryBudget: typeof rawStatus.retry_budget === "number" ? rawStatus.retry_budget : 0, returnReason: typeof rawStatus.return_reason === "string" ? rawStatus.return_reason : null } : null,
    stations: Array.isArray(root.stations) ? root.stations.flatMap((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && typeof (entry as JsonObject).station_type === "string" ? [{ stationType: (entry as JsonObject).station_type as string, status: typeof (entry as JsonObject).status === "string" ? (entry as JsonObject).status as string : "unknown" }] : []) : [],
    facilities: Array.isArray(root.facilities) ? root.facilities.flatMap((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && typeof (entry as JsonObject).facility_type === "string" ? [{ facilityType: (entry as JsonObject).facility_type as string, status: typeof (entry as JsonObject).status === "string" ? (entry as JsonObject).status as string : "unknown" }] : []) : [],
    evidenceCards, conditionMatrix, researchGapCandidates, materialFacts,
    sourceMapSummary: (() => { const summary = reviewedSummary(root.reviewed_source_map_summary, "segment_count"); return { documentCount: summary.documentCount, segmentCount: summary.recordCount, documentIds: summary.documentIds };  })(),
    materialFactSummary: (() => { const summary = reviewedSummary(root.reviewed_material_fact_summary, "fact_count"); return { documentCount: summary.documentCount, factCount: summary.recordCount }; })(),
    auditSummary: auditSummary(root.audit_summary),
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
