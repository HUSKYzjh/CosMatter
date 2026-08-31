import type { Context } from '@deepseek-ai/cordis';
import '@deepseek-ai/cordis';
import type { CosMatterDocumentConfig } from './config.js';
export declare const name = "cosmatter-document";
export declare const inject: string[];
declare module '@deepseek-ai/cordis' {
    interface Events {
        'cosmatter-document/submitted'(payload: {
            run_id: string;
            document_id: string;
            task_state: string;
        }): void;
        'cosmatter-document/polled'(payload: {
            run_id: string;
            document_id: string;
            task_state: string;
        }): void;
    }
}
export declare function apply(ctx: Context, config?: CosMatterDocumentConfig): void;
