import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { ExtractionRow } from "../src/extractionTable";
import { stageContractFixture } from "../src/stageContractFixture";

const run = "map_orca_test";
const papers = { "alpha-long": "Longer ID", alpha: "Alpha film", gap: "Included paper", absent: "Candidate only" };
const tablePath = `/api/runs/${run}/extraction-table`;

function emptyRow(document_id: keyof typeof papers): ExtractionRow {
  return { document_id, title: papers[document_id], doi: null, status: "awaiting_extraction",
    evidence_id: null, claim: null, material: null, property_name: null, stance: null,
    conditions: {}, locator: null, document_version: null, source: null, reader_available: false, reported_facts: [] };
}

function reviewedRow(id: "alpha" | "alpha-long", evidence: string, figure: string): ExtractionRow {
  return { ...emptyRow(id), status: "reviewed", evidence_id: evidence,
    claim: "Synthetic measurement", locator: figure, reader_available: true };
}

async function openMap(page: Page, paper: keyof typeof papers) {
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.literature_graph = {
    trust_status: "navigation_metadata",
    nodes: Object.entries(papers).map(([id, label]) => ({
      node_id: "paper:" + id, kind: "candidate_paper", label, trust_status: "candidate_metadata",
    })),
    edges: [{ source_id: "paper:absent", target_id: "paper:gap", edge_type: "citation_reference",
      relation_source: "fixture", trust_status: "public_metadata" }],
  };
  const allRows = [reviewedRow("alpha-long", "other-card", "Figure 2"), reviewedRow("alpha", "a1", "Figure 4"),
    reviewedRow("alpha", "a2", "Figure 5"), emptyRow("gap")];
  const reads: string[] = [];
  const writes: string[] = [];
  const prefix = "/api/runs/" + run;
  const included = (["alpha-long", "alpha", "gap"] as const).map(document_id => ({ document_id, title: papers[document_id], source: "fixture" }));
  await page.context().route("**/api/**", route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (route.request().method() !== "GET") {
      writes.push(route.request().method() + " " + path);
      return route.fulfill({ status: 405 });
    }
    if (path === tablePath) {
      reads.push(path + url.search);
      const documentId = url.searchParams.get("document_id");
      const rows = documentId === null ? allRows : allRows.filter(row => row.document_id === documentId);
      const gaps = rows.filter(row => row.status !== "reviewed");
      return route.fulfill({ json: { schema_version: "cosmatter.extraction-table/v1", run_id: run, screening_status: "current",
        ...(documentId === null ? {} : { document_id: documentId }),
        summary: { document_count: new Set(rows.map(row => row.document_id)).size, reviewed_count: rows.length - gaps.length,
          gap_count: new Set(gaps.map(row => row.document_id)).size }, rows } });
    }
    if (path === prefix + "/ui") return route.fulfill({ json: bundle });
    if (path === prefix + "/status") return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    if (path === prefix + "/stage-contract") return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "extraction") });
    if (path === prefix + "/candidate-screening") return route.fulfill({ json: {
      run_id: run, candidate_count: included.length, candidates: included,
      trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
      decisions: included.map(({ document_id }) => ({ document_id, decision: "include_for_fulltext", reason_codes: ["material_match"] })),
    } });
    if (path === prefix + "/source-parse-status") return route.fulfill({ json: {
      run_id: run, mission_id: bundle.mission.mission_id, trust_status: "saved_source_parse_state_not_scientific_evidence",
      tasks: [{ document_id: "alpha", state: "done", markdown_ready: true, source_map_segment_count: 2 }],
    } });
    return route.fulfill({ status: 404 });
  });
  await page.goto(`/?api=local#run=${run}&document=${paper}`);
  if (paper === "alpha") {
    const stages = page.getByRole("list", { name: "研究阶段" });
    await expect(stages.getByRole("button", { name: /证据核对/ })).toHaveAttribute("aria-current", "step", { timeout: 30_000 });
    await stages.getByRole("button", { name: /文献星图/ }).click();
  }
  const inspector = page.getByRole("complementary", { name: "图谱检查器" });
  const verify = inspector.getByRole("button", { name: "核验这篇论文", exact: true });
  await expect(verify).toBeVisible({ timeout: 30_000 });
  expect(reads).toEqual([]);
  const table = page.getByRole("region", { name: "跨文献证据对照表" });
  return { reads, writes, inspector, verify, table };
}

async function downloadPaperTask(page: Page, table: Locator) {
  const download = page.waitForEvent("download");
  await table.getByRole("button", { name: "导出本篇 Orca 核验任务", exact: true }).click();
  const file = await download;
  const manifest = JSON.parse(await readFile((await file.path())!, "utf8"));
  expect(manifest.schema_version).toBe("cosmatter.orca-tasks/v1");
  expect(manifest.run_id).toBe(run);
  expect(manifest.tasks).toHaveLength(1);
  const task = manifest.tasks[0];
  return { title: task.task_title, spec: task.spec, target: JSON.parse(task.spec.split("\n").at(-1)) };
}

