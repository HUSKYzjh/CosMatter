import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterMissionConfig } from './config.js';
export declare const name = "cosmatter-mission";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-mission/created'(payload: {
            run_id: string;
            mission_id: string;
            fleet_type: string;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterMissionConfig): void;
