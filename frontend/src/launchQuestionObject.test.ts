import { describe, expect, it } from "vitest";

import { researchObjectFromQuestion } from "./launchQuestionObject";

describe("question research-object convenience", () => {
  it("recognises the explicit BiFeO3 spelling without inferring a scientific property", () => {
    expect(researchObjectFromQuestion("BiFeO3 的磁转变温度和居里温度分别是什么？")).toBe("BiFeO₃");
    expect(researchObjectFromQuestion("What changes its magnetic transition temperature?")).toBeNull();
  });

  it("retains explicit formulas and bounded Chinese material phrases", () => {
    expect(researchObjectFromQuestion("What is the band gap of MoS2?")).toBe("MoS2");
    expect(researchObjectFromQuestion("如何比较钠离子层状正极在高电压下的循环稳定性？")).toBe("钠离子层状正极");
  });

  it.each<[string, string | null]>([
    ["MoS₂的带隙是多少？", "MoS₂"],
    ["What is the band gap of La0.7Sr0.3MnO3?", "La0.7Sr0.3MnO3"],
    ["How does strain affect the band gap of MoS_{2}?", "MoS_{2}"],
    ["比较 (Pb_x Sr_{1-x})TiO_3 与 BaTiO₃ 的介电常数", "(Pb_x Sr_{1-x})TiO_3 与 BaTiO₃"],
    ["Compare BaTiO₃, SrTiO₃ and BiFeO₃ transition temperatures.", "BaTiO₃, SrTiO₃ and BiFeO₃"],
    ["Compare the band gap of MoS₂ with that of WS₂.", "MoS₂ vs. WS₂"],
    ["BiFeO3 薄膜生长在 SrTiO₃ 衬底时，剩余极化如何变化？", "BiFeO₃"],
    ["How do SrTiO₃ films grown on BiFeO₃ respond to strain?", "SrTiO₃"],
    ["Does the identifier sampleBiFeO3x affect the response?", null],
  ])("preserves the material expressed in %s", (question, material) => {
    expect(researchObjectFromQuestion(question)).toBe(material);
  });
});
