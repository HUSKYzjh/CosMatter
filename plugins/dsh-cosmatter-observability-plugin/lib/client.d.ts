import { type CosMatterObservabilityConfig, type NormalizedConfig } from './config.js';
export interface WorkflowStage {
    stage: string;
    status: string;
    counts: Record<string, number>;
}
export interface WorkflowStatus {
    schema_version: '1.0';
    run_id: string;
    mission_id: string;
    trust_status: 'loopback_workflow_status_not_scientific_evidence';
    next_stage: string | null;
    stages: WorkflowStage[];
}
export interface StageContractStage {
    stage: string;
    status: string;
    completion_requirements: string[];
    human_gate: string;
    expected_outputs: string[];
    recovery_route: string;
    metrics: Record<string, number>;
}
export interface StageContract {
    schema_version: 'cosmatter.stage-contract/v1';
    run_id: string;
    mission_id: string;
    trust_status: 'loopback_stage_contract_not_scientific_evidence_or_execution_authorization';
    next_stage: string | null;
    runtime_safety: string;
    stages: StageContractStage[];
}
export interface ProviderOperationTelemetry {
    provider: string;
    operation: string;
    request_count: number;
    successful_response_count: number;
    client_error_count: number;
    server_error_count: number;
    other_status_count: number;
}
export interface DispatchOperationTelemetry {
    operation: string;
    dispatch_count: number;
    completed_count: number;
    incomplete_count: number;
    unknown_outcome_count: number;
}
export interface CostLatencyTelemetry {
    provider_id: string;
    request_count: number;
    successful_request_count: number;
    failed_request_count: number;
    currency: string;
    total_cost: number;
    median_latency_seconds: number;
    p95_latency_seconds: number;
}
export interface OperationalTelemetry {
    schema_version: 'cosmatter.operational-telemetry/v1';
    run_id: string;
    mission_id: string;
    trust_status: 'loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence';
    provider_operations: ProviderOperationTelemetry[];
    dispatch_operations: DispatchOperationTelemetry[];
    cost_latency_status: string;
    cost_latency: CostLatencyTelemetry[];
}
export interface WorkflowDagStage {
    stage: string;
    depends_on: string[];
    status: string;
    allowed_descriptors: string[];
    data_classification: string;
    execution_class: string;
}
export interface WorkflowDag {
    schema_version: 'cosmatter.workflow-dag/v1';
    run_id: string;
    mission_id: string;
    trust_status: 'loopback_declared_dag_readiness_projection_not_execution_authorization';
    dag_id: 'cosmatter_review_gated_linear_workflow';
    max_concurrency: 1;
    scheduler_status: 'declarative_only_no_execution_authorization';
    runtime_safety: string;
    eligible_stages: string[];
    blocked_stage_count: number;
    human_review_required: boolean;
    stages: WorkflowDagStage[];
}
export interface ArtifactCard {
    artifact_id: string;
    title: string;
    media_type: string;
    sha256: string;
    generated_at: string;
    trust_status: string;
    download_path: string;
}
export interface ArtifactManifest {
    schema_version: 'cosmatter.artifact/v1';
    run_id: string;
    mission_id: string;
    trust_status: 'allowlisted_artifact_index_not_scientific_evidence';
    artifact_count: number;
    artifacts: ArtifactCard[];
}
export declare class CosMatterObservabilityClient {
    private readonly request;
    readonly config: NormalizedConfig;
    constructor(config?: CosMatterObservabilityConfig, request?: typeof fetch);
    workflowStatus(runIdValue: string, signal?: AbortSignal): Promise<WorkflowStatus>;
    artifactManifest(runIdValue: string, signal?: AbortSignal): Promise<ArtifactManifest>;
    stageContract(runIdValue: string, signal?: AbortSignal): Promise<StageContract>;
    operationalTelemetry(runIdValue: string, signal?: AbortSignal): Promise<OperationalTelemetry>;
    workflowDag(runIdValue: string, signal?: AbortSignal): Promise<WorkflowDag>;
}
export declare function validateWorkflowStatus(value: unknown, expectedRunId: string): WorkflowStatus;
export declare function validateArtifactManifest(value: unknown, expectedRunId: string): ArtifactManifest;
export declare function validateStageContract(value: unknown, expectedRunId: string): StageContract;
export declare function validateOperationalTelemetry(value: unknown, expectedRunId: string): OperationalTelemetry;
export declare function validateWorkflowDag(value: unknown, expectedRunId: string): WorkflowDag;
