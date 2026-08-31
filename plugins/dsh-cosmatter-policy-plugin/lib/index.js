import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterPolicyClient } from './client.js';
export const name = 'cosmatter-policy';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterPolicyClient(config);
    ctx.tools.register(defineTool({ name: 'cosmatter_plugin_catalogue', description: 'Read the static CosMatter capability catalogue. It does not load code, grant permission, execute adapters, or accept evidence.', parameters: {}, output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] }, async execute(_args, exec) { const catalogue = await client.catalogue(exec.signal); ctx.emit('cosmatter-policy/catalogue-read', { plugin_count: catalogue.plugins.length }); return catalogue; } }));
    ctx.tools.register(defineTool({ name: 'cosmatter_plugin_authorization_plan', description: 'Create a non-executing authorization boundary evaluation for an existing local run. It is not consent, dispatch, a provider call, or evidence acceptance.', parameters: { run_id: { type: 'string', required: true }, plugin_id: { type: 'string', required: true }, authorizations: { type: 'array', required: true, items: { type: 'string' } } }, output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] }, async execute(args, exec) { const plan = await client.authorizationPlan(args.run_id, args.plugin_id, args.authorizations, exec.signal); ctx.emit('cosmatter-policy/plan-created', { run_id: args.run_id, plugin_id: args.plugin_id, permitted: plan.permitted }); return plan; } }));
    ctx.effect(() => () => undefined);
}
