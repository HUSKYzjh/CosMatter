import { normalizeConfig, type CosMatterDocumentConfig, type NormalizedConfig } from './config.js'

const runId = /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/
const authorization = /^[a-z][a-z0-9_-]{1,119}$/
const requiredAuthorizations = ['mission_scoped_egress_consent', 'mineru_file_consent', 'private_content_to_mineru']

export interface MinerUTaskStatus { run_id: string; document_id: string; provider: 'mineru'; task_state: 'pending' | 'running' | 'done' | 'failed'; trust_status: string; idempotency_status?: 'duplicate_completed'; workbench_url: string }

const statusKeys = new Set(['run_id', 'document_id', 'provider', 'task_state', 'trust_status', 'idempotency_status'])
type MinerURequest = { document_id: string; authorizations: string[]; dsh_call_id: string; source_url?: string }

export class CosMatterDocumentClient {
  readonly config: NormalizedConfig
  constructor(config: CosMatterDocumentConfig = {}, private readonly request: typeof fetch = fetch) { this.config = normalizeConfig(config) }

  async submit(runIdValue: string, input: { authorizations: string[]; document_id: string; source_url: string }, dshCallId: string, signal?: AbortSignal): Promise<MinerUTaskStatus> {
    assertInput(runIdValue, input.authorizations, input.document_id)
    assertPublicHttpsUrl(input.source_url)
    assertDshCallId(dshCallId)
    return this.post(runIdValue, 'submit', { ...input, dsh_call_id: dshCallId }, signal)
  }

  async poll(runIdValue: string, input: { authorizations: string[]; document_id: string }, dshCallId: string, signal?: AbortSignal): Promise<MinerUTaskStatus> {
    assertInput(runIdValue, input.authorizations, input.document_id)
    assertDshCallId(dshCallId)
    return this.post(runIdValue, 'poll', { ...input, dsh_call_id: dshCallId }, signal)
  }

  private async post(run: string, operation: 'submit' | 'poll', body: MinerURequest, signal?: AbortSignal): Promise<MinerUTaskStatus> {
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), this.config.timeoutMs); const abort = () => controller.abort(); signal?.addEventListener('abort', abort, { once: true })
    try {
      const path = `/api/runs/${encodeURIComponent(run)}/authorized-mineru-${operation}`
      const response = await this.request(new URL(path, this.config.baseUrl), { method: 'POST', redirect: 'error', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body), signal: controller.signal })
      if (!response.ok) throw new Error(`CosMatter document request failed with HTTP ${response.status}`)
      const declared = Number(response.headers.get('content-length') ?? 0); if (declared > this.config.maxResponseBytes) throw new Error('CosMatter document response exceeds configured size')
      const text = await response.text(); if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes) throw new Error('CosMatter document response exceeds configured size')
      const value: unknown = JSON.parse(text)
      if (!isObject(value) || value.run_id !== run || value.document_id !== body.document_id || value.provider !== 'mineru'
        || typeof value.task_state !== 'string' || !['pending', 'running', 'done', 'failed'].includes(value.task_state)
        || typeof value.trust_status !== 'string' || !['authorized_parse_dispatch_not_evidence_acceptance', 'authorized_parse_status_not_evidence_acceptance'].includes(value.trust_status)
        || (value.idempotency_status !== undefined && value.idempotency_status !== 'duplicate_completed')
        || Object.keys(value).some(key => !statusKeys.has(key))) throw new Error('CosMatter document response is invalid')
      const workbench = new URL('/?api=local', this.config.baseUrl)
      workbench.hash = new URLSearchParams({ run, document: body.document_id }).toString()
      return { ...value, workbench_url: workbench.href } as unknown as MinerUTaskStatus
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort) }
  }
}

function assertInput(runIdValue: string, authorizations: string[], documentId: string): void {
  if (!runId.test(runIdValue) || typeof documentId !== 'string' || !documentId || documentId.trim() !== documentId
    || documentId.length > 255 || /[\u0000-\u001f\u007f]/.test(documentId)
    || !Array.isArray(authorizations) || authorizations.length !== requiredAuthorizations.length
    || authorizations.some(value => !authorization.test(value)) || !requiredAuthorizations.every(value => authorizations.includes(value))) {
    throw new Error('explicit MinerU authorization input is invalid')
  }
}

function assertPublicHttpsUrl(value: string): void {
  if (typeof value !== 'string' || !value.trim() || value.length > 2_000) throw new Error('source_url is invalid')
  const parsed = new URL(value); if (parsed.protocol !== 'https:' || !parsed.hostname || parsed.username || parsed.password) throw new Error('source_url must be a credential-free HTTPS URL')
}
function assertDshCallId(value: string): void { if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$/.test(value)) throw new Error('DSH call identity is invalid') }
function isObject(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value) }
