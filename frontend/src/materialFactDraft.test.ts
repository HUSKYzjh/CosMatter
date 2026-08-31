import { describe, expect, it } from "vitest";

import { validateMaterialFactDraft } from "./materialFactDraft";

const valid = () => ({
  facts: [{ factId: "phase_boundary", segmentId: "seg_01", category: "property", name: "Phase boundary", value: "2.1", unit: "%", normalizedValue: "2.1", normalizedUnit: "%", qualifiersJson: '{"temperature_k":300}' }],
  segmentIds: ["seg_01"], confirmed: true, hasRecordHandler: true,
});

describe("validateMaterialFactDraft", () => {
  it("accepts a bounded fact attached to a reviewed source segment", () => {
    expect(validateMaterialFactDraft(valid())).toEqual({ ready: true, issue: null });
  });

  it("rejects repeated fact IDs after trimming", () => {
    const input = valid();
    input.facts.push({ ...input.facts[0], factId: " phase_boundary " });
    expect(validateMaterialFactDraft(input).issue).toBe("duplicate-id");
  });

  it("rejects unknown segments and oversized fields before a write", () => {
    const unknownSegment = valid();
    unknownSegment.facts[0].segmentId = "missing";
    expect(validateMaterialFactDraft(unknownSegment).issue).toBe("segment");
    const oversized = valid();
    oversized.facts[0].unit = "u".repeat(81);
    expect(validateMaterialFactDraft(oversized).issue).toBe("unit");
  });

  it("rejects non-scalar or invalid qualifier values", () => {
    const nested = valid();
    nested.facts[0].qualifiersJson = '{"temperature":{"value":300}}';
    expect(validateMaterialFactDraft(nested).issue).toBe("qualifiers");
    const blank = valid();
    blank.facts[0].qualifiersJson = '{"substrate":" "}';
    expect(validateMaterialFactDraft(blank).issue).toBe("qualifiers");
  });

  it("preflights only provably inconsistent known numeric conversions", () => {
    const converted = valid();
    converted.facts[0] = { ...converted.facts[0], value: "1000", unit: "nm", normalizedValue: "1", normalizedUnit: "μm" };
    expect(validateMaterialFactDraft(converted)).toEqual({ ready: true, issue: null });

    const inconsistent = valid();
    inconsistent.facts[0] = { ...inconsistent.facts[0], value: "1000", unit: "nm", normalizedValue: "2", normalizedUnit: "um" };
    expect(validateMaterialFactDraft(inconsistent)).toEqual({ ready: false, issue: "conversion" });

    const unknown = valid();
    unknown.facts[0] = { ...unknown.facts[0], value: "about one", unit: "arb.", normalizedValue: "about one", normalizedUnit: "arb." };
    expect(validateMaterialFactDraft(unknown)).toEqual({ ready: true, issue: null });
  });
});
