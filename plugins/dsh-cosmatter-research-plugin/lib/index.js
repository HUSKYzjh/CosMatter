import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterResearchClient, isScreeningRevision, queryWorkbenchLink } from './client.js';
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
            if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta))
                return;
            const { candidate_count, screening_revision, workbench_url, resumed } = meta;
            if (typeof candidate_count !== 'number' || !Number.isInteger(candidate_count) || candidate_count < 0 || candidate_count > 60
                || (screening_revision !== null && !isScreeningRevision(screening_revision)))
                return;
            if (workbench_url !== queryWorkbenchLink(client.config.baseUrl, run_id, screening_revision ?? undefined))
                return;
            const count = candidate_count === 1 ? '1 metadata candidate' : `${candidate_count} metadata candidates`;
            const action = screening_revision ? 'Open the screening checklist' : 'Open the run';
            return { card: 'generic', title: 'CosMatter retrieval result', content: [
                    { type: 'text', text: `${count}${resumed === true ? ' · Previously completed' : ''}\n${action}\n${workbench_url}` },
                ] };
        },
        async execute(args, exec) {
            const result = await client.executeQuery(String(args.run_id), { authorizations: args.authorizations, query_index: args.query_index, counter: args.counter, sources: args.sources }, String(exec.callId), exec.signal);
            ctx.emit('cosmatter-research/query-executed', { run_id: result.run_id, query_kind: result.query_kind, candidate_count: result.candidate_count });
            return result;
        },
    }));
    ctx.effect(() => () => undefined);
}
