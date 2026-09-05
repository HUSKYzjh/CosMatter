import { For, Show, createEffect, createSignal, onCleanup, onMount, untrack } from "solid-js";
import { uiLanguage } from "./zh";
import { LAUNCH_STAGES, launchModeStatus, stageForLaunchMode, type LaunchPreviewStage } from "./launchStages";
import { isCurrentCandidateResponse } from "./launchCandidateRequest";
import { isLaunchMissionReady, launchMissionMissingFields, type LaunchMissionField } from "./launchMissionValidation";
import { bfoTaskPresets, isBfoTaskPresetId } from "./bfoTaskPresets";
import { bfoTaskFormation } from "./bfoTaskFormation";
import { questionBoundFallbackCandidates } from "./launchQuestionCandidates";

export type LaunchMode = "question" | "pdf" | "resume";
export interface LaunchCandidate { id: string; question: string; material: string; property: string; scope: string; kind: "survey" | "contrast" | "mechanism"; }
export interface LaunchMission { question: string; material: string; property: string; scope: string; templateId?: string; }
export interface LaunchPdfCandidateTarget { runId: string; documentId: string; title: string; }

type Theme = "light" | "dark" | "eye";
type CandidateOrigin = "deepseek" | "local_no_api" | "local_after_failure" | null;
const copy = (zh: string, en: string) => uiLanguage() === "zh" ? zh : en;
const launchFleetMasks = ["/ambient-backgrounds/launch-masks/fleet-01-flagship-mask.png", "/ambient-backgrounds/launch-masks/fleet-02-formation-mask.png", "/ambient-backgrounds/launch-masks/fleet-03-flotilla-mask.png", "/ambient-backgrounds/launch-masks/fleet-04-expedition-mask.png", "/ambient-backgrounds/launch-masks/fleet-05-surveyor-mask.png"] as const;

type FleetRoute = { widthVw: number; startX: number; startY: number; endX: number; endY: number; rotation: number };
const FLEET_ROUTES: FleetRoute[] = [
  { widthVw: 88, startX: 92, startY: -24, endX: -152, endY: 18, rotation: 0 },
  { widthVw: 68, startX: 86, startY: -48, endX: -124, endY: 94, rotation: 7 },
  { widthVw: 78, startX: -118, startY: 92, endX: 74, endY: -42, rotation: -9 },
  { widthVw: 100, startX: -146, startY: 31, endX: 88, endY: 11, rotation: 0 },
  { widthVw: 63, startX: -96, startY: -58, endX: 96, endY: 98, rotation: 11 },
];

function nextFleetIndex(previous?: number) {
  if (launchFleetMasks.length < 2) return 0;
  const offset = 1 + Math.floor(Math.random() * (launchFleetMasks.length - 1));
  return previous === undefined ? Math.floor(Math.random() * launchFleetMasks.length) : (previous + offset) % launchFleetMasks.length;
}
const fallbackCandidates = (question: string): LaunchCandidate[] => questionBoundFallbackCandidates(question, uiLanguage());

const MODES: Array<{ id: LaunchMode; icon: string; zh: string; en: string; zhDetail: string; enDetail: string }> = [
  { id: "question", icon: "✦", zh: "问题启航", en: "Question", zhDetail: "问题 → 候选资料库 / 计划", enDetail: "Question → candidates / plan" },
  { id: "pdf", icon: "▱", zh: "文献入港", en: "PDF intake", zhDetail: "PDF → 私有 Markdown / 引文", enDetail: "PDF → private Markdown / citations" },
  { id: "resume", icon: "↗", zh: "续航任务", en: "Resume", zhDetail: "运行包 → 未完成阶段", enDetail: "Run package → unfinished stage" },
];

