import { expect, test } from "@playwright/test";
import type { Core } from "cytoscape";

test("keeps source arrows clear of other papers and cards when opening the inspector", async ({ page }) => {
  const papers = ["alpha", "beta", "gamma", "excluded"];
  const cards = ["a1", "a2"];
  const nodes = [
    { node_id: "mission:m", kind: "mission", label: "BiFeO3 / temperature" },
    ...papers.map(id => ({ node_id: "paper:" + id, kind: "candidate_paper", label: "Paper " + id })),
    ...cards.map(id => ({ node_id: "evidence:" + id, kind: "accepted_evidence", label: "Measured temperature" })),
  ].map(n => ({ ...n, trust_status: "metadata_fixture" }));
  const edges = [
    ...papers.map(id => ({ source_id: "mission:m", target_id: "paper:" + id, edge_type: "retrieval_candidate" })),
    ...cards.map(id => ({ source_id: "paper:alpha", target_id: "evidence:" + id, edge_type: "source_provenance" })),
  ].map(e => ({ ...e, relation_source: "fixture", trust_status: "metadata_fixture" }));
  await page.route("**/ui.json", r => r.fulfill({ json: { schema_version: "1.0", generated_at: "2026-11-21T00:00:00Z",
    mission: { mission_id: "m", question: "Compare temperatures", material: "BiFeO3", property_name: "temperature", scope: "films" },
    literature_graph: { trust_status: "metadata_fixture", nodes, edges } } }));
  for (const width of [1366, 320]) {
    await page.setViewportSize({ width, height: 880 });
    await page.goto("/?ui=server&api=local");
    const map = page.getByRole("group", { name: "交互式文献图谱" });
    await expect(map.locator("canvas").first()).toBeVisible({ timeout: 30_000 });
    const measure = () => map.evaluate(el => {
      const cy = (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy;
      const paper = cy.getElementById("paper:alpha");
      let clearance = Infinity;
      const arrows = cy.edges('[flightRole="evidence"]');
      for (const edge of arrows) {
        const start = edge.renderedSourceEndpoint(), end = edge.renderedTargetEndpoint();
        const ctrl = edge.renderedControlPoints()?.[0] ?? { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
        const others = cy.nodes('[isCluster="no"]').difference(edge.connectedNodes());
        for (let i = 1; i < 160; i++) {
          const t = i / 160, s = 1 - t;
          const x = s*s*start.x + 2*s*t*ctrl.x + t*t*end.x, y = s*s*start.y + 2*s*t*ctrl.y + t*t*end.y;
          for (const other of others) {
            const p = other.renderedPosition();
            clearance = Math.min(clearance, Math.hypot(x-p.x, y-p.y) - (other.renderedOuterWidth() + edge.renderedWidth()) / 2);
          }
        }
      }
      return { clearance, arrows: arrows.length, ring: paper.style("border-color"), selected: paper.hasClass("is-emphasized") };
    });
    const original = await measure();
    expect(original.arrows).toBe(2);
    expect(original.clearance).toBeGreaterThan(2);
    await page.locator(".fleet-reading-cards button").filter({hasText: "Paper alpha"}).click();
    await expect(page.locator(".evidence-inspector h2")).toHaveText("Paper alpha");
    await expect.poll(async () => {
      const selected = await measure();
      return selected.selected && selected.clearance > 2 && selected.ring === original.ring;
    }).toBe(true);
  }
});

for (const width of [320, 1366]) {
  test(`keeps the zoomed map available when inspecting a paper at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    const nodes = [
      ["paper:a", "candidate_paper", "Thin film A"],
      ["paper:b", "candidate_paper", "Thin film B"],
      ["evidence:a", "accepted_evidence", "Diffraction measurement"],
    ].map(([node_id, kind, label]) => ({ node_id, kind, label, trust_status: "metadata_only" }));
    await page.route("**/ui.json", route => route.fulfill({ json: {
      schema_version: "1.0", generated_at: "2026-09-05T00:00:00Z",
      mission: { mission_id: "canvas", question: "Compare film measurements", material: "BiFeO3", property_name: "strain", scope: "thin films" },
      literature_graph: { trust_status: "metadata_only_navigation_not_scientific_evidence", nodes,
        edges: [{ source_id: "paper:a", target_id: "evidence:a", edge_type: "source_provenance", relation_source: "fixture", trust_status: "metadata_only" }] },
    } }));
    await page.goto("/?ui=server&api=local");
    const map = page.getByRole("group", { name: "交互式文献图谱" });
    const zoom = page.getByLabel("图谱缩放比例");
    await expect(map.locator("canvas").first()).toBeVisible({ timeout: 30_000 });
    const painting = await map.locator("canvas").first().elementHandle();
    const initial = await zoom.innerText();
    await page.getByRole("button", { name: "放大", exact: true }).click();
    await expect(zoom).not.toHaveText(initial);
    const enlarged = await zoom.innerText();
    await map.press("+");
    await expect(zoom).not.toHaveText(enlarged);
    const magnification = await zoom.innerText();

    const cards = page.locator(".fleet-reading-cards button");
    for (const title of ["Thin film A", "Thin film B"]) {
      await cards.filter({ hasText: title }).click();
      await expect(page.locator(".evidence-inspector h2")).toHaveText(title);
      expect(await painting!.evaluate(element => element.isConnected)).toBe(true);
      await expect(zoom).toHaveText(magnification);
    }
    // Re-enter the canvas before the next paint. A pending inspector focus must yield to it.
    await cards.filter({ hasText: "Thin film B" }).evaluate(async card => {
      (card as HTMLElement).focus();
      (card as HTMLElement).click();
      document.querySelector<HTMLElement>(".cytoscape-literature-canvas")!.focus();
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    });
    await expect(map).toBeFocused();
    await map.press("0");
    await expect(zoom).not.toHaveText(magnification);
    await expect(map).toBeFocused();
    const layout = await page.locator(".lens-canvas-region").evaluate(region => {
      const bounds = (selector: string) => region.querySelector(selector)!.getBoundingClientRect();
      return {
        legendStarts: bounds(".paper-workflow-legend").top,
        legendEnds: bounds(".paper-workflow-legend").bottom,
        toolsEnd: bounds(".lens-canvas-tools").bottom,
        mapStarts: bounds(".cytoscape-literature-canvas").top,
        mapEnds: bounds(".cytoscape-literature-canvas").bottom,
        captionStarts: bounds(".lens-footnote").top,
      };
    });
    expect(layout.toolsEnd).toBeLessThanOrEqual(layout.mapStarts + 1);
    if (width === 320) expect(layout.mapEnds).toBeLessThanOrEqual(layout.legendStarts + 1);
    else expect(layout.legendEnds).toBeLessThanOrEqual(layout.mapStarts + 1);
    expect(layout.mapEnds).toBeLessThanOrEqual(layout.captionStarts + 1);
  });
}

for (const width of [320, 1366]) {
  test(`keeps dense literature labels readable and separated at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    const topics = ["Ferroelectric polarization", "Piezoelectric strain", "Interface", "Domain", "Simulation", "Structure"];
    const papers = Array.from({length: 48}, (_, i) => ({
      node_id: "paper:p" + i, kind: "candidate_paper", label: `${topics[i % topics.length]} ${i} in doped samples`,
      trust_status: "candidate_metadata",
    }));
    await page.route("**/ui.json", route => route.fulfill({ json: {
      schema_version: "1.0", generated_at: "2026-09-05T00:00:00Z",
      mission: { mission_id: "dense", question: "Compare papers", material: "BiFeO3", property_name: "strain", scope: "films" },
      literature_graph: { trust_status: "navigation_metadata",
        nodes: [{ node_id: "mission:dense", kind: "mission", label: "BiFeO3 films", trust_status: "mission_navigation" }, ...papers],
        edges: papers.map(p => ({ source_id: "mission:dense", target_id: p.node_id, edge_type: "retrieval_candidate",
          relation_source: "fixture", trust_status: "candidate_metadata" })) },
    } }));
    await page.goto("/?ui=server&api=local");
    const map = page.getByRole("group", {name: "交互式文献图谱"});
    await expect(map.locator("canvas").first()).toBeVisible({timeout: 30_000});
    const metrics = () => map.evaluate(el => {
      const cy = (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy;
      const papers = cy.nodes('[nodeKind="candidate_paper"]');
      const labels = papers.filter(node => Boolean(node.style("label")));
      const hidden = papers.filter(node => !node.style("label"))[0];
      const boxes = labels.map(node => node.renderedBoundingBox({ includeNodes: false, includeEdges: false, includeOverlays: false, includeUnderlays: false }));
      const regions = cy.nodes('[isCluster="yes"]');
      const regionsByTopic = new Map(regions.map(node => [node.data("region"), node] as const));
      const withinRegion = papers.every(paper => {
        const region = regionsByTopic.get(paper.data("region"));
        if (!region) return false;
        const box = region.boundingBox({ includeLabels: false });
        const point = paper.position();
        return box.x1 <= point.x && point.x <= box.x2 && box.y1 <= point.y && point.y <= box.y2;
      });
      return {
        papers: papers.length, labels: labels.length,
        withinRegion, topics: new Set(papers.map(node => node.data("region"))).size,
        markedRegion: regions.filter(node => node.hasClass("active-region")).map(node => node.data("region")),
        selectedRegion: papers.filter(node => node.hasClass("is-emphasized")).first().data("region"),
        activeEdges: cy.edges(".is-adjacent").length, retrievalCurves: cy.edges('[flightRole="formation"][weight]').length,
        font: Math.min(...labels.map(node => parseFloat(node.style("font-size")) * cy.zoom())),
        overlaps: boxes.some((a,i) => boxes.slice(i+1).some(b => Math.min(a.x2,b.x2) > Math.max(a.x1,b.x1) && Math.min(a.y2,b.y2) > Math.max(a.y1,b.y1))),
        hidden: hidden && { position: hidden.renderedPosition(), title: hidden.data("label") },
      };
    });
    for (const inspect of [false, true]) {
      if (inspect) {
        await map.scrollIntoViewIfNeeded();
        const target = (await metrics()).hidden!;
        expect(target).toBeTruthy();
        // A toolbar or banner can shift the canvas without changing its dimensions.
        // Prime hit testing at its old position, then click the same marker at its new one.
        const before = (await map.boundingBox())!;
        await page.mouse.move(before.x + target.position.x, before.y + target.position.y);
        await map.evaluate(el => { (el as HTMLElement).style.transform = "translateY(-56px)"; });
        const after = (await map.boundingBox())!;
        expect(after.y).toBeCloseTo(before.y - 56, 0);
        await page.mouse.click(after.x + target.position.x, after.y + target.position.y);
        await expect(page.locator(".evidence-inspector h2")).toHaveText(target.title);
        await expect.poll(() => map.evaluate(el =>
          (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy.nodes(".is-emphasized")[0]?.style("label") || ""
        )).not.toBe("");
      }
      await expect.poll(async () => {
        const result = await metrics();
        const selectionMatches = inspect ? result.markedRegion.length === 1 && result.markedRegion[0] === result.selectedRegion && result.activeEdges === 1
          : result.markedRegion.length === 0 && result.activeEdges === 0;
        return result.papers === 48 && result.labels >= 5 && result.font >= 10.5 && !result.overlaps
          && result.topics === 6 && result.withinRegion && result.retrievalCurves === 48 && selectionMatches;
      }).toBe(true);
    }
  });
}
