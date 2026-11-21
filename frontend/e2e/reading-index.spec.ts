import { expect, test } from "@playwright/test";

for (const width of [320, 1366]) {
  test(`browses the full reading index and follows graph selection at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const papers = Array.from({ length: 8 }, (_, i) => ({
      node_id: `paper:index-${i + 1}`,
      kind: "candidate_paper",
      label: `Structural response of specimen ${i + 1} under variable temperature, pressure and mechanical boundary conditions`,
      publication_year: 2020 + i,
      source: "Fixture archive",
      trust_status: "metadata_fixture",
    }));
    await page.route("**/ui.json", route => route.fulfill({ json: {
      schema_version: "1.0",
      generated_at: "2026-09-05T00:00:00Z",
      mission: { mission_id: "index", question: "Compare specimen response", material: "oxide", property_name: "dielectric", scope: "bulk" },
      literature_graph: { trust_status: "metadata_fixture", nodes: papers, edges: [] },
    } }));
    await page.goto("/?ui=server&api=local");
    const index = page.getByRole("region", { name: "舰队阅读航道" });
    const rows = index.locator("li button");
    await expect(rows).toHaveCount(6, { timeout: 30_000 });
    await index.getByRole("button", { name: "下一页" }).click();
    await expect(rows).toHaveCount(2);
    await expect(rows.first()).toBeFocused();
    await expect(rows.last()).toHaveAttribute("data-document-id", "index-8");
    await expect(rows.last()).toContainText("2027 · Fixture archive");
    const title = rows.last().locator("strong");
    await expect(title).toHaveText(papers[7].label);
    expect(await title.evaluate(el => {
      const text = document.createRange();
      text.selectNodeContents(el);
      const box = el.closest("button")!.getBoundingClientRect();
      return [...text.getClientRects()].every(rect => rect.left >= box.left - 1 && rect.right <= box.right + 1 && rect.bottom <= box.bottom + 1)
        && getComputedStyle(el).webkitLineClamp === "none";
    })).toBe(true);
    await rows.last().click();
    await expect(page.locator(".evidence-inspector h2")).toHaveText(papers[7].label);
    await expect(rows.last()).toHaveAttribute("aria-current", "true");
    await page.locator(".graph-paper-search input[type=search]").fill("index-2");
    await page.locator(".graph-search-results button").first().click();
    await expect(rows).toHaveCount(6);
    await expect(rows.nth(1)).toHaveAttribute("aria-current", "true");
    await expect(index.getByRole("button", { name: "上一页" })).toBeDisabled();
  });
}
