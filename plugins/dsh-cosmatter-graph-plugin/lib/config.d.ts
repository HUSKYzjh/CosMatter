export interface CosMatterGraphConfig {
    /** A loopback-only CosMatter preview API endpoint. */
    baseUrl?: string;
    timeoutMs?: number;
    maxGraphBytes?: number;
}
export interface NormalizedConfig {
    baseUrl: URL;
    timeoutMs: number;
    maxGraphBytes: number;
}
export declare function normalizeConfig(config?: CosMatterGraphConfig): NormalizedConfig;
