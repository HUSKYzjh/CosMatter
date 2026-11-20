import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

test("jumping between bridge sections preserves a DSH run through reload", async ({ page }) => {
  const runId = "run_bridge_navigation";
  const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
  const statusPath = `/api/runs/${runId}/status`;
  const writes: string[] = [];
  let statusReads = 0;
  let hasPdf = false;
  let screening = false;
  await page.route("**/api/**", route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") writes.push(path);
    if (path === statusPath) {
      statusReads++;
      return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    }
    if (path === `/api/runs/${runId}/ui`) return route.fulfill({ json: bundle });
    if (screening && path === `/api/runs/${runId}/stage-contract`) {
      return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "screening") });
    }
    if (path === `/api/runs/${runId}/pdf/tasks/cached`) return route.fulfill({ json: {
      run_id: runId, trust_status: "private_pdf_task_registry_metadata_only", tasks: hasPdf ? [{
        document_id: "pdf_0123456789abcdef01234567", candidate_document_id: null,
        audit_document_id: "pdf_0123456789abcdef01234567",
        file_name: "transition.pdf", state: "running", audit_state: "running",
        doi: null, doi_status: "pending", markdown_ready: false, source_map_review_status: "absent",
        source_map_segment_count: 0, error: null, trust_status: "private_markdown_outside_run_not_scientific_evidence",
      }] : [],
    } });
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto(`/?api=local#run=${runId}`);
  const nav = page.getByRole("navigation", { name: "舰桥快速导航" });
  await expect(nav).toBeVisible({ timeout: 20_000 });
  const originalUrl = page.url();
  const historyLength = await page.evaluate(() => history.length);
  const pdf = nav.getByRole("button", { name: /私有全文/ });
  for (const width of [1360, 320]) {
    await page.setViewportSize({ width, height: 800 });
    for (const [id, label] of [["bridge-fleet", "舰队编队"], ["bridge-flight", "任务航线"], ["bridge-next", "下一门禁"]]) {
      await nav.getByText(new RegExp(label)).click();
      await expect(page).toHaveURL(originalUrl);
      const section = page.locator(`#${id}`);
      await expect(section).toBeFocused();
      await expect(section).toBeInViewport();
      const [target, bar] = await Promise.all([section.boundingBox(), nav.boundingBox()]);
      expect(target!.y).toBeGreaterThanOrEqual(Math.min(bar!.y + bar!.height, 800));
      expect(target!.y).toBeLessThan(800);
    }
    await expect(pdf).toBeDisabled();
  }
  expect(await page.evaluate(() => history.length)).toBe(historyLength);
  const readsBeforeReload = statusReads;
  hasPdf = true;
  await page.reload();
  await expect(page.locator(".rail-run-id code")).toHaveText(runId);
  await expect(pdf).toBeEnabled();
  await pdf.press("Enter");
  const privateReview = page.locator("#bridge-private-review");
  await expect(privateReview).toBeFocused();
  await expect(privateReview).toContainText("transition.pdf");
  await expect(page).toHaveURL(originalUrl);
  expect(statusReads).toBeGreaterThan(readsBeforeReload);

  // Returning from a different paper keeps its identity and offers the lone PDF for explicit selection.
  screening = true;
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", nodes: [{
    node_id: "paper:other", kind: "candidate_paper", label: "Different paper", trust_status: "candidate_metadata_not_scientific_evidence",
  }], edges: [] };
  const paperUrl = originalUrl + "&document=other";
  await page.goto(paperUrl);
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/);
  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await pdf.press("Enter");
  const picker = privateReview.getByRole("combobox");
  await expect(picker).toHaveValue("");
  await expect(privateReview.locator(".pdf-task-progress")).toHaveCount(0);
  await picker.selectOption("pdf_0123456789abcdef01234567");
  await expect(privateReview.locator(".pdf-task-progress")).toContainText("transition.pdf");
  await expect(picker).toHaveValue("pdf_0123456789abcdef01234567");
  await expect(page).toHaveURL(paperUrl);
  expect(writes).toEqual([]);
});
