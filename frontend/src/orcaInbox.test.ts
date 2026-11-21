import { describe, expect, it } from "vitest";
import { readOrcaInbox } from "./orcaInbox";
import { localPaperMapLink } from "./liveRunIdentity";

const origin = "http://127.0.0.1:8765";
const run = "compare";
const documents = new Set(["alpha", "beta"]);
const body = (id: string) => ({ document_id: id, paper_url: localPaperMapLink(origin, run, id) });
const receipt = {
  id: "msg_01", type: "worker_done", delivery_contract: "current_delivery",
  run_id: "run_group", from_handle: "term_first", to_handle: "run:run_group",
  body: JSON.stringify({ ...body("alpha"), values: [[300, "K"]] }),
  payload: JSON.stringify({ taskId: "task_01", dispatchId: "ctx_01", outcome: "succeeded" }),
};
const parse = (...messages: unknown[]) => readOrcaInbox({ ok: true, result: { messages } }, origin, run, documents);

describe("the native Orca inbox", () => {
  it("retains the worker and dispatch identities for success and failure, exposing no scientific values", () => {
    const result = parse(receipt, receipt, { ...receipt, id: "msg_02", from_handle: "term_other", body: body("beta"),
      payload: { taskId: "task_02", dispatchId: "ctx_02", outcome: "failed" } });
    expect(result).toEqual([
      { message: "msg_01", run: "run_group", worker: "term_first", task: "task_01", dispatch: "ctx_01", document: "alpha", outcome: "succeeded" },
      { message: "msg_02", run: "run_group", worker: "term_other", task: "task_02", dispatch: "ctx_02", document: "beta", outcome: "failed" },
    ]);
  });
  it("matches only the assigned paper in this workbench, run and native mailbox", () => {
    const wrongBodies = [body("unknown"), { document_id: "alpha", paper_url: body("beta").paper_url },
      { document_id: "alpha", paper_url: localPaperMapLink(origin, "other", "alpha") },
      { document_id: "alpha", paper_url: localPaperMapLink("http://localhost:9999", run, "alpha") }];
    expect(parse(...wrongBodies.map(body => ({ ...receipt, body })), { ...receipt, delivery_contract: "historic" },
      { ...receipt, type: "heartbeat" }, { ...receipt, run_id: "run_other" }, { ...receipt, payload: {} },
      { ...receipt, payload: { taskId: "task_a", dispatchId: "ctx_b", outcome: "blocked" } })).toEqual([]);
  });
  it("omits conflicting copies of one message, preserves separate attempts, and rejects other file formats", () => {
    const retry = { ...receipt, id: "msg_retry", payload: { taskId: "task_01", dispatchId: "ctx_retry", outcome: "succeeded" } };
    expect(parse(receipt, { ...receipt, body: body("beta") }, receipt, retry).map(row => row.dispatch)).toEqual(["ctx_retry"]);
    for (const input of [[], { tasks: [] }, { ok: false, result: { messages: [] } }])
      expect(() => readOrcaInbox(input, origin, run, documents)).toThrow("Invalid Orca inbox");
  });
});
