import { expect, test, type Page } from "@playwright/test";
import { resolve } from "node:path";
import { stageContractFixture } from "../src/stageContractFixture";

const routeDiagnosticsExport = resolve(process.cwd(), "..", "examples", "ui-demo", "route_diagnostics.json");
const workspaceLoad = { timeout: 15_000 };
const lazyWorkspaceContentLoad = { timeout: 30_000 };
const operationContracts = {
  schema_version: "cosmatter.operation-parameter-contracts/v1",
  trust_status: "static_parameter_contracts_not_execution_authorization",
  operations: {
    sciverse_read_content: {
      type: "object",
      additionalProperties: false,
      required: ["offset", "limit"],
      properties: {
        offset: { type: "integer", minimum: 0, default: 0 },
        limit: { type: "integer", minimum: 200, maximum: 4000, default: 2000 },
      },
    },
  },
};
const dshProfileSnapshot = {
  schema_version: "cosmatter.dsh-profile-status/v2",
  profile_name: "tui",
  installation_state: "installed",
  expected_bundle_count: 7,
  declared_bundle_count: 7,
  installed_bundle_count: 7,
  packages: ["mission", "observability", "policy", "research", "review", "document", "graph"].map((name) => ({ package: `@cosmatter/dsh-${name}-plugin`, install_status: "verified", dependency_kind: "local_link" })),
  composition_status: "not_checked_by_http_api",
  trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution",
};

async function openEditableTaskDefinition(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await page.locator("details.mission-api > summary").click();
  return page.locator(".import-control input[type=file]");
}

async function openMissionDefinitionWithPendingArtifacts(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
}

async function tinyInteractiveLabels(page: Page) {
  return page.locator("button, button *, a, a *, summary, summary *").evaluateAll((elements) => elements.flatMap((element) => {
    const node = element as HTMLElement;
    const style = getComputedStyle(node);
    const box = node.getBoundingClientRect();
    const text = (node.textContent ?? "").replace(/\s+/g, " ").trim();
    if (!text || box.width <= 0 || box.height <= 0 || style.visibility !== "visible" || style.display === "none") return [];
    const size = Number.parseFloat(style.fontSize);
    if (!Number.isFinite(size) || size >= 12) return [];
    return [{ tag: node.tagName.toLowerCase(), className: node.className, text: text.slice(0, 72), size }];
  }).slice(0, 30));
}

