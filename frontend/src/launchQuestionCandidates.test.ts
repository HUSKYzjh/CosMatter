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
    expect(routes.every((route) => route.material === "钠离子层状正极")).toBe(true);
    expect(routes.every((route) => route.property === "循环稳定性")).toBe(true);
    expect(routes[2].question).toContain("电极组成与载量");
    expect(routes[2].question).not.toContain("相变指派");
  });

  it("uses electronic-property checks for an English formula question", () => {
    const input = "What is the band gap of MoS2?";
    const routes = questionBoundFallbackCandidates(input, "en");
    expect(routes.map((route) => route.material)).toEqual(["MoS2", "MoS2", "MoS2"]);
    expect(routes.map((route) => route.property)).toEqual(["band gap", "band gap", "band gap"]);
    expect(routes[2].question).toContain("primary spectrum or response curve");
    expect(routes[2].question).not.toContain("transition assignments");
  });

  it("uses synthesis checks only for a synthesis question", () => {
    const input = "SrTiO3薄膜的沉积温度如何影响物相纯度？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes.every((route) => route.material === "SrTiO3")).toBe(true);
    expect(routes.every((route) => route.property === "制备条件与产物")).toBe(true);
    expect(routes[2].question).toContain("前驱体");
    expect(routes[2].question).not.toContain("电极组成与载量");
  });
});