async function openExportedPaperLink(page: Page, inspector: Locator, paper: keyof typeof papers, exportedUrl: string) {
  const link = inspector.getByRole("link", { name: "本篇星图链接", exact: true });
  const href = await link.evaluate((anchor: HTMLAnchorElement) => anchor.href);
  expect(exportedUrl).toBe(href);
  const url = new URL(href);
  expect(url.origin).toBe(new URL(page.url()).origin);
  expect(url.searchParams.get("api")).toBe("local");
  expect(Object.fromEntries(new URLSearchParams(url.hash.slice(1)))).toEqual({ run, document: paper, view: "map" });
  const [restored] = await Promise.all([page.waitForEvent("popup"), link.click()]);
  const selected = restored.getByRole("complementary", { name: "图谱检查器" });
  await expect(selected.getByRole("heading", { name: papers[paper], exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(restored).toHaveURL(href);
}

test("opens the exact paper from a local Orca receipt and clears previous results on a bad import", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 880 });
  const { inspector, reads, writes } = await openMap(page, "alpha");
  const inbox = page.locator(".orca-map-inbox");
  await inbox.locator("summary").first().press("Enter");
  const origin = new URL(page.url()).origin;
  const receipt = (paper: string, outcome: string, id: string) => ({
    type: "worker_done", delivery_contract: "current_delivery", id: "msg_" + id, run_id: "run_team",
    to_handle: "run:run_team", from_handle: "term_" + id,
    payload: JSON.stringify({ taskId: "task_" + id, dispatchId: "ctx_" + id, outcome }),
    body: JSON.stringify({ document_id: paper, paper_url: origin + "/?api=local#run=" + run + "&document=" + paper + "&view=map" }),
  });
  const rows = [receipt("alpha-long", "succeeded", "one"), receipt("alpha", "failed", "two"), receipt("missing", "succeeded", "three")];
  const fileInput = inbox.getByLabel("选择 Orca 收件箱 JSON");
  await fileInput.setInputFiles({ name: "inbox.json", mimeType: "application/json", buffer: Buffer.from("\uFEFF" + JSON.stringify({ ok: true, result: { messages: rows } })) });
  await expect(inbox.getByRole("status")).toHaveText("为当前星图匹配到 2 条回执。");
  const first = inbox.getByRole("listitem").first();
  await first.getByText("查看派工标识").click();
  await expect(first).toContainText("ctx_one");
  await first.getByRole("button", { name: "Longer ID" }).press("Enter");
  await expect(inspector.getByRole("heading", { name: "Longer ID", exact: true })).toBeVisible();
  await inbox.getByRole("button", { name: "Alpha film" }).click();
  await expect(inspector.getByRole("heading", { name: "Alpha film", exact: true })).toBeVisible();
  await expect(inbox).toContainText("执行失败");
  expect(await inbox.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await fileInput.setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from("not json") });
  await expect(inbox.getByRole("status")).toContainText("无法读取 Orca 收件箱");
  await expect(inbox.getByRole("listitem")).toHaveCount(0);
  expect(reads).toEqual([]);
  expect(writes).toEqual([]);
});

test("exports exactly the selected paper and merges its two cards into one Orca task", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 860 });
  const { reads, writes, inspector, verify, table } = await openMap(page, "alpha");
  await verify.press("Enter");
  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.getByRole("table")).not.toContainText(papers["alpha-long"]);
  const result = await downloadPaperTask(page, table);
  expect(result.title).toBe("Verify paper [alpha]");
  expect(result.target.document_id).toBe("alpha");
  expect(result.target.extraction_table_url).toBe(new URL(tablePath + "?document_id=alpha", page.url()).href);
  expect(result.target.statuses).toEqual(["reviewed"]);
  expect(result.target.evidence).toEqual(["a1", "a2"].map(id => ({
    evidence_id: id, reader_url: expect.stringContaining(`#run=${run}&document=alpha&evidence=${id}`),
  })));
  expect(result.spec).not.toContain("other-card");
  await table.getByRole("button", { name: "返回星图", exact: true }).press("Enter");
  await expect(inspector.getByRole("heading", { name: papers.alpha })).toBeVisible();
  await openExportedPaperLink(page, inspector, "alpha", result.target.paper_url);
  expect(reads).toEqual([tablePath + "?document_id=alpha"]);
  expect(writes).toEqual([]);
});

test("distinguishes a candidate with no table row from an included paper with an evidence gap", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 880 });
  const { inspector, verify, table, reads, writes } = await openMap(page, "absent");
  await verify.click();
  await expect(table).toContainText("这篇论文暂无可导出的核验记录");
  await expect(table.getByRole("button", { name: "导出本篇 Orca 核验任务" })).toBeDisabled();
  await expect(table.locator("tbody tr")).toHaveCount(0);
  expect(reads).toEqual([tablePath + "?document_id=absent"]);
  await table.getByRole("button", { name: "查看全部论文" }).click();
  await expect(table.locator("tbody tr")).toHaveCount(4);
  expect(reads).toEqual([tablePath + "?document_id=absent", tablePath]);
  await expect(table.getByRole("button", { name: "导出 Orca 核验任务", exact: true })).toBeEnabled();
  await page.getByRole("group", { name: "文献展示方式" }).getByRole("button", { name: "文献关系图" }).click();
  await expect(inspector.getByRole("heading", { name: papers.absent })).toBeVisible();
  await inspector.getByRole("region", { name: "直接关系" }).getByRole("button", { name: /Included paper/ }).click();
  await verify.click();
  await expect(table.getByRole("table")).toContainText("待提取");
  const result = await downloadPaperTask(page, table);
  expect(result.target.document_id).toBe("gap");
  expect(result.target.extraction_table_url).toBe(new URL(tablePath + "?document_id=gap", page.url()).href);
  expect(result.target.statuses).toEqual(["awaiting_extraction"]);
  expect(result.target.evidence).toEqual([]);
  expect(result.spec).toContain("Keep this gap open");
  expect(await table.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await table.getByRole("button", { name: "返回星图", exact: true }).click();
  await openExportedPaperLink(page, inspector, "gap", result.target.paper_url);
  expect(reads).toEqual([tablePath + "?document_id=absent", tablePath, tablePath + "?document_id=gap"]);
  expect(writes).toEqual([]);
});
