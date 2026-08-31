import { describe, expect, it } from "vitest";

import { bfoTaskFormation } from "./bfoTaskFormation";
import { bfoTaskPresets } from "./bfoTaskPresets";

describe("BFO task formation", () => {
  it("assigns every BFO local brief a complete bounded research formation", () => {
    const requiredFleetIds = ["pioneer", "observatory", "sentinel", "constellation", "diagnostics", "horizon"];
    for (const preset of bfoTaskPresets("zh")) {
      const formation = bfoTaskFormation(preset.id, "zh");
      expect(formation).toHaveLength(6);
      expect(formation[0].fleetId).toBe("pioneer");
      expect(formation.map((station) => station.fleetId)).toEqual(expect.arrayContaining(requiredFleetIds));
      expect(formation.every((station) => station.intake && station.artifact && station.acceptanceGate)).toBe(true);
    }
  });

  it("returns no fictitious formation for an unknown task", () => {
    expect(bfoTaskFormation("unknown", "en")).toEqual([]);
  });
});
