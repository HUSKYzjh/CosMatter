import type { WorkflowDag, WorkflowStageName, WorkflowStageStatus } from "./localApi";

export const WORKFLOW_DAG_STAGES = ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"] as const satisfies readonly WorkflowStageName[];

const DAG_TRUST_STATUS = "loopback_declared_dag_readiness_projection_not_execution_authorization";
const FIXED_DAG = [
  { stage: "intake", dependsOn: [], descriptors: ["mission.define"], dataClassification: "mission", executionClass: "local_review_gated" },
  { stage: "plan", dependsOn: ["intake"], descriptors: ["planning.orchestrate"], dataClassification: "mission", executionClass: "local_review_gated" },
  { stage: "retrieval", dependsOn: ["plan"], descriptors: ["literature.metadata_retrieval", "literature.deduplicate_and_rank"], dataClassification: "public_metadata", executionClass: "explicit_consent_required" },
  { stage: "screening", dependsOn: ["retrieval"], descriptors: [], dataClassification: "public_metadata", executionClass: "human_review_required" },
  { stage: "parse", dependsOn: ["screening"], descriptors: ["document.mineru_private_parse"], dataClassification: "private_fulltext", executionClass: "explicit_consent_required" },
  { stage: "extraction", dependsOn: ["parse"], descriptors: ["evidence.material_extract", "evidence.source_map", "evidence.verify"], dataClassification: "reviewable_excerpt", executionClass: "human_review_required" },
  { stage: "gap", dependsOn: ["extraction"], descriptors: ["research.gap_candidates"], dataClassification: "accepted_evidence", executionClass: "human_review_required" },
  { stage: "report", dependsOn: ["gap"], descriptors: ["report.generate"], dataClassification: "accepted_evidence", executionClass: "local_review_gated" },
  { stage: "evaluation", dependsOn: ["report"], descriptors: [], dataClassification: "run_summary", executionClass: "human_review_required" },
] as const;

const sameStrings = (actual: unknown, expected: readonly string[]) => Array.isArray(actual) && actual.length === expected.length && actual.every((value, index) => typeof value === "string" && value === expected[index]);

export type WorkflowDagRail =
  | { state: "unavailable"; stages: []; eligibleStage: null }
  | { state: "declared"; stages: Array<{ stage: WorkflowStageName; status: WorkflowStageStatus }>; eligibleStage: WorkflowStageName | null };

/**
 * Keep the UI's fleet rail bound to the checked-in serial DAG shape.
 * A malformed loopback response is rendered as unavailable rather than being
 * mistaken for a scheduler command or an arbitrary workflow definition.
 */
export function workflowDagRail(dag: WorkflowDag | null): WorkflowDagRail {
  if (!dag
    || dag.schema_version !== "cosmatter.workflow-dag/v1"
    || typeof dag.run_id !== "string" || !dag.run_id.trim()
    || typeof dag.mission_id !== "string" || !dag.mission_id.trim()
    || dag.trust_status !== DAG_TRUST_STATUS
    || dag.dag_id !== "cosmatter_review_gated_linear_workflow"
    || dag.max_concurrency !== 1
    || dag.scheduler_status !== "declarative_only_no_execution_authorization"
    || !["verified", "attention_required"].includes(dag.runtime_safety)
    || !Array.isArray(dag.stages)
    || dag.stages.length !== WORKFLOW_DAG_STAGES.length
    || !Array.isArray(dag.eligible_stages)
    || dag.eligible_stages.length > 1) return { state: "unavailable", stages: [], eligibleStage: null };

  if (dag.stages.some((rawItem, index) => {
    if (!rawItem || typeof rawItem !== "object" || Array.isArray(rawItem)) return true;
    const item = rawItem as unknown as Record<string, unknown>;
    const fixed = FIXED_DAG[index];
    return item.stage !== fixed.stage
      || typeof item.status !== "string"
      || !["completed", "ready", "waiting_human_review", "blocked"].includes(item.status)
      || !sameStrings(item.depends_on, fixed.dependsOn)
      || !sameStrings(item.allowed_descriptors, fixed.descriptors)
      || item.data_classification !== fixed.dataClassification
      || item.execution_class !== fixed.executionClass;
  })) return { state: "unavailable", stages: [], eligibleStage: null };
  const stages = dag.stages.map((item) => ({ stage: item.stage, status: item.status }));

  const firstUnfinished = stages.find((item) => item.status !== "completed")?.stage ?? null;
  const completedAfterFirstUnfinished = firstUnfinished !== null && stages.slice(WORKFLOW_DAG_STAGES.indexOf(firstUnfinished) + 1).some((item) => item.status === "completed");
  const eligibleStage = dag.eligible_stages[0] ?? null;
  const expectedEligible = dag.runtime_safety === "verified" && firstUnfinished !== null && stages.find((item) => item.stage === firstUnfinished)?.status === "ready" ? firstUnfinished : null;
  const blockedStageCount = stages.filter((item) => item.status === "blocked").length;
  const humanReviewRequired = stages.some((item) => item.status === "waiting_human_review");
  if (completedAfterFirstUnfinished || eligibleStage !== expectedEligible || dag.blocked_stage_count !== blockedStageCount || dag.human_review_required !== humanReviewRequired) return { state: "unavailable", stages: [], eligibleStage: null };
  return { state: "declared", stages, eligibleStage };
}
