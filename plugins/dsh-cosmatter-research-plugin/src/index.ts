import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'

import { CosMatterResearchClient, isScreeningRevision, queryWorkbenchLink } from './client.js'
import type { CosMatterResearchConfig } from './config.js'
import { pstOccupancyTool } from './pst-occupancy.js'
import { fieldResponseTool } from './field-response.js'

export const name = 'cosmatter-research'
export const inject = ['tools']

declare module '@deepseek-ai/cordis' {
  interface Events {
    'cosmatter-research/plan-drafted'(payload: { run_id: string }): void
    'cosmatter-research/plan-approved'(payload: { run_id: string; plan_id: string }): void
    'cosmatter-research/query-executed'(payload: { run_id: string; query_kind: string; candidate_count: number }): void
  }
}

export function apply(ctx: Context, config: CosMatterResearchConfig = {}): void {
  const client = new CosMatterResearchClient(config)
  ctx.tools.register(defineTool({
    name: 'cosmatter_research_plan_draft',
    description: 'Create an untrusted DeepSeek research-plan draft through the local CosMatter backend. Requires exactly mission_scoped_egress_consent and deepseek_request_consent. This does not approve a plan, retrieve literature, or accept evidence.',
    parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const draft = await client.draftPlan(String(args.run_id), args.authorizations as string[], String(exec.callId), exec.signal)
      ctx.emit('cosmatter-research/plan-drafted', { run_id: draft.run_id })
      return draft as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_research_plan_approve',
    description: 'Record a human-reviewed bounded FlightPlan. The caller must review plan contents; this tool never parses the model draft implicitly and does not retrieve literature.',
    parameters: { run_id: { type: 'string', required: true }, subquestions: { type: 'array', required: true, items: { type: 'string' } }, queries: { type: 'array', required: true, items: { type: 'string' } }, counter_queries: { type: 'array', required: true, items: { type: 'string' } }, max_rounds: { type: 'number' }, max_papers: { type: 'number' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const plan = await client.approvePlan(String(args.run_id), { subquestions: args.subquestions as string[], queries: args.queries as string[], counter_queries: args.counter_queries as string[], ...(typeof args.max_rounds === 'number' ? { max_rounds: args.max_rounds } : {}), ...(typeof args.max_papers === 'number' ? { max_papers: args.max_papers } : {}) }, exec.signal)
      ctx.emit('cosmatter-research/plan-approved', { run_id: plan.run_id, plan_id: plan.plan_id })
      return plan as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_research_query_execute',
    description: 'Execute one reviewed FlightPlan query against selected metadata providers through the local backend. Requires exactly mission_scoped_egress_consent and metadata_provider_consent. Results are metadata candidates, with a workbench_url for the verified screening checklist or the run’s current stage.',
    parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, query_index: { type: 'number', required: true }, counter: { type: 'boolean' }, sources: { type: 'array', required: true, items: { type: 'string' } } },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => ({
        candidate_count: value.candidate_count ?? null, screening_revision: value.screening_revision ?? null,
        workbench_url: value.workbench_url ?? null, resumed: value.idempotency_status === 'duplicate_completed',
      }),
    },
    presentCall: ({ run_id, counter }) => ({
      card: 'generic', kind: 'search', title: counter ? 'Find CosMatter counterevidence candidates' : 'Find CosMatter literature candidates',
      rawInput: run_id,
    }),
    presentResult: ({ run_id }, { isError, meta }) => {
      if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta)) return
      const { candidate_count, screening_revision, workbench_url, resumed } = meta
      if (typeof candidate_count !== 'number' || !Number.isInteger(candidate_count) || candidate_count < 0 || candidate_count > 60
        || (screening_revision !== null && !isScreeningRevision(screening_revision))) return
      if (workbench_url !== queryWorkbenchLink(client.config.baseUrl, run_id, screening_revision ?? undefined)) return
      const count = candidate_count === 1 ? '1 metadata candidate' : `${candidate_count} metadata candidates`
      const action = screening_revision ? 'Open the screening checklist' : 'Open the run'
      return { card: 'generic', title: 'CosMatter retrieval result', content: [
        { type: 'text', text: `${count}${resumed === true ? ' · Previously completed' : ''}\n${action}\n${workbench_url}` },
      ] }
    },
    async execute(args, exec) {
      const result = await client.executeQuery(String(args.run_id), { authorizations: args.authorizations as string[], query_index: args.query_index as number, counter: args.counter as boolean | undefined, sources: args.sources as string[] }, String(exec.callId), exec.signal)
      ctx.emit('cosmatter-research/query-executed', { run_id: result.run_id, query_kind: result.query_kind, candidate_count: result.candidate_count })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(pstOccupancyTool)
  ctx.tools.register(fieldResponseTool)
  ctx.effect(() => () => undefined)
}
