/** A launch preview may render local artifacts but must never receive run actions. */
export function previewAllowsRunAction(readOnlyPreview: boolean, runId: string | null | undefined): boolean {
  return !readOnlyPreview && Boolean(runId);
}
