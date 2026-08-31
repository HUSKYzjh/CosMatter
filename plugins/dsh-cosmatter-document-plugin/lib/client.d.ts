import { type CosMatterDocumentConfig, type NormalizedConfig } from './config.js';
export interface MinerUTaskStatus {
    run_id: string;
    document_id: string;
    provider: 'mineru';
    task_state: 'pending' | 'running' | 'done' | 'failed';
    trust_status: string;
    idempotency_status?: 'duplicate_completed';
}
export declare class CosMatterDocumentClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterDocumentConfig, request?: typeof fetch);
    submit(runIdValue: string, input: {
        authorizations: string[];
        document_id: string;
        source_url: string;
    }, dshCallId: string, signal?: AbortSignal): Promise<MinerUTaskStatus>;
    poll(runIdValue: string, input: {
        authorizations: string[];
        document_id: string;
    }, dshCallId: string, signal?: AbortSignal): Promise<MinerUTaskStatus>;
    private post;
}
