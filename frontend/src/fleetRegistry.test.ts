import { describe, expect, it } from "vitest";

import { FLEETS, fleetChannels } from "./fleetRegistry";

describe("fleet registry", () => {
  it("registers ten specialised fleets with flagship-mediated channels", () => {
    expect(FLEETS).toHaveLength(10);
    expect(new Set(FLEETS.map((fleet) => fleet.id)).size).toBe(FLEETS.length);
    for (const fleet of FLEETS) {
      expect(fleet.ships.some((ship) => ship.id === fleet.flagshipId)).toBe(true);
      expect(fleetChannels(fleet).every((channel) => channel.from === fleet.flagshipId || channel.to === fleet.flagshipId)).toBe(true);
    }
  });

  it("makes future DFT, DP and MD fleets explicitly framework-only", () => {
    for (const id of ["dft", "potential", "dynamics"]) {
      const fleet = FLEETS.find((item) => item.id === id);
      expect(fleet?.status).toBe("framework_only");
      expect(fleet?.ships.flatMap((ship) => ship.tools).every((tool) => tool.status === "framework_only")).toBe(true);
    }
  });

  it("keeps tool and shuttle catalogues substantial and traceable", () => {
    expect(FLEETS.flatMap((fleet) => fleet.ships).flatMap((ship) => ship.tools)).toHaveLength(44);
    expect(FLEETS.flatMap((fleet) => fleet.ships).flatMap((ship) => ship.shuttles ?? [])).toHaveLength(7);
  });
});
