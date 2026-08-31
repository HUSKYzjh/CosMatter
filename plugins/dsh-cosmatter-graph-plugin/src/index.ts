import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool, type JsonValue } from '@deepseek-ai/dsh-tools'

import { CosMatterLoopbackClient } from './client.js'
import type { CosMatterGraphConfig } from './config.js'

export const name = 'cosmatter-graph'
export const inject = ['tools']

declare module '@deepseek-ai/cordis' {
  interface Events {
    'cosmatter-graph/query'(payload: { run_id: string; graph_id: string; node_count: number; edge_count: number }): void
    'cosmatter-graph/plan-created'(payload: { run_id: string; intent_length: number }): void
  }
}

export function apply(ctx: Context, config: CosMatterGraphConfig = {}): void {
  const client = new CosMatterLoopbackClient(config)
  ctx.tools.register(defineTool({
    name: 'cosmatter_graph_query',
    description: 'Read an existing CosMatter mission graph projected from accepted evidence only. It never creates evidence, reads private text, or draws a scientific conclusion.',
    parameters: {
      run_id: { type: 'string', required: true, description: 'A local CosMatter run identifier.' },
      node_type: { type: 'string', enum: ['Mission', 'Paper', 'Entity', 'Condition', 'EvidenceCard'], description: 'Optional node type filter.' },
      offset: { type: 'integer', description: 'Optional zero-based page offset.' },
      limit: { type: 'integer', description: 'Optional page size, at most 100.' },
    },
    output: {
      // The detailed, versioned schema is checked by assertGraphSnapshot before
      // this open JSON object crosses the DSH tool boundary.
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      if ((args.offset !== undefined && args.offset < 0) || (args.limit !== undefined && (args.limit < 1 || args.limit > 100))) throw new Error('graph page parameters are invalid')
      const graph = await client.graph(args.run_id, { nodeType: args.node_type, offset: args.offset, limit: args.limit, signal: exec.signal })
      ctx.emit('cosmatter-graph/query', { run_id: graph.mission_id, graph_id: graph.graph_id, node_count: graph.nodes.length, edge_count: graph.edges.length })
      return graph as unknown as Record<string, JsonValue>
    },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_accepted_evidence_search',
    description: 'Search only already human-accepted evidence-card metadata for this run. Results are source-located pointers, never raw full text, MinerU output, unreviewed material, or a new scientific conclusion.',
    parameters: { run_id: { type: 'string', required: true }, query: { type: 'string', required: true }, limit: { type: 'integer' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) { return await client.searchAcceptedEvidence(String(args.run_id), String(args.query), typeof args.limit === 'number' ? args.limit : 8, exec.signal) as Record<string, JsonValue> },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_graph_review_request', description: 'Submit a pending human review request for existing graph nodes. It cannot approve evidence or modify the graph.',
    parameters: { run_id: { type: 'string', required: true }, node_ids: { type: 'array', required: true, items: { type: 'string' } }, rationale: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) { return await client.requestReview(args.run_id, args.node_ids, args.rationale, exec.signal) as Record<string, JsonValue> },
  }))
  ctx.tools.register(defineTool({
    name: 'cosmatter_graph_plan',
    description: 'Record a non-executing request plan for a human to inspect selected CosMatter graph nodes. It calls only the local loopback API and cannot approve evidence or execute a graph action.',
    parameters: {
      run_id: { type: 'string', required: true, description: 'A local CosMatter run identifier.' },
      node_ids: { type: 'array', required: true, items: { type: 'string' }, description: 'One to 25 existing graph node identifiers selected for human review.' },
      intent: { type: 'string', required: true, description: 'A bounded human-readable graph inspection intent.' },
    },
    output: {
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          mission_id: { type: 'string' }, graph_id: { type: 'string' }, node_ids: { type: 'array' }, intent: { type: 'string' },
          proposed_action: { type: 'string', const: 'request_human_to_review_or_project_graph' },
          trust_status: { type: 'string', const: 'untrusted_graph_plan_draft_not_execution_or_evidence_acceptance' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      const plan = await client.draftPlan(args.run_id, args.node_ids, args.intent, exec.signal)
      ctx.emit('cosmatter-graph/plan-created', { run_id: args.run_id, intent_length: args.intent.trim().length })
      return plan as Record<string, JsonValue>
    },
  }))
  ctx.effect(() => () => undefined)
}
