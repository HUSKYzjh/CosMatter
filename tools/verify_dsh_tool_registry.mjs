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
  return result
}

async function browserRead(webOrigin, path) {
  const response = await fetch(new URL(path, webOrigin), { signal: AbortSignal.timeout(5000) })
  if (!response.ok) throw new Error(`browser handoff read for ${path} returned HTTP ${response.status}`)
  return await response.json()
}

export async function apply(ctx, { expectedTools, catalogue, webOrigin, runId, savedDocument }) {
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
    const { value: discovered } = await dispatch(ctx, 'cosmatter_plugin_catalogue', {})
    assert.deepEqual(JSON.parse(JSON.stringify(discovered)), catalogue)
    const missionArgs = {
      run_id: runId,
      question: 'How would epitaxial strain affect phase stability in a BiFeO3 thin film?',
      material: 'BiFeO3',
      property: 'phase stability',
      scope: 'Synthetic thin-film mission for the local DSH release check',
    }
    const missionResult = await dispatch(ctx, 'cosmatter_mission_create', missionArgs)
    const mission = missionResult.value
    assert.equal(mission.run_id, runId)
    assert.equal(mission.state, 'INTAKE')
    assert.equal(mission.workbench_url, `${webOrigin}/?api=local#run=${runId}`)
    assert.deepEqual(JSON.parse(missionResult.content[0].text), JSON.parse(JSON.stringify(mission)))
    assert.deepEqual(JSON.parse(JSON.stringify(missionResult.meta)), { run_id: runId, workbench_url: mission.workbench_url })
    const missionTool = ctx.tools.definitions().find(({ name }) => name === 'cosmatter_mission_create')
    const missionCard = missionTool.presentResult(missionArgs, missionResult)
    assert.equal(missionCard?.card, 'generic')
    assert.deepEqual(missionCard.content, [{ type: 'text', text: `${runId}\n${mission.workbench_url}` }])
    const { value: recentRuns } = await dispatch(ctx, 'cosmatter_recent_runs', {})
    assert.equal(recentRuns.schema_version, 'cosmatter.recent-run-links/v1')
    assert.deepEqual(recentRuns.runs.map(row => row.run_id).sort(), [runId, savedDocument.run_id].sort())
    const recent = recentRuns.runs.find(row => row.run_id === runId)
    assert.deepEqual(Object.keys(recent).sort(), ['run_id', 'stopped', 'updated_at', 'workbench_url'])
    assert.equal(recent.run_id, runId)
    assert.equal(recent.workbench_url, mission.workbench_url)
    assert.equal(recent.stopped, false)
    const { value: workflow } = await dispatch(ctx, 'cosmatter_workflow_status', { run_id: runId })
    assert.equal(workflow.run_id, runId)
    assert.equal(workflow.mission_id, mission.mission_id)
    assert.equal(workflow.next_stage, 'plan')
    const contract = await dispatch(ctx, 'cosmatter_stage_contract', {})
    assert.equal(contract.value.run_id, runId)
    assert.equal(contract.value.mission_id, mission.mission_id)
    assert.equal(contract.value.next_stage, workflow.next_stage)
    assert.deepEqual(JSON.parse(contract.content[0].text), JSON.parse(JSON.stringify(contract.value)))
    const contractTool = ctx.tools.definitions().find(({ name }) => name === 'cosmatter_stage_contract')
    assert.deepEqual(contractTool.presentResult({}, contract)?.content, [{
      type: 'text', text: `${runId}\nNext stage: plan\nHuman review: plan approval\nCompletion requires: approved flight plan`,
    }])
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
    const documentTool = ctx.tools.definitions().find(({ name }) => name === 'cosmatter_mineru_source_submit')
    const documentResult = await dispatch(ctx, documentTool.name, savedDocument)
    const documentUrl = new URL('/?api=local', webOrigin)
    documentUrl.hash = new URLSearchParams({ run: savedDocument.run_id, document: savedDocument.document_id }).toString()
    assert.equal(documentResult.value.idempotency_status, 'duplicate_completed')
    assert.equal(documentResult.value.workbench_url, documentUrl.href)
    assert.deepEqual(JSON.parse(documentResult.content[0].text), JSON.parse(JSON.stringify(documentResult.value)))
    const receiptText = [`Run: ${savedDocument.run_id}`, `Document: ${savedDocument.document_id}`, 'Parsing finished. Open CosMatter to continue the run’s current review step.',
      'Showing the saved receipt for this call.', documentUrl.href].join('\n')
    assert.deepEqual(documentTool.presentResult(savedDocument, documentResult)?.content, [{ type: 'text', text: receiptText }])
    const documentRoute = `/api/runs/${savedDocument.run_id}`
    const [saved, documentStage, documentBundle] = await Promise.all([
      browserRead(webOrigin, `${documentRoute}/source-parse-status`),
      browserRead(webOrigin, `${documentRoute}/stage-contract`),
      browserRead(webOrigin, `${documentRoute}/ui`),
    ])
    assert.equal(saved.tasks.find(task => task.document_id === savedDocument.document_id)?.state, 'done')
    assert.equal(documentStage.runtime_safety, 'verified')
    assert.equal(documentStage.next_stage, 'extraction')
    assert.ok(documentBundle.literature_graph.nodes.some(node => node.node_id === `paper:${savedDocument.document_id}`))
    process.stdout.write(`CosMatter release probe: ${expectedTools.length} tools, loopback catalogue, mission result card, bound stage contract, document receipt card, and browser handoff verified\n`, () => process.exit(0))
  } catch (error) {
    process.stderr.write(`CosMatter release probe failed: ${error.message}\n`, () => process.exit(1))
  }
}
