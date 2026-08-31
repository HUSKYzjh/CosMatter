import assert from 'node:assert/strict'
import test from 'node:test'

import { CosMatterObservabilityClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const stageNames = ['intake', 'plan', 'retrieval', 'screening', 'parse', 'extraction', 'gap', 'report', 'evaluation']
const status = {
  schema_version: '1.0', run_id: 'run_001', mission_id: 'mission_abcdef12',
  trust_status: 'loopback_workflow_status_not_scientific_evidence', next_stage: 'screening',
  stages: stageNames.map((stage, index) => ({ stage, status: index < 3 ? 'completed' : 'waiting_human_review', counts: { item_count: index } })),
}
const artifacts = {
  schema_version: 'cosmatter.artifact/v1', run_id: 'run_001', mission_id: 'mission_abcdef12',
  trust_status: 'allowlisted_artifact_index_not_scientific_evidence', artifact_count: 1,
  artifacts: [{ artifact_id: 'ui_bundle', title: 'Safe UI export', media_type: 'application/json; charset=utf-8', sha256: 'a'.repeat(64), generated_at: '2026-08-29T00:00:00+00:00', trust_status: 'browser_safe_export_from_reviewed_artifacts', download_path: '/api/runs/run_001/artifacts/ui_bundle' }],
}
const contractTemplates = {
  intake: [['mission_boundary_recorded'], 'mission_definition', ['mission_brief'], 'mission_boundary_review'],
  plan: [['approved_flight_plan'], 'plan_approval', ['approved_flight_plan'], 'plan_review'],
  retrieval: [['approved_queries_executed', 'provider_receipt_links_valid'], 'mission_scoped_egress_consent', ['retrieval_candidate_history', 'provider_receipt_links'], 'authorized_retrieval_review'],
  screening: [['candidate_fingerprint_current', 'human_candidate_screening_complete'], 'candidate_screening', ['candidate_screening_decision'], 'candidate_screening_review'],
  parse: [['fulltext_access_confirmed', 'mineru_task_receipts_linked'], 'content_access_and_parse_consent', ['source_parse_task_ledger'], 'content_access_review'],
  extraction: [['human_source_map_recorded', 'human_evidence_decision_recorded'], 'source_map_and_evidence_review', ['source_map', 'material_fact', 'verification_decision'], 'source_map_review'],
  gap: [['accepted_evidence_conditions_compared', 'counterevidence_boundary_executed'], 'gap_candidate_review', ['research_gap_candidate'], 'counterevidence_review'],
  report: [['review_gated_inputs_available', 'report_audit_valid'], 'report_review', ['review_gated_report'], 'report_audit_review'],
  evaluation: [['required_human_metric_families_complete'], 'evaluation_review', ['human_evaluation_summary'], 'evaluation_review'],
}
const contract = {
  schema_version: 'cosmatter.stage-contract/v1', run_id: 'run_001', mission_id: 'mission_abcdef12',
  trust_status: 'loopback_stage_contract_not_scientific_evidence_or_execution_authorization', next_stage: 'screening', runtime_safety: 'verified',
  stages: stageNames.map((stage, index) => {
    const [completion_requirements, human_gate, expected_outputs, recovery_route] = contractTemplates[stage]
    return { stage, status: index < 3 ? 'completed' : 'waiting_human_review', completion_requirements, human_gate, expected_outputs, recovery_route, metrics: { item_count: index } }
  }),
}
const telemetry = {
  schema_version: 'cosmatter.operational-telemetry/v1', run_id: 'run_001', mission_id: 'mission_abcdef12',
  trust_status: 'loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence',
  provider_operations: [{ provider: 'sciverse', operation: 'agentic_search', request_count: 2, successful_response_count: 1, client_error_count: 1, server_error_count: 0, other_status_count: 0 }],
  dispatch_operations: [{ operation: 'metadata_query', dispatch_count: 2, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 1 }],
  cost_latency_status: 'not_recorded', cost_latency: [],
}
const dagSpecs = {
  intake: [[], ['mission.define'], 'mission', 'local_review_gated'], plan: [['intake'], ['planning.orchestrate'], 'mission', 'local_review_gated'], retrieval: [['plan'], ['literature.metadata_retrieval', 'literature.deduplicate_and_rank'], 'public_metadata', 'explicit_consent_required'], screening: [['retrieval'], [], 'public_metadata', 'human_review_required'], parse: [['screening'], ['document.mineru_private_parse'], 'private_fulltext', 'explicit_consent_required'], extraction: [['parse'], ['evidence.material_extract', 'evidence.source_map', 'evidence.verify'], 'reviewable_excerpt', 'human_review_required'], gap: [['extraction'], ['research.gap_candidates'], 'accepted_evidence', 'human_review_required'], report: [['gap'], ['report.generate'], 'accepted_evidence', 'local_review_gated'], evaluation: [['report'], [], 'run_summary', 'human_review_required'],
}
const dag = {
  schema_version: 'cosmatter.workflow-dag/v1', run_id: 'run_001', mission_id: 'mission_abcdef12', trust_status: 'loopback_declared_dag_readiness_projection_not_execution_authorization', dag_id: 'cosmatter_review_gated_linear_workflow', max_concurrency: 1, scheduler_status: 'declarative_only_no_execution_authorization', runtime_safety: 'verified', eligible_stages: [], blocked_stage_count: 0, human_review_required: true,
  stages: stageNames.map((stage, index) => { const [depends_on, allowed_descriptors, data_classification, execution_class] = dagSpecs[stage]; return { stage, depends_on, status: index < 3 ? 'completed' : 'waiting_human_review', allowed_descriptors, data_classification, execution_class } }),
}

test('client reads only a bounded workflow-status projection', async () => {
  let request
  const client = new CosMatterObservabilityClient({}, async (url, options) => {
    request = { url: String(url), options }
    return new Response(JSON.stringify(status), { status: 200 })
  })
  const result = await client.workflowStatus('run_001')
  assert.equal(result.next_stage, 'screening')
  assert.equal(request.url, 'http://127.0.0.1:8765/api/runs/run_001/workflow-status')
  assert.equal(request.options.method, 'GET')
})

test('client rejects non-loopback endpoints and sensitive response fields', async () => {
  assert.throws(() => new CosMatterObservabilityClient({ baseUrl: 'https://example.com' }))
  const client = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify({ ...status, private_path: 'nope' }), { status: 200 }))
  await assert.rejects(() => client.workflowStatus('run_001'), /forbidden fields/)
})

