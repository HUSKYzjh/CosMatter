import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterDocumentClient, documentWorkbenchUrl } from './client.js';
export const name = 'cosmatter-document';
export const inject = ['tools'];
const taskGuidance = new Map([
    ['pending', 'Parsing is queued. Open the document to see its saved task status.'],
    ['running', 'Parsing is in progress. Open the document to see its saved task status.'],
    ['done', 'Parsing finished. Open the document in CosMatter for human review.'],
    ['failed', 'Parsing failed. Open the document to inspect its saved task status.'],
]);
const taskOutput = {
    schema: { type: 'object', additionalProperties: true },
    render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    presentationMeta: (_args, value) => ({
        workbench_url: value.workbench_url, task_state: value.task_state, replayed: value.idempotency_status === 'duplicate_completed',
    }),
};
export function apply(ctx, config = {}) {
    const client = new CosMatterDocumentClient(config);
    function presentTask({ run_id, document_id }, { isError, meta }) {
        if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta))
            return;
        const { task_state, workbench_url, replayed } = meta;
        const guidance = typeof task_state === 'string' && taskGuidance.get(task_state);
        if (!guidance || typeof workbench_url !== 'string' || typeof replayed !== 'boolean')
            return;
        try {
            if (workbench_url !== documentWorkbenchUrl(client.config.baseUrl, run_id, document_id))
                return;
        }
        catch {
            return;
        }
        const lines = [`Run: ${run_id}`, `Document: ${document_id}`, guidance];
        if (replayed)
            lines.push('Showing the saved receipt for this call.');
        lines.push(workbench_url);
        return { card: 'generic', title: 'MinerU document parsing', content: [{ type: 'text', text: lines.join('\n') }] };
    }
    ctx.tools.register(defineTool({
        name: 'cosmatter_mineru_source_submit',
        description: 'Submit one human-screened, content-authorized HTTPS candidate source to MinerU through the local backend. Requires exactly mission_scoped_egress_consent, mineru_file_consent, and private_content_to_mineru. Returns task metadata and a same-machine workbench_url for this candidate.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, document_id: { type: 'string', required: true }, source_url: { type: 'string', required: true } },
        output: taskOutput,
        presentCall: () => ({ card: 'generic', kind: 'execute', title: 'Submit a document to MinerU' }),
        presentResult: presentTask,
        async execute(args, exec) { const result = await client.submit(String(args.run_id), { authorizations: args.authorizations, document_id: String(args.document_id), source_url: String(args.source_url) }, String(exec.callId), exec.signal); ctx.emit('cosmatter-document/submitted', { run_id: result.run_id, document_id: result.document_id, task_state: result.task_state }); return result; },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_mineru_task_poll',
        description: 'Poll one prior MinerU task through the local backend after the same exact explicit authorizations. Returns task state and a same-machine workbench_url for this candidate. Opening the link resumes the verified local review step.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, document_id: { type: 'string', required: true } },
        output: taskOutput,
        presentCall: () => ({ card: 'generic', kind: 'fetch', title: 'Check MinerU parsing status' }),
        presentResult: presentTask,
        async execute(args, exec) { const result = await client.poll(String(args.run_id), { authorizations: args.authorizations, document_id: String(args.document_id) }, String(exec.callId), exec.signal); ctx.emit('cosmatter-document/polled', { run_id: result.run_id, document_id: result.document_id, task_state: result.task_state }); return result; },
    }));
    ctx.effect(() => () => undefined);
}
