export interface LocalApiStatus {
  api_mode: "loopback_only";
  providers: Record<string, boolean>;
}
export interface FacilityContractManifest { facility_type: string; fleet_types: string[]; input_schema: string[]; output_schema: string[]; allowed_descriptors: string[]; failure_modes: string[]; human_review_required: boolean; execution_boundary: "static_contract_only_not_execution_authorization"; }
export interface FacilityContractCatalogue { schema_version: "cosmatter.facility-contract-catalogue/v1"; trust_status: "static_facility_contracts_not_execution_or_evidence_acceptance"; contracts: FacilityContractManifest[]; }
export type FacilityCatalogueHealth = "disabled" | "loading" | "ready" | "unavailable";

const stringList = (value: unknown, maximum: number): value is string[] => Array.isArray(value)
  && value.length > 0 && value.length <= maximum
  && value.every((item) => typeof item === "string" && item.length > 0 && item.length <= 120);

/** Validate the small static contract surface before treating it as locally loaded. */
export function isFacilityContractCatalogue(value: unknown): value is FacilityContractCatalogue {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const catalogue = value as Record<string, unknown>;
  if (catalogue.schema_version !== "cosmatter.facility-contract-catalogue/v1" || catalogue.trust_status !== "static_facility_contracts_not_execution_or_evidence_acceptance" || !Array.isArray(catalogue.contracts) || catalogue.contracts.length !== 15) return false;
  const facilityTypes = new Set<string>();
  return catalogue.contracts.every((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const contract = item as Record<string, unknown>;
    if (typeof contract.facility_type !== "string" || !contract.facility_type || contract.facility_type.length > 80 || facilityTypes.has(contract.facility_type)) return false;
    facilityTypes.add(contract.facility_type);
    return stringList(contract.fleet_types, 4)
      && stringList(contract.input_schema, 8)
      && stringList(contract.output_schema, 8)
      && stringList(contract.allowed_descriptors, 8)
      && stringList(contract.failure_modes, 8)
      && typeof contract.human_review_required === "boolean"
      && contract.execution_boundary === "static_contract_only_not_execution_authorization";
  });
}

export interface LiveMission { run_id: string; mission_id: string; fleet_type: string; mission_type: string; state: string; }
export interface DraftPlan { run_id: string; trust_status: "untrusted_draft"; content: string; }
export interface ApprovedPlan { run_id: string; plan_id: string; queries: string[]; counter_queries: string[]; }
export interface SearchResult { run_id: string; candidate_count: number; sources: string[]; source_counts: Record<string, number>; }
export type RetrievalSource = "sciverse" | "openalex" | "crossref";

export function localApiEnabled(): boolean { return new URLSearchParams(window.location.search).get("api") === "local"; }

export type LocalApiRequestFailure = "read_timeout" | "write_outcome_unknown" | "transport";

/** Safe, display-neutral request failure classification for the loopback API. */
export class LocalApiRequestError extends Error {
  readonly failure: LocalApiRequestFailure;
  constructor(failure: LocalApiRequestFailure) {
    super(failure === "write_outcome_unknown" ? "local API write outcome is unknown" : "local API request is unavailable");
    this.name = "LocalApiRequestError";
    this.failure = failure;
  }
}

export const LOCAL_API_READ_TIMEOUT_MS = 12_000;
export const LOCAL_API_WRITE_TIMEOUT_MS = 60_000;

export function localApiTimeoutFailure(method?: string): LocalApiRequestFailure {
  return (method ?? "GET").toUpperCase() === "GET" ? "read_timeout" : "write_outcome_unknown";
}

