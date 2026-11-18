import assert from 'node:assert/strict'
import { setTimeout as sleep } from 'node:timers/promises'

export const name = 'cosmatter-release-registry-probe'
export const inject = ['tools']

export async function apply(ctx, { expectedTools, catalogue }) {
  try {
    const registeredCosMatterTools = () => ctx.tools.definitions()
      .map(({ name }) => name)
      .filter((tool) => tool.startsWith('cosmatter_'))
      .sort()
    const deadline = Date.now() + 8000
    while (registeredCosMatterTools().length < expectedTools.length && Date.now() < deadline) {
      await sleep(50)
    }
    assert.deepEqual(registeredCosMatterTools(), [...expectedTools].sort())
    const tool = ctx.tools.get('cosmatter_plugin_catalogue')
    const result = await tool.execute({}, { signal: AbortSignal.timeout(5000) })
    assert.deepEqual(result, catalogue)
    process.stdout.write(`CosMatter release probe: ${expectedTools.length} tools, loopback catalogue verified\n`, () => process.exit(0))
  } catch (error) {
    process.stderr.write(`CosMatter release probe failed: ${error.message}\n`, () => process.exit(1))
  }
}
