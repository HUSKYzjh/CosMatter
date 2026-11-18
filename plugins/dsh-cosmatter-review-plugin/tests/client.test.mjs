import assert from 'node:assert/strict'
import test from 'node:test'
import { CosMatterReviewClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'
const template = { run_id: 'run_1', trust_status: 'blank_human_candidate_screening_template_not_a_result', candidate_count: 1, candidates: [{ document_id: 'doc-1', title: 'Candidate', source: 'Sciverse', publication_year: 2025 }], decisions: [{ document_id: 'doc-1', decision: 'unreviewed', reason_codes: [] }] }
const recorded = { run_id: 'run_1', candidate_count: 1, decision_counts: { include_for_fulltext: 1 }, trust_status: 'human_reviewed_candidate_screening_not_scientific_evidence' }
const decisions = [{ document_id: 'doc-1', decision: 'include_for_fulltext', reason_codes: ['material_match', 'property_match'] }]
test('reads recorded human decisions and can send the matching checklist revision', async () => {
  const revision = 'a'.repeat(64)
  const stored = { ...template, decisions, trust_status: recorded.trust_status, checklist_revision: revision }
  const client = new CosMatterReviewClient({}, async (_url, options) => {
    if (options.method === 'POST') {
      assert.deepEqual(JSON.parse(options.body), { decisions, checklist_revision: revision })
      return new Response(JSON.stringify(recorded))
    }
    return new Response(JSON.stringify(stored))
  })
  assert.deepEqual(await client.template('run_1'), stored)
  await client.record('run_1', decisions, undefined, revision)
  const mismatched = { ...stored, decisions: [{ ...decisions[0], document_id: 'different-doc' }] }
  const invalid = new CosMatterReviewClient({}, async () => new Response(JSON.stringify(mismatched)))
  await assert.rejects(() => invalid.template('run_1'), /identities/)
})
test('client keeps screening metadata bounded and requires full decisions', async () => { assert.throws(() => new CosMatterReviewClient({ baseUrl: 'https://example.com' })); const responses = [template, recorded]; const client = new CosMatterReviewClient({}, async () => new Response(JSON.stringify(responses.shift()), { status: 200 })); assert.equal((await client.template('run_1')).candidate_count, 1); assert.equal((await client.record('run_1', decisions)).candidate_count, 1); await assert.rejects(() => client.record('run_1', [{ ...decisions[0], reason_codes: [] }]), /invalid/) })
test('DSH screening links target the validated revision and configured loopback port', async (context) => {
  const tools = []
  const events = []
  let dispose
  const revision = 'a'.repeat(64)
  const responses = [{ ...template, checklist_revision: revision }, template, recorded]
  context.mock.method(globalThis, 'fetch', async () => Response.json(responses.shift()))
  apply({
    tools: { register: tool => tools.push(tool) },
    emit: (event, payload) => events.push([event, payload]),
    effect: effect => { dispose = effect() },
  }, { baseUrl: 'http://127.0.0.1:8789' })
  assert.equal(name, 'cosmatter-review')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_candidate_screening_template', 'cosmatter_candidate_screening_record'])
  const exec = { signal: new AbortController().signal }
  const saved = await tools[0].execute({ run_id: 'run_1' }, exec)
  assert.equal(saved.workbench_url, `http://127.0.0.1:8789/?api=local#run=run_1&screening=${revision}`)
  const legacy = await tools[0].execute({ run_id: 'run_1' }, exec)
  assert.deepEqual(legacy, template)
  const result = await tools[1].execute({ run_id: 'run_1', decisions }, exec)
  assert.equal(result.candidate_count, 1)
  assert.deepEqual(events.map(item => item[0]), ['cosmatter-review/template-read', 'cosmatter-review/template-read', 'cosmatter-review/recorded'])
  dispose()
})
