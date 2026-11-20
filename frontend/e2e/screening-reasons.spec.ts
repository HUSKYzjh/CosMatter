import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";
import type { CandidateScreeningDecision } from "../src/localApi";

async function openRecordedScreening(page: Page) {
  const runId = "screening_multiple_reasons";
  const bundle = JSON.parse(await readFile(resolve(process.cwd(), "../examples/ui-demo/route_diagnostics.json"), "utf8"));
  const candidates = [
    { document_id: "paper_a", title: "Sample A", source: "local fixture", publication_year: 2024 },
    { document_id: "paper_b", title: "Sample B", source: "local fixture", publication_year: 2025 },
  ];
  bundle.literature_graph = {
    trust_status: "human_reviewed_graph_projection",
    nodes: candidates.map(paper => ({ node_id: "paper:" + paper.document_id, kind: "candidate_paper", label: paper.title,
      trust_status: "candidate_metadata_not_scientific_evidence" })),
    edges: [],
  };
  const recorded: CandidateScreeningDecision[] = [
    { document_id: "paper_a", decision: "include_for_fulltext", reason_codes: ["material_match", "scope_match"] },
    { document_id: "paper_b", decision: "exclude", reason_codes: ["review_or_protocol", "out_of_scope_material"] },
  ];
  let checklist = {
    run_id: runId, candidates, candidate_count: candidates.length, checklist_revision: "a".repeat(64),
    trust_status: "human_reviewed_candidate_screening_not_scientific_evidence", decisions: recorded,
  };
  const writes: { decisions: CandidateScreeningDecision[]; checklist_revision: string }[] = [];
  await page.route("**/api/**", route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const prefix = "/api/runs/" + runId;
    if (path === prefix + "/status") return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    if (path === prefix + "/ui") return route.fulfill({ json: bundle });
    if (path === prefix + "/stage-contract") return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "screening") });
    if (path === prefix + "/candidate-screening") {
      if (request.method() === "GET") return route.fulfill({ json: checklist });
      const result = request.postDataJSON();
      writes.push(result);
      checklist = { ...checklist, decisions: result.decisions, checklist_revision: "b".repeat(64) };
      return route.fulfill({ json: { run_id: runId, candidate_count: candidates.length } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto(`/?api=local#run=${runId}&screening=${checklist.checklist_revision}`, { waitUntil: "domcontentloaded" });
  const panel = page.getByRole("region", { name: "候选文献人工筛选" });
  await expect(panel.getByRole("heading")).toBeVisible({ timeout: 30_000 });
  return { panel, recorded, writes };
}

test("adding a screening reason preserves the recorded reasons after reload and on submission", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  const { panel, recorded, writes } = await openRecordedScreening(page);
  const selected = panel.getByRole("list", { name: "已选理由" });
  await expect(selected.getByRole("button")).toHaveCount(2);
  await panel.getByRole("combobox", { name: "理由", exact: true }).selectOption("method_match");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(panel.getByText("已登记 2 篇 · 草稿修改 1 篇")).toBeVisible({ timeout: 30_000 });
  await expect(selected.getByRole("button")).toHaveCount(3);
  expect(await selected.evaluate(list => list.scrollWidth <= list.clientWidth)).toBe(true);
  const add = panel.getByRole("combobox", { name: "理由", exact: true });
  await expect(add.locator('option[value="method_match"]')).toHaveJSProperty("disabled", true);
  await panel.getByRole("button", { name: "下一篇", exact: true }).click();
  await expect(selected.getByRole("button", { name: "移除理由：综述或方案" })).toBeVisible();
  await panel.getByRole("button", { name: "上一篇", exact: true }).click();
  await expect(selected.getByRole("button", { name: "移除理由：范围匹配" })).toBeVisible();
  await panel.getByRole("button", { name: "提交人工筛选决定" }).click();
  await expect.poll(() => writes.map(body => body.decisions)).toEqual([[
    { ...recorded[0], reason_codes: ["material_match", "scope_match", "method_match"] }, recorded[1],
  ]]);
  expect(writes[0].checklist_revision).toBe("a".repeat(64));
});

test("removes only the chosen reason and requires fresh reasons when the decision changes", async ({ page }) => {
  const { panel, recorded, writes } = await openRecordedScreening(page);
  const selected = panel.getByRole("list", { name: "已选理由" });
  const add = panel.getByRole("combobox", { name: "理由", exact: true });
  const submit = panel.getByRole("button", { name: "提交人工筛选决定" });
  await selected.getByRole("button", { name: "移除理由：范围匹配" }).press("Enter");
  await expect(selected.getByRole("button")).toHaveCount(1);
  await expect(selected.getByRole("button", { name: "移除理由：材料匹配" })).toBeVisible();
  await expect(add).toBeFocused();
  await expect(submit).toBeEnabled();
  await selected.getByRole("button", { name: "移除理由：材料匹配" }).press("Enter");
  await expect(submit).toBeDisabled();
  await add.selectOption("scope_match");
  await panel.getByRole("combobox", { name: "决定", exact: true }).selectOption("needs_metadata_review");
  await expect(selected).toHaveCount(0);
  await expect(submit).toBeDisabled();
  await add.selectOption("not_enough_metadata");
  await submit.press("Enter");
  await expect.poll(() => writes.map(body => body.decisions)).toEqual([[
    { document_id: "paper_a", decision: "needs_metadata_review", reason_codes: ["not_enough_metadata"] }, recorded[1],
  ]]);
});
