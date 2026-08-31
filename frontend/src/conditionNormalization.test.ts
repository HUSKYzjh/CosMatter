import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

const base = { schema_version: "1.0", mission: { mission_id: "m1", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" }, stations: [], facilities: [], evidence_cards: [], condition_matrix: [], research_gap_candidates: [], literature_graph: null };

describe("condition normalization import", () => {
  it("retains only explicit human-reviewed field mappings without values", () => {
    const bundle = readBundle({ ...base, condition_normalization: { trust_status: "human_reviewed_condition_normalization_no_conversion", mappings: [{ evidence_id: "e1", raw_field: "thickness_nm", canonical_field: "thickness", unit: "nm" }] } });
    expect(bundle.conditionNormalization?.mappings).toEqual([{ evidenceId: "e1", rawField: "thickness_nm", canonicalField: "thickness", unit: "nm" }]);
  });

  it("rejects an extra field instead of treating a conversion as safe", () => {
    const bundle = readBundle({ ...base, condition_normalization: { trust_status: "human_reviewed_condition_normalization_no_conversion", mappings: [{ evidence_id: "e1", raw_field: "thickness_nm", canonical_field: "thickness", unit: "nm", converted_value: 0.03 }] } });
    expect(bundle.conditionNormalization).toBeNull();
  });
});
