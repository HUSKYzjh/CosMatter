import { type CosMatterGraphConfig, type NormalizedConfig } from './config.js';
import { type GraphSnapshot } from './contract.js';
export declare class CosMatterLoopbackClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterGraphConfig, request?: typeof fetch);
    graph(runIdValue: string, options?: {
        nodeType?: string;
        offset?: number;
        limit?: number;
        signal?: AbortSignal;
    }): Promise<GraphSnapshot>;
    searchAcceptedEvidence(runIdValue: string, query: string, limit?: number, signal?: AbortSignal): Promise<Record<string, unknown>>;
    requestReview(runIdValue: string, nodeIds: string[], rationale: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
    draftPlan(runIdValue: string, nodeIds: string[], intent: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
}
