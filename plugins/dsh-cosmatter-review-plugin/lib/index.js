import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterReviewClient } from './client.js';
export const name = 'cosmatter-review';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterReviewClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_candidate_screening_template',
        description: 'Read the metadata-only screening checklist and recorded human decisions. A workbench link targets the returned checklist revision.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.template(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-review/template-read', { run_id: result.run_id, candidate_count: result.candidate_count });
            if (!result.checklist_revision || !result.candidate_count || result.run_id.length > 255)
                return result;
            const link = new URL('/?api=local', client.config.baseUrl);
            link.hash = new URLSearchParams({ run: result.run_id, screening: result.checklist_revision }).toString();
            return { ...result, workbench_url: link.href };
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_candidate_screening_record',
        description: 'Record the human reviewer’s decision and reasons for every listed candidate. Pass the checklist revision returned by the read tool with these decisions.',
        parameters: {
            run_id: { type: 'string', required: true },
            checklist_revision: { type: 'string', description: 'Revision from the checklist used by the human reviewer.' },
            decisions: { type: 'array', required: true, items: { type: 'object', additionalProperties: true } },
        },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.record(String(args.run_id), args.decisions, exec.signal, args.checklist_revision);
            ctx.emit('cosmatter-review/recorded', { run_id: result.run_id, candidate_count: result.candidate_count });
            return result;
        },
    }));
    ctx.effect(() => () => undefined);
}
