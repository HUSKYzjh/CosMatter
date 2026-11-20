import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'
import { CosMatterObservabilityClient, localWorkbenchUrl, stageContractTemplate } from './client.js'
import type { CosMatterObservabilityConfig } from './config.js'

export const name = 'cosmatter-observability'
export const inject = ['tools']
declare module '@deepseek-ai/cordis' { interface Events { 'cosmatter-observability/workflow-read'(payload: { run_id: string; next_stage: string | null }): void; 'cosmatter-observability/artifact-read'(payload: { run_id: string; artifact_count: number }): void; 'cosmatter-observability/stage-contract-read'(payload: { run_id: string; next_stage: string | null; runtime_safety: string }): void; 'cosmatter-observability/telemetry-read'(payload: { run_id: string; provider_operation_count: number; cost_latency_status: string }): void; 'cosmatter-observability/dag-read'(payload: { run_id: string; eligible_stage_count: number; scheduler_status: string }): void } }

function isWorkbenchLink(value: JsonValue | undefined, runId: JsonValue | undefined, artifactList = false): value is string {
  if (typeof runId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(runId) || typeof value !== 'string') return false
  try {
    const link = new URL(value)
    return link.protocol === 'http:' && link.hostname === '127.0.0.1'
      && value === localWorkbenchUrl(link.origin, runId, artifactList)
  } catch {
    return false
  }
}

