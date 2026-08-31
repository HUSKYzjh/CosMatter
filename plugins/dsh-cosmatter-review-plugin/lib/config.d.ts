export interface CosMatterReviewConfig {
    baseUrl?: string;
    timeoutMs?: number;
    maxResponseBytes?: number;
}
export interface NormalizedConfig {
    baseUrl: string;
    timeoutMs: number;
    maxResponseBytes: number;
}
export declare function normalizeConfig(config?: CosMatterReviewConfig): NormalizedConfig;
