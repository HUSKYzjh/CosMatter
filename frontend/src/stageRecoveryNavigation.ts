import type { StageContractStage } from "./localApi";

export type StageRecoveryTarget = "task-control" | "graph" | "reader" | "horizon";

export interface StageRecoveryNavigation {
  target: StageRecoveryTarget;
  recoveryRoute: string;
}

/**
 * Convert the closed backend recovery-route vocabulary into a local navigation
 * target.  These targets only focus an existing review surface; they never
 * submit retrieval, upload a document, or approve an artifact.
 */
export function stageRecoveryNavigation(stage: StageContractStage | null): StageRecoveryNavigation | null {
  if (!stage) return null;
  const target = ({
    mission_boundary_review: "task-control",
    plan_review: "task-control",
    authorized_retrieval_review: "task-control",
    candidate_screening_review: "graph",
    content_access_review: "graph",
    source_map_review: "reader",
    counterevidence_review: "task-control",
    report_audit_review: "horizon",
    evaluation_review: "horizon",
  } as Record<string, StageRecoveryTarget>)[stage.recovery_route];
  return target ? { target, recoveryRoute: stage.recovery_route } : null;
}