/** A received 5xx does not prove that a mutation failed before committing. */
export function localApiHttpFailure(method: string | undefined, status: number): LocalApiRequestFailure {
  return (method ?? "GET").toUpperCase() !== "GET" && status >= 500 ? "write_outcome_unknown" : "transport";
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = (init?.method ?? "GET") === "GET" ? LOCAL_API_READ_TIMEOUT_MS : LOCAL_API_WRITE_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  let response: Response;
  try {
    response = await fetch(path, { ...init, cache: "no-store", signal: controller.signal });
  } catch {
    throw new LocalApiRequestError(timedOut ? localApiTimeoutFailure(init?.method) : "transport");
  } finally {
    window.clearTimeout(timeout);
  }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    // Provider and filesystem details are untrusted display data.  Callers
    // receive only a neutral transport classification.
    throw new LocalApiRequestError(localApiHttpFailure(init?.method, response.status));
  }
  return payload as T;
}
function jsonPost<T>(path: string, payload: unknown): Promise<T> { return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }
export function getLocalApiStatus(): Promise<LocalApiStatus> { return request<LocalApiStatus>("./api/status"); }
export function getFacilityContractCatalogue(): Promise<FacilityContractCatalogue> { return request<FacilityContractCatalogue>("./api/facility-contracts"); }
export function createLiveMission(payload: { question: string; material: string; property: string; scope: string }): Promise<LiveMission> { return jsonPost<LiveMission>("./api/missions", payload); }
export function draftAuthorizedPlan(runId: string, dshCallId: string): Promise<DraftPlan> { return jsonPost<DraftPlan>(`./api/runs/${encodeURIComponent(runId)}/authorized-draft-plan`, { authorizations: ["mission_scoped_egress_consent", "deepseek_request_consent"], actor: "browser_researcher", dsh_call_id: dshCallId }); }
export function approveLivePlan(runId: string, plan: unknown): Promise<ApprovedPlan> { return jsonPost<ApprovedPlan>(`./api/runs/${encodeURIComponent(runId)}/approve-plan`, plan); }
export function executeAuthorizedApprovedQuery(runId: string, queryIndex: number, sources: RetrievalSource[], counter: boolean, dshCallId: string): Promise<SearchResult> { return jsonPost<SearchResult>(`./api/runs/${encodeURIComponent(runId)}/authorized-execute-query`, { query_index: queryIndex, counter, sources, authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"], actor: "browser_researcher", dsh_call_id: dshCallId }); }
export function fetchLiveUiBundle(runId: string): Promise<unknown> { return request<unknown>(`./api/runs/${encodeURIComponent(runId)}/ui`); }
export type EvidenceGraphNodeType = "Mission" | "Paper" | "Entity" | "Condition" | "EvidenceCard";
export interface EvidenceGraphPage { schema_version: "1.0"; graph_id: string; mission_id: string; trust_status: string; nodes: Array<{ node_id: string; node_type: EvidenceGraphNodeType; label: string; attributes: Record<string, unknown> }>; edges: Array<{ edge_id: string; source_id: string; target_id: string; relation: string }>; page: { node_types: EvidenceGraphNodeType[]; offset: number; limit: number; node_total: number; edge_count: number; truncated: boolean; empty_result_meaning: string }; }
export function getEvidenceGraphPage(runId: string, options: { nodeType?: EvidenceGraphNodeType; offset?: number; limit?: number } = {}): Promise<EvidenceGraphPage> { const query = new URLSearchParams(); if (options.nodeType) query.set("node_type", options.nodeType); if (options.offset !== undefined) query.set("offset", String(options.offset)); if (options.limit !== undefined) query.set("limit", String(options.limit)); return request<EvidenceGraphPage>(`./api/runs/${encodeURIComponent(runId)}/graph${query.size ? `?${query}` : ""}`); }
export interface EvidenceGraphReviewRequest { request_id: string; graph_id: string; node_ids: string[]; rationale: string; status: "pending_human_review_not_evidence_acceptance"; }
export interface EvidenceGraphPlanDraft { plan_id: string; graph_id: string; node_ids: string[]; intent: string; proposed_action: "request_human_to_review_or_project_graph"; trust_status: "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance"; }
export interface EvidenceGraphPlanApproval { approval_id: string; plan_id: string; reviewer: string; rationale: string; status: "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance"; }
export function requestEvidenceGraphReview(runId: string, nodeIds: string[], rationale: string): Promise<EvidenceGraphReviewRequest> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/graph/review-request`, { node_ids: nodeIds, rationale }); }
export function draftEvidenceGraphPlan(runId: string, nodeIds: string[], intent: string): Promise<EvidenceGraphPlanDraft> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/graph/plan-draft`, { node_ids: nodeIds, intent }); }
export function approveEvidenceGraphPlan(runId: string, planId: string, reviewer: string, rationale: string): Promise<EvidenceGraphPlanApproval> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/graph/plan-approval`, { plan_id: planId, reviewer, rationale }); }
export interface QuestionCandidate { id: string; question: string; material: string; property: string; scope: string; kind: "survey" | "contrast" | "mechanism"; }
export async function requestQuestionCandidates(question: string): Promise<QuestionCandidate[]> {
  const result = await jsonPost<{ trust_status: string; candidates: QuestionCandidate[] }>("./api/question-candidates", { question, candidate_generation_authorized: true });
  return result.candidates;
}
export interface CandidateScreeningDecision { document_id: string; decision: string; reason_codes: string[]; }
export interface CandidateScreeningCandidate { document_id: string; title: string; source: string; publication_year: number | null; }
export interface CandidateScreening { run_id: string; trust_status: string; candidate_count: number; candidates: CandidateScreeningCandidate[]; decisions: CandidateScreeningDecision[]; }
export interface CandidateScreeningResult { run_id: string; candidate_count: number; decision_counts: Record<string, number>; trust_status: string; }
export interface AutomaticExecutionStatus { state: "queued" | "running" | "succeeded" | "failed" | "cancelled"; candidate_count: number; failure_count: number; failed_sources?: string[]; planning_warning: boolean; trust_status: string; }
export interface RunStatus { run_id: string; mission_id: string; state: string; terminal?: boolean; cancellation?: "available" | "requested"; automatic_execution?: AutomaticExecutionStatus; }
export type WorkflowStageName = "intake" | "plan" | "retrieval" | "screening" | "parse" | "extraction" | "gap" | "report" | "evaluation";
export type WorkflowStageStatus = "completed" | "ready" | "waiting_human_review" | "blocked";
export interface StageContractStage { stage: WorkflowStageName; status: WorkflowStageStatus; completion_requirements: string[]; human_gate: string; expected_outputs: string[]; recovery_route: string; metrics: Record<string, number>; }
export interface StageContract { schema_version: "cosmatter.stage-contract/v1"; run_id: string; mission_id: string; trust_status: string; next_stage: WorkflowStageName | null; runtime_safety: "verified" | "attention_required"; stages: StageContractStage[]; }
export interface WorkflowDagStage { stage: WorkflowStageName; depends_on: WorkflowStageName[]; status: WorkflowStageStatus; allowed_descriptors: string[]; data_classification: string; execution_class: string; }
export interface WorkflowDag { schema_version: "cosmatter.workflow-dag/v1"; run_id: string; mission_id: string; trust_status: string; dag_id: string; max_concurrency: 1; scheduler_status: "declarative_only_no_execution_authorization"; runtime_safety: "verified" | "attention_required"; eligible_stages: WorkflowStageName[]; blocked_stage_count: number; human_review_required: boolean; stages: WorkflowDagStage[]; }
export interface ProviderOperationTelemetry { provider: "sciverse" | "mineru"; operation: string; request_count: number; successful_response_count: number; client_error_count: number; server_error_count: number; other_status_count: number; }
export const DISPATCH_OPERATIONS = ["deepseek_plan_draft", "deepseek_graph_plan_draft", "metadata_query", "citation_expansion", "mineru_submit", "mineru_poll"] as const;
export type DispatchOperation = typeof DISPATCH_OPERATIONS[number];
export interface DispatchOperationTelemetry { operation: DispatchOperation; dispatch_count: number; completed_count: number; incomplete_count: number; unknown_outcome_count: number; }
export interface CostLatencyTelemetry { provider_id: string; request_count: number; successful_request_count: number; failed_request_count: number; currency: "CNY" | "USD" | "EUR" | "not_applicable"; total_cost: number; median_latency_seconds: number; p95_latency_seconds: number; }
export interface OperationalTelemetry { schema_version: "cosmatter.operational-telemetry/v1"; run_id: string; mission_id: string; trust_status: string; provider_operations: ProviderOperationTelemetry[]; dispatch_operations: DispatchOperationTelemetry[]; cost_latency_status: "not_recorded" | "recorded" | "invalid"; cost_latency: CostLatencyTelemetry[]; }
export type OperationalReminderAction = "inspect_runtime_invariants" | "review_stage_boundary" | "complete_human_review" | "verify_dispatch_before_recovery" | "verify_provider_outcome_before_recovery" | "review_operational_todo";
export interface OperationalReminder { scope: "run" | "project_memory"; identifier: string; kind: "human_review_required" | "workflow_blocked" | "runtime_attention" | "external_dispatch_incomplete" | "external_outcome_unknown" | "expired_todo"; status: "open" | "overdue"; priority: "attention" | "review"; stage: WorkflowStageName | null; action_label: OperationalReminderAction; }
export interface ReminderBoard { schema_version: "cosmatter.project-reminder-board/v1"; trust_status: string; scheduler_status: "not_scheduled_local_observation_only"; reminder_count: number; reminders: OperationalReminder[]; }
const REMINDER_RULES: Record<string, { scope: "run" | "project_memory"; action: OperationalReminderAction; requiresStage: boolean }> = {
  human_review_required: { scope: "run", action: "complete_human_review", requiresStage: true },
  workflow_blocked: { scope: "run", action: "review_stage_boundary", requiresStage: true },
  runtime_attention: { scope: "run", action: "inspect_runtime_invariants", requiresStage: false },
  external_dispatch_incomplete: { scope: "run", action: "verify_dispatch_before_recovery", requiresStage: false },
  external_outcome_unknown: { scope: "run", action: "verify_provider_outcome_before_recovery", requiresStage: false },
  expired_todo: { scope: "project_memory", action: "review_operational_todo", requiresStage: false },
};
const REMINDER_STAGES = new Set<string>(["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"]);
const LOCAL_API_PROVIDER_KEYS = ["deepseek", "sciverse", "mineru", "openalex", "crossref", "crossref_polite_contact"] as const;
const exactObjectKeys = (value: unknown, keys: readonly string[]) => Boolean(value && typeof value === "object" && !Array.isArray(value) && (() => { const actual = Object.keys(value as Record<string, unknown>); return actual.length === keys.length && actual.every((key) => keys.includes(key)); })());

/** Accept only the fixed, presence-only local API capability surface. */
export function isLocalApiStatus(value: unknown): value is LocalApiStatus {
  if (!exactObjectKeys(value, ["api_mode", "providers"])) return false;
  const status = value as Record<string, unknown>;
  return status.api_mode === "loopback_only" && exactObjectKeys(status.providers, LOCAL_API_PROVIDER_KEYS)
    && LOCAL_API_PROVIDER_KEYS.every((key) => typeof (status.providers as Record<string, unknown>)[key] === "boolean");
}

/** Treat a malformed reminder projection as unavailable instead of actionable. */
export function isReminderBoard(value: unknown): value is ReminderBoard {
  if (!exactObjectKeys(value, ["schema_version", "trust_status", "scheduler_status", "reminder_count", "reminders"])) return false;
  const board = value as Record<string, unknown>;
  if (board.schema_version !== "cosmatter.project-reminder-board/v1" || board.trust_status !== "loopback_operational_reminders_not_schedule_or_execution_authorization" || board.scheduler_status !== "not_scheduled_local_observation_only" || !Number.isInteger(board.reminder_count) || (board.reminder_count as number) < 0 || (board.reminder_count as number) > 100 || !Array.isArray(board.reminders) || board.reminders.length !== board.reminder_count) return false;
  const seen = new Set<string>();
  return board.reminders.every((raw) => {
    if (!exactObjectKeys(raw, ["scope", "identifier", "kind", "status", "priority", "stage", "action_label"])) return false;
    const item = raw as Record<string, unknown>;
    const rule = REMINDER_RULES[item.kind as string];
    if (!(["run", "project_memory"] as string[]).includes(item.scope as string) || typeof item.identifier !== "string" || !item.identifier || item.identifier.length > 80 || !rule || !(["open", "overdue"] as string[]).includes(item.status as string) || !(["attention", "review"] as string[]).includes(item.priority as string) || item.stage !== null && !REMINDER_STAGES.has(item.stage as string) || item.scope !== rule.scope || item.action_label !== rule.action || (item.stage !== null) !== rule.requiresStage) return false;
    const key = `${item.scope}:${item.identifier}:${item.kind}:${item.stage ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
export interface HarnessAuthorization { mission_id: string; plugin_authorization_decisions: Array<{ plugin_id: string; permitted: boolean }>; trust_status: "authorization_checked_before_automatic_dispatch"; }
export interface AutoMissionResult extends LiveMission { candidate_count: number; failures: string[]; status: RunStatus; trust_status: string; harness_authorization?: HarnessAuthorization; }
export const PDF_TASK_STATES = ["waiting-file", "uploading", "pending", "converting", "running", "done", "failed"] as const;
export type PdfTaskState = typeof PDF_TASK_STATES[number];
export const PDF_DOI_STATUSES = ["pending", "resolved", "needs_human_doi", "human_confirmed"] as const;
export type PdfDoiStatus = typeof PDF_DOI_STATUSES[number];
export interface PdfRunResult extends LiveMission { document_id: string; candidate_document_id?: string | null; doi_status: PdfDoiStatus; state: PdfTaskState; }
export interface PdfTaskStatus { document_id: string; candidate_document_id?: string | null; audit_document_id: string; audit_state: "pending" | "running" | "done" | "failed"; file_name: string; state: PdfTaskState; doi: string | null; doi_status: PdfDoiStatus; markdown_ready: boolean; source_map_review_status: "absent" | "recorded" | "invalid"; source_map_segment_count: number; error?: string | null; trust_status: string; }
export function createAutomaticMission(payload: { question: string; material: string; property: string; scope: string; sources: RetrievalSource[] }): Promise<AutoMissionResult> { return jsonPost<AutoMissionResult>("./api/missions/auto", { ...payload, consent: true }); }
export function getRunStatus(runId: string): Promise<RunStatus> { return request<RunStatus>(`./api/runs/${encodeURIComponent(runId)}/status`); }
export function getStageContract(runId: string): Promise<StageContract> { return request<StageContract>(`./api/runs/${encodeURIComponent(runId)}/stage-contract`); }
export function getWorkflowDag(runId: string): Promise<WorkflowDag> { return request<WorkflowDag>(`./api/runs/${encodeURIComponent(runId)}/workflow-dag`); }
export function getOperationalTelemetry(runId: string): Promise<OperationalTelemetry> { return request<OperationalTelemetry>(`./api/runs/${encodeURIComponent(runId)}/operational-telemetry`); }
export function getReminderBoard(): Promise<ReminderBoard> { return request<ReminderBoard>("./api/reminder-board"); }
export function getCandidateScreening(runId: string): Promise<CandidateScreening> { return request<CandidateScreening>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`); }
export function recordCandidateScreening(runId: string, decisions: CandidateScreeningDecision[]): Promise<CandidateScreeningResult> { return jsonPost<CandidateScreeningResult>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`, { decisions }); }
export function cancelRun(runId: string): Promise<RunStatus> { return jsonPost<RunStatus>(`./api/runs/${encodeURIComponent(runId)}/cancel`, {}); }
export function createPdfRun(file: File, mission: { missionId?: string; question: string; material: string; property: string; scope: string }, candidateTarget?: { runId: string; documentId: string }): Promise<PdfRunResult> { const form = new FormData(); form.append("payload", JSON.stringify(candidateTarget ? { run_id: candidateTarget.runId, candidate_document_id: candidateTarget.documentId, consent: true } : { ...mission, run_id: mission.missionId, consent: true })); form.append("file", file, file.name); return request<PdfRunResult>("./api/pdf-runs", { method: "POST", body: form }); }
export interface PdfTaskRegistry { run_id: string; tasks: PdfTaskStatus[]; trust_status: "private_pdf_task_registry_metadata_only"; }
const PDF_TASK_KEYS = ["document_id", "candidate_document_id", "audit_document_id", "audit_state", "file_name", "state", "doi", "doi_status", "markdown_ready", "source_map_review_status", "source_map_segment_count", "error", "trust_status"] as const;
const PDF_REGISTRY_KEYS = ["run_id", "tasks", "trust_status"] as const;
const boundedString = (value: unknown, maximum: number) => typeof value === "string" && value.trim().length > 0 && value.length <= maximum;

/** Parse only the fixed metadata projection; private PDF and Markdown never cross this boundary. */
export function isPdfTaskStatus(value: unknown): value is PdfTaskStatus {
  if (!exactObjectKeys(value, PDF_TASK_KEYS)) return false;
  const task = value as Record<string, unknown>;
  const state = task.state;
  const doiStatus = task.doi_status;
  if (!boundedString(task.document_id, 255) || task.candidate_document_id !== null && !boundedString(task.candidate_document_id, 255)
    || !boundedString(task.audit_document_id, 255) || !boundedString(task.file_name, 240)
    || !(PDF_TASK_STATES as readonly string[]).includes(state as string) || !(PDF_DOI_STATUSES as readonly string[]).includes(doiStatus as string)
    || !["pending", "running", "done", "failed"].includes(task.audit_state as string)
    || typeof task.markdown_ready !== "boolean" || !["absent", "recorded", "invalid"].includes(task.source_map_review_status as string)
    || !Number.isInteger(task.source_map_segment_count) || (task.source_map_segment_count as number) < 0 || (task.source_map_segment_count as number) > 100
    || task.doi !== null && !boundedString(task.doi, 255) || task.error !== null && !boundedString(task.error, 300)
    || task.trust_status !== "private_markdown_outside_run_not_scientific_evidence") return false;
  const completed = state === "done";
  if (task.markdown_ready !== completed || (completed && task.audit_state !== "done") || (!completed && (task.doi !== null || doiStatus !== "pending"))) return false;
  return task.source_map_review_status !== "recorded" || Boolean(task.markdown_ready && (task.source_map_segment_count as number) > 0);
}

export function isPdfTaskRegistry(value: unknown, runId?: string): value is PdfTaskRegistry {
  if (!exactObjectKeys(value, PDF_REGISTRY_KEYS)) return false;
  const registry = value as Record<string, unknown>;
  if (!boundedString(registry.run_id, 120) || runId !== undefined && registry.run_id !== runId || registry.trust_status !== "private_pdf_task_registry_metadata_only" || !Array.isArray(registry.tasks) || registry.tasks.length > 12) return false;
  const documentIds = new Set<string>();
  return registry.tasks.every((task) => isPdfTaskStatus(task) && !documentIds.has(task.document_id) && Boolean(documentIds.add(task.document_id)));
}
export async function getPdfTasks(runId: string): Promise<PdfTaskRegistry> { const registry = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/pdf/tasks`); if (!isPdfTaskRegistry(registry, runId)) throw new LocalApiRequestError("transport"); return registry; }
export async function getPdfStatus(runId: string, documentId: string): Promise<PdfTaskStatus> { const task = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/status`); if (!isPdfTaskStatus(task)) throw new LocalApiRequestError("transport"); return task; }
export function privateMarkdownUrl(runId: string, documentId: string): string { return `./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/markdown`; }
export interface PrivateSourceMapSegment { locator: string; kind: "paragraph" | "table" | "formula" | "figure_caption"; quote: string; }
export interface RecordedSourceMapSegment { segment_id: string; locator: string; kind: PrivateSourceMapSegment["kind"]; }
export interface SourceMapRecordResult { run_id: string; document_id: string; segment_count: number; segments: RecordedSourceMapSegment[]; trust_status: string; }
export type MaterialFactCategory = "composition" | "structure" | "property" | "processing" | "experimental_condition" | "simulation_method";
export interface HumanMaterialFactInput { fact_id: string; segment_id: string; category: MaterialFactCategory; name: string; value: string | number | null; unit: string | null; normalized_value: string | number | null; normalized_unit: string | null; qualifiers: Record<string, string | number | null>; }
export function getPdfSourceMapContext(runId: string, documentId: string): Promise<SourceMapRecordResult> { return request<SourceMapRecordResult>(`./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/source-map`); }
export function recordPdfSourceMap(runId: string, documentId: string, segments: PrivateSourceMapSegment[]): Promise<SourceMapRecordResult> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/pdf/source-map`, { document_id: documentId, human_confirmed: true, segments }); }
export function recordPdfMaterialFacts(runId: string, documentId: string, facts: HumanMaterialFactInput[]): Promise<{ run_id: string; document_id: string; fact_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/pdf/material-facts`, { document_id: documentId, human_confirmed: true, facts }); }
export interface HumanEvidenceReviewInput { segment_id: string; claim: string; stance: "support" | "contradict" | "context"; conditions: Record<string, string | number | null>; reviewer_confidence: number; }
export interface EvidenceReviewResult { run_id: string; evidence_id: string; document_id: string; locator: string; review_status: "accepted"; trust_status: string; }
export function recordPdfEvidenceCard(runId: string, documentId: string, input: HumanEvidenceReviewInput): Promise<EvidenceReviewResult> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/pdf/evidence-card`, { document_id: documentId, human_confirmed: true, ...input }); }
export function confirmPdfDoi(runId: string, documentId: string, doi: string): Promise<PdfTaskStatus> { return jsonPost<PdfTaskStatus>(`./api/runs/${encodeURIComponent(runId)}/pdf/doi`, { document_id: documentId, doi, human_confirmed: true }); }
export function expandAuthorizedPdfCitations(runId: string, documentId: string, dshCallId: string): Promise<{ node_count: number; edge_count: number; failure_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/authorized-citation-expansion`, { document_id: documentId, authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"], actor: "human_bibliography_review", dsh_call_id: dshCallId }); }
export function diagnoseConditions(runId: string): Promise<{ run_id: string; matrix_row_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/condition-diagnostics`, {}); }
export function generateGapCandidates(runId: string): Promise<{ run_id: string; candidate_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/gap-candidates`, {}); }
export function importRunPackage(packagePayload: unknown): Promise<{ run_id: string; mission_id: string; next_stage: string | null; trust_status: "allowlisted_continuation_package" }> { return jsonPost("./api/runs/import", { package: packagePayload }); }
