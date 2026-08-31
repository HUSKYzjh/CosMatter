import { describe, expect, it } from "vitest";

import { validateEvidenceDraft } from "./evidenceReviewDraft";

const base = () => ({
  candidateLinked: true,
  segmentId: "segment-1",
  segments: [{ segment_id: "segment-1", locator: "markdown_line:1-2", kind: "paragraph" as const }],
  claim: "The phase boundary shifts under the recorded condition.",
  conditionsText: JSON.stringify({ sample_form: "film", strain_percent: 1, substrate: "STO", thickness_nm: 20, temperature_k: 300, method: "XRD" }),
  confidenceText: "0.8",
  confirmed: true,
  hasRecordHandler: true,
});

describe("EvidenceCard form draft validation", () => {
  it("accepts only a complete local draft", () => {
    const result = validateEvidenceDraft(base());
    expect(result).toMatchObject({ ready: true, issue: null, confidence: 0.8 });
    expect(result.conditions?.method).toBe("XRD");
  });

  it("blocks incomplete conditions before a loopback request", () => {
    const input = base();
    input.conditionsText = JSON.stringify({ sample_form: "film", strain_percent: 1, substrate: "", thickness_nm: 20, temperature_k: 300, method: "XRD" });
    expect(validateEvidenceDraft(input).issue).toBe("conditions-required");
  });

  it("blocks malformed conditions, stale segments, and invalid confidence", () => {
    const malformed = base(); malformed.conditionsText = "not-json";
    expect(validateEvidenceDraft(malformed).issue).toBe("conditions-json");
    const stale = base(); stale.segmentId = "not-in-source-map";
    expect(validateEvidenceDraft(stale).issue).toBe("segment");
    const confidence = base(); confidence.confidenceText = "1.1";
    expect(validateEvidenceDraft(confidence).issue).toBe("confidence");
  });

  it("requires finite numeric conditions and non-negative physical dimensions", () => {
    const negativeThickness = base();
    negativeThickness.conditionsText = JSON.stringify({ sample_form: "film", strain_percent: -1, substrate: "STO", thickness_nm: -2, temperature_k: 300, method: "XRD" });
    expect(validateEvidenceDraft(negativeThickness).issue).toBe("conditions-range");

    const textualTemperature = base();
    textualTemperature.conditionsText = JSON.stringify({ sample_form: "film", strain_percent: 1, substrate: "STO", thickness_nm: 20, temperature_k: "room temperature", method: "XRD" });
    expect(validateEvidenceDraft(textualTemperature).issue).toBe("conditions-range");

    const numericSubstrate = base();
    numericSubstrate.conditionsText = JSON.stringify({ sample_form: "film", strain_percent: 1, substrate: 10, thickness_nm: 20, temperature_k: 300, method: "XRD" });
    expect(validateEvidenceDraft(numericSubstrate).issue).toBe("conditions-text");
  });
});
