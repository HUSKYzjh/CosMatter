import { describe, expect, it } from "vitest";

import { liveBundleMatchesRun, runtimeProjectionsMatchRun } from "./liveRunIdentity";
import { demoBundle } from "./model";
import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";

describe("live run identity fence", () => {
  const status = (): RunStatus => ({ run_id: "run_1", mission_id: demoBundle.mission.missionId, state: "INTAKE" });
  const contract = (): StageContract => ({ schema_version: "cosmatter.stage-contract/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", next_stage: null, runtime_safety: "verified", stages: [] });
  const dag = (): WorkflowDag => ({ schema_version: "cosmatter.workflow-dag/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", dag_id: "dag_1", max_concurrency: 1, scheduler_status: "declarative_only_no_execution_authorization", runtime_safety: "verified", eligible_stages: [], blocked_stage_count: 0, human_review_required: true, stages: [] });
  const telemetry = (): OperationalTelemetry => ({ schema_version: "cosmatter.operational-telemetry/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", provider_operations: [], dispatch_operations: [], cost_latency_status: "not_recorded", cost_latency: [] });

  it("requires the hydrated bundle mission to match the status for that exact run", () => {
    expect(liveBundleMatchesRun("run_1", status(), demoBundle)).toBe(true);
    expect(liveBundleMatchesRun("run_2", status(), demoBundle)).toBe(false);
    expect(liveBundleMatchesRun("run_1", { ...status(), mission_id: "other" }, demoBundle)).toBe(false);
  });

  it("rejects mixed runtime projections", () => {
    expect(runtimeProjectionsMatchRun("run_1", contract(), dag(), telemetry())).toBe(true);
    expect(runtimeProjectionsMatchRun("run_1", contract(), { ...dag(), mission_id: "other" }, telemetry())).toBe(false);
    expect(runtimeProjectionsMatchRun("run_1", contract(), dag(), { ...telemetry(), run_id: "run_2" })).toBe(false);
  });
});
