import { describe, expect, it } from "vitest";

import { questionBoundFallbackCandidates } from "./launchQuestionCandidates";

describe("question-bound local candidate routes", () => {
  it("keeps the named BiFeO3 phase-transition question and focus in every route", () => {
    const input = "BiFeO3的相转变温度是多少？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes).toHaveLength(3);
    expect(routes.map((route) => route.material)).toEqual(["BiFeO₃", "BiFeO₃", "BiFeO₃"]);
    expect(routes.map((route) => route.property)).toEqual(["相转变温度", "相转变温度", "相转变温度"]);
    expect(routes[0].question).toBe(input);
    expect(routes[1].question).toContain("相转变温度");
    expect(routes[2].question).toContain("相转变温度");
    expect(routes[0].scope).toContain(input);
  });

  it("keeps a non-recognised question visible instead of replacing it with a generic route", () => {
    const input = "如何比较钠离子层状正极在高电压下的循环稳定性？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes[0].question).toBe(input);
    expect(routes.every((route) => route.scope.includes(input))).toBe(true);
    expect(routes.every((route) => route.property !== "研究背景与证据全景")).toBe(true);
  });
});
