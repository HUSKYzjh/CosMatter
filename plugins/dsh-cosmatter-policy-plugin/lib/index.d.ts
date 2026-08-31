import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterPolicyConfig } from './config.js';
export declare const name = "cosmatter-policy";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-policy/catalogue-read'(payload: {
            plugin_count: number;
        }): void;
        'cosmatter-policy/plan-created'(payload: {
            run_id: string;
            plugin_id: string;
            permitted: boolean;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterPolicyConfig): void;
