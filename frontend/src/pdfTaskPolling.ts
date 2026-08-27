import type { PdfTaskStatus } from "./localApi";

/** Poll only an in-progress private PDF task. Terminal records remain static. */
export function shouldPollPdfTask(runId: string | null, task: PdfTaskStatus | null): boolean {
  if (!runId || !task) return false;
  return !["done", "failed", "cancelled"].includes(task.state);
}