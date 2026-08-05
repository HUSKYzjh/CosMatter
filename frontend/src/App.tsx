import { For, Show, createMemo, createSignal, onMount } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { GraphNetwork } from "./GraphNetwork";
import { PaperReader } from "./PaperReader";
import { ResearchExpansion } from "./ResearchExpansion";
import { ResearchWorkflow } from "./ResearchWorkflow";
import { approveLivePlan, createLiveMission, draftLivePlan, executeApprovedQuery, fetchLiveUiBundle, getLocalApiStatus, localApiEnabled, type RetrievalSource } from "./localApi";
import { demoBundle, readBundle, type ImportedBundle } from "./model";
import { zh } from "./zh";

type Theme = "light" | "dark" | "eye";
type View = "discover" | "workflow" | "graph" | "reader" | "horizon";
type DiscoveryKind = "scope" | "condition" | "evidence" | "question";
interface DiscoveryObject { id: string; kind: DiscoveryKind; index: number; title: string; detail: string; footer: string; }
const bi = (_zh: string, en: string) => zh(en);
const EXAMPLES = [
  bi("为什么不同薄膜研究对 BiFeO3 应变相变有相反结论？", "Why do thin-film BiFeO3 strain studies reach opposite phase conclusions?"),
  bi("氧空位如何改变钙钛矿薄膜的铁电相稳定性？", "How do oxygen vacancies change ferroelectric phase stability in perovskite films?"),
  bi("如何比较不同表征方法得到的材料相边界？", "How can phase boundaries inferred from different characterisation methods be compared?"),
  bi("哪些实验条件会导致材料文献结论不能直接比较？", "Which experimental conditions make material-literature conclusions non-comparable?"),
];
const KIND_LABEL: Record<DiscoveryKind, string> = { scope: bi("任务范围", "Mission scope"), condition: bi("条件差分", "Condition differential"), evidence: bi("已批准证据", "Approved evidence"), question: bi("待核查问题", "Open verification question") };
const SOURCES: Array<{ id: RetrievalSource; label: string; provider: string }> = [
  { id: "sciverse", label: "Sciverse / agentic retrieval", provider: "sciverse" },
  { id: "openalex", label: "OpenAlex / scholarly metadata", provider: "openalex" },
  { id: "crossref", label: "Crossref / bibliographic metadata", provider: "crossref" },
];

function createObjects(bundle: ImportedBundle): DiscoveryObject[] {
  const { mission } = bundle;
  return [
    { id: "scope", kind: "scope", index: 1, title: mission.material, detail: bi(`关注性质：${mission.property}。当前范围：${mission.scope}。`, `Property: ${mission.property}. Current scope: ${mission.scope}.`), footer: bi("任务简报，本地任务边界", "Mission brief, local task boundary") },
    { id: "condition", kind: "condition", index: 2, title: bi("条件差分", "Condition differential"), detail: bi("应变、厚度、衬底、氧空位与表征方法需显式记录后才能比较。", "Strain, thickness, substrate, oxygen vacancies, and measurement method must be recorded before comparison."), footer: bi("条件矩阵，待审查补全", "Condition matrix, awaiting review") },
    { id: "evidence", kind: "evidence", index: 3, title: bi("证据门禁", "Evidence gate"), detail: bi("只显示具有来源定位、条件字段和 accepted 审查结论的短证据。", "Only short evidence with source locations, condition fields, and accepted review is shown."), footer: bi("证据卡，不载入全文", "Evidence card, no full text loaded") },
    { id: "question", kind: "question", index: 4, title: bi("反例航线", "Counterexample route"), detail: bi("主检索与反例检索计划必须由人类批准；界面不会自动推断。", "Primary and counterexample queries require human approval; the interface does not infer them automatically."), footer: bi("飞行计划，批准后执行", "Flight plan, execute after approval") },
  ];
}

