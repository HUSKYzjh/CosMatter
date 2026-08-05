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
export function executeApprovedQuery(runId: string, queryIndex: number, sources: RetrievalSource[]): Promise<SearchResult> { return jsonPost<SearchResult>(`./api/runs/${encodeURIComponent(runId)}/execute-query`, { query_index: queryIndex, counter: false, sources }); }
export function fetchLiveUiBundle(runId: string): Promise<unknown> { return request<unknown>(`./api/runs/${encodeURIComponent(runId)}/ui`); }