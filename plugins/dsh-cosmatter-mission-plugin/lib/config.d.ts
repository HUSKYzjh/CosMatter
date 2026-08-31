export interface CosMatterMissionConfig {
    baseUrl?: string;
    timeoutMs?: number;
}
export interface NormalizedConfig {
    baseUrl: string;
    timeoutMs: number;
}
export declare function normalizeConfig(config?: CosMatterMissionConfig): NormalizedConfig;
