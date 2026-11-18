import assert from 'node:assert/strict'
import { setTimeout as sleep } from 'node:timers/promises'

export const name = 'cosmatter-release-registry-probe'
export const inject = ['tools']

async function dispatch(ctx, name, args) {
  const callId = `release-probe-${name}`
  const batch = await ctx.tools.execute({
    calls: [{ type: 'tool-call', id: callId, name, arguments: JSON.stringify(args) }],
    signal: AbortSignal.timeout(5000),
  })
  assert.equal(batch.results.length, 1)
  const { callId: resultId, result } = batch.results[0]
  assert.equal(resultId, callId)
  if (result.isError) throw new Error(`DSH dispatch failed for ${name}: ${result.error.code}`)
  return result.value
}

async function browserRead(webOrigin, path) {
  const response = await fetch(new URL(path, webOrigin), { signal: AbortSignal.timeout(5000) })
  if (!response.ok) throw new Error(`browser handoff read for ${path} returned HTTP ${response.status}`)
  return await response.json()
}

export async function apply(ctx, { expectedTools, catalogue, webOrigin }) {
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
    const discovered = await dispatch(ctx, 'cosmatter_plugin_catalogue', {})
    assert.deepEqual(JSON.parse(JSON.stringify(discovered)), catalogue)
    const runId = 'cosmatter_release_probe'
    const mission = await dispatch(ctx, 'cosmatter_mission_create', {
      run_id: runId,
      question: 'How would epitaxial strain affect phase stability in a BiFeO3 thin film?',
      material: 'BiFeO3',
      property: 'phase stability',
      scope: 'Synthetic thin-film mission for the local DSH release check',
    })
    assert.equal(mission.run_id, runId)
    assert.equal(mission.state, 'INTAKE')
    assert.equal(mission.workbench_url, `${webOrigin}/?api=local#run=${runId}`)
    const workflow = await dispatch(ctx, 'cosmatter_workflow_status', { run_id: runId })
    assert.equal(workflow.run_id, runId)
    assert.equal(workflow.mission_id, mission.mission_id)
    assert.equal(workflow.next_stage, 'plan')
    const runRoute = `/api/runs/${runId}`
    const [browserStatus, browserBundle, pdfRegistry] = await Promise.all([
      browserRead(webOrigin, `${runRoute}/status`),
      browserRead(webOrigin, `${runRoute}/ui`),
      browserRead(webOrigin, `${runRoute}/pdf/tasks/cached`),
    ])
    assert.equal(browserStatus.run_id, runId)
    assert.equal(browserStatus.mission_id, mission.mission_id)
    assert.equal(browserBundle.mission.mission_id, mission.mission_id)
    assert.equal(pdfRegistry.run_id, runId)
    assert.deepEqual(pdfRegistry.tasks, [])
    process.stdout.write(`CosMatter release probe: ${expectedTools.length} tools, loopback catalogue, mission, and browser handoff verified\n`, () => process.exit(0))
  } catch (error) {
    process.stderr.write(`CosMatter release probe failed: ${error.message}\n`, () => process.exit(1))
  }
}
