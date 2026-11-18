import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'

import { CosMatterMissionClient, type MissionHandoff } from './client.js'
import type { CosMatterMissionConfig } from './config.js'

export const name = 'cosmatter-mission'
export const inject = ['tools']

declare module '@deepseek-ai/cordis' {
  interface Events {
    'cosmatter-mission/created'(payload: Pick<MissionHandoff, 'run_id' | 'mission_id' | 'fleet_type' | 'workbench_url'>): void
  }
}

export function apply(ctx: Context, config: CosMatterMissionConfig = {}): void {
  const client = new CosMatterMissionClient(config)
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const mission = await client.create(args, exec.signal)
      ctx.emit('cosmatter-mission/created', { run_id: mission.run_id, mission_id: mission.mission_id, fleet_type: mission.fleet_type, workbench_url: mission.workbench_url })
      return mission as unknown as Record<string, JsonValue>
    },
  }))
  ctx.effect(() => () => undefined)
}
