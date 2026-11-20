import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'

import { CosMatterLoopbackClient, acceptedEvidenceWorkbenchLink, canonicalEvidenceDoi } from './client.js'
import type { CosMatterGraphConfig } from './config.js'

export const name = 'cosmatter-graph'
export const inject = ['tools']

declare module '@deepseek-ai/cordis' {
  interface Events {
    'cosmatter-graph/query'(payload: { run_id: string; graph_id: string; node_count: number; edge_count: number }): void
    'cosmatter-graph/plan-created'(payload: { run_id: string; intent_length: number }): void
  }
}

function evidencePreview(value: JsonValue | undefined, maximum: number): string | null {
  if (typeof value !== 'string') return null
  const line = value.replace(/[\p{Cc}\p{Cf}\s]+/gu, ' ').trim()
  const characters = [...line]
  return characters.length > maximum ? characters.slice(0, maximum - 1).join('').trimEnd() + '…' : line
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
    description: 'Find accepted evidence in one run by keyword query, exact evidence_id, document_id and locator, or paper DOI with an optional exact figure/table locator. DOI results include each reviewed claim, material, property, conditions, locator, and a local reader link when available.',
    parameters: {
      run_id: { type: 'string', required: true }, query: { type: 'string' }, evidence_id: { type: 'string' },
      document_id: { type: 'string', description: 'Exact document identifier, used together with locator.' },
      doi: { type: 'string', description: 'Published DOI as recorded in card provenance, optionally with an exact locator.' },
      locator: { type: 'string', description: 'Exact reviewed locator, for example figure:2. Use it with document_id or doi.' },
      limit: { type: 'integer', description: 'Maximum number of returned cards, 1 to 12 (default 8).' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (args, value) => {
        if (!Array.isArray(value.results)) return null
        const entries = value.results.map(item => {
          if (!item || typeof item !== 'object' || Array.isArray(item)) return null
          return {
            evidence_id: item.evidence_id ?? null, document_id: item.document_id ?? null, workbench_url: item.workbench_url ?? null,
            ...(args.doi === undefined ? {} : {
              doi: item.doi ?? null, review_status: item.review_status ?? null,
              material: evidencePreview(item.material, 100), property: evidencePreview(item.property_name, 100),
            }),
            claim: evidencePreview(item.claim, 180), locator: args.locator === undefined ? evidencePreview(item.locator, 100) : item.locator ?? null,
          }
        })
        return args.locator === undefined && args.doi === undefined ? entries : { entries, matched_count: value.matched_count ?? null }
      },
    },
    presentCall: ({ run_id, evidence_id }) => ({
      card: 'generic', kind: evidence_id === undefined ? 'search' : 'read',
      title: evidence_id === undefined ? 'Search accepted CosMatter evidence' : 'Find an accepted CosMatter evidence card',
      rawInput: run_id,
    }),
    presentResult: ({ run_id, evidence_id: requestedEvidenceId, document_id: requestedDocument, doi, locator, limit = 8 }, { isError, meta }) => {
      if (isError) return
      const locationMeta = meta && typeof meta === 'object' && !Array.isArray(meta) ? meta : undefined
      const atPaper = locator !== undefined || doi !== undefined
      const hits = atPaper ? locationMeta?.entries : meta
      if (!Array.isArray(hits) || hits.length > (requestedEvidenceId === undefined ? 12 : 1)) return
      const matched = locationMeta?.matched_count
      if (atPaper && (typeof matched !== 'number' || !Number.isSafeInteger(matched) || matched < 0 || hits.length !== Math.min(limit, matched))) return
      const entries = []
      for (const item of hits) {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return
        const { evidence_id, document_id, workbench_url } = item
        if (typeof evidence_id !== 'string' || typeof document_id !== 'string'
          || (requestedEvidenceId !== undefined && requestedEvidenceId !== evidence_id)
          || (requestedDocument !== undefined && requestedDocument !== document_id)
          || (locator !== undefined && item.locator !== locator)
          || (doi !== undefined && (typeof item.doi !== 'string' || canonicalEvidenceDoi(doi) !== item.doi || item.review_status !== 'accepted'))) return
        const expectedLink = acceptedEvidenceWorkbenchLink(client.config.baseUrl.origin, run_id, document_id, evidence_id)
        if (workbench_url !== null && workbench_url !== expectedLink) return
        const title = evidencePreview(evidence_id, 200) || 'Evidence card'
        const subject = doi === undefined ? null : [evidencePreview(item.material, 100), evidencePreview(item.property, 100)].filter(Boolean).join(' · ')
        const rows = [title, doi === undefined ? null : `DOI: ${item.doi} · Review: accepted`, subject, evidencePreview(item.claim, 180), evidencePreview(item.locator, locator === undefined ? 100 : 240),
          workbench_url ?? 'Local reader link unavailable.']
        entries.push(rows.filter(Boolean).join('\n'))
      }
      if (typeof matched === 'number' && matched > hits.length) entries.push(`Showing ${hits.length} of ${matched} matching cards.`)
      return { card: 'generic', title: 'Accepted CosMatter evidence', content: [
        { type: 'text', text: entries.join('\n\n') || 'No accepted evidence cards matched.' },
      ] }
    },
    async execute(args, exec) {
      const { query, evidence_id, document_id, doi, locator } = args
      const selectors = []
      if (query !== undefined) selectors.push(query)
      if (evidence_id !== undefined) selectors.push({ evidenceId: evidence_id })
      if (doi !== undefined) selectors.push({ doi, locator })
      if (document_id !== undefined && locator !== undefined) selectors.push({ documentId: document_id, locator })
      if (selectors.length !== 1 || (document_id !== undefined && locator === undefined) || (locator !== undefined && document_id === undefined && doi === undefined)) {
        throw new Error('provide a query or one exact evidence ID, a document ID and locator together, or a DOI with optional locator')
      }
      return await client.searchAcceptedEvidence(args.run_id, selectors[0], args.limit, exec.signal) as Record<string, JsonValue>
    },
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
