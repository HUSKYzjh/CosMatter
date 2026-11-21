import { test, expect } from "@playwright/test";
import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { paperKeyphrase } from "../src/paperKeyphrase";

test("ships the current offline paper label bundle", async () => {
  await promisify(execFile)(process.execPath, [resolve("scripts/build-offline-paper-labels.mjs"), "--check"]);
});

for (const width of [320, 1366]) {
  test(`shows only the shared keyphrase on every offline paper node at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    await page.context().setOffline(true);
    const requests: string[] = [];
    page.on("request", request => { if (/^https?:/u.test(request.url())) requests.push(request.url()); });
    await page.goto(pathToFileURL(resolve("..", "web/network.html")).href);
    const titles = ["Critical phenomena and polarization rotation in epitaxial thin films", "Origin of stationary domain wall enhanced ferroelectric susceptibility"];
    const bundle = { schema_version: "1.0", mission: { material: "BiFeO3" },
      research_guide: { items: titles.map((title, i) => ({ document_id: "study-" + i, title })) },
      evidence_cards: [{ evidence_id: "card", review_status: "accepted", provenance: { document_id: "untitled-record", locator: "p. 7" } }],
      condition_matrix: [] };
    await page.locator("#network-bundle-file").setInputFiles({ name: "titles.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(bundle)) });
    const canvas = page.locator("#evidence-network");
    for (const title of titles) {
      const paper = canvas.getByRole("button", { name: title, exact: true });
      await expect(paper.locator("text")).toHaveText([paperKeyphrase(title)]);
      await paper.press("Enter");
      await expect(page.locator("#node-title")).toHaveText(title);
      const fits = await paper.evaluate(node => {
        const text = node.querySelector("text")!.getBoundingClientRect();
        const box = node.querySelector("rect")!.getBoundingClientRect();
        return text.left >= box.left && text.right <= box.right && text.top >= box.top && text.bottom <= box.bottom;
      });
      expect(fits).toBe(true);
    }
    await expect(canvas.getByRole("button", { name: "untitled-record" }).locator("text")).toHaveText(["题名待补"]);
    const search = page.getByRole("searchbox", { name: "搜索节点" });
    for (const query of ["Critical phenomena", paperKeyphrase(titles[0])]) {
      await search.fill(query);
      await expect(canvas.locator(".paper")).toHaveCount(1);
      await expect(page.locator("#node-title")).toHaveText(titles[0]);
    }
    expect(requests).toEqual([]);
  });
}

test("follows a paper's direct relations on the offline map and returns to the same node in overview", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 880 });
  const network: string[] = [];
  page.on("request", request => { if (/^https?:/u.test(request.url())) network.push(request.url()); });
  await page.goto(pathToFileURL(resolve("..", "web/network.html")).href);
  const canvas = page.getByRole("group", { name: "条件感知证据关系网络" });
  const toggle = page.getByRole("button", { name: "直接关系", exact: true });
  const index = page.getByRole("navigation", { name: "图内直接关系" });
  await canvas.getByRole("button", { name: "Synthetic strain study" }).press("Enter");
  await expect(index.getByRole("button")).toHaveCount(2);
  await toggle.press("Space");
  await expect(canvas.getByRole("button")).toHaveCount(3);
  await expect(canvas.locator(".graph-edge")).toHaveCount(2);
  await expect(canvas.getByRole("button", { name: "oxygen vacancy" })).toHaveCount(0);
  await index.getByRole("button", { name: /证据出处.*evidence_demo_001/ }).press("Enter");
  await expect(page.locator("#node-title")).toHaveText("evidence_demo_001");
  await expect(page.locator("#node-title")).toBeFocused();
  await expect(canvas.getByRole("button", { pressed: true })).toHaveAttribute("aria-label", "evidence_demo_001");
  await expect(index.getByRole("button", { name: /审核支持.*压缩应变/ })).toBeVisible();
  await page.setViewportSize({ width: 1366, height: 880 });
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await toggle.click();
  await expect(canvas.getByRole("button")).toHaveCount(5);
  await expect(canvas.getByRole("button", { pressed: true })).toHaveAttribute("aria-label", "evidence_demo_001");
  const search = page.getByRole("searchbox", { name: "搜索节点" });
  await search.fill("Synthetic strain");
  await expect(canvas.getByRole("button")).toHaveCount(1);
  await toggle.click();
  await expect(canvas.getByRole("button")).toHaveCount(3);
  await index.getByRole("button", { name: /证据出处.*evidence_demo_001/ }).click();
  await toggle.click();
  await expect(search).toHaveValue("Synthetic strain");
  await expect(canvas.getByRole("button", { pressed: true })).toHaveAttribute("aria-label", "Synthetic strain study");
  expect(network).toEqual([]);
});

test("searches the offline literature map and keeps its inspector on a visible match", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 880 });
  const network: string[] = [];
  page.on("request", request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
  await page.goto(pathToFileURL(resolve("..", "web/network.html")).href);
  const canvas = page.getByRole("group", { name: "条件感知证据关系网络" });
  const search = page.getByRole("searchbox", { name: "搜索节点" });
  const heading = page.locator("#node-title");
  await page.getByLabel("节点类别").selectOption("paper");
  await expect(heading).toHaveText("Synthetic strain study");
  await canvas.getByRole("button", { name: "Synthetic strain study" }).press("Enter");
  await expect(canvas.getByRole("button", { pressed: true })).toHaveAttribute("aria-label", "Synthetic strain study");
  await search.fill("doc_demo");
  await expect(heading).toHaveText("Synthetic strain study");
  await search.fill("no matching DOI");
  await expect(heading).toHaveText("没有匹配节点");
  await expect(canvas.getByRole("button")).toHaveCount(0);
  await search.fill("");
  const guide = Array.from({ length: 12 }, (_, index) => ({ title: "Paper " + index, document_id: "doc" + index }));
  const fixture = { schema_version: "1.0", mission: { material: "Test" }, research_guide: { items: guide },
    evidence_cards: [{ evidence_id: "e", review_status: "accepted", provenance: { document_id: "outside-guide", locator: "p. 4" } }],
    condition_matrix: [] };
  await page.locator("#network-bundle-file").setInputFiles({
    name: "offline.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(fixture)),
  });
  await search.fill("outside-guide");
  const paper = canvas.getByRole("button", { name: "outside-guide" });
  await expect(paper).toHaveAttribute("aria-pressed", "true");
  const cx = Number(await paper.locator("circle").getAttribute("cx"));
  expect(cx).toBeGreaterThan(35);
  expect(cx).toBeLessThan(965);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(network).toEqual([]);
});
