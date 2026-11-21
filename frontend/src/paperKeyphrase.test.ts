import { describe, expect, it } from "vitest";
import { paperKeyphrase } from "./paperKeyphrase";

describe("paper keyphrases", () => {
  it("finds named physical mechanisms and methods even when they occur late in a title", () => {
    const cases = [
      ["Origin of stationary domain wall enhanced ferroelectric susceptibility", "静止畴壁", "stationary domain wall"],
      ["Critical phenomena and polarization rotation in epitaxial thin films", "极化旋转", "polarization rotation"],
      ["Prediction of perovskite-related structures using density functional theory and Bayesian optimization", "贝叶斯优化", "Bayesian optimization"],
      ["Polar behavior in a magnetic perovskite via A-site disorder", "A 位无序", "A-site disorder"],
      ["Interface design beyond epitaxy: oxide heterostructures comprising symmetry‐forbidden interfaces", "对称性禁戒界面", "symmetry-forbidden interfaces"],
    ];
    for (const [title, chinese, english] of cases) {
      expect(paperKeyphrase(title)).toBe(chinese);
      expect(paperKeyphrase(title, "en")).toBe(english);
    }
  });

  it("retains qualifiers that distinguish superficially similar titles", () => {
    const related = ["Cation ordering in perovskites", "Partial cation ordering in solid solutions",
      "B-site cation ordering by STEM", "Orbital ordering of Co", "Cation ordering in complex oxides"];
    expect(related.map(title => paperKeyphrase(title))).toEqual([
      "阳离子有序", "部分阳离子有序", "B 位阳离子有序", "轨道有序", "复合氧化物阳离子有序",
    ]);
    expect(paperKeyphrase("Magnetic properties of a new perovskite")).not.toMatch(/磁有序|阳离子有序/u);
  });

  it("uses meaningful source words for Chinese and papers outside the glossary", () => {
    expect(paperKeyphrase("BiFeO₃ 薄膜中极化旋转的证据")).toBe("极化旋转");
    expect(paperKeyphrase("城市绿地中的鸟类迁徙研究")).toBe("鸟类迁徙");
    const longChinese = "青藏高原东部天然草原候鸟越冬栖息地植被生态环境变化趋势";
    const label = paperKeyphrase(longChinese);
    expect(label.length).toBeGreaterThan(1);
    expect(label.length).toBeLessThan(15);
    expect(longChinese).toContain(label);
    expect(paperKeyphrase("Mapping urban tree canopies using airborne lidar")).toBe("urban tree canopies");
    expect(paperKeyphrase("A review of memory consolidation during sleep")).toBe("memory consolidation");
    expect(paperKeyphrase("Thin film A")).toBe("Thin film A");
    expect(paperKeyphrase("BiFeO$_3$")).toBe("BiFeO₃");
  });

  it("does not turn bibliographic identifiers or boilerplate into a scientific subject", () => {
    for (const input of ["", "A study", "N/A", "题名未记录", "https://doi.org/10.1234/test", "arXiv:2603.01234", "paper:0c45", "123"]) {
      expect(paperKeyphrase(input)).toBe("");
    }
  });
});
