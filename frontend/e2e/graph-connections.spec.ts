import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

for (const width of [320, 1366]) {
  test(`follows both citation directions and an exact evidence source at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    const run = "graph_neighbours";
    const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
    const node = (node_id: string, kind: string, label: string) => ({ node_id, kind, label, trust_status: "candidate_metadata" });
    const edge = (source_id: string, target_id: string, edge_type: string, relation_source: string, trust_status = "public_metadata") =>
      ({ source_id, target_id, edge_type, relation_source, trust_status });
    bundle.literature_graph = {
      trust_status: "navigation_metadata", nodes: [
        node("paper:alpha", "candidate_paper", "Alpha film"), node("paper:beta", "candidate_paper", "Beta reference"),
        node("paper:gamma", "candidate_paper", "Gamma follow-up"), node("evidence:e1", "accepted_evidence", "Alpha measurement"),
        node("evidence:e2", "evidence_card", "Unverified measurement"),
      ], edges: [
        edge("paper:alpha", "paper:beta", "citation_reference", "OpenAlex"),
        edge("paper:alpha", "paper:gamma", "citation_cited_by", "OpenAlex"),
        edge("paper:alpha", "evidence:e1", "source_provenance", "reviewed source map", "accepted"),
        edge("paper:alpha", "evidence:e2", "source_provenance", "metadata link", "candidate_metadata"),
      ],
    };
    const card = { evidence_id: "e1", claim: "Alpha measurement", quote: "Fixture alpha reported 300 K.",
      review_status: "accepted", stance: "support", conditions: { temperature_K: 300 },
      provenance: { document_id: "alpha", locator: "Figure 5", source: "fixture", access_policy: "authorized" } };
    bundle.evidence_cards = [card, { ...card, evidence_id: "e2", claim: "Unverified measurement" }];
    const writes: string[] = [];
    await page.route("**/api/**", route => {
      const url = new URL(route.request().url());
      if (route.request().method() !== "GET") writes.push(url.pathname);
      if (url.pathname === `/api/runs/${run}/ui`) return route.fulfill({ json: bundle });
      if (url.pathname === `/api/runs/${run}/status`) return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      if (url.pathname === `/api/runs/${run}/stage-contract`) return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "extraction") });
      return route.fulfill({ status: 404 });
    });
    await page.goto(`/?api=local#run=${run}&document=alpha`);
    const inspector = page.getByRole("complementary", { name: "图谱检查器" });
    const links = inspector.getByRole("region", { name: "直接关系" });
    await expect(links).toBeVisible({ timeout: 30_000 });
    if (width === 320) {
      const tools = page.getByRole("button", { name: "运行与 DSH 工具", exact: true });
      const copyId = page.getByRole("button", { name: "复制运行 ID", exact: true });
      await expect(tools).toHaveAttribute("aria-expanded", "false");
      await tools.press("Enter");
      await expect(copyId).toBeVisible();
      await tools.press("Enter");
      await expect(copyId).toBeHidden();
    }
    await links.getByRole("button", { name: /引用了.*Beta reference/ }).press("Enter");
    await expect(inspector.getByRole("heading", { name: "Beta reference" })).toBeVisible();
    await expect(inspector).toBeFocused();
    await expect(links.getByRole("button", { name: /被其引用.*Alpha film/ })).toBeVisible();
    await inspector.getByRole("button", { name: /返回上一节点.*Alpha film/ }).click();
    await links.getByRole("button", { name: /被其引用.*Gamma follow-up/ }).click();
    await expect(links.getByRole("button", { name: /引用了.*Alpha film/ })).toBeVisible();
    await inspector.getByRole("button", { name: /返回上一节点.*Alpha film/ }).press("Enter");
    await links.getByRole("button", { name: /Unverified measurement/ }).click();
    await expect(inspector.getByRole("button", { name: /在原文核对/ })).toHaveCount(0);
    await inspector.getByRole("button", { name: /返回上一节点/ }).click();
    await links.getByRole("button", { name: /Alpha measurement/ }).press("Enter");
    await inspector.getByRole("button", { name: "在原文核对 · Figure 5" }).click();
    await expect(page.locator(".source-reader blockquote")).toHaveText(card.quote, { timeout: 30_000 });
    expect(writes).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
