import { normalizeConfig, type CosMatterGraphConfig, type NormalizedConfig } from './config.js'
import { assertGraphSnapshot, type GraphSnapshot } from './contract.js'

const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/
const evidenceSearchKeys = new Set(['run_id', 'schema_version', 'mission_id', 'trust_status', 'query_sha256', 'query_char_count', 'accepted_evidence_count', 'result_count', 'results', 'match_mode'])

export class CosMatterLoopbackClient {
  readonly config: NormalizedConfig

  constructor(config: CosMatterGraphConfig = {}, private readonly request: typeof fetch = fetch) {
    this.config = normalizeConfig(config)
  }

  async graph(runIdValue: string, options: { nodeType?: string; offset?: number; limit?: number; signal?: AbortSignal } = {}): Promise<GraphSnapshot> {
    if (!runId.test(runIdValue)) throw new Error('run_id must use letters, numbers, underscores, or hyphens')
    const url = new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph`, this.config.baseUrl)
    if (options.nodeType) url.searchParams.set('node_type', options.nodeType)
    if (options.offset !== undefined) url.searchParams.set('offset', String(options.offset))
    if (options.limit !== undefined) url.searchParams.set('limit', String(options.limit))
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.config.timeoutMs)
    const abort = () => controller.abort()
    options.signal?.addEventListener('abort', abort, { once: true })
    try {
      const response = await this.request(url, { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal })
      if (!response.ok) throw new Error(`CosMatter graph request failed with HTTP ${response.status}`)
      const declaredSize = Number(response.headers.get('content-length') ?? 0)
      if (declaredSize > this.config.maxGraphBytes) throw new Error('CosMatter graph response exceeds configured size')
      const text = await response.text()
      if (new TextEncoder().encode(text).byteLength > this.config.maxGraphBytes) throw new Error('CosMatter graph response exceeds configured size')
      const payload: unknown = JSON.parse(text)
      assertGraphSnapshot(payload)
      return payload
    } finally {
      clearTimeout(timer)
      options.signal?.removeEventListener('abort', abort)
    }
  }

  async searchAcceptedEvidence(runIdValue: string, selector: string | { evidenceId: string }, limit = 8, signal?: AbortSignal): Promise<Record<string, unknown>> {
    if (!runId.test(runIdValue) || runIdValue.length > 255 || !Number.isInteger(limit) || limit < 1 || limit > 12) throw new Error('accepted-evidence search request is invalid')
    const query = typeof selector === 'string' ? selector.trim() : null
    const evidenceId = typeof selector === 'string' ? null : selector?.evidenceId
    if (query !== null ? !query || query.length > 300 : typeof evidenceId !== 'string' || !canLinkIdentifier(evidenceId, 200)) throw new Error('accepted-evidence search selector is invalid')
    const url = new URL(`/api/runs/${encodeURIComponent(runIdValue)}/accepted-evidence/search`, this.config.baseUrl)
    const timeout = AbortSignal.timeout(this.config.timeoutMs)
    const response = await this.request(url, {
      method: 'POST', redirect: 'error', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ ...(query === null ? { evidence_id: evidenceId } : { query }), limit }), signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    })
    if (!response.ok) throw new Error('accepted-evidence search was rejected')
    if (Number(response.headers.get('content-length') ?? 0) > this.config.maxGraphBytes) throw new Error('accepted-evidence search response exceeds configured size')
    const text = await response.text()
    if (new TextEncoder().encode(text).byteLength > this.config.maxGraphBytes) throw new Error('accepted-evidence search response exceeds configured size')
    const payload: unknown = JSON.parse(text)
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('accepted-evidence search response is invalid')
    const result = payload as Record<string, unknown>
    if (Object.keys(result).some(key => !evidenceSearchKeys.has(key)) || (result.run_id !== undefined && result.run_id !== runIdValue)
      || typeof result.mission_id !== 'string' || !result.mission_id.trim()
      || result.trust_status !== 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion'
      || typeof result.query_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(result.query_sha256)
      || !Array.isArray(result.results) || result.results.length > limit || !result.results.every(safeEvidenceResult)) throw new Error('accepted-evidence search response is invalid')
    if (evidenceId && (result.match_mode !== 'exact_id' || result.results.length > 1 || result.results.some(item => item.evidence_id !== evidenceId))) throw new Error('accepted-evidence exact response is invalid')
    const results = result.results.map(item => {
      const link = acceptedEvidenceWorkbenchLink(this.config.baseUrl.origin, runIdValue, item.document_id, item.evidence_id)
      return link ? { ...item, workbench_url: link } : item
    })
    return { ...result, results }
  }

  async requestReview(runIdValue: string, nodeIds: string[], rationale: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    if (!runId.test(runIdValue) || !nodeIds.length || nodeIds.length > 25 || nodeIds.some(item => !/^[a-z_]+:[a-f0-9]{16,64}$/.test(item)) || !rationale.trim() || rationale.length > 1000) throw new Error('graph review request is invalid')
    const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph/review-request`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ node_ids: nodeIds, rationale: rationale.trim() }), signal })
    const payload: unknown = await response.json()
    if (!response.ok || !payload || typeof payload !== 'object' || (payload as Record<string, unknown>).status !== 'pending_human_review_not_evidence_acceptance') throw new Error('CosMatter graph review request was rejected')
    return payload as Record<string, unknown>
  }

  async draftPlan(runIdValue: string, nodeIds: string[], intent: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    if (!runId.test(runIdValue) || !nodeIds.length || nodeIds.length > 25 || nodeIds.some(item => !/^[a-z_]+:[a-f0-9]{16,64}$/.test(item)) || !intent.trim() || intent.length > 500) throw new Error('graph plan draft is invalid')
    const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph/plan-draft`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ node_ids: nodeIds, intent: intent.trim() }), signal })
    const payload: unknown = await response.json()
    if (!response.ok || !payload || typeof payload !== 'object' || (payload as Record<string, unknown>).trust_status !== 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance') throw new Error('CosMatter graph plan draft was rejected')
    return payload as Record<string, unknown>
  }
}

export function acceptedEvidenceWorkbenchLink(origin: string, run: string, document: string, evidence: string): string | null {
  if (!runId.test(run) || run.length > 255 || !canLinkIdentifier(document, 255) || !canLinkIdentifier(evidence, 200)) return null
  const url = new URL('/?api=local', origin)
  url.hash = new URLSearchParams({ run, document, evidence }).toString()
  return url.href
}

function canLinkIdentifier(value: string, maxLength: number): boolean {
  return value.length > 0 && value.length <= maxLength && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value)
}

function safeEvidenceResult(value: unknown): value is Record<string, unknown> & { evidence_id: string; document_id: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const item = value as Record<string, unknown>
  const allowed = new Set(['evidence_id', 'document_id', 'claim', 'stance', 'material', 'property_name', 'conditions', 'locator', 'source', 'score'])
  return !Object.keys(item).some(key => !allowed.has(key) || /quote|url|token|secret|content|path/i.test(key)) && typeof item.evidence_id === 'string' && typeof item.document_id === 'string' && typeof item.claim === 'string' && typeof item.locator === 'string' && typeof item.source === 'string' && typeof item.score === 'number' && item.score > 0
}
