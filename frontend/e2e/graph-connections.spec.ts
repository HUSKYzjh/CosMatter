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
        node("evidence:e2", "evidence_card", "Unverified measurement"), node("evidence:e3", "accepted_evidence", "Alpha measurement"),
      ], edges: [
        edge("paper:alpha", "paper:beta", "citation_reference", "OpenAlex"),
        edge("paper:alpha", "paper:gamma", "citation_cited_by", "OpenAlex"),
        edge("paper:alpha", "evidence:e1", "source_provenance", "reviewed source map", "accepted"),
        edge("paper:alpha", "evidence:e3", "source_provenance", "reviewed source map", "accepted"),
        edge("paper:beta", "evidence:e1", "source_provenance", "unverified cross-paper link", "candidate_metadata"),
        edge("paper:alpha", "evidence:e2", "source_provenance", "metadata link", "candidate_metadata"),
      ],
    };
    const card = { evidence_id: "e1", claim: "Alpha measurement", quote: "Fixture alpha reported 300 K.",
      review_status: "accepted", stance: "support", conditions: { temperature_K: 300 },
      provenance: { document_id: "alpha", locator: "Figure 5", source: "fixture", access_policy: "authorized" } };
    bundle.evidence_cards = [card, { ...card, evidence_id: "e2", claim: "Unverified measurement" },
      { ...card, evidence_id: "e3", provenance: { ...card.provenance, locator: "p. 9, Table II" }, quote: "Table II reports the other measurement." }];
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
      const tools = page.getByRole("button", { name: "运行工具", exact: true });
      const copyId = page.getByRole("button", { name: "复制运行 ID", exact: true });
      await expect(tools).toHaveAttribute("aria-expanded", "false");
      await tools.press("Enter");
      await expect(copyId).toBeVisible();
      await tools.press("Enter");
      await expect(copyId).toBeHidden();
    }
    const firstCard = links.getByRole("listitem").filter({ has: page.getByRole("button", { name: "在原文核对 · Figure 5 · e1" }) });
    const otherCard = links.getByRole("listitem").filter({ has: page.getByRole("button", { name: "在原文核对 · p. 9, Table II · e3" }) });
    await expect(firstCard).toContainText("证据来源 · fixture");
    await expect(firstCard).toContainText("关系来源 · reviewed source map");
    await expect(firstCard).toContainText("Alpha measurement");
    await expect(otherCard).toContainText("Alpha measurement");
    await expect(links.getByRole("button", { name: /在原文核对/ })).toHaveCount(2);
    await links.getByRole("button", { name: /引用了.*Beta reference/ }).press("Enter");
    await expect(inspector.getByRole("heading", { name: "Beta reference" })).toBeVisible();
    await expect(inspector).toBeFocused();
    await expect(links.getByRole("button", { name: /在原文核对/ })).toHaveCount(0);
    await expect(links.getByRole("button", { name: /被其引用.*Alpha film/ })).toBeVisible();
    await inspector.getByRole("button", { name: /返回上一节点.*Alpha film/ }).click();
    await links.getByRole("button", { name: /被其引用.*Gamma follow-up/ }).click();
    await expect(links.getByRole("button", { name: /引用了.*Alpha film/ })).toBeVisible();
    await inspector.getByRole("button", { name: /返回上一节点.*Alpha film/ }).press("Enter");
    await links.getByRole("button", { name: /Unverified measurement/ }).click();
    await expect(inspector.getByRole("button", { name: /在原文核对/ })).toHaveCount(0);
    await inspector.getByRole("button", { name: /返回上一节点/ }).click();
    await firstCard.getByRole("button", { name: /Alpha measurement/ }).press("Enter");
    await expect(inspector.locator(".graph-record-meta")).toContainText("证据卡 IDe1");
    await inspector.getByRole("button", { name: "在原文核对 · Figure 5 · e1" }).click();
    await expect(page.locator(".source-reader blockquote")).toHaveText(card.quote, { timeout: 30_000 });
    await page.goto(`/?api=local#run=${run}&document=alpha&view=map`);
    await otherCard.getByRole("button", { name: /在原文核对/ }).press("Enter");
    await expect(page.locator(".source-reader blockquote")).toHaveText("Table II reports the other measurement.");
    expect(writes).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("keeps citation lines off until the map toolbar enables them", async ({ page }) => {
  const run = "citation-layer";
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  bundle.literature_graph = {
    trust_status: "public_metadata",
    nodes: [
      { node_id: "paper:seed", kind: "relation_root_paper", label: "Seed paper", trust_status: "public_metadata" },
      { node_id: "citation:one", kind: "citation_work", label: "Cited work", trust_status: "public_metadata" },
      { node_id: "citation:two", kind: "citation_work", label: "Citing work", trust_status: "public_metadata" },
    ],
    edges: [
      { source_id: "paper:seed", target_id: "citation:one", edge_type: "citation_reference", relation_source: "OpenAlex", trust_status: "public_metadata" },
      { source_id: "citation:two", target_id: "paper:seed", edge_type: "citation_cited_by", relation_source: "OpenAlex", trust_status: "public_metadata" },
    ],
  };
  await page.route("**/api/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname === `/api/runs/${run}/ui`) return route.fulfill({ json: bundle });
    if (url.pathname === `/api/runs/${run}/status`) return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    if (url.pathname === `/api/runs/${run}/stage-contract`) return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "extraction") });
    return route.fulfill({ status: 404 });
  });
  await page.goto(`/?api=local#run=${run}`);
  const map = page.getByRole("group", { name: "交互式文献图谱" });
  await expect(map.locator("canvas").first()).toBeVisible({ timeout: 30_000 });
  const toggle = page.getByRole("button", { name: "切换引文关系线", exact: true });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => map.evaluate(el => (el as HTMLElement & { _cyreg: { cy: { edges: (selector: string) => { filter: (predicate: (edge: { style: (key: string) => string }) => boolean) => { length: number } } } } })._cyreg.cy.edges('[flightRole="bibliography"]').filter(edge => edge.style("opacity") !== "0").length)).toBe(0);
  await toggle.press("Enter");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => map.evaluate(el => (el as HTMLElement & { _cyreg: { cy: { edges: (selector: string) => { filter: (predicate: (edge: { style: (key: string) => string }) => boolean) => { length: number } } } } })._cyreg.cy.edges('[flightRole="bibliography"]').filter(edge => edge.style("opacity") !== "0").length)).toBe(2);
  await toggle.press("Space");
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => map.evaluate(el => (el as HTMLElement & { _cyreg: { cy: { nodes: (selector: string) => { length: number } } } })._cyreg.cy.nodes('[group="References"]').length)).toBe(0);
});