test('client reads only fixed artifact cards and rejects arbitrary download paths', async () => {
  const client = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify(artifacts), { status: 200 }))
  const result = await client.artifactManifest('run_001')
  assert.equal(result.artifacts[0].artifact_id, 'ui_bundle')
  const unsafe = structuredClone(artifacts); unsafe.artifacts[0].download_path = '/api/runs/run_001/pdf/private'
  const unsafeClient = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify(unsafe), { status: 200 }))
  await assert.rejects(() => unsafeClient.artifactManifest('run_001'), /artifact card is invalid/)
})

test('client reads a fixed non-executing stage contract and rejects changed recovery routes', async () => {
  let request
  const client = new CosMatterObservabilityClient({}, async url => {
    request = String(url)
    return new Response(JSON.stringify(contract), { status: 200 })
  })
  const result = await client.stageContract('run_001')
  assert.equal(result.stages[1].recovery_route, 'plan_review')
  assert.equal(request, 'http://127.0.0.1:8765/api/runs/run_001/stage-contract')
  const unsafe = structuredClone(contract); unsafe.stages[0].recovery_route = 'execute_arbitrary_command'
  const unsafeClient = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify(unsafe), { status: 200 }))
  await assert.rejects(() => unsafeClient.stageContract('run_001'), /template is invalid/)
})

test('client reads only aggregate telemetry and rejects a mismatched count', async () => {
  let request
  const client = new CosMatterObservabilityClient({}, async url => {
    request = String(url)
    return new Response(JSON.stringify(telemetry), { status: 200 })
  })
  const result = await client.operationalTelemetry('run_001')
  assert.equal(result.dispatch_operations[0].unknown_outcome_count, 1)
  assert.equal(request, 'http://127.0.0.1:8765/api/runs/run_001/operational-telemetry')
  const unsafe = structuredClone(telemetry); unsafe.provider_operations[0].request_count = 3
  const unsafeClient = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify(unsafe), { status: 200 }))
  await assert.rejects(() => unsafeClient.operationalTelemetry('run_001'), /provider operation telemetry is invalid/)
})

test('client reads a fixed DAG but rejects scheduler-like mutations', async () => {
  let request
  const client = new CosMatterObservabilityClient({}, async url => { request = String(url); return new Response(JSON.stringify(dag), { status: 200 }) })
  const result = await client.workflowDag('run_001')
  assert.equal(result.max_concurrency, 1)
  assert.equal(request, 'http://127.0.0.1:8765/api/runs/run_001/workflow-dag')
  const unsafe = structuredClone(dag); unsafe.max_concurrency = 2
  const unsafeClient = new CosMatterObservabilityClient({}, async () => new Response(JSON.stringify(unsafe), { status: 200 }))
  await assert.rejects(() => unsafeClient.workflowDag('run_001'), /workflow DAG response is invalid/)
})

test('DSH apply registers only read-only observability tools', async () => {
  const tools = []; const events = []; let dispose
  const originalFetch = globalThis.fetch
  globalThis.fetch = async url => new Response(JSON.stringify(String(url).endsWith('/artifacts') ? artifacts : String(url).endsWith('/stage-contract') ? contract : String(url).endsWith('/operational-telemetry') ? telemetry : String(url).endsWith('/workflow-dag') ? dag : status), { status: 200 })
  apply({ tools: { register: tool => tools.push(tool) }, emit: (event, payload) => events.push([event, payload]), effect: effect => { dispose = effect() } })
  assert.equal(name, 'cosmatter-observability')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_workflow_status', 'cosmatter_artifact_manifest', 'cosmatter_stage_contract', 'cosmatter_operational_telemetry', 'cosmatter_workflow_dag'])
  const result = await tools[0].execute({ run_id: 'run_001' }, { signal: new AbortController().signal })
  assert.equal(result.next_stage, 'screening')
  assert.equal(events[0][0], 'cosmatter-observability/workflow-read')
  const manifest = await tools[1].execute({ run_id: 'run_001' }, { signal: new AbortController().signal })
  assert.equal(manifest.artifact_count, 1)
  assert.equal(events[1][0], 'cosmatter-observability/artifact-read')
  const stageContract = await tools[2].execute({ run_id: 'run_001' }, { signal: new AbortController().signal })
  assert.equal(stageContract.runtime_safety, 'verified')
  assert.equal(events[2][0], 'cosmatter-observability/stage-contract-read')
  const telemetryResult = await tools[3].execute({ run_id: 'run_001' }, { signal: new AbortController().signal })
  assert.equal(telemetryResult.provider_operations.length, 1)
  assert.equal(events[3][0], 'cosmatter-observability/telemetry-read')
  const dagResult = await tools[4].execute({ run_id: 'run_001' }, { signal: new AbortController().signal })
  assert.equal(dagResult.scheduler_status, 'declarative_only_no_execution_authorization')
  assert.equal(events[4][0], 'cosmatter-observability/dag-read')
  dispose()
  globalThis.fetch = originalFetch
})
