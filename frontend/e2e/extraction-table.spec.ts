import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

for (const width of [320, 1280]) {
  test(`compares papers, exports matching rows and follows a verified source at ${width}px`, async ({ page, context }) => {
    // Both the map and the newly opened reader boot their own workbench.
    test.setTimeout(90_000);
    await page.setViewportSize({ width, height: 860 });
    const run = "extraction_fixture";
    const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
    const claim = "Fixture film A has a longitudinal response.";
    const locator = "Fig. 5b";
    bundle.evidence_cards = [{ evidence_id: "e1", claim, quote: "Fixture source excerpt", review_status: "accepted",
      stance: "support", conditions: { temperature_K: 300 }, provenance: { document_id: "film-a", locator, source: "fixture", access_policy: "authorized" } }];
    bundle.literature_graph = { trust_status: "human_reviewed_graph_projection",
      nodes: [{ node_id: "paper:film-a", kind: "candidate_paper", label: "Film A", trust_status: "candidate_metadata_not_scientific_evidence" },
        { node_id: "paper:film-b", kind: "candidate_paper", label: "Film B", trust_status: "candidate_metadata_not_scientific_evidence" },
        { node_id: "evidence:e1", kind: "evidence_card", label: claim, trust_status: "accepted" }],
      edges: [{ source_id: "paper:film-a", target_id: "evidence:e1", edge_type: "source_provenance", relation_source: "reviewed source map", trust_status: "accepted" }] };
    const measurement = { document_id: "film-a", title: "Film A", doi: "10.1000/a", status: "reviewed", evidence_id: "e1",
      material: "BiFeO₃", property_name: "d33", claim, stance: "support", conditions: { temperature_K: 300 },
      reported_facts: [{ fact_id: "f1", name: "d33", value: 38, unit: "pm/V", qualifiers: { direction: "z" } }],
      locator, document_version: "published", source: "fixture", reader_available: true };
    const gap = { document_id: "film-b", title: "Film B", doi: null, status: "awaiting_extraction", evidence_id: null,
      material: null, property_name: null, claim: null, stance: null, conditions: {}, reported_facts: [],
      locator: null, document_version: null, source: null, reader_available: false };
    const extraction = { schema_version: "cosmatter.extraction-table/v1", run_id: run, screening_status: "current",
      summary: { document_count: 2, reviewed_count: 1, gap_count: 1 }, rows: [measurement, gap] };
    let current = extraction;
    let reads = 0;
    const mutations: string[] = [];
    await context.route("**/api/**", async route => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() !== "GET") mutations.push(route.request().method() + " " + path);
      if (path === `/api/runs/${run}/extraction-table`) {
        reads++;
        return reads === 1 ? route.fulfill({ status: 503 }) : route.fulfill({ json: current });
      }
      if (path === `/api/runs/${run}/ui`) return route.fulfill({ json: bundle });
      if (path === `/api/runs/${run}/status`) return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      if (path === `/api/runs/${run}/stage-contract`) return route.fulfill({ json: stageContractFixture(run, bundle.mission.mission_id, "extraction") });
      return route.fulfill({ status: 404 });
    });
    await page.goto(`/?api=local#run=${run}&document=film-a`);
    const open = page.getByRole("button", { name: "跨文献证据对照", exact: true });
    await expect(open).toBeVisible({ timeout: 30_000 });
    expect(reads).toBe(0);
    await open.click();
    const panel = page.getByRole("region", { name: "跨文献证据对照表" });
    await expect(panel.getByRole("alert")).toBeVisible();
    await panel.getByRole("button", { name: "刷新对照表" }).click();
    await expect(panel.getByRole("table")).toContainText("Film B");
    await expect(panel.getByRole("table")).toContainText("38 pm/V");
    await panel.getByLabel("审核状态").selectOption("awaiting_extraction");
    await expect(panel.getByRole("table")).not.toContainText("Film A");
    await expect(panel.getByRole("link")).toHaveCount(0);
    const gapDownload = page.waitForEvent("download");
    await panel.getByRole("button", { name: "导出 Orca 核验任务" }).click();
    const downloadedGap = await gapDownload;
    expect(downloadedGap.suggestedFilename()).toBe(run + "-orca-tasks.json");
    const gapTasks = JSON.parse(await readFile((await downloadedGap.path())!, "utf8"));
    expect(gapTasks.schema_version).toBe("cosmatter.orca-tasks/v1");
    expect(gapTasks.tasks).toHaveLength(1);
    expect(gapTasks.tasks[0].task_title).toBe("Verify paper [film-b]");
    expect(gapTasks.tasks[0].spec).toContain("Keep this gap open");
    expect(gapTasks.tasks[0].spec).not.toContain("film-a");
    expect(mutations).toEqual([]);
    await panel.getByRole("button", { name: "清除对照筛选" }).click();
    await panel.getByRole("searchbox").fill("d33 300");
    await expect(panel.getByRole("table")).not.toContainText("Film B");
    const downloadEvent = page.waitForEvent("download");
    await panel.getByRole("button", { name: "导出匹配行 CSV" }).click();
    const download = await downloadEvent;
    expect(download.suggestedFilename()).toBe(run + "-extraction.csv");
    const csv = await readFile((await download.path())!, "utf8");
    expect(csv).toContain('"film-a"');
    expect(csv).not.toContain('"film-b"');
    const popup = page.waitForEvent("popup");
    await panel.getByRole("link", { name: /在新标签页核对/ }).click();
    const reader = await popup;
    await expect(reader.locator(".source-reader blockquote")).toHaveText("Fixture source excerpt", { timeout: 30_000 });
    await expect(panel.getByRole("searchbox")).toHaveValue("d33 300");
    expect(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    const en = page.getByRole("button", { name: "EN", exact: true }).first();
    await en.click();
    const english = page.getByRole("region", { name: "Cross-paper evidence table" });
    await expect(english).toContainText("Source verified");
    if (width === 1280) {
      await english.getByLabel("Measured property").selectOption("d33");
      // All measurements change on refresh. Keep the user's selection explicit until they clear it.
      current = { ...extraction, summary: { document_count: 1, reviewed_count: 22, gap_count: 0 },
        rows: Array.from({ length: 22 }, (_, i) => ({ ...measurement, evidence_id: `temperature-${i + 1}`,
          property_name: "temperature", claim: `Measurement ${i + 1}` })) };
      await english.getByRole("button", { name: "Refresh table" }).click();
      await expect(english.getByLabel("Measured property")).toHaveValue("d33");
      await expect(english).toContainText("no current records");
      await expect(english.getByRole("button", { name: "Export matching rows as CSV" })).toBeDisabled();
      const orca = english.getByRole("button", { name: "Export Orca verification tasks" });
      await expect(orca).toBeDisabled();
      await english.getByRole("button", { name: "Clear table filters" }).click();
      await expect(english.locator("tbody tr")).toHaveCount(20);
      await english.getByRole("button", { name: "Next", exact: true }).press("Enter");
      await expect(english.locator("tbody tr")).toHaveCount(2);
      const nextDownload = page.waitForEvent("download");
      await english.getByRole("button", { name: "Export matching rows as CSV" }).click();
      const all = await readFile((await (await nextDownload).path())!, "utf8");
      expect(all).toContain('"temperature-1"');
      expect(all).toContain('"temperature-22"');
      const taskDownload = page.waitForEvent("download");
      await orca.click();
      const exported = JSON.parse(await readFile((await (await taskDownload).path())!, "utf8"));
      expect(exported.tasks).toHaveLength(1);
      const target = JSON.parse(exported.tasks[0].spec.split("\n").at(-1));
      expect(target.document_id).toBe("film-a");
      expect(target.evidence).toHaveLength(22);
      expect(target.evidence[0].evidence_id).toBe("temperature-1");
      expect(target.evidence[21].evidence_id).toBe("temperature-22");
      expect(mutations).toEqual([]);
      current = { ...extraction, rows: [], summary: { document_count: 0, reviewed_count: 0, gap_count: 0 } };
      await english.getByRole("button", { name: "Refresh table" }).click();
      await expect(english).toContainText("No included papers");
      await expect(orca).toBeDisabled();
      current = extraction;
      await page.getByRole("group", { name: "Literature view" }).getByRole("button", { name: "Literature map" }).click();
      await page.getByRole("button", { name: "Compare paper evidence" }).press("Enter");
      await expect(english.locator("tbody tr")).toHaveCount(2);
      await expect(english).toContainText("Film B");
    }
  });
}
