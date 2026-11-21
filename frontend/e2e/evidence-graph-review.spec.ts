import { expect, test, type Route } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

test("loads the accepted graph on demand and keeps failed pages and stale write receipts out of the queue", async ({ page }) => {
  const run = "graph_review";
  const bundle = JSON.parse(await readFile(resolve(process.cwd(), "../examples/ui-demo/route_diagnostics.json"), "utf8"));
  const mission = bundle.mission.mission_id, graph = "graph:" + "a".repeat(32);
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", nodes: [{ node_id: "paper:sample", kind: "candidate_paper", label: "Sample paper", trust_status: "retrieval_candidate_not_scientific_evidence" }], edges: [] };
  const reads: string[] = [];
  let pendingPage: Route | null = null, pendingDraft: Route | null = null;
  let stallPage = true, stallDraft = true, wrongMission = false, wrongApproval = true;
  await page.route("**/api/runs/**", async route => {
    const url = new URL(route.request().url()), endpoint = url.pathname.split("/").pop();
    if (endpoint === "ui") return route.fulfill({ json: bundle });
    if (endpoint === "status") return route.fulfill({ json: { run_id: run, mission_id: mission, state: "RETRIEVE" } });
    if (endpoint === "stage-contract") return route.fulfill({ json: stageContractFixture(run, mission, "screening") });
    if (endpoint === "graph") {
      const type = url.searchParams.get("node_type")!, offset = Number(url.searchParams.get("offset"));
      reads.push(type + offset);
      if (offset === 25 && stallPage) { pendingPage = route; return; }
      const total = type === "EvidenceCard" ? 26 : 1;
      const nodes = Array.from({ length: Math.min(25, total - offset) }, (_, i) => ({
        node_id: type + "_" + (offset + i), node_type: type, label: type + " sample " + (offset + i), attributes: {},
      }));
      return route.fulfill({ json: { schema_version: "1.0", mission_id: wrongMission ? "other_mission" : mission, graph_id: graph,
        trust_status: "accepted_evidence_projection_not_scientific_conclusion", nodes, edges: [],
        page: { node_types: [type], offset, limit: 25, node_total: total, truncated: offset + nodes.length < total } } });
    }
    if (endpoint === "plan-draft") {
      if (stallDraft) { pendingDraft = route; return; }
      const body = route.request().postDataJSON();
      return route.fulfill({ json: { ...body, plan_id: "graph_plan_valid", mission_id: mission, graph_id: graph,
        proposed_action: "request_human_to_review_or_project_graph", trust_status: "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance" } });
    }
    if (endpoint === "plan-approval") return route.fulfill({ json: { ...route.request().postDataJSON(), ...(wrongApproval ? { plan_id: "graph_plan_other" } : {}), mission_id: mission,
      graph_id: graph, approval_id: "graph_plan_approval_valid", status: "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance" } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/?api=local#run=" + run);
  await page.getByRole("button", { name: /^03 文献星图/ }).click();
  const queue = page.locator("details.graph-review-tools").filter({ hasText: "已接受证据的审核队列" });
  await expect(queue.locator("summary")).toBeVisible({ timeout: 30_000 });
  expect(reads).toEqual([]);
  await queue.locator("summary").press("Enter");
  await expect(queue.getByRole("checkbox")).toHaveCount(25);
  await queue.getByRole("checkbox").first().check();
  await queue.getByRole("button", { name: "下一页", exact: true }).click();
  await expect.poll(() => Boolean(pendingPage)).toBe(true);
  await expect(queue.getByRole("checkbox")).toHaveCount(0);
  await expect(queue.getByRole("button", { name: "创建不可信草案" })).toHaveCount(0);
  await pendingPage!.fulfill({ status: 503, json: {} });
  await expect(queue.getByRole("alert")).toBeVisible();
  stallPage = false;
  await queue.getByRole("button", { name: "重试读取" }).click();
  await expect(queue.getByRole("checkbox", { name: /EvidenceCard sample 25/ })).toBeVisible();

  await queue.getByRole("checkbox").check();
  await queue.getByLabel("审核或检查理由").fill("Review this card");
  await queue.getByRole("button", { name: "创建不可信草案" }).click();
  await expect.poll(() => Boolean(pendingDraft)).toBe(true);
  wrongMission = true;
  await queue.getByRole("button", { name: "Paper", exact: true }).click();
  await expect(queue.getByRole("alert")).toBeVisible();
  await expect(queue.getByRole("checkbox")).toHaveCount(0);
  wrongMission = false;
  await queue.getByRole("button", { name: "重试读取" }).click();
  await expect(queue.getByRole("checkbox", { name: /Paper sample 0/ })).toBeVisible();
  await pendingDraft!.fulfill({ json: { plan_id: "graph_plan_stale", mission_id: mission, graph_id: graph, node_ids: ["EvidenceCard_25"],
    intent: "Review this card", proposed_action: "request_human_to_review_or_project_graph", trust_status: "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance" } });
  await expect(queue.getByLabel("人工审核者")).toHaveCount(0);
  stallDraft = false;
  await queue.getByRole("checkbox").check();
  await queue.getByLabel("审核或检查理由").fill("Inspect the paper");
  await queue.getByRole("button", { name: "创建不可信草案" }).click();
  await queue.getByLabel("人工审核者").fill("Reviewer");
  await queue.getByLabel("审核或检查理由").fill("Inspect this paper's method");
  await expect(queue.getByRole("button", { name: "记录人工跟进确认" })).toHaveCount(0);
  await queue.getByRole("button", { name: "创建不可信草案" }).click();
  await queue.getByLabel("人工审核者").fill("Reviewer");
  await queue.getByRole("button", { name: "记录人工跟进确认" }).click();
  await expect(queue.getByText(/未能核对操作回执/)).toBeVisible();
  await expect(queue.getByLabel("人工审核者")).toHaveCount(0);
  wrongApproval = false;
  await queue.getByRole("button", { name: "创建不可信草案" }).click();
  await queue.getByLabel("人工审核者").fill("Reviewer");
  await queue.getByRole("button", { name: "记录人工跟进确认" }).click();
  await expect(queue.getByText(/approval_valid/)).toBeVisible();
  await expect(queue.getByLabel("人工审核者")).toHaveCount(0);
  const requests = reads.length;
  await queue.locator("summary").click();
  await queue.locator("summary").click();
  expect(reads.length).toBe(requests);
});
