import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import { type MissionHandoff } from './client.js';
import type { CosMatterMissionConfig } from './config.js';
export declare const name = "cosmatter-mission";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-mission/created'(payload: Pick<MissionHandoff, 'run_id' | 'mission_id' | 'fleet_type' | 'workbench_url'>): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterMissionConfig): void;
