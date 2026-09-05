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
});
