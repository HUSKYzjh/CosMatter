import { describe, expect, it } from "vitest";

import { FLEETS } from "./fleetRegistry";
import { demoBundle, type ImportedBundle } from "./model";
import { fleetMissionRole, fleetParticipantsForMission, fleetRuntimeLabel, fleetRuntimeStatus } from "./fleetRuntimeState";

describe("fleet runtime state", () => {
  it("treats a local mission shell as ready, never actively executing", () => {
    const pioneer = FLEETS.find((fleet) => fleet.id === "pioneer")!;
    const local: ImportedBundle = { ...demoBundle, status: { missionState: "LOCAL", retryCount: 0, retryBudget: 0, returnReason: null } };
    expect(fleetRuntimeStatus(pioneer, local)).toBe("ready");
    expect(fleetParticipantsForMission(local).map((fleet) => fleet.id)).toEqual(["pioneer"]);
  });

  it("explains the active handoff and keeps unrelated fleets catalogue-only", () => {
    const retrieving: ImportedBundle = { ...demoBundle, status: { missionState: "RETRIEVE", retryCount: 0, retryBudget: 0, returnReason: null } };
    const observatory = FLEETS.find((fleet) => fleet.id === "observatory")!;
    const pioneer = FLEETS.find((fleet) => fleet.id === "pioneer")!;
    expect(fleetMissionRole(observatory, retrieving)).toMatchObject({ participates: true, handoffEn: "Candidate literature list" });
    expect(fleetMissionRole(pioneer, retrieving)).toMatchObject({ participates: false, handoffEn: "No current handoff artifact" });
  });

  it("shows only stage-relevant participants and marks the retrieval fleet as stage-assigned", () => {
    const retrieving: ImportedBundle = { ...demoBundle, status: { missionState: "RETRIEVE", retryCount: 0, retryBudget: 0, returnReason: null } };
    const observatory = FLEETS.find((fleet) => fleet.id === "observatory")!;
    expect(fleetRuntimeStatus(observatory, retrieving)).toBe("active");
    expect(fleetParticipantsForMission(retrieving).map((fleet) => fleet.id)).toEqual(["observatory"]);
  });

  it("labels stage assignment without claiming that an external tool is executing", () => {
    expect(fleetRuntimeLabel("active", "zh")).toBe("当前编排");
    expect(fleetRuntimeLabel("active", "en")).toBe("In current stage");
  });
});
