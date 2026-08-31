import { expect, it } from "vitest";

import type { WorkflowDag } from "./localApi";
import { workflowDagRail } from "./workflowDagProjection";

function dag(): WorkflowDag {
  return {
    schema_version: "cosmatter.workflow-dag/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback_declared_dag_readiness_projection_not_execution_authorization", dag_id: "cosmatter_review_gated_linear_workflow", max_concurrency: 1,
    scheduler_status: "declarative_only_no_execution_authorization", runtime_safety: "verified", eligible_stages: ["retrieval"], blocked_stage_count: 6, human_review_required: false,
    stages: [
      ["intake", [], ["mission.define"], "mission", "local_review_gated"],
      ["plan", ["intake"], ["planning.orchestrate"], "mission", "local_review_gated"],
      ["retrieval", ["plan"], ["literature.metadata_retrieval", "literature.deduplicate_and_rank"], "public_metadata", "explicit_consent_required"],
      ["screening", ["retrieval"], [], "public_metadata", "human_review_required"],
      ["parse", ["screening"], ["document.mineru_private_parse"], "private_fulltext", "explicit_consent_required"],
      ["extraction", ["parse"], ["evidence.material_extract", "evidence.source_map", "evidence.verify"], "reviewable_excerpt", "human_review_required"],
      ["gap", ["extraction"], ["research.gap_candidates"], "accepted_evidence", "human_review_required"],
      ["report", ["gap"], ["report.generate"], "accepted_evidence", "local_review_gated"],
      ["evaluation", ["report"], [], "run_summary", "human_review_required"],
    ].map(([stage, depends_on, allowed_descriptors, data_classification, execution_class], index) => ({
      stage: stage as WorkflowDag["stages"][number]["stage"], depends_on: depends_on as WorkflowDag["stages"][number]["depends_on"],
      status: index < 2 ? "completed" : index === 2 ? "ready" : "blocked", allowed_descriptors: allowed_descriptors as string[], data_classification, execution_class,
    })) as WorkflowDag["stages"],
  };
}

it("projects only the fixed serial, nonexecuting DAG rail", () => {
  expect(workflowDagRail(dag())).toMatchObject({ state: "declared", eligibleStage: "retrieval" });
  expect(workflowDagRail(dag()).stages).toHaveLength(9);
});

it("hides malformed or nonserial declarations rather than rendering them as commands", () => {
  const mutated = dag();
  mutated.max_concurrency = 2 as 1;
  expect(workflowDagRail(mutated)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
  const outOfOrder = dag();
  outOfOrder.stages[4].status = "completed";
  expect(workflowDagRail(outOfOrder)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
  const descriptor = dag();
  descriptor.stages[2].allowed_descriptors = ["unknown.execute"];
  expect(workflowDagRail(descriptor)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
  const trust = dag();
  trust.trust_status = "unverified";
  expect(workflowDagRail(trust)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
  const count = dag();
  count.blocked_stage_count = 0;
  expect(workflowDagRail(count)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
  const malformed = dag();
  malformed.stages[2].allowed_descriptors = null as unknown as string[];
  expect(workflowDagRail(malformed)).toEqual({ state: "unavailable", stages: [], eligibleStage: null });
});
