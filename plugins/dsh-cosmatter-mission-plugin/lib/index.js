import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterMissionClient } from './client.js';
export const name = 'cosmatter-mission';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterMissionClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_mission_create',
        description: 'Create a bounded local CosMatter Mission Brief. This performs no literature, model, PDF, shell, or filesystem operation; it cannot approve plans or accept evidence.',
        parameters: {
            question: { type: 'string', required: true, description: 'Research question, up to 3000 characters.' },
            material: { type: 'string', required: true, description: 'Material scope.' },
            property: { type: 'string', required: true, description: 'Property under investigation.' },
            scope: { type: 'string', required: true, description: 'Bounded study scope.' },
            run_id: { type: 'string', description: 'Optional safe local run identifier.' },
            mission_type: { type: 'string', description: 'Optional bounded mission type.' },
        },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const mission = await client.create(args, exec.signal);
            ctx.emit('cosmatter-mission/created', { run_id: mission.run_id, mission_id: mission.mission_id, fleet_type: mission.fleet_type });
            return mission;
        },
    }));
    ctx.effect(() => () => undefined);
}
