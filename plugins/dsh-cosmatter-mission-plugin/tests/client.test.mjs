import assert from 'node:assert/strict'
import test from 'node:test'

import { CosMatterMissionClient } from '../lib/client.js'
import { apply, inject, name } from '../lib/index.js'

const created = { run_id: 'bfo_001', mission_id: 'mission_abcdef12', fleet_type: 'literature_review', mission_type: 'literature_review', state: 'INTAKE' }

test('client creates a bounded mission through the loopback API', async () => {
  let request
  const client = new CosMatterMissionClient({}, async (url, options) => {
    request = { url: String(url), options }
    return new Response(JSON.stringify(created), { status: 201 })
  })
  const result = await client.create({ question: 'How does strain change phase stability?', material: 'BiFeO3', property: 'phase stability', scope: 'thin films', run_id: 'bfo_001' })
  assert.equal(result.run_id, 'bfo_001')
  assert.equal(result.workbench_url, 'http://127.0.0.1:8765/?api=local#run=bfo_001')
  assert.equal(request.url, 'http://127.0.0.1:8765/api/missions')
  assert.equal(request.options.redirect, 'error')
  assert.equal(JSON.parse(request.options.body).run_id, 'bfo_001')
})

test('derives the workbench link from the configured port and verified run identity', async () => {
  const client = new CosMatterMissionClient({ baseUrl: 'http://127.0.0.1:8769' }, async () => new Response(JSON.stringify({
    ...created, workbench_url: 'https://example.com/elsewhere', details: { secret: 'sensitive' },
  }), { status: 201 }))
  const input = { question: 'A valid research question', material: 'BiFeO3', property: 'phase stability', scope: 'thin films' }
  assert.deepEqual(await client.create(input), { ...created, workbench_url: 'http://127.0.0.1:8769/?api=local#run=bfo_001' })
  await assert.rejects(() => client.create({ ...input, run_id: 'other_run' }), /does not match the requested run/)
})

test('client rejects invalid endpoints and sensitive responses', async () => {
  assert.throws(() => new CosMatterMissionClient({ baseUrl: 'https://example.com' }))
  const client = new CosMatterMissionClient({}, async () => new Response(JSON.stringify({ ...created, api_key: 'nope' }), { status: 201 }))
  await assert.rejects(() => client.create({ question: 'A valid research question', material: 'BiFeO3', property: 'phase stability', scope: 'thin films' }), /forbidden field/)
})

test('DSH apply registers only bounded mission creation', async () => {
  const tools = []
  const events = []
  let dispose
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify(created), { status: 201 })
  apply({ tools: { register: tool => tools.push(tool) }, emit: (event, payload) => events.push([event, payload]), effect: effect => { dispose = effect() } })
  assert.equal(name, 'cosmatter-mission')
  assert.deepEqual(inject, ['tools'])
  assert.deepEqual(tools.map(tool => tool.name), ['cosmatter_mission_create'])
  const result = await tools[0].execute({ question: 'How does strain change phase stability?', material: 'BiFeO3', property: 'phase stability', scope: 'thin films', run_id: 'bfo_001' }, { signal: new AbortController().signal })
  assert.equal(result.state, 'INTAKE')
  assert.equal(events[0][0], 'cosmatter-mission/created')
  assert.equal(events[0][1].workbench_url, result.workbench_url)
  assert.equal(JSON.parse(tools[0].output.render({}, result)[0].text).workbench_url, result.workbench_url)
  dispose()
  globalThis.fetch = originalFetch
})

test('the native result card presents only the created run and its verified workbench URL', async (t) => {
  const baseUrl = 'http://127.0.0.1:8791'
  const args = { question: 'Synthetic question?', material: 'Sample', property: 'Example', scope: 'Local trial' }
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(created), { status: 201 }))
  let tool
  apply({ tools: { register: item => { tool = item } }, emit() {}, effect() {} }, { baseUrl })
  const value = await tool.execute(args, { signal: new AbortController().signal })
  const content = tool.output.render(args, value)
  assert.deepEqual(JSON.parse(content[0].text), value)
  const workbench_url = `${baseUrl}/?api=local#run=${created.run_id}`
  const meta = tool.output.presentationMeta(args, value)
  assert.deepEqual(meta, { run_id: created.run_id, workbench_url })
  const result = { content, isError: false, meta }
  const card = { card: 'generic', title: 'CosMatter mission created', content: [
    { type: 'text', text: `${created.run_id}\n${workbench_url}` },
  ] }
  assert.deepEqual(tool.presentResult(args, result), card)
  assert.deepEqual(tool.presentResult({ ...args, run_id: created.run_id }, result), card)
  assert.equal(tool.presentResult({ ...args, run_id: 'another_run' }, result), undefined)
  assert.equal(tool.presentResult(args, { ...result, isError: true }), undefined)
  for (const badMeta of [null, [], { run_id: '../example', workbench_url }, { run_id: created.run_id },
    { ...meta, workbench_url: workbench_url.replace(':8791', ':8792') },
    { ...meta, workbench_url: workbench_url.replace('127.0.0.1', 'example.org') },
    { ...meta, workbench_url: workbench_url.replace(created.run_id, 'another_run') },
    { ...meta, workbench_url: workbench_url + '&artifacts=1' }]) {
    assert.equal(tool.presentResult(args, { ...result, meta: badMeta }), undefined)
  }
})
