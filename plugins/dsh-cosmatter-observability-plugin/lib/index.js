import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterObservabilityClient } from './client.js';
export const name = 'cosmatter-observability';
export const inject = ['tools'];
export function apply(ctx, config = {}) {
    const client = new CosMatterObservabilityClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_workflow_status',
        description: 'Read a count-only, loopback-only CosMatter workflow status. It never invokes providers, reads source content, accepts evidence, grants consent, or changes a run.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.workflowStatus(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/workflow-read', { run_id: result.run_id, next_stage: result.next_stage });
            return result;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_artifact_manifest',
        description: 'Read fixed, already-generated CosMatter artifact cards with title, SHA-256, time, trust status, and a fixed download route. It cannot read arbitrary paths, PDFs, MinerU Markdown, provider receipts, source URLs, credentials, or unaccepted evidence.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.artifactManifest(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/artifact-read', { run_id: result.run_id, artifact_count: result.artifact_count });
            return result;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_stage_contract',
        description: 'Read fixed completion requirements, human gates, expected symbolic outputs, and non-executing recovery routes for every CosMatter stage. It is loopback-only and cannot grant consent, dispatch providers, expose audit details, or change a run.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.stageContract(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/stage-contract-read', { run_id: result.run_id, next_stage: result.next_stage, runtime_safety: result.runtime_safety });
            return result;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_operational_telemetry',
        description: 'Read count-only local provider receipt and dispatch summaries, plus any already human-reviewed aggregate cost/latency disclosure. It is not a provider bill or performance benchmark and cannot dispatch, retry, grant consent, read requests, URLs, sources, audit details, or credentials.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.operationalTelemetry(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/telemetry-read', { run_id: result.run_id, provider_operation_count: result.provider_operations.length, cost_latency_status: result.cost_latency_status });
            return result;
        },
    }));
    ctx.tools.register(defineTool({
        name: 'cosmatter_workflow_dag',
        description: 'Read CosMatter’s fixed, linear workflow-DAG readiness projection. It declares dependencies and one eligible stage at most, but cannot schedule, dispatch, retry, grant consent, expose content, or change a run.',
        parameters: { run_id: { type: 'string', required: true } },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args, exec) {
            const result = await client.workflowDag(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/dag-read', { run_id: result.run_id, eligible_stage_count: result.eligible_stages.length, scheduler_status: result.scheduler_status });
            return result;
        },
    }));
    ctx.effect(() => () => undefined);
}
