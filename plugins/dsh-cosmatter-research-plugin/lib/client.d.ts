import { type CosMatterResearchConfig, type NormalizedConfig } from './config.js';
export interface ResearchPlan {
    subquestions: string[];
    queries: string[];
    counter_queries: string[];
    max_rounds?: number;
    max_papers?: number;
}
export interface PlanDraft {
    run_id: string;
    trust_status: 'untrusted_draft';
    content: string;
    idempotency_status?: 'duplicate_completed';
}
export interface ApprovedPlan {
    run_id: string;
    plan_id: string;
    queries: string[];
    counter_queries: string[];
}
export interface QueryResult {
    run_id: string;
    query_kind: 'primary' | 'counter';
    query_index: number;
    sources: string[];
    source_counts: Record<string, number>;
    candidate_count: number;
    candidates: Array<Record<string, unknown>>;
    idempotency_status?: 'duplicate_completed';
}
export declare class CosMatterResearchClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterResearchConfig, request?: typeof fetch);
    draftPlan(runIdValue: string, authorizations: string[], dshCallId: string, signal?: AbortSignal): Promise<PlanDraft>;
    approvePlan(runIdValue: string, plan: ResearchPlan, signal?: AbortSignal): Promise<ApprovedPlan>;
    executeQuery(runIdValue: string, input: {
        authorizations: string[];
        query_index: number;
        counter?: boolean;
        sources: string[];
    }, dshCallId: string, signal?: AbortSignal): Promise<QueryResult>;
    private post;
}
