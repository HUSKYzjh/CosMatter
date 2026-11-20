import assert from 'node:assert/strict'
import test from 'node:test'
import { apply } from '../lib/index.js'

function registeredTool() {
  const tools = []
  apply({ tools: { register: tool => tools.push(tool) }, effect() {} })
  return tools.find(tool => tool.name === 'cosmatter_pst_occupancy_count')
}

test('native PST tool gives exact labeled counts without fetching or rounding', async t => {
  t.mock.method(globalThis, 'fetch', () => assert.fail('Local occupancy calculation must not fetch'))
  const tool = registeredTool()
  // Independent reference computed with Python math.comb(512, 256).
  const centralCount = '472553303154964924989004370051186389478210715642481882577328859153566070336566100844650299634054239969857431328433974960326174706663509667348266572071494'
  for (const [x, nPb, count] of [
    ['0', 0, '1'], ['1', 512, '1'], ['1/512', 1, '512'], ['511/512', 511, '512'], ['2/512', 2, '130816'],
    ['.5', 256, centralCount], ['2/4', 256, centralCount],
  ]) {
    const args = { pb_fraction: x }
    const output = await tool.execute(args)
    assert.deepEqual(JSON.parse(tool.output.render(args, output)[0].text), output)
    assert.equal(output.realizable, true)
    assert.equal(output.n_pb, nPb)
    assert.equal(output.n_sr, 512 - nPb)
    assert.equal(output.arrangement_count, count)
    assert.equal(output.count_basis, 'labeled_a_sites_before_symmetry_reduction')
  }
})

test('unrealizable fractions return only the two bracketing compositions', async () => {
  const tool = registeredTool()
  for (const [x, lower] of [['1/3', 170], ['0.5000000000000000000000000000000001', 256], ['0.4999999999999999999999999999999999', 255]]) {
    const output = await tool.execute({ pb_fraction: x })
    assert.equal(output.realizable, false)
    assert.equal(output.arrangement_count, undefined)
    assert.deepEqual(output.nearest_compositions, [lower, lower + 1].map(n_pb => ({
      n_pb, n_sr: 512 - n_pb, pb_fraction: String(n_pb / 512),
    })))
  }
  for (const x of [null, true, 0.5, '', '.', '1/0', '2/1', '-0.01', '0x1', '1e-1', '1.0.0', '1/2/3', '0'.repeat(257)]) {
    await assert.rejects(() => tool.execute({ pb_fraction: x }))
  }
})
