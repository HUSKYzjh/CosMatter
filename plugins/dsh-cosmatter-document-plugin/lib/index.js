import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterDocumentClient } from './client.js';
export const name = 'cosmatter-document';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterDocumentClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_mineru_source_submit',
        description: 'Submit one human-screened, content-authorized HTTPS candidate source to MinerU through the local backend. Requires exactly mission_scoped_egress_consent, mineru_file_consent, and private_content_to_mineru. It returns task metadata only; it never returns parser output, a source URL, full text, or accepted evidence.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, document_id: { type: 'string', required: true }, source_url: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) { const result = await client.submit(String(args.run_id), { authorizations: args.authorizations, document_id: String(args.document_id), source_url: String(args.source_url) }, String(exec.callId), exec.signal); ctx.emit('cosmatter-document/submitted', { run_id: result.run_id, document_id: result.document_id, task_state: result.task_state }); return result; },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_mineru_task_poll',
        description: 'Poll one prior MinerU task through the local backend after the same exact explicit authorizations. It returns task state only and never downloads parser output or accepts evidence.',
        parameters: { run_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } }, document_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) { const result = await client.poll(String(args.run_id), { authorizations: args.authorizations, document_id: String(args.document_id) }, String(exec.callId), exec.signal); ctx.emit('cosmatter-document/polled', { run_id: result.run_id, document_id: result.document_id, task_state: result.task_state }); return result; },
    }));
    ctx.effect(() => () => undefined);
}
