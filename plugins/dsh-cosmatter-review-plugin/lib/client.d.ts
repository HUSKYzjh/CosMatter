import { type CosMatterReviewConfig, type NormalizedConfig } from './config.js';
export interface CandidateDecision {
    document_id: string;
    decision: 'include_for_fulltext' | 'exclude' | 'needs_metadata_review';
    reason_codes: string[];
}
export interface ScreeningTemplate {
    run_id: string;
    trust_status: string;
    candidate_count: number;
    candidates: Array<Record<string, unknown>>;
    decisions: Array<Record<string, unknown>>;
}
export interface ScreeningRecorded {
    run_id: string;
    candidate_count: number;
    decision_counts: Record<string, number>;
    trust_status: 'human_reviewed_candidate_screening_not_scientific_evidence';
}
export declare class CosMatterReviewClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterReviewConfig, request?: typeof fetch);
    template(runIdValue: string, signal?: AbortSignal): Promise<ScreeningTemplate>;
    record(runIdValue: string, decisions: CandidateDecision[], signal?: AbortSignal): Promise<ScreeningRecorded>;
    private fetchJson;
}
