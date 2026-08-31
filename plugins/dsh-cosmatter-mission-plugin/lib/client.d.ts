import { type CosMatterMissionConfig, type NormalizedConfig } from './config.js';
export interface MissionInput {
    question: string;
    material: string;
    property: string;
    scope: string;
    run_id?: string;
    mission_type?: string;
}
export interface MissionCreated {
    run_id: string;
    mission_id: string;
    fleet_type: string;
    mission_type: string;
    state: 'INTAKE';
}
export declare class CosMatterMissionClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterMissionConfig, request?: typeof fetch);
    create(input: MissionInput, signal?: AbortSignal): Promise<MissionCreated>;
}
export declare function validateMissionCreated(value: unknown): MissionCreated;
