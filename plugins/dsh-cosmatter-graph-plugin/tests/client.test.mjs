import assert from 'node:assert/strict'
import test from 'node:test'

import { CosMatterLoopbackClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const graph = {
  schema_version: '1.0', graph_id: `graph:${'a'.repeat(32)}`, mission_id: 'mission_1',
  trust_status: 'accepted_evidence_projection_not_scientific_conclusion', source_artifact_hashes: ['a'.repeat(64)],
  nodes: [
    { node_id: `mission:${'b'.repeat(32)}`, node_type: 'Mission', label: 'BiFeO3', attributes: {} },
    { node_id: `evidence:${'c'.repeat(32)}`, node_type: 'EvidenceCard', label: 'evidence-1', attributes: { review_status: 'accepted', claim_digest: 'x', provenance_digest: 'y' } },
  ], edges: [],
}

test('client permits an allowlisted loopback graph response', async () => {
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify(graph), { status: 200 }))
  assert.equal((await client.graph('run_1')).graph_id, graph.graph_id)
})

test('client rejects a non-loopback endpoint and raw evidence content', async () => {
  assert.throws(() => new CosMatterLoopbackClient({ baseUrl: 'https://example.com' }))
  const invalid = structuredClone(graph)
  invalid.nodes[1].attributes.quote = 'private text'
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify(invalid), { status: 200 }))
  await assert.rejects(() => client.graph('run_1'), /forbidden raw content/)
})

test('client accepts a bounded single-type page but validates its controls', async () => {
  const page = structuredClone(graph)
  page.nodes = [page.nodes[1]]
  page.page = { node_types: ['EvidenceCard'], offset: 0, limit: 25, node_total: 1, edge_count: 0, truncated: false, empty_result_meaning: 'No matching nodes in this bounded mission graph page; this does not establish a global absence.' }
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify(page), { status: 200 }))
  assert.equal((await client.graph('run_1', { nodeType: 'EvidenceCard' })).nodes.length, 1)
})

test('review requests accept only pending-human-review responses', async () => {
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify({ status: 'pending_human_review_not_evidence_acceptance', request_id: 'review_1' }), { status: 200 }))
  const result = await client.requestReview('run_1', [`evidence:${'c'.repeat(32)}`], 'Check relation semantics.')
  assert.equal(result.status, 'pending_human_review_not_evidence_acceptance')
})

test('graph plan drafts accept only the untrusted local response', async () => {
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify({ trust_status: 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance', graph_id: graph.graph_id }), { status: 200 }))
  const result = await client.draftPlan('run_1', [`evidence:${'c'.repeat(32)}`], 'Inspect relation semantics.')
  assert.equal(result.trust_status, 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance')
})

test('accepted-evidence search accepts only safe reviewed-card pointers', async () => {
  const response = { mission_id: 'mission_1', trust_status: 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion', query_sha256: 'a'.repeat(64), results: [{ evidence_id: 'evidence_1', document_id: 'doc_1', claim: 'Reviewed claim', stance: 'support', material: 'BiFeO3', property_name: 'phase stability', conditions: { strain_percent: 1 }, locator: 'figure:2', source: 'fixture', score: 2 }] }
  const client = new CosMatterLoopbackClient({}, async () => new Response(JSON.stringify(response), { status: 200 }))
  assert.equal((await client.searchAcceptedEvidence('run_1', 'strain phase stability')).results.length, 1)
})

test('DSH apply registers the bounded query and plan tools', async () => {
  const tools = []
  const events = []
  let dispose
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({
    mission_id: 'mission_1', graph_id: graph.graph_id, node_ids: [`evidence:${'c'.repeat(32)}`], intent: 'Inspect accepted evidence conflicts.',
    proposed_action: 'request_human_to_review_or_project_graph', trust_status: 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance',
  }), { status: 200 })
  apply({
    tools: { register: tool => tools.push(tool) },
    emit: (event, payload) => events.push([event, payload]),
    effect: effect => { dispose = effect() },
  })
  assert.equal(name, 'cosmatter-graph')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_graph_query', 'cosmatter_accepted_evidence_search', 'cosmatter_graph_review_request', 'cosmatter_graph_plan'])
  const plan = await tools[3].execute(
    { run_id: 'run_1', node_ids: [`evidence:${'c'.repeat(32)}`], intent: 'Inspect accepted evidence conflicts.' },
    { signal: new AbortController().signal },
  )
  assert.equal(plan.trust_status, 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance')
  assert.equal(events[0][0], 'cosmatter-graph/plan-created')
  dispose()
  globalThis.fetch = originalFetch
})
