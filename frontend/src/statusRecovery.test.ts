import { describe, expect, it } from "vitest";

import { ordinaryStatus, recoverableStatus } from "./statusRecovery";

describe("status recovery pairing", () => {
  it("clears a stale recovery route whenever a newer ordinary status arrives", () => {
    const unknownOutcome = recoverableStatus("Outcome unknown", { view: "workflow" });
    expect(unknownOutcome.recovery).toEqual({ view: "workflow" });

    expect(ordinaryStatus<typeof unknownOutcome.recovery>("Local state refreshed")).toEqual({
      message: "Local state refreshed",
      recovery: null,
    });
  });

  it("keeps the recovery route paired to an unknown outcome", () => {
    expect(recoverableStatus("Outcome unknown", { view: "graph" })).toEqual({
      message: "Outcome unknown",
      recovery: { view: "graph" },
    });
  });
});
