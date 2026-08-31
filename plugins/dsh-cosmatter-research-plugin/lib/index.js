import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterResearchClient } from './client.js';
export const name = 'cosmatter-research';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterResearchClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_research_plan_draft',
        description: 'Create an untrusted DeepSeek research-plan draft through the local CosMatter backend. Requires exactly mission_scoped_egress_consent and deepseek_request_consent. This does not approve a plan, retrieve literature, or accept evidence.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const draft = await client.draftPlan(String(args.run_id), args.authorizations, String(exec.callId), exec.signal);
            ctx.emit('cosmatter-research/plan-drafted', { run_id: draft.run_id });
            return draft;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_research_plan_approve',
        description: 'Record a human-reviewed bounded FlightPlan. The caller must review plan contents; this tool never parses the model draft implicitly and does not retrieve literature.',
        parameters: { run_id: { type: 'string', required: true }, subquestions: { type: 'array', required: true, items: { type: 'string' } }, queries: { type: 'array', required: true, items: { type: 'string' } }, counter_queries: { type: 'array', required: true, items: { type: 'string' } }, max_rounds: { type: 'number' }, max_papers: { type: 'number' } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const plan = await client.approvePlan(String(args.run_id), { subquestions: args.subquestions, queries: args.queries, counter_queries: args.counter_queries, ...(typeof args.max_rounds === 'number' ? { max_rounds: args.max_rounds } : {}), ...(typeof args.max_papers === 'number' ? { max_papers: args.max_papers } : {}) }, exec.signal);
            ctx.emit('cosmatter-research/plan-approved', { run_id: plan.run_id, plan_id: plan.plan_id });
            return plan;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_research_query_execute',
        description: 'Execute one reviewed FlightPlan query against selected metadata providers through the local backend. Requires exactly mission_scoped_egress_consent and metadata_provider_consent. Results are candidates only, never full text or accepted evidence.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, query_index: { type: 'number', required: true }, counter: { type: 'boolean' }, sources: { type: 'array', required: true, items: { type: 'string' } } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.executeQuery(String(args.run_id), { authorizations: args.authorizations, query_index: args.query_index, counter: args.counter, sources: args.sources }, String(exec.callId), exec.signal);
            ctx.emit('cosmatter-research/query-executed', { run_id: result.run_id, query_kind: result.query_kind, candidate_count: result.candidate_count });
            return result;
        },
    }));
    ctx.effect(() => () => undefined);
}
