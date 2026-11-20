import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterMissionClient, isMissionRunId, missionWorkbenchUrl } from './client.js';
export const name = 'cosmatter-mission';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterMissionClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_mission_create',
        description: 'Create a bounded local CosMatter Mission Brief. Return its run ID and same-machine workbench link (workbench_url) for the user. This tool does not retrieve literature, call a model, parse PDFs, approve plans, or accept evidence.',
        parameters: {
            question: { type: 'string', required: true, description: 'Research question, up to 3000 characters.' },
            material: { type: 'string', required: true, description: 'Material scope.' },
            property: { type: 'string', required: true, description: 'Property under investigation.' },
            scope: { type: 'string', required: true, description: 'Bounded study scope.' },
            run_id: { type: 'string', description: 'Optional safe local run identifier.' },
            mission_type: { type: 'string', description: 'Optional bounded mission type.' },
        },
        output: {
            schema: { type: 'object', additionalProperties: true },
            render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
            presentationMeta: (_args, value) => ({ run_id: value.run_id ?? null, workbench_url: value.workbench_url ?? null }),
        },
        presentCall: () => ({ card: 'generic', kind: 'edit', title: 'Create a CosMatter mission' }),
        presentResult: (args, { isError, meta }) => {
            if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta))
                return;
            const { run_id, workbench_url } = meta;
            if (!isMissionRunId(run_id) || (args.run_id !== undefined && run_id !== args.run_id)
                || workbench_url !== missionWorkbenchUrl(client.config.baseUrl, run_id))
                return;
            return { card: 'generic', title: 'CosMatter mission created', content: [
                    { type: 'text', text: `${run_id}\n${workbench_url}` },
                ] };
        },
        async execute(args, exec) {
            const mission = await client.create(args, exec.signal);
            ctx.emit('cosmatter-mission/created', { run_id: mission.run_id, mission_id: mission.mission_id, fleet_type: mission.fleet_type, workbench_url: mission.workbench_url });
            return mission;
        },
    }));
    ctx.effect(() => () => undefined);
}
