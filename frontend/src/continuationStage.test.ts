import { describe, expect, it } from "vitest";

import { continuationStageLabel, viewForContinuationStage, viewForRestoredRun } from "./continuationStage";

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

  it("keeps a failed artifact hydration on the controlled bridge", () => {
    expect(viewForRestoredRun("screening", false)).toBe("workflow");
    expect(viewForRestoredRun("screening", true)).toBe("graph");
  });

  it("reopens downstream work at the map because paper selection is session-only", () => {
    for (const stage of ["screening", "parse", "extraction", "gap", "report", "evaluation"]) {
      expect(viewForContinuationStage(stage)).toBe("graph");
    }
  });
});