export function App() {
  const [bundle, setBundle] = createSignal<ImportedBundle>(demoBundle);
  const [question, setQuestion] = createSignal(demoBundle.mission.question);
  const [theme, setTheme] = createSignal<Theme>("light");
  const [view, setView] = createSignal<View>("discover");
  const [status, setStatus] = createSignal(bi("当前显示合成演示对象，尚未发起网络请求。", "Showing synthetic demo objects; no network request has been made."));
  const [filter, setFilter] = createSignal<DiscoveryKind | "all">("all");
  const [apiSummary, setApiSummary] = createSignal(bi("本地 API 未启用。请用 --api 启动预览并打开 ?api=local。", "Local API is disabled. Start preview with --api and open ?api=local."));
  const [apiProviders, setApiProviders] = createSignal<Record<string, boolean>>({});
  const [retrievalSources, setRetrievalSources] = createSignal<RetrievalSource[]>(["crossref"]);
  const [liveRunId, setLiveRunId] = createSignal<string | null>(null);
  const [draftContent, setDraftContent] = createSignal("");
  const [reviewedPlan, setReviewedPlan] = createSignal("");
  const [planApproved, setPlanApproved] = createSignal(false);
  const [approvedQueryCount, setApprovedQueryCount] = createSignal(0);
  const objects = createMemo(() => createObjects(bundle()));
  const visibleObjects = createMemo(() => objects().filter((item) => filter() === "all" || item.kind === filter()));

  onMount(() => {
    if (localApiEnabled()) void getLocalApiStatus().then((result) => {
      setApiProviders(result.providers);
      const ready = SOURCES.filter((source) => result.providers[source.provider]).map((source) => source.id);
      setRetrievalSources(ready.length ? ready : ["crossref"]);
      setApiSummary(bi(`本地 API 已就绪：DeepSeek ${result.providers.deepseek ? "已配置" : "未配置"}；Sciverse ${result.providers.sciverse ? "已配置" : "未配置"}；OpenAlex ${result.providers.openalex ? "已配置" : "未配置"}；Crossref 可用。`, `Local API ready: DeepSeek ${result.providers.deepseek ? "configured" : "not configured"}; Sciverse ${result.providers.sciverse ? "configured" : "not configured"}; OpenAlex ${result.providers.openalex ? "configured" : "not configured"}; Crossref available.`));
    }).catch((error: unknown) => setApiSummary(error instanceof Error ? error.message : bi("无法连接本地 API。", "Unable to reach the local API.")));
    if (new URLSearchParams(window.location.search).get("ui") !== "server") return;
    void fetch("./ui.json", { cache: "no-store" }).then((response) => { if (!response.ok) throw new Error(bi("所选本地 UI 数据不可用。", "The selected local UI bundle is unavailable.")); return response.json(); }).then((payload) => { const imported = readBundle(payload, "loopback"); setBundle(imported); setQuestion(imported.mission.question); setStatus(bi("已载入本地回环 UI 数据，未连接外部服务。", "Loaded loopback UI data; no external service was contacted.")); }).catch((error: unknown) => setStatus(error instanceof Error ? error.message : bi("无法载入本地 UI 数据。", "Unable to load local UI data.")));
  });

  async function launchLiveMission() { try { const result = await createLiveMission({ question: question().trim(), material: bundle().mission.material, property: bundle().mission.property, scope: bundle().mission.scope }); setLiveRunId(result.run_id); setDraftContent(""); setReviewedPlan(""); setPlanApproved(false); setApprovedQueryCount(0); setStatus(bi(`已启动本地 API 任务 ${result.run_id}。`, `Local API mission ${result.run_id} launched.`)); } catch (error) { setStatus(error instanceof Error ? error.message : bi("无法启动本地 API 任务。", "Unable to launch the local API mission.")); } }
  async function requestPlanDraft() { const runId = liveRunId(); if (!runId) return; try { const result = await draftLivePlan(runId); setDraftContent(result.content); setStatus(bi("DeepSeek 返回未受信草案；请审核并替换为有效 JSON 后批准。", "DeepSeek returned an untrusted draft. Review and replace it with valid JSON before approval.")); } catch (error) { setStatus(error instanceof Error ? error.message : bi("无法请求计划草案。", "Unable to request a plan draft.")); } }
  async function approveReviewedPlan() { const runId = liveRunId(); if (!runId) return; try { const result = await approveLivePlan(runId, JSON.parse(reviewedPlan())); setPlanApproved(true); setApprovedQueryCount(result.queries.length); setStatus(bi(`已批准人工复核计划，含 ${result.queries.length} 条主检索式。`, `Human-reviewed plan approved with ${result.queries.length} primary queries.`)); } catch (error) { setStatus(error instanceof Error ? error.message : bi("复核计划必须是有效 JSON。", "The reviewed plan must be valid JSON.")); } }
  async function executeApprovedQueries() { const runId = liveRunId(); const queryCount = approvedQueryCount(); const sources = retrievalSources(); if (!runId || !planApproved() || !queryCount || !sources.length) return; try { let received = 0; for (let index = 0; index < queryCount; index += 1) { setStatus(bi(`正在执行第 ${index + 1}/${queryCount} 条已批准检索，来源：${sources.join("、")}；仅收集候选元数据。`, `Running approved query ${index + 1}/${queryCount} via ${sources.join(", ")}; candidate metadata only.`)); const result = await executeApprovedQuery(runId, index, sources); received += result.candidate_count; } const payload = await fetchLiveUiBundle(runId); const imported = readBundle(payload, "loopback"); setBundle(imported); setStatus(bi(`已完成 ${queryCount} 条检索，收到 ${received} 条候选元数据（去重前）；图谱已更新。`, `Completed ${queryCount} queries; received ${received} candidate records before deduplication. The graph is updated.`)); setView("graph"); } catch (error) { setStatus(error instanceof Error ? error.message : bi("无法执行已批准检索。", "Unable to execute the approved retrieval set.")); } }
  function toggleSource(source: RetrievalSource) { setRetrievalSources((current) => current.includes(source) ? current.filter((item) => item !== source) : [...current, source]); }
  function beginDiscovery() { const trimmed = question().trim(); if (!trimmed) { setStatus(bi("请先输入可审查的研究问题。", "Enter an auditable research question first.")); return; } setBundle((current) => ({ ...current, mission: { ...current.mission, question: trimmed } })); setStatus(bi("已更新本地发现台；尚未调用模型、检索服务或第三方 API。", "Local discovery view updated; no model, retrieval service, or third-party API was called.")); }
  function loadExample(example: string) { setQuestion(example); setStatus(bi("已载入示例问题；点击“更新发现台”后才改变本地预览。", "Example question loaded; select Update discovery to change the local preview.")); }
  async function importBundle(file: File | undefined) { if (!file) return; try { const parsed = readBundle(JSON.parse(await file.text())); setBundle(parsed); setQuestion(parsed.mission.question); setStatus(bi(`已导入 ${file.name}；仅解析浏览器本地选择的 JSON。`, `Imported ${file.name}; only the browser-selected local JSON was parsed.`)); } catch (error) { setStatus(error instanceof Error ? error.message : bi("无法解析该 JSON 工件。", "Unable to parse this JSON artifact.")); } }

  return <div class={`workbench theme-${theme()} ${view() === "graph" ? "graph-focus" : ""}`}>
    <Show when={view() !== "graph"}><aside class="research-rail" aria-label={bi("研究控制栏", "Research controls")}>
      <a class="wordmark" href="/" aria-label={bi("CosMatter 研究发现页", "CosMatter research discovery")}>Cos<span>Matter</span></a><p class="rail-kicker">材料科学发现 / MATERIALS DISCOVERY</p>
      <nav class="view-switcher" aria-label={bi("工作台视图", "Workbench views")}><button type="button" classList={{ active: view() === "discover" }} onClick={() => setView("discover")}>{bi("发现", "Discover")}</button><button type="button" classList={{ active: view() === "workflow" }} onClick={() => setView("workflow")}>{bi("工作流", "Workflow")}</button><button type="button" classList={{ active: view() === "graph" }} onClick={() => setView("graph")}>{bi("图谱", "Graph")}</button><button type="button" classList={{ active: view() === "reader" }} onClick={() => setView("reader")}>{bi("阅读", "Reading")}</button><button type="button" classList={{ active: view() === "horizon" }} onClick={() => setView("horizon")}>{bi("拓展", "Horizon")}</button></nav>
      <section class="rail-stats" aria-label={bi("任务摘要", "Mission summary")}><div><strong>{bundle().status?.missionState ?? "LOCAL"}</strong><span>{bi("任务状态", "mission state")}</span></div><div><strong>{String(bundle().stations.length).padStart(2, "0")}</strong><span>{bi("站点", "stations")}</span></div><div><strong>{String(bundle().evidenceCards.length).padStart(2, "0")}</strong><span>{bi("已批准证据", "approved evidence")}</span></div><div><strong>{String(bundle().timeline.length).padStart(2, "0")}</strong><span>{bi("时间线事件", "timeline events")}</span></div></section>
      <label class="question-label">{bi("研究问题", "Research question")}<textarea value={question()} onInput={(event) => setQuestion(event.currentTarget.value)} rows="4" /></label><button class="primary-action" type="button" onClick={beginDiscovery}>{bi("更新发现台", "Update discovery")}</button>
      <Show when={localApiEnabled()}><section class="live-api-panel" aria-live="polite"><small>{apiSummary()}</small><button class="primary-action" type="button" onClick={() => void launchLiveMission()}>{bi("启动 API 任务", "Launch API mission")}</button><Show when={liveRunId()}><small>{bi(`任务 ${liveRunId()}；密钥始终留在回环后端。`, `Run ${liveRunId()}; provider keys stay on the loopback backend.`)}</small><button type="button" disabled={!apiProviders().deepseek} onClick={() => void requestPlanDraft()}>{bi("用 DeepSeek 起草计划", "Draft plan with DeepSeek")}</button><Show when={draftContent()}><label>{bi("未受信 LLM 草案", "Untrusted LLM draft")}<textarea value={draftContent()} readOnly rows="5" /></label></Show><label>{bi("人工复核计划 JSON", "Human-reviewed plan JSON")}<textarea value={reviewedPlan()} onInput={(event) => setReviewedPlan(event.currentTarget.value)} rows="7" placeholder='{"subquestions":["..."],"queries":["..."],"counter_queries":["..."]}' /></label><button type="button" onClick={() => void approveReviewedPlan()}>{bi("批准复核计划", "Approve reviewed plan")}</button><Show when={planApproved()}><fieldset class="retrieval-sources"><legend>{bi("检索来源（明确执行后才联网）", "Retrieval sources (network only after explicit execution)")}</legend><For each={SOURCES}>{(source) => <label><input type="checkbox" checked={retrievalSources().includes(source.id)} disabled={!apiProviders()[source.provider]} onChange={() => toggleSource(source.id)} />{source.label}<small>{apiProviders()[source.provider] ? bi("可用", "available") : bi("未配置", "not configured")}</small></label>}</For></fieldset><button class="primary-action" type="button" disabled={!retrievalSources().length} onClick={() => void executeApprovedQueries()}>{bi(`执行 ${approvedQueryCount()} 条已批准检索`, `Run ${approvedQueryCount()} approved queries`)}</button></Show></Show></section></Show>
      <section class="examples" aria-labelledby="examples-title"><p id="examples-title" class="rail-kicker">建议问题 / SUGGESTED QUESTIONS</p><For each={EXAMPLES}>{(example, index) => <button type="button" onClick={() => loadExample(example)}><span>{String(index() + 1).padStart(2, "0")}</span>{example}</button>}</For></section><label class="import-control">{bi("导入已脱敏 UI JSON", "Import redacted UI JSON")}<input type="file" accept="application/json,.json" onChange={(event) => void importBundle(event.currentTarget.files?.[0])} /></label><div class="rail-footer"><label>{bi("主题", "Theme")}<select value={theme()} onChange={(event) => setTheme(event.currentTarget.value as Theme)}><option value="light">{bi("浅色", "Light")}</option><option value="dark">{bi("深色", "Dark")}</option><option value="eye">{bi("护眼", "Eye care")}</option></select></label><small>{bi("密钥、全文和运行日志不会进入浏览器。", "Keys, full text, and runtime logs never enter the browser.")}</small></div>
    </aside></Show>
    <Show when={view() === "discover"} fallback={view() === "workflow" ? <ResearchWorkflow bundle={bundle()} /> : view() === "graph" ? <GraphNetwork bundle={bundle()} theme={theme()} onNavigate={setView} /> : view() === "reader" ? <PaperReader bundle={bundle()} /> : <ResearchExpansion bundle={bundle()} />}><main class="discovery-stage"><FleetDecoration kind="discover" /><header class="stage-header"><div><p class="stage-kicker">COSMATTER / 研究发现 RESEARCH DISCOVERY</p><h1>{bi("发现材料分歧", "Discover material disagreement")}</h1><p>{bundle().mission.question}</p></div><div class="stage-tools"><button type="button" aria-label={bi("筛选研究对象", "Filter research objects")}>{"\u7b5b\u9009"}</button><button type="button" aria-label={bi("聚焦画布", "Focus canvas")}>{"\u805a\u7126"}</button><button type="button" aria-label={bi("放大画布", "Zoom canvas")}>+</button></div></header><section class="scope-strip" aria-label={bi("当前任务范围", "Current mission scope")}><span>{bi("材料", "Material")} <strong>{bundle().mission.material}</strong></span><span>{bi("性质", "Property")} <strong>{bundle().mission.property}</strong></span><span>{bi("范围", "Scope")} <strong>{bundle().mission.scope}</strong></span><span>{bundle().source === "demo" ? bi("合成演示工件", "Synthetic demo artifact") : bi("本地导入工件", "Local imported artifact")}</span></section><section class="discovery-toolbar" aria-label={bi("研究对象筛选", "Research-object filters")}><p>{status()}</p><div class="filter-group"><For each={["all", "scope", "condition", "evidence", "question"] as const}>{(kind) => <button classList={{ selected: filter() === kind }} type="button" onClick={() => setFilter(kind)}>{kind === "all" ? bi("全部对象", "All objects") : KIND_LABEL[kind]}</button>}</For></div></section><section class="discovery-canvas" aria-label={bi("研究发现对象", "Research discovery objects")}><Show when={visibleObjects().length} fallback={<p class="empty-state">{bi("当前筛选没有可显示对象。", "No objects match the current filter.")}</p>}><For each={visibleObjects()}>{(item) => <article class={`discovery-object kind-${item.kind}`}><header><span>{String(item.index).padStart(2, "0")}</span><small>{KIND_LABEL[item.kind]}</small></header><h2>{item.title}</h2><p>{item.detail}</p><footer>{item.footer}<b>→</b></footer></article>}</For></Show></section><footer class="stage-note">{bi("对象只由本地任务工件派生，是导航信息，不构成材料科学结论。", "Objects are derived from local mission artifacts for navigation and are not material-science conclusions.")}</footer></main></Show>
  </div>;
}