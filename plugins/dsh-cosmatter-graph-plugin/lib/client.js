import { normalizeConfig } from './config.js';
import { assertGraphSnapshot } from './contract.js';
const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
export class CosMatterLoopbackClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async graph(runIdValue, options = {}) {
        if (!runId.test(runIdValue))
            throw new Error('run_id must use letters, numbers, underscores, or hyphens');
        const url = new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph`, this.config.baseUrl);
        if (options.nodeType)
            url.searchParams.set('node_type', options.nodeType);
        if (options.offset !== undefined)
            url.searchParams.set('offset', String(options.offset));
        if (options.limit !== undefined)
            url.searchParams.set('limit', String(options.limit));
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        options.signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(url, { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            if (!response.ok)
                throw new Error(`CosMatter graph request failed with HTTP ${response.status}`);
            const declaredSize = Number(response.headers.get('content-length') ?? 0);
            if (declaredSize > this.config.maxGraphBytes)
                throw new Error('CosMatter graph response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxGraphBytes)
                throw new Error('CosMatter graph response exceeds configured size');
            const payload = JSON.parse(text);
            assertGraphSnapshot(payload);
            return payload;
        }
        finally {
            clearTimeout(timer);
            options.signal?.removeEventListener('abort', abort);
        }
    }
    async searchAcceptedEvidence(runIdValue, query, limit = 8, signal) {
        if (!runId.test(runIdValue) || typeof query !== 'string' || !query.trim() || query.length > 300 || !Number.isInteger(limit) || limit < 1 || limit > 12)
            throw new Error('accepted-evidence search request is invalid');
        const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/accepted-evidence/search`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ query: query.trim(), limit }), signal });
        const payload = await response.json();
        if (!response.ok || !payload || typeof payload !== 'object')
            throw new Error('accepted-evidence search was rejected');
        const result = payload;
        if (result.mission_id === undefined || result.trust_status !== 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion' || typeof result.query_sha256 !== 'string' || !Array.isArray(result.results) || result.results.length > limit || result.results.some(item => !safeEvidenceResult(item)))
            throw new Error('accepted-evidence search response is invalid');
        return result;
    }
    async requestReview(runIdValue, nodeIds, rationale, signal) {
        if (!runId.test(runIdValue) || !nodeIds.length || nodeIds.length > 25 || nodeIds.some(item => !/^[a-z_]+:[a-f0-9]{16,64}$/.test(item)) || !rationale.trim() || rationale.length > 1000)
            throw new Error('graph review request is invalid');
        const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph/review-request`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ node_ids: nodeIds, rationale: rationale.trim() }), signal });
        const payload = await response.json();
        if (!response.ok || !payload || typeof payload !== 'object' || payload.status !== 'pending_human_review_not_evidence_acceptance')
            throw new Error('CosMatter graph review request was rejected');
        return payload;
    }
    async draftPlan(runIdValue, nodeIds, intent, signal) {
        if (!runId.test(runIdValue) || !nodeIds.length || nodeIds.length > 25 || nodeIds.some(item => !/^[a-z_]+:[a-f0-9]{16,64}$/.test(item)) || !intent.trim() || intent.length > 500)
            throw new Error('graph plan draft is invalid');
        const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/graph/plan-draft`, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ node_ids: nodeIds, intent: intent.trim() }), signal });
        const payload = await response.json();
        if (!response.ok || !payload || typeof payload !== 'object' || payload.trust_status !== 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance')
            throw new Error('CosMatter graph plan draft was rejected');
        return payload;
    }
}
function safeEvidenceResult(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const item = value;
    const allowed = new Set(['evidence_id', 'document_id', 'claim', 'stance', 'material', 'property_name', 'conditions', 'locator', 'source', 'score']);
    return !Object.keys(item).some(key => !allowed.has(key) || /quote|url|token|secret|content|path/i.test(key)) && typeof item.evidence_id === 'string' && typeof item.document_id === 'string' && typeof item.claim === 'string' && typeof item.locator === 'string' && typeof item.source === 'string' && typeof item.score === 'number' && item.score > 0;
}
