import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

describe("readBundle", () => {
  it("reads the complete safe UI projection", () => {
    const bundle = readBundle({ schema_version: "1.0", mission: { mission_id: "mission_1", question: "question", material: "BiFeO3", property_name: "phase", scope: "films" }, fleet_assignment: { display_name_en: "Route Diagnostics Fleet", mission_type: "literature_discrepancy", release_gate: "review" }, status: { mission_state: "REVIEW", retry_count: 1, retry_budget: 2, return_reason: null }, stations: [{ station_type: "question_intake", status: "done" }], facilities: [{ facility_type: "condition_differential", status: "queued" }], evidence_cards: [{ evidence_id: "evidence_1", claim: "A bounded claim", stance: "support", conditions: { strain: 1 }, quote: "Short quote", review_status: "accepted", provenance: { document_id: "doc_1", locator: "p.1", source: "fixture", access_policy: "authorized" } }, { evidence_id: "rejected", claim: "Hidden", quote: "Hidden", review_status: "rejected", provenance: {} }], condition_matrix: [{ condition_cluster: "film", supporting_evidence_ids: ["evidence_1"], contradicting_evidence_ids: [], differing_fields: ["strain"], unknowns: ["thickness"] }], timeline: [{ station_type: "review", action: "Reviewed", state: "REVIEW", occurred_at: "2026-01-01" }], literature_relations: { trust_status: "metadata", edges: [{ target: "work" }] }, mission_report: { summary: "Approved", limitations: ["limited"], next_steps: ["extend"] } });
    expect(bundle.evidenceCards).toHaveLength(1);
    expect(bundle.evidenceCards[0].evidenceId).toBe("evidence_1");
    expect(bundle.conditionMatrix[0].unknowns).toEqual(["thickness"]);
    expect(bundle.literatureRelations?.edgeCount).toBe(1);
    expect(bundle.report?.summary).toBe("Approved");
  });

  it("requires a complete mission boundary", () => {
    expect(() => readBundle({ mission: { mission_id: "m", question: "q" } })).toThrow("mission.material");
  });
});