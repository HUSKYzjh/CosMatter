import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import dagDefinition from "../../configs/cosmatter_workflow_dag.json" with { type: "json" };
import { CosMatterObservabilityClient, localWorkbenchUrl } from "../../plugins/dsh-cosmatter-observability-plugin/lib/client.js";
import { stageContractFixture } from "../src/stageContractFixture";

test("opens source-map review from a DSH run after the matching paper is selected", async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const run = "run_source_review";
  const paper = { document_id: "zno-film", title: "ZnO film optical measurements", source: "crossref", publication_year: 2023 };
  const other = { ...paper, document_id: "unreviewed-film", title: "Unscreened thin film" };
  const papers = [paper, other];
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", edges: [], nodes: papers.map(item => ({
    node_id: "paper:" + item.document_id, label: item.title, kind: "candidate_paper", trust_status: "candidate_metadata_not_scientific_evidence",
  })) };
  const mission = bundle.mission.mission_id;
  const contract = stageContractFixture(run, mission, "extraction");
  const runPath = `/api/runs/${run}/`;
  const client = new CosMatterObservabilityClient({ baseUrl: baseURL }, async url => {
    expect(new URL(String(url)).pathname).toBe(runPath + "stage-contract");
    return Response.json(contract);
  });
  const dsh = await client.stageContract(run);
  expect(dsh.stages.find(stage => stage.stage === dsh.next_stage)?.recovery_route).toBe("source_map_review");

  const writes: string[] = [];
  await page.route("**/api/**", route => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (request.method() !== "GET") writes.push(pathname);
    if (!pathname.startsWith(runPath)) return route.fulfill({ status: 404, json: {} });
    switch (pathname.slice(runPath.length)) {
      case "ui": return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: run, mission_id: mission, state: "HUMAN_REVIEW" } });
      case "stage-contract": return route.fulfill({ json: contract });
      case "workflow-dag": return route.fulfill({ json: {
        schema_version: "cosmatter.workflow-dag/v1", run_id: run, mission_id: mission, dag_id: dagDefinition.dag_id,
        trust_status: "loopback_declared_dag_readiness_projection_not_execution_authorization", scheduler_status: "declarative_only_no_execution_authorization",
        runtime_safety: "verified", max_concurrency: 1, eligible_stages: [], human_review_required: true,
        blocked_stage_count: contract.stages.filter(stage => stage.status === "blocked").length,
        stages: dagDefinition.stages.map((stage, index) => ({ ...stage, status: contract.stages[index].status })),
      } });
      case "operational-telemetry": return route.fulfill({ json: {
        schema_version: "cosmatter.operational-telemetry/v2", run_id: run, mission_id: mission,
        trust_status: "loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence", dispatch_operations: [],
        provider_operations: [], validation_rejections: [], cost_latency_status: "not_recorded", cost_latency: [],
      } });
      case "candidate-screening": return route.fulfill({ json: { run_id: run, candidate_count: papers.length, candidates: papers,
        trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
        decisions: [{ document_id: paper.document_id, decision: "include_for_fulltext", reason_codes: ["material_match"] }] } });
      case "source-parse-status": return route.fulfill({ json: { run_id: run, mission_id: mission,
        trust_status: "saved_source_parse_state_not_scientific_evidence", tasks: [{ document_id: paper.document_id,
          state: "done", markdown_ready: true, source_map_segment_count: 0 }] } });
      default: return route.fulfill({ status: 404, json: {} });
    }
  });
  await page.goto(localWorkbenchUrl(baseURL!, run));
  const workbench = page.locator(".workbench");
  const recovery = page.getByRole("region", { name: "阶段恢复导航" });
  const relay = page.getByRole("region", { name: "航线提示" });
  const openReview = recovery.getByRole("button", { name: "打开来源定位审核" });
  await expect(workbench).toHaveClass(/view-graph/);
  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await recovery.getByRole("button", { name: "选择论文以核对来源" }).click();
  await expect(workbench).toHaveClass(/view-graph/);
  await expect(relay).toContainText("请先在文献星图选择一篇待核对论文");

  const cards = page.locator(".fleet-reading-cards");
  await cards.getByRole("button", { name: new RegExp(other.title) }).click();
  await openReview.click();
  await expect(workbench).toHaveClass(/view-graph/);
  await expect(relay).toContainText("当前论文尚未被人工纳入全文核对");
  await expect(relay.getByRole("button", { name: "返回文献星图选择论文" })).toBeVisible();

  await cards.getByRole("button", { name: new RegExp(paper.title) }).click();
  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await openReview.click();
  await expect(workbench).toHaveClass(/view-reader/);
  await expect(page.locator(".private-source-map-review")).toContainText("人工来源定位", { timeout: 30_000 });
  await expect(page.locator(".rail-run-id code")).toHaveText(run);
  expect(writes).toEqual([]);
});
