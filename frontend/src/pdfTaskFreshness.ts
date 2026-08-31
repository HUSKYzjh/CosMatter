import type { PdfTaskStatus } from "./localApi";

export const PDF_TASK_STALE_AFTER_MS = 15_000;
export type PdfTaskReadHealth = "disabled" | "loading" | "ready" | "unavailable";
export type PdfTaskFreshnessState = "absent" | "pending" | "current" | "aging" | "unavailable";

export interface PdfTaskSnapshotFreshness {
  state: PdfTaskFreshnessState;
  observedAt: number | null;
  ageMs: number | null;
}

/**
 * Retain the last registered PDF task on a transient read failure, but label
 * it unavailable rather than presenting it as a live MinerU status.
 */
export function pdfTaskSnapshotFreshness(
  task: PdfTaskStatus | null,
  health: PdfTaskReadHealth,
  observedAt: number | null,
  now = Date.now(),
): PdfTaskSnapshotFreshness {
  if (!task) return { state: "absent", observedAt: null, ageMs: null };
  if (health === "unavailable") return { state: "unavailable", observedAt, ageMs: observedAt === null ? null : Math.max(0, now - observedAt) };
  if (health !== "ready" || observedAt === null) return { state: "pending", observedAt: null, ageMs: null };
  const ageMs = Math.max(0, now - observedAt);
  return { state: ageMs > PDF_TASK_STALE_AFTER_MS ? "aging" : "current", observedAt, ageMs };
}
