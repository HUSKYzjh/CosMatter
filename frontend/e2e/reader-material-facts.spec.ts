import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

const run = "reader_material_facts";
const papers = [
  { document_id: "synthetic-film", title: "Polarization in paired films", source: "Fixture" },
  { document_id: "synthetic-crystal", title: "Crystal control", source: "Fixture" },
];
const segment = { segment_id: "fig_2", kind: "figure_caption", locator: "markdown_line:2-3", markdown_range: { start: 2, end: 3 } };
const lines = ["# Paired films", "Figure 2. Sample A: 0 mC/m² at 0 K.", "Sample B: 32 mC/m² at 300 K."];
const observation = {
  fact_id: "film_a", category: "property", name: "极化强度", segment_id: segment.segment_id, locator: segment.locator,
  value: 0, unit: "mC/m²", normalized_value: 0, normalized_unit: "C/m²",
  qualifiers: { figure: "Fig. 2", sample: "A", temperature_K: 0, annealed: false, uncertainty: null },
};
const trustStatus = "human_reviewed_structured_material_facts_not_scientific_conclusion";
const ledgers = [
  { document_id: papers[0].document_id, trust_status: trustStatus, facts: [
    observation,
    { ...observation, fact_id: "film_b", value: 32, normalized_value: 0.032,
      qualifiers: { figure: "Fig. 2", sample: "B", temperature_K: 300, annealed: true, uncertainty: 0.1 } },
    { ...observation, fact_id: "other_locator", name: "参照观察", value: null, normalized_value: null, locator: "markdown_line:4-4" },
  ] },
  { document_id: papers[1].document_id, trust_status: trustStatus, facts: [
    { ...observation, fact_id: "crystal", name: "晶体对照", value: 14, normalized_value: 0.014,
      qualifiers: { figure: "Fig. 2", sample: "crystal-control", temperature_K: 200 } },
  ] },
];

async function expectQualifier(card: Locator, key: string, value: string) {
  const pair = card.locator("dl > div").filter({ has: card.page().getByText(key, { exact: true }) });
  await expect(pair.locator("dd")).toHaveText(value);
}

function receipt(documentId: string, runId = run) {
  return { run_id: runId, document_id: documentId, segment_count: 1,
    trust_status: "human_reviewed_parser_selection_not_evidence_card", segments: [segment] };
}

async function installRun(page: Page, savedCount: () => number, sourceMap: (route: Route) => Promise<void>) {
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.material_fact_ledgers = ledgers;
  bundle.material_facts = ledgers[0];
  bundle.evidence_cards = [];
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", edges: [],
    nodes: papers.map(paper => ({ node_id: "paper:" + paper.document_id, kind: "candidate_paper", label: paper.title,
      trust_status: "candidate_metadata_not_scientific_evidence" })) };
  const lineReads: { document: string | null; segment: string | null }[] = [];
  const writes: string[] = [];
  await page.route("**/api/**", route => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() !== "GET") writes.push(request.method() + " " + url.pathname);
    const prefix = "/api/runs/" + run + "/";
    if (!url.pathname.startsWith(prefix)) return route.fulfill({ status: 404 });
    switch (url.pathname.slice(prefix.length)) {
      case "ui": return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      case "stage-contract": return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "parse") });
      case "pdf/tasks/cached": return route.fulfill({ json: { run_id: run, tasks: [], trust_status: "private_pdf_task_registry_metadata_only" } });
      case "candidate-screening": return route.fulfill({ json: { run_id: run, candidate_count: papers.length, candidates: papers,
        trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
        decisions: papers.map(paper => ({ document_id: paper.document_id, decision: "include_for_fulltext", reason_codes: ["material_match"] })) } });
      case "source-parse-status": return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id,
        trust_status: "saved_source_parse_state_not_scientific_evidence",
        tasks: papers.map(paper => ({ document_id: paper.document_id, state: "done", markdown_ready: true, source_map_segment_count: savedCount() })) } });
      case "source-map": return sourceMap(route);
      case "source-markdown-lines": {
        const read = { document: url.searchParams.get("document_id"), segment: url.searchParams.get("segment_id") };
        lineReads.push(read);
        if (read.document !== papers[0].document_id || read.segment !== segment.segment_id) return route.fulfill({ status: 409 });
        const start = segment.markdown_range.start;
        return route.fulfill({ json: { run_id: run, document_id: read.document, recorded_range: segment.markdown_range, start,
          total_lines: lines.length, lines: lines.slice(start - 1).map((text, index) => ({ number: start + index, text, truncated: false })) } });
      }
      default: return route.fulfill({ status: 404 });
    }
  });
  return { lineReads, writes };
}