test("keeps visible interactive labels at twelve pixels or larger", async ({ page }) => {
  for (const width of [1366, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(await tinyInteractiveLabels(page)).toEqual([]);
    await page.getByRole("button", { name: "预览：受控编排" }).click();
    await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
    expect(await tinyInteractiveLabels(page)).toEqual([]);
  }
});

test("keeps the narrow launch workspace horizontally contained", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const workspace = page.locator(".launch-workspace");
  await expect(workspace).toBeVisible();
  if (process.platform === "win32") {
    // Warm the installed Edge rasterizer once, then compare one deterministic
    // frame. `toHaveScreenshot` requires two identical consecutive captures;
    // Windows can alternate one font-antialiasing frame even when the final
    // capture is byte-identical to the committed baseline.
    await workspace.screenshot({ animations: "disabled" });
    expect(await workspace.screenshot({ animations: "disabled" })).toMatchSnapshot("launch-workspace-narrow.png");
  } else {
    const box = await workspace.boundingBox();
    if (!box) throw new Error("launch workspace did not render a layout box");
    expect(Math.ceil(box.x + box.width)).toBeLessThanOrEqual(390);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("keeps launch regions separate across structural breakpoints", async ({ page }) => {
  const separated = async (first: string, second: string) => {
    const [a, b] = await Promise.all([page.locator(first).boundingBox(), page.locator(second).boundingBox()]);
    if (!a || !b) throw new Error(`missing layout box for ${first} or ${second}`);
    const horizontalGap = Math.max(a.x, b.x) - Math.min(a.x + a.width, b.x + b.width);
    const verticalGap = Math.max(a.y, b.y) - Math.min(a.y + a.height, b.y + b.height);
    expect(Math.max(horizontalGap, verticalGap)).toBeGreaterThanOrEqual(0);
  };

  for (const width of [1440, 1040, 880, 560, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await separated(".launch-controls", ".launch-briefing");
    await separated(".launch-briefing", ".launch-stage-column");
    await separated(".launch-hero", ".launch-workspace");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
});

test("centres the wide launch route and keeps its primary sections aligned", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const boxes = await Promise.all([
    page.locator(".launch-hero").boundingBox(),
    page.locator(".launch-workspace").boundingBox(),
    page.locator(".launch-flow").boundingBox(),
    page.locator(".signal-receiver").boundingBox(),
  ]);
  if (boxes.some((box) => !box)) throw new Error("wide launch sections did not render layout boxes");
  const [hero, workspace, flow, receiver] = boxes as Array<{ x: number; y: number; width: number; height: number }>;
  expect(Math.abs(hero.x - (1920 - hero.width) / 2)).toBeLessThanOrEqual(1);
  expect(Math.abs(hero.x - workspace.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(workspace.x - flow.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(workspace.width - receiver.width)).toBeLessThanOrEqual(1);
});

test("renders BFO templates as readable cards without a line crossing their copy", async ({ page }) => {
  for (const width of [1440, 880, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const deck = page.locator(".bfo-task-deck");
    const first = deck.getByRole("button").first();
    await expect(first).toBeVisible();
    expect(await deck.locator(":scope > div").evaluate((element) => getComputedStyle(element, "::before").display)).toBe("none");
    expect(await first.locator("strong").evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(13);
    expect(await first.locator("span").evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(11);
    expect(await first.evaluate((element) => element.scrollWidth <= element.clientWidth && element.scrollHeight <= element.clientHeight)).toBe(true);
  }
});

test("moves the research rail above the workspace before it crowds operational cards", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const columns = await page.locator(".workbench").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/));
  expect(columns).toHaveLength(1);
  const [rail, stage] = await Promise.all([page.locator(".research-rail").boundingBox(), page.locator(".workflow-stage").boundingBox()]);
  if (!rail || !stage) throw new Error("research rail or workflow stage did not render a layout box");
  expect(rail.y + rail.height).toBeLessThanOrEqual(stage.y + 1);
  await expect(page.locator(".rail-context")).not.toHaveAttribute("open", "");
  expect(await page.locator(".deployment-flagship").evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
});

test("keeps operational labels and evidence copy at a readable scale", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const fontPixels = (selector: string) => page.locator(selector).first().evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize));
  const expectReadableMetadata = async (selectors: string[]) => {
    for (const selector of selectors) {
      await expect(page.locator(selector).first()).toBeVisible(lazyWorkspaceContentLoad);
      expect(await fontPixels(selector), selector).toBeGreaterThanOrEqual(12);
    }
  };
  expect(await fontPixels(".launch-modes button span")).toBeGreaterThanOrEqual(15);
  expect(await fontPixels(".launch-modes button small")).toBeGreaterThanOrEqual(12);
  expect(await fontPixels(".launch-stage-copy strong")).toBeGreaterThanOrEqual(14);
  expect(await fontPixels(".launch-stage-copy small")).toBeGreaterThanOrEqual(12);
  await expectReadableMetadata([".launch-modes button b", ".bfo-task-deck > header small", ".bfo-task-deck button > small", ".bfo-task-deck button em"]);

  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  expect(await fontPixels(".workflow-artifact-flow h2")).toBeGreaterThanOrEqual(20);
  expect(await fontPixels(".workflow-artifact-flow p")).toBeGreaterThanOrEqual(15);
  expect(await fontPixels(".journey-track button small")).toBeGreaterThanOrEqual(12);
  await page.setViewportSize({ width: 390, height: 900 });
  await expectReadableMetadata([
    ".journey-track button span",
    ".rail-context > summary small",
    ".workflow-artifact-flow article > small",
    ".mission-event-ledger > header small",
    ".fleet-deployment-radar > header small",
    ".fleet-handoff-manifest > header small",
    ".stage-note",
  ]);
  const [deploymentPlane, firstShip] = await Promise.all([
    page.locator(".deployment-plane").boundingBox(),
    page.locator(".deployment-ship").first().boundingBox(),
  ]);
  if (!deploymentPlane || !firstShip) throw new Error("mobile deployment station did not render a layout box");
  expect(firstShip.width).toBeGreaterThanOrEqual(deploymentPlane.width * 0.9);
  expect(await page.locator(".deployment-ship").first().evaluate((element) => element.scrollWidth <= element.clientWidth && element.scrollHeight <= element.clientHeight)).toBe(true);

  await page.getByRole("button", { name: /^05 研究拓展/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-horizon/, workspaceLoad);
  await expectReadableMetadata([
    ".evidence-maturity-panel > header small",
    ".simulation-campaign-panel > header small",
    ".expansion-gate small",
    ".expansion-gate > .cm-action",
    ".stage-note",
  ]);
  await expect(page.locator(".expansion-gate > .cm-action")).toHaveClass(/cm-action--secondary/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("shows the DSH contract bridge without presenting catalogue discovery as execution", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("**/api/status", async (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      api_mode: "loopback_only",
      providers: { deepseek: false, sciverse: false, mineru: false, openalex: false, crossref: false, crossref_polite_contact: false },
      operation_contracts: operationContracts,
    }),
  }));
  await page.route("**/api/plugins", async (route) => {
    if (!route.request().url().endsWith("/api/plugins")) return route.fallback();
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        catalogue_api_version: "2.0",
        trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance",
        plugins: [{
          plugin_id: "literature.metadata_retrieval",
          title: "书目元数据检索",
          domain: "retrieval",
          entrypoint: "cosmatter.metadata_search:MetadataSearch",
          api_version: "2.0",
          capabilities: ["metadata_search"],
          data_classification: "public_metadata",
          automation_class: "external_authorized",
          required_authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"],
          requires_human_review: false,
          contract: { input_schema: "cosmatter.plugin-input/v1", output_schema: "cosmatter.plugin-output/v1", execution_mode: "provider_request", lifecycle: "authorize -> dispatch -> receipt" },
          execution_boundary: "Descriptor only; catalogue discovery grants no execution authority.",
        }],
      }),
    });
  });
  await page.route("**/api/dsh-profile", async (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify(dshProfileSnapshot),
  }));
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  const deck = page.locator(".harness-capability-deck");
  await expect(deck).toHaveClass(/state-ready/, workspaceLoad);
  await expect(deck).toContainText("本机目录已连接");
  await expect(deck.locator(".harness-installation-card")).toContainText("已验证 7/7");
  await expect(deck.locator(".harness-installation-card")).toContainText("已声明 7 个依赖");
  await expect(deck).toContainText("尚无派发回执");
  await expect(deck).toContainText("任何一层都不能代替工具结果");
  const activationTrack = deck.locator(".harness-activation-track");
  await expect(activationTrack).toContainText("安装文件");
  await expect(activationTrack).toContainText("已验证 7/7");
  await expect(activationTrack).toContainText("配置组合待核验");
  await expect(activationTrack).toContainText("隔离注册");
  await expect(activationTrack).toContainText("工具注册待核验");
  await expect(activationTrack).toContainText("契约目录已连接");
  await expect(activationTrack).toContainText("派发回执");
  await expect(activationTrack).toContainText("尚无执行回执");
  const activationVerdict = deck.locator(".harness-activation-verdict");
  await expect(activationVerdict).toHaveClass(/state-partial/);
  await expect(activationVerdict).toContainText("安装与契约已就绪，工具注册待核验");
  await expect(activationVerdict).toContainText("任务派发结果见本次运行回执");
  await expect(deck.locator(".harness-capability-metrics strong").first()).toHaveText("1");
  const packageProof = deck.locator(".harness-package-proof");
  await expect(packageProof.locator("summary")).toContainText("查看逐包检查结果");
  await expect(packageProof.locator("summary strong")).toHaveText("7/7");
  await expect(packageProof.locator("ul")).not.toBeVisible();
  await packageProof.locator("summary").click();
  await expect(packageProof.locator("li")).toHaveCount(7);
  await expect(packageProof).toContainText("任务建立");
  await expect(packageProof).toContainText("@cosmatter/dsh-mission-plugin");
  await expect(packageProof).toContainText("本地链接");
  await expect(packageProof.locator(".harness-package-state b").first()).toHaveText("已验证");
  if (process.platform === "win32") {
    await deck.screenshot({ animations: "disabled" });
    expect(await deck.screenshot({ animations: "disabled" })).toMatchSnapshot("dsh-profile-proof.png");
  }
  await page.setViewportSize({ width: 390, height: 900 });
  const minimumReadableSize = await deck.locator(".cm-status-badge, .harness-state-ledger p").evaluateAll((elements) => elements.every((element) => Number.parseFloat(getComputedStyle(element).fontSize) >= 11));
  expect(minimumReadableSize).toBe(true);
  expect(await activationTrack.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(2);
  expect(await activationVerdict.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(1);
  expect(await packageProof.locator("ul").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(1);
  const tools = deck.locator(".dsh-tool-catalogue");
  await tools.locator(":scope > summary").press("Enter");
  await expect(tools.getByRole("status")).toHaveText("显示 20/20 个工具");
  const search = tools.getByRole("searchbox", { name: "搜索工具或插件包" });
  const filter = tools.getByLabel("授权类型");
  await filter.selectOption("external");
  await expect(tools.getByRole("status")).toHaveText("显示 4/20 个工具");
  await search.fill("书目查询");
  const matching = tools.locator(".dsh-tool-item");
  await expect(matching).toHaveCount(1);
  await matching.locator("summary").press("Enter");
  await expect(matching).toContainText("metadata_provider_consent");
  await expect(matching).toContainText("安装文件已验证，待核验组合");
  await matching.getByRole("button", { name: "复制工具名" }).click();
  await expect(matching.getByRole("status")).toHaveText("工具名已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("cosmatter_research_query_execute");
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", {
    value: () => Promise.reject(new DOMException("Clipboard access denied", "NotAllowedError")),
  }));
  await matching.getByRole("button", { name: "复制工具名" }).click();
  await expect(matching.locator(".dsh-tool-manual-copy")).toHaveText("cosmatter_research_query_execute");
  expect(await deck.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await search.fill("nonexistent");
  await expect(tools.getByRole("status")).toHaveText("显示 0/20 个工具");
  await tools.getByRole("button", { name: "清除筛选" }).click();
  await expect(tools.getByRole("status")).toHaveText("显示 20/20 个工具");
  await expect(tools.getByRole("button", { name: "只看本阶段" })).toHaveCount(0);
  const stage = tools.getByLabel("研究阶段");
  await stage.selectOption("parse");
  await expect(tools.getByRole("status")).toHaveText("显示 4/20 个工具");
  await filter.selectOption("external");
  await expect(tools.getByRole("status")).toHaveText("显示 2/20 个工具");
  await expect(tools.locator(".dsh-tool-item > summary code")).toHaveText(["cosmatter_mineru_source_submit", "cosmatter_mineru_task_poll"]);
  await stage.selectOption("report");
  await expect(tools.getByRole("status")).toHaveText("显示 0/20 个工具");
  await expect(tools.locator(".dsh-stage-note")).toContainText("在工作台审核报告");
  await filter.selectOption("read");
  await expect(tools.locator(".dsh-tool-item > summary code")).toHaveText(["cosmatter_stage_contract", "cosmatter_artifact_manifest"]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("rechecks a missing DSH bundle while the catalogue is unavailable", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("**/api/status", async (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      api_mode: "loopback_only",
      providers: { deepseek: false, sciverse: false, mineru: false, openalex: false, crossref: false, crossref_polite_contact: false },
      operation_contracts: operationContracts,
    }),
  }));
  await page.route("**/api/plugins", async (route) => route.fulfill({ status: 503, body: "catalogue unavailable" }));
  let repaired = false;
  let filesChanged = false;
  let finishCheck: () => void = () => {};
  const checkInProgress = new Promise<void>((resolve) => { finishCheck = resolve; });
  await page.route("**/api/dsh-profile", async (route) => {
    if (repaired) await checkInProgress;
    return route.fulfill({ json: repaired ? {
      ...dshProfileSnapshot,
      composition_check: {
        schema_version: "cosmatter.dsh-composition-check/v1",
        checked_at: "2026-11-18T03:00:00Z",
        dsh_version: "0.2.2-rc.3",
        bundles: dshProfileSnapshot.packages.map(({ package: name }) => name),
        matches_local_files: !filesChanged,
      },
      tool_registry_check: {
        schema_version: "cosmatter.dsh-tool-registry-check/v1",
        checked_at: "2026-11-18T03:00:00Z",
        dsh_version: "0.2.2-rc.3",
        bundles: dshProfileSnapshot.packages.slice(0, 2).map(({ package: name }) => name),
        matches_local_files: !filesChanged,
        registered_tools: ["cosmatter_workflow_status"],
      },
    } : {
      ...dshProfileSnapshot,
      installed_bundle_count: 6,
      installation_state: "partial",
      packages: [{ ...dshProfileSnapshot.packages[0], install_status: "missing_bundle" }, ...dshProfileSnapshot.packages.slice(1)],
    } });
  });
  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();

  const deck = page.locator(".harness-capability-deck");
  await expect(deck).toHaveClass(/state-unavailable/, workspaceLoad);
  await expect(deck).toContainText("目录不可用");
  const installationCard = deck.locator(".harness-installation-card");
  await expect(installationCard).toContainText("已验证 6/7");
  await expect(installationCard).toContainText("已声明 7 个依赖");
  await expect(deck).toContainText("目录、profile 依赖快照与运行回执独立检查");
  const packageProof = deck.locator(".harness-package-proof");
  await packageProof.locator("summary").press("Enter");
  await expect(packageProof.locator("li").first()).toContainText("文件缺失");
  const composition = deck.getByRole("region", { name: "DSH 终端核验" });
  await composition.getByRole("button", { name: "复制核验命令" }).click();
  await expect(composition.getByRole("status")).toHaveText("已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("cosmatter check-dsh-profile --verify-tools");

  repaired = true;
  await composition.getByRole("button", { name: "刷新核验结果" }).click();
  try {
    const busy = composition.getByRole("button", { name: "正在读取…" });
    await expect(busy).toHaveAttribute("aria-busy", "true");
    await expect(busy).toBeDisabled();
  } finally {
    finishCheck();
  }
  await expect(installationCard).toContainText("已验证 7/7");
  await expect(packageProof.locator("li").first().locator(".harness-package-state b")).toHaveText("已验证");
  await expect(deck.locator(".harness-activation-track")).toContainText("上次组合 7/7");
  await expect(composition).toContainText("已注册 1/20");
  await expect(packageProof.locator("li").first()).toContainText("注册 0/1");
  const tools = deck.locator(".dsh-tool-catalogue");
  await tools.locator(":scope > summary").press("Enter");
  await expect(tools.getByText("隔离核验已注册", { exact: true })).toHaveCount(1);
  await expect(tools.getByText("隔离核验未注册", { exact: true })).toHaveCount(6);
  filesChanged = true;
  await composition.getByRole("button", { name: "刷新核验结果" }).click();
  await expect(composition).toContainText("工具核验已过期");
  await expect(tools.locator(".dsh-tool-registration")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("wraps narrow rail handoffs and manifest counts without collisions", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const railVector = page.locator(".research-rail .route-handoff-vector");
  expect(await railVector.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(1);
  for (const selector of [".route-handoff-origin", ".route-handoff-destination"]) {
    const station = page.locator(`.research-rail ${selector}`);
    expect(await station.locator("strong").evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await station.locator("span").evaluate((element) => element.scrollHeight <= element.clientHeight)).toBe(true);
  }

  const manifestEntry = page.locator(".handoff-manifest-entry").first();
  await expect(manifestEntry).toBeVisible(lazyWorkspaceContentLoad);
  const count = manifestEntry.locator(":scope > small");
  const [entryBox, countBox] = await Promise.all([manifestEntry.boundingBox(), count.boundingBox()]);
  if (!entryBox || !countBox) throw new Error("manifest entry or artifact count did not render a layout box");
  expect(countBox.width).toBeGreaterThan(entryBox.width * 0.45);
  expect(await count.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
});

test("turns a typed question into an explicit selectable and confirmable mission path", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByLabel("候选航向研究问题").fill("围绕该研究议题，现有文献的研究对象、报告结论与证据边界分别是什么？");

  const handoff = page.locator(".candidate-handoff");
  await expect(handoff).toContainText("候选已生成；请选择一条航向", { timeout: 4_000 });
  const firstRoute = page.getByRole("button", { name: /全景梳理 点击选择此航向/ });
  await expect(firstRoute).toHaveAttribute("aria-pressed", "false");

  await firstRoute.click();
  await expect(handoff).toContainText("已选择候选航向；请在下方核对并编辑任务边界");
  await expect(page.getByRole("region", { name: "下一步 / 任务简报与可编辑边界" })).toBeVisible();
  const confirm = page.getByRole("button", { name: "确认任务并进入编排" });
  await expect(confirm).toBeDisabled();
  await expect(confirm).toHaveClass(/cm-action--primary/);
  await expect(confirm).toHaveClass(/cm-action--lg/);

  await page.getByLabel("研究对象").fill("BiFeO₃ 外延薄膜");
  await expect(confirm).toBeDisabled();
  await page.getByLabel("任务简报研究问题").fill("BiFeO₃ 外延薄膜的相稳定性在不同应变条件下如何变化？");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.locator(".session-handoff > .cm-action")).toHaveClass(/cm-action--sm/);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await expect(page.locator(".mission-definition-actions .cm-action")).toHaveClass(/cm-action--primary/);
  await expect(page.locator(".mission-definition-actions .cm-action")).toHaveClass(/cm-action--lg/);
});

test("keeps fallback routes tied to the entered material property instead of generic boilerplate", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const input = "BiFeO3的相转变温度是";
  await page.getByLabel("候选航向研究问题").fill(input);

  const routes = page.locator(".candidate-planet");
  await expect(routes).toHaveCount(3, { timeout: 4_000 });
  await expect(routes.nth(0)).toContainText("BiFeO₃");
  await expect(routes.nth(0)).toContainText("转变温区");
  await expect(routes.nth(1)).toContainText("体相、陶瓷与薄膜");
  await expect(routes.nth(2)).toContainText("材料分解与测量伪影");
  expect(await routes.nth(0).locator("strong").evaluate((element) => element.scrollHeight <= element.clientHeight)).toBe(true);
  await expect(page.getByRole("status", { name: "候选生成来源" })).toContainText("本地问题绑定回退");
  await expect(page.getByRole("status", { name: "候选生成来源" })).toContainText("未连接本机候选生成 API");
  const visibleRoutes = (await routes.allTextContents()).join(" ");
  expect(visibleRoutes).not.toContain("围绕该研究议题");
  expect(visibleRoutes).not.toContain("需要优先核对哪些可定位的原文证据");

  await routes.nth(0).click();
  await expect(page.getByLabel("研究对象")).toHaveValue("BiFeO₃");
  await expect(page.getByLabel("研究目标")).toHaveValue("相转变温度");
  await expect(page.getByRole("button", { name: "确认任务并进入编排" })).toBeEnabled();
});

test("loads an explicitly server-selected UI bundle as a read-only literature map", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.route("**/ui.json", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      schema_version: "1.0",
      generated_at: "2026-09-05T00:00:00Z",
      mission: { mission_id: "mission_server_preview", question: "BiFeO3 的相变温度是多少？", material: "BiFeO3", property_name: "相变温度", scope: "按样品状态与测量条件比较" },
      literature_graph: {
        trust_status: "metadata_only_navigation_not_scientific_evidence",
        nodes: [{ node_id: "paper:bfo", kind: "candidate_paper", label: "Phase transitions in BiFeO3", trust_status: "candidate_metadata_not_scientific_evidence", source: "Sciverse" }],
        edges: [],
      },
    }),
  }));

  await page.goto("/?ui=server&api=local", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, lazyWorkspaceContentLoad);
  await expect(page.getByText("只读预览：可查看阶段与空态")).toBeVisible();
  await expect(page.locator(".fleet-reading-cards")).toContainText("Phase transitions in BiFeO3", lazyWorkspaceContentLoad);
  await expect(page.locator(".fleet-reading-cards")).toContainText("任务对象与维度双命中", lazyWorkspaceContentLoad);
  await page.locator(".fleet-reading-cards button").first().click();
  const inspector = page.locator(".evidence-inspector");
  await expect(inspector).toBeVisible();
  expect(await inspector.locator(":scope > small").evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(12);
  expect(await inspector.locator("p").first().evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(13);
  expect(await inspector.locator("dd").evaluateAll((elements) => elements.every((element) => Number.parseFloat(getComputedStyle(element).fontSize) >= 13))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(apiRequests).toEqual([]);
});

test("labels a rejected model result and retries without silently presenting it as DeepSeek output", async ({ page }) => {
  let candidateRequests = 0;
  await page.route("**/api/status", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ api_mode: "loopback_only", providers: { deepseek: true, sciverse: true, mineru: true, openalex: true, crossref: true, crossref_polite_contact: true }, operation_contracts: operationContracts }),
  }));
  await page.route("**/api/question-candidates", async (route) => {
    candidateRequests += 1;
    if (candidateRequests === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: "rejected" }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        trust_status: "untrusted_question_suggestions",
        candidates: [
          { id: "candidate_1", question: "哪些实验文献直接测定 BiFeO3 相转变温度及其不确定度？", material: "BiFeO3", property: "相转变温度", scope: "实验测量与误差", kind: "survey" },
          { id: "candidate_2", question: "哪些样品、气氛和升温条件解释 BiFeO3 相转变温度的文献分歧？", material: "BiFeO3", property: "相转变温度", scope: "可比条件", kind: "contrast" },
          { id: "candidate_3", question: "哪些原位结构观测可区分 BiFeO3 相转变温度附近的竞争相指派？", material: "BiFeO3", property: "相转变温度", scope: "机制判据", kind: "mechanism" },
        ],
      }),
    });
  });

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  const consent = page.getByLabel(/我同意将上述研究问题发送/);
  await expect(consent).toBeVisible();
  await page.getByLabel("候选航向研究问题").fill("BiFeO3的相转变温度是多少？");
  await consent.check();

  const origin = page.getByRole("status", { name: "候选生成来源" });
  await expect(origin).toContainText("本地问题绑定回退", { timeout: 4_000 });
  await expect(origin).toContainText("模型请求失败或输出未通过相关性校验");
  await page.getByRole("button", { name: "重新请求模型" }).click();
  await expect(origin).toContainText("DeepSeek 候选生成 · 已通过问题锚点校验", { timeout: 4_000 });
  await expect(page.locator(".candidate-planet").first()).toContainText("BiFeO3 相转变温度");
  expect(candidateRequests).toBe(2);
});

