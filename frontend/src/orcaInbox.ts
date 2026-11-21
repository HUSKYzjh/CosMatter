import { localPaperMapLink } from "./liveRunIdentity";

export interface OrcaPaperReceipt {
  message: string;
  run: string;
  task: string;
  dispatch: string;
  worker: string;
  document: string;
  outcome: "succeeded" | "failed";
}

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function jsonField(value: unknown) {
  if (typeof value !== "string") return object(value);
  try { return object(JSON.parse(value)); } catch { return null; }
}

function identifier(value: unknown, prefix: string): value is string {
  return typeof value === "string" && value.startsWith(prefix) && /^[a-zA-Z0-9_-]{1,160}$/.test(value.slice(prefix.length));
}

/** Read a native Orca CLI export. A worker's report never changes the paper's evidence state. */
export function readOrcaInbox(input: unknown, origin: string, runId: string, documents: ReadonlySet<string>): OrcaPaperReceipt[] {
  const envelope = object(input);
  const result = object(envelope?.result);
  if (envelope?.ok !== true || !Array.isArray(result?.messages)) throw new Error("Invalid Orca inbox");
  const receipts = new Map<string, OrcaPaperReceipt | null>();
  for (const raw of result.messages) {
    const row = object(raw);
    if (!row || row.type !== "worker_done" || row.delivery_contract !== "current_delivery" ||
      !identifier(row.id, "msg_") || !identifier(row.run_id, "run_") ||
      row.to_handle !== "run:" + row.run_id || !identifier(row.from_handle, "term_")) continue;
    const payload = jsonField(row.payload);
    const body = jsonField(row.body);
    if (!body || typeof body.document_id !== "string" || !documents.has(body.document_id) || !payload ||
      !identifier(payload.taskId, "task_") || !identifier(payload.dispatchId, "ctx_") ||
      (payload.outcome !== "succeeded" && payload.outcome !== "failed")) continue;
    const paperUrl = localPaperMapLink(origin, runId, body.document_id);
    if (!paperUrl || body.paper_url !== paperUrl) continue;
    const key = row.run_id + "/" + row.id;
    const receipt: OrcaPaperReceipt = { message: row.id, run: row.run_id, task: payload.taskId, dispatch: payload.dispatchId,
      worker: row.from_handle, document: body.document_id, outcome: payload.outcome };
    const prior = receipts.get(key);
    if (prior === undefined) receipts.set(key, receipt);
    else if (prior && (prior.task !== receipt.task || prior.dispatch !== receipt.dispatch || prior.worker !== receipt.worker ||
      prior.document !== receipt.document || prior.outcome !== receipt.outcome)) receipts.set(key, null);
  }
  return [...receipts.values()].filter(row => row !== null);
}
