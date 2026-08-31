import { describe, expect, it } from "vitest";

import { bfoTemplateDeployment } from "./bfoTemplateDeployment";
import { demoBundle, type ImportedBundle } from "./model";

const at = (missionState: string): ImportedBundle => ({ ...demoBundle, status: { missionState, retryCount: 0, retryBudget: 0, returnReason: null } });

describe("BFO template deployment", () => {
  it("keeps launch template stations distinct from the route state of the current mission", () => {
    const formation = bfoTemplateDeployment("bfo-phase-boundary", at("LOCAL"), "zh");
    expect(formation.find((entry) => entry.fleetId === "pioneer")?.routeState).toBe("active");
    expect(formation.find((entry) => entry.fleetId === "observatory")?.routeState).toBe("next");
    expect(formation.find((entry) => entry.fleetId === "sentinel")?.routeState).toBe("standby");
  });

  it("updates the template comparison from the imported mission state", () => {
    const formation = bfoTemplateDeployment("bfo-domain-coupling", at("EXTRACT"), "en");
    expect(formation.find((entry) => entry.fleetId === "observatory")?.routeState).toBe("active");
    expect(formation.find((entry) => entry.fleetId === "sentinel")?.routeState).toBe("active");
    expect(formation.find((entry) => entry.fleetId === "constellation")?.routeState).toBe("next");
  });
});
