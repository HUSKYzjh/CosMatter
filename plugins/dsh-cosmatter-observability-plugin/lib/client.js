import { normalizeConfig } from './config.js';
const runId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const sensitiveKey = /(token|secret|password|authorization|api[_-]?key|private_path|quote|url)/i;
const stages = new Set(['intake', 'plan', 'retrieval', 'screening', 'parse', 'extraction', 'gap', 'report', 'evaluation']);
const states = new Set(['completed', 'ready', 'waiting_human_review', 'blocked']);
const runtimeSafety = new Set(['verified', 'attention_required']);
const costLatencyStatus = new Set(['not_recorded', 'recorded', 'invalid']);
const receiptOperations = new Set(['agentic_search', 'content', 'source_parse_submit', 'source_parse_poll']);
const dispatchOperations = new Set(['deepseek_plan_draft', 'metadata_query', 'mineru_submit', 'mineru_poll']);
const currencies = new Set(['CNY', 'USD', 'EUR', 'not_applicable']);
const stageContracts = {
    intake: { requirements: ['mission_boundary_recorded'], humanGate: 'mission_definition', outputs: ['mission_brief'], recoveryRoute: 'mission_boundary_review' },
    plan: { requirements: ['approved_flight_plan'], humanGate: 'plan_approval', outputs: ['approved_flight_plan'], recoveryRoute: 'plan_review' },
    retrieval: { requirements: ['approved_queries_executed', 'provider_receipt_links_valid'], humanGate: 'mission_scoped_egress_consent', outputs: ['retrieval_candidate_history', 'provider_receipt_links'], recoveryRoute: 'authorized_retrieval_review' },
    screening: { requirements: ['candidate_fingerprint_current', 'human_candidate_screening_complete'], humanGate: 'candidate_screening', outputs: ['candidate_screening_decision'], recoveryRoute: 'candidate_screening_review' },
    parse: { requirements: ['fulltext_access_confirmed', 'mineru_task_receipts_linked'], humanGate: 'content_access_and_parse_consent', outputs: ['source_parse_task_ledger'], recoveryRoute: 'content_access_review' },
    extraction: { requirements: ['human_source_map_recorded', 'human_evidence_decision_recorded'], humanGate: 'source_map_and_evidence_review', outputs: ['source_map', 'material_fact', 'verification_decision'], recoveryRoute: 'source_map_review' },
    gap: { requirements: ['accepted_evidence_conditions_compared', 'counterevidence_boundary_executed'], humanGate: 'gap_candidate_review', outputs: ['research_gap_candidate'], recoveryRoute: 'counterevidence_review' },
    report: { requirements: ['review_gated_inputs_available', 'report_audit_valid'], humanGate: 'report_review', outputs: ['review_gated_report'], recoveryRoute: 'report_audit_review' },
    evaluation: { requirements: ['required_human_metric_families_complete'], humanGate: 'evaluation_review', outputs: ['human_evaluation_summary'], recoveryRoute: 'evaluation_review' },
};
const dagSpecs = {
    intake: { dependsOn: [], descriptors: ['mission.define'], dataClassification: 'mission', executionClass: 'local_review_gated' },
    plan: { dependsOn: ['intake'], descriptors: ['planning.orchestrate'], dataClassification: 'mission', executionClass: 'local_review_gated' },
    retrieval: { dependsOn: ['plan'], descriptors: ['literature.metadata_retrieval', 'literature.deduplicate_and_rank'], dataClassification: 'public_metadata', executionClass: 'explicit_consent_required' },
    screening: { dependsOn: ['retrieval'], descriptors: [], dataClassification: 'public_metadata', executionClass: 'human_review_required' },
    parse: { dependsOn: ['screening'], descriptors: ['document.mineru_private_parse'], dataClassification: 'private_fulltext', executionClass: 'explicit_consent_required' },
    extraction: { dependsOn: ['parse'], descriptors: ['evidence.material_extract', 'evidence.source_map', 'evidence.verify'], dataClassification: 'reviewable_excerpt', executionClass: 'human_review_required' },
    gap: { dependsOn: ['extraction'], descriptors: ['research.gap_candidates'], dataClassification: 'accepted_evidence', executionClass: 'human_review_required' },
    report: { dependsOn: ['gap'], descriptors: ['report.generate'], dataClassification: 'accepted_evidence', executionClass: 'local_review_gated' },
    evaluation: { dependsOn: ['report'], descriptors: [], dataClassification: 'run_summary', executionClass: 'human_review_required' },
};
const artifactIds = new Set(['ui_bundle', 'graph_snapshot', 'workflow_readiness', 'runtime_invariants', 'mission_report', 'research_report']);
const artifactTrust = new Set(['browser_safe_export_from_reviewed_artifacts', 'accepted_evidence_projection_not_scientific_conclusion', 'derived_workflow_readiness_not_scientific_evidence', 'runtime_relationship_audit_not_scientific_evidence_or_provider_status_verification', 'review_gated_evidence_manifest', 'review_gated_structured_report']);
const sha256 = /^[a-f0-9]{64}$/;
export class CosMatterObservabilityClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async workflowStatus(runIdValue, signal) {
        if (!runId.test(runIdValue))
            throw new Error('run_id is invalid');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/workflow-status`, this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxResponseBytes)
                throw new Error('CosMatter workflow status response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter workflow status response exceeds configured size');
            if (!response.ok)
                throw new Error(`CosMatter workflow status request failed with HTTP ${response.status}`);
            return validateWorkflowStatus(JSON.parse(text), runIdValue);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
    async artifactManifest(runIdValue, signal) {
        if (!runId.test(runIdValue))
            throw new Error('run_id is invalid');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/artifacts`, this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxResponseBytes)
                throw new Error('CosMatter artifact manifest response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter artifact manifest response exceeds configured size');
            if (!response.ok)
                throw new Error(`CosMatter artifact manifest request failed with HTTP ${response.status}`);
            return validateArtifactManifest(JSON.parse(text), runIdValue);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
    async stageContract(runIdValue, signal) {
        if (!runId.test(runIdValue))
            throw new Error('run_id is invalid');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/stage-contract`, this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxResponseBytes)
                throw new Error('CosMatter stage contract response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter stage contract response exceeds configured size');
            if (!response.ok)
                throw new Error(`CosMatter stage contract request failed with HTTP ${response.status}`);
            return validateStageContract(JSON.parse(text), runIdValue);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
    async operationalTelemetry(runIdValue, signal) {
        if (!runId.test(runIdValue))
            throw new Error('run_id is invalid');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/operational-telemetry`, this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxResponseBytes)
                throw new Error('CosMatter operational telemetry response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter operational telemetry response exceeds configured size');
            if (!response.ok)
                throw new Error(`CosMatter operational telemetry request failed with HTTP ${response.status}`);
            return validateOperationalTelemetry(JSON.parse(text), runIdValue);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
    async workflowDag(runIdValue, signal) {
        if (!runId.test(runIdValue))
            throw new Error('run_id is invalid');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL(`/api/runs/${encodeURIComponent(runIdValue)}/workflow-dag`, this.config.baseUrl), { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal });
            const length = Number(response.headers.get('content-length') ?? 0);
            if (length > this.config.maxResponseBytes)
                throw new Error('CosMatter workflow DAG response exceeds configured size');
            const text = await response.text();
            if (new TextEncoder().encode(text).byteLength > this.config.maxResponseBytes)
                throw new Error('CosMatter workflow DAG response exceeds configured size');
            if (!response.ok)
                throw new Error(`CosMatter workflow DAG request failed with HTTP ${response.status}`);
            return validateWorkflowDag(JSON.parse(text), runIdValue);
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
}
export function validateWorkflowStatus(value, expectedRunId) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter workflow status response is invalid');
    const result = value;
    const expected = new Set(['schema_version', 'run_id', 'mission_id', 'trust_status', 'next_stage', 'stages']);
    if (Object.keys(result).length !== expected.size || Object.keys(result).some(key => !expected.has(key) || sensitiveKey.test(key)))
        throw new Error('CosMatter workflow status response contains forbidden fields');
    if (result.schema_version !== '1.0' || result.run_id !== expectedRunId || typeof result.mission_id !== 'string' || !result.mission_id || result.trust_status !== 'loopback_workflow_status_not_scientific_evidence' || !(typeof result.next_stage === 'string' || result.next_stage === null) || (typeof result.next_stage === 'string' && !stages.has(result.next_stage)) || !Array.isArray(result.stages) || result.stages.length !== stages.size)
        throw new Error('CosMatter workflow status response is invalid');
    const seen = new Set();
    for (const stage of result.stages) {
        if (!stage || typeof stage !== 'object' || Array.isArray(stage))
            throw new Error('CosMatter workflow stage is invalid');
        const item = stage;
        if (Object.keys(item).length !== 3 || Object.keys(item).some(key => !['stage', 'status', 'counts'].includes(key) || sensitiveKey.test(key)) || typeof item.stage !== 'string' || !stages.has(item.stage) || seen.has(item.stage) || typeof item.status !== 'string' || !states.has(item.status) || !item.counts || typeof item.counts !== 'object' || Array.isArray(item.counts))
            throw new Error('CosMatter workflow stage is invalid');
        for (const [key, count] of Object.entries(item.counts)) {
            if (!key || sensitiveKey.test(key) || typeof count !== 'number' || !Number.isInteger(count) || count < 0 || count > 1_000_000)
                throw new Error('CosMatter workflow count is invalid');
        }
        seen.add(item.stage);
    }
    return result;
}
export function validateArtifactManifest(value, expectedRunId) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter artifact manifest response is invalid');
    const result = value;
    const expected = new Set(['schema_version', 'run_id', 'mission_id', 'trust_status', 'artifact_count', 'artifacts']);
    if (Object.keys(result).length !== expected.size || Object.keys(result).some(key => !expected.has(key) || sensitiveKey.test(key)))
        throw new Error('CosMatter artifact manifest response contains forbidden fields');
    if (result.schema_version !== 'cosmatter.artifact/v1' || result.run_id !== expectedRunId || typeof result.mission_id !== 'string' || !result.mission_id || result.trust_status !== 'allowlisted_artifact_index_not_scientific_evidence' || !Number.isInteger(result.artifact_count) || result.artifact_count < 0 || !Array.isArray(result.artifacts) || result.artifact_count !== result.artifacts.length)
        throw new Error('CosMatter artifact manifest response is invalid');
    const seen = new Set();
    for (const item of result.artifacts) {
        if (!item || typeof item !== 'object' || Array.isArray(item))
            throw new Error('CosMatter artifact card is invalid');
        const card = item;
        const keys = new Set(['artifact_id', 'title', 'media_type', 'sha256', 'generated_at', 'trust_status', 'download_path']);
        if (Object.keys(card).length !== keys.size || Object.keys(card).some(key => !keys.has(key) || sensitiveKey.test(key)) || typeof card.artifact_id !== 'string' || !artifactIds.has(card.artifact_id) || seen.has(card.artifact_id) || typeof card.title !== 'string' || !card.title || card.title.length > 200 || typeof card.media_type !== 'string' || !/^(application\/json|text\/markdown); charset=utf-8$/.test(card.media_type) || typeof card.sha256 !== 'string' || !sha256.test(card.sha256) || typeof card.generated_at !== 'string' || !card.generated_at || typeof card.trust_status !== 'string' || !artifactTrust.has(card.trust_status) || card.download_path !== `/api/runs/${expectedRunId}/artifacts/${card.artifact_id}`)
            throw new Error('CosMatter artifact card is invalid');
        seen.add(card.artifact_id);
    }
    return result;
}
export function validateStageContract(value, expectedRunId) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter stage contract response is invalid');
    const result = value;
    const expected = new Set(['schema_version', 'run_id', 'mission_id', 'trust_status', 'next_stage', 'runtime_safety', 'stages']);
    if (Object.keys(result).length !== expected.size || Object.keys(result).some(key => !expected.has(key) || sensitiveKey.test(key)))
        throw new Error('CosMatter stage contract response contains forbidden fields');
    if (result.schema_version !== 'cosmatter.stage-contract/v1' || result.run_id !== expectedRunId || typeof result.mission_id !== 'string' || !result.mission_id || result.trust_status !== 'loopback_stage_contract_not_scientific_evidence_or_execution_authorization' || !(typeof result.next_stage === 'string' || result.next_stage === null) || (typeof result.next_stage === 'string' && !stages.has(result.next_stage)) || typeof result.runtime_safety !== 'string' || !runtimeSafety.has(result.runtime_safety) || !Array.isArray(result.stages) || result.stages.length !== stages.size)
        throw new Error('CosMatter stage contract response is invalid');
    const seen = new Set();
    let nextStage = null;
    for (const stage of result.stages) {
        if (!stage || typeof stage !== 'object' || Array.isArray(stage))
            throw new Error('CosMatter stage contract stage is invalid');
        const item = stage;
        const fields = new Set(['stage', 'status', 'completion_requirements', 'human_gate', 'expected_outputs', 'recovery_route', 'metrics']);
        if (Object.keys(item).length !== fields.size || Object.keys(item).some(key => !fields.has(key) || sensitiveKey.test(key)) || typeof item.stage !== 'string' || !stages.has(item.stage) || seen.has(item.stage) || typeof item.status !== 'string' || !states.has(item.status) || !Array.isArray(item.completion_requirements) || !Array.isArray(item.expected_outputs) || typeof item.human_gate !== 'string' || typeof item.recovery_route !== 'string' || !item.metrics || typeof item.metrics !== 'object' || Array.isArray(item.metrics))
            throw new Error('CosMatter stage contract stage is invalid');
        const contract = stageContracts[item.stage];
        if (!contract || JSON.stringify(item.completion_requirements) !== JSON.stringify(contract.requirements) || item.human_gate !== contract.humanGate || JSON.stringify(item.expected_outputs) !== JSON.stringify(contract.outputs) || item.recovery_route !== contract.recoveryRoute)
            throw new Error('CosMatter stage contract template is invalid');
        for (const [key, count] of Object.entries(item.metrics)) {
            if (!key || sensitiveKey.test(key) || typeof count !== 'number' || !Number.isInteger(count) || count < 0 || count > 1_000_000)
                throw new Error('CosMatter stage contract metric is invalid');
        }
        if (nextStage === null && item.status !== 'completed')
            nextStage = item.stage;
        seen.add(item.stage);
    }
    if (result.next_stage !== nextStage)
        throw new Error('CosMatter stage contract next stage is invalid');
    return result;
}
export function validateOperationalTelemetry(value, expectedRunId) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter operational telemetry response is invalid');
    const result = value;
    const expected = new Set(['schema_version', 'run_id', 'mission_id', 'trust_status', 'provider_operations', 'dispatch_operations', 'cost_latency_status', 'cost_latency']);
    if (Object.keys(result).length !== expected.size || Object.keys(result).some(key => !expected.has(key) || sensitiveKey.test(key)))
        throw new Error('CosMatter operational telemetry response contains forbidden fields');
    if (result.schema_version !== 'cosmatter.operational-telemetry/v1' || result.run_id !== expectedRunId || typeof result.mission_id !== 'string' || !result.mission_id || result.trust_status !== 'loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence' || !Array.isArray(result.provider_operations) || !Array.isArray(result.dispatch_operations) || typeof result.cost_latency_status !== 'string' || !costLatencyStatus.has(result.cost_latency_status) || !Array.isArray(result.cost_latency))
        throw new Error('CosMatter operational telemetry response is invalid');
    const providerKeys = new Set();
    for (const raw of result.provider_operations) {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw))
            throw new Error('CosMatter provider operation telemetry is invalid');
        const item = raw;
        const fields = new Set(['provider', 'operation', 'request_count', 'successful_response_count', 'client_error_count', 'server_error_count', 'other_status_count']);
        if (Object.keys(item).length !== fields.size || Object.keys(item).some(key => !fields.has(key) || sensitiveKey.test(key)) || (item.provider !== 'sciverse' && item.provider !== 'mineru') || typeof item.operation !== 'string' || !receiptOperations.has(item.operation))
            throw new Error('CosMatter provider operation telemetry is invalid');
        const values = ['request_count', 'successful_response_count', 'client_error_count', 'server_error_count', 'other_status_count'].map(key => item[key]);
        if (values.some(value => typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 10_000_000) || Number(values[0]) !== Number(values[1]) + Number(values[2]) + Number(values[3]) + Number(values[4]) || providerKeys.has(`${item.provider}:${item.operation}`))
            throw new Error('CosMatter provider operation telemetry is invalid');
        providerKeys.add(`${item.provider}:${item.operation}`);
    }
    const dispatchKeys = new Set();
    for (const raw of result.dispatch_operations) {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw))
            throw new Error('CosMatter dispatch operation telemetry is invalid');
        const item = raw;
        const fields = new Set(['operation', 'dispatch_count', 'completed_count', 'incomplete_count', 'unknown_outcome_count']);
        if (Object.keys(item).length !== fields.size || Object.keys(item).some(key => !fields.has(key) || sensitiveKey.test(key)) || typeof item.operation !== 'string' || !dispatchOperations.has(item.operation))
            throw new Error('CosMatter dispatch operation telemetry is invalid');
        const values = ['dispatch_count', 'completed_count', 'incomplete_count', 'unknown_outcome_count'].map(key => item[key]);
        if (values.some(value => typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 10_000_000) || Number(values[0]) !== Number(values[1]) + Number(values[2]) + Number(values[3]) || dispatchKeys.has(item.operation))
            throw new Error('CosMatter dispatch operation telemetry is invalid');
        dispatchKeys.add(item.operation);
    }
    if (result.cost_latency_status !== 'recorded' && result.cost_latency.length)
        throw new Error('CosMatter cost latency telemetry is invalid');
    const costProviders = new Set();
    for (const raw of result.cost_latency) {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw))
            throw new Error('CosMatter cost latency telemetry is invalid');
        const item = raw;
        const fields = new Set(['provider_id', 'request_count', 'successful_request_count', 'failed_request_count', 'currency', 'total_cost', 'median_latency_seconds', 'p95_latency_seconds']);
        if (Object.keys(item).length !== fields.size || Object.keys(item).some(key => !fields.has(key) || sensitiveKey.test(key)) || typeof item.provider_id !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,79}$/.test(item.provider_id) || costProviders.has(item.provider_id) || typeof item.currency !== 'string' || !currencies.has(item.currency))
            throw new Error('CosMatter cost latency telemetry is invalid');
        const requestValues = ['request_count', 'successful_request_count', 'failed_request_count'].map(key => item[key]);
        const valueKeys = ['total_cost', 'median_latency_seconds', 'p95_latency_seconds'];
        if (requestValues.some(value => typeof value !== 'number' || !Number.isInteger(value) || value < 0) || requestValues[0] !== Number(requestValues[1]) + Number(requestValues[2]) || valueKeys.some(key => typeof item[key] !== 'number' || !Number.isFinite(item[key]) || Number(item[key]) < 0) || Number(item.p95_latency_seconds) < Number(item.median_latency_seconds))
            throw new Error('CosMatter cost latency telemetry is invalid');
        costProviders.add(item.provider_id);
    }
    return result;
}
export function validateWorkflowDag(value, expectedRunId) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter workflow DAG response is invalid');
    const result = value;
    const fields = new Set(['schema_version', 'run_id', 'mission_id', 'trust_status', 'dag_id', 'max_concurrency', 'scheduler_status', 'runtime_safety', 'eligible_stages', 'blocked_stage_count', 'human_review_required', 'stages']);
    if (Object.keys(result).length !== fields.size || Object.keys(result).some(key => !fields.has(key) || sensitiveKey.test(key)))
        throw new Error('CosMatter workflow DAG response contains forbidden fields');
    if (result.schema_version !== 'cosmatter.workflow-dag/v1' || result.run_id !== expectedRunId || typeof result.mission_id !== 'string' || !result.mission_id || result.trust_status !== 'loopback_declared_dag_readiness_projection_not_execution_authorization' || result.dag_id !== 'cosmatter_review_gated_linear_workflow' || result.max_concurrency !== 1 || result.scheduler_status !== 'declarative_only_no_execution_authorization' || !runtimeSafety.has(String(result.runtime_safety)) || !Array.isArray(result.eligible_stages) || result.eligible_stages.length > 1 || !Number.isInteger(result.blocked_stage_count) || Number(result.blocked_stage_count) < 0 || Number(result.blocked_stage_count) > stages.size || typeof result.human_review_required !== 'boolean' || !Array.isArray(result.stages) || result.stages.length !== stages.size)
        throw new Error('CosMatter workflow DAG response is invalid');
    let firstUnfinished = null;
    let blocked = 0;
    let waiting = false;
    for (const raw of result.stages) {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw))
            throw new Error('CosMatter workflow DAG stage is invalid');
        const item = raw;
        const keys = new Set(['stage', 'depends_on', 'status', 'allowed_descriptors', 'data_classification', 'execution_class']);
        if (Object.keys(item).length !== keys.size || Object.keys(item).some(key => !keys.has(key) || sensitiveKey.test(key)) || typeof item.stage !== 'string' || !stages.has(item.stage) || typeof item.status !== 'string' || !states.has(item.status) || !Array.isArray(item.depends_on) || !Array.isArray(item.allowed_descriptors))
            throw new Error('CosMatter workflow DAG stage is invalid');
        const spec = dagSpecs[item.stage];
        if (!spec || JSON.stringify(item.depends_on) !== JSON.stringify(spec.dependsOn) || JSON.stringify(item.allowed_descriptors) !== JSON.stringify(spec.descriptors) || item.data_classification !== spec.dataClassification || item.execution_class !== spec.executionClass)
            throw new Error('CosMatter workflow DAG template is invalid');
        if (firstUnfinished === null && item.status !== 'completed')
            firstUnfinished = item.stage;
        blocked += item.status === 'blocked' ? 1 : 0;
        waiting ||= item.status === 'waiting_human_review';
    }
    const expectedEligible = firstUnfinished !== null && result.runtime_safety === 'verified' && result.stages.find(raw => raw.stage === firstUnfinished).status === 'ready' ? [firstUnfinished] : [];
    if (JSON.stringify(result.eligible_stages) !== JSON.stringify(expectedEligible) || result.blocked_stage_count !== blocked || result.human_review_required !== waiting)
        throw new Error('CosMatter workflow DAG status is invalid');
    return result;
}
