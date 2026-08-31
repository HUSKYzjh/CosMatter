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
  assert.equal(request.url, 'http://127.0.0.1:8765/api/missions')
  assert.equal(JSON.parse(request.options.body).run_id, 'bfo_001')
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
  dispose()
  globalThis.fetch = originalFetch
})
