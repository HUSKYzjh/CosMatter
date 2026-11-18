import { normalizeConfig, type CosMatterResearchConfig, type NormalizedConfig } from './config.js'

const runId = /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/
const authorization = /^[a-z][a-z0-9_-]{1,119}$/
const sourceNames = new Set(['sciverse', 'openalex', 'crossref'])
const reviewStages = new Set(['screening', 'parse', 'extraction', 'gap', 'report', 'evaluation', null])
const screeningTrust = new Set(['blank_human_candidate_screening_template_not_a_result', 'human_reviewed_candidate_screening_not_scientific_evidence'])

export interface ResearchPlan {
  subquestions: string[]
  queries: string[]
  counter_queries: string[]
  max_rounds?: number
  max_papers?: number
}

export interface PlanDraft {
  run_id: string
  trust_status: 'untrusted_draft'
  content: string
  idempotency_status?: 'duplicate_completed'
}

export interface ApprovedPlan {
  run_id: string
  plan_id: string
  queries: string[]
  counter_queries: string[]
}

export interface QueryResult {
  run_id: string
  query_kind: 'primary' | 'counter'
  query_index: number
  sources: string[]
  source_counts: Record<string, number>
  candidate_count: number
  candidates: Array<Record<string, unknown>>
  idempotency_status?: 'duplicate_completed'
  screening_revision?: string
  workbench_url: string
}

export function queryWorkbenchLink(baseUrl: string, id: string, screeningRevision?: string): string {
  const url = new URL('/?api=local', baseUrl)
  const params = new URLSearchParams({ run: id })
  if (screeningRevision) params.set('screening', screeningRevision)
  url.hash = params.toString()
  return url.href
}

export function isScreeningRevision(value: unknown): value is string {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
}

export class CosMatterResearchClient {
  readonly config: NormalizedConfig

  constructor(config: CosMatterResearchConfig = {}, private readonly request: typeof fetch = fetch) {
    this.config = normalizeConfig(config)
  }

  async draftPlan(runIdValue: string, authorizations: string[], dshCallId: string, signal?: AbortSignal): Promise<PlanDraft> {
    assertRunAndAuthorizations(runIdValue, authorizations, ['mission_scoped_egress_consent', 'deepseek_request_consent'])
    assertDshCallId(dshCallId)
    const value = await this.post(`/api/runs/${encodeURIComponent(runIdValue)}/authorized-draft-plan`, { authorizations, dsh_call_id: dshCallId }, signal)
    if (!isObject(value) || value.run_id !== runIdValue || value.trust_status !== 'untrusted_draft' || typeof value.content !== 'string' || !value.content.trim() || value.content.length > 16_000 || !validIdempotencyStatus(value.idempotency_status)) throw new Error('CosMatter research plan draft is invalid')
    return value as unknown as PlanDraft
  }

  async approvePlan(runIdValue: string, plan: ResearchPlan, signal?: AbortSignal): Promise<ApprovedPlan> {
    if (!runId.test(runIdValue) || !validPlan(plan)) throw new Error('CosMatter reviewed plan is invalid')
    const value = await this.post(`/api/runs/${encodeURIComponent(runIdValue)}/approve-plan`, plan, signal)
    if (!isObject(value) || value.run_id !== runIdValue || typeof value.plan_id !== 'string' || !/^plan_[a-z0-9]{12,64}$/.test(value.plan_id) || !stringArray(value.queries, 8) || !stringArray(value.counter_queries, 4)) throw new Error('CosMatter approved plan response is invalid')
    return value as unknown as ApprovedPlan
  }

  async executeQuery(runIdValue: string, input: { authorizations: string[]; query_index: number; counter?: boolean; sources: string[] }, dshCallId: string, signal?: AbortSignal): Promise<QueryResult> {
    assertRunAndAuthorizations(runIdValue, input.authorizations, ['mission_scoped_egress_consent', 'metadata_provider_consent'])
    if (!Number.isInteger(input.query_index) || input.query_index < 0 || input.query_index > 7 || (input.counter !== undefined && typeof input.counter !== 'boolean') || !validSources(input.sources)) throw new Error('CosMatter research query is invalid')
    assertDshCallId(dshCallId)
    const runPath = `/api/runs/${encodeURIComponent(runIdValue)}`
    const value = await this.post(`${runPath}/authorized-execute-query`, { authorizations: input.authorizations, query_index: input.query_index, counter: input.counter ?? false, sources: input.sources, dsh_call_id: dshCallId }, signal)
    if (!isObject(value) || value.run_id !== runIdValue || value.query_kind !== (input.counter ? 'counter' : 'primary') || value.query_index !== input.query_index
      || !validSources(value.sources) || !safeCounts(value.source_counts) || !Array.isArray(value.candidates)
      || value.candidates.length > 60 || value.candidate_count !== value.candidates.length || !value.candidates.every(safeCandidate)
      || !validIdempotencyStatus(value.idempotency_status)) throw new Error('CosMatter research query response is invalid')
    const revision = await this.screeningRevision(runIdValue, runPath, signal)
    return {
      run_id: runIdValue, query_kind: input.counter ? 'counter' : 'primary', query_index: input.query_index,
      sources: value.sources, source_counts: value.source_counts, candidate_count: value.candidates.length,
      candidates: value.candidates,
      ...(value.idempotency_status === 'duplicate_completed' ? { idempotency_status: value.idempotency_status } : {}),
      ...(revision ? { screening_revision: revision } : {}),
      workbench_url: queryWorkbenchLink(this.config.baseUrl, runIdValue, revision),
    }
  }

