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
  input_count: 3, execution_permitted: false, execution_state: "blocked_plan_only",
  chain: { evidence: "bound", hypothesis: "approved", protocol: "approved", execution: "blocked" },
  missing_fields: [], budget: { max_jobs: 0, max_gpu_jobs: 0, max_dft_jobs: 0 },
  continuation_reason: "execution profile is intentionally disabled",
};

describe("simulation campaign projection", () => {
  it("keeps a valid approved plan-only summary and no execution capability", () => {
    const bundle = readBundle({ ...base, simulation_campaign_delivery_status: "approved", simulation_campaign: campaign });
    expect(bundle.simulationCampaignStatus).toBe("approved");
    expect(bundle.simulationCampaign).toEqual({
      deliveryStatus: "approved_plan_only", simulationKind: "dft", evidenceCount: 2,
      inputCount: 3, executionPermitted: false, executionState: "blocked_plan_only",
      chain: { evidence: "bound", hypothesis: "approved", protocol: "approved", execution: "blocked" },
      missingFields: [], budget: { maxJobs: 0, maxGpuJobs: 0, maxDftJobs: 0 },
      continuationReason: "execution profile is intentionally disabled",
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
