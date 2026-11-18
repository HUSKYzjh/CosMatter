import { packages as dshBundles } from "../../plugins/dsh-plugin-group.json";
import { isLocalRunId } from "./liveRunIdentity";

export interface LocalApiStatus {
  api_mode: "loopback_only";
  providers: Record<string, boolean>;
  operation_contracts: OperationParameterContracts;
}
export interface IntegerParameterContract { type: "integer"; minimum: number; maximum?: number; default: number; }
export interface SciverseReadContentParameterSchema { type: "object"; additionalProperties: false; required: ["offset", "limit"]; properties: { offset: IntegerParameterContract; limit: IntegerParameterContract; }; }
export interface OperationParameterContracts { schema_version: "cosmatter.operation-parameter-contracts/v1"; trust_status: "static_parameter_contracts_not_execution_authorization"; operations: { sciverse_read_content: SciverseReadContentParameterSchema; }; }
export interface FacilityContractManifest { facility_type: string; fleet_types: string[]; input_schema: string[]; output_schema: string[]; allowed_descriptors: string[]; failure_modes: string[]; human_review_required: boolean; execution_boundary: "static_contract_only_not_execution_authorization"; }
export interface FacilityContractCatalogue { schema_version: "cosmatter.facility-contract-catalogue/v1"; trust_status: "static_facility_contracts_not_execution_or_evidence_acceptance"; contracts: FacilityContractManifest[]; }
export type FacilityCatalogueHealth = "disabled" | "loading" | "ready" | "unavailable";
export interface HarnessPluginDescriptor {
  plugin_id: string;
  title: string;
  domain: string;
  entrypoint: string;
  api_version: "2.0";
  capabilities: string[];
  data_classification: string;
  automation_class: "local_safe" | "external_authorized" | "human_gate";
  required_authorizations: string[];
  requires_human_review: boolean;
  contract: { input_schema: string; output_schema: string; execution_mode: string; lifecycle: string };
  execution_boundary: string;
}
export interface HarnessPluginCatalogue {
  catalogue_api_version: "2.0";
  plugins: HarnessPluginDescriptor[];
  trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance";
}
export type HarnessCatalogueHealth = "disabled" | "loading" | "ready" | "unavailable";
export type DshProfileInstallationState = "installed" | "partial" | "not_installed" | "unavailable";
export interface DshProfilePackageStatus {
  package: string;
  dependency_kind: "local_link" | "registry_reference" | "remote_reference" | "absent";
  install_status: "verified" | "missing_bundle" | "invalid_bundle" | "not_declared";
}
export interface DshCompositionCheck {
  schema_version: "cosmatter.dsh-composition-check/v1";
  checked_at: string;
  dsh_version: string;
  bundles: string[];
  matches_local_files: boolean;
}
export interface DshToolRegistryCheck extends Omit<DshCompositionCheck, "schema_version"> {
  schema_version: "cosmatter.dsh-tool-registry-check/v1";
  registered_tools: string[];
}
export interface DshProfileStatus {
  schema_version: "cosmatter.dsh-profile-status/v2";
  profile_name: "tui";
  installation_state: DshProfileInstallationState;
  expected_bundle_count: 7;
  declared_bundle_count: number;
  installed_bundle_count: number;
  packages: DshProfilePackageStatus[];
  composition_status: "not_checked_by_http_api";
  composition_check?: DshCompositionCheck;
  tool_registry_check?: DshToolRegistryCheck;
  trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution";
}
export type DshProfileHealth = "disabled" | "loading" | "ready" | "unavailable";

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

