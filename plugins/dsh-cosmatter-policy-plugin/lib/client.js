import { normalizeConfig } from './config.js';
const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const sensitive = /(token|secret|password|api[_-]?key|private_path|quote|content)/i;
export class CosMatterPolicyClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async catalogue(signal) {
        const result = await this.fetchJson(new URL('/api/plugins', this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal });
        if (!result || typeof result !== 'object' || Array.isArray(result))
            throw new Error('CosMatter plugin catalogue is invalid');
        const value = result;
        if (value.catalogue_api_version !== '2.0' || value.trust_status !== 'static_catalogue_not_plugin_execution_or_evidence_acceptance' || !Array.isArray(value.plugins) || !value.plugins.length || value.plugins.length > 64 || value.plugins.some(plugin => !plugin || typeof plugin !== 'object' || sensitiveKeys(plugin) || typeof plugin.plugin_id !== 'string'))
            throw new Error('CosMatter plugin catalogue is invalid');
        return value;
    }
    async authorizationPlan(runIdValue, pluginId, authorizations, signal) {
        if (!runId.test(runIdValue) || !/^[a-z][a-z0-9_.-]{1,119}$/.test(pluginId) || authorizations.length > 12 || authorizations.some(value => !/^[a-z][a-z0-9_-]{1,119}$/.test(value)))
            throw new Error('policy plan input is invalid');
        const result = await this.fetchJson(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/plugin-authorization-plan`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ plugin_id: pluginId, authorizations }), signal });
        if (!result || typeof result !== 'object' || Array.isArray(result))
            throw new Error('CosMatter authorization plan is invalid');
        const value = result;
        if (value.trust_status !== 'nonexecuting_authorization_plan_not_consent_or_execution' || value.plugin_id !== pluginId || typeof value.mission_id !== 'string' || typeof value.permitted !== 'boolean' || typeof value.reason !== 'string' || !Array.isArray(value.missing_authorizations) || typeof value.requires_human_review !== 'boolean' || typeof value.next_boundary !== 'string')
            throw new Error('CosMatter authorization plan is invalid');
        return value;
    }
    async fetchJson(url, init) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const outerSignal = init.signal;
        const abort = () => controller.abort();
        outerSignal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(url, { ...init, signal: controller.signal });
            if (!response.ok)
                throw new Error(`CosMatter policy request failed with HTTP ${response.status}`);
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxCatalogueBytes)
                throw new Error('CosMatter policy response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxCatalogueBytes)
                throw new Error('CosMatter policy response exceeds configured size');
            return JSON.parse(text);
        }
        finally {
            clearTimeout(timer);
            outerSignal?.removeEventListener('abort', abort);
        }
    }
}
function sensitiveKeys(value) { return Object.keys(value).some(key => sensitive.test(key)); }
