import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterResearchConfig } from './config.js';
export declare const name = "cosmatter-research";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-research/plan-drafted'(payload: {
            run_id: string;
        }): void;
        'cosmatter-research/plan-approved'(payload: {
            run_id: string;
            plan_id: string;
        }): void;
        'cosmatter-research/query-executed'(payload: {
            run_id: string;
            query_kind: string;
            candidate_count: number;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterResearchConfig): void;
