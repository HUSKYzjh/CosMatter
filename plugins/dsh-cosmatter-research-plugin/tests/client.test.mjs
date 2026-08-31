import assert from 'node:assert/strict'
import test from 'node:test'

import { CosMatterResearchClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const draft = { run_id: 'run_1', trust_status: 'untrusted_draft', content: '{"queries":["bounded query"]}' }
const approved = { run_id: 'run_1', plan_id: 'plan_123456789abc', queries: ['bounded query'], counter_queries: ['bounded counter query'] }
const query = { run_id: 'run_1', query_kind: 'primary', query_index: 0, sources: ['sciverse'], source_counts: { Sciverse: 1 }, candidate_count: 1, candidates: [{ candidate_id: 'candidate_1', created_at: '2026-01-01T00:00:00Z', deduplication: {}, document_id: 'doc-1', doi: null, is_content_accessible: false, locator_hint: null, publication_year: 2025, query: 'bounded query', retrieval_origins: [], score: 0.9, source: 'Sciverse', title: 'Bounded paper' }] }

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

test('DSH apply registers only the explicit-consent research tools', async () => {
  const tools = []; const events = []; let dispose
  const responses = [draft, approved, query]
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify(responses.shift()), { status: 200 })
  apply({ tools: { register: tool => tools.push(tool) }, emit: (event, payload) => events.push([event, payload]), effect: effect => { dispose = effect() } })
  assert.equal(name, 'cosmatter-research')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_research_plan_draft', 'cosmatter_research_plan_approve', 'cosmatter_research_query_execute'])
  await tools[0].execute({ run_id: 'run_1', authorizations: ['mission_scoped_egress_consent', 'deepseek_request_consent'] }, { signal: new AbortController().signal })
  await tools[1].execute({ run_id: 'run_1', subquestions: ['question'], queries: ['bounded query'], counter_queries: ['bounded counter query'] }, { signal: new AbortController().signal })
  const result = await tools[2].execute({ run_id: 'run_1', authorizations: ['mission_scoped_egress_consent', 'metadata_provider_consent'], query_index: 0, sources: ['sciverse'] }, { signal: new AbortController().signal })
  assert.equal(result.candidate_count, 1)
  assert.deepEqual(events.map(event => event[0]), ['cosmatter-research/plan-drafted', 'cosmatter-research/plan-approved', 'cosmatter-research/query-executed'])
  dispose(); globalThis.fetch = originalFetch
})
