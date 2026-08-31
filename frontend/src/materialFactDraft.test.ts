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
});