/** Validate the non-executing Harness contract catalogue before displaying it. */
export function isHarnessPluginCatalogue(value: unknown): value is HarnessPluginCatalogue {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const catalogue = value as Record<string, unknown>;
  if (catalogue.catalogue_api_version !== "2.0"
    || catalogue.trust_status !== "static_catalogue_not_plugin_execution_or_evidence_acceptance"
    || !Array.isArray(catalogue.plugins)
    || catalogue.plugins.length < 1
    || catalogue.plugins.length > 64) return false;
  const pluginIds = new Set<string>();
  return catalogue.plugins.every((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const plugin = item as Record<string, unknown>;
    if (typeof plugin.plugin_id !== "string" || !plugin.plugin_id || plugin.plugin_id.length > 120 || pluginIds.has(plugin.plugin_id)) return false;
    pluginIds.add(plugin.plugin_id);
    const contract = plugin.contract;
    if (!contract || typeof contract !== "object" || Array.isArray(contract)) return false;
    const contractRecord = contract as Record<string, unknown>;
    return typeof plugin.title === "string" && plugin.title.length > 0 && plugin.title.length <= 120
      && typeof plugin.domain === "string" && plugin.domain.length > 0 && plugin.domain.length <= 80
      && typeof plugin.entrypoint === "string" && plugin.entrypoint.length > 0 && plugin.entrypoint.length <= 240
      && plugin.api_version === "2.0"
      && stringList(plugin.capabilities, 16)
      && typeof plugin.data_classification === "string" && plugin.data_classification.length > 0 && plugin.data_classification.length <= 80
      && ["local_safe", "external_authorized", "human_gate"].includes(String(plugin.automation_class))
      && Array.isArray(plugin.required_authorizations) && plugin.required_authorizations.length <= 12
      && plugin.required_authorizations.every((authorization) => typeof authorization === "string" && authorization.length > 0 && authorization.length <= 120)
      && typeof plugin.requires_human_review === "boolean"
      && typeof contractRecord.input_schema === "string" && contractRecord.input_schema.length > 0 && contractRecord.input_schema.length <= 160
      && typeof contractRecord.output_schema === "string" && contractRecord.output_schema.length > 0 && contractRecord.output_schema.length <= 160
      && typeof contractRecord.execution_mode === "string" && contractRecord.execution_mode.length > 0 && contractRecord.execution_mode.length <= 80
      && typeof contractRecord.lifecycle === "string" && contractRecord.lifecycle.length > 0 && contractRecord.lifecycle.length <= 240
      && typeof plugin.execution_boundary === "string" && plugin.execution_boundary.length > 0 && plugin.execution_boundary.length <= 360;
  });
}

export interface LiveMission { run_id: string; mission_id: string; fleet_type: string; mission_type: string; state: string; }
export interface RecentLocalRun {
  run_id: string;
  material: string;
  property: string;
  updated_at: string;
  stopped: boolean;
}
export interface DraftPlan { run_id: string; trust_status: "untrusted_draft"; content: string; }
export interface ApprovedPlan { run_id: string; plan_id: string; queries: string[]; counter_queries: string[]; query_track_counts?: { exact_material: number; mechanism_analogue: number; algorithm: number }; query_track_planning_status?: "approved_independent_tracks" | "legacy_unclassified"; }
export interface SearchResult { run_id: string; candidate_count: number; sources: string[]; source_counts: Record<string, number>; }
export type RetrievalSource = "sciverse" | "openalex" | "crossref";

export function localApiEnabled(): boolean { return new URLSearchParams(window.location.search).get("api") === "local"; }

export type LocalApiRequestFailure = "read_timeout" | "write_outcome_unknown" | "transport";

