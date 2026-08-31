import { describe, expect, it } from "vitest";

import { demoBundle, type ImportedBundle } from "./model";
import { fleetOrchestration } from "./fleetOrchestration";

const at = (missionState: string): ImportedBundle => ({ ...demoBundle, status: { missionState, retryCount: 0, retryBudget: 0, returnReason: null } });

describe("fleet orchestration", () => {
  it("marks only registered stage participants active and shows the next fleet without claiming execution", () => {
    const entries = fleetOrchestration(at("RETRIEVE"));
    expect(entries.filter((entry) => entry.state === "active").map((entry) => entry.fleet.id)).toEqual(["observatory"]);
    expect(entries.filter((entry) => entry.state === "next").map((entry) => entry.fleet.id)).toEqual(["sentinel"]);
    expect(entries.find((entry) => entry.fleet.id === "dft")).toMatchObject({ state: "framework" });
  });

  it("keeps the local shell ready for pioneer and names observatory as the first downstream handoff", () => {
    const entries = fleetOrchestration(at("LOCAL"));
    expect(entries.find((entry) => entry.fleet.id === "pioneer")).toMatchObject({ state: "active" });
    expect(entries.find((entry) => entry.fleet.id === "observatory")).toMatchObject({ state: "next" });
  });

  it("shows concurrent extract work without making future fleets active", () => {
    const entries = fleetOrchestration(at("EXTRACT"));
    expect(entries.filter((entry) => entry.state === "active").map((entry) => entry.fleet.id)).toEqual(["observatory", "sentinel"]);
    expect(entries.find((entry) => entry.fleet.id === "constellation")).toMatchObject({ state: "next" });
    expect(entries.find((entry) => entry.fleet.id === "horizon")).toMatchObject({ state: "standby" });
  });
});
