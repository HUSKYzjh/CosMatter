import { describe, expect, it } from "vitest";

import { liveBundleMatchesRun, localRunArtifactsLink, localRunLink, localRunScreeningLink, parseLocalRunLink, runtimeProjectionsMatchRun } from "./liveRunIdentity";
import { demoBundle } from "./model";
import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";

describe("live run identity fence", () => {
  const status = (): RunStatus => ({ run_id: "run_1", mission_id: demoBundle.mission.missionId, state: "INTAKE" });
  const contract = (): StageContract => ({ schema_version: "cosmatter.stage-contract/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", next_stage: null, runtime_safety: "verified", stages: [] });
  const dag = (): WorkflowDag => ({ schema_version: "cosmatter.workflow-dag/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", dag_id: "dag_1", max_concurrency: 1, scheduler_status: "declarative_only_no_execution_authorization", runtime_safety: "verified", eligible_stages: [], blocked_stage_count: 0, human_review_required: true, stages: [] });
  const telemetry = (): OperationalTelemetry => ({ schema_version: "cosmatter.operational-telemetry/v2", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", provider_operations: [], dispatch_operations: [], validation_rejections: [], cost_latency_status: "not_recorded", cost_latency: [] });

  it("round-trips document links and rejects ambiguous or malformed handoffs", () => {
    const url = new URL(localRunLink("http://127.0.0.1:8790", "run_1", "文献 & x=1"));
    expect(url.search).toBe("?api=local");
    expect(parseLocalRunLink(url.hash)).toEqual({ runId: "run_1", documentId: "文献 & x=1", evidenceId: null });
    expect(parseLocalRunLink("#run=run_1")).toEqual({ runId: "run_1", documentId: null, evidenceId: null });
    const evidenceUrl = new URL(localRunLink("http://127.0.0.1:8790", "run_1", "文献 & x=1", "证据 + y=2"));
    expect(parseLocalRunLink(evidenceUrl.hash)).toEqual({ runId: "run_1", documentId: "文献 & x=1", evidenceId: "证据 + y=2" });
    for (const fragment of ["#run=../run", "#run=run_1&run=run_2", "#run=run_1&document=", "#run=run_1&document=a%00b", "#run=run_1&document=a&document=b", "#run=run_1&view=reader", "#run=run_1&evidence=e", "#run=run_1&document=a&evidence=", "#run=run_1&document=a&evidence=x&evidence=y", "#run=run_1&document=a&evidence=x%0Ay"]) {
      expect(parseLocalRunLink(fragment)).toBeNull();
    }
  });

  it("requires the hydrated bundle mission to match the status for that exact run", () => {
    expect(liveBundleMatchesRun("run_1", status(), demoBundle)).toBe(true);
    expect(liveBundleMatchesRun("run_2", status(), demoBundle)).toBe(false);
    expect(liveBundleMatchesRun("run_1", { ...status(), mission_id: "other" }, demoBundle)).toBe(false);
  });

  it("binds linked screening to one run and one checklist revision", () => {
    const revision = "a".repeat(64);
    const url = new URL(localRunScreeningLink("http://127.0.0.1:8790", "run_1", revision));
    expect(url.href).toBe(`http://127.0.0.1:8790/?api=local#run=run_1&screening=${revision}`);
    expect(parseLocalRunLink(url.hash)).toEqual({ runId: "run_1", documentId: null, evidenceId: null, screeningRevision: revision });
    for (const suffix of ["&document=a", "&document=a&evidence=b", "&screening=" + revision]) expect(parseLocalRunLink(url.hash + suffix)).toBeNull();
    expect(parseLocalRunLink("#run=run_1&screening=bad")).toBeNull();
  });

  it("opens the artifact list only for an unambiguous local run selector", () => {
    const url = new URL(localRunArtifactsLink("http://127.0.0.1:8790", "run_1"));
    expect(url.href).toBe("http://127.0.0.1:8790/?api=local#run=run_1&artifacts=1");
    expect(parseLocalRunLink(url.hash)).toEqual({ runId: "run_1", documentId: null, evidenceId: null, artifactList: true });
    for (const suffix of ["&artifacts=1", "&document=p", "&screening=" + "a".repeat(64)]) expect(parseLocalRunLink(url.hash + suffix)).toBeNull();
    expect(parseLocalRunLink("#run=run_1&artifacts=2")).toBeNull();
  });

  it("rejects mixed runtime projections", () => {
    expect(runtimeProjectionsMatchRun("run_1", contract(), dag(), telemetry())).toBe(true);
    expect(runtimeProjectionsMatchRun("run_1", contract(), { ...dag(), mission_id: "other" }, telemetry())).toBe(false);
    expect(runtimeProjectionsMatchRun("run_1", contract(), dag(), { ...telemetry(), run_id: "run_2" })).toBe(false);
  });
});
