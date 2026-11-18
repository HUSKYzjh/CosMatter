import '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CosMatterObservabilityClient, localWorkbenchUrl } from './client.js';
export const name = 'cosmatter-observability';
export const inject = ['tools'];
function isWorkbenchLink(value, runId, artifactList = false) {
    if (typeof runId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(runId) || typeof value !== 'string')
        return false;
    try {
        const link = new URL(value);
        return link.protocol === 'http:' && link.hostname === '127.0.0.1'
            && value === localWorkbenchUrl(link.origin, runId, artifactList);
    }
    catch {
        return false;
    }
}
export function apply(ctx, config = {}) {
    const client = new CosMatterObservabilityClient(config);
    ctx.tools.register(defineTool({
        name: 'cosmatter_recent_runs',
        description: 'List up to twelve recent local CosMatter run IDs, update times, stopped flags and workbench links. Use it when a run ID is unknown.',
        parameters: {},
        output: {
            schema: { type: 'object', additionalProperties: true },
            render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
            presentationMeta: (_args, value) => value.runs ?? null,
        },
        presentCall: () => ({ card: 'generic', kind: 'read', title: 'Find recent CosMatter runs' }),
        presentResult: (_args, { isError, meta }) => {
            if (isError || !Array.isArray(meta) || meta.length > 12)
                return;
            const entries = [];
            for (const row of meta) {
                if (!row || typeof row !== 'object' || Array.isArray(row))
                    return;
                const { run_id, workbench_url, stopped, updated_at } = row;
                if (!isWorkbenchLink(workbench_url, run_id) || typeof stopped !== 'boolean'
                    || typeof updated_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(updated_at))
                    return;
                entries.push(`${run_id} · ${stopped ? 'Stopped' : 'Available'} · ${updated_at}\n${workbench_url}`);
            }
            return { card: 'generic', title: 'Recent CosMatter runs', content: [
                    { type: 'text', text: entries.join('\n\n') || 'No local runs found.' },
                ] };
        },
        async execute(_args, exec) {
            return await client.recentRunLinks(exec.signal);
        },
    }));
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
        description: 'Read fixed, already-generated CosMatter artifact cards with title, SHA-256, time, trust status, and fixed download routes. The workbench link opens the saved artifact list for this run.',
        parameters: { run_id: { type: 'string', required: true } },
        output: {
            schema: { type: 'object', additionalProperties: true },
            render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
            presentationMeta: (_args, value) => ({ workbench_url: value.workbench_url ?? null, artifact_count: value.artifact_count ?? null }),
        },
        presentCall: ({ run_id }) => ({ card: 'generic', kind: 'read', title: 'Read saved CosMatter artifacts', rawInput: run_id }),
        presentResult: ({ run_id }, { isError, meta }) => {
            if (isError || !meta || typeof meta !== 'object' || Array.isArray(meta))
                return;
            const { artifact_count, workbench_url } = meta;
            if (!isWorkbenchLink(workbench_url, run_id, true) || typeof artifact_count !== 'number'
                || !Number.isSafeInteger(artifact_count) || artifact_count < 0)
                return;
            const summary = artifact_count === 1 ? '1 saved artifact' : `${artifact_count} saved artifacts`;
            return { card: 'generic', title: 'Saved CosMatter artifacts', content: [
                    { type: 'text', text: `${run_id} · ${summary}\n${workbench_url}` },
                ] };
        },
        async execute(args, exec) {
            const result = await client.artifactManifest(String(args.run_id), exec.signal);
            ctx.emit('cosmatter-observability/artifact-read', { run_id: result.run_id, artifact_count: result.artifact_count });
            return { ...result, workbench_url: localWorkbenchUrl(client.config.baseUrl, result.run_id, true) };
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
