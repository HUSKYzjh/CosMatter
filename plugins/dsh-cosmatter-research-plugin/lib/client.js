import { normalizeConfig } from './config.js';
const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const authorization = /^[a-z][a-z0-9_-]{1,119}$/;
const sourceNames = new Set(['sciverse', 'openalex', 'crossref']);
export class CosMatterResearchClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async draftPlan(runIdValue, authorizations, dshCallId, signal) {
        assertRunAndAuthorizations(runIdValue, authorizations, ['mission_scoped_egress_consent', 'deepseek_request_consent']);
        assertDshCallId(dshCallId);
        const value = await this.post(`/api/runs/${encodeURIComponent(runIdValue)}/authorized-draft-plan`, { authorizations, dsh_call_id: dshCallId }, signal);
        if (!isObject(value) || value.run_id !== runIdValue || value.trust_status !== 'untrusted_draft' || typeof value.content !== 'string' || !value.content.trim() || value.content.length > 16_000 || !validIdempotencyStatus(value.idempotency_status))
            throw new Error('CosMatter research plan draft is invalid');
        return value;
    }
    async approvePlan(runIdValue, plan, signal) {
        if (!runId.test(runIdValue) || !validPlan(plan))
            throw new Error('CosMatter reviewed plan is invalid');
        const value = await this.post(`/api/runs/${encodeURIComponent(runIdValue)}/approve-plan`, plan, signal);
        if (!isObject(value) || value.run_id !== runIdValue || typeof value.plan_id !== 'string' || !/^plan_[a-z0-9]{12,64}$/.test(value.plan_id) || !stringArray(value.queries, 8) || !stringArray(value.counter_queries, 4))
            throw new Error('CosMatter approved plan response is invalid');
        return value;
    }
    async executeQuery(runIdValue, input, dshCallId, signal) {
        assertRunAndAuthorizations(runIdValue, input.authorizations, ['mission_scoped_egress_consent', 'metadata_provider_consent']);
        if (!Number.isInteger(input.query_index) || input.query_index < 0 || input.query_index > 7 || (input.counter !== undefined && typeof input.counter !== 'boolean') || !validSources(input.sources))
            throw new Error('CosMatter research query is invalid');
        assertDshCallId(dshCallId);
        const value = await this.post(`/api/runs/${encodeURIComponent(runIdValue)}/authorized-execute-query`, { authorizations: input.authorizations, query_index: input.query_index, counter: input.counter ?? false, sources: input.sources, dsh_call_id: dshCallId }, signal);
        if (!isObject(value) || value.run_id !== runIdValue || (value.query_kind !== 'primary' && value.query_kind !== 'counter') || !Number.isInteger(value.query_index) || !validSources(value.sources) || !safeCounts(value.source_counts) || typeof value.candidate_count !== 'number' || !Number.isInteger(value.candidate_count) || value.candidate_count < 0 || value.candidate_count > 60 || !Array.isArray(value.candidates) || value.candidates.length > 60 || !value.candidates.every(safeCandidate) || !validIdempotencyStatus(value.idempotency_status))
            throw new Error('CosMatter research query response is invalid');
        return value;
    }
    async post(path, body, signal) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(path, this.config.baseUrl), { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body), signal: controller.signal });
            if (!response.ok)
                throw new Error(`CosMatter research request failed with HTTP ${response.status}`);
            const declared = Number(response.headers.get('content-length') ?? 0);
            if (declared > this.config.maxResponseBytes)
                throw new Error('CosMatter research response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter research response exceeds configured size');
            return JSON.parse(text);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
}
function assertRunAndAuthorizations(runIdValue, values, required) {
    if (!runId.test(runIdValue) || !Array.isArray(values) || values.length !== required.length || values.some(value => !authorization.test(value)) || [...new Set(values)].sort().join(',') !== [...required].sort().join(','))
        throw new Error('explicit research authorization is invalid');
}
function assertDshCallId(value) {
    if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$/.test(value))
        throw new Error('DSH call identity is invalid');
}
function validIdempotencyStatus(value) {
    return value === undefined || value === 'duplicate_completed';
}
function validPlan(plan) {
    return isObject(plan) && stringArray(plan.subquestions, 5) && stringArray(plan.queries, 8) && stringArray(plan.counter_queries, 4) && (plan.max_rounds === undefined || (Number.isInteger(plan.max_rounds) && plan.max_rounds >= 1 && plan.max_rounds <= 3)) && (plan.max_papers === undefined || (Number.isInteger(plan.max_papers) && plan.max_papers >= 1 && plan.max_papers <= 20));
}
function validSources(values) {
    return Array.isArray(values) && values.length >= 1 && values.length <= 3 && values.every(value => typeof value === 'string' && sourceNames.has(value)) && new Set(values).size === values.length;
}
function stringArray(value, maximum) {
    return Array.isArray(value) && value.length >= 1 && value.length <= maximum && value.every(item => typeof item === 'string' && item.trim().length > 0 && item.length <= 1_000) && new Set(value).size === value.length;
}
function safeCounts(value) {
    return isObject(value) && Object.entries(value).every(([key, count]) => ['Sciverse', 'OpenAlex', 'Crossref'].includes(key) && typeof count === 'number' && Number.isInteger(count) && count >= 0 && count <= 20);
}
function safeCandidate(value) {
    if (!isObject(value))
        return false;
    const allowed = new Set(['candidate_id', 'created_at', 'deduplication', 'document_id', 'doi', 'is_content_accessible', 'locator_hint', 'publication_year', 'query', 'retrieval_origins', 'score', 'source', 'title']);
    if (Object.keys(value).some(key => !allowed.has(key)))
        return false;
    return typeof value.document_id === 'string' && value.document_id.length <= 255 && typeof value.title === 'string' && value.title.length <= 2_000 && typeof value.is_content_accessible === 'boolean';
}
function isObject(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value);
}
