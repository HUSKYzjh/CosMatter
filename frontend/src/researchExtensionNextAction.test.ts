import { describe, expect, it } from "vitest";

import { researchExtensionNextAction } from "./researchExtensionNextAction";

const comparison = (ready: boolean, reason: "evidence" | "provenance-audit" | "documents" | "comparison" | "conditions" | null) => ({ ready, reason });
const counterevidence = (ready: boolean) => ({ ready });

describe("researchExtensionNextAction", () => {
  it("asks for comparison evidence before counterevidence execution when cross-paper evidence is missing", () => {
    expect(researchExtensionNextAction(comparison(false, "evidence"), counterevidence(false), 0)).toBe("comparison-evidence");
  });

  it("returns to evidence verification instead of the graph when exact provenance is missing", () => {
    expect(researchExtensionNextAction(comparison(false, "provenance-audit"), counterevidence(false), 0)).toBe("provenance-audit");
  });

  it("asks for approved counterevidence before a condition matrix once the evidence comparison is otherwise ready", () => {
    expect(researchExtensionNextAction(comparison(false, "conditions"), counterevidence(false), 0)).toBe("counterevidence");
  });

  it("builds a condition matrix before generating Gap candidates", () => {
    expect(researchExtensionNextAction(comparison(false, "conditions"), counterevidence(true), 0)).toBe("condition-matrix");
  });

  it("does not offer a new generator once review-required candidates already exist", () => {
    expect(researchExtensionNextAction(comparison(true, null), counterevidence(true), 2)).toBe("review-candidates");
  });
});