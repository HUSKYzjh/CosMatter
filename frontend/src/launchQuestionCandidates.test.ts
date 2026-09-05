import { describe, expect, it } from "vitest";

import { questionBoundFallbackCandidates } from "./launchQuestionCandidates";

describe("question-bound local candidate routes", () => {
  it("keeps the named BiFeO3 phase-transition question and focus in every route", () => {
    const input = "BiFeO3的相转变温度是多少？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes).toHaveLength(3);
    expect(routes.map((route) => route.material)).toEqual(["BiFeO₃", "BiFeO₃", "BiFeO₃"]);
    expect(routes.map((route) => route.property)).toEqual(["相转变温度", "相转变温度", "相转变温度"]);
    expect(routes.every((route) => route.question.includes("BiFeO₃"))).toBe(true);
    expect(routes.every((route) => route.question.includes("相转变温度"))).toBe(true);
    expect(routes[0].question).toContain("转变温区");
    expect(routes[0].question).toContain("相结构指派");
    expect(routes[1].question).toContain("体相、陶瓷与薄膜");
    expect(routes[2].question).toContain("材料分解与测量伪影");
    expect(routes.map((route) => route.question)).not.toContain(input);
    expect(routes[0].scope).toContain(input);
  });

  it("keeps a non-recognised question visible instead of replacing it with a generic route", () => {
    const input = "如何比较钠离子层状正极在高电压下的循环稳定性？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes[0].question).not.toBe(input);
    expect(routes.every((route) => route.scope.includes(input))).toBe(true);
    expect(routes.every((route) => route.material === "钠离子层状正极")).toBe(true);
    expect(routes.every((route) => route.property === "循环稳定性")).toBe(true);
    expect(routes[0].question).toContain("保持率定义");
    expect(routes[1].question).toContain("载量");
    expect(routes[2].question).toContain("循环后结构、化学与电化学观测");
    expect(routes[2].question).not.toContain("相结构指派");
  });

  it("uses electronic-property checks for an English formula question", () => {
    const input = "What is the band gap of MoS2?";
    const routes = questionBoundFallbackCandidates(input, "en");
    expect(routes.map((route) => route.material)).toEqual(["MoS2", "MoS2", "MoS2"]);
    expect(routes.map((route) => route.property)).toEqual(["band gap", "band gap", "band gap"]);
    expect(routes[0].question).toContain("experimental and computational values");
    expect(routes[2].question).toContain("primary spectra or response curves");
    expect(routes[2].question).not.toContain("transition ranges");
  });

  it("uses synthesis checks only for a synthesis question", () => {
    const input = "SrTiO3薄膜的沉积温度如何影响物相纯度？";
    const routes = questionBoundFallbackCandidates(input, "zh");
    expect(routes.every((route) => route.material === "SrTiO3")).toBe(true);
    expect(routes.every((route) => route.property === "制备条件与产物")).toBe(true);
    expect(routes[0].question).toContain("前驱体");
    expect(routes[2].question).toContain("受控工艺对比");
    expect(routes[2].question).not.toContain("循环后结构");
  });

  it("never returns the three generic workflow prompts reported by the launch UI", () => {
    const routes = questionBoundFallbackCandidates("BiFeO3的相转变温度是", "zh");
    const visible = routes.map((route) => route.question).join(" ");
    expect(visible).not.toContain("围绕该研究议题");
    expect(visible).not.toContain("哪些可比较的制备、几何、环境与测量条件");
    expect(visible).not.toContain("需要优先核对哪些可定位的原文证据");
  });

  it("keeps an unresolved research object visibly gated instead of creating a launchable generic mission", () => {
    const routes = questionBoundFallbackCandidates("围绕该研究议题，现有报告的结论与证据边界是什么？", "zh");
    expect(routes.every((route) => route.material.includes("待人工确认"))).toBe(true);
    expect(routes.every((route) => route.question.includes("待人工确认"))).toBe(true);
  });
});
