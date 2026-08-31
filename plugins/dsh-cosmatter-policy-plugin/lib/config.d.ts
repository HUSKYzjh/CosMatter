export interface CosMatterPolicyConfig {
    baseUrl?: string;
    timeoutMs?: number;
    maxCatalogueBytes?: number;
}
export interface NormalizedConfig {
    baseUrl: string;
    timeoutMs: number;
    maxCatalogueBytes: number;
}
export declare function normalizeConfig(config?: CosMatterPolicyConfig): NormalizedConfig;
