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

test('native submit and poll cards show the saved task state and the exact local document', async t => {
  const origin = 'http://127.0.0.1:8790'
  const documentId = 'BiFeO₃ film & XRD/1'
  const url = new URL('/?api=local', origin)
  url.hash = new URLSearchParams({ run: 'run_1', document: documentId }).toString()
  const input = { run_id: 'run_1', authorizations: auth, document_id: documentId }
  const submitInput = { ...input, source_url: 'https://example.invalid/source.pdf?temporary=hidden' }
  let response
  t.mock.method(globalThis, 'fetch', async () => Response.json(response))
  const tools = new Map()
  apply({ tools: { register: tool => tools.set(tool.name, tool) }, emit() {}, effect() {} }, { baseUrl: origin })
  const submit = tools.get('cosmatter_mineru_source_submit')
  const poll = tools.get('cosmatter_mineru_task_poll')
  assert.deepEqual(submit.presentCall(submitInput), { card: 'generic', kind: 'execute', title: 'Submit a document to MinerU' })
  assert.deepEqual(poll.presentCall(input), { card: 'generic', kind: 'fetch', title: 'Check MinerU parsing status' })
  for (const [state, guidance] of [
    ['pending', 'Parsing is queued. Check its saved status in CosMatter.'],
    ['running', 'Parsing is in progress. Check its saved status in CosMatter.'],
    ['failed', 'Parsing failed. Review its saved status in CosMatter.'],
    ['done', 'Parsing finished. Open CosMatter to continue the run’s current review step.'],
  ]) {
    const tool = state === 'pending' ? submit : poll
    const args = tool === submit ? submitInput : input
    const replayed = state === 'done'
    response = { ...(tool === submit ? submitted : polled), document_id: documentId, task_state: state,
      ...(replayed ? { idempotency_status: 'duplicate_completed' } : {}) }
    const value = await tool.execute(args, { callId: 'test-parse-receipt', signal: new AbortController().signal })
    const content = tool.output.render(args, value)
    assert.deepEqual(JSON.parse(content[0].text), { ...response, workbench_url: url.href })
    const meta = tool.output.presentationMeta(args, value)
    assert.deepEqual(meta, { workbench_url: url.href, task_state: state, replayed })
    const result = { isError: false, content, meta }
    const text = ['Run: run_1', `Document: ${documentId}`, guidance, ...(replayed ? ['Showing the saved receipt for this call.'] : []), url.href].join('\n')
    assert.deepEqual(tool.presentResult(args, result).content, [{ type: 'text', text }])
    assert.equal(tool.presentResult(args, { ...result, isError: true }), undefined)
    assert.equal(tool.presentResult({ ...args, document_id: 'another document' }, result), undefined)
    assert.equal(tool.presentResult({ ...args, run_id: 'run_other' }, result), undefined)
    for (const changed of [{ workbench_url: url.href.replace(':8790', ':8791') }, { workbench_url: submitInput.source_url },
      { task_state: 'unknown' }, { replayed: 'yes' }]) {
      assert.equal(tool.presentResult(args, { ...result, meta: { ...meta, ...changed } }), undefined)
    }
  }
})
