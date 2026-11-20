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
  const response = { run_id: 'run_1', mission_id: 'mission_1', trust_status: 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion', query_sha256: 'a'.repeat(64), results: [{ evidence_id: '证据 + y=2', document_id: '文献 & x=1', claim: 'Reviewed claim', stance: 'support', material: 'BiFeO3', property_name: 'phase stability', conditions: { strain_percent: 1 }, locator: 'figure:2', source: 'fixture', score: 2 }] }
  let output = response
  const client = new CosMatterLoopbackClient({ baseUrl: 'http://127.0.0.1:8790' }, async (url, init) => {
    assert.equal(url.origin, 'http://127.0.0.1:8790')
    assert.equal(init.redirect, 'error')
    return new Response(JSON.stringify(output), { status: 200 })
  })
  const search = () => client.searchAcceptedEvidence('run_1', 'strain phase stability')
  const result = await search()
  assert.equal(result.results.length, 1)
  const link = new URL(result.results[0].workbench_url)
  assert.equal(link.origin, 'http://127.0.0.1:8790')
  assert.equal(link.search, '?api=local')
  assert.deepEqual(Object.fromEntries(new URLSearchParams(link.hash.slice(1))), { run: 'run_1', document: '文献 & x=1', evidence: '证据 + y=2' })
  output = { ...response, results: [{ ...response.results[0], reader_available: false }] }
  const unavailable = await search()
  assert.equal(unavailable.results[0].evidence_id, response.results[0].evidence_id)
  assert.equal(unavailable.results[0].workbench_url, undefined)
  output = { ...response, run_id: 'another_run' }
  await assert.rejects(search, /response is invalid/)
  output = { ...response, results: [{ ...response.results[0], workbench_url: 'https://example.org/' }] }
  await assert.rejects(search, /response is invalid/)
  output = { ...response, quote: 'A body that must stay local' }
  await assert.rejects(search, /response is invalid/)
})

test('exact evidence search submits only the selected identifier and rejects a different card', async () => {
  const hit = { evidence_id: "ev'id", document_id: 'doc_1', claim: 'Reviewed claim', locator: 'figure:2', source: 'fixture', score: 1 }
  const response = { run_id: 'run_1', mission_id: 'mission_1', trust_status: 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion', query_sha256: 'a'.repeat(64), match_mode: 'exact_id', results: [hit] }
  const client = new CosMatterLoopbackClient({}, async (_url, init) => {
    assert.deepEqual(JSON.parse(init.body), { evidence_id: "ev'id", limit: 1 })
    return new Response(JSON.stringify(response), { status: 200 })
  })
  const exact = () => client.searchAcceptedEvidence('run_1', { evidenceId: "ev'id" }, 1)
  const result = await exact()
  assert.match(result.results[0].workbench_url, /evidence=ev%27id$/)
  hit.evidence_id = 'similar_id'
  await assert.rejects(exact, /exact response is invalid/)
})

test('DSH forwards exact document and locator and keeps separate card links at the same position', async t => {
  const documentId = 'Paper & XRD'
  const locator = 'table:' + 'strain-'.repeat(15) + 'row 2'
  const hit = { document_id: documentId, locator, evidence_id: 'card_1', claim: 'First reading', source: 'fixture', score: 1 }
  const hits = [hit, { ...hit, evidence_id: 'card_2', claim: 'Second reading' }]
  const args = { run_id: 'run_1', document_id: documentId, locator, limit: 2 }
  let response = { run_id: args.run_id, mission_id: 'mission_1', trust_status: 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion',
    query_sha256: 'a'.repeat(64), match_mode: 'exact_locator', matched_count: 3, results: hits }
  const fetch = t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url.href, 'http://127.0.0.1:8790/api/runs/run_1/accepted-evidence/search')
    assert.deepEqual(JSON.parse(init.body), { document_id: documentId, locator, limit: 2 })
    return Response.json(response)
  })
  const tools = []
  apply({ tools: { register: tool => tools.push(tool) }, emit() {}, effect() {} }, { baseUrl: 'http://127.0.0.1:8790' })
  const tool = tools.find(tool => tool.name === 'cosmatter_accepted_evidence_search')
  const execute = (input = args) => tool.execute(input, { signal: new AbortController().signal })
  for (const invalid of [{ run_id: args.run_id, document_id: documentId }, { run_id: args.run_id, locator }, { ...args, query: 'strain' }, { ...args, evidence_id: 'card_1' }]) {
    await assert.rejects(() => execute(invalid), /locator together/)
  }
  assert.equal(fetch.mock.callCount(), 0)
  const result = await execute()
  const meta = tool.output.presentationMeta(args, result)
  const card = tool.presentResult(args, { isError: false, meta })
  for (const [index, entry] of result.results.entries()) {
    const url = new URL(entry.workbench_url)
    assert.deepEqual(Object.fromEntries(new URLSearchParams(url.hash.slice(1))), { run: args.run_id, document: documentId, evidence: hits[index].evidence_id })
    assert.ok(card.content[0].text.includes(entry.workbench_url))
    assert.ok(card.content[0].text.includes(locator))
  }
  assert.ok(card.content[0].text.includes('Showing 2 of 3 matching cards.'))
  assert.equal(tool.presentResult({ ...args, locator: 'table:3' }, { isError: false, meta }), undefined)
  for (const invalid of [{ match_mode: undefined }, { matched_count: 1 }, { results: [hit, hit] },
    { results: [hit, { ...hits[1], locator: 'table:3' }] }, { results: [hit, { ...hits[1], document_id: 'other' }] }]) {
    const saved = response
    response = { ...saved, ...invalid }
    await assert.rejects(() => execute(), /location response is invalid/)
    response = saved
  }
})

