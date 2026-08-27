import { describe, expect, it } from "vitest";

import { preferredConditionCluster } from "./conditionClusterSelection";

describe("preferredConditionCluster", () => {
  const rows = [
    { conditionCluster: "strain matched", supportingEvidenceIds: ["evidence-a"], contradictingEvidenceIds: [], differingFields: [], unknowns: [] },
    { conditionCluster: "oxygen boundary", supportingEvidenceIds: [], contradictingEvidenceIds: ["evidence-b"], differingFields: [], unknowns: [] },
  ];
  it("opens the cluster that contains the current evidence rather than the first row", () => {
    expect(preferredConditionCluster(rows, "evidence-b")).toBe("oxygen boundary");
  });
  it("falls back to the first cluster when the current evidence is not in the matrix", () => {
    expect(preferredConditionCluster(rows, "unmapped")).toBe("strain matched");
  });
});
