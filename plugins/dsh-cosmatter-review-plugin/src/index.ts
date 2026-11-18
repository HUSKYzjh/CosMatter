import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'
import { CosMatterReviewClient } from './client.js'
import type { CosMatterReviewConfig } from './config.js'
export const name = 'cosmatter-review'
export const inject = ['tools']

declare module '@deepseek-ai/cordis' {
  interface Events {
    'cosmatter-review/template-read'(payload: { run_id: string; candidate_count: number }): void
    'cosmatter-review/recorded'(payload: { run_id: string; candidate_count: number }): void
  }
}

export function apply(ctx: Context, config: CosMatterReviewConfig = {}): void {
  const client = new CosMatterReviewClient(config)
  ctx.tools.register(defineTool({
    name: 'cosmatter_candidate_screening_template',
    description: 'Read the metadata-only screening checklist and any human decisions already recorded for this run.',
    parameters: { run_id: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args, exec) {
      const result = await client.template(String(args.run_id), exec.signal)
      ctx.emit('cosmatter-review/template-read', { run_id: result.run_id, candidate_count: result.candidate_count })
      return result as unknown as Record<string, JsonValue>
    },
  }))
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
      const result = await client.record(String(args.run_id), args.decisions as never[], exec.signal, args.checklist_revision)
      ctx.emit('cosmatter-review/recorded', { run_id: result.run_id, candidate_count: result.candidate_count })
      return result as unknown as Record<string, JsonValue>
    },
  }))
  ctx.effect(() => () => undefined)
}
