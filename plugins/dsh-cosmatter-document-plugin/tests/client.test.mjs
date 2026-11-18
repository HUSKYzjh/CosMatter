import assert from 'node:assert/strict'
import test from 'node:test'
import { CosMatterDocumentClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const submitted = { run_id: 'run_1', document_id: 'doc-1', provider: 'mineru', task_state: 'pending', trust_status: 'authorized_parse_dispatch_not_evidence_acceptance' }
const polled = { ...submitted, task_state: 'done', trust_status: 'authorized_parse_status_not_evidence_acceptance' }
const auth = ['mission_scoped_egress_consent', 'mineru_file_consent', 'private_content_to_mineru']

test('client rejects non-loopback endpoints, incomplete consent, and credential URLs', async () => {
  assert.throws(() => new CosMatterDocumentClient({ baseUrl: 'https://example.com' }))
  const client = new CosMatterDocumentClient({}, async () => new Response(JSON.stringify(submitted), { status: 200 }))
  await assert.rejects(() => client.submit('run_1', { authorizations: auth.slice(0, 2), document_id: 'doc-1', source_url: 'https://example.org/paper.pdf' }, 'call-0001'), /authorization/)
  await assert.rejects(() => client.submit('run_1', { authorizations: auth, document_id: 'doc-1', source_url: 'https://name:password@example.org/paper.pdf' }, 'call-0002'), /credential-free/)
  assert.equal((await client.submit('run_1', { authorizations: auth, document_id: 'doc-1', source_url: 'https://example.org/paper.pdf' }, 'call-0003')).task_state, 'pending')
})

test('client and DSH tools return task metadata with a loopback candidate link', async () => {
  const responses = [submitted, polled]
  const client = new CosMatterDocumentClient({}, async () => new Response(JSON.stringify(responses.shift()), { status: 200 }))
  assert.equal((await client.poll('run_1', { authorizations: auth, document_id: 'doc-1' }, 'call-0004')).task_state, 'pending')
  const tools = []; const events = []; let dispose; const originalFetch = globalThis.fetch; const toolResponses = [submitted, polled]
  globalThis.fetch = async () => new Response(JSON.stringify(toolResponses.shift()), { status: 200 })
  apply({ tools: { register: tool => tools.push(tool) }, emit: (event, payload) => events.push([event, payload]), effect: effect => { dispose = effect() } })
  assert.equal(name, 'cosmatter-document'); assert.deepEqual(inject, ['tools']); assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_mineru_source_submit', 'cosmatter_mineru_task_poll'])
  const result = await tools[0].execute({ run_id: 'run_1', authorizations: auth, document_id: 'doc-1', source_url: 'https://example.org/paper.pdf' }, { signal: new AbortController().signal })
  assert.equal(result.task_state, 'pending'); assert.equal(events[0][0], 'cosmatter-document/submitted')
  assert.equal(result.workbench_url, 'http://127.0.0.1:8765/?api=local#run=run_1&document=doc-1')
  const completed = await tools[1].execute({ run_id: 'run_1', authorizations: auth, document_id: 'doc-1' }, { signal: new AbortController().signal })
  assert.equal(completed.task_state, 'done')
  assert.equal(completed.workbench_url, result.workbench_url)
  dispose(); globalThis.fetch = originalFetch
})

test('generates links from the configured origin and verified request identifiers', async () => {
  const documentId = '文献 & x=1'
  const expected = { ...polled, document_id: documentId }
  let response = expected
  const client = new CosMatterDocumentClient({ baseUrl: 'http://127.0.0.1:8790' }, async (url, init) => {
    assert.equal(url.origin, 'http://127.0.0.1:8790')
    assert.equal(init.redirect, 'error')
    return new Response(JSON.stringify(response), { status: 200 })
  })
  const input = { authorizations: auth, document_id: documentId }
  const result = await client.poll('run_1', input, 'call-0005')
  const url = new URL(result.workbench_url)
  assert.equal(url.origin, 'http://127.0.0.1:8790')
  assert.equal(url.search, '?api=local')
  assert.deepEqual(Object.fromEntries(new URLSearchParams(url.hash.slice(1))), { run: 'run_1', document: documentId })
  for (const invalid of [{ run_id: 'another_run' }, { document_id: 'another-paper' }, { workbench_url: 'https://example.org/' }]) {
    response = { ...expected, ...invalid }
    await assert.rejects(() => client.poll('run_1', input, 'call-0006'), /response is invalid/)
  }
})