/** Safe, display-neutral request failure classification for the loopback API. */
export class LocalApiRequestError extends Error {
  readonly failure: LocalApiRequestFailure;
  constructor(failure: LocalApiRequestFailure, readonly httpStatus?: number) {
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
  try {
    const response = await fetch(path, { ...init, cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      // Provider and filesystem details are untrusted display data.
      throw new LocalApiRequestError(localApiHttpFailure(init?.method, response.status), response.status);
    }
    return await response.json().catch((error) => {
      if (controller.signal.aborted) throw error;
      return {};
    }) as T;
  } catch (error) {
    if (error instanceof LocalApiRequestError) throw error;
    throw new LocalApiRequestError(timedOut ? localApiTimeoutFailure(init?.method) : "transport");
  } finally {
    window.clearTimeout(timeout);
  }
}
function jsonPost<T>(path: string, payload: unknown): Promise<T> { return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }
export async function getRecentLocalRuns(): Promise<RecentLocalRun[]> {
  const payload = await request<unknown>("./api/recent-runs", { credentials: "omit", redirect: "error" });
  if (!exactObjectKeys(payload, ["schema_version", "runs"])) throw new LocalApiRequestError("transport");
  const { schema_version, runs } = payload as { schema_version: unknown; runs: unknown };
  if (schema_version !== "cosmatter.recent-local-runs/v1" || !Array.isArray(runs) || runs.length > 12
    || !runs.every(isRecentLocalRun) || new Set(runs.map(({ run_id }) => run_id)).size !== runs.length) {
    throw new LocalApiRequestError("transport");
  }
  return runs;
}

function isRecentLocalRun(value: unknown): value is RecentLocalRun {
  if (!exactObjectKeys(value, ["run_id", "material", "property", "updated_at", "stopped"])) return false;
  const { run_id, material, property, updated_at, stopped } = value as Record<string, unknown>;
  return typeof run_id === "string" && isLocalRunId(run_id)
    && typeof material === "string" && material.trim().length > 0 && material.length <= 240
    && typeof property === "string" && property.trim().length > 0 && property.length <= 240
    && typeof stopped === "boolean" && typeof updated_at === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(updated_at) && Number.isFinite(Date.parse(updated_at))
    && new Date(updated_at).toISOString() === updated_at.replace("Z", ".000Z");
}
export function getLocalApiStatus(): Promise<LocalApiStatus> { return request<LocalApiStatus>("./api/status"); }
export function getFacilityContractCatalogue(): Promise<FacilityContractCatalogue> { return request<FacilityContractCatalogue>("./api/facility-contracts"); }
export function getHarnessPluginCatalogue(): Promise<HarnessPluginCatalogue> { return request<HarnessPluginCatalogue>("./api/plugins"); }
export function getDshProfileStatus(): Promise<DshProfileStatus> { return request<DshProfileStatus>("./api/dsh-profile"); }
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
export interface CandidateScreening { run_id: string; trust_status: string; candidate_count: number; checklist_revision?: string; candidates: CandidateScreeningCandidate[]; decisions: CandidateScreeningDecision[]; }
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
export interface ValidationRejectionTelemetry { command: "sciverse_read_context"; reason_code: "invalid_integer" | "offset_below_minimum" | "limit_below_minimum" | "limit_above_maximum"; rejection_count: number; }
export interface CostLatencyTelemetry { provider_id: string; request_count: number; successful_request_count: number; failed_request_count: number; currency: "CNY" | "USD" | "EUR" | "not_applicable"; total_cost: number; median_latency_seconds: number; p95_latency_seconds: number; }
export interface OperationalTelemetry { schema_version: "cosmatter.operational-telemetry/v2"; run_id: string; mission_id: string; trust_status: string; provider_operations: ProviderOperationTelemetry[]; dispatch_operations: DispatchOperationTelemetry[]; validation_rejections: ValidationRejectionTelemetry[]; cost_latency_status: "not_recorded" | "recorded" | "invalid"; cost_latency: CostLatencyTelemetry[]; }
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
const DSH_PACKAGE_NAMES = dshBundles.map((bundle) => bundle.package);
const exactObjectKeys = (value: unknown, keys: readonly string[]) => Boolean(value && typeof value === "object" && !Array.isArray(value) && (() => { const actual = Object.keys(value as Record<string, unknown>); return actual.length === keys.length && actual.every((key) => keys.includes(key)); })());

/** Accept the redacted fixed-profile snapshot only when the package states agree. */
export function isDshProfileStatus(value: unknown): value is DshProfileStatus {
  const keys = ["schema_version", "profile_name", "installation_state", "expected_bundle_count", "declared_bundle_count", "installed_bundle_count", "packages", "composition_status", "trust_status"];
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const status = value as Record<string, unknown>;
  const optional = ["composition_check", "tool_registry_check"].filter((key) => Object.hasOwn(status, key));
  if (!exactObjectKeys(status, [...keys, ...optional])) return false;
  if (status.schema_version !== "cosmatter.dsh-profile-status/v2"
    || status.profile_name !== "tui"
    || status.expected_bundle_count !== DSH_PACKAGE_NAMES.length
    || status.composition_status !== "not_checked_by_http_api"
    || status.trust_status !== "local_installation_snapshot_not_profile_boot_or_plugin_execution"
    || (optional.includes("composition_check") && !isDshCompositionCheck(status.composition_check))
    || (optional.includes("tool_registry_check") && !isDshToolRegistryCheck(status.tool_registry_check))
    || !Array.isArray(status.packages)
    || status.packages.length !== DSH_PACKAGE_NAMES.length) return false;
  const packagesAreValid = status.packages.every((item, index) => {
    if (!exactObjectKeys(item, ["package", "dependency_kind", "install_status"])) return false;
    const packageStatus = item as Record<string, unknown>;
    if (packageStatus.package !== DSH_PACKAGE_NAMES[index]) return false;
    if (packageStatus.dependency_kind === "absent") return packageStatus.install_status === "not_declared";
    return ["local_link", "registry_reference", "remote_reference"].some((kind) => kind === packageStatus.dependency_kind)
      && ["verified", "missing_bundle", "invalid_bundle"].some((state) => state === packageStatus.install_status);
  });
  if (!packagesAreValid) return false;
  const declaredCount = status.packages.filter((item) => item.dependency_kind !== "absent").length;
  const installedCount = status.packages.filter((item) => item.install_status === "verified").length;
  const installationState = installedCount === DSH_PACKAGE_NAMES.length ? "installed" : installedCount ? "partial" : "not_installed";
  return declaredCount === status.declared_bundle_count
    && installedCount === status.installed_bundle_count
    && (status.installation_state === installationState || (status.installation_state === "unavailable" && declaredCount === 0));
}

function isDshCompositionCheck(value: unknown): value is DshCompositionCheck {
  if (!exactObjectKeys(value, ["schema_version", "checked_at", "dsh_version", "bundles", "matches_local_files"])) return false;
  const check = value as Record<string, unknown>;
  return check.schema_version === "cosmatter.dsh-composition-check/v1" && isDshCheckFields(check);
}

function isDshToolRegistryCheck(value: unknown): value is DshToolRegistryCheck {
  if (!exactObjectKeys(value, ["schema_version", "checked_at", "dsh_version", "bundles", "matches_local_files", "registered_tools"])) return false;
  const check = value as Record<string, unknown>;
  if (check.schema_version !== "cosmatter.dsh-tool-registry-check/v1" || !isDshCheckFields(check) || !check.bundles.length || !Array.isArray(check.registered_tools)) return false;
  const tools = check.registered_tools;
  const expected = dshBundles.filter(({ package: name }) => check.bundles.includes(name)).flatMap(({ tools }) => tools).sort();
  const filtered = expected.filter((name) => tools.includes(name));
  return filtered.length === tools.length && filtered.every((name, index) => name === tools[index]);
}

function isDshCheckFields(check: Record<string, unknown>): check is Record<string, unknown> & Pick<DshCompositionCheck, "bundles" | "checked_at" | "dsh_version" | "matches_local_files"> {
  if (typeof check.checked_at !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(check.checked_at)
    || typeof check.dsh_version !== "string"
    || !/^\d{1,4}\.\d{1,4}\.\d{1,4}(?:-[a-z0-9.]{1,24})?$/.test(check.dsh_version)
    || typeof check.matches_local_files !== "boolean"
    || !Array.isArray(check.bundles) || check.bundles.length > DSH_PACKAGE_NAMES.length) return false;
  const timestamp = new Date(check.checked_at);
  if (!Number.isFinite(timestamp.getTime()) || timestamp.toISOString() !== check.checked_at.replace("Z", ".000Z")) return false;
  const bundles = check.bundles;
  const ordered = DSH_PACKAGE_NAMES.filter((name) => bundles.includes(name));
  return ordered.length === bundles.length && ordered.every((name, index) => name === bundles[index]);
}

/** Accept only the fixed, presence-only local API capability surface. */
export function isLocalApiStatus(value: unknown): value is LocalApiStatus {
  if (!exactObjectKeys(value, ["api_mode", "providers", "operation_contracts"])) return false;
  const status = value as Record<string, unknown>;
  return status.api_mode === "loopback_only" && exactObjectKeys(status.providers, LOCAL_API_PROVIDER_KEYS)
    && LOCAL_API_PROVIDER_KEYS.every((key) => typeof (status.providers as Record<string, unknown>)[key] === "boolean")
    && isOperationParameterContracts(status.operation_contracts);
}

/** Validate static parameter discovery before displaying or applying a bound. */
export function isOperationParameterContracts(value: unknown): value is OperationParameterContracts {
  if (!exactObjectKeys(value, ["schema_version", "trust_status", "operations"])) return false;
  const contract = value as Record<string, unknown>;
  if (contract.schema_version !== "cosmatter.operation-parameter-contracts/v1" || contract.trust_status !== "static_parameter_contracts_not_execution_authorization" || !exactObjectKeys(contract.operations, ["sciverse_read_content"])) return false;
  const read = (contract.operations as Record<string, unknown>).sciverse_read_content;
  if (!exactObjectKeys(read, ["type", "additionalProperties", "required", "properties"])) return false;
  const schema = read as Record<string, unknown>;
  if (schema.type !== "object" || schema.additionalProperties !== false || JSON.stringify(schema.required) !== JSON.stringify(["offset", "limit"]) || !exactObjectKeys(schema.properties, ["offset", "limit"])) return false;
  const properties = schema.properties as Record<string, unknown>;
  if (!exactObjectKeys(properties.offset, ["type", "minimum", "default"]) || !exactObjectKeys(properties.limit, ["type", "minimum", "maximum", "default"])) return false;
  const offset = properties.offset as Record<string, unknown>;
  const limit = properties.limit as Record<string, unknown>;
  return offset.type === "integer" && offset.minimum === 0 && offset.default === 0
    && limit.type === "integer" && limit.minimum === 200 && limit.maximum === 4000 && limit.default === 2000;
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
export interface SavedSourceParseTask {
  document_id: string;
  state: "pending" | "running" | "done" | "failed";
  markdown_ready?: boolean;
  can_link_markdown?: boolean;
  source_map_segment_count?: number;
}
export type SavedSourceParseHealth = "idle" | "loading" | "ready" | "unavailable";
export function createAutomaticMission(payload: { question: string; material: string; property: string; scope: string; sources: RetrievalSource[] }): Promise<AutoMissionResult> { return jsonPost<AutoMissionResult>("./api/missions/auto", { ...payload, consent: true }); }
export function getRunStatus(runId: string): Promise<RunStatus> { return request<RunStatus>(`./api/runs/${encodeURIComponent(runId)}/status`); }
export function getStageContract(runId: string, timeoutMs?: number): Promise<StageContract> {
  return request<StageContract>(`./api/runs/${encodeURIComponent(runId)}/stage-contract`, undefined, timeoutMs);
}
export function getWorkflowDag(runId: string): Promise<WorkflowDag> { return request<WorkflowDag>(`./api/runs/${encodeURIComponent(runId)}/workflow-dag`); }
export function getOperationalTelemetry(runId: string): Promise<OperationalTelemetry> { return request<OperationalTelemetry>(`./api/runs/${encodeURIComponent(runId)}/operational-telemetry`); }
export function getReminderBoard(): Promise<ReminderBoard> { return request<ReminderBoard>("./api/reminder-board"); }
export function getCandidateScreening(runId: string): Promise<CandidateScreening> { return request<CandidateScreening>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`); }
export function recordCandidateScreening(runId: string, decisions: CandidateScreeningDecision[], revision?: string): Promise<CandidateScreeningResult> {
  return jsonPost<CandidateScreeningResult>(`./api/runs/${encodeURIComponent(runId)}/candidate-screening`, { decisions, checklist_revision: revision });
}
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
export async function getPdfTasks(runId: string, readMode: "refresh" | "cached" = "refresh"): Promise<PdfTaskRegistry> {
  const suffix = readMode === "cached" ? "/cached" : "";
  const registry = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/pdf/tasks${suffix}`);
  if (!isPdfTaskRegistry(registry, runId)) throw new LocalApiRequestError("transport");
  return registry;
}
export async function getSavedSourceParses(runId: string, missionId: string): Promise<SavedSourceParseTask[]> {
  const response = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/source-parse-status`, { redirect: "error" });
  if (!exactObjectKeys(response, ["run_id", "mission_id", "trust_status", "tasks"])) throw new LocalApiRequestError("transport");
  const data = response as Record<string, unknown>;
  if (data.run_id !== runId || data.mission_id !== missionId || data.trust_status !== "saved_source_parse_state_not_scientific_evidence"
    || !Array.isArray(data.tasks) || data.tasks.length > 12) throw new LocalApiRequestError("transport");
  const seen = new Set<string>();
  for (const task of data.tasks) {
    const legacy = exactObjectKeys(task, ["document_id", "state"]);
    const cachedKeys = ["document_id", "state", "markdown_ready", "source_map_segment_count"];
    const linkable = exactObjectKeys(task, [...cachedKeys, "can_link_markdown"]);
    if ((!legacy && !linkable && !exactObjectKeys(task, cachedKeys)) || !boundedString(task.document_id, 255)
      || typeof task.state !== "string" || !["pending", "running", "done", "failed"].includes(task.state)
      || seen.has(task.document_id)) throw new LocalApiRequestError("transport");
    if (!legacy && (typeof task.markdown_ready !== "boolean" || (task.markdown_ready && task.state !== "done")
      || typeof task.source_map_segment_count !== "number" || !Number.isInteger(task.source_map_segment_count)
      || task.source_map_segment_count < 0 || task.source_map_segment_count > (task.markdown_ready ? 12 : 0))) throw new LocalApiRequestError("transport");
    if (linkable && (typeof task.can_link_markdown !== "boolean" || (task.can_link_markdown && (task.state !== "done" || task.markdown_ready)))) throw new LocalApiRequestError("transport");
    seen.add(task.document_id);
  }
  return data.tasks;
}
export async function getPdfStatus(runId: string, documentId: string): Promise<PdfTaskStatus> { const task = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/status`); if (!isPdfTaskStatus(task)) throw new LocalApiRequestError("transport"); return task; }
export function privateMarkdownUrl(runId: string, documentId: string): string { return `./api/runs/${encodeURIComponent(runId)}/pdf/${encodeURIComponent(documentId)}/markdown`; }
export function fetchedMarkdownUrl(runId: string, documentId: string): string { return `./api/runs/${encodeURIComponent(runId)}/source-markdown?document_id=${encodeURIComponent(documentId)}`; }
export interface PrivateMarkdownLineSource { runId: string; documentId: string; fetched: boolean; }
export const PRIVATE_MARKDOWN_WINDOW_SIZE = 20;
export interface PrivateMarkdownLine { number: number; text: string; truncated: boolean; }
export interface PrivateMarkdownWindow { start: number; total_lines: number; lines: PrivateMarkdownLine[]; }
export async function getPrivateMarkdownLines(source: PrivateMarkdownLineSource, start: number): Promise<PrivateMarkdownWindow> {
  const run = encodeURIComponent(source.runId);
  const documentId = encodeURIComponent(source.documentId);
  const suffix = source.fetched ? `source-markdown-lines?document_id=${documentId}&start=${start}` : `pdf/${documentId}/markdown-lines?start=${start}`;
  const response = await request<unknown>(`./api/runs/${run}/${suffix}`, { redirect: "error" });
  if (!exactObjectKeys(response, ["run_id", "document_id", "start", "total_lines", "lines"])) throw new LocalApiRequestError("transport");
  const data = response as Record<string, unknown>;
  if (data.run_id !== source.runId || data.document_id !== source.documentId || data.start !== start
    || typeof data.total_lines !== "number" || !Number.isSafeInteger(data.total_lines) || data.total_lines < start
    || !Array.isArray(data.lines) || data.lines.length !== Math.min(PRIVATE_MARKDOWN_WINDOW_SIZE, data.total_lines - start + 1)) throw new LocalApiRequestError("transport");
  for (const [index, line] of data.lines.entries()) {
    if (!exactObjectKeys(line, ["number", "text", "truncated"]) || line.number !== start + index
      || typeof line.text !== "string" || line.text.length > 3_200 || /[\r\n\u000b\u000c\u001c-\u001e\u0085\u2028\u2029]/.test(line.text)
      || typeof line.truncated !== "boolean") throw new LocalApiRequestError("transport");
  }
  return { start, total_lines: data.total_lines, lines: data.lines };
}
export async function linkFetchedMarkdown(runId: string, documentId: string, file: File): Promise<void> {
  const response = await request<unknown>(`./api/runs/${encodeURIComponent(runId)}/source-markdown-link?document_id=${encodeURIComponent(documentId)}`, {
    method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file, redirect: "error",
  });
  if (!exactObjectKeys(response, ["run_id", "document_id", "markdown_ready"])) throw new LocalApiRequestError("write_outcome_unknown");
  const data = response as Record<string, unknown>;
  if (data.run_id !== runId || data.document_id !== documentId || data.markdown_ready !== true) throw new LocalApiRequestError("write_outcome_unknown");
}
export interface PrivateSourceMapSegment { locator: string; kind: "paragraph" | "table" | "formula" | "figure_caption"; quote: string; }
export interface RecordedSourceMapSegment { segment_id: string; locator: string; kind: PrivateSourceMapSegment["kind"]; }
export interface SourceMapRecordResult { run_id: string; document_id: string; segment_count: number; segments: RecordedSourceMapSegment[]; trust_status: string; }
export type MaterialFactCategory = "composition" | "structure" | "property" | "processing" | "experimental_condition" | "simulation_method";
export interface HumanMaterialFactInput { fact_id: string; segment_id: string; category: MaterialFactCategory; name: string; value: string | number | null; unit: string | null; normalized_value: string | number | null; normalized_unit: string | null; qualifiers: Record<string, string | number | null>; }
export function getPdfSourceMapContext(runId: string, documentId: string, fetched = false): Promise<SourceMapRecordResult> {
  const id = encodeURIComponent(documentId);
  const suffix = fetched ? `source-map?document_id=${id}` : `pdf/${id}/source-map`;
  return request<SourceMapRecordResult>(`./api/runs/${encodeURIComponent(runId)}/${suffix}`);
}
export function recordPdfSourceMap(runId: string, documentId: string, segments: PrivateSourceMapSegment[], fetched = false): Promise<SourceMapRecordResult> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/${fetched ? "source-map" : "pdf/source-map"}`, { document_id: documentId, human_confirmed: true, segments }); }
export function recordPdfMaterialFacts(runId: string, documentId: string, facts: HumanMaterialFactInput[], fetched = false): Promise<{ run_id: string; document_id: string; fact_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/${fetched ? "source-material-facts" : "pdf/material-facts"}`, { document_id: documentId, human_confirmed: true, facts }); }
export interface HumanEvidenceReviewInput { segment_id: string; claim: string; stance: "support" | "contradict" | "context"; conditions: Record<string, string | number | null>; reviewer_confidence: number; }
export interface EvidenceReviewResult { run_id: string; evidence_id: string; document_id: string; locator: string; review_status: "accepted"; trust_status: string; }
export function recordPdfEvidenceCard(runId: string, documentId: string, input: HumanEvidenceReviewInput, fetched = false): Promise<EvidenceReviewResult> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/${fetched ? "source-evidence-card" : "pdf/evidence-card"}`, { document_id: documentId, human_confirmed: true, ...input }); }
export function confirmPdfDoi(runId: string, documentId: string, doi: string): Promise<PdfTaskStatus> { return jsonPost<PdfTaskStatus>(`./api/runs/${encodeURIComponent(runId)}/pdf/doi`, { document_id: documentId, doi, human_confirmed: true }); }
export function expandAuthorizedPdfCitations(runId: string, documentId: string, dshCallId: string): Promise<{ node_count: number; edge_count: number; failure_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/authorized-citation-expansion`, { document_id: documentId, authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"], actor: "human_bibliography_review", dsh_call_id: dshCallId }); }
export function diagnoseConditions(runId: string): Promise<{ run_id: string; matrix_row_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/condition-diagnostics`, {}); }
export function generateGapCandidates(runId: string): Promise<{ run_id: string; candidate_count: number; trust_status: string }> { return jsonPost(`./api/runs/${encodeURIComponent(runId)}/gap-candidates`, {}); }
export function importRunPackage(packagePayload: unknown): Promise<{ run_id: string; mission_id: string; next_stage: string | null; trust_status: "allowlisted_continuation_package" }> { return jsonPost("./api/runs/import", { package: packagePayload }); }
