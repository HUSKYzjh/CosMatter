import { type CosMatterPolicyConfig, type NormalizedConfig } from './config.js';
export interface PolicyCatalogue {
    catalogue_api_version: '2.0';
    plugins: Array<Record<string, unknown>>;
    trust_status: 'static_catalogue_not_plugin_execution_or_evidence_acceptance';
}
export interface AuthorizationPlan {
    mission_id: string;
    plugin_id: string;
    permitted: boolean;
    reason: string;
    missing_authorizations: string[];
    requires_human_review: boolean;
    next_boundary: string;
    trust_status: 'nonexecuting_authorization_plan_not_consent_or_execution';
}
export declare class CosMatterPolicyClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterPolicyConfig, request?: typeof fetch);
    catalogue(signal?: AbortSignal): Promise<PolicyCatalogue>;
    authorizationPlan(runIdValue: string, pluginId: string, authorizations: string[], signal?: AbortSignal): Promise<AuthorizationPlan>;
    private fetchJson;
}
