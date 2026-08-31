import type { RuntimeProjectionHealth } from "./runtimeProjection";

export const RUNTIME_PROJECTION_STALE_AFTER_MS = 25_000;

export type RuntimeProjectionFreshness = "disabled" | "pending" | "current" | "aging" | "unavailable";

export interface RuntimeProjectionSnapshotFreshness {
  state: RuntimeProjectionFreshness;
  observedAt: number | null;
  ageMs: number | null;
}

/**
 * A runtime snapshot is current only after all run-bound projections pass the
 * identity check together.  It becomes aging before a stalled poll could be
 * mistaken for a continuously live service connection.
 */
export function runtimeProjectionSnapshotFreshness(
  health: RuntimeProjectionHealth,
  observedAt: number | null,
  now = Date.now(),
): RuntimeProjectionSnapshotFreshness {
  if (health === "disabled") return { state: "disabled", observedAt: null, ageMs: null };
  if (health === "unavailable") return { state: "unavailable", observedAt: null, ageMs: null };
  if (health !== "ready" || observedAt === null) return { state: "pending", observedAt: null, ageMs: null };
  const ageMs = Math.max(0, now - observedAt);
  return { state: ageMs > RUNTIME_PROJECTION_STALE_AFTER_MS ? "aging" : "current", observedAt, ageMs };
}
