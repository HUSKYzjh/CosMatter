import { normalizeConfig, type CosMatterPolicyConfig, type NormalizedConfig } from './config.js'

const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/
const sensitive = /(token|secret|password|api[_-]?key|private_path|quote|content)/i
export interface PolicyCatalogue { catalogue_api_version: '2.0'; plugins: Array<Record<string, unknown>>; trust_status: 'static_catalogue_not_plugin_execution_or_evidence_acceptance' }
export interface AuthorizationPlan { mission_id: string; plugin_id: string; permitted: boolean; reason: string; missing_authorizations: string[]; requires_human_review: boolean; next_boundary: string; trust_status: 'nonexecuting_authorization_plan_not_consent_or_execution' }

export class CosMatterPolicyClient {
  readonly config: NormalizedConfig
  constructor(config: CosMatterPolicyConfig = {}, private readonly request: typeof fetch = fetch) { this.config = normalizeConfig(config) }
  async catalogue(signal?: AbortSignal): Promise<PolicyCatalogue> {
    const result = await this.fetchJson(new URL('/api/plugins', this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal })
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('CosMatter plugin catalogue is invalid')
    const value = result as Record<string, unknown>
    if (value.catalogue_api_version !== '2.0' || value.trust_status !== 'static_catalogue_not_plugin_execution_or_evidence_acceptance' || !Array.isArray(value.plugins) || !value.plugins.length || value.plugins.length > 64 || value.plugins.some(plugin => !plugin || typeof plugin !== 'object' || sensitiveKeys(plugin as Record<string, unknown>) || typeof (plugin as Record<string, unknown>).plugin_id !== 'string')) throw new Error('CosMatter plugin catalogue is invalid')
    return value as unknown as PolicyCatalogue
  }
  async authorizationPlan(runIdValue: string, pluginId: string, authorizations: string[], signal?: AbortSignal): Promise<AuthorizationPlan> {
    if (!runId.test(runIdValue) || !/^[a-z][a-z0-9_.-]{1,119}$/.test(pluginId) || authorizations.length > 12 || authorizations.some(value => !/^[a-z][a-z0-9_-]{1,119}$/.test(value))) throw new Error('policy plan input is invalid')
    const result = await this.fetchJson(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/plugin-authorization-plan`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ plugin_id: pluginId, authorizations }), signal })
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('CosMatter authorization plan is invalid')
    const value = result as Record<string, unknown>
    if (value.trust_status !== 'nonexecuting_authorization_plan_not_consent_or_execution' || value.plugin_id !== pluginId || typeof value.mission_id !== 'string' || typeof value.permitted !== 'boolean' || typeof value.reason !== 'string' || !Array.isArray(value.missing_authorizations) || typeof value.requires_human_review !== 'boolean' || typeof value.next_boundary !== 'string') throw new Error('CosMatter authorization plan is invalid')
    return value as unknown as AuthorizationPlan
  }
  private async fetchJson(url: URL, init: RequestInit): Promise<unknown> {
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), this.config.timeoutMs); const outerSignal = init.signal
    const abort = () => controller.abort(); outerSignal?.addEventListener('abort', abort, { once: true })
    try {
      const response = await this.request(url, { ...init, signal: controller.signal }); if (!response.ok) throw new Error(`CosMatter policy request failed with HTTP ${response.status}`)
      const length = Number(response.headers.get('content-length') ?? 0); if (length > this.config.maxCatalogueBytes) throw new Error('CosMatter policy response exceeds configured size')
      const text = await response.text(); if (new TextEncoder().encode(text).byteLength > this.config.maxCatalogueBytes) throw new Error('CosMatter policy response exceeds configured size')
      return JSON.parse(text)
    } finally { clearTimeout(timer); outerSignal?.removeEventListener('abort', abort) }
  }
}
function sensitiveKeys(value: Record<string, unknown>): boolean { return Object.keys(value).some(key => sensitive.test(key)) }
