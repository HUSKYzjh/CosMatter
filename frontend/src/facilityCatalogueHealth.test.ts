import { expect, it } from "vitest";

import { isFacilityContractCatalogue } from "./localApi";

const manifest = (facilityType: string) => ({
  facility_type: facilityType,
  fleet_types: ["route_diagnostics"],
  input_schema: ["accepted_evidence_cards"],
  output_schema: ["condition_matrix"],
  allowed_descriptors: ["knowledge.fuse"],
  failure_modes: ["incomplete_conditions"],
  human_review_required: true,
  execution_boundary: "static_contract_only_not_execution_authorization" as const,
});

const catalogue = () => ({
  schema_version: "cosmatter.facility-contract-catalogue/v1" as const,
  trust_status: "static_facility_contracts_not_execution_or_evidence_acceptance" as const,
  contracts: Array.from({ length: 15 }, (_, index) => manifest(`facility_${index}`)),
});

it("accepts only a complete static facility catalogue", () => {
  expect(isFacilityContractCatalogue(catalogue())).toBe(true);
  expect(isFacilityContractCatalogue({ ...catalogue(), contracts: catalogue().contracts.slice(0, 14) })).toBe(false);
});

it("rejects an execution-looking boundary or duplicate facility type", () => {
  const executionBoundary = catalogue();
  executionBoundary.contracts[0].execution_boundary = "run_now" as "static_contract_only_not_execution_authorization";
  expect(isFacilityContractCatalogue(executionBoundary)).toBe(false);
  const duplicate = catalogue();
  duplicate.contracts[14].facility_type = duplicate.contracts[0].facility_type;
  expect(isFacilityContractCatalogue(duplicate)).toBe(false);
});
