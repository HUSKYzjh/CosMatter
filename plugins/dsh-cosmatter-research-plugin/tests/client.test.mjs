import assert from 'node:assert/strict'
import test from 'node:test'

import { CosMatterResearchClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const draft = { run_id: 'run_1', trust_status: 'untrusted_draft', content: '{"queries":["bounded query"]}' }
const approved = { run_id: 'run_1', plan_id: 'plan_123456789abc', queries: ['bounded query'], counter_queries: ['bounded counter query'] }
const query = { run_id: 'run_1', query_kind: 'primary', query_index: 0, sources: ['sciverse'], source_counts: { Sciverse: 1 }, candidate_count: 1, candidates: [{ candidate_id: 'candidate_1', created_at: '2026-01-01T00:00:00Z', deduplication: {}, document_id: 'doc-1', doi: null, is_content_accessible: false, locator_hint: null, publication_year: 2025, query: 'bounded query', retrieval_origins: [], score: 0.9, source: 'Sciverse', title: 'Bounded paper' }] }
const stage = {
  run_id: 'run_1', schema_version: 'cosmatter.stage-contract/v1',
  trust_status: 'loopback_stage_contract_not_scientific_evidence_or_execution_authorization',
  next_stage: 'screening', runtime_safety: 'verified',
}
const checklist = {
  run_id: 'run_1', checklist_revision: 'a'.repeat(64), candidate_count: 1, candidates: [{ document_id: 'doc-1' }],
  trust_status: 'blank_human_candidate_screening_template_not_a_result',
}
const queryArgs = { run_id: 'run_1', authorizations: ['mission_scoped_egress_consent', 'metadata_provider_consent'], query_index: 0, sources: ['sciverse'] }

test('client requires exact external authorizations and rejects non-loopback endpoints', async () => {
  assert.throws(() => new CosMatterResearchClient({ baseUrl: 'https://example.com' }))
  const client = new CosMatterResearchClient({}, async () => new Response(JSON.stringify(draft), { status: 200 }))
  await assert.rejects(() => client.draftPlan('run_1', ['mission_scoped_egress_consent'], 'call-0001'), /explicit research authorization/)
  assert.equal((await client.draftPlan('run_1', ['deepseek_request_consent', 'mission_scoped_egress_consent'], 'call-0002')).trust_status, 'untrusted_draft')
})

test('client keeps approved plans and metadata candidates bounded', async () => {
  const responses = [approved, query]
  const client = new CosMatterResearchClient({}, async () => new Response(JSON.stringify(responses.shift()), { status: 200 }))
  assert.equal((await client.approvePlan('run_1', { subquestions: ['question'], queries: ['bounded query'], counter_queries: ['bounded counter query'] })).plan_id, approved.plan_id)
  assert.equal((await client.executeQuery('run_1', { authorizations: ['metadata_provider_consent', 'mission_scoped_egress_consent'], query_index: 0, sources: ['sciverse'] }, 'call-0003')).candidate_count, 1)
})

test('DSH registers research and offline calculation tools and preserves research dispatch events', async t => {
  const tools = []; const events = []; let dispose
  const responses = [draft, approved, query]
  t.mock.method(globalThis, 'fetch', async (_url, init) =>
    init.method === 'POST' ? Response.json(responses.shift()) : new Response(null, { status: 404 }))
  apply({ tools: { register: tool => tools.push(tool) }, emit: (event, payload) => events.push([event, payload]), effect: effect => { dispose = effect() } })
  assert.equal(name, 'cosmatter-research')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_research_plan_draft', 'cosmatter_research_plan_approve', 'cosmatter_research_query_execute', 'cosmatter_pst_occupancy_count', 'cosmatter_md_field_response'])
  await tools[0].execute({ run_id: 'run_1', authorizations: ['mission_scoped_egress_consent', 'deepseek_request_consent'] }, { signal: new AbortController().signal, callId: 'call-0004' })
  await tools[1].execute({ run_id: 'run_1', subquestions: ['question'], queries: ['bounded query'], counter_queries: ['bounded counter query'] }, { signal: new AbortController().signal })
  const result = await tools[2].execute(queryArgs, { signal: new AbortController().signal, callId: 'call-0005' })
  assert.equal(result.candidate_count, 1)
  assert.equal(result.workbench_url, 'http://127.0.0.1:8765/?api=local#run=run_1')
  assert.equal(result.screening_revision, undefined)
  assert.deepEqual(events.map(event => event[0]), ['cosmatter-research/plan-drafted', 'cosmatter-research/plan-approved', 'cosmatter-research/query-executed'])
  dispose()
})

test('retrieval returns an exact screening link only after the local handoff is verified', async t => {
  const calls = []
  let contract = { ...stage, next_stage: 'retrieval' }
  let screening = checklist
  const origin = 'http://127.0.0.1:8792'
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url.origin, origin)
    assert.equal(init.redirect, 'error')
    const action = url.pathname.split('/').at(-1)
    calls.push([init.method, action])
    if (action === 'authorized-execute-query') return Response.json({ ...query, workbench_url: 'https://example.invalid/forged' })
    if (action === 'stage-contract') return Response.json(contract)
    return Response.json(screening)
  })
  const tools = []
  apply({ tools: { register: tool => tools.push(tool) }, emit() {}, effect() {} }, { baseUrl: origin })
  const tool = tools.find(item => item.name === 'cosmatter_research_query_execute')
  const execute = () => tool.execute(queryArgs, { signal: new AbortController().signal, callId: 'call-0006' })
  const runLink = origin + '/?api=local#run=run_1'
  const early = await execute()
  assert.equal(early.workbench_url, runLink)
  assert.equal(early.screening_revision, undefined)
  assert.deepEqual(calls.splice(0), [['POST', 'authorized-execute-query'], ['GET', 'stage-contract']])
  contract = stage
  const result = await execute()
  assert.equal(result.screening_revision, checklist.checklist_revision)
  assert.equal(result.workbench_url, runLink + '&screening=' + checklist.checklist_revision)
  assert.deepEqual(calls.splice(0), [['POST', 'authorized-execute-query'], ['GET', 'stage-contract'], ['GET', 'candidate-screening']])
  const content = tool.output.render(queryArgs, result)
  assert.deepEqual(JSON.parse(content[0].text).candidates, query.candidates)
  const meta = tool.output.presentationMeta(queryArgs, result)
  assert.equal(tool.presentResult(queryArgs, { content, meta, isError: false }).content[0].text,
    '1 metadata candidate\nOpen the screening checklist\n' + result.workbench_url)
  assert.equal(tool.presentResult(queryArgs, { content, meta: { ...meta, workbench_url: runLink }, isError: false }), undefined)
  screening = { ...checklist, run_id: 'different_run' }
  assert.equal((await execute()).workbench_url, runLink)
  screening = { ...checklist, candidate_count: 0, candidates: [] }
  assert.equal((await execute()).workbench_url, runLink)
})