test("keeps manual API execution explicitly staged and readable on a narrow viewport", async ({ page }) => {
  await page.route("**/api/status", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      api_mode: "loopback_only",
      providers: { deepseek: true, sciverse: false, mineru: false, openalex: false, crossref: false, crossref_polite_contact: false },
      operation_contracts: operationContracts,
    }),
  }));

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await page.locator("details.mission-api > summary").click();

  const actions = page.locator(".mission-api-actions");
  await expect(actions.getByRole("button", { name: "仅更新本地任务边界" })).toHaveClass(/cm-action--quiet/);
  await expect(actions.getByRole("button", { name: "启动受控 API 任务" })).toHaveClass(/cm-action--primary/);
  await expect(page.locator(".mission-api-sequence")).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 900 });
  expect(await actions.getByRole("button").evaluateAll((elements) => elements.every((element) => element.getBoundingClientRect().width === elements[0].getBoundingClientRect().width))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("discloses metadata destinations and allows local orchestration without consent", async ({ page }) => {
  let automaticRequests = 0;
  await page.route("**/api/missions/auto", (route) => {
    automaticRequests++;
    return route.abort();
  });
  await page.route("**/api/status", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ api_mode: "loopback_only", providers: { deepseek: false, sciverse: true, mineru: true, openalex: true, crossref: true, crossref_polite_contact: true }, operation_contracts: operationContracts }),
  }));

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByLabel("候选航向研究问题").fill("BiFeO3的相转变温度是多少？");
  await page.locator(".candidate-planet").first().click();

  const destinations = page.getByRole("status").filter({ hasText: "本次元数据将发送至" });
  await expect(destinations).toContainText("Sciverse、OpenAlex、Crossref");
  await expect(page.getByLabel(/我确认本次任务可向上列书目服务发送/)).toBeVisible();
  await expect(page.getByRole("button", { name: "确认并授权元数据检索" })).toBeDisabled();
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "仅进入本机编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  expect(automaticRequests).toBe(0);
});

test("dispatches an automatic metadata mission only from the authorized action", async ({ page }) => {
  await page.route("**/api/status", (route) => route.fulfill({ json: {
    api_mode: "loopback_only",
    providers: { deepseek: false, sciverse: true, mineru: false, openalex: false, crossref: true, crossref_polite_contact: true },
    operation_contracts: operationContracts,
  } }));
  await page.route("**/api/missions/auto", (route) => route.fulfill({ status: 503 }));
  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByLabel(/我确认本次任务可向上列书目服务发送/).check();
  const request = page.waitForRequest("**/api/missions/auto");
  await page.getByRole("button", { name: "确认并授权元数据检索" }).click();
  expect((await request).postDataJSON()).toMatchObject({ consent: true, sources: ["sciverse", "crossref"] });
});

test("activates a BFO task template through the keyboard with an explicit pressed state", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const bfo = page.getByRole("button", { name: /BFO-01/ });
  await expect(bfo).toHaveAttribute("aria-pressed", "false");
  await bfo.focus();
  await page.keyboard.press("Enter");
  await expect(bfo).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("研究对象")).toHaveValue("BiFeO₃ 外延薄膜");
  await expect(page.getByRole("button", { name: "预览：任务定义" })).toHaveAttribute("aria-current", "step");
});

test("keeps synthetic launch-preview papers out of the real research route", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const bridge = page.locator(".fleet-command-stage");
  await expect(bridge).toContainText("只读预览数据层", lazyWorkspaceContentLoad);
  await expect(bridge).toContainText("只读预览未检查");
  await expect(bridge.getByRole("button", { name: "刷新核验结果" })).toHaveCount(0);
  await expect(bridge.locator(".workflow-next")).toContainText("等待受控检索或导入可审查文献子图");
  await expect(bridge).not.toContainText("20 篇可审查文献");

  await page.getByRole("button", { name: "03 文献星图" }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, workspaceLoad);
  await expect(page.locator(".graph-empty")).toContainText("仅供导航或演示的论文式节点", lazyWorkspaceContentLoad);
  const returnToBridge = page.getByRole("button", { name: "返回舰桥查看工件状态" });
  await expect(returnToBridge).toHaveClass(/cm-action--primary/);
  expect(await returnToBridge.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(13);
});

test("opens an existing DSH run by ID and reads PDF status from the local snapshot", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const runId = "run_dsh_existing_01";
  const missionId = "mission_dsh_existing_01";
  const documentId = "pdf_0123456789abcdef01234567";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  bundle.mission.mission_id = missionId;
  bundle.mission.question = "Local DSH handoff for a reviewed BiFeO3 thin-film question";
  const requests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/")) requests.push(`${request.method()} ${path}`);
  });
  await page.route("**/api/runs/**/ui", (route) => route.fulfill({ json: bundle }));
  await page.route("**/api/runs/**/status", (route) => {
    const id = new URL(route.request().url()).pathname.split("/")[3];
    return route.fulfill({ json: { run_id: id, mission_id: id === runId ? missionId : "mismatched_mission", state: "INTAKE" } });
  });
  await page.route(`**/api/runs/${runId}/pdf/tasks/cached`, (route) => route.fulfill({ json: {
    run_id: runId, trust_status: "private_pdf_task_registry_metadata_only", tasks: [{
      document_id: documentId, candidate_document_id: null, audit_document_id: documentId,
      file_name: "cached-running.pdf", state: "running", audit_state: "running",
      doi: null, doi_status: "pending", markdown_ready: false, source_map_review_status: "absent",
      source_map_segment_count: 0, error: null, trust_status: "private_markdown_outside_run_not_scientific_evidence",
    }],
  } }));

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /^续航任务/ }).click();
  const input = page.getByLabel("现有运行 ID");
  const open = page.getByRole("button", { name: "打开本机运行" });
  await input.fill("../anything");
  await expect(open).toBeDisabled();
  expect(requests.every((request) => !request.includes("/api/runs/"))).toBe(true);
  await input.fill("wrong_mission_run");
  await open.click();
  await expect(page.getByRole("alert")).toContainText("无法打开该运行");
  await expect(input).toHaveValue("wrong_mission_run");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await input.fill(` ${runId} `);
  await input.press("Enter");
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.getByText("cached-running.pdf", { exact: true })).toBeVisible(lazyWorkspaceContentLoad);
  await expect(page.locator(".rail-run-id code")).toHaveText(runId);
  await page.getByRole("button", { name: "复制运行 ID" }).click();
  await expect(page.locator(".rail-run-identity").getByRole("status")).toHaveText("运行 ID 已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(runId);
  await page.getByRole("button", { name: "复制任务链接" }).click();
  await expect(page.locator(".rail-run-identity").getByRole("status")).toHaveText("本机任务链接已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
  const handoff = page.locator(".dsh-run-handoff");
  await handoff.locator("summary").press("Enter");
  const command = "cosmatter dsh-run-status " + runId + " --port " + new URL(page.url()).port;
  await expect(handoff.locator("code")).toHaveText(command);
  await handoff.getByRole("button", { name: "复制 DSH 命令" }).click();
  await expect(handoff.getByRole("status")).toHaveText("DSH 命令已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(command);
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", {
    value: () => Promise.reject(new DOMException("Clipboard access denied", "NotAllowedError")),
  }));
  await handoff.getByRole("button", { name: "复制 DSH 命令" }).click();
  await expect(handoff.getByRole("status")).toHaveText("剪贴板不可用，可选中上方命令复制。");
  expect(await handoff.evaluate((element) => element.scrollWidth === element.clientWidth)).toBe(true);
  await page.getByRole("link", { name: "CosMatter", exact: true }).click();
  expect(new URL(page.url()).hash).toBe("");
  await page.getByRole("button", { name: /^续航任务/ }).click();
  await input.fill("wrong_mission_run");
  await open.click();
  await expect(page.getByRole("alert")).toContainText("无法打开该运行");
  await expect(page.locator(".launch-active-run")).toContainText(runId);
  await page.getByRole("button", { name: "返回当前任务" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  expect(requests.filter((request) => request.includes("/pdf/"))).toEqual([`GET /api/runs/${runId}/pdf/tasks/cached`]);
  expect(requests.every((request) => request.startsWith("GET "))).toBe(true);
});

test("finds recent local missions without a run ID and reuses the selected run", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const runId = "saved_run_05";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  bundle.literature_graph = {
    trust_status: "human_reviewed_graph_projection",
    nodes: [{ node_id: "paper:saved", kind: "candidate_paper", label: "Saved candidate to screen", trust_status: "candidate_metadata_not_scientific_evidence" }],
    edges: [],
  };
  const requests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/")) requests.push(request.method() + " " + path);
  });
  let count = 0;
  let releaseStatus: () => void = () => {};
  const statusAllowed = new Promise<void>((resolve) => { releaseStatus = resolve; });
  await page.route("**/api/recent-runs", (route) => {
    count += 1;
    if (count === 1) return route.fulfill({ status: 503, json: {} });
    return route.fulfill({ json: {
      schema_version: "cosmatter.recent-local-runs/v1",
      runs: Array.from({ length: 5 }, (_, index) => ({
        run_id: "saved_run_0" + (index + 1), material: "BiFeO3", property: "phase stability under epitaxial strain".repeat(3),
        updated_at: "2026-11-18T03:00:05Z", stopped: index === 1,
      })),
    } });
  });
  await page.route("**/api/runs/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs/" + runId + "/ui") return route.fulfill({ json: bundle });
    if (path === "/api/runs/" + runId + "/stage-contract") return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "screening") });
    if (path === "/api/runs/" + runId + "/status") {
      await statusAllowed;
      return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/?api=local");
  await expect(page.locator(".workbench")).toHaveClass(/view-launch/);
  expect(count).toBe(0);
  await page.getByRole("button", { name: /^续航任务/ }).click();
  const list = page.getByRole("region", { name: "最近的本机任务" });
  await expect(list.getByRole("status")).toHaveText(/无法读取最近任务/);
  const command = list.locator(".dsh-run-handoff");
  await command.locator("summary").press("Enter");
  await expect(command).toHaveAttribute("open", "");
  const expectedCommand = "cosmatter dsh-recent-runs --port " + new URL(page.url()).port;
  await expect(command.locator("code")).toHaveText(expectedCommand);
  await command.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(command.getByRole("status")).toHaveText("DSH 命令已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedCommand);
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", {
    value: () => Promise.reject(new DOMException("Clipboard access denied", "NotAllowedError")),
  }));
  await command.getByRole("button", { name: "复制 DSH 命令" }).click();
  await expect(command.getByRole("status")).toHaveText("剪贴板不可用，可选中上方命令复制。");
  expect(count).toBe(1);
  await list.getByRole("button", { name: "刷新列表" }).click();
  await expect(list.getByRole("listitem")).toHaveCount(4);
  await expect(list.getByText("已停止", { exact: true })).toBeVisible();
  await expect(list.getByRole("button", { name: "打开 saved_run_02" })).toHaveCount(0);
  await list.getByRole("button", { name: "查看全部 5 条" }).press("Enter");
  await expect(list.getByRole("listitem")).toHaveCount(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  await list.getByRole("button", { name: "打开 " + runId }).press("Enter");
  try {
    const opening = list.getByRole("button", { name: "正在打开 " + runId });
    await expect(opening).toHaveAttribute("aria-busy", "true");
    await expect(opening).toBeDisabled();
  } finally {
    releaseStatus();
  }
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, workspaceLoad);
  await expect(page.locator(".rail-run-id code")).toHaveText(runId);
  await expect(page.getByText(/打开时阶段为“候选筛选”/)).toBeVisible();
  await page.getByRole("link", { name: "CosMatter", exact: true }).click();
  await page.getByRole("button", { name: "返回当前任务" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, workspaceLoad);
  expect(requests.filter((request) => request === "GET /api/runs/" + runId + "/ui")).toHaveLength(1);
  expect(requests.every((request) => request.startsWith("GET "))).toBe(true);
});

