import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

test("follows each evidence card to its exact verified quote within shared source lines", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  const run = "reader_quote_check";
  const paper = { document_id: "synthetic-film", title: "Film measurements", source: "fixture" };
  const lines = ["Sample A used 300 K; sample B", "used 500 K. The control used 300 K."];
  const cards = [
    { id: "card_a", quote: "Sample A used 300 K", range: { start: 1, end: 1 } },
    { id: "card_b", quote: "sample B\nused 500 K", range: { start: 1, end: 2 } },
    { id: "card_repeat", quote: "300 K", range: { start: 1, end: 2 } },
  ];
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.evidence_cards = cards.map(({ id, quote, range }) => ({
    evidence_id: id, claim: id, quote, review_status: "accepted", stance: "support", conditions: {},
    provenance: { document_id: paper.document_id, locator: `markdown_line:${range.start}-${range.end}`, source: "fixture", access_policy: "authorized" },
  }));
  const paperNode = `paper:${paper.document_id}`;
  bundle.literature_graph = {
    trust_status: "human_reviewed_graph_projection",
    nodes: [{ node_id: paperNode, kind: "candidate_paper", label: paper.title, trust_status: "candidate_metadata_not_scientific_evidence" },
      ...cards.map(({ id }) => ({ node_id: `evidence:${id}`, kind: "evidence_card", label: id, trust_status: "accepted" }))],
    edges: cards.map(({ id }) => ({ source_id: paperNode, target_id: `evidence:${id}`, edge_type: "source_provenance", relation_source: "reviewed source map", trust_status: "accepted" })),
  };
  const reads: string[] = [];
  const writes: string[] = [];
  let mismatch = false;
  let releaseSegment!: () => void;
  const delayedSegment = new Promise<void>(resolve => { releaseSegment = resolve; });
  await page.route("**/api/**", route => {
    const req = route.request();
    const url = new URL(req.url());
    if (req.method() !== "GET") writes.push(req.method());
    const prefix = `/api/runs/${run}/`;
    if (!url.pathname.startsWith(prefix)) return route.fulfill({ status: 404 });
    switch (url.pathname.slice(prefix.length)) {
      case "ui": return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      case "stage-contract": return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "parse") });
      case "pdf/tasks/cached": return route.fulfill({ json: { run_id: run, tasks: [], trust_status: "private_pdf_task_registry_metadata_only" } });
      case "candidate-screening": return route.fulfill({ json: { run_id: run, candidate_count: 1, candidates: [paper],
        trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
        decisions: [{ document_id: paper.document_id, decision: "include_for_fulltext", reason_codes: ["material_match"] }] } });
      case "source-parse-status": return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id,
        trust_status: "saved_source_parse_state_not_scientific_evidence",
        tasks: [{ document_id: paper.document_id, state: "done", markdown_ready: true, source_map_segment_count: cards.length }] } });
      case "source-map": return route.fulfill({ json: { run_id: run, document_id: paper.document_id, segment_count: cards.length,
        trust_status: "human_reviewed_parser_selection_not_evidence_card", segments: cards.map(({ id, range }) => ({
          segment_id: id, locator: `markdown_line:${range.start}-${range.end}`, kind: "paragraph", markdown_range: range,
        })) } });
      case "source-markdown-lines": {
        const segmentId = url.searchParams.get("segment_id");
        const card = cards.find(item => item.id === (segmentId ?? url.searchParams.get("evidence_id")));
        if (!card || url.searchParams.get("document_id") !== paper.document_id) return route.fulfill({ status: 409 });
        reads.push(segmentId ? `segment:${segmentId}` : card.id);
        if (mismatch) return route.fulfill({ status: 409 });
        const response = { run_id: run, document_id: paper.document_id, recorded_range: card.range, start: 1, total_lines: 2,
          lines: lines.map((text, index) => ({ number: index + 1, text, truncated: false })) };
        if (segmentId) return delayedSegment.then(() => route.fulfill({ json: response }));
        return route.fulfill({ json: { ...response, evidence_id: card.id } });
      }
      default: return route.fulfill({ status: 404 });
    }
  });
  await page.goto(`/?api=local#run=${run}&document=${paper.document_id}`);
  const source = page.getByRole("region", { name: "原文行号" });
  const marks = source.locator("mark");
  const openCard = async (id: string) => {
    await page.locator(".evidence-queue").getByRole("button", { name: new RegExp(id) }).press("Enter");
    await page.getByRole("button", { name: "核对原文", exact: true }).press("Enter");
    await expect(source).toBeFocused();
  };
  await openCard("card_a");
  await expect(marks).toHaveText(["Sample A used 300 K"]);
  await expect(marks.first()).toBeInViewport();
  await source.getByRole("button", { name: "返回证据卡" }).press("Enter");
  await expect(page.getByRole("button", { name: "核对原文", exact: true })).toBeFocused();
  await expect(source.locator(".source-line-text")).toHaveCount(0);
  await openCard("card_b");
  await expect(marks).toHaveText(["sample B", "used 500 K"]);
  await expect(source.locator(".source-line-text")).toHaveText(lines);
  await page.getByRole("button", { name: "查看原文 markdown_line:1-1", exact: true }).press("Enter");
  await expect(source.getByText("正在读取原文行…")).toBeVisible();
  await expect(source.locator(".source-line-text")).toHaveCount(0);
  releaseSegment();
  await expect(source.getByText("来源定位第 1 行", { exact: true })).toBeVisible();
  await expect(marks).toHaveCount(0);
  await expect(source.locator("li.selected .source-line-text")).toHaveText(lines[0]);
  await openCard("card_repeat");
  await expect(source.getByText("来源定位第 1–2 行", { exact: true })).toBeVisible();
  await expect(marks).toHaveCount(0);
  await expect(source.getByText(/当前窗口无法唯一标出/)).toBeVisible();
  mismatch = true;
  await openCard("card_a");
  await expect(source.getByText("该证据卡与当前原文无法对应。")).toBeVisible();
  await expect(source.locator(".source-line-text")).toHaveCount(0);
  expect(reads).toEqual(["card_a", "card_b", "segment:card_a", "card_repeat", "card_a"]);
  expect(writes).toEqual([]);
});
