import { describe, expect, it } from "vitest";

import { questionBoundFallbackCandidates } from "./launchQuestionCandidates";
import { isLaunchMissionReady } from "./launchMissionValidation";

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

  it("keeps every requested BFO temperature in the editable target and standalone query", () => {
    const original = "BiFeO3的磁转变温度，电转变温度，居里温度，相变温度是？";
    for (const route of questionBoundFallbackCandidates(original, "zh")) {
      for (const target of ["磁转变温度", "电转变温度", "居里温度", "相变温度"]) {
        expect(route.question).toContain(target);
        expect(route.property).toContain(target);
      }
      expect(route.material).toBe("BiFeO₃");
      expect(route.scope).toContain(original);
      expect(isLaunchMissionReady(route)).toBe(true);
    }
  });

  it.each(["8×8×8", "8\\times8\\times8", "8 \\times 8 \\times 8"])("keeps the mixed formula and all occupancy-search constraints for a %s supercell", (dimensions) => {
    const original = "给定分子动力学势场，可描述 (Pb_x Sr_{1-x})TiO_3 钙钛矿固溶体任意组分。对固定组分 x，在 " + dimensions + " 超胞中，A位由 Pb/Sr 随机占据。问：能否设计算法，对于一个给定的组分，在海量构型空间中搜索最优的 Pb/Sr 排列，使体系性质（介电、压电）最优？约束：介电/压电数据只能由分子动力学模拟获得，不存在性质预测的代理模型。";
    for (const route of questionBoundFallbackCandidates(original, "zh")) {
      expect(route.material).toBe("(Pb_x Sr_{1-x})TiO_3");
      expect(route.property).toBe("介电、压电");
      for (const term of [route.material, "构型优化", "介电", "压电", "固定组分 x", "8×8×8", "A 位", "Pb/Sr", "随机占位", "势场", "性质仅由分子动力学模拟获得", "无性质预测代理模型"]) {
        expect(route.question).toContain(term);
      }
      expect(route.scope).toContain(original);
      expect(isLaunchMissionReady(route)).toBe(true);
    }
  });

  it("only carries the constraints stated for a different configuration search", () => {
    const original = "How can a fixed composition (BaₓSr₁₋ₓ)TiO₃ configuration search optimize dielectric response in a 4x4x4 supercell?";
    for (const route of questionBoundFallbackCandidates(original, "en")) {
      expect(route.question).toContain("(BaₓSr₁₋ₓ)TiO₃");
      expect(route.question).toContain("4x4x4");
      expect(route.question).not.toMatch(/surrogate|8×8×8|molecular dynamics|Pb\/Sr/i);
    }
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
