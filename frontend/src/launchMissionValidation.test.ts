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

  it.each([
    ["测量频率未指定的样品有何差异？", "分别比较已标注样品和测量频率未指定的样品"],
    ["Which sample temperatures were not specified?", "Compare measured phases with those still to be confirmed."],
  ])("accepts a scientific question and scope that describe missing metadata", (question, scope) => {
    expect(launchMissionMissingFields({ question, scope, material: "BiFeO₃", property: "介电响应" })).toEqual([]);
  });

  it.each([
    ["输入中的研究对象，待人工确认", "输入中的研究对象，待人工确认 的介电响应采用了哪些方法？"],
    ["Research object in the prompt; confirm manually", "Which values are reported for Research object in the prompt; confirm manually?"],
  ])("requires the generated material label to be replaced in both editable fields", (material, question) => {
    const draft = { question, material, scope: "films", property: "dielectric response" };
    expect(launchMissionMissingFields(draft)).toEqual(["question", "material"]);
    expect(launchMissionMissingFields({ ...draft, material: "BiFeO₃" })).toEqual(["question"]);
  });
});
