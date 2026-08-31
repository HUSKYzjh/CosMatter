import { describe, expect, it } from "vitest";

import { RUNTIME_PROJECTION_STALE_AFTER_MS, runtimeProjectionSnapshotFreshness } from "./runtimeProjectionFreshness";

describe("runtime projection freshness", () => {
  it("calls a complete, identity-checked local read current only inside the freshness window", () => {
    expect(runtimeProjectionSnapshotFreshness("ready", 1_000, 1_000)).toMatchObject({ state: "current", observedAt: 1_000, ageMs: 0 });
    expect(runtimeProjectionSnapshotFreshness("ready", 1_000, 1_000 + RUNTIME_PROJECTION_STALE_AFTER_MS)).toMatchObject({ state: "current" });
    expect(runtimeProjectionSnapshotFreshness("ready", 1_000, 1_001 + RUNTIME_PROJECTION_STALE_AFTER_MS)).toMatchObject({ state: "aging" });
  });

  it("never displays retained timestamps for a failed, pending, or disabled read", () => {
    expect(runtimeProjectionSnapshotFreshness("unavailable", 1_000, 2_000)).toEqual({ state: "unavailable", observedAt: null, ageMs: null });
    expect(runtimeProjectionSnapshotFreshness("loading", 1_000, 2_000)).toEqual({ state: "pending", observedAt: null, ageMs: null });
    expect(runtimeProjectionSnapshotFreshness("disabled", 1_000, 2_000)).toEqual({ state: "disabled", observedAt: null, ageMs: null });
  });
});