export function apply(ctx: Context, config: CosMatterObservabilityConfig = {}): void {
  const client = new CosMatterObservabilityClient(config)
  const sessionRun = config.workbenchRunId
  if (sessionRun !== undefined && (typeof sessionRun !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(sessionRun))) {
    throw new Error('Invalid CosMatter workbench run ID')
  }
  const runParameters = { run_id: sessionRun ? { type: 'string' } as const : { type: 'string', required: true } as const }
  const sessionRunHint = sessionRun ? ' Omit run_id to read the run selected in the workbench.' : ''
  function selectedRunId(requested: unknown = sessionRun): string {
    if (typeof requested !== 'string') throw new Error('A CosMatter run ID is required')
    return requested
  }
  ctx.tools.register(defineTool({
    name: 'cosmatter_recent_runs',
    description: 'List up to twelve recent local CosMatter run IDs, update times, stopped flags and workbench links. Use it when a run ID is unknown.',
    parameters: {},
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => value.runs ?? null,
    },
    presentCall: () => ({ card: 'generic', kind: 'read', title: 'Find recent CosMatter runs' }),
    presentResult: (_args, { isError, meta }) => {
      if (isError || !Array.isArray(meta) || meta.length > 12) return
      const entries = []
      for (const row of meta) {
        if (!row || typeof row !== 'object' || Array.isArray(row)) return
        const { run_id, workbench_url, stopped, updated_at } = row
        if (!isWorkbenchLink(workbench_url, run_id) || typeof stopped !== 'boolean'
          || typeof updated_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(updated_at)) return
        entries.push(`${run_id} · ${stopped ? 'Stopped' : 'Available'} · ${updated_at}\n${workbench_url}`)
      }
      return { card: 'generic', title: 'Recent CosMatter runs', content: [
        { type: 'text', text: entries.join('\n\n') || 'No local runs found.' },
      ] }
    },
    async execute(_args, exec) {
      return await client.recentRunLinks(exec.signal) as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_workflow_status',
    description: 'Read a count-only, loopback-only CosMatter workflow status. It never invokes providers, reads source content, accepts evidence, grants consent, or changes a run.'
      + sessionRunHint,
    parameters: runParameters,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const result = await client.workflowStatus(selectedRunId(args.run_id), exec.signal)
      ctx.emit('cosmatter-observability/workflow-read', { run_id: result.run_id, next_stage: result.next_stage })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_artifact_manifest',
    description: 'Read fixed, already-generated CosMatter artifact cards with title, SHA-256, time, trust status, and fixed download routes. The workbench link opens the saved artifact list for this run.',
    parameters: { run_id: { type: 'string', required: true } },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => ({ workbench_url: value.workbench_url ?? null, artifact_count: value.artifact_count ?? null }),
    },
    presentCall: ({ run_id }) => ({ card: 'generic', kind: 'read', title: 'Read saved CosMatter artifacts', rawInput: run_id }),
    presentResult: ({ run_id }, { isError, meta }) => {
      if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta)) return
      const { artifact_count, workbench_url } = meta
      if (!isWorkbenchLink(workbench_url, run_id, true) || typeof artifact_count !== 'number'
        || !Number.isSafeInteger(artifact_count) || artifact_count < 0) return
      const summary = artifact_count === 1 ? '1 saved artifact' : `${artifact_count} saved artifacts`
      return { card: 'generic', title: 'Saved CosMatter artifacts', content: [
        { type: 'text', text: `${run_id} · ${summary}\n${workbench_url}` },
      ] }
    },
    async execute(args, exec) {
      const result = await client.artifactManifest(String(args.run_id), exec.signal)
      ctx.emit('cosmatter-observability/artifact-read', { run_id: result.run_id, artifact_count: result.artifact_count })
      return { ...result, workbench_url: localWorkbenchUrl(client.config.baseUrl, result.run_id, true) } as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_stage_contract',
    description: 'Read the next stage and its human review gate, plus fixed completion requirements, expected outputs and recovery routes for every CosMatter stage. It is loopback-only and cannot grant consent, dispatch providers, expose audit details, or change a run.' + sessionRunHint,
    parameters: runParameters,
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => ({ run_id: value.run_id, next_stage: value.next_stage, runtime_safety: value.runtime_safety }),
    },
    presentCall: () => ({ card: 'generic', kind: 'read', title: 'Read CosMatter stage requirements' }),
    presentResult: ({ run_id }, { isError, meta }) => {
      if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta)) return
      const { run_id: run, next_stage: stage, runtime_safety: safety } = meta
      if (typeof run !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(run) || run !== (run_id ?? sessionRun)
        || (safety !== 'verified' && safety !== 'attention_required')) return
      const lines = [run]
      if (safety === 'attention_required') lines.push('Runtime checks require attention.')
      if (stage === null) {
        lines.push('No next stage listed.')
      } else {
        const template = stageContractTemplate(stage)
        if (!template || typeof stage !== 'string') return
        lines.push(`Next stage: ${stage}`, `Human review: ${template.humanGate.replaceAll('_', ' ')}`,
          `Completion requires: ${template.requirements.map(label => label.replaceAll('_', ' ')).join(', ')}`)
      }
      return { card: 'generic', title: 'CosMatter stage requirements', content: [{ type: 'text', text: lines.join('\n') }] }
    },
    async execute(args, exec) {
      const result = await client.stageContract(selectedRunId(args.run_id), exec.signal)
      ctx.emit('cosmatter-observability/stage-contract-read', { run_id: result.run_id, next_stage: result.next_stage, runtime_safety: result.runtime_safety })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_operational_telemetry',
    description: 'Read count-only local provider receipt and dispatch summaries, plus any already human-reviewed aggregate cost/latency disclosure. It is not a provider bill or performance benchmark and cannot dispatch, retry, grant consent, read requests, URLs, sources, audit details, or credentials.',
    parameters: { run_id: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const result = await client.operationalTelemetry(String(args.run_id), exec.signal)
      ctx.emit('cosmatter-observability/telemetry-read', { run_id: result.run_id, provider_operation_count: result.provider_operations.length, cost_latency_status: result.cost_latency_status })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_workflow_dag',
    description: 'Read CosMatter’s fixed, linear workflow-DAG readiness projection. It declares dependencies and one eligible stage at most, but cannot schedule, dispatch, retry, grant consent, expose content, or change a run.',
    parameters: { run_id: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const result = await client.workflowDag(String(args.run_id), exec.signal)
      ctx.emit('cosmatter-observability/dag-read', { run_id: result.run_id, eligible_stage_count: result.eligible_stages.length, scheduler_status: result.scheduler_status })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.effect(() => () => undefined)
}
