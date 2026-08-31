import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterReviewConfig } from './config.js';
export declare const name = "cosmatter-review";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-review/template-read'(payload: {
            run_id: string;
            candidate_count: number;
        }): void;
        'cosmatter-review/recorded'(payload: {
            run_id: string;
            candidate_count: number;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterReviewConfig): void;
