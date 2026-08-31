import { describe, expect, it } from "vitest";

import { FLEETS } from "./fleetRegistry";
import { demoBundle, type ImportedBundle } from "./model";
import { FLEET_MISSION_ROUTE, fleetMissionRole, fleetParticipantsForMission, fleetRuntimeLabel, fleetRuntimeStatus } from "./fleetRuntimeState";
import { fleetOrchestration } from "./fleetOrchestration";

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

  it("uses one stage contract for the formation, current participants, and runtime labels", () => {
    for (const missionState of FLEET_MISSION_ROUTE) {
      const bundle: ImportedBundle = { ...demoBundle, status: { missionState, retryCount: 0, retryBudget: 0, returnReason: null } };
      const formation = fleetOrchestration(bundle).filter((entry) => entry.state === "active").map((entry) => entry.fleet.id);
      const participants = fleetParticipantsForMission(bundle).map((fleet) => fleet.id);
      expect(formation).toEqual(participants);
      for (const fleet of FLEETS) {
        const runtime = fleetRuntimeStatus(fleet, bundle);
        const stageAssigned = missionState !== "LOCAL" && participants.includes(fleet.id);
        expect(["active", "waiting_approval"].includes(runtime)).toBe(stageAssigned);
      }
    }
  });

  it("keeps an unknown imported state entirely non-executing", () => {
    const unknown: ImportedBundle = { ...demoBundle, status: { missionState: "FUTURE_STAGE", retryCount: 0, retryBudget: 0, returnReason: null } };
    expect(fleetParticipantsForMission(unknown)).toEqual([]);
    expect(fleetOrchestration(unknown).every((entry) => entry.state !== "active" && entry.state !== "next")).toBe(true);
    for (const fleet of FLEETS) expect(fleetRuntimeStatus(fleet, unknown)).not.toBe("active");
  });
});