test("opens stopped runs as read-only records from DSH links and recent tasks", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const runId = "archived_resume";
  const missionId = "mission_archive";
  const resource = `/api/runs/${runId}`;
  const downloadPath = resource + "/artifacts/workflow_readiness";
  const title = "工作流就绪度摘要";
  let manifests = 0;
  const calls: string[] = [];
  await page.route("**/api/runs/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push(route.request().method() + " " + path);
    if (path === resource + "/status") return route.fulfill({ json: { run_id: runId, mission_id: missionId, state: "CANCELLED" } });
    if (path === resource + "/artifacts") {
      manifests += 1;
      return route.fulfill({ json: {
        schema_version: "cosmatter.artifact/v1", run_id: runId, mission_id: missionId,
        trust_status: "allowlisted_artifact_index_not_scientific_evidence", artifact_count: 1,
        artifacts: [{ artifact_id: "workflow_readiness", title, generated_at: "2026-11-19T03:00:00Z",
          media_type: "application/json; charset=utf-8", sha256: "a".repeat(64), trust_status: "derived_workflow_readiness_not_scientific_evidence",
          download_path: manifests === 1 ? "https://example.invalid/escaped" : downloadPath }],
      } });
    }
    if (path === downloadPath) return route.fulfill({ headers: { "Content-Disposition": 'attachment; filename="workflow_readiness.json"' }, json: { mission_id: missionId } });
    return route.fulfill({ status: 404 });
  });
  await page.route("**/api/recent-runs", (route) => route.fulfill({ json: {
    schema_version: "cosmatter.recent-local-runs/v1",
    runs: [{ run_id: runId, material: "BiFeO3", property: "phase transitions", updated_at: "2026-11-19T03:00:00Z", stopped: true }],
  } }));
  await page.goto(`/?api=local#run=${runId}&document=paper_a&evidence=card_a`);
  const record = page.getByRole("region", { name: "已停止的任务记录" });
  await expect(record.getByRole("heading")).toBeFocused();
  await expect(record.getByRole("status")).toHaveText("暂时无法核验工件目录。");
  await expect(record.getByRole("link")).toHaveCount(0);
  expect(new URL(page.url()).hash).toBe("#run=" + runId);
  await record.getByRole("button", { name: "重试读取目录" }).press("Enter");
  const download = record.getByRole("link", { name: "下载" + title });
  await expect(download).toHaveAttribute("href", downloadPath);
  const file = page.waitForEvent("download");
  await download.press("Enter");
  expect((await file).suggestedFilename()).toBe("workflow_readiness.json");
  await record.locator(".dsh-run-handoff > summary").press("Enter");
  await record.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(record.getByRole("status")).toHaveText("DSH 命令已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(`cosmatter dsh-run-artifacts ${runId} --port ${new URL(page.url()).port}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  await record.getByRole("button", { name: "关闭记录" }).press("Enter");
  await expect(record).toHaveCount(0);
  await expect(page.getByLabel("现有运行 ID")).toBeFocused();
  expect(new URL(page.url()).hash).toBe("");
  const recent = page.getByRole("region", { name: "最近的本机任务" });
  await recent.getByRole("button", { name: "查看最近任务" }).click();
  await recent.getByRole("button", { name: "查看记录 " + runId }).press("Enter");
  await expect(record.getByRole("link", { name: "下载" + title })).toBeVisible();
  expect(calls).toEqual([
    "GET " + resource + "/status", "GET " + resource + "/artifacts", "GET " + resource + "/artifacts", "GET " + downloadPath,
    "GET " + resource + "/status", "GET " + resource + "/artifacts",
  ]);
});

