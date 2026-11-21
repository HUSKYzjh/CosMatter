import { expect, test } from "@playwright/test";

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