  private async screeningRevision(id: string, runPath: string, signal?: AbortSignal): Promise<string | undefined> {
    const budget = AbortSignal.timeout(Math.min(1_500, this.config.timeoutMs))
    const readSignal = signal ? AbortSignal.any([signal, budget]) : budget
    try {
      const stage = await this.requestJson(`${runPath}/stage-contract`, { method: 'GET' }, readSignal)
      if (!isObject(stage) || stage.run_id !== id || stage.schema_version !== 'cosmatter.stage-contract/v1'
        || stage.trust_status !== 'loopback_stage_contract_not_scientific_evidence_or_execution_authorization'
        || stage.runtime_safety !== 'verified' || (typeof stage.next_stage !== 'string' && stage.next_stage !== null)
        || !reviewStages.has(stage.next_stage)) return
      const checklist = await this.requestJson(`${runPath}/candidate-screening`, { method: 'GET' }, readSignal)
      if (isObject(checklist) && checklist.run_id === id && isScreeningRevision(checklist.checklist_revision)
        && typeof checklist.trust_status === 'string' && screeningTrust.has(checklist.trust_status)
        && Array.isArray(checklist.candidates) && checklist.candidates.length > 0 && checklist.candidate_count === checklist.candidates.length) {
        return checklist.checklist_revision
      }
    } catch {
      // A failed handoff lookup must preserve the completed query and its call ID.
    }
  }

  private async post(path: string, body: object, signal?: AbortSignal): Promise<unknown> {
    const budget = AbortSignal.timeout(this.config.timeoutMs)
    return this.requestJson(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body),
    }, signal ? AbortSignal.any([signal, budget]) : budget)
  }

  private async requestJson(path: string, options: RequestInit, signal: AbortSignal): Promise<unknown> {
    signal.throwIfAborted()
    const response = await this.request(new URL(path, this.config.baseUrl), {
      headers: { Accept: 'application/json' }, ...options, redirect: 'error', signal,
    })
    if (!response.ok) throw new Error(`CosMatter research request failed with HTTP ${response.status}`)
    const declared = Number(response.headers.get('content-length') ?? 0)
    if (declared > this.config.maxResponseBytes) throw new Error('CosMatter research response exceeds configured size')
    const text = await response.text()
    if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes) throw new Error('CosMatter research response exceeds configured size')
    return JSON.parse(text)
  }
}

function assertRunAndAuthorizations(runIdValue: string, values: string[], required: string[]): void {
  if (!runId.test(runIdValue) || !Array.isArray(values) || values.length !== required.length || values.some(value => !authorization.test(value)) || [...new Set(values)].sort().join(',') !== [...required].sort().join(',')) throw new Error('explicit research authorization is invalid')
}

function assertDshCallId(value: string): void {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$/.test(value)) throw new Error('DSH call identity is invalid')
}

function validIdempotencyStatus(value: unknown): boolean {
  return value === undefined || value === 'duplicate_completed'
}

function validPlan(plan: ResearchPlan): boolean {
  return isObject(plan) && stringArray(plan.subquestions, 5) && stringArray(plan.queries, 8) && stringArray(plan.counter_queries, 4) && (plan.max_rounds === undefined || (Number.isInteger(plan.max_rounds) && plan.max_rounds >= 1 && plan.max_rounds <= 3)) && (plan.max_papers === undefined || (Number.isInteger(plan.max_papers) && plan.max_papers >= 1 && plan.max_papers <= 20))
}

function validSources(values: unknown): values is string[] {
  return Array.isArray(values) && values.length >= 1 && values.length <= 3 && values.every(value => typeof value === 'string' && sourceNames.has(value)) && new Set(values).size === values.length
}

function stringArray(value: unknown, maximum: number): value is string[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= maximum && value.every(item => typeof item === 'string' && item.trim().length > 0 && item.length <= 1_000) && new Set(value).size === value.length
}

function safeCounts(value: unknown): value is Record<string, number> {
  return isObject(value) && Object.entries(value).every(([key, count]) => ['Sciverse', 'OpenAlex', 'Crossref'].includes(key) && typeof count === 'number' && Number.isInteger(count) && count >= 0 && count <= 20)
}

function safeCandidate(value: unknown): value is Record<string, unknown> {
  if (!isObject(value)) return false
  const allowed = new Set(['candidate_id', 'created_at', 'deduplication', 'document_id', 'doi', 'is_content_accessible', 'locator_hint', 'publication_year', 'query', 'retrieval_origins', 'score', 'source', 'title'])
  if (Object.keys(value).some(key => !allowed.has(key))) return false
  return typeof value.document_id === 'string' && value.document_id.length <= 255 && typeof value.title === 'string' && value.title.length <= 2_000 && typeof value.is_content_accessible === 'boolean'
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