for (const width of [320, 1280]) {
  test("keeps observations, conditions and verified source lines tied to the selected paper at " + width + "px", async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    let crystalReads = 0;
    const { lineReads, writes } = await installRun(page, () => 1, route => {
      const target = new URL(route.request().url()).searchParams.get("document_id");
      if (target !== papers[1].document_id) return route.fulfill({ json: receipt(papers[0].document_id) });
      crystalReads++;
      // The other paper and the other run both have the same segment ID and locator.
      if (crystalReads === 1) return route.fulfill({ json: receipt(papers[0].document_id) });
      if (crystalReads === 2) return route.fulfill({ json: receipt(target, "other_run") });
      return route.fulfill({ json: receipt(target) });
    });

    await page.goto("/?api=local#run=" + run + "&document=" + papers[0].document_id, { waitUntil: "domcontentloaded" });
    const ledger = page.getByRole("region", { name: "本篇材料事实" });
    const cards = ledger.getByRole("listitem");
    await expect(cards).toHaveCount(3, { timeout: 30_000 });
    const first = cards.filter({ hasText: "property · film_a" });
    const second = cards.filter({ hasText: "property · film_b" });
    for (const card of [first, second]) {
      await expect(card.getByRole("heading", { name: "极化强度", exact: true })).toBeVisible();
      await expect(card.getByText("markdown_line:2-3 · fig_2", { exact: true })).toBeVisible();
      await expectQualifier(card, "figure", "Fig. 2");
    }
    await expect(first.getByText("0 mC/m²", { exact: true })).toBeVisible();
    await expect(first.getByText("已登记的规范值 0 C/m²", { exact: true })).toBeVisible();
    await expectQualifier(first, "sample", "A");
    await expectQualifier(first, "temperature_K", "0");
    await expectQualifier(first, "annealed", "false");
    await expectQualifier(first, "uncertainty", "未提供");
    await expect(second.getByText("32 mC/m²", { exact: true })).toBeVisible();
    await expect(second.getByText("已登记的规范值 0.032 C/m²", { exact: true })).toBeVisible();
    await expectQualifier(second, "sample", "B");
    await expectQualifier(second, "temperature_K", "300");
    await expectQualifier(second, "annealed", "true");
    const wrongLocator = cards.filter({ hasText: "property · other_locator" });
    await expect(wrongLocator.getByText("未提供数值", { exact: false })).toBeVisible();
    await expect(first.getByRole("button", { name: "查看来源 极化强度 · film_a" })).toBeVisible();
    const openSource = second.getByRole("button", { name: "查看来源 极化强度 · film_b" });
    await expect(openSource).toBeVisible();
    await expect(wrongLocator.getByRole("button")).toHaveCount(0);

    const rectangles = await cards.evaluateAll(items => items.map(item => {
      const { left, right, top, bottom } = item.getBoundingClientRect();
      const textFits = [...item.querySelectorAll("h3, p, dt, dd, button")].every(element => {
        const range = document.createRange();
        range.selectNodeContents(element);
        return [...range.getClientRects()].every(box => box.left >= left - 1 && box.right <= right + 1);
      });
      return { left, right, top, bottom, textFits };
    }));
    for (const [index, rect] of rectangles.entries()) {
      expect(rect.left).toBeGreaterThanOrEqual(0);
      expect(rect.right).toBeLessThanOrEqual(width);
      expect(rect.textFits).toBe(true);
      for (const other of rectangles.slice(index + 1)) {
        expect(rect.right <= other.left || other.right <= rect.left || rect.bottom <= other.top || other.bottom <= rect.top).toBe(true);
      }
    }

    await openSource.press("Enter");
    const source = page.getByRole("region", { name: "原文行号" });
    await expect(source).toBeFocused();
    await expect(source.getByText("来源定位第 2–3 行", { exact: true })).toBeVisible();
    await expect(source.locator("li.selected .source-line-text")).toHaveText(lines.slice(1));
    await expect(source.locator("li.selected .source-line-number")).toHaveText(["2", "3"]);
    await source.getByRole("button", { name: "返回材料事实" }).press("Enter");
    await expect(openSource).toBeFocused();
    await expect(openSource).toBeInViewport();

    await page.getByRole("button", { name: "更换论文" }).press("Enter");
    const otherMap = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname.endsWith("/source-map") && url.searchParams.get("document_id") === papers[1].document_id;
    });
    await page.getByRole("button", { name: "进入阅读页 · " + papers[1].title }).press("Enter");
    await otherMap;
    await expect(cards).toHaveCount(1);
    await expect(cards.getByRole("heading", { name: "晶体对照" })).toBeVisible();
    await expect(cards.getByText("14 mC/m²", { exact: true })).toBeVisible();
    await expectQualifier(cards, "sample", "crystal-control");
    await expect(ledger.getByText("极化强度", { exact: true })).toHaveCount(0);
    const retry = page.getByRole("button", { name: "重新读取已登记定位" });
    for (const attempt of [1, 2]) {
      await expect.poll(() => crystalReads).toBe(attempt);
      await expect(page.getByText("来源定位回执与当前任务或论文不匹配，请重试。")).toBeVisible();
      await expect(page.locator(".recorded-source-map, .source-map-followups")).toHaveCount(0);
      await expect(page.getByRole("button", { name: "查看原文 " + segment.locator, exact: true })).toHaveCount(0);
      await expect(cards.getByRole("button", { name: /查看来源/ })).toHaveCount(0);
      await retry.press("Enter");
    }
    await expect(cards.getByRole("button", { name: "查看来源 晶体对照 · crystal" })).toBeVisible();
    await expect(page.locator(".recorded-source-map")).toContainText(segment.locator);
    await expect(page.getByRole("region", { name: "后续人工核对步骤" })).toBeVisible();
    await expect(source.locator(".source-line-text")).toHaveCount(0);
    expect(lineReads).toEqual([{ document: papers[0].document_id, segment: segment.segment_id }]);
    expect(writes).toEqual([]);
  });
}

