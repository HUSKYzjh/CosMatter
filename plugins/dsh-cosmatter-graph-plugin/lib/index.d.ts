import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterGraphConfig } from './config.js';
export declare const name = "cosmatter-graph";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-graph/query'(payload: {
            run_id: string;
            graph_id: string;
            node_count: number;
            edge_count: number;
        }): void;
        'cosmatter-graph/plan-created'(payload: {
            run_id: string;
            intent_length: number;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterGraphConfig): void;
