import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";
import type { CandidateScreeningDecision } from "../src/localApi";

test("explicit screening progress survives closing a tab and restores the exact candidate with keyboard focus", async ({ context, page }) => {
  const runId = "review_checkpoint";
  const papers = ["A", "B", "C"].map(letter => ({ document_id: "doc_" + letter, title: "Paper " + letter, source: "fixture", publication_year: 2025 }));
  const bundle = JSON.parse(await readFile(resolve(process.cwd(), "../examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", edges: [], nodes: papers.map(item => ({
    node_id: "paper:" + item.document_id, kind: "candidate_paper", label: item.title, trust_status: "candidate_metadata_not_scientific_evidence",
  })) };
  let revision = "a".repeat(64), submissions = 0;
  let decisions: CandidateScreeningDecision[] = papers.map(({ document_id }) => ({ document_id, decision: "unreviewed", reason_codes: [] }));
  const link = () => "/?api=local#run=" + runId + "&screening=" + revision;
  await context.route("**/api/runs/**", async route => {
    switch (new URL(route.request().url()).pathname.split("/").pop()) {
      case "ui": return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "RETRIEVE" } });
      case "stage-contract": return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "screening") });
      case "candidate-screening":
        if (route.request().method() === "POST") {
          decisions = route.request().postDataJSON().decisions;
          revision = "c".repeat(64);
          submissions++;
          return route.fulfill({ json: { run_id: runId, candidate_count: papers.length } });
        }
        return route.fulfill({ json: { run_id: runId, candidate_count: papers.length, candidates: papers,
          decisions, checklist_revision: revision, trust_status: submissions ? "human_reviewed_candidate_screening_not_scientific_evidence" : "blank_human_candidate_screening_template_not_a_result" } });
      default: return route.fulfill({ status: 404, json: {} });
    }
  });
  await page.goto(link());
  const initial = page.getByRole("region", { name: "候选文献人工筛选" });
  await initial.getByRole("combobox", { name: "决定", exact: true }).selectOption("include_for_fulltext");
  await initial.getByRole("combobox", { name: "理由", exact: true }).selectOption("material_match");
  await initial.getByRole("button", { name: "下一篇", exact: true }).click();
  await initial.getByRole("combobox", { name: "决定", exact: true }).selectOption("exclude");
  await initial.getByRole("combobox", { name: "理由", exact: true }).selectOption("out_of_scope_material");
  await initial.getByRole("button", { name: "下一篇", exact: true }).click();
  await initial.getByRole("button", { name: "保存进度到本机" }).press("Enter");
  await expect(initial.getByText("已保存当前文献和筛选草稿。")).toBeVisible();
  await page.close();

  const reopened = await context.newPage();
  await reopened.setViewportSize({ width: 320, height: 860 });
  await reopened.goto(link());
  const panel = reopened.getByRole("region", { name: "候选文献人工筛选" });
  await expect(panel.getByText("已填 0 / 3")).toBeVisible();
  const restore = panel.getByRole("button", { name: "恢复上次进度" });
  await restore.press("Enter");
  await expect(panel.getByText("已填 2 / 3")).toBeVisible();
  await expect(panel.locator("article strong", { hasText: "Paper C" })).toBeFocused();
  expect(submissions).toBe(0);
  const clear = panel.getByRole("button", { name: "清除已存进度" });
  await clear.click();
  await expect(restore).toHaveCount(0);
  await expect(panel.getByText("已填 2 / 3")).toBeVisible();
  await panel.getByRole("button", { name: "保存进度到本机" }).click();
  revision = "b".repeat(64);
  await restore.click();
  await expect(panel.getByText("当前清单已变化，已存进度失效。")).toBeVisible();
  await expect(restore).toHaveCount(0);
  await expect(panel.getByText("已填 0 / 3")).toBeVisible();
  expect(submissions).toBe(0);
  for (const item of papers) {
    await panel.getByRole("button", { name: new RegExp(item.title) }).click();
    await panel.getByRole("combobox", { name: "决定", exact: true }).selectOption("exclude");
    await panel.getByRole("combobox", { name: "理由", exact: true }).selectOption("out_of_scope_material");
  }
  await panel.getByRole("button", { name: "保存进度到本机" }).click();
  await panel.getByRole("button", { name: "提交人工筛选决定" }).click();
  await expect.poll(() => submissions).toBe(1);
  await expect.poll(() => reopened.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("cosmatter.screening-checkpoint")).length)).toBe(0);
});
