import { describe, expect, it } from "vitest";

import { continuationStageLabel, localRunLanding, reconcileRestoredStage, viewForContinuationStage } from "./continuationStage";
import { readBundle } from "./model";
import { stageContractFixture } from "./stageContractFixture";

describe("viewForContinuationStage", () => {
  it("keeps plan and retrieval recovery on the controlled bridge", () => {
    expect(viewForContinuationStage("plan")).toBe("workflow");
    expect(viewForContinuationStage("retrieval")).toBe("workflow");
    expect(viewForContinuationStage(undefined)).toBe("workflow");
  });

  it("labels the audited stage for the active interface language", () => {
    expect(continuationStageLabel("screening", "zh")).toBe("候选筛选");
    expect(continuationStageLabel("screening", "en")).toBe("candidate screening");
  });

  it("routes a verified local task to its usable workspace", () => {
    const bundle = readBundle({
      schema_version: "1.0",
      mission: { mission_id: "mission_run", question: "How does strain affect BiFeO3?", material: "BiFeO3", property_name: "phase stability", scope: "thin films" },
      literature_graph: { trust_status: "human_reviewed_graph_projection", nodes: [
        { node_id: "paper:candidate", label: "Candidate to screen", kind: "candidate_paper", trust_status: "candidate_metadata_not_scientific_evidence" },
      ], edges: [] },
    }, "loopback");
    const screening = stageContractFixture("saved_run", bundle.mission.missionId, "screening");
    const graphless = { ...bundle, literatureGraph: { ...bundle.literatureGraph, nodes: [], edges: [] } };
    expect(localRunLanding("saved_run", bundle, screening)).toEqual({ view: "graph", state: "confirmed", stage: "screening" });
    expect(localRunLanding("saved_run", graphless, screening).state).toBe("graph_unavailable");
    expect(localRunLanding("saved_run", bundle, { ...screening, runtime_safety: "attention_required" }).view).toBe("workflow");
    expect(localRunLanding("saved_run", bundle, { ...screening, mission_id: "another_mission" }).state).toBe("unverified");
    expect(localRunLanding("saved_run", bundle, { ...screening, next_stage: "parse" }).view).toBe("workflow");
    const complete = stageContractFixture("saved_run", bundle.mission.missionId, null);
    expect(localRunLanding("saved_run", bundle, complete)).toEqual({ view: "graph", state: "confirmed", stage: null });
  });

  it("reopens downstream work at the map because paper selection is session-only", () => {
    for (const stage of ["screening", "parse", "extraction", "gap", "report", "evaluation"]) {
      expect(viewForContinuationStage(stage)).toBe("graph");
    }
  });

  it("uses a newly derived local stage over an older package snapshot", () => {
    expect(reconcileRestoredStage("screening", "plan", true)).toEqual({ stage: "plan", source: "local_contract", differsFromPackage: true });
    expect(reconcileRestoredStage("screening", undefined, false)).toEqual({ stage: "screening", source: "package_snapshot", differsFromPackage: false });
  });
});
