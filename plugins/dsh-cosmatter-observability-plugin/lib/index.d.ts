import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterObservabilityConfig } from './config.js';
export declare const name = "cosmatter-observability";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-observability/workflow-read'(payload: {
            run_id: string;
            next_stage: string | null;
        }): void;
        'cosmatter-observability/artifact-read'(payload: {
            run_id: string;
            artifact_count: number;
        }): void;
        'cosmatter-observability/stage-contract-read'(payload: {
            run_id: string;
            next_stage: string | null;
            runtime_safety: string;
        }): void;
        'cosmatter-observability/telemetry-read'(payload: {
            run_id: string;
            provider_operation_count: number;
            cost_latency_status: string;
        }): void;
        'cosmatter-observability/dag-read'(payload: {
            run_id: string;
            eligible_stage_count: number;
            scheduler_status: string;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterObservabilityConfig): void;
