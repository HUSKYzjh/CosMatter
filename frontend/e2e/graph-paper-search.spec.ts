import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

for (const width of [320, 1280]) {
  test(`finds a filtered paper from its DOI and returns to paginated results, ${width}px`, async ({ page }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width, height: 860 });
    const run = "search_fixture";
    const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
    const printedTitle = "Film with piezoelectric response of La₂O₃";
    const nodes = Array.from({ length: 8 }, (_, n) => ({
      node_id: `paper:film-${n}`, kind: "candidate_paper", label: n === 7 ? "Film with piezoelectric response of La$_2$O$_3$" : "Film " + n,
      doi: `10.1234/film-${n}`, publication_year: 2021, source: "Sciverse", trust_status: "retrieval_candidate",
    }));
    bundle.literature_graph = { trust_status: "fixture", coverage: { candidate_count: 28, visible_candidate_count: 8, accepted_evidence_count: 0, linked_accepted_evidence_count: 0 }, nodes, edges: [] };
    const methods: string[] = [];
    await page.route("**/api/**", route => {
      methods.push(route.request().method());
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/ui")) return route.fulfill({ json: bundle });
      if (path.endsWith("/status")) return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      if (path.endsWith("/stage-contract")) return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "extraction") });
      return route.fulfill({ status: 404 });
    });
    await page.goto(`/?api=local#run=${run}&document=film-0`);
    const search = page.getByRole("region", { name: "检索当前星图" });
    const input = search.getByRole("searchbox");
    await expect(search).toContainText("8 / 28 篇候选", { timeout: 30_000 });
    const question = page.locator(".graph-question");
    await question.locator("summary").press("Enter");
    await expect(question.locator("p")).toHaveText(bundle.mission.question);
    await question.locator("summary").press("Enter");
    await expect(question.locator("p")).toBeHidden();
    if (width <= 600) await page.getByRole("button", { name: "图谱显示选项" }).click();
    await page.getByLabel("主题簇").selectOption("ferroelectric");
    await input.fill("https://doi.org/10.1234/FILM-7");
    const hit = search.getByRole("button", { name: /Film with piezoelectric response/ });
    await expect(hit).toContainText("显示被筛选隐藏的节点");
    await input.press("ArrowDown");
    await expect(hit).toBeFocused();
    await hit.press("Enter");
    const inspector = page.getByRole("complementary", { name: "图谱检查器" });
    await expect(inspector).toBeFocused();
    await expect(inspector.getByRole("heading", { name: printedTitle, exact: true })).toBeVisible();
    await expect(inspector.getByText("10.1234/film-7", { exact: true })).toBeVisible();
    await expect(page.getByLabel("主题簇")).toHaveValue("all");
    await inspector.getByRole("button", { name: "返回检索结果" }).click();
    await expect(input).toBeFocused();
    await input.fill("La₂O₃");
    await expect(search.getByRole("listitem")).toHaveCount(1);
    await expect(hit.locator("strong")).toHaveText(printedTitle);
    await input.fill("Sciverse 2021");
    await expect(search.getByRole("listitem")).toHaveCount(6);
    await search.getByRole("button", { name: "下一页" }).click();
    await expect(search.getByRole("listitem")).toHaveCount(2);
    await expect(search.getByRole("listitem").first().getByRole("button")).toBeFocused();
    await input.fill("missing-document");
    await expect(search.getByRole("status")).toContainText("当前星图没有匹配项");
    await expect(search.getByRole("button", { name: "查看完整候选清单" })).toBeVisible();
    await input.press("Escape");
    await expect(input).toHaveValue("");
    expect(await search.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    expect(methods.every(method => method === "GET")).toBe(true);
  });
}