test("opens the active run artifact directory from the bridge and an exact DSH link", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const runId = "run_saved_outputs";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  const missionId = bundle.mission.mission_id;
  const prefix = `/api/runs/${runId}`;
  const downloadPath = prefix + "/artifacts/workflow_readiness";
  const artifact = { artifact_id: "workflow_readiness", title: "工作流就绪度摘要", generated_at: "2026-11-19T03:00:00Z",
    media_type: "application/json; charset=utf-8", sha256: "ab".repeat(32), trust_status: "derived_workflow_readiness_not_scientific_evidence", download_path: downloadPath };
  let artifactReads = 0;
  let linkedReads: string[] | undefined;
  const writes: string[] = [];
  await page.route("**/api/runs/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    linkedReads?.push(path);
    if (route.request().method() !== "GET") writes.push(path);
    if (path === prefix + "/status") return route.fulfill({ json: { run_id: runId, mission_id: missionId, state: "INTAKE" } });
    if (path === prefix + "/ui") return route.fulfill({ json: bundle });
    if (path === prefix + "/stage-contract") return route.fulfill({ json: stageContractFixture(runId, missionId, "plan") });
    if (path === prefix + "/artifacts") {
      artifactReads += 1;
      const artifacts = artifactReads > 1 ? [artifact] : [];
      return route.fulfill({ json: { schema_version: "cosmatter.artifact/v1", run_id: runId, mission_id: missionId,
        trust_status: "allowlisted_artifact_index_not_scientific_evidence", artifact_count: artifacts.length, artifacts } });
    }
    if (path === downloadPath) return route.fulfill({ headers: { "Content-Disposition": 'attachment; filename="workflow_readiness.json"' }, json: { mission_id: missionId } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/?api=local#run=" + runId);
  const summary = page.locator(".saved-run-artifacts-deck > summary");
  const directory = page.getByRole("region", { name: "已保存工件" });
  await expect(summary).toBeVisible(workspaceLoad);
  expect(artifactReads).toBe(0);
  await summary.press("Enter");
  await expect(directory.getByRole("status")).toHaveText("暂无可下载的工件。");
  await directory.getByRole("button", { name: "刷新工件目录" }).press("Enter");
  await expect(directory.getByRole("link", { name: "下载" + artifact.title })).toBeVisible();
  await directory.getByRole("button", { name: "复制工件目录链接" }).press("Enter");
  await expect(directory.getByText("工件目录链接已复制。", { exact: true })).toBeVisible();
  const copiedLink = await page.evaluate(() => navigator.clipboard.readText());
  expect(copiedLink).toBe(new URL(`/?api=local#run=${runId}&artifacts=1`, page.url()).href);
  linkedReads = [];
  await page.evaluate((link) => { window.location.href = link; }, copiedLink);
  await expect(directory.getByRole("heading", { name: "已保存工件" })).toBeFocused(workspaceLoad);
  await expect(directory.getByRole("button", { name: "打开任务" })).toBeVisible();
  await directory.locator(".saved-artifact-hash > summary").press("Enter");
  await expect(directory.locator(".saved-artifact-hash code")).toHaveText(artifact.sha256);
  await directory.getByRole("button", { name: "复制 SHA-256" }).press("Enter");
  await expect(directory.getByText("SHA-256 已复制。", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(artifact.sha256);
  await directory.locator(".dsh-run-handoff > summary").press("Enter");
  await expect(directory.locator(".dsh-run-handoff code")).toHaveText(`cosmatter dsh-run-artifacts ${runId} --port ${new URL(page.url()).port}`);
  const file = page.waitForEvent("download");
  await directory.getByRole("link", { name: "下载" + artifact.title }).press("Enter");
  expect((await file).suggestedFilename()).toBe("workflow_readiness.json");
  expect(artifactReads).toBe(3);
  expect(linkedReads).toEqual([prefix + "/status", prefix + "/artifacts", downloadPath]);
  expect(writes).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
});

test("resumes browser screening drafts and requires the current checklist revision when recording", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const runId = "local_screening_draft";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  const papers = [
    { document_id: "paper_a", title: "Candidate A", source: "local fixture", publication_year: 2024 },
    { document_id: "paper_b", title: "Candidate B with a long title for narrow layout validation".repeat(3), source: "local fixture", publication_year: 2025 },
  ];
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", nodes: papers.map((paper) => ({
    node_id: "paper:" + paper.document_id, kind: "candidate_paper", label: paper.title, trust_status: "candidate_metadata_not_scientific_evidence",
  })), edges: [] };
  let screening = {
    run_id: runId, candidate_count: papers.length, candidates: papers, trust_status: "blank_human_candidate_screening_template_not_a_result",
    checklist_revision: "a".repeat(64), decisions: papers.map(({ document_id }) => ({ document_id, decision: "unreviewed", reason_codes: [] as string[] })),
  };
  const submissions: unknown[] = [];
  let sourceTasks: { document_id: string; state: string; markdown_ready?: boolean; can_link_markdown?: boolean; source_map_segment_count?: number }[] = [];
  const reviewedExcerpt = "Synthetic checked source excerpt.";
  const conditionLine = "Reported measurement conditions.";
  const markdownLines = ["# Candidate A", reviewedExcerpt, conditionLine, '<img src="https://example.invalid/figure.png">',
    ...Array.from({ length: 16 }, (_, index) => `Synthetic line ${5 + index}`), "x".repeat(1_601), "Last line"];
  const originalMarkdown = Buffer.from(markdownLines.join("\n") + "\n");
  const previewStarts: number[] = [];
  const tracedSegments: string[] = [];
  let recordedLocationChanged = false;
  const markdownLinkAttempts: string[] = [];
  const sourceMapPosts: unknown[] = [];
  const sourceMap = { run_id: runId, document_id: "paper_a", segment_count: 2, trust_status: "human_reviewed_parser_selection_not_evidence_card",
    segments: [{ segment_id: "private_md_001", locator: "markdown_line:1-1", kind: "paragraph", markdown_range: { start: 1, end: 1 } },
      { segment_id: "private_md_002", locator: "markdown_line:2-3", kind: "paragraph", markdown_range: { start: 2, end: 3 } }] };
  await page.route("**/api/runs/**", (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.split("/").pop();
    if (path === "ui") return route.fulfill({ json: bundle });
    if (path === "status") return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    if (path === "stage-contract") return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "screening") });
    if (path === "source-parse-status") return route.fulfill({ json: {
      run_id: runId, mission_id: bundle.mission.mission_id,
      trust_status: "saved_source_parse_state_not_scientific_evidence", tasks: sourceTasks,
    } });
    if (path === "source-markdown-link" && route.request().method() === "POST") {
      const documentId = url.searchParams.get("document_id");
      if (documentId !== "paper_a" || route.request().headers()["content-type"] !== "application/octet-stream") return route.fulfill({ status: 400 });
      const data = route.request().postDataBuffer();
      markdownLinkAttempts.push(data?.toString() ?? "");
      if (!data?.equals(originalMarkdown)) return route.fulfill({ status: 422 });
      sourceTasks = [{ document_id: documentId, state: "done", markdown_ready: true, can_link_markdown: false, source_map_segment_count: 0 }];
      return route.fulfill({ json: { run_id: runId, document_id: documentId, markdown_ready: true } });
    }
    if (path === "source-markdown-lines" && url.searchParams.get("document_id") === "paper_a" && route.request().method() === "GET") {
      const start = Number(url.searchParams.get("start"));
      previewStarts.push(start);
      const segmentId = url.searchParams.get("segment_id");
      const recordedRange = sourceMap.segments.find((segment) => segment.segment_id === segmentId)?.markdown_range;
      if (segmentId) {
        tracedSegments.push(segmentId);
        if (!recordedRange || recordedLocationChanged) return route.fulfill({ status: 409 });
      }
      return route.fulfill({ json: { run_id: runId, document_id: "paper_a", start, total_lines: markdownLines.length,
        lines: markdownLines.slice(start - 1, start + 19).map((text, index) => ({ number: start + index, text: text.slice(0, 1_600), truncated: text.length > 1_600 })),
        ...(recordedRange ? { recorded_range: recordedRange } : {}),
      } });
    }
    if (path === "source-map") {
      if (route.request().method() === "POST") {
        sourceMapPosts.push(route.request().postDataJSON());
        sourceTasks = [{ document_id: "paper_a", state: "done", markdown_ready: true, source_map_segment_count: 2 }];
        return route.fulfill({ json: sourceMap });
      }
      if (url.searchParams.get("document_id") === "paper_a") return route.fulfill({ json: sourceMap });
    }
    if (path === "candidate-screening") {
      if (route.request().method() === "GET") return route.fulfill({ json: screening });
      const body = route.request().postDataJSON();
      submissions.push(body);
      screening = { ...screening, decisions: body.decisions, trust_status: "human_reviewed_candidate_screening_not_scientific_evidence", checklist_revision: "c".repeat(64) };
      return route.fulfill({ json: { run_id: runId, candidate_count: 2 } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  const panel = page.getByRole("region", { name: "候选文献人工筛选" });
  const originalScreeningLink = `/?api=local#run=${runId}&screening=${screening.checklist_revision}`;
  const selectA = async () => {
    await panel.getByRole("combobox", { name: "决定", exact: true }).selectOption("include_for_fulltext");
    await expect(panel.getByRole("combobox", { name: "理由", exact: true })).toHaveValue("");
    await panel.getByRole("combobox", { name: "理由", exact: true }).selectOption("material_match");
  };
  await page.goto(originalScreeningLink);
  await expect(panel.getByRole("heading")).toBeFocused();
  await expect(panel.locator(".screening-link-notice")).toHaveText("已从 DSH 打开同一版本的筛选清单。");
  await panel.getByRole("button", { name: "复制筛选链接" }).press("Enter");
  await expect(panel.getByText("筛选链接已复制。", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
  await selectA();
  await expect(panel.getByText("已登记 0 篇 · 草稿修改 1 篇")).toBeVisible();
  await expect(panel.getByRole("button", { name: "提交人工筛选决定" })).toBeDisabled();
  expect(submissions).toEqual([]);
  await panel.getByRole("button", { name: "下一待审" }).press("Enter");
  await expect(panel.locator(".screening-queue-card")).toContainText("Candidate B");
  await panel.getByRole("button", { name: "收起筛选" }).click();
  await expect(panel).toHaveCount(0);
  await page.reload();
  await expect(panel.getByRole("heading")).toBeFocused();
  await expect(panel.locator(".screening-queue-card")).toContainText("Candidate B");
  await expect(panel.getByText("已登记 0 篇 · 草稿修改 1 篇")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);

  screening = { ...screening, checklist_revision: "b".repeat(64) };
  await page.reload();
  await expect(panel.locator(".screening-link-notice")).toHaveText("DSH 链接中的清单已更新，请按当前版本重新核对。");
  const currentLink = new URL(page.url());
  currentLink.hash = new URLSearchParams({ run: runId, screening: screening.checklist_revision }).toString();
  await panel.locator(".dsh-run-handoff > summary").press("Enter");
  const screeningCommand = `cosmatter dsh-screening '${currentLink.href}'`;
  await expect(panel.locator(".dsh-run-handoff code")).toHaveText(screeningCommand);
  await panel.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(panel.getByText("DSH 命令已复制。", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(screeningCommand);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  await expect(panel.getByText("清单或登记记录已更新，请按当前版本重新核对。", { exact: true })).toBeVisible();
  await expect(panel.locator(".screening-queue-card")).toContainText("Candidate A");
  await expect(panel.getByRole("button", { name: "提交人工筛选决定" })).toBeDisabled();
  expect(submissions).toEqual([]);
  await selectA();
  await panel.getByRole("button", { name: "下一待审" }).click();
  await panel.getByRole("combobox", { name: "决定", exact: true }).selectOption("exclude");
  await panel.getByRole("combobox", { name: "理由", exact: true }).selectOption("out_of_scope_material");
  const queue = page.getByRole("region", { name: "全文核对队列" });
  await expect(queue).toHaveCount(0);
  await panel.getByRole("button", { name: "提交人工筛选决定" }).click();
  await expect(panel.getByText("已登记 2 篇 · 草稿修改 0 篇")).toBeVisible();
  await expect(queue.getByRole("button", { name: "选择授权 PDF · Candidate A" })).toBeEnabled();
  expect(submissions).toEqual([{ checklist_revision: "b".repeat(64), decisions: screening.decisions }]);

  sourceTasks = [{ document_id: "paper_a", state: "running" }];
  await queue.getByRole("button", { name: "刷新本机解析记录" }).click();
  await expect(queue.getByText("来源解析中", { exact: true })).toBeVisible();
  await expect(queue.getByRole("button", { name: /选择授权 PDF/ })).toHaveCount(0);
  sourceTasks = [{ document_id: "paper_a", state: "done" }];
  await queue.getByRole("button", { name: "刷新本机解析记录" }).click();
  await expect(queue.getByText("来源解析完成", { exact: true })).toBeVisible();
  await expect(queue.getByRole("button", { name: /选择授权 PDF|进入阅读页/ })).toHaveCount(0);
  await expect(queue.getByRole("button", { name: /关联本机 Markdown/ })).toHaveCount(0);
  sourceTasks = [{ document_id: "paper_a", state: "done", markdown_ready: false, can_link_markdown: true, source_map_segment_count: 0 }];
  await queue.getByRole("button", { name: "刷新本机解析记录" }).click();
  await expect(queue.getByText("等待关联原文件", { exact: true })).toBeVisible();
  const linkFile = async (buffer: Buffer) => {
    const chooser = page.waitForEvent("filechooser");
    await queue.getByRole("button", { name: "关联本机 Markdown · Candidate A" }).press("Enter");
    await (await chooser).setFiles({ name: "original.md", mimeType: "text/markdown", buffer });
  };
  await linkFile(Buffer.from("wrong candidate file"));
  await expect(queue.getByRole("status")).toContainText("文件与该候选的 MinerU 回执不匹配");
  await expect(queue.getByRole("button", { name: /进入阅读页/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  await linkFile(originalMarkdown);
  await expect(queue.getByText("本机 Markdown 就绪", { exact: true })).toBeVisible();
  expect(markdownLinkAttempts).toEqual(["wrong candidate file", originalMarkdown.toString()]);
  await queue.getByRole("button", { name: "进入阅读页 · Candidate A" }).press("Enter");
  await expect(page.locator(".reader-selection")).toContainText("Candidate A");
  const markdownLink = page.getByRole("link", { name: "下载私有 Markdown" });
  await expect(markdownLink).toHaveAttribute("href", /\/source-markdown\?document_id=paper_a$/);
  const locators = page.getByLabel("来源定位", { exact: true });
  const quotes = page.getByLabel("人工核对的短引文", { exact: true });
  const confirmation = page.getByRole("checkbox", { name: /我已在本地 Markdown 中核对/ });
  await locators.first().pressSequentially("markdown_line:1-1");
  await expect(locators.first()).toHaveValue("markdown_line:1-1");
  await quotes.first().fill("# Candidate A");
  await confirmation.check();
  expect(previewStarts).toEqual([]);

  const source = page.getByRole("region", { name: "原文行号" });
  await source.getByRole("button", { name: "查看带行号的原文" }).press("Enter");
  await expect(source.getByText("第 1–20 行，共 22 行")).toBeVisible();
  await expect(source.getByText('<img src="https://example.invalid/figure.png">', { exact: true })).toBeVisible();
  await expect(source.locator("img")).toHaveCount(0);
  await source.getByRole("button", { name: "下一段" }).click();
  await expect(source.getByText("第 21–22 行，共 22 行")).toBeVisible();
  await source.getByRole("button", { name: "第 21 行", exact: true }).click();
  await expect(source.getByRole("button", { name: "填入来源草稿" })).toBeDisabled();
  await source.getByLabel("行号", { exact: true }).fill("2");
  await source.getByRole("button", { name: "跳转" }).click();
  await expect(source.getByText("第 2–21 行，共 22 行")).toBeVisible();
  await source.getByRole("button", { name: "第 2 行", exact: true }).press("Enter");
  await source.getByRole("button", { name: "第 3 行", exact: true }).press("Enter");
  await source.getByRole("button", { name: "填入来源草稿" }).click();
  expect(previewStarts).toEqual([1, 21, 2]);
  await expect(locators.first()).toHaveValue("markdown_line:1-1");
  await expect(locators.nth(1)).toHaveValue("markdown_line:2-3");
  await expect(quotes.nth(1)).toHaveValue(`${reviewedExcerpt}\n${conditionLine}`);
  await expect(confirmation).not.toBeChecked();
  expect(sourceMapPosts).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  const save = page.getByRole("button", { name: "登记人工 Source Map" });
  await expect(save).toBeDisabled();
  await confirmation.check();
  await save.click();
  await expect(page.locator(".recorded-source-map")).toContainText("markdown_line:2-3");
  expect(sourceMapPosts).toEqual([{ document_id: "paper_a", human_confirmed: true, segments: [
    { locator: "markdown_line:1-1", kind: "paragraph", quote: "# Candidate A" },
    { locator: "markdown_line:2-3", kind: "paragraph", quote: `${reviewedExcerpt}\n${conditionLine}` },
  ] }]);
  await page.getByRole("button", { name: "更换论文" }).click();
  await expect(queue.getByText("已登记来源定位", { exact: true })).toBeVisible();
  await queue.getByRole("button", { name: "进入阅读页 · Candidate A" }).press("Enter");
  const jumpToSecondLocation = page.getByRole("button", { name: "查看原文 markdown_line:2-3", exact: true });
  await expect(source.getByRole("button", { name: "查看带行号的原文" })).toBeVisible();
  await jumpToSecondLocation.press("Enter");
  await expect(source).toBeFocused();
  await expect(source.getByText("来源定位第 2–3 行", { exact: true })).toBeVisible();
  await expect(source.locator("li.selected")).toHaveText([`2${reviewedExcerpt}`, `3${conditionLine}`]);
  await expect(jumpToSecondLocation).toHaveAttribute("aria-pressed", "true");
  await source.getByRole("button", { name: "下一段" }).click();
  await expect(source.getByText("第 22 行，共 22 行", { exact: true })).toBeVisible();
  await expect(source.locator("li.selected")).toHaveCount(0);
  await source.getByRole("button", { name: "返回定位起点" }).click();
  await expect(source.locator("li.selected")).toHaveCount(2);

  recordedLocationChanged = true;
  await jumpToSecondLocation.click();
  await expect(source.getByText("该来源定位与当前原文无法对应。", { exact: true })).toBeVisible();
  await expect(source.locator("li.selected")).toHaveCount(0);
  expect(tracedSegments).toEqual(Array(4).fill("private_md_002"));
  expect(sourceMapPosts).toHaveLength(1);
  await page.getByRole("button", { name: "更换论文" }).click();
  await expect(queue.getByText("已登记来源定位", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  sourceTasks = [{ document_id: "paper_a", state: "failed" }];
  await queue.getByRole("button", { name: "刷新本机解析记录" }).click();
  await queue.getByRole("button", { name: "重新选择授权 PDF · Candidate A" }).click();
  await expect(page.locator(".candidate-pdf-context")).toContainText("Candidate A");
  await page.getByRole("button", { name: "返回文献星图", exact: true }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, workspaceLoad);
});

test("opens local DSH links directly and keeps a failed linked run editable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const runId = "run_dsh_link_01";
  const missingId = "missing_run";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  const runRequests: string[] = [];
  let recentRequests = 0;
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/runs/")) runRequests.push(`${request.method()} ${path}`);
    if (path === "/api/recent-runs") recentRequests += 1;
  });
  await page.route("**/api/runs/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/runs/${runId}/ui`) return route.fulfill({ json: bundle });
    if (path === `/api/runs/${runId}/status`) return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
    if (path === `/api/runs/${runId}/pdf/tasks/cached`) return route.fulfill({ json: { run_id: runId, tasks: [] } });
    return route.fulfill({ status: 404, json: {} });
  });

  await page.goto(`/#run=${runId}`);
  await expect(page.locator(".workbench")).toHaveClass(/view-launch/);
  await page.goto("/?api=local#run=..%2Foutside");
  await expect(page.locator(".workbench")).toHaveClass(/view-launch/);
  expect(runRequests).toEqual([]);

  await page.goto(`/?api=local#run=${missingId}`);
  await expect(page.getByRole("alert")).toContainText("无法打开该运行");
  await expect(page.getByLabel("现有运行 ID")).toHaveValue(missingId);
  await expect(page.getByRole("button", { name: "打开本机运行" })).toBeEnabled();

  const cached = page.waitForResponse(`**/api/runs/${runId}/pdf/tasks/cached`);
  await page.goto(`/?api=local#run=${runId}`);
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.locator(".rail-run-id code")).toHaveText(runId);
  await expect(page.getByText(/阶段暂未核验/)).toBeVisible();
  await cached;
  expect(recentRequests).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  expect(runRequests.every((request) => request.startsWith("GET "))).toBe(true);
  expect(runRequests.filter((request) => request.includes("/pdf/"))).toEqual([`GET /api/runs/${runId}/pdf/tasks/cached`]);
  await page.goto(`/?api=local#run=${runId}&screening=${"a".repeat(64)}`);
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.getByText(/暂时无法打开链接指定的筛选清单/)).toBeVisible();
  await expect(page.getByRole("region", { name: "候选文献人工筛选" })).toHaveCount(0);
  expect(runRequests.every((request) => request.startsWith("GET "))).toBe(true);
});

test("opens the linked DSH candidate at its verified review step", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.setViewportSize({ width: 320, height: 900 });
  const runId = "dsh_candidate_handoff";
  const { readFile } = await import("node:fs/promises");
  const bundle = JSON.parse(await readFile(routeDiagnosticsExport, "utf8"));
  const ready = "文献 & ready=1";
  const pending = "pending_paper";
  const excluded = "excluded_paper";
  const papers = [
    { document_id: ready, title: "Ready candidate", source: "local fixture" },
    { document_id: pending, title: "Pending candidate", source: "local fixture" },
    { document_id: excluded, title: "Excluded candidate", source: "local fixture" },
  ];
  const reviewedCards = [
    { evidence_id: "source_ready", claim: "Measured phase boundary", quote: "Temperature measured at 300 K.", locator: "markdown_line:7-7" },
    { evidence_id: "source_stale", claim: "Recorded comparison", quote: "Observed boundary change.", locator: "markdown_line:8-8" },
  ];
  bundle.evidence_cards = reviewedCards.map(({ locator, ...card }) => ({ ...card, review_status: "accepted", stance: "support", conditions: { temperature_k: 300 },
    provenance: { document_id: ready, locator, source: "human-reviewed MinerU source map", access_policy: "authorized" },
  }));
  bundle.evidence_cards.push({ ...bundle.evidence_cards[0], evidence_id: "source_unlinked" });
  bundle.literature_graph = { trust_status: "human_reviewed_graph_projection", nodes: [...papers.map((paper) => ({
    node_id: `paper:${paper.document_id}`, kind: "candidate_paper", label: paper.title, trust_status: "candidate_metadata_not_scientific_evidence",
  })), ...reviewedCards.map((card) => ({ node_id: `evidence:${card.evidence_id}`, kind: "evidence_card", label: card.claim, trust_status: "accepted" }))],
    edges: reviewedCards.map((card) => ({ source_id: `paper:${ready}`, target_id: `evidence:${card.evidence_id}`,
      edge_type: "source_provenance", relation_source: "reviewed source map", trust_status: "accepted" })),
  };
  const requests: string[] = [];
  const evidenceJumps: (string | null)[] = [];
  let markdownReady = true;
  const paperFragment = (document: string, evidence?: string) => new URLSearchParams({ run: runId, document, ...(evidence ? { evidence } : {}) }).toString();
  await page.route("**/api/runs/**", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    requests.push(`${request.method()} ${path}`);
    const prefix = `/api/runs/${runId}/`;
    if (!path.startsWith(prefix)) return route.fulfill({ status: 404 });
    switch (path.slice(prefix.length)) {
      case "ui": return route.fulfill({ json: bundle });
      case "status": return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      case "stage-contract": return route.fulfill({ json: stageContractFixture(runId, bundle.mission.mission_id, "parse") });
      case "pdf/tasks/cached": return route.fulfill({ json: { run_id: runId, tasks: [], trust_status: "private_pdf_task_registry_metadata_only" } });
      case "candidate-screening": return route.fulfill({ json: { run_id: runId, candidate_count: papers.length, candidates: papers, trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
        decisions: papers.map(({ document_id }) => ({ document_id, decision: document_id === excluded ? "exclude" : "include_for_fulltext", reason_codes: [document_id === excluded ? "out_of_scope_material" : "material_match"] })),
      } });
      case "source-parse-status": return route.fulfill({ json: { run_id: runId, mission_id: bundle.mission.mission_id, trust_status: "saved_source_parse_state_not_scientific_evidence",
        tasks: papers.map(({ document_id }) => ({ document_id, state: document_id === pending ? "running" : "done", markdown_ready: document_id !== pending && markdownReady, can_link_markdown: false, source_map_segment_count: document_id === ready && markdownReady ? 2 : 0 })),
      } });
      case "source-map": return route.fulfill({ json: { run_id: runId, document_id: ready, segment_count: 2, trust_status: "human_reviewed_parser_selection_not_evidence_card",
        segments: reviewedCards.map(({ locator }, index) => ({ segment_id: `segment_${index}`, locator, kind: "paragraph", markdown_range: { start: 7 + index, end: 7 + index } })),
      } });
      case "source-markdown-lines": {
        const evidenceId = url.searchParams.get("evidence_id");
        evidenceJumps.push(evidenceId);
        if (evidenceId !== "source_ready" || url.searchParams.get("document_id") !== ready || url.searchParams.has("start")) return route.fulfill({ status: 409 });
        return route.fulfill({ json: { run_id: runId, document_id: ready, evidence_id: evidenceId, start: 7, total_lines: 8,
          recorded_range: { start: 7, end: 7 }, lines: reviewedCards.map((card, index) => ({ number: 7 + index, text: card.quote, truncated: false })),
        } });
      }
      default: return route.fulfill({ status: 404 });
    }
  });

  await page.goto(`/?api=local#${paperFragment(ready)}`);
  await expect(page.locator(".reader-selection")).toContainText("Ready candidate", workspaceLoad);
  await expect(page.locator(".reader-source-intake a[download]")).toHaveAttribute("href", /document_id=%E6%96%87%E7%8C%AE%20%26%20ready%3D1$/);
  await page.reload();
  await expect(page.locator(".reader-selection")).toContainText("Ready candidate", workspaceLoad);
  await page.getByRole("button", { name: /source_ready.*Measured phase boundary/ }).press("Enter");
  const openSource = page.getByRole("button", { name: "核对原文", exact: true });
  const sourcePreview = page.getByRole("region", { name: "原文行号" });
  expect(evidenceJumps).toEqual([]);
  await openSource.press("Enter");
  await expect(sourcePreview).toBeFocused();
  await expect(sourcePreview.getByText("来源定位第 7 行", { exact: true })).toBeVisible();
  await expect(sourcePreview.locator("li.selected")).toHaveText("7Temperature measured at 300 K.");
  const toolOpener = page.locator(".research-rail").getByRole("button", { name: "查找 DSH 工具" });
  const toolDialog = page.getByRole("dialog", { name: "查找 DSH 工具" });
  const readerFragment = new URL(page.url()).hash;
  await page.setViewportSize({ width: 320, height: 568 });
  await toolOpener.press("Enter");
  await expect(toolDialog.getByRole("heading")).toBeFocused();
  const stagePicker = toolDialog.getByLabel("研究阶段");
  const search = toolDialog.getByRole("searchbox", { name: "搜索工具或插件包" });
  const resultPane = toolDialog.getByRole("region", { name: "工具结果" });
  await expect(stagePicker).toHaveValue("all");
  await expect(toolDialog.getByRole("button", { name: "只看本阶段" })).toHaveCount(0);
  const searchPosition = await search.boundingBox();
  await resultPane.press("End");
  await expect.poll(() => resultPane.evaluate((element) => element.scrollTop / (element.scrollHeight - element.clientHeight))).toBeGreaterThan(0.99);
  expect(await search.boundingBox()).toEqual(searchPosition);
  await stagePicker.selectOption("parse");
  await expect(toolDialog.locator(".dsh-tool-item")).toHaveCount(4);
  await expect.poll(() => resultPane.evaluate((element) => element.scrollTop)).toBe(0);
  const stageTool = toolDialog.locator(".dsh-tool-item").filter({ hasText: "cosmatter_stage_contract" });
  await stageTool.locator("summary").press("Enter");
  const stageCommand = `cosmatter dsh-read cosmatter_stage_contract --run-id ${runId} --port ${new URL(page.url()).port}`;
  await expect(stageTool.locator(".dsh-tool-terminal code")).toHaveText(stageCommand);
  await stageTool.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(stageTool.getByRole("status")).toHaveText("DSH 命令已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(stageCommand);
  const externalTool = toolDialog.locator(".dsh-tool-item").filter({ hasText: "cosmatter_mineru_source_submit" });
  await externalTool.locator("summary").press("Enter");
  await expect(externalTool.getByRole("button", { name: "复制 DSH 命令" })).toHaveCount(0);
  await expect(externalTool.getByRole("button", { name: "复制工具名" })).toBeVisible();
  await stagePicker.selectOption("extraction");
  const evidenceTool = toolDialog.locator(".dsh-tool-item").filter({ hasText: "cosmatter_accepted_evidence_search" });
  await evidenceTool.locator("summary").press("Enter");
  const exactLink = new URL(`/?api=local#${paperFragment(ready, "source_ready")}`, page.url());
  const evidenceCommand = `cosmatter dsh-evidence '${exactLink.href}'`;
  await expect(evidenceTool.locator(".dsh-tool-terminal code")).toHaveText(evidenceCommand);
  await evidenceTool.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(evidenceTool.getByRole("status")).toHaveText("DSH 命令已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(evidenceCommand);
  await toolDialog.getByRole("button", { name: "清除筛选" }).press("Enter");
  await expect(stagePicker).toHaveValue("all");
  await expect(search).toBeFocused();
  await expect(toolDialog.locator(".dsh-tool-item")).toHaveCount(20);
  expect(await toolDialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(toolDialog).toHaveCount(0);
  await expect(toolOpener).toBeFocused();
  await page.setViewportSize({ width: 320, height: 900 });
  await expect(sourcePreview.locator("li.selected")).toHaveText("7Temperature measured at 300 K.");
  expect(evidenceJumps).toEqual(["source_ready"]);
  expect(new URL(page.url()).hash).toBe(readerFragment);
  await page.getByRole("button", { name: /source_stale.*Recorded comparison/ }).press("Enter");
  await expect(sourcePreview.locator("li.selected")).toHaveCount(0);
  expect(evidenceJumps).toEqual(["source_ready"]);
  await openSource.click();
  await expect(sourcePreview.getByText("该证据卡与当前原文无法对应。", { exact: true })).toBeVisible();
  await expect(sourcePreview.locator("li.selected")).toHaveCount(0);
  expect(evidenceJumps).toEqual(["source_ready", "source_stale"]);

  const followPaper = (documentId: string, evidenceId?: string) => page.evaluate((fragment) => { window.location.hash = fragment; }, paperFragment(documentId, evidenceId));
  await followPaper(ready, "source_ready");
  await expect(page.locator(".source-reader blockquote")).toHaveText(reviewedCards[0].quote, workspaceLoad);
  await expect(page.locator(".source-reader")).toBeFocused();
  expect(new URL(page.url()).hash).toBe("#" + paperFragment(ready, "source_ready"));
  expect(evidenceJumps).toEqual(["source_ready", "source_stale"]);
  const evidenceCard = page.locator(".source-reader");
  const cardLink = page.url();
  await evidenceCard.getByRole("button", { name: "复制证据链接" }).click();
  await expect(evidenceCard.getByText("证据链接已复制。", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(cardLink);
  await evidenceCard.locator(".dsh-run-handoff > summary").press("Enter");
  await evidenceCard.getByRole("button", { name: "复制 DSH 命令" }).click();
  await expect(evidenceCard.getByText("DSH 命令已复制。", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(`cosmatter dsh-evidence '${cardLink}'`);
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", { value: () => Promise.reject(new DOMException("Clipboard access denied", "NotAllowedError")) }));
  await evidenceCard.getByRole("button", { name: "复制证据链接" }).click();
  await expect(evidenceCard.getByRole("textbox", { name: "证据链接", exact: true })).toHaveValue(cardLink);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  markdownReady = false;
  await page.reload();
  await expect(page.locator(".source-reader blockquote")).toHaveText(reviewedCards[0].quote, workspaceLoad);
  await expect(openSource).toHaveCount(0);
  markdownReady = true;

  const inspector = page.getByRole("complementary", { name: "图谱检查器" });
  await followPaper(ready, "source_unlinked");
  await expect(inspector.getByRole("heading", { name: "Ready candidate", exact: true })).toBeVisible(workspaceLoad);
  await expect(page.getByText("链接指定的 EvidenceCard 或其已审核来源关系在当前运行中不可用。", { exact: true })).toBeVisible();
  await expect(page.locator(".source-reader blockquote")).toHaveCount(0);
  await followPaper(pending, "source_ready");
  await expect(inspector.getByRole("heading", { name: "Pending candidate", exact: true })).toBeVisible(workspaceLoad);
  await expect(page.getByText("链接指定的 EvidenceCard 或其已审核来源关系在当前运行中不可用。", { exact: true })).toBeVisible();
  await followPaper(pending);
  await expect(inspector.getByRole("heading", { name: "Pending candidate", exact: true })).toBeVisible(workspaceLoad);
  await expect(inspector).toBeFocused();
  await expect(inspector.getByText(/DSH 轮询后可刷新/)).toBeVisible();
  await toolOpener.press("Enter");
  await expect(toolDialog.getByRole("heading")).toBeFocused();
  await stagePicker.selectOption("extraction");
  await evidenceTool.locator("summary").press("Enter");
  await expect(evidenceTool.getByRole("button", { name: "复制 DSH 命令" })).toHaveCount(0);
  await toolDialog.getByRole("button", { name: "关闭工具目录" }).press("Enter");
  await expect(toolDialog).toHaveCount(0);
  await expect(toolOpener).toBeFocused();
  await expect(inspector.getByRole("heading", { name: "Pending candidate", exact: true })).toBeVisible();
  await followPaper(excluded);
  await expect(inspector.getByRole("heading", { name: "Excluded candidate", exact: true })).toBeVisible(workspaceLoad);
  await expect(inspector.getByText("请先完成当前候选的人工筛选。")).toBeVisible();
  await expect(page.getByRole("link", { name: "下载私有 Markdown" })).toHaveCount(0);
  await followPaper("missing_paper");
  await expect(page.getByText("当前文献星图找不到链接指定的论文。", { exact: true })).toBeVisible(workspaceLoad);
  await expect(inspector).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  expect(requests.every((request) => request.startsWith("GET "))).toBe(true);
  expect(requests).not.toContain(`GET /api/runs/${runId}/pdf/tasks`);
});

test("keeps one reachable PDF refresh or citation action on the bridge", async ({ page }) => {
  const trustStatus = "private_markdown_outside_run_not_scientific_evidence";
  const pdf = {
    document_id: "test-doc", candidate_document_id: null, audit_document_id: "test-doc",
    file_name: `${"long-research-file-name-".repeat(6)}.pdf`, state: "running",
    audit_state: "running", doi: null, doi_status: "pending", markdown_ready: false,
    source_map_review_status: "absent", source_map_segment_count: 0, error: null, trust_status: trustStatus,
  };
  let parsed = false;
  let statusUnavailable = false;
  let releaseCitation: () => void = () => {};
  const pendingCitation = new Promise<void>((resolve) => { releaseCitation = resolve; });
  await page.route("**/api/status", (route) => route.fulfill({ json: {
    api_mode: "loopback_only",
    providers: { deepseek: false, sciverse: false, mineru: true, openalex: false, crossref: true, crossref_polite_contact: false },
    operation_contracts: operationContracts,
  } }));
  await page.route("**/api/pdf-runs", (route) => route.fulfill({ json: {
    run_id: "test-run", mission_id: "test-run", document_id: pdf.document_id, state: pdf.state, doi_status: pdf.doi_status,
  } }));
  await page.route("**/api/runs/test-run/pdf/test-doc/status", (route) => statusUnavailable
    ? route.fulfill({ status: 503 })
    : route.fulfill({ json: parsed
    ? { ...pdf, state: "done", audit_state: "done", doi: "10.1234/example", doi_status: "resolved", markdown_ready: true }
    : pdf,
  }));
  await page.route("**/api/runs/test-run/authorized-citation-expansion", async (route) => {
    await pendingCitation;
    await route.fulfill({ status: 503 });
  });

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /^文献入港/ }).click();
  await page.getByLabel("选择 PDF").setInputFiles({ name: pdf.file_name, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7\n") });
  await page.getByLabel(/我确认有权处理该 PDF/).check();
  await page.getByRole("button", { name: "创建解析任务" }).click();

  const next = page.locator(".workflow-next");
  const refresh = page.getByRole("button", { name: "刷新解析状态", exact: true });
  await expect(refresh).toHaveCount(1, workspaceLoad);
  await expect(next.getByRole("button", { name: "刷新解析状态" })).toBeEnabled();
  statusUnavailable = true;
  await refresh.click();
  await expect(next.getByRole("status")).toContainText("无法刷新本机 PDF 状态");
  statusUnavailable = false;
  parsed = true;
  await refresh.click();
  const citation = page.getByRole("button", { name: "构建双向两层引文图", exact: true });
  await expect(citation).toHaveCount(1);
  await expect(next.getByRole("button", { name: "构建双向两层引文图" })).toHaveClass(/cm-action--primary/);
  expect(await page.locator(".pdf-task-progress").evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  page.once("dialog", (dialog) => dialog.accept());
  await citation.click();
  try {
    const busy = next.getByRole("button", { name: "正在构建引文图…" });
    await expect(busy).toBeDisabled();
    await expect(busy).toHaveAttribute("aria-busy", "true");
  } finally {
    releaseCitation();
  }
  await expect(citation).toBeEnabled();
});

test("keeps the bridge artifact flow readable beside its research rail", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const flow = page.locator(".workflow-artifact-flow");
  await expect(flow).toBeVisible(lazyWorkspaceContentLoad);
  await expect(flow.locator("article")).toHaveCount(4);
  expect(await flow.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(2);
  expect(await flow.locator(":scope > i").evaluateAll((arrows) => arrows.every((arrow) => getComputedStyle(arrow).display === "none"))).toBe(true);
});

test("keeps the evidence proof chain readable beside its research rail", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: "04 证据核对" }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-reader/, workspaceLoad);

  const proofTrack = page.locator(".reader-proof-track");
  await expect(proofTrack).toBeVisible(lazyWorkspaceContentLoad);
  await expect(proofTrack.locator(".reader-proof-station")).toHaveCount(5);
  expect(await proofTrack.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(3);
  expect(await proofTrack.evaluate((element) => getComputedStyle(element, "::before").display)).toBe("none");
  const returnToMap = page.getByRole("button", { name: "返回文献星图", exact: true });
  await expect(returnToMap).toHaveClass(/cm-action--primary/);
  expect(await returnToMap.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(13);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("keeps an empty task explicit, then renders a redacted exported condition matrix", async ({ page }) => {
  const importInput = await openEditableTaskDefinition(page);

  await expect(page.locator(".mission-preview")).toContainText("尚未导入条件簇");
  await importInput.setInputFiles(routeDiagnosticsExport);

  await expect(page.locator(".rail-status")).toContainText("已导入 route_diagnostics.json");
  await expect(importInput).toHaveValue("");
  await expect(page.locator(".mission-preview")).toContainText("条件簇");
  await expect(page.locator(".mission-preview")).toContainText("1");
  const receipt = page.getByLabel("已导入工件摘要");
  await expect(receipt).toContainText("route_diagnostics.json");
  await expect(receipt).toContainText("工件自述版本");
  await expect(receipt).toContainText("1.0");
  await expect(receipt).toContainText("工件自述生成时间");
  await expect(receipt).toContainText("不会验证完整性、作者身份或科学结论");
  await expect(receipt).toContainText("文件大小");
  await expect(receipt).toContainText("可显示数据项");
  await expect(page.locator("body")).not.toContainText("Synthetic demonstration only; no paper text is included.");

  await page.getByRole("button", { name: "下一步：进入舰桥编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.getByLabel("当前本地工件")).toContainText("route_diagnostics.json");
  await expect(page.getByLabel("当前本地工件")).toContainText("1.0");
  await expect(page.getByLabel("当前本地工件")).toContainText("工件自述版本");
});

test("safely rejects malformed UI JSON without replacing the imported condition artifact", async ({ page }) => {
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles(routeDiagnosticsExport);
  await expect(page.locator(".rail-status")).toContainText("已导入 route_diagnostics.json");

  await importInput.setInputFiles({
    name: "malformed-ui.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"mission":'),
  });

  await expect(page.locator(".rail-status")).toContainText("该 UI JSON 未通过格式校验");
  await expect(page.locator(".rail-status")).not.toContainText("SyntaxError");
  await expect(page.locator(".mission-preview")).toContainText("条件簇");
  await expect(page.locator(".mission-preview")).toContainText("1");
  await expect(page.getByLabel("已导入工件摘要")).toContainText("route_diagnostics.json");
});

test("opens the pending-condition navigation card through the keyboard without starting execution", async ({ page }) => {
  await openMissionDefinitionWithPendingArtifacts(page);
  const next = page.getByRole("button", { name: "下一步：导入条件工件" });
  await next.focus();
  await page.keyboard.press("Enter");

  await expect(page.locator("details.mission-api")).toHaveAttribute("open", "");
  await expect(page.locator(".import-control input[type=file]")).toBeVisible();
  await expect(page.locator(".rail-status")).toContainText("已打开高级手动受控执行");
});

test("opens a read-only evaluation audit from frozen-corpus readiness without claiming a metric", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles({
    name: "frozen-evaluation-readiness.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "1.0",
      mission: { mission_id: "frozen-evaluation-demo", question: "Inspect evaluation readiness only.", material: "BiFeO3", property_name: "phase stability", scope: "private review cohort" },
      audit_summary: {
        submission_readiness: {
          question_set: { reviewed_question_count: 8, included_question_count: 7, excluded_question_count: 1, included_evidence_level_counts: { literature_mentioned: 1, data_supported: 4, reproducible: 1, already_reproduced: 1 }, freeze_gate: "ready_for_question_level_evaluation_not_metrics" },
          frozen_corpus: { expected_document_count: 90, frozen_document_count: 90, expected_count_matched: true, document_id_uniqueness_valid: true, doi_present_count: 88, doi_missing_count: 2, authorized_access_boundary_valid: true, evaluation_gate: "ready_for_private_human_annotation" },
        },
      },
    })),
  });

  await expect(page.locator(".rail-status")).toContainText("已导入 frozen-evaluation-readiness.json");
  await page.getByRole("button", { name: "05 研究拓展" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-horizon/, workspaceLoad);
  const audit = page.getByLabel("审计与评测");
  await audit.locator("summary").click();
  await expect(page.getByLabel("评测前置门禁")).toContainText("可开始私有人工标注");
  await expect(audit).toContainText("未生成");
  await expect(page.getByLabel("评测下一步")).toContainText("在私有位置完成相关性金标准标注");
  await expect(audit).toContainText("不代表任何指标已经生成");
  expect(apiRequests).toEqual([]);
});

test("reviews a local question set without network activity or implicit approval", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  await openMissionDefinitionWithPendingArtifacts(page);
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);

  const desk = page.getByLabel("冻结问题集人工审核台");
  await desk.locator("summary").click();
  await desk.locator("input[type=file]").setInputFiles({
    name: "bfo-question-review.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "cosmatter.question-set-review/v1",
      question_set_id: "bfo-ui-review-v1",
      material_family: "BiFeO3",
      trust_status: "blank_human_question_set_review_not_frozen",
      review_instructions: { decision: "Review every question.", checks: "Complete every check.", note: "Record a reason." },
      questions: [1, 2, 3].map((number) => ({
        question_id: `bfo-${number}`,
        question: `Which source-located BiFeO3 phase-transition value is reported for bounded condition ${number}?`,
        material: "BiFeO3",
        target_property: "phase-transition temperature",
        scope: `Condition ${number}; compare source-located reports only.`,
        intended_evidence_level: "data_supported",
        review_decision: "unreviewed",
        review_checks: { answerable_by_literature: null, material_explicit: null, target_property_explicit: null, scope_bounded: null, avoids_assumed_answer: null },
        review_note: "",
      })),
    })),
  });

  await expect(desk).toContainText("0/3");
  const attestation = desk.locator(".question-review-release input[type=checkbox]");
  await expect(attestation).toBeDisabled();
  const items = desk.locator(".question-review-item");
  await expect(items).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    const item = items.nth(index);
    await item.locator("select").first().selectOption("include");
    for (const check of await item.locator("fieldset select").all()) await check.selectOption("true");
    await item.locator("textarea").fill("Independently checked for wording, scope, and a source-locatable answer.");
  }
  await expect(desk).toContainText("3/3");
  await expect(attestation).toBeEnabled();
  await expect(desk.getByRole("button", { name: "导出本地审核草稿" })).toHaveClass(/cm-action--primary/);
  await attestation.check();
  await expect(desk.getByRole("button", { name: "导出可冻结审核 JSON" })).toBeVisible();
  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /^01 任务定义/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await desk.locator("summary").click();
  await expect(desk).toContainText("已恢复本浏览器会话中的审核草稿");
  await expect(desk.locator(".question-review-item").first().locator("select").first()).toHaveValue("include");
  await expect(desk.locator(".question-review-release input[type=checkbox]")).not.toBeChecked();
  await expect(desk.getByRole("button", { name: "导出本地审核草稿" })).toBeVisible();
  await desk.locator("input[type=file]").setInputFiles({ name: "invalid-review.json", mimeType: "application/json", buffer: Buffer.from("{not-json") });
  await expect(desk.getByRole("alert")).toContainText("没有导入任何内容");
  await expect(desk.locator(".question-review-item")).toHaveCount(3);
  const clearQuestionDraft = desk.getByRole("button", { name: "清除本会话草稿" });
  await expect(clearQuestionDraft).toHaveClass(/cm-action--quiet/);
  await clearQuestionDraft.click();
  await expect(desk.locator(".question-review-item")).toHaveCount(3);
  const confirmClearQuestionDraft = desk.getByRole("button", { name: "再次点击确认清除" });
  await expect(confirmClearQuestionDraft).toHaveClass(/cm-action--danger/);
  await confirmClearQuestionDraft.click();
  await expect(desk.locator(".question-review-item")).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});

test("reviews frozen-corpus relevance locally with exact bibliography binding and no implicit attestation", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  await openMissionDefinitionWithPendingArtifacts(page);

  const instructions = {
    retrieval_relevance: "Mark relevance after reading the authorized paper.",
    evidence_annotations: "Preserve reviewed evidence annotations.",
    material_fact_annotations: "Preserve reviewed material-fact annotations.",
    comparison_annotations: "Preserve reviewed comparisons.",
    gap_annotations: "Preserve reviewed gap annotations.",
  };
  const gold = {
    schema_version: "1.0",
    mission_id: "mission-bfo-corpus-review",
    corpus_id: "bfo-ui-corpus-3",
    trust_status: "blank_human_annotation_template_not_evaluation_result",
    annotation_instructions: instructions,
    documents: [1, 2, 3].map((number) => ({
      document_id: `bfo-paper-${number}`,
      retrieval_relevance: "unreviewed",
      evidence_annotations: number === 1 ? [{ retained: "opaque" }] : [],
      material_fact_annotations: [],
      comparison_annotations: [],
      gap_annotations: [],
    })),
  };
  const manifest = {
    schema_version: "1.0",
    mission_id: gold.mission_id,
    corpus_id: gold.corpus_id,
    material: "BiFeO3",
    trust_status: "human_reviewed_authorized_corpus_manifest_not_evaluation_result",
    access_boundary: "institutional_access_local_review_only_no_fulltext_redistribution",
    documents: [1, 2, 3].map((number) => ({
      document_id: `bfo-paper-${number}`,
      title: `Source-located BiFeO3 transition study ${number}`,
      doi: number === 1 ? "10.1000/bfo.1" : null,
      access_policy: "institutional_access_internal_review_only",
    })),
  };

  const desk = page.getByLabel("冻结语料相关性人工审核台");
  await desk.locator("summary").click();
  const fileInputs = desk.locator("input[type=file]");
  await fileInputs.nth(0).setInputFiles({ name: "bfo-human-gold.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(gold)) });
  await expect(desk).toContainText("0/3");
  await fileInputs.nth(1).setInputFiles({ name: "bfo-corpus-manifest.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(manifest)) });
  await expect(desk).toContainText("Source-located BiFeO3 transition study 1");
  await expect(desk).toContainText("10.1000/bfo.1");

  const attestation = desk.locator(".corpus-review-release input[type=checkbox]");
  await expect(attestation).toBeDisabled();
  const items = desk.locator(".corpus-review-item");
  await expect(items).toHaveCount(3);
  await items.nth(0).locator("select").selectOption("relevant");
  await items.nth(1).locator("select").selectOption("partially_relevant");
  await items.nth(2).locator("select").selectOption("not_relevant");
  await expect(desk).toContainText("3/3");
  await expect(attestation).toBeEnabled();
  await expect(desk.getByRole("button", { name: "导出本地相关性草稿" })).toHaveClass(/cm-action--primary/);
  await attestation.check();
  await expect(desk.getByRole("button", { name: "导出可评测金标准" })).toBeVisible();

  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /^01 任务定义/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await desk.locator("summary").click();
  await expect(desk).toContainText("已恢复本浏览器会话中的相关性草稿");
  await expect(desk.locator(".corpus-review-item").first().locator("select")).toHaveValue("relevant");
  await expect(desk.locator(".corpus-review-release input[type=checkbox]")).not.toBeChecked();
  await expect(desk.getByRole("button", { name: "导出本地相关性草稿" })).toBeVisible();

  await desk.locator("input[type=file]").first().setInputFiles({ name: "invalid-human-gold.json", mimeType: "application/json", buffer: Buffer.from("{not-json") });
  await expect(desk.getByRole("alert")).toContainText("当前草稿保持不变");
  await expect(desk.locator(".corpus-review-item")).toHaveCount(3);
  const clearCorpusDraft = desk.getByRole("button", { name: "清除本会话草稿" });
  await expect(clearCorpusDraft).toHaveClass(/cm-action--quiet/);
  await clearCorpusDraft.click();
  await expect(desk.locator(".corpus-review-item")).toHaveCount(3);
  const confirmClearCorpusDraft = desk.getByRole("button", { name: "再次点击确认清除" });
  await expect(confirmClearCorpusDraft).toHaveClass(/cm-action--danger/);
  await confirmClearCorpusDraft.click();
  await expect(desk.locator(".corpus-review-item")).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});

test("renders cross-source reconciliation revisions in the map without calling a local API", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles({
    name: "reconciliation-summary.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "1.0",
      generated_at: "2026-08-31T09:30:00Z",
      mission: { mission_id: "reconciliation-demo", question: "Inspect reviewed bibliography mappings.", material: "BiFeO3", property_name: "phase stability", scope: "synthetic UI fixture" },
      literature_graph: { trust_status: "human_reviewed_graph_projection", nodes: [{ node_id: "paper:demo-paper", kind: "candidate_paper", label: "Reviewable synthetic candidate", trust_status: "candidate_metadata_not_scientific_evidence" }], edges: [] },
      evidence_cards: [{ evidence_id: "evidence-demo", claim: "A reviewer-bound bibliography identity check.", stance: "context", conditions: {}, quote: "Identity mapping recorded for the selected paper.", review_status: "accepted", provenance: { document_id: "demo-paper", locator: "metadata_record:1", source: "human review", access_policy: "authorized" } }],
      relation_reconciliation: {
        trust_status: "human_reviewed_cross_source_identity_not_scientific_evidence",
        source: { evidence_id: "evidence-demo", document_id: "demo-paper" },
        mappings: [{ openalex_work_id: "https://openalex.org/W123", crossref_doi: "10.1000/demo", status: "conflict", basis: "Human review recorded a DOI disagreement." }],
        revision_history: [{ revision: 1, recorded_at: "2026-08-31T09:30:00Z", mapping_count: 1, status_counts: { matched: 0, conflict: 1, unresolved: 0 } }],
      },
      audit_summary: {
        evaluation: {
          evidence_quality: { trust_status: "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit", evidence_count: 8, predicted_contradiction_count: 3, citation_precision: 0.875, condition_completeness: 0.75, contradiction_precision: 2 / 3 },
        },
        submission_readiness: {
          question_set: { reviewed_question_count: 8, included_question_count: 7, excluded_question_count: 1, included_evidence_level_counts: { literature_mentioned: 1, data_supported: 4, reproducible: 1, already_reproduced: 1 }, freeze_gate: "ready_for_question_level_evaluation_not_metrics" },
          frozen_corpus: { expected_document_count: 90, frozen_document_count: 90, expected_count_matched: true, document_id_uniqueness_valid: true, doi_present_count: 88, doi_missing_count: 2, authorized_access_boundary_valid: true, evaluation_gate: "ready_for_private_human_annotation" },
          human_annotation: { frozen_document_count: 90, annotation_file_status: "human_reviewed_gold_standard_for_evaluation", relevance_counts: { unreviewed: 0, relevant: 50, partially_relevant: 20, not_relevant: 20 }, documents_with_evidence_annotations: 30, documents_with_material_fact_annotations: 25, documents_with_comparison_annotations: 18, documents_with_gap_annotations: 5, relevance_evaluation_gate: "ready_for_human_retrieval_evaluation" },
          bibliographic_source: { frozen_document_count: 90, documents_with_reviewed_bibliographic_source: 90, distinct_bibliographic_source_count: 3, bibliographic_source_coverage_gate: "ready_for_source_traceable_evaluation" },
        },
      },
    })),
  });

  await expect(page.locator(".rail-status")).toContainText("已导入 reconciliation-summary.json");
  await page.getByRole("button", { name: "03 文献星图" }).click();
  await expect(page.locator(".frontier-literature-workbench")).toBeVisible({ timeout: 30_000 });
  const route = page.getByLabel("舰队阅读航道");
  await expect(route).toContainText("航线 01");
  await expect(route).toContainText("完成人工筛选");
  expect(await route.locator(".fleet-formation-slot").evaluateAll((slots) => slots.every((slot) => {
    const bounds = slot.getBoundingClientRect();
    return [...slot.children].every((child) => child.getBoundingClientRect().bottom <= bounds.bottom + 1);
  }))).toBe(true);
  const panel = page.getByLabel("跨源标识人工对账");
  await expect(panel).toContainText("冲突，未合并");
  const summary = panel.locator("summary");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(panel).toContainText("修订摘要（1 次）");
  await expect(panel).toContainText("映射 1 · 匹配 0 · 冲突 1 · 未决 0");
  await page.getByRole("button", { name: "05 研究拓展" }).click();
  const audit = page.locator("details.evaluation-audit");
  await expect(audit).toBeVisible({ timeout: 30_000 });
  await audit.locator("summary").click();
  await expect(audit).toContainText("引用定位");
  await expect(audit).toContainText("88%");
  await expect(audit).toContainText("已复核证据");
  const readiness = page.getByLabel("评测前置门禁");
  await expect(readiness).toContainText("冻结问题集");
  await expect(readiness).toContainText("纳入 7/8");
  await expect(readiness).toContainText("可开始逐题评测；指标仍未生成");
  await expect(readiness).toContainText("1 / 4 / 1 / 1");
  await expect(readiness).toContainText("90/90");
  await expect(readiness).toContainText("可开始私有人工标注");
  await expect(readiness).toContainText("相关性标注已齐备");
  await expect(readiness).toContainText("书目来源覆盖已齐备");
  await expect(audit).toContainText("不代表任何指标已经生成");
  expect(apiRequests).toEqual([]);
});

test("renders title-only candidate duplicates as an unmerged review queue", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles({
    name: "candidate-duplicate-queue.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "1.0",
      mission: { mission_id: "duplicate-demo", question: "Review duplicate candidate identities.", material: "BiFeO3", property_name: "phase stability", scope: "synthetic UI fixture" },
      literature_graph: {
        trust_status: "candidate_metadata_not_scientific_evidence",
        nodes: [
          { node_id: "paper:doc-a", kind: "candidate_paper", label: "Shared title", trust_status: "candidate_metadata_not_scientific_evidence" },
          { node_id: "paper:doc-b", kind: "candidate_paper", label: "Shared title", trust_status: "candidate_metadata_not_scientific_evidence" },
        ], edges: [],
      },
      candidate_duplicate_queue: {
        trust_status: "derived_exact_title_duplicate_queue_not_scientific_evidence",
        group_count: 1,
        groups: [{ group_id: "candidate_duplicate_aaaaaaaaaaaaaaaaaaaaaaaa", document_ids: ["doc-a", "doc-b"], doi_state: "title_only_review_required", canonical_document_id: null, alias_document_ids: [] }],
        summary: { conflicting_doi_review_required_count: 0, partial_doi_review_required_count: 0, same_doi_merge_allowed_count: 0, title_only_review_required_count: 1 },
      },
    })),
  });
  await page.getByRole("button", { name: "03 文献星图" }).click();
  const panel = page.getByLabel("候选重复待对账");
  await expect(panel).toBeVisible(lazyWorkspaceContentLoad);
  await expect(panel).toContainText("题名相同不是同一篇文献");
  await expect(panel).toContainText("仅题名相同，待人工对账");
  await expect(panel).toContainText("未决，未合并");
  expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(apiRequests).toEqual([]);
});