test('DSH presents accepted cards with bounded previews and verified reader links', async t => {
  const hit = { evidence_id: "证据 + '1", document_id: '文献 & x=1', claim: 'Reviewed claim\n' + 'x'.repeat(200), locator: 'figure:2', source: 'fixture', score: 1 }
  const response = { run_id: 'run_1', mission_id: 'mission_1', trust_status: 'accepted_evidence_search_not_new_evidence_or_scientific_conclusion',
    query_sha256: 'a'.repeat(64), match_mode: 'exact_id', results: [hit] }
  t.mock.method(globalThis, 'fetch', async () => Response.json(response))
  const tools = []
  apply({ tools: { register: tool => tools.push(tool) }, emit() {}, effect() {} }, { baseUrl: 'http://127.0.0.1:8790' })
  const tool = tools.find(item => item.name === 'cosmatter_accepted_evidence_search')
  const args = { run_id: 'run_1', evidence_id: hit.evidence_id, limit: 1 }
  const result = await tool.execute(args, { signal: new AbortController().signal })
  const content = tool.output.render(args, result)
  assert.equal(JSON.parse(content[0].text).results[0].claim, hit.claim)
  const meta = tool.output.presentationMeta(args, result)
  const card = tool.presentResult(args, { content, meta, isError: false })
  assert.equal(card.title, 'Accepted CosMatter evidence')
  const [id, preview, locator, url] = card.content[0].text.split('\n')
  assert.equal(id, hit.evidence_id)
  assert.match(preview, /^Reviewed claim x+…$/)
  assert.equal(preview.length, 180)
  assert.equal(locator, hit.locator)
  assert.equal(url, result.results[0].workbench_url)
  assert.equal(tool.presentResult(args, { content, meta: [{ ...meta[0], workbench_url: 'https://example.invalid/' }], isError: false }), undefined)
  assert.equal(tool.presentResult({ ...args, evidence_id: 'different' }, { content, meta, isError: false }), undefined)
  assert.equal(tool.presentResult(args, { content, meta, isError: true }), undefined)
  assert.equal(tool.presentResult(args, { content, meta: [], isError: false }).content[0].text, 'No accepted evidence cards matched.')
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