export function Launchpad(props: { onQuestion: (mission: LaunchMission) => void; onPdf: (file: File, candidateTarget?: LaunchPdfCandidateTarget) => void; onResume: (file: File) => void; onCandidates?: (question: string) => Promise<LaunchCandidate[]>; onPreviewStage: (stage: LaunchPreviewStage) => void; candidatePdfTarget?: LaunchPdfCandidateTarget | null; activeRunId?: string | null; onReturnToActiveRun?: () => void; automaticExecutionAvailable?: boolean; launchNotice?: string | null; onDismissLaunchNotice?: () => void; pdfSubmissionPending?: boolean; retryPdfSubmission?: { fileName: string } | null; onRetryPdfSubmission?: () => void; resumeSubmissionPending?: boolean; language: "zh" | "en"; theme: Theme; onLanguage: (language: "zh" | "en") => void; onTheme: (theme: Theme) => void; }) {
  const [foregroundIndex, setForegroundIndex] = createSignal(nextFleetIndex());
  const [mode, setMode] = createSignal<LaunchMode>("question");
  const activeStage = () => stageForLaunchMode(mode());
  const [prompt, setPrompt] = createSignal("");
  const [candidates, setCandidates] = createSignal<LaunchCandidate[]>([]);
  const [candidatePending, setCandidatePending] = createSignal(false);
  const [candidateConsent, setCandidateConsent] = createSignal(false);
  const [candidateOrigin, setCandidateOrigin] = createSignal<CandidateOrigin>(null);
  const [candidateAttempt, setCandidateAttempt] = createSignal(0);
  const [selected, setSelected] = createSignal<LaunchCandidate | null>(null);
  const [jumping, setJumping] = createSignal(false);
  const [pdf, setPdf] = createSignal<File | null>(null);
  const [pdfConsent, setPdfConsent] = createSignal(false);
  const [automaticConsent, setAutomaticConsent] = createSignal(false);
  const [resume, setResume] = createSignal<File | null>(null);
  const bfoPresets = () => bfoTaskPresets(props.language);
  const selectedBfoFormation = () => {
    const candidate = selected();
    return candidate ? bfoTaskFormation(candidate.id, props.language) : [];
  };
  const selectedMissing = () => { const candidate = selected(); return candidate ? launchMissionMissingFields(candidate) : [] as LaunchMissionField[]; };
  const selectedReady = () => { const candidate = selected(); return Boolean(candidate && isLaunchMissionReady(candidate)); };
  const fieldLabel = (field: LaunchMissionField) => ({ question: copy("研究问题", "research question"), material: copy("研究对象", "research objects"), property: copy("研究目标", "research target"), scope: copy("比较范围", "comparison scope") } as const)[field];
  let latestCandidateRequest = 0;
  createEffect(() => { if (props.candidatePdfTarget) setMode("pdf"); });
  let fleetNode: HTMLDivElement | undefined;
  onMount(() => {
    if (!fleetNode) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reducedMotion.matches) {
      const route = FLEET_ROUTES[foregroundIndex()];
      fleetNode.style.width = route.widthVw + "vw";
      fleetNode.style.opacity = ".38";
      fleetNode.style.transform = "translate3d(" + ((route.startX + route.endX) * window.innerWidth / 200) + "px, " + ((route.startY + route.endY) * window.innerHeight / 200) + "px, 0) rotate(" + route.rotation + "deg)";
      return;
    }
    const transitMs = 20_000;
    const cycleMs = 25_000;
    const startedAt = performance.now();
    let frame = 0;
    let completedCycle = 0;
    const tick = (now: number) => {
      const elapsed = now - startedAt;
      const currentCycle = Math.floor(elapsed / cycleMs);
      if (currentCycle > completedCycle) {
        completedCycle = currentCycle;
        setForegroundIndex((previous) => nextFleetIndex(previous));
      }
      const phase = elapsed % cycleMs;
      const route = FLEET_ROUTES[foregroundIndex()];
      fleetNode!.style.width = route.widthVw + "vw";
      const progress = Math.min(1, phase / transitMs);
      const offsetX = (route.startX + (route.endX - route.startX) * progress) * window.innerWidth / 100;
      const offsetY = (route.startY + (route.endY - route.startY) * progress) * window.innerHeight / 100;
      const opacity = phase >= transitMs ? 0 : progress < .025 ? progress / .025 : progress > .775 ? (1 - progress) / .225 : 1;
      fleetNode!.style.opacity = String(Math.max(0, opacity));
      fleetNode!.style.transform = "translate3d(" + offsetX + "px, " + offsetY + "px, 0) rotate(" + route.rotation + "deg)";
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    onCleanup(() => window.cancelAnimationFrame(frame));
  });

  createEffect(() => {
    const question = prompt().trim();
    candidateAttempt();
    // Provider health is refreshed independently every 30 seconds. Reading
    // this conditional prop reactively would resend the same authorized
    // question whenever that health object is replaced, even if availability
    // did not change. Only question/consent/retry are allowed request triggers.
    const modelCandidateRequest = untrack(() => props.onCandidates);
    const requestId = ++latestCandidateRequest;
    setSelected(null);
    setAutomaticConsent(false);
    setCandidateOrigin(null);
    if (mode() !== "question" || question.length < 12 || (modelCandidateRequest && !candidateConsent())) { setCandidates([]); setCandidatePending(false); return; }
    setCandidates([]);
    setCandidatePending(true);
    const timer = window.setTimeout(() => {
      const request = modelCandidateRequest ? modelCandidateRequest(question) : Promise.resolve(fallbackCandidates(question));
      void request
        .then((result) => {
          if (isCurrentCandidateResponse(requestId, latestCandidateRequest, question, prompt())) {
            setCandidates(result);
            setCandidateOrigin(modelCandidateRequest ? "deepseek" : "local_no_api");
            setCandidatePending(false);
          }
        })
        .catch(() => {
          if (isCurrentCandidateResponse(requestId, latestCandidateRequest, question, prompt())) {
            setCandidates(fallbackCandidates(question));
            setCandidateOrigin("local_after_failure");
            setCandidatePending(false);
          }
        });
    }, 800);
    onCleanup(() => window.clearTimeout(timer));
  });

  function updateCandidate(field: keyof LaunchMission, value: string) {
    const current = selected();
    if (current) setSelected({ ...current, [field]: value });
  }
  function selectBfoPreset(candidate: LaunchCandidate) {
    setSelected({ ...candidate });
    setAutomaticConsent(false);
  }
  function beginQuestion() {
    if (jumping()) return;
    const candidate = selected();
    if (!candidate || !isLaunchMissionReady(candidate) || (props.automaticExecutionAvailable && !automaticConsent())) return;
    setJumping(true);
    window.setTimeout(() => props.onQuestion({ ...candidate, templateId: isBfoTaskPresetId(candidate.id) ? candidate.id : undefined }), 680);
  }
  function resizeQuestionInput(textarea: HTMLTextAreaElement) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 208) + "px";
  }

  return <main classList={{ launchpad: true, "launch-jumping": jumping() }}>
    <div class="launch-sky" aria-hidden="true"><i /><i /><i /><i /></div>
    <div class="launch-fleet-extract" ref={(node) => { fleetNode = node; }} aria-hidden="true"><img class="launch-fleet-main" src={launchFleetMasks[foregroundIndex()]} alt="" /><img class="launch-fleet-echo" src={launchFleetMasks[foregroundIndex()]} alt="" /></div>
    <section class="launch-controls" aria-label={copy("起始页显示设置", "Launch display settings")}>
      <div class="launch-control-group"><button classList={{ active: props.language === "zh" }} type="button" onClick={() => props.onLanguage("zh")} aria-label="切换为中文" title="中文">中</button><button classList={{ active: props.language === "en" }} type="button" onClick={() => props.onLanguage("en")} aria-label="Switch to English" title="English">En</button></div>
      <div class="launch-control-group"><button classList={{ active: props.theme === "light" }} type="button" onClick={() => props.onTheme("light")} aria-label={copy("浅色主题", "Light theme")} title={copy("浅色", "Light")}>☀</button><button classList={{ active: props.theme === "dark" }} type="button" onClick={() => props.onTheme("dark")} aria-label={copy("深色主题", "Dark theme")} title={copy("深色", "Dark")}>☾</button><button classList={{ active: props.theme === "eye" }} type="button" onClick={() => props.onTheme("eye")} aria-label={copy("护眼主题", "Eye-care theme")} title={copy("护眼", "Eye care")}>◉</button></div>
    </section>

    <section class="launch-hero">
      <div class="launch-briefing">
        <p class="launch-kicker">COSMATTER / {copy("材料科学证据航线", "MATERIALS EVIDENCE ROUTE")}</p>
        <h1>{copy("从一个问题，驶向可审计的材料研究。", "From one question to auditable materials research.")}</h1>
        <p class="launch-boundary">{copy("自动生成的候选、背景与计划均为未受信建议；只有人工核对来源定位后的 EvidenceCard 才能进入后续推论。", "Generated candidates, context and plans are untrusted suggestions. Only human-checked, located EvidenceCards can support later reasoning.")}</p>
        <nav class="launch-modes" aria-label={copy("任务入口", "Mission entry modes")}>
          <For each={MODES}>{(item, index) => <button classList={{ active: mode() === item.id }} type="button" aria-label={copy(`${item.zh}：${item.zhDetail}`, `${item.en}: ${item.enDetail}`)} aria-pressed={mode() === item.id} disabled={jumping()} onClick={() => setMode(item.id)}><b>0{index() + 1}</b><i>{item.icon}</i><span>{copy(item.zh, item.en)}</span><small>{copy(item.zhDetail, item.enDetail)}</small></button>}</For>
        </nav>
      </div>
      <aside class="launch-stage-column" aria-label={copy("科研闭环阶段", "Research evidence stages")}>
        <header><p>RESEARCH EVIDENCE ROUTE</p><strong>{copy("科研闭环", "Research evidence loop")}</strong><span>{launchModeStatus(mode(), props.language)}</span></header>
        <ol>
          <For each={LAUNCH_STAGES}>{(stage, index) => <li classList={{ active: activeStage() === stage.id }}>
            <button type="button" onClick={() => props.onPreviewStage(stage.id)} aria-current={activeStage() === stage.id ? "step" : undefined} aria-label={copy(`预览：${stage.zh}`, `Preview: ${stage.en}`)}>
              <span class="launch-stage-index">{String(index() + 1).padStart(2, "0")}</span>
              <span class="launch-stage-copy"><strong>{copy(stage.zh, stage.en)}</strong><small>{copy(stage.inputZh, stage.inputEn)} → {copy(stage.outputZh, stage.outputEn)}</small><em>{copy(stage.gateZh, stage.gateEn)}</em></span>
              <b aria-hidden="true">↗</b>
            </button>
          </li>}</For>
        </ol>
        <footer>{copy("点击仅打开本地只读预览；不会创建任务、上传文件或调用 API。", "Click for a local read-only preview only. No task, upload, or API call is started.")}</footer>
      </aside>
    </section>

    <section class="launch-workspace">
      <Show when={props.launchNotice}>{(notice) => <section class="launch-notice" role="alert" aria-live="assertive"><div><small>{copy("本地文件校验提示", "LOCAL FILE VALIDATION")}</small><p>{notice()}</p></div><button type="button" onClick={() => props.onDismissLaunchNotice?.()}>{copy("关闭提示", "Dismiss")}</button></section>}</Show>
      <Show when={props.activeRunId}>{(runId) => <section class="launch-active-run" role="status" aria-live="polite"><div><small>{copy("本机任务仍在保留", "LOCAL RUN RETAINED")}</small><strong>{copy("返回起始页不会取消当前任务", "Returning to launch does not cancel the current task")}</strong><p>{copy(`本机运行 ${runId()} 仍可继续查看。只有明确修改任务边界或新建任务时才会替换它。`, `Local run ${runId()} remains available for review. It is replaced only after an explicit task-boundary change or new task.`)}</p></div><button type="button" onClick={() => props.onReturnToActiveRun?.()}>{copy("返回当前任务", "Return to current task")}</button></section>}</Show>
      <Show when={mode() === "question"}>
        <section class="signal-receiver"><header><p class="launch-kicker">QUESTION SIGNAL</p><h2>{copy("提出一个可由文献证据回答的问题", "Ask a question answerable with literature evidence")}</h2><ol><li>{copy("输入研究问题", "Enter a research question")}</li><li>{copy("生成未受信候选航向", "Generate untrusted candidate routes")}</li><li>{copy("确认任务边界", "Confirm the task boundary")}</li></ol></header><section class="bfo-task-deck" aria-label={copy("BiFeO₃ 任务模板", "BiFeO₃ task templates")}><header><small>{copy("BFO 任务模板 / 只填入本地简报", "BFO TASK TEMPLATES / LOCAL BRIEF ONLY")}</small><span>{copy("选择后仍可编辑，并须确认；不会检索、上传或创建任务。", "Selection remains editable and requires confirmation; it does not retrieve, upload, or create a task.")}</span></header><div><For each={bfoPresets()}>{(preset, index) => <button type="button" aria-pressed={selected()?.id === preset.id} classList={{ selected: selected()?.id === preset.id }} onClick={() => selectBfoPreset(preset)}><small>BFO-{String(index() + 1).padStart(2, "0")}</small><strong>{preset.question}</strong><span>{preset.material} · {preset.property}</span><em>{preset.scope}</em></button>}</For></div></section><label>{copy("候选航向研究问题", "Candidate-route research question")}<textarea value={prompt()} rows="3" onInput={(event) => { setPrompt(event.currentTarget.value); resizeQuestionInput(event.currentTarget); }} placeholder={copy("例如：为什么不同薄膜研究对 BiFeO₃ 相稳定性有相反结论？", "Example: Why do thin-film studies disagree about BiFeO₃ phase stability?")} /></label><small>{props.onCandidates ? copy("输入至少 12 个字符后，先明确授权候选生成模型；授权后约 0.8 秒生成未受信候选航向。", "After at least 12 characters, explicitly authorize the candidate-generation model; untrusted route suggestions appear about 0.8 seconds later.") : copy("输入至少 12 个字符后，系统将在约 0.8 秒后形成候选航向。", "After at least 12 characters, candidate routes appear in about 0.8 seconds.")}</small>
          <Show when={props.onCandidates}><label class="consent launch-candidate-consent"><input type="checkbox" checked={candidateConsent()} onChange={(event) => setCandidateConsent(event.currentTarget.checked)} />{copy("我同意将上述研究问题发送至已配置的候选生成模型，以形成未受信候选航向；不会检索、上传全文或创建任务。", "I authorize sending the research question above to the configured candidate-generation model for untrusted route suggestions. This does not retrieve, upload full text, or create a task.")}</label></Show>
          <Show when={candidates().length > 0}><section class="candidate-handoff" aria-live="polite"><div><p>{copy("下一步 / 选择一个候选航向", "NEXT / SELECT A CANDIDATE ROUTE")}</p><strong>{selected() ? copy("已选择候选航向；请在下方核对并编辑任务边界。", "Candidate selected; review and edit the task boundary below.") : copy("候选已生成；请选择一条航向以打开可编辑的任务简报。", "Candidate routes are ready; select one to open an editable mission brief.")}</strong><span>{copy("选择不会检索、上传全文或创建任务。", "Selection does not retrieve, upload full text, or create a task.")}</span></div><b>{selected() ? copy("已选择", "SELECTED") : copy("待选择", "SELECT")}</b></section></Show>
          <Show when={candidateOrigin()}>{(origin) => <section classList={{ "candidate-origin": true, warning: origin() !== "deepseek" }} role="status" aria-label={copy("候选生成来源", "Candidate generation source")}><div><strong>{origin() === "deepseek" ? copy("DeepSeek 候选生成 · 已通过问题锚点校验", "DeepSeek candidate generation · question anchors validated") : copy("本地问题绑定回退", "Question-bound local fallback")}</strong><span>{origin() === "deepseek" ? copy("每条可见问题均保留原问题中的材料与目标性质；候选仍是未受信建议。", "Every visible question retains the material and target property from the original question; candidates remain untrusted suggestions.") : origin() === "local_after_failure" ? copy("模型请求失败或输出未通过相关性校验；失配结果未显示，当前候选由本机规则生成。", "The model request failed or its output did not pass relevance validation. The mismatched result was withheld and these routes were generated locally.") : copy("当前页面未连接本机候选生成 API；这些候选由本机规则生成，不是模型回答。", "This page is not connected to the local candidate-generation API. These routes were generated locally and are not a model response.")}</span></div><Show when={origin() === "local_after_failure" && props.onCandidates}><button type="button" disabled={candidatePending()} onClick={() => setCandidateAttempt((value) => value + 1)}>{copy("重新请求模型", "Retry model")}</button></Show></section>}</Show>
          <div classList={{ "candidate-orbits": true, ready: candidates().length > 0 }}><Show when={candidates().length > 0} fallback={<p class="launch-empty" role="status">{candidatePending() ? copy("正在生成未受信候选航向；不会创建任务或调用检索。", "Generating untrusted candidate routes; no task or retrieval is started.") : props.onCandidates && prompt().trim().length >= 12 && !candidateConsent() ? copy("请先授权候选生成模型，再发送研究问题形成候选航向。", "Authorize the candidate-generation model before sending the research question for route suggestions.") : copy("等待研究信号。", "Waiting for a research signal.")}</p>}><For each={candidates()}>{(candidate, index) => <button type="button" aria-pressed={selected()?.id === candidate.id} disabled={jumping()} classList={{ "candidate-planet": true, selected: selected()?.id === candidate.id, [`planet-${candidate.kind}`]: true }} style={{ "--orbit-delay": `${index() * 110}ms` }} onClick={() => { setSelected({ ...candidate }); setAutomaticConsent(false); }}><small>{selected()?.id === candidate.id ? copy("已选航向", "SELECTED") : `0${index() + 1}`}</small><strong>{candidate.question}</strong><span>{candidate.kind === "survey" ? copy("全景梳理", "Landscape") : candidate.kind === "contrast" ? copy("条件分歧", "Contrast") : copy("机制核验", "Mechanism")}</span><em>{selected()?.id === candidate.id ? copy("继续：核对任务边界", "Next: review boundary") : copy("点击选择此航向", "Select this route")}</em></button>}</For></Show></div>
          <Show when={selected()}>{(candidate) => <section class="launch-brief-editor" aria-labelledby="mission-brief-heading"><div><p id="mission-brief-heading">{copy("下一步 / 任务简报与可编辑边界", "NEXT / MISSION BRIEF AND EDITABLE BOUNDARY")}</p><label>{copy("任务简报研究问题", "Mission-brief research question")}<input value={candidate().question} onInput={(event) => updateCandidate("question", event.currentTarget.value)} /></label><label>{copy("研究对象", "Research objects")}<input value={candidate().material} onInput={(event) => updateCandidate("material", event.currentTarget.value)} /></label><label>{copy("研究目标", "Research target")}<input value={candidate().property} onInput={(event) => updateCandidate("property", event.currentTarget.value)} /></label><label>{copy("比较范围", "Comparison scope")}<input value={candidate().scope} onInput={(event) => updateCandidate("scope", event.currentTarget.value)} /></label></div><div class="launch-confirmation"><Show when={selectedMissing().length}><p class="launch-brief-warning">{copy("仍需人工确认：", "Still requires human confirmation: ")}<For each={selectedMissing()}>{(field, index) => <>{index() ? "、" : ""}{fieldLabel(field)}</>}</For>{copy("。候选航向不会直接成为检索任务。", ". A candidate route cannot directly become a retrieval task.")}</p></Show><Show when={props.automaticExecutionAvailable}><label class="consent launch-auto-consent"><input type="checkbox" checked={automaticConsent()} onChange={(event) => setAutomaticConsent(event.currentTarget.checked)} />{copy("我确认本次任务可向已选书目服务发送问题、对象、目标与范围，用于受控元数据检索；该授权不接受 EvidenceCard，也不上传全文。", "I authorize this task to send its question, objects, target, and scope to selected bibliographic services for controlled metadata retrieval. This does not accept EvidenceCards or upload full text.")}</label></Show><button class="launch-primary" disabled={jumping() || !selectedReady() || (props.automaticExecutionAvailable && !automaticConsent())} type="button" onClick={beginQuestion}>{props.automaticExecutionAvailable ? copy("确认并授权元数据检索", "Confirm and authorize metadata retrieval") : copy("确认任务并进入编排", "Confirm and enter orchestration")}</button></div></section>}</Show>
          <Show when={selectedBfoFormation().length}><section class="bfo-formation-brief" aria-label={copy("BFO 计划编队", "BFO planned formation")}><header><small>{copy("计划编队契约 / 尚未执行", "PLANNED FORMATION CONTRACT / NOT EXECUTING")}</small><span>{copy("每一舰位都写明输入、输出与人工门禁。选择模板或确认任务均不会启动工具。", "Every station names its input, output, and human gate. Selecting or confirming a template does not start a tool.")}</span></header><div role="list"><For each={selectedBfoFormation()}>{(station, index) => <div role="listitem"><span>{String(index() + 1).padStart(2, "0")}</span><strong>{station.fleetLabel}</strong><em>{station.role}</em><small class="formation-intake">{copy("输入", "INPUT")}: {station.intake}</small><small class="formation-artifact">{copy("输出", "OUTPUT")}: {station.artifact}</small><small class="formation-gate">{copy("门禁", "GATE")}: {station.acceptanceGate}</small></div>}</For></div></section></Show>
        </section>
      </Show>
      <Show when={mode() === "pdf"}><section class="mode-panel" aria-busy={props.pdfSubmissionPending}><p class="launch-kicker">DOCUMENT INTAKE</p><h2>{copy("将有权处理的 PDF 送入私有资料舱", "Send an authorized PDF to the private document bay")}</h2><Show when={props.candidatePdfTarget}>{(target) => <p class="candidate-pdf-context">{copy("当前将把已人工纳入的候选关联到原任务：", "The authorized PDF will be linked to the original task for the human-included candidate:")} <strong>{target().title}</strong></p>}</Show><Show when={props.retryPdfSubmission}>{(retry) => <section class="launch-pdf-retry" role="status"><small>{copy("未确认提交 / 原任务仍保留", "UNCONFIRMED SUBMISSION / ORIGINAL TASK RETAINED")}</small><p>{copy(`“${retry().fileName}”仍只保留在此浏览器会话内。重试将使用原任务 ID，不会创建第二个任务。`, `“${retry().fileName}” remains only in this browser session. Retrying uses the original task ID and does not create a second task.`)}</p><button class="launch-primary" disabled={props.pdfSubmissionPending} type="button" onClick={() => props.onRetryPdfSubmission?.()}>{props.pdfSubmissionPending ? copy("正在重试解析任务…", "Retrying parsing task…") : copy("使用原任务重试", "Retry original task")}</button></section>}</Show><p>{copy("文件先进入本机环回服务；确认后才提交 MinerU。完整 Markdown 不进入 UI JSON 或运行包。", "The file first enters the local loopback service; it reaches MinerU only after consent. Full Markdown never enters UI JSON or a run package.")}</p><label class="file-bay">{copy("选择 PDF", "Choose PDF")}<input type="file" disabled={props.pdfSubmissionPending} accept="application/pdf,.pdf" onChange={(event) => setPdf(event.currentTarget.files?.[0] ?? null)} /></label><Show when={pdf()}>{(file) => <p class="file-name">{file().name} · {(file().size / 1024 / 1024).toFixed(1)} MB</p>}</Show><label class="consent"><input type="checkbox" disabled={props.pdfSubmissionPending} checked={pdfConsent()} onChange={(event) => setPdfConsent(event.currentTarget.checked)} />{copy("我确认有权处理该 PDF，并同意提交后发送至 MinerU 云端。", "I have the right to process this PDF and consent to MinerU cloud submission.")}</label><button class="launch-primary" disabled={props.pdfSubmissionPending || !pdf() || !pdfConsent()} type="button" onClick={() => pdf() && props.onPdf(pdf()!, props.candidatePdfTarget ?? undefined)}>{props.pdfSubmissionPending ? copy("正在提交解析任务…", "Submitting parsing task…") : copy("创建解析任务", "Create parsing task")}</button></section></Show>
      <Show when={mode() === "resume"}><section class="mode-panel" aria-busy={props.resumeSubmissionPending}><p class="launch-kicker">RUN CONTINUATION</p><h2>{copy("恢复可执行的研究航程", "Restore an executable research voyage")}</h2><p>{copy("仅接受版本化 .cosmatter-run.json。旧 ui.json 仅可只读查看，不能恢复后端执行。", "Only versioned .cosmatter-run.json is accepted. Legacy ui.json remains read-only and cannot resume backend execution.")}</p><label class="file-bay">{copy("选择运行包", "Choose run package")}<input type="file" disabled={props.resumeSubmissionPending} accept="application/json,.json" onChange={(event) => setResume(event.currentTarget.files?.[0] ?? null)} /></label><Show when={resume()}>{(file) => <p class="file-name">{file().name}</p>}</Show><button class="launch-primary" disabled={props.resumeSubmissionPending || !resume()} type="button" onClick={() => resume() && props.onResume(resume()!)}>{props.resumeSubmissionPending ? copy("正在校验并恢复…", "Validating and restoring…") : copy("校验并继续任务", "Validate and continue")}</button></section></Show>
    </section>

    <footer class="launch-flow" aria-label={copy("证据流程", "Evidence workflow")}><p>{copy("证据流程", "EVIDENCE ROUTE")}</p><div><span>{copy("输入", "Input")}</span><i>→</i><span>{copy("编排", "Orchestrate")}</span><i>→</i><span>{copy("文献星图", "Literature map")}</span><i>→</i><span>{copy("证据核对", "Verify")}</span><i>→</i><span>Gap {copy("候选", "candidates")}</span></div></footer>
  </main>;
}
