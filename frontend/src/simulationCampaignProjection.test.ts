import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

const base = {
  schema_version: "1.0",
  mission: {
    mission_id: "campaign-demo", question: "Can a reviewed campaign remain plan only?",
    material: "BiFeO3", property_name: "phase stability", scope: "epitaxial films",
  },
};
const campaign = {
  delivery_status: "approved_plan_only", simulation_kind: "dft", evidence_count: 2,
  input_count: 3, execution_permitted: false, execution_state: "not_started",
};

describe("simulation campaign projection", () => {
  it("keeps a valid approved plan-only summary and no execution capability", () => {
    const bundle = readBundle({ ...base, simulation_campaign_delivery_status: "approved", simulation_campaign: campaign });
    expect(bundle.simulationCampaignStatus).toBe("approved");
    expect(bundle.simulationCampaign).toEqual({
      deliveryStatus: "approved_plan_only", simulationKind: "dft", evidenceCount: 2,
      inputCount: 3, executionPermitted: false, executionState: "not_started",
    });
  });

  it("rejects any malformed or execution-enabled campaign projection", () => {
    const malformed = readBundle({ ...base, simulation_campaign_delivery_status: "approved", simulation_campaign: { ...campaign, execution_permitted: true } });
    const missing = readBundle({ ...base, simulation_campaign_delivery_status: "approved" });
    expect(malformed.simulationCampaign).toBeNull();
    expect(malformed.simulationCampaignStatus).toBe("rejected");
    expect(missing.simulationCampaign).toBeNull();
    expect(missing.simulationCampaignStatus).toBe("rejected");
  });
});
