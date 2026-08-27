import { describe, expect, it } from "vitest";

import { emptyBundleForMission } from "./missionBundleFactory";
import { reviewablePaperCount } from "./evidenceLinking";

describe("emptyBundleForMission", () => {
  it("never carries demo literature, evidence, or Gap artifacts into a newly confirmed task", () => {
    const bundle = emptyBundleForMission({ missionId: "local_1", question: "A new question", material: "Material A", property: "Property B", scope: "Scope C" });
    expect(bundle.literatureGraph.nodes).toHaveLength(1);
    expect(reviewablePaperCount(bundle)).toBe(0);
    expect(bundle.evidenceCards).toEqual([]);
    expect(bundle.researchGapCandidates).toEqual([]);
    expect(bundle.sourceMapSummary.segmentCount).toBe(0);
  });
});
