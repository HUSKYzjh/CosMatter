import { describe, expect, it } from "vitest";

import { researchObjectFromQuestion } from "./launchQuestionObject";

describe("question research-object convenience", () => {
  it("recognises the explicit BiFeO3 spelling without inferring a scientific property", () => {
    expect(researchObjectFromQuestion("BiFeO3 的磁转变温度和居里温度分别是什么？")).toBe("BiFeO₃");
    expect(researchObjectFromQuestion("What changes its magnetic transition temperature?")).toBeNull();
  });
});
