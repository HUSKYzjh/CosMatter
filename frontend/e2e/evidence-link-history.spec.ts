import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

const runId = "evidence_link_history";
const cards = [
  { document: "oxide-a", title: "Oxide A", evidence: "card-a", locator: "p. 4, Fig. 2", quote: "Sample A reached 310 K." },
  { document: "oxide-b", title: "Oxide B", evidence: "card-b", locator: "p. 8, Table 1", quote: "Sample B reached 470 K." },
];

async function setupRun(page: Page, waitForBundle?: () => Promise<void>) {
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.evidence_cards = cards.map(card => ({
    evidence_id: card.evidence, claim: card.quote, quote: card.quote, review_status: "accepted", stance: "support", conditions: {},
    provenance: { document_id: card.document, locator: card.locator, source: "fixture", access_policy: "authorized" },
  }));
  bundle.literature_graph = {
    trust_status: "human_reviewed_graph_projection",
    nodes: cards.flatMap(card => [
      { node_id: "paper:" + card.document, kind: "candidate_paper", label: card.title, trust_status: "candidate_metadata_not_scientific_evidence" },
      { node_id: "evidence:" + card.evidence, kind: "evidence_card", label: card.quote, trust_status: "accepted" },
    ]),
    edges: cards.map(card => ({
      source_id: "paper:" + card.document, target_id: "evidence:" + card.evidence,
      edge_type: "source_provenance", relation_source: "reviewed source map", trust_status: "accepted",
    })),
  };
  const writes: string[] = [];
  await page.route("**/api/**", async route => {
    const request = route.request();
    if (request.method() !== "GET") writes.push(request.method());
    const path = new URL(request.url()).pathname;
    const prefix = `/api/runs/${runId}/`;
    if (!path.startsWith(prefix)) return route.fulfill({ status: 404 });
    switch (path.slice(prefix.length)) {
      case "ui":
        await waitForBundle?.();
        return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      case "stage-contract": return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "extraction") });
      case "pdf/tasks/cached": return route.fulfill({ json: { run_id: runId, tasks: [], trust_status: "private_pdf_task_registry_metadata_only" } });
      default: return route.fulfill({ status: 404 });
    }
  });
  return writes;
}

function fragment(card?: typeof cards[number]) {
  const params = new URLSearchParams({ run: runId });
  if (card) { params.set("document", card.document); params.set("evidence", card.evidence); }
  return "#" + params;
}

async function follow(page: Page, card?: typeof cards[number]) {
  await page.evaluate(hash => { location.hash = hash; }, fragment(card));
}

async function expectCard(page: Page, card: typeof cards[number]) {
  const reader = page.locator(".source-reader");
  await expect(reader.locator("blockquote")).toHaveText(card.quote, { timeout: 30_000 });
  await expect(reader.getByText(card.document, { exact: true })).toBeVisible();
  await expect(reader.getByText(card.locator, { exact: true })).toBeVisible();
  await expect(reader).toBeFocused();
  expect(new URL(page.url()).hash).toBe(fragment(card));
}

test("restores the run landing and both exact reader targets from DSH link history", async ({ page }) => {
  const writes = await setupRun(page);
  await page.goto("/?api=local" + fragment());
  const graph = page.getByRole("region", { name: "文献证据闭环状态" });
  await expect(graph).toBeVisible({ timeout: 30_000 });
  for (const card of cards) {
    await follow(page, card);
    await expectCard(page, card);
  }
  await page.goBack();
  await expectCard(page, cards[0]);
  await page.goBack();
  await expect(graph).toBeVisible();
  await expect(page.locator(".source-reader")).toHaveCount(0);
  expect(new URL(page.url()).hash).toBe(fragment());
  await page.goForward();
  await expectCard(page, cards[0]);
  await page.goForward();
  await expectCard(page, cards[1]);
  expect(writes).toEqual([]);
});

for (const launchHash of ["", "#run=..%2Foutside"]) {
  test(`returning to the ${launchHash ? "invalid-link" : "plain"} launch URL discards a late evidence response`, async ({ page }) => {
    let release!: () => void;
    const held = new Promise<void>(resolve => { release = resolve; });
    const writes = await setupRun(page, () => held);
    const bundlePath = `/api/runs/${runId}/ui`;
    await page.goto("/?api=local" + launchHash);
    const requested = page.waitForRequest(request => new URL(request.url()).pathname === bundlePath);
    await follow(page, cards[0]);
    await requested;
    await page.goBack();
    await expect(page.locator('.run-continuation[aria-busy="true"]')).toHaveCount(0);
    const response = page.waitForResponse(res => new URL(res.url()).pathname === bundlePath);
    release();
    await (await response).finished();
    expect(new URL(page.url()).hash).toBe(launchHash);
    await expect(page.locator(".workbench")).toHaveClass(/view-launch/);
    await expect(page.locator(".source-reader")).toHaveCount(0);
    await page.goForward();
    await expectCard(page, cards[0]);
    expect(writes).toEqual([]);
  });
}
