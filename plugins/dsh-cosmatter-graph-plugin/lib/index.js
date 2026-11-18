import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterLoopbackClient, acceptedEvidenceWorkbenchLink } from './client.js';
export const name = 'cosmatter-graph';
export const inject = ['tools'];
function evidencePreview(value, maximum) {
    if (typeof value !== 'string')
        return null;
    const line = value.replace(/[\p{Cc}\p{Cf}\s]+/gu, ' ').trim();
    const characters = [...line];
    return characters.length > maximum ? characters.slice(0, maximum - 1).join('').trimEnd() + '…' : line;
}
export function apply(ctx, config = {}) {
    const client = new CosMatterLoopbackClient(config);
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
            if ((args.offset !== undefined && args.offset < 0) || (args.limit !== undefined && (args.limit < 1 || args.limit > 100)))
                throw new Error('graph page parameters are invalid');
            const graph = await client.graph(args.run_id, { nodeType: args.node_type, offset: args.offset, limit: args.limit, signal: exec.signal });
            ctx.emit('cosmatter-graph/query', { run_id: graph.mission_id, graph_id: graph.graph_id, node_count: graph.nodes.length, edge_count: graph.edges.length });
            return graph;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_accepted_evidence_search',
        description: 'Search human-accepted evidence-card metadata for this run. Provide a keyword query or one exact evidence_id. A result with a workbench_url opens the card in the local reader.',
        parameters: { run_id: { type: 'string', required: true }, query: { type: 'string' }, evidence_id: { type: 'string' }, limit: { type: 'integer' } },
        output: {
            schema: { type: 'object', additionalProperties: true },
            render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
            presentationMeta: (_args, value) => Array.isArray(value.results) ? value.results.map((item) => {
                if (!item || typeof item !== 'object' || Array.isArray(item))
                    return null;
                return {
                    evidence_id: item.evidence_id ?? null, document_id: item.document_id ?? null, workbench_url: item.workbench_url ?? null,
                    claim: evidencePreview(item.claim, 180), locator: evidencePreview(item.locator, 100),
                };
            }) : null,
        },
        presentCall: ({ run_id, evidence_id }) => ({
            card: 'generic', kind: evidence_id === undefined ? 'search' : 'read',
            title: evidence_id === undefined ? 'Search accepted CosMatter evidence' : 'Find an accepted CosMatter evidence card',
            rawInput: run_id,
        }),
        presentResult: ({ run_id, evidence_id: requestedEvidenceId }, { isError, meta }) => {
            if (isError || !Array.isArray(meta) || meta.length > (requestedEvidenceId === undefined ? 12 : 1))
                return;
            const entries = [];
            for (const item of meta) {
                if (!item || typeof item !== 'object' || Array.isArray(item))
                    return;
                const { evidence_id, document_id, workbench_url } = item;
                if (typeof evidence_id !== 'string' || typeof document_id !== 'string'
                    || (requestedEvidenceId !== undefined && requestedEvidenceId !== evidence_id))
                    return;
                const expectedLink = acceptedEvidenceWorkbenchLink(client.config.baseUrl.origin, run_id, document_id, evidence_id);
                if (workbench_url !== null && workbench_url !== expectedLink)
                    return;
                const title = evidencePreview(evidence_id, 200) || 'Evidence card';
                const rows = [title, evidencePreview(item.claim, 180), evidencePreview(item.locator, 100),
                    workbench_url ?? 'Local reader link unavailable.'];
                entries.push(rows.filter(Boolean).join('\n'));
            }
            return { card: 'generic', title: 'Accepted CosMatter evidence', content: [
                    { type: 'text', text: entries.join('\n\n') || 'No accepted evidence cards matched.' },
                ] };
        },
        async execute(args, exec) {
            const query = typeof args.query === 'string' ? args.query : null;
            const evidenceId = typeof args.evidence_id === 'string' ? args.evidence_id : null;
            if ((query === null) === (evidenceId === null))
                throw new Error('provide a query or one exact evidence ID');
            const selector = evidenceId === null ? query : { evidenceId };
            return await client.searchAcceptedEvidence(String(args.run_id), selector, typeof args.limit === 'number' ? args.limit : 8, exec.signal);
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_graph_review_request', description: 'Submit a pending human review request for existing graph nodes. It cannot approve evidence or modify the graph.',
        parameters: { run_id: { type: 'string', required: true }, node_ids: { type: 'array', required: true, items: { type: 'string' } }, rationale: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) { return await client.requestReview(args.run_id, args.node_ids, args.rationale, exec.signal); },
    }));
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
            const plan = await client.draftPlan(args.run_id, args.node_ids, args.intent, exec.signal);
            ctx.emit('cosmatter-graph/plan-created', { run_id: args.run_id, intent_length: args.intent.trim().length });
            return plan;
        },
    }));
    ctx.effect(() => () => undefined);
}
