export type AutomaticCancellationState = "queued" | "running" | "succeeded" | "failed" | "cancelled";

/** A cancellation control is only valid for a live, non-terminal automatic run. */
export function automaticCancellationEnabled(
  readOnlyPreview: boolean,
  runId: string | null,
  state: AutomaticCancellationState | null | undefined,
  cancellationRequested: boolean,
): boolean {
  return !readOnlyPreview
    && Boolean(runId)
    && !cancellationRequested
    && (state === "queued" || state === "running");
}
