import { expect, it } from "vitest";

import { stageRecoveryNavigation } from "./stageRecoveryNavigation";
import type { StageContractStage } from "./localApi";

const stage = (recovery_route: string): StageContractStage => ({
  stage: "retrieval", status: "ready", completion_requirements: ["approved_queries_executed"], human_gate: "mission_scoped_egress_consent", expected_outputs: ["history"], recovery_route, metrics: { count: 0 },
});

it("maps only closed recovery routes to local, non-executing review surfaces", () => {
  expect(stageRecoveryNavigation(stage("authorized_retrieval_review"))).toEqual({ target: "task-control", recoveryRoute: "authorized_retrieval_review" });
  expect(stageRecoveryNavigation(stage("source_map_review"))).toEqual({ target: "reader", recoveryRoute: "source_map_review" });
  expect(stageRecoveryNavigation(stage("untrusted_command"))).toBeNull();
});
