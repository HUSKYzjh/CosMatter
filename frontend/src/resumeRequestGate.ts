/** A locally-read run package may commit only to the task epoch that queued it. */
export function queuedResumeCanCommit(queuedTaskEpoch: number, currentTaskEpoch: number): boolean {
  return queuedTaskEpoch === currentTaskEpoch;
}
