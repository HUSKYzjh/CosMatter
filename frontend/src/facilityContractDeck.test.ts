import { expect, it } from "vitest";

import { facilityContractCoverage, facilityContractDeck } from "./facilityContractDeck";
import type { FacilityContractManifest } from "./localApi";

const facilityTypes = [
  "sector_cartography", "timeline_observatory", "citation_array", "source_locator", "evidence_comparator",
  "condition_recorder", "trajectory_overlay", "condition_differential", "counterevidence_detector", "blind_spot_scan",
  "variable_combination_scan", "hypothesis_triage", "experiment_mission_design", "computation_mission_design", "falsification_monitor",
] as const;

const contract = (): FacilityContractManifest => ({
  facility_type: "condition_differential", fleet_types: ["route_diagnostics"], input_schema: ["accepted_evidence_cards", "counterevidence_record"], output_schema: ["condition_matrix"], allowed_descriptors: ["knowledge.fuse"], failure_modes: ["incomplete_conditions"], human_review_required: true,
  execution_boundary: "static_contract_only_not_execution_authorization",
});

it("joins only fixed static contracts to mission-assigned facilities", () => {
  expect(facilityContractDeck([{ facilityType: "condition_differential", status: "queued" }], [contract()])).toEqual([expect.objectContaining({ facilityType: "condition_differential", labelZh: "条件差分舱", labelEn: "Condition Differential", status: "queued", humanReviewRequired: true })]);
});

it("hides malformed contracts instead of treating them as an executable facility", () => {
  const invalid = contract();
  invalid.execution_boundary = "run_now" as "static_contract_only_not_execution_authorization";
  expect(facilityContractDeck([{ facilityType: "condition_differential", status: "queued" }], [invalid])).toEqual([]);
});

it("hides an unrecognised catalogue type instead of exposing a provider-defined label", () => {
  const unrecognised = { ...contract(), facility_type: "remote_execution_console" };
  expect(facilityContractDeck([{ facilityType: "remote_execution_console", status: "queued" }], [unrecognised])).toEqual([]);
});

it("keeps a human-readable bilingual label for every closed facility type", () => {
  const contracts = facilityTypes.map((facility_type) => ({ ...contract(), facility_type }));
  const deck = facilityContractDeck(facilityTypes.map((facilityType) => ({ facilityType, status: "ready" })), contracts);
  expect(deck).toHaveLength(facilityTypes.length);
  expect(deck.every((item) => item.labelZh.length > 0 && item.labelEn.length > 0)).toBe(true);
});

it("reports unmapped assigned facilities instead of hiding mixed catalogue state", () => {
  const facilities = [
    { facilityType: "condition_differential", status: "queued" },
    { facilityType: "remote_execution_console", status: "unknown" },
  ];
  const deck = facilityContractDeck(facilities, [contract(), { ...contract(), facility_type: "remote_execution_console" }]);
  expect(facilityContractCoverage(facilities, deck)).toEqual({ assignedCount: 2, mappedCount: 1, unmappedCount: 1, humanReviewCount: 1 });
});