test("keeps the checked source draft editable after a mismatched write receipt and accepts its retry", async ({ page }) => {
  const paper = papers[0];
  const posts: unknown[] = [];
  let saved = false;
  const { writes } = await installRun(page, () => saved ? 1 : 0, route => {
    if (route.request().method() === "POST") {
      posts.push(route.request().postDataJSON());
      if (posts.length === 1) return route.fulfill({ json: receipt(papers[1].document_id) });
      saved = true;
    }
    return route.fulfill({ json: receipt(paper.document_id) });
  });
  await page.goto("/?api=local#run=" + run + "&document=" + paper.document_id, { waitUntil: "domcontentloaded" });
  const locator = page.getByLabel("来源定位", { exact: true });
  const quote = page.getByLabel("人工核对的短引文");
  const confirm = page.getByRole("checkbox", { name: /我已在本地 Markdown 中核对/ });
  const submit = page.getByRole("button", { name: "登记人工 Source Map" });
  await expect(locator).toBeVisible({ timeout: 30_000 });
  await locator.fill(segment.locator);
  await quote.fill(lines.slice(1).join("\n"));
  await confirm.check();
  await submit.press("Enter");
  await expect(page.locator(".source-map-message")).toHaveText("来源定位回执与当前任务或论文不匹配，请重试。");
  await expect(page.locator(".recorded-source-map, .source-map-followups")).toHaveCount(0);
  await expect(locator).toHaveValue(segment.locator);
  await expect(quote).toHaveValue(lines.slice(1).join("\n"));
  await expect(confirm).toBeChecked();
  await expect(submit).toBeEnabled();
  await submit.press("Enter");
  await expect(page.locator(".recorded-source-map")).toContainText(segment.locator);
  await expect(page.getByRole("region", { name: "后续人工核对步骤" })).toBeVisible();
  expect(posts).toHaveLength(2);
  expect(posts[1]).toEqual(posts[0]);
  expect(writes).toEqual(Array(2).fill("POST /api/runs/" + run + "/source-map"));
});
