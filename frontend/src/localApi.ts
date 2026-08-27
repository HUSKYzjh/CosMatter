export interface LocalApiStatus {
  api_mode: "loopback_only";
  providers: Record<string, boolean>;
}

export interface LiveMission { run_id: string; mission_id: string; fleet_type: string; mission_type: string; state: string; }
export interface DraftPlan { run_id: string; trust_status: "untrusted_draft"; content: string; }
export interface ApprovedPlan { run_id: string; plan_id: string; queries: string[]; counter_queries: string[]; }
export interface SearchResult { run_id: string; candidate_count: number; sources: string[]; source_counts: Record<string, number>; }
export type RetrievalSource = "sciverse" | "openalex" | "crossref";

export function localApiEnabled(): boolean { return new URLSearchParams(window.location.search).get("api") === "local"; }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null && "error" in payload && typeof payload.error === "string" ? payload.error : `Local API request failed (${response.status}).`;
    throw new Error(message);
  }
  return payload as T;
}
function jsonPost<T>(path: string, payload: unknown): Promise<T> { return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }
export function getLocalApiStatus(): Promise<LocalApiStatus> { return request<LocalApiStatus>("./api/status"); }
export function createLiveMission(payload: { question: string; material: string; property: string; scope: string }): Promise<LiveMission> { return jsonPost<LiveMission>("./api/missions", payload); }
export function draftLivePlan(runId: string): Promise<DraftPlan> { return jsonPost<DraftPlan>(`./api/runs/${encodeURIComponent(runId)}/draft-plan`, {}); }
export function approveLivePlan(runId: string, plan: unknown): Promise<ApprovedPlan> { return jsonPost<ApprovedPlan>(`./api/runs/${encodeURIComponent(runId)}/approve-plan`, plan); }
export function executeApprovedQuery(runId: string, queryIndex: number, sources: RetrievalSource[], counter = false): Promise<SearchResult> { return jsonPost<SearchResult>(`./api/runs/${encodeURIComponent(runId)}/execute-query`, { query_index: queryIndex, counter, sources }); }
export function fetchLiveUiBundle(runId: string): Promise<unknown> { return request<unknown>(`./api/runs/${encodeURIComponent(runId)}/ui`); }
export interface QuestionCandidate { id: string; question: string; material: string; property: string; scope: string; kind: "survey" | "contrast" | "mechanism"; }
export async function requestQuestionCandidates(question: string): Promise<QuestionCandidate[]> {
  const result = await jsonPost<{ trust_status: string; candidates: QuestionCandidate[] }>("./api/question-candidates", { question });
  return result.candidates;
}
export interface CandidateScreeningDecision { document_id: string; decision: string; reason_codes: string[]; }
export interface CandidateScreeningCandidate { document_id: string; title: string; source: string; publication_year: number | null; }
export interface CandidateScreening { run_id: string; trust_status: string; candidate_count: number; candidates: CandidateScreeningCandidate[]; decisions: CandidateScreeningDecision[]; }
export interface CandidateScreeningResult { run_id: string; candidate_count: number; decision_counts: Record<string, number>; trust_status: string; }
export interface AutomaticExecutionStatus { state: "queued" | "running" | "succeeded" | "failed" | "cancelled"; candidate_count: number; failure_count: number; failed_sources?: string[]; planning_warning: boolean; trust_status: string; }
export interface RunStatus { run_id: string; state: string; terminal?: boolean; cancellation?: "available" | "requested"; automatic_execution?: AutomaticExecutionStatus; }
export interface HarnessAuthorization { mission_id: string; plugin_authorization_decisions: Array<{ plugin_id: string; permitted: boolean }>; trust_status: "authorization_checked_before_automatic_dispatch"; }
export interface AutoMissionResult extends LiveMission { candidate_count: number; failures: string[]; status: RunStatus; trust_status: string; harness_authorization?: HarnessAuthorization; }
export interface PdfRunResult extends LiveMission { document_id: string; candidate_document_id?: string | null; doi_status: string; state: string; }
export interface PdfTaskStatus { document_id: string; candidate_document_id?: string | null; audit_document_id: string; audit_state: "pending" | "running" | "done" | "failed"; file_name: string; state: string; doi: string | null; doi_status: string; markdown_ready: boolean; source_map_review_status: "absent" | "recorded" | "invalid"; source_map_segment_count: number; error?: string; trust_status: string; }
export function createAutomaticMission(payload: { question: string; material: string; property: string; scope: string; sources: RetrievalSource[] }): Promise<AutoMissionResult> { return jsonPost<AutoMissionResult>("./api/missions/auto", { ...payload, consent: true }); }
export function getRunStatus(runId: string): Promise<RunStatus> { return request<RunStatus>(`./api/runs/${encodeURIComponent(runId)}/status`); }
export function getCandidateScreening(runId: string): Promise<CandidateScreening> { return request<CandidateScreening>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`); }
export function recordCandidateScreening(runId: string, decisions: CandidateScreeningDecision[]): Promise<CandidateScreeningResult> { return jsonPost<CandidateScreeningResult>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`, { decisions }); }
export function cancelRun(runId: string): Promise<RunStatus> { return jsonPost<RunStatus>(`./api/runs/${encodeURIComponent(runId)}/cancel`, {}); }
export function createPdfRun(file: File, mission: { question: string; material: string; property: string; scope: string }, candidateTarget?: { runId: string; documentId: string }): Promise<PdfRunResult> { const form = new FormData(); form.append("payload", JSON.stringify(candidateTarget ? { run_id: candidateTarget.runId, candidate_document_id: candidateTarget.documentId, consent: true } : { ...mission, consent: true })); form.append("file", file, file.name); return request<PdfRunResult>("./api/pdf-runs", { method: "POST", body: form }); }
export interface PdfTaskRegistry { run_id: string; tasks: PdfTaskStatus[]; trust_status: string; }
export function getPdfTasks(runId: string): Promise<PdfTaskRegistry> { return request<PdfTaskRegistry>(`./api/runs/${encodeURIComponent(runId)}/pdf/tasks`); }
export function getPdfStatus(runId: string, documentId: string): Promise<PdfTaskStatus> { return request<PdfTaskStatus>(`./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/status`); }
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
export function expandPdfCitations(runId: string, documentId: string): Promise<{ node_count: number; edge_count: number; failure_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/citations`, {}); }
export function diagnoseConditions(runId: string): Promise<{ run_id: string; matrix_row_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/condition-diagnostics`, {}); }
export function generateGapCandidates(runId: string): Promise<{ run_id: string; candidate_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/gap-candidates`, {}); }
export function importRunPackage(packagePayload: unknown): Promise<{ run_id: string; next_stage: string }> { return jsonPost("./api/runs/import", { package: packagePayload }); }
