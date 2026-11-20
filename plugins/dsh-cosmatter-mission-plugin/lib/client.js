import { normalizeConfig } from './config.js';
const safeRunId = /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/;
const sensitiveKey = /(token|secret|password|authorization|api[_-]?key|path|quote|content)/i;
export function isMissionRunId(value) {
    return typeof value === 'string' && safeRunId.test(value);
}
export function missionWorkbenchUrl(baseUrl, runId) {
    const workbench = new URL('/?api=local', baseUrl);
    workbench.hash = `run=${runId}`;
    return workbench.href;
}
function bounded(value, field, max) {
    if (!value.trim() || value.trim().length > max)
        throw new Error(`${field} is invalid`);
    return value.trim();
}
export class CosMatterMissionClient {
    request;
    config;
    constructor(config = {}, request = fetch) {
        this.request = request;
        this.config = normalizeConfig(config);
    }
    async create(input, signal) {
        const payload = {
            question: bounded(input.question, 'question', 3_000),
            material: bounded(input.material, 'material', 300),
            property: bounded(input.property, 'property', 300),
            scope: bounded(input.scope, 'scope', 1_000),
        };
        if (input.run_id !== undefined) {
            if (!isMissionRunId(input.run_id))
                throw new Error('run_id is invalid');
            payload.run_id = input.run_id;
        }
        if (input.mission_type !== undefined)
            payload.mission_type = bounded(input.mission_type, 'mission_type', 80);
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        try {
            const response = await this.request(new URL('/api/missions', this.config.baseUrl), {
                method: 'POST', redirect: 'error', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(payload), signal: controller.signal,
            });
            if (response.status === 409)
                throw new Error('This CosMatter run ID is already in use. Look up the ID in the local workbench to continue an existing mission. For a new mission, omit run_id or choose a different one.');
            if (!response.ok)
                throw new Error(`CosMatter mission creation failed with HTTP ${response.status}`);
            const value = await response.json();
            const mission = validateMissionCreated(value);
            if (payload.run_id !== undefined && mission.run_id !== payload.run_id)
                throw new Error('CosMatter mission response does not match the requested run');
            return { ...mission, workbench_url: missionWorkbenchUrl(this.config.baseUrl, mission.run_id) };
        }
        finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    }
}
export function validateMissionCreated(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('CosMatter mission response is invalid');
    const result = value;
    if (Object.keys(result).some(key => sensitiveKey.test(key)))
        throw new Error('CosMatter mission response contains a forbidden field');
    const { run_id, mission_id, fleet_type, mission_type, state } = result;
    if (!isMissionRunId(run_id) || typeof mission_id !== 'string' || !/^mission_[a-z0-9_]{8,128}$/i.test(mission_id) || typeof fleet_type !== 'string' || typeof mission_type !== 'string' || state !== 'INTAKE') {
        throw new Error('CosMatter mission response is invalid');
    }
    return { run_id, mission_id, fleet_type, mission_type, state };
}
