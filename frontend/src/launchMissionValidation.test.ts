import { describe, expect, it } from "vitest";

import { isLaunchMissionReady, launchMissionMissingFields } from "./launchMissionValidation";

describe("launch mission validation", () => {
  it("accepts an explicit multi-material research boundary", () => {
    const mission = { question: "How do strain and defects affect phase stability?", material: "BiFeO3; BaTiO3", property: "phase stability", scope: "epitaxial films under reported strain and defect conditions" };
    expect(isLaunchMissionReady(mission)).toBe(true);
  });

  it("rejects visible candidate placeholders before automatic retrieval", () => {
    const mission = { question: "Which conditions explain divergent reports?", material: "由输入问题识别，待人工确认", property: "Research background", scope: "Use the prompt as retrieval intent" };
    expect(launchMissionMissingFields(mission)).toEqual(["material"]);
    expect(isLaunchMissionReady(mission)).toBe(false);
  });

  it("rejects incomplete source-location placeholders", () => {
    const mission = { question: "What evidence distinguishes competing mechanisms?", material: "Normalize after source location", property: "mechanism", scope: "films" };
    expect(launchMissionMissingFields(mission)).toEqual(["material"]);
  });
});
