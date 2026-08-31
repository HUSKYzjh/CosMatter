import { normalizeConfig } from './config.js';
const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const authorization = /^[a-z][a-z0-9_-]{1,119}$/;
const requiredAuthorizations = ['mission_scoped_egress_consent', 'mineru_file_consent', 'private_content_to_mineru'];
export class CosMatterDocumentClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async submit(runIdValue, input, dshCallId, signal) {
        assertInput(runIdValue, input.authorizations, input.document_id);
        assertPublicHttpsUrl(input.source_url);
        assertDshCallId(dshCallId);
        return this.post(`/api/runs/${encodeURIComponent(runIdValue)}/authorized-mineru-submit`, { ...input, dsh_call_id: dshCallId }, signal);
    }
    async poll(runIdValue, input, dshCallId, signal) {
        assertInput(runIdValue, input.authorizations, input.document_id);
        assertDshCallId(dshCallId);
        return this.post(`/api/runs/${encodeURIComponent(runIdValue)}/authorized-mineru-poll`, { ...input, dsh_call_id: dshCallId }, signal);
    }
    async post(path, body, signal) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(path, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body), signal: controller.signal });
            if (!response.ok)
                throw new Error(`CosMatter document request failed with HTTP ${response.status}`);
            const declared = Number(response.headers.get('content-length') ?? 0);
            if (declared > this.config.maxResponseBytes)
                throw new Error('CosMatter document response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter document response exceeds configured size');
            const value = JSON.parse(text);
            if (!isObject(value) || value.run_id === undefined || typeof value.document_id !== 'string' || value.document_id.length > 255 || value.provider !== 'mineru' || !['pending', 'running', 'done', 'failed'].includes(String(value.task_state)) || typeof value.trust_status !== 'string' || (value.idempotency_status !== undefined && value.idempotency_status !== 'duplicate_completed') || Object.keys(value).some(key => /url|token|secret|password|api[_-]?key|content|quote|path/i.test(key)))
                throw new Error('CosMatter document response is invalid');
            return value;
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
}
function assertInput(runIdValue, authorizations, documentId) {
    if (!runId.test(runIdValue) || typeof documentId !== 'string' || !documentId.trim() || documentId.length > 255 || !Array.isArray(authorizations) || authorizations.length !== requiredAuthorizations.length || authorizations.some(value => !authorization.test(value)) || [...new Set(authorizations)].sort().join(',') !== [...requiredAuthorizations].sort().join(','))
        throw new Error('explicit MinerU authorization input is invalid');
}
function assertPublicHttpsUrl(value) {
    if (typeof value !== 'string' || !value.trim() || value.length > 2_000)
        throw new Error('source_url is invalid');
    const parsed = new URL(value);
    if (parsed.protocol !== 'https:' || !parsed.hostname || parsed.username || parsed.password)
        throw new Error('source_url must be a credential-free HTTPS URL');
}
function assertDshCallId(value) { if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$/.test(value))
    throw new Error('DSH call identity is invalid'); }
function isObject(value) { return !!value && typeof value === 'object' && !Array.isArray(value); }
