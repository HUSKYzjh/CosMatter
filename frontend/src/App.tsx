import { For, Show, createEffect, createMemo, createSignal, onCleanup, onMount } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { Launchpad, type LaunchMission, type LaunchPdfCandidateTarget } from "./Launchpad";
import { type LaunchPreviewStage } from "./launchStages";
import { launchMissionMissingFields } from "./launchMissionValidation";
import { continuationStageLabel, viewForRestoredRun } from "./continuationStage";
import { fleetVisualState } from "./fleetVisualState";
import { FleetCommand } from "./FleetCommand";
import { GraphNetwork } from "./GraphNetwork";
import { hasNavigableLiteratureGraph, missionJourney, type JourneyStage } from "./missionJourney";
import { automaticGraphHandoffTarget } from "./automaticGraphHandoff";
import { deriveMissionArtifactStatus, taskBoundaryFingerprint, type MissionArtifactStatus } from "./missionArtifactStatus";
import { PaperReader } from "./PaperReader";
import { ResearchExpansion } from "./ResearchExpansion";
import { auditableAcceptedEvidence, documentIdForReviewablePaper, evidenceForPaper, reviewablePaperCount, reviewablePaperForDocumentId } from "./evidenceLinking";
import { focusEvidenceSession } from "./evidenceSessionFocus";
import { emptyResearchSession, evidenceGate, reconcileResearchSession, selectEvidence, selectPaper, type ResearchSession } from "./researchSession";
import { emptyBundleForMission, newLocalMissionId } from "./missionBundleFactory";
import { approveLivePlan, createLiveMission, createAutomaticMission, createPdfRun, cancelRun, draftLivePlan, diagnoseConditions, executeApprovedQuery, expandPdfCitations, generateGapCandidates, confirmPdfDoi, fetchLiveUiBundle, getCandidateScreening, getLocalApiStatus, getPdfSourceMapContext, getPdfStatus, getPdfTasks, getRunStatus, importRunPackage, localApiEnabled, privateMarkdownUrl, recordCandidateScreening, recordPdfEvidenceCard, recordPdfMaterialFacts, recordPdfSourceMap, requestQuestionCandidates, type CandidateScreening, type CandidateScreeningCandidate, type AutomaticExecutionStatus, type HarnessAuthorization, type CandidateScreeningDecision, type EvidenceReviewResult, type HumanEvidenceReviewInput, type HumanMaterialFactInput, type PdfTaskStatus, type PrivateSourceMapSegment, type RetrievalSource, type SourceMapRecordResult } from "./localApi";
import { demoBundle, readBundle, type EvidenceCard, type ImportedBundle, type LiteratureGraphNode } from "./model";
import { setUiLanguage, uiLanguage } from "./zh";
import { shouldPollPdfTask } from "./pdfTaskPolling";
import { candidateFulltextGate } from "./candidateFulltextGate";
import { completedPrivateSourceMapMatchesPaper, screeningAllowsSourceReview } from "./currentPaperReviewRoute";
type Theme = "light" | "dark" | "eye";
type View = "launch" | "discover" | "workflow" | "graph" | "reader" | "horizon";
type RouteRecovery = { view: View; zh: string; en: string };
const text = (zhText: string, enText: string) => uiLanguage() === "zh" ? zhText : enText;
const SOURCES: Array<{ id: RetrievalSource; label: string; provider: string }> = [
  { id: "sciverse", label: "Sciverse", provider: "sciverse" },
  { id: "openalex", label: "OpenAlex", provider: "openalex" },
  { id: "crossref", label: "Crossref", provider: "crossref" },
];

function artifactTitle(card: MissionArtifactStatus): string {
  return ({ brief: text("任务简报", "Mission brief"), conditions: text("条件矩阵", "Condition matrix"), evidence: text("证据门禁", "Evidence gate"), counterevidence: text("反例边界", "Counterevidence boundary") } as const)[card.key];
}
function artifactState(card: MissionArtifactStatus): string {
  return ({ ready: text("已登记", "REGISTERED"), pending: text("待补齐", "PENDING"), recheck: text("需重新核验", "RECHECK REQUIRED") } as const)[card.state];
}
function journeyStateLabel(stage: JourneyStage): string {
  if (stage.state === "current") return text("进行中", "IN PROGRESS");
  if (stage.state === "complete") return text("已完成", "COMPLETE");
  if (stage.state === "ready") return text("可进入", "READY");
  return uiLanguage() === "zh" ? stage.reasonZh ?? "待补齐前置工件" : stage.reasonEn ?? "Prerequisite artifacts are pending.";
}
function artifactNext(card: MissionArtifactStatus): string {
  return ({ "complete-brief": text("下一步：补齐任务边界", "Next: complete task boundaries"), orchestrate: text("下一步：进入舰桥编排", "Next: enter bridge orchestration"), "import-conditions": text("下一步：导入条件工件", "Next: import condition artifact"), "verify-source": text("下一步：选择文献并核对来源", "Next: select literature and verify source"), "review-counterevidence": text("下一步：补充反例边界", "Next: review counterevidence boundary"), reimport: text("下一步：重新导入匹配工件", "Next: re-import matching artifact") } as const)[card.next];
}
function metricLabel(key: string): string {
  return ({ material: text("材料", "Material"), property: text("性质", "Property"), scope: text("范围", "Scope"), conditionClusters: text("条件簇", "condition clusters"), contradictions: text("矛盾记录", "contradictions"), unknowns: text("未知项", "unknowns"), acceptedEvidence: text("已接受证据", "accepted evidence"), sourceDocuments: text("来源文档", "source documents"), sourceSegments: text("来源片段", "source segments"), gapCandidates: text("Gap 候选", "Gap candidates") } as Record<string, string>)[key] ?? key;
}
function artifactDetail(card: MissionArtifactStatus): string {
  if (card.key === "brief") return card.state === "ready" ? card.detail : text("研究问题、对象、比较维度或范围尚未填写完整。", "The research question, objects, comparison dimensions, or scope is incomplete.");
  if (card.key === "conditions") return card.metrics[0].value ? text("已从导入工件读取条件簇；字段内容以实际工件为准。", "Condition clusters come from the imported artifact.") : text("尚未导入条件簇；不会预设任何材料体系的具体变量。", "No condition cluster is imported; no domain-specific variable is assumed.");
  if (card.key === "evidence") return card.state === "ready" ? text("已记录可用来源映射与精确溯源匹配。", "Source-map coverage and exact provenance matches are recorded.") : text("尚缺已接受证据、来源片段或精确溯源匹配。", "Accepted evidence, source segments, or an exact provenance match is still missing.");
  return card.metrics[0].value || card.metrics[1].value || card.metrics[2].value ? text("保留导入工件中的候选、矛盾与未知项，等待人工复核。", "Imported candidates, contradictions, and unknowns remain pending human review.") : text("尚未登记反例边界或可审查 Gap 候选。", "No counterevidence boundary or reviewable Gap candidate is recorded.");
}
function examples(): string[] {
  return [
    text("为什么不同薄膜研究对 BiFeO₃ 相稳定性有相反结论？", "Why do bounded thin-film studies disagree about BiFeO₃ phase stability?"),
    text("氧空位如何改变钙钛矿薄膜的铁电相稳定性？", "How do oxygen vacancies change ferroelectric phase stability in perovskite films?"),
    text("如何比较不同表征方法得到的材料相边界？", "How can phase boundaries inferred by different characterisation methods be compared?"),
  ];
}

export function App() {
  const [bundle, setBundle] = createSignal<ImportedBundle>(demoBundle);
  const [question, setQuestion] = createSignal(demoBundle.mission.question);
  const [missionBoundary, setMissionBoundary] = createSignal({
    material: demoBundle.mission.material,
    property: demoBundle.mission.property,
    scope: demoBundle.mission.scope,
  });
  let questionTextarea: HTMLTextAreaElement | undefined;
  const [theme, setTheme] = createSignal<Theme>("light");
  const [language, setLanguage] = createSignal(uiLanguage());
  const [view, setView] = createSignal<View>("launch");
  const [launchPreview, setLaunchPreview] = createSignal(false);
  const [status, setStatus] = createSignal(text("当前显示本地演示工件；尚未发起网络请求。", "Showing local demonstration artifacts; no network request has been made."));
  const [routeRecovery, setRouteRecovery] = createSignal<RouteRecovery | null>(null);
  const [automaticMissionPending, setAutomaticMissionPending] = createSignal(false);
  const [automaticGraphHandoffPending, setAutomaticGraphHandoffPending] = createSignal(false);
  const [automaticExecution, setAutomaticExecution] = createSignal<AutomaticExecutionStatus | null>(null);
  const [automaticAuthorization, setAutomaticAuthorization] = createSignal<HarnessAuthorization | null>(null);
  const [apiSummary, setApiSummary] = createSignal(text("本地 API 未启用。", "Local API is disabled."));
  const [apiProviders, setApiProviders] = createSignal<Record<string, boolean>>({});
  const [retrievalSources, setRetrievalSources] = createSignal<RetrievalSource[]>(["crossref"]);
  const [liveRunId, setLiveRunId] = createSignal<string | null>(null);
  const [candidateScreening, setCandidateScreening] = createSignal<CandidateScreening | null>(null);
  const [candidatePdfTarget, setCandidatePdfTarget] = createSignal<LaunchPdfCandidateTarget | null>(null);
  const [pdfTask, setPdfTask] = createSignal<PdfTaskStatus | null>(null);
  const [pdfTasks, setPdfTasks] = createSignal<PdfTaskStatus[]>([]);
  const [draftContent, setDraftContent] = createSignal("");
  const [reviewedPlan, setReviewedPlan] = createSignal("");
  const [planApproved, setPlanApproved] = createSignal(false);
  const [manualControlOpen, setManualControlOpen] = createSignal(false);
  const [approvedQueryCount, setApprovedQueryCount] = createSignal(0);
  const [approvedCounterQueryCount, setApprovedCounterQueryCount] = createSignal(0);
  const [researchSession, setResearchSession] = createSignal<ResearchSession>(emptyResearchSession());
  const [artifactBoundaryFingerprint, setArtifactBoundaryFingerprint] = createSignal(taskBoundaryFingerprint(demoBundle.mission));
  const [taskArtifactLocked, setTaskArtifactLocked] = createSignal(false);
  const selectedDocumentId = createMemo(() => documentIdForReviewablePaper(researchSession().selectedNode));
  // A completed private PDF only unlocks this rail when it belongs to the selected candidate.
  // A screening decision may invite private full-text review, but is still not scientific evidence.
  const privateSourceMapIntakeAvailable = createMemo(() => completedPrivateSourceMapMatchesPaper(pdfTask(), selectedDocumentId()));
  const selectedPaperScreenedForFulltext = createMemo(() => screeningAllowsSourceReview(candidateScreening(), selectedDocumentId()));
  const selectedPaperHasAcceptedEvidence = createMemo(() => evidenceForPaper(bundle(), researchSession().selectedNode).length > 0);
  const gate = createMemo(() => evidenceGate(bundle(), researchSession()));
  const missionDraftChanged = createMemo(() => taskBoundaryFingerprint({
    ...bundle().mission,
    question: question().trim(),
    material: missionBoundary().material.trim(),
    property: missionBoundary().property.trim(),
    scope: missionBoundary().scope.trim(),
  }) !== taskBoundaryFingerprint(bundle().mission));
  const missionDraftMissing = createMemo(() => [
    !question().trim() ? text("研究问题", "research question") : "",
    !missionBoundary().material.trim() ? text("研究对象", "research objects") : "",
    !missionBoundary().property.trim() ? text("研究目标／比较维度", "research targets / comparison dimensions") : "",
    !missionBoundary().scope.trim() ? text("研究边界／比较范围", "research boundaries / comparison scope") : "",
  ].filter(Boolean));
  const missionDraftReady = createMemo(() => missionDraftMissing().length === 0);
  // Navigation leaves task definition only after the displayed draft has been
  // committed to the mission bundle. This prevents old artifacts from being
  // presented under an unconfirmed question or boundary.
  const missionConfirmed = createMemo(() => missionDraftReady() && !missionDraftChanged());
  const journey = createMemo(() => missionJourney(
    bundle(),
    question(),
    view() === "launch" ? "discover" : view() as Exclude<View, "launch">,
    taskArtifactLocked(),
    privateSourceMapIntakeAvailable(),
    { paperSelected: Boolean(selectedDocumentId()), evidenceReady: gate().ready, screeningAllowsSourceReview: selectedPaperScreenedForFulltext(), paperHasAcceptedEvidence: selectedPaperHasAcceptedEvidence() },
    missionConfirmed(),
  ));
  const artifactStatuses = createMemo(() => deriveMissionArtifactStatus(bundle(), taskArtifactLocked()));

  const gateCopy = () => ({
    paper: text("请先在文献星图选择一篇待核对论文。", "Select a paper in the literature map first."),
    evidence: text("请从导入工件中选择一张已接受 EvidenceCard。", "Select an accepted EvidenceCard from the imported artifact."),
    "source-link": text("所选 EvidenceCard 没有与当前论文对应的已审核来源映射。", "The selected EvidenceCard has no reviewed source-map link to the current paper."),
    locator: text("当前 EvidenceCard 缺少来源文档 ID 或定位符。", "The selected EvidenceCard lacks a source document ID or locator."),
    "source-map": text("所选 EvidenceCard 对应文献没有可审计的来源映射片段。", "The paper for the selected EvidenceCard has no auditable source-map segment."),
    "provenance-audit": text("当前已接受 EvidenceCard 尚未全部通过精确来源映射审计。", "Accepted EvidenceCards have not all passed the exact source-map provenance audit."),
  } as const);

  function navigate(next: View) {
    if (launchPreview()) { setRouteRecovery(null); setView(next); return; }
    if (taskArtifactLocked() && ["graph", "reader", "horizon"].includes(next)) {
      setStatus(text("任务边界已改变；旧工件保留供回看，但需重新导入匹配工件或执行受控检索。", "The task boundary changed. Old artifacts remain for review, but matching artifacts must be re-imported or retrieved in the controlled flow."));
      setRouteRecovery({ view: "discover", zh: "返回任务定义，重新建立匹配工件", en: "Return to task definition and rebuild matching artifacts" });
      return;
    }
    if (next === "reader" && !researchSession().selectedNode) {
      setStatus(gateCopy().paper);
      setRouteRecovery({ view: "graph", zh: "返回文献星图选择论文", en: "Return to literature map and select a paper" });
      return;
    }
    if (next === "horizon" && !gate().ready) {
      setStatus(gateCopy()[gate().reason ?? "evidence"]);
      setRouteRecovery({
        view: gate().reason === "paper" ? "graph" : "reader",
        zh: gate().reason === "paper" ? "返回文献星图选择论文" : "返回证据核对补齐来源与 EvidenceCard",
        en: gate().reason === "paper" ? "Return to literature map and select a paper" : "Return to evidence verification and complete source/EvidenceCard review",
      });
      return;
    }
    const stage = journey().find((item) => item.view === next);
    if (stage?.state === "blocked") {
      setStatus(language() === "zh" ? stage.reasonZh ?? "上一步尚未完成。" : stage.reasonEn ?? "The preceding stage is not ready.");
      const recovery = ({ workflow: { view: "discover", zh: "返回任务定义补齐边界", en: "Return to task definition and complete boundaries" }, graph: { view: "workflow", zh: "返回舰桥建立任务工件", en: "Return to bridge and create mission artifacts" }, reader: { view: "graph", zh: "返回文献星图选择论文", en: "Return to literature map and select a paper" }, horizon: { view: "reader", zh: "返回证据核对补齐审计链路", en: "Return to evidence verification and complete the audit chain" } } as Partial<Record<View, RouteRecovery>>)[next];
      setRouteRecovery(recovery ?? null);
      return;
    }
    setRouteRecovery(null);
    setView(next);
  }
  function openLaunchPreview(stage: LaunchPreviewStage) {
    setLaunchPreview(true);
    setResearchSession(emptyResearchSession());
    setView(stage);
    setStatus(text("当前为起始页只读预览：未创建任务、未上传文件、未调用模型或检索 API。", "This is a launch-page read-only preview: no task, upload, model, or retrieval API was started."));
  }

  function returnToLaunch() {
    setLaunchPreview(false);
    setView("launch");
    setStatus(text("已返回起始页；选择入口并完成确认后才会执行任务。", "Returned to launch. A task runs only after an entry is selected and confirmed."));
  }

  function updateMission() {
    if (launchPreview()) { setStatus(text("只读预览不能修改任务边界。", "The read-only preview cannot change the task boundary.")); return false; }
    const trimmed = question().trim();
    if (!trimmed) { setStatus(text("请先输入可审查的研究问题。", "Enter an auditable research question first.")); return false; }
    const boundary = missionBoundary();
    const missingBoundary = [!boundary.material.trim() ? text("研究对象", "research objects") : "", !boundary.property.trim() ? text("研究目标／比较维度", "research targets / comparison dimensions") : "", !boundary.scope.trim() ? text("研究边界／比较范围", "research boundaries / comparison scope") : ""].filter(Boolean);
    if (missingBoundary.length) { setStatus(text(`请先补齐：${missingBoundary.join("、")}。`, `Complete: ${missingBoundary.join(", ")}.`)); return false; }
    const nextMission = {
      ...bundle().mission,
      question: trimmed,
      material: boundary.material.trim(),
      property: boundary.property.trim(),
      scope: boundary.scope.trim(),
    };
    const changed = taskBoundaryFingerprint(nextMission) !== artifactBoundaryFingerprint();
    setBundle((current) => ({ ...current, mission: nextMission }));
    setResearchSession(emptyResearchSession());
    if (changed) { supersedeActiveRun(); setLiveRunId(null); setCandidateScreening(null); setPdfTask(null); setPdfTasks([]); }
    setTaskArtifactLocked(changed);
    setStatus(changed
      ? text("任务边界已更新。旧图谱、证据和 Gap 已锁定供回看；请重新导入匹配工件或执行受控检索。", "Mission boundary updated. Old graph, evidence, and Gaps are retained but locked for review; re-import matching artifacts or run controlled retrieval.")
      : text("任务边界已确认；尚未调用模型、检索服务或第三方 API。", "Mission boundary confirmed; no model, retrieval service, or third-party API was called."));
    return true;
  }

  function resizeQuestionTextarea(element = questionTextarea) {
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 240)}px`;
  }

  function updateQuestion(value: string) {
    if (launchPreview()) return;
    setQuestion(value);
    requestAnimationFrame(() => resizeQuestionTextarea());
  }

  function updateMissionBoundary(field: "material" | "property" | "scope", value: string) {
    if (launchPreview()) return;
    setMissionBoundary((current) => ({ ...current, [field]: value }));
  }

  function resetMissionBoundary(mission: { material: string; property: string; scope: string }) {
    setMissionBoundary({ material: mission.material, property: mission.property, scope: mission.scope });
  }

  // A launch can finish after the researcher has already started another task.
  // Keep its result out of the new mission and ask the local service to stop it.
  let taskEpoch = 0;
  function supersedeActiveRun() {
    taskEpoch += 1;
    setAutomaticMissionPending(false);
    setAutomaticGraphHandoffPending(false);
    setAutomaticExecution(null);
    setAutomaticAuthorization(null);
    const priorRunId = liveRunId();
    if (priorRunId && localApiEnabled()) void cancelRun(priorRunId).catch(() => undefined);
    return taskEpoch;
  }
  function isCurrentTask(epoch: number) { return epoch === taskEpoch; }
  function scheduleCurrentView(epoch: number, next: View, delayMs = 80) {
    window.setTimeout(() => { if (isCurrentTask(epoch)) setView(next); }, delayMs);
  }
  function currentRunGuard(runId: string, epoch = taskEpoch) {
    return () => isCurrentTask(epoch) && liveRunId() === runId;
  }
  function requireCurrentRun(runId: string, epoch = taskEpoch) {
    if (!currentRunGuard(runId, epoch)()) throw new Error("stale task result");
  }
  function stopCurrentRun() {
    const runId = liveRunId();
    if (!runId || !localApiEnabled()) return;
    supersedeActiveRun();
    setLiveRunId(null);
    setCandidateScreening(null);
    setCandidatePdfTarget(null);
    setDraftContent("");
    setReviewedPlan("");
    setPlanApproved(false);
    setApprovedQueryCount(0);
    setApprovedCounterQueryCount(0);
    setStatus(text("已请求停止当前本地任务。已登记的工件保留供回看；迟到的检索或解析结果将被忽略。", "Stop requested for the current local task. Registered artifacts remain reviewable; late retrieval or parsing results will be ignored."));
  }
  function enterBridge() {
    if (updateMission()) navigate("workflow");
  }
  /**
   * Candidate screening, private PDF tasks, and draft-plan controls belong to
   * one loopback run. Never let them cross into a newly created/restored run.
   * Imported UI bundles are handled separately because hydration may retain a
   * matching in-run PDF task while refreshing its graph projection.
   */
  function clearRunScopedClientArtifacts() {
    setCandidateScreening(null);
    setCandidatePdfTarget(null);
    setPdfTask(null);
    setPdfTasks([]);
    setResearchSession(emptyResearchSession());
    setDraftContent("");
    setReviewedPlan("");
    setPlanApproved(false);
    setApprovedQueryCount(0);
    setApprovedCounterQueryCount(0);
  }
  function openManualTaskControl() {
    if (launchPreview()) { setStatus(text("只读预览不允许打开手动执行控制。", "The read-only preview cannot open manual execution controls.")); return; }
    setManualControlOpen(true);
    setView("discover");
    setStatus(text("已打开高级手动受控执行。请先核对任务边界、计划与数据源，再执行反例检索。", "Advanced manual control is open. Verify the task boundary, plan, and sources before running counterevidence retrieval."));
  }

  function applyImportedBundle(imported: ImportedBundle, preserveResearchSession = false) {
    const previousSession = researchSession();
    setBundle(imported);
    setQuestion(imported.mission.question);
    resetMissionBoundary(imported.mission);
    setArtifactBoundaryFingerprint(taskBoundaryFingerprint(imported.mission));
    setTaskArtifactLocked(false);
    setResearchSession(preserveResearchSession ? reconcileResearchSession(imported, previousSession) : emptyResearchSession());
    setCandidateScreening(null);
    setCandidatePdfTarget(null);
  }

  async function hydrateLiveRunBundle(runId: string, stillCurrent: () => boolean = () => true, preserveResearchSession = false): Promise<ImportedBundle> {
    const imported = readBundle(await fetchLiveUiBundle(runId), "loopback");
    if (!stillCurrent()) throw new Error("stale task result");
    applyImportedBundle(imported, preserveResearchSession);
    if (localApiEnabled()) {
      try {
        const screening = await getCandidateScreening(runId);
        if (!stillCurrent()) throw new Error("stale task result");
        setCandidateScreening(screening);
      } catch (error) {
        if (!stillCurrent()) throw error;
        setCandidateScreening(null);
      }
    }
    return imported;
  }

  async function loadCandidateScreening() {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可筛选的本地任务。", "There is no local task available for screening."));
    const epoch = taskEpoch;
    const screening = await getCandidateScreening(runId);
    requireCurrentRun(runId, epoch);
    setCandidateScreening(screening);
  }

  async function submitCandidateScreening(decisions: CandidateScreeningDecision[]) {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可提交的本地任务。", "There is no local task available for submission."));
    const epoch = taskEpoch;
    const result = await recordCandidateScreening(runId, decisions);
    requireCurrentRun(runId, epoch);
    const refreshedScreening = await getCandidateScreening(runId);
    requireCurrentRun(runId, epoch);
    setCandidateScreening(refreshedScreening);
    await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
    requireCurrentRun(runId, epoch);
    setStatus(text(`已提交 ${result.candidate_count} 篇候选论文的人工筛选；“纳入”仅开放后续受控全文流程。`, `Human screening was submitted for ${result.candidate_count} candidate paper(s); inclusion only opens a later controlled full-text workflow.`));
  }

  function prepareCandidatePdf(candidate: CandidateScreeningCandidate) {
    const runId = liveRunId();
    if (!runId) { setStatus(text("当前没有可关联候选的本地任务。", "There is no local task to link this candidate to.")); return; }
    const gate = candidateFulltextGate(candidateScreening(), bundle().literatureGraph.nodes, candidate);
    if (!gate.ready) {
      const reason = ({ screening: text("人工筛选尚未完整提交并重新载入", "the human screening record is not persisted"), candidate: text("候选不属于当前筛选清单", "the candidate is not in the current screening checklist"), decision: text("该候选未被纳入全文核对", "the candidate is not included for full-text review"), paper: text("当前文献星图没有对应的可审查论文", "the current literature map has no matching reviewable paper") } as const)[gate.reason!];
      setStatus(text(`不能进入 PDF 入港：${reason}。请返回文献星图完成或刷新人工筛选。`, `PDF intake is blocked because ${reason}. Return to the literature map to complete or refresh human screening.`));
      return;
    }
    const paper = reviewablePaperForDocumentId(bundle().literatureGraph.nodes, candidate.document_id)!;
    setResearchSession(selectPaper(emptyResearchSession(), paper));
    setCandidatePdfTarget({ runId, documentId: candidate.document_id, title: candidate.title });
    setView("launch");
    setStatus(text(`已选择“${candidate.title}”。请仅选择你有权处理的对应 PDF；提交时会再次核验该候选的人工纳入记录。`, `Selected “${candidate.title}”. Choose only the corresponding PDF you are authorized to process; the human inclusion record will be checked again on submission.`));
  }
  function upsertPdfTask(task: PdfTaskStatus, select = true) {
    setPdfTasks((current) => [...current.filter((item) => item.document_id !== task.document_id), task]);
    if (select) setPdfTask(task);
  }
  async function refreshPdfTask(runId = liveRunId(), documentId = pdfTask()?.document_id, stillCurrent: () => boolean = () => true, announce = true) {
    if (!runId || !documentId) throw new Error(text("当前没有已选择的 PDF 解析任务。", "There is no selected PDF parsing task."));
    const epoch = taskEpoch;
    const guard = () => stillCurrent() && currentRunGuard(runId, epoch)();
    const task = await getPdfStatus(runId, documentId);
    if (!guard()) throw new Error("stale task result");
    upsertPdfTask(task);
    if (task.state === "failed") setStatus(text(`PDF 解析失败：${task.error ?? "未提供原因"}`, `PDF parsing failed: ${task.error ?? "no reason provided"}`));
    else if (announce) setStatus(text(`PDF 解析状态：${task.state}；DOI：${task.doi_status}。`, `PDF parsing status: ${task.state}; DOI: ${task.doi_status}.`));
  }
  async function refreshPdfTasks(runId = liveRunId(), stillCurrent: () => boolean = () => true) {
    if (!runId) return [];
    const epoch = taskEpoch;
    const registry = await getPdfTasks(runId);
    if (!stillCurrent() || !currentRunGuard(runId, epoch)()) return [];
    setPdfTasks(registry.tasks);
    setPdfTask((selected) => registry.tasks.find((item) => item.document_id === selected?.document_id) ?? registry.tasks[0] ?? null);
    return registry.tasks;
  }

  createEffect(() => {
    const runId = liveRunId();
    const tasks = pdfTasks();
    if (!localApiEnabled() || !runId || !tasks.some((task) => shouldPollPdfTask(runId, task))) return;
    const timer = window.setInterval(() => {
      void refreshPdfTasks(runId, () => liveRunId() === runId).catch(() => undefined);
    }, 5000);
    onCleanup(() => window.clearInterval(timer));
  });

  async function confirmManualPdfDoi(doi: string) {
    const runId = liveRunId();
    if (!runId || !pdfTask()) throw new Error(text("当前没有可确认 DOI 的 PDF 任务。", "There is no PDF task available for DOI confirmation."));
    const epoch = taskEpoch;
    const task = await confirmPdfDoi(runId, pdfTask()!.document_id, doi);
    requireCurrentRun(runId, epoch);
    setPdfTask(task);
    setStatus(text(`已人工确认 DOI：${task.doi}。它仅用于书目引文导航，不构成材料证据。`, `Human-confirmed DOI: ${task.doi}. It is used only for bibliographic navigation, not materials evidence.`));
  }

  async function loadPrivateSourceMap(): Promise<SourceMapRecordResult> {
    const runId = liveRunId();
    if (!runId || !pdfTask()) throw new Error(text("当前没有可恢复来源定位的 PDF 任务。", "There is no PDF task available for Source Map recovery."));
    const epoch = taskEpoch;
    const result = await getPdfSourceMapContext(runId, pdfTask()!.document_id);
    requireCurrentRun(runId, epoch);
    return result;
  }
  async function recordPrivateSourceMap(segments: PrivateSourceMapSegment[]): Promise<SourceMapRecordResult> {
    const runId = liveRunId();
    if (!runId || !pdfTask()) throw new Error(text("当前没有可登记来源定位的 PDF 任务。", "There is no PDF task available for Source Map recording."));
    const epoch = taskEpoch;
    const result = await recordPdfSourceMap(runId, pdfTask()!.document_id, segments);
    requireCurrentRun(runId, epoch);
    await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
    await refreshPdfTask(runId, pdfTask()!.document_id, currentRunGuard(runId, epoch));
    requireCurrentRun(runId, epoch);
    setStatus(text(`已登记 ${result.segment_count} 条人工来源定位。它们仍不是 EvidenceCard；下一步是人工登记受控材料事实。`, `${result.segment_count} human-reviewed source locations were recorded. They are not EvidenceCards; human-reviewed material fact registration remains next.`));
    return result;
  }
  async function recordPrivateMaterialFacts(facts: HumanMaterialFactInput[]) {
    const runId = liveRunId();
    if (!runId || !pdfTask()) throw new Error(text("当前没有可登记材料事实的 PDF 任务。", "There is no PDF task available for material-fact registration."));
    const epoch = taskEpoch;
    const result = await recordPdfMaterialFacts(runId, pdfTask()!.document_id, facts);
    requireCurrentRun(runId, epoch);
    await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
    requireCurrentRun(runId, epoch);
    setStatus(text(`已登记 ${result.fact_count} 条人工复核的材料事实。它们不是 EvidenceCard，也不构成科学结论。`, `${result.fact_count} human-reviewed material facts were recorded. They are not EvidenceCards or scientific conclusions.`));
  }
  async function recordPrivateEvidenceCard(input: HumanEvidenceReviewInput): Promise<EvidenceReviewResult> {
    const runId = liveRunId();
    if (!runId || !pdfTask()) throw new Error(text("当前没有可接受 EvidenceCard 的 PDF 任务。", "There is no PDF task available for EvidenceCard acceptance."));
    const epoch = taskEpoch;
    const result = await recordPdfEvidenceCard(runId, pdfTask()!.document_id, input);
    requireCurrentRun(runId, epoch);
    const imported = await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
    requireCurrentRun(runId, epoch);
    const evidence = imported.evidenceCards.find((item) => item.evidenceId === result.evidence_id);
    const paper = reviewablePaperForDocumentId(imported.literatureGraph.nodes, result.document_id);
    if (evidence && paper) setResearchSession(selectEvidence(selectPaper(emptyResearchSession(), paper), evidence));
    setStatus(text(`已人工接受 ${result.evidence_id}。该卡仅绑定当前文献与定位符；请在文献星图核对关联后，再进入研究拓展。`, `${result.evidence_id} was accepted by human review. It is bound only to this paper and locator; inspect its graph link before entering research extension.`));
    return result;
  }
  async function buildConditionMatrix() {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可诊断的本地任务。", "There is no local task available for diagnostics."));
    const epoch = taskEpoch;
    const result = await diagnoseConditions(runId);
    requireCurrentRun(runId, epoch);
    await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
    requireCurrentRun(runId, epoch);
    setStatus(text(`已生成 ${result.matrix_row_count} 个确定性条件比较行；它们不是科学结论。`, `${result.matrix_row_count} deterministic condition-comparison row(s) were generated; they are not scientific conclusions.`));
  }
  async function buildGapCandidates() {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可生成候选的本地任务。", "There is no local task available for candidate generation."));
    const epoch = taskEpoch;
    const result = await generateGapCandidates(runId);
    requireCurrentRun(runId, epoch);
    await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
    requireCurrentRun(runId, epoch);
    setStatus(text(`已生成 ${result.candidate_count} 个证据约束候选，均需人工复核。`, `${result.candidate_count} evidence-bound candidate(s) were generated; all require human review.`));
  }
  async function expandPdfCitationGraph() {
    const runId = liveRunId();
    if (!runId || !pdfTask()?.markdown_ready || !["resolved", "human_confirmed"].includes(pdfTask()!.doi_status)) return;
    const epoch = taskEpoch;
    const result = await expandPdfCitations(runId, pdfTask()!.document_id);
    requireCurrentRun(runId, epoch);
    const imported = await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
    requireCurrentRun(runId, epoch);
    if (!hasNavigableLiteratureGraph(imported)) {
      setStatus(text("引文扩展已完成，但未返回可导航的 DOI 关系；仍保留在舰桥，可更换 DOI 或检查来源配置。", "Citation expansion completed but returned no navigable DOI relation. The workflow stays on the bridge; confirm the DOI or source configuration."));
      setView("workflow");
      return;
    }
    setStatus(text(`已建立双向两层书目图：${result.node_count} 个节点、${result.edge_count} 条关系。它只用于文献导航，不构成材料证据。`, `A two-hop bidirectional bibliography map was built: ${result.node_count} nodes and ${result.edge_count} relations. It is for literature navigation only, not materials evidence.`));
    setView("graph");
  }  async function refreshAutomaticMission(runId: string, stillCurrent: () => boolean = () => true) {
    const epoch = taskEpoch;
    const guard = () => stillCurrent() && currentRunGuard(runId, epoch)();
    const summary = await getRunStatus(runId);
    if (!guard()) return;
    const automatic = summary.automatic_execution;
    if (!automatic) {
      setAutomaticMissionPending(false);
      setAutomaticGraphHandoffPending(false);
      setAutomaticExecution(null);
    setAutomaticAuthorization(null);
      setStatus(text("本机服务未返回自动任务状态摘要；当前保留空任务壳，不会载入演示文献。", "The local service returned no automatic-task status summary. The empty mission shell is retained and no demo literature is loaded."));
      return;
    }
    setAutomaticExecution(automatic);
    if (["queued", "running"].includes(automatic.state)) {
      setAutomaticMissionPending(true);
      setStatus(text(`自动元数据检索${automatic.state === "queued" ? "已排队" : "正在执行"}；尚未返回可审查文献。`, `Automatic metadata retrieval is ${automatic.state}; no reviewable literature has returned yet.`));
      return;
    }
    setAutomaticMissionPending(false);
    if (automatic.state === "cancelled") {
      setAutomaticGraphHandoffPending(false);
      setStatus(text("自动元数据检索已取消；空任务壳保留，迟到结果不会写入当前任务。", "Automatic metadata retrieval was cancelled. The empty mission shell is retained and late results are not written into this task."));
      return;
    }
    if (automatic.state === "failed") {
      setAutomaticGraphHandoffPending(false);
      setStatus(text(`自动元数据检索失败（${automatic.failure_count} 个受控来源失败）；空任务壳保留，可调整任务边界后重试。`, `Automatic metadata retrieval failed (${automatic.failure_count} controlled provider failure(s)). The empty mission shell is retained; adjust the boundary before retrying.`));
      return;
    }
    const imported = readBundle(await fetchLiveUiBundle(runId), "loopback");
    if (!guard()) return;
    applyImportedBundle(imported);
    try {
      const screening = await getCandidateScreening(runId);
      if (guard()) setCandidateScreening(screening);
    } catch {
      if (guard()) setCandidateScreening(null);
    }
    if (!guard()) return;
    const failedSources = automatic.failed_sources?.length ? automatic.failed_sources.join("、") : automatic.failure_count ? String(automatic.failure_count) : "";
    const warning = automatic.failure_count ? text(`；来源告警：${failedSources}`, `; provider warning(s): ${failedSources}`) : "";
    if (!hasNavigableLiteratureGraph(imported)) {
      setAutomaticGraphHandoffPending(false);
      setStatus(text(`自动任务已完成，但未返回可导航的候选论文或 DOI 关系${warning}。请在舰桥检查已选来源，或调整任务边界后重新执行。`, `Automatic task completed but returned no navigable candidate paper or DOI relation${warning}. Inspect selected sources on the bridge or revise the task boundary before rerunning.`));
      return;
    }
    setStatus(text(`自动任务已返回 ${imported.literatureGraph.nodes.length} 个脱敏图谱节点${warning}。下一步是逐篇完成人工筛选；候选元数据仍不是已接受证据。`, `Automatic task returned ${imported.literatureGraph.nodes.length} redacted graph nodes${warning}. Next, complete human screening for each candidate; candidate metadata is not accepted evidence.`));
    // The automatic path stops before any scientific-evidence decision. A
    // completed retrieval may have won the launch-transition race, so the
    // effect below performs the one safe bridge-to-map handoff when relevant.
  }

  createEffect(() => {
    const target = automaticGraphHandoffTarget(
      automaticGraphHandoffPending(),
      automaticExecution()?.state,
      view() === "launch" ? "discover" : view() as Exclude<View, "launch">,
      hasNavigableLiteratureGraph(bundle()),
    );
    if (target) {
      setAutomaticGraphHandoffPending(false);
      setView(target);
    }
  });

  createEffect(() => {
    const runId = liveRunId();
    const automatic = automaticExecution();
    if (!localApiEnabled() || !runId || !automatic || !["queued", "running"].includes(automatic.state)) return;
    const poll = () => void refreshAutomaticMission(runId, () => liveRunId() === runId).catch((error) => {
      if (liveRunId() === runId) setStatus(error instanceof Error ? error.message : text("无法刷新自动任务状态。", "Unable to refresh automatic task status."));
    });
    const timer = window.setInterval(poll, 2500);
    onCleanup(() => window.clearInterval(timer));
  });
  function beginLaunchMission(mission: LaunchMission) {
    const nextMission = {
      missionId: newLocalMissionId(),
      question: mission.question.trim(),
      material: mission.material.trim(),
      property: mission.property.trim(),
      scope: mission.scope.trim(),
    };
    const missingBoundary = launchMissionMissingFields(nextMission).map((field) => ({ question: text("研究问题", "research question"), material: text("研究对象", "research objects"), property: text("研究目标／比较维度", "research targets / comparison dimensions"), scope: text("研究边界／比较范围", "research boundaries / comparison scope") } as const)[field]);
    if (missingBoundary.length) { setStatus(text(`请先补齐或替换待确认内容：${missingBoundary.join("、")}。`, `Complete or replace unconfirmed content: ${missingBoundary.join(", ")}.`)); return; }
    const missionEpoch = supersedeActiveRun();
    setLiveRunId(null); setPdfTask(null); setPdfTasks([]); setCandidateScreening(null);
    applyImportedBundle(emptyBundleForMission(nextMission));
    setStatus(localApiEnabled()
      ? text("任务已确认；正在登记一次已授权的自动元数据检索。完成前仅显示空任务壳，候选元数据仍不是证据。", "Mission confirmed; registering the one-time authorised metadata retrieval. Until it finishes, only an empty task shell is shown and candidate metadata is not evidence.")
      : text("任务已确认；当前仅建立空任务壳。文献子图必须由受控检索或导入工件填充。", "Mission confirmed; only an empty task shell exists. A literature map can be populated only by controlled retrieval or imported artifacts."));
    if (localApiEnabled()) {
      setAutomaticMissionPending(true);
      setAutomaticGraphHandoffPending(true);
      void createAutomaticMission({ question: nextMission.question, material: nextMission.material, property: nextMission.property, scope: nextMission.scope, sources: retrievalSources() }).then((result) => {
        if (!isCurrentTask(missionEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
        const authorization = result.harness_authorization;
        if (!authorization || authorization.trust_status !== "authorization_checked_before_automatic_dispatch") {
          void cancelRun(result.run_id).catch(() => undefined);
          setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false);
          setStatus(text("本机服务未返回自动检索的 Harness 授权审计；已请求取消该运行，当前仅保留空任务壳。", "The local service returned no Harness authorization audit for automatic retrieval. Cancellation was requested and only the empty mission shell is retained."));
          return;
        }
        setLiveRunId(result.run_id);
        setAutomaticAuthorization(authorization);
        const automatic = result.status.automatic_execution ?? { state: "queued", candidate_count: 0, failure_count: 0, planning_warning: false, trust_status: result.trust_status };
        setAutomaticExecution(automatic);
        setAutomaticMissionPending(["queued", "running"].includes(automatic.state));
        void refreshAutomaticMission(result.run_id, () => isCurrentTask(missionEpoch)).catch((error) => {
          if (isCurrentTask(missionEpoch)) { setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false); setStatus(error instanceof Error ? error.message : text("无法刷新自动本地任务；当前保留空任务壳。", "Unable to refresh the automatic local task; the empty task shell is retained.")); }
        });
      }).catch((error: unknown) => { if (isCurrentTask(missionEpoch)) { setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false); setAutomaticExecution(null); setStatus(error instanceof Error ? error.message : text("无法启动自动本地任务；当前保留空任务壳。", "Unable to start the automatic local task; the empty task shell is retained.")); } });
    }
    scheduleCurrentView(missionEpoch, "workflow");
  }
  function beginPdfMission(file: File, candidateTarget?: LaunchPdfCandidateTarget) {
    if (!localApiEnabled()) {
      setStatus(text("PDF 入港需要以 ?api=local 启动本机环回 API；未创建解析任务，也不会上传文件。", "PDF intake requires the local loopback API (?api=local). No parsing task was created and no file was uploaded."));
      return;
    }
    if (candidateTarget) {
      if (!liveRunId() || liveRunId() !== candidateTarget.runId) {
        setStatus(text("候选全文入口已失效；请回到文献星图重新选择已人工纳入的候选。", "The candidate full-text entry has expired; return to the literature map and reselect a human-included candidate."));
        return;
      }
      const pdfEpoch = taskEpoch;
      void createPdfRun(file, bundle().mission, { runId: candidateTarget.runId, documentId: candidateTarget.documentId }).then((result) => {
        if (!isCurrentTask(pdfEpoch) || liveRunId() !== candidateTarget.runId) { void cancelRun(result.run_id).catch(() => undefined); return; }
        setCandidatePdfTarget(null);
        upsertPdfTask({ document_id: result.document_id, candidate_document_id: result.candidate_document_id ?? candidateTarget.documentId, audit_document_id: result.candidate_document_id ?? candidateTarget.documentId, audit_state: "pending", file_name: file.name, state: result.state, doi: null, doi_status: result.doi_status, markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence" });
        setStatus(text(`已将授权 PDF 关联到已人工纳入的候选“${candidateTarget.title}”；MinerU 任务当前为 ${result.state}。Markdown 始终位于本机私有缓存。`, `The authorized PDF is linked to the human-included candidate “${candidateTarget.title}”; the MinerU task is ${result.state}. Markdown remains in local private cache.`));
        setView("workflow");
        void refreshPdfTask(result.run_id).catch(() => undefined);
      }).catch((error: unknown) => { if (isCurrentTask(pdfEpoch) && liveRunId() === candidateTarget.runId) setStatus(error instanceof Error ? error.message : text("无法提交候选 PDF 入港任务。", "Unable to submit the candidate PDF intake task.")); });
      return;
    }
    const nextMission = {
      missionId: newLocalMissionId(),
      question: `Parse and map the literature network for ${file.name}`,
      material: "User-authorized PDF",
      property: "Markdown conversion and citation navigation",
      scope: `Local PDF intake: ${file.name}`,
    };
    const pdfEpoch = supersedeActiveRun();
    setCandidatePdfTarget(null); setLiveRunId(null); setPdfTask(null); setPdfTasks([]);
    applyImportedBundle(emptyBundleForMission(nextMission));
    setStatus(text("已建立私有 PDF 任务壳；在 MinerU 解析、DOI 识别和引文工件返回前，不显示任何演示论文或来源定位。", "A private PDF task shell was created. No demo paper or source locator is shown before MinerU parsing, DOI recognition, and citation artifacts return."));
    {
      void createPdfRun(file, nextMission).then((result) => {
        if (!isCurrentTask(pdfEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
        setLiveRunId(result.run_id);
        upsertPdfTask({ document_id: result.document_id, candidate_document_id: result.candidate_document_id ?? null, audit_document_id: result.candidate_document_id ?? result.document_id, audit_state: "pending", file_name: file.name, state: result.state, doi: null, doi_status: result.doi_status, markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence" });
        setStatus(text(`私有 PDF 任务 ${result.run_id} 当前为 ${result.state}；Markdown 始终位于本机私有缓存，等待 DOI 与书目工件。`, `Private PDF task ${result.run_id} is ${result.state}; Markdown remains in local private cache while DOI and bibliographic artifacts are pending.`));
        void refreshPdfTask(result.run_id).catch(() => undefined);
      }).catch((error: unknown) => { if (isCurrentTask(pdfEpoch)) setStatus(error instanceof Error ? error.message : text("无法提交私有 PDF 任务。", "Unable to submit the private PDF task.")); });
    }
    scheduleCurrentView(pdfEpoch, "workflow");
  }

  function resumeLaunch(file: File) {
    if (!file.name.endsWith(".cosmatter-run.json")) { setStatus(text("续航入口只接受 .cosmatter-run.json；旧 UI JSON 请在工作台的只读导入中打开。", "Continuation accepts only .cosmatter-run.json; open legacy UI JSON through the workbench read-only import.")); return; }
    const resumeEpoch = supersedeActiveRun();
    void file.text().then(async (raw) => {
      const payload = JSON.parse(raw) as { mission?: { question?: string; material?: string; property_name?: string; scope?: string }; package_type?: string };
      if (payload.package_type !== "cosmatter_run" || !payload.mission?.question || !payload.mission.material || !payload.mission.property_name || !payload.mission.scope) throw new Error(text("运行包缺少可恢复的任务简报。", "The run package has no recoverable mission brief."));
      if (!localApiEnabled()) throw new Error(text("续航需要以 ?api=local 启动本机环回 API。", "Continuation requires the local loopback API (?api=local)."));
      const result = await importRunPackage(payload);
      if (!isCurrentTask(resumeEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
      clearRunScopedClientArtifacts();
      setLiveRunId(result.run_id);
      let artifactsHydrated = false;
      try {
        await hydrateLiveRunBundle(result.run_id, () => isCurrentTask(resumeEpoch));
        if (!isCurrentTask(resumeEpoch)) return;
        try { await refreshPdfTasks(result.run_id, () => isCurrentTask(resumeEpoch)); } catch { if (isCurrentTask(resumeEpoch)) { setPdfTask(null); setPdfTasks([]); } }
        artifactsHydrated = true;
        const resumeStage = continuationStageLabel(result.next_stage, language());
        setStatus(text(`运行包已恢复为 ${result.run_id}；将在“${resumeStage}”阶段继续，不会重新发起自动检索。`, `Run package restored as ${result.run_id}; continuing at ${resumeStage} without starting a new automatic retrieval.`));
      } catch (error) {
        if (!isCurrentTask(resumeEpoch)) return;
        const detail = error instanceof Error ? error.message : text("无法载入运行工件", "Unable to load run artifacts");
        const fallbackMission = { missionId: newLocalMissionId(), question: payload.mission.question, material: payload.mission.material, property: payload.mission.property_name, scope: payload.mission.scope };
        applyImportedBundle(emptyBundleForMission(fallbackMission));
        setStatus(text(`运行包已登记，但工件未能载入：${detail}。已保留空任务壳，且不会重新发起自动检索。`, `Run package was registered but artifacts could not be loaded: ${detail}. An empty task shell is retained and no automatic retrieval was restarted.`));
      }
      setView(viewForRestoredRun(result.next_stage, artifactsHydrated));
    }).catch((error: unknown) => setStatus(error instanceof Error ? error.message : text("无法解析运行包。", "Unable to parse the run package.")));
  }

  function importBundle(file: File | undefined) {
    if (!file) return;
    const importEpoch = supersedeActiveRun();
    void file.text().then((raw) => {
      const imported = readBundle(JSON.parse(raw));
      if (!isCurrentTask(importEpoch)) return;
      setLiveRunId(null); setPdfTask(null); setPdfTasks([]);
      applyImportedBundle(imported);
      setStatus(text(`已导入 ${file.name}；仅在浏览器解析本地 JSON 工件。`, `Imported ${file.name}; the local JSON artifact was parsed only in this browser.`));
    }).catch((error: unknown) => setStatus(error instanceof Error ? error.message : text("无法解析该 JSON 工件。", "Unable to parse this JSON artifact.")));
  }

  async function launchLiveMission() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    if (!updateMission()) return;
    const mission = bundle().mission;
    try {
      const launchEpoch = supersedeActiveRun();
      clearRunScopedClientArtifacts();
      setLiveRunId(null);
      const result = await createLiveMission({ question: mission.question, material: mission.material, property: mission.property, scope: mission.scope });
      if (!isCurrentTask(launchEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
      setLiveRunId(result.run_id);
      try {
        await hydrateLiveRunBundle(result.run_id, currentRunGuard(result.run_id, launchEpoch));
      } catch (error) {
        if (!isCurrentTask(launchEpoch)) return;
        applyImportedBundle(emptyBundleForMission({ ...mission, missionId: result.mission_id }));
        setStatus(text(`已创建受控本地任务 ${result.run_id}，但空工件未能载入：${error instanceof Error ? error.message : "未知原因"}。界面不会保留旧任务数据。`, `Controlled local mission ${result.run_id} was created, but its empty artifacts could not be loaded: ${error instanceof Error ? error.message : "unknown reason"}. The UI will not retain data from the prior task.`));
        return;
      }
      requireCurrentRun(result.run_id, launchEpoch);
      setStatus(text(`已启动受控本地任务 ${result.run_id}；当前仅显示该任务的空工件，下一步可起草并人工批准检索计划。`, `Controlled local mission ${result.run_id} started. Only this task’s empty artifacts are shown; draft and approve a retrieval plan next.`));
    } catch (error) { setStatus(error instanceof Error ? error.message : text("无法启动本地 API 任务。", "Unable to start the local API mission.")); }
  }
  async function requestPlanDraft() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId) return;
    const epoch = taskEpoch;
    try {
      const result = await draftLivePlan(runId);
      requireCurrentRun(runId, epoch);
      setDraftContent(result.content);
      setStatus(text("已取得未受信草案；必须人工复核后才能批准。", "An untrusted draft is available; human review is required before approval."));
    } catch (error) {
      if (currentRunGuard(runId, epoch)()) setStatus(error instanceof Error ? error.message : text("无法请求计划草案。", "Unable to request a plan draft."));
    }
  }
  async function approveReviewedPlan() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId) return;
    const epoch = taskEpoch;
    try {
      const result = await approveLivePlan(runId, JSON.parse(reviewedPlan()));
      requireCurrentRun(runId, epoch);
      setPlanApproved(true); setApprovedQueryCount(result.queries.length); setApprovedCounterQueryCount(result.counter_queries.length);
      setStatus(text(`已批准 ${result.queries.length} 条主检索式与 ${result.counter_queries.length} 条反例检索式。`, `${result.queries.length} primary and ${result.counter_queries.length} counterevidence queries were approved.`));
    } catch (error) {
      if (currentRunGuard(runId, epoch)()) setStatus(error instanceof Error ? error.message : text("复核计划必须是有效 JSON。", "The reviewed plan must be valid JSON."));
    }
  }
  async function executeApprovedQueries() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId || !planApproved() || !approvedQueryCount() || !retrievalSources().length) return;
    const executionEpoch = taskEpoch;
    const stillCurrent = () => isCurrentTask(executionEpoch) && liveRunId() === runId;
    try {
      let received = 0;
      for (let index = 0; index < approvedQueryCount(); index += 1) {
        if (!stillCurrent()) { void cancelRun(runId).catch(() => undefined); return; }
        received += (await executeApprovedQuery(runId, index, retrievalSources())).candidate_count;
      }
      for (let index = 0; index < approvedCounterQueryCount(); index += 1) {
        if (!stillCurrent()) { void cancelRun(runId).catch(() => undefined); return; }
        received += (await executeApprovedQuery(runId, index, retrievalSources(), true)).candidate_count;
      }
      await hydrateLiveRunBundle(runId, stillCurrent);
      if (!stillCurrent()) return;
      setStatus(text(`已完成 ${approvedQueryCount()} 条主检索与 ${approvedCounterQueryCount()} 条反例检索，收到 ${received} 条候选元数据（去重前）。`, `Completed ${approvedQueryCount()} primary and ${approvedCounterQueryCount()} counterevidence queries with ${received} candidate metadata records before deduplication.`));
      navigate("graph");
    } catch (error) {
      if (!stillCurrent()) return;
      setStatus(error instanceof Error ? error.message : text("无法执行已批准检索。", "Unable to execute the approved retrieval."));
    }
  }
  function toggleSource(source: RetrievalSource) { setRetrievalSources((current) => current.includes(source) ? current.filter((item) => item !== source) : [...current, source]); }

  function choosePaper(node: LiteratureGraphNode) {
    if (launchPreview()) { setStatus(text("只读预览不会写入选中文献或证据会话。", "The read-only preview does not save a selected paper or evidence session.")); return; }
    if (!documentIdForReviewablePaper(node)) { setStatus(text("该节点仅用于书目或结构导航，不能作为当前任务的待核对论文。", "This node is for bibliography or structure navigation only and cannot become the current paper for verification.")); return; }
    setResearchSession((current) => selectPaper(current, node));
    const documentId = documentIdForReviewablePaper(node);
    const matchingPdf = pdfTasks().find((task) => task.candidate_document_id === documentId);
    if (matchingPdf) setPdfTask(matchingPdf);
    setStatus(text(`已选择待核对论文：“${node.label}”。尚未建立来源定位。`, `Selected paper for verification: “${node.label}”. No source locator has been asserted.`));
  }

  function chooseEvidence(evidence: EvidenceCard) {
    if (launchPreview()) { setStatus(text("只读预览不会写入选中文献或证据会话。", "The read-only preview does not save a selected paper or evidence session.")); return; }
    const focused = focusEvidenceSession(bundle(), evidence);
    if (!focused) {
      setStatus(text("该 EvidenceCard 在当前图谱中没有显式的已审核论文—来源关联，不能作为本次核对的证据。", "This EvidenceCard has no explicit reviewed paper-to-source link in the current map and cannot be used for verification."));
      return;
    }
    setResearchSession(focused);
    const matchingPdf = pdfTasks().find((task) => task.candidate_document_id === evidence.provenance.documentId);
    if (matchingPdf) setPdfTask(matchingPdf);
    setStatus(text(`已定位 EvidenceCard ${evidence.evidenceId} 所属论文；状态仅来自导入工件。`, `Focused the paper for accepted EvidenceCard ${evidence.evidenceId}; its status comes only from the imported artifact.`));
  }

  function focusGapEvidence(evidence: EvidenceCard) {
    if (launchPreview()) { setStatus(text("只读预览不会切换证据会话。", "Read-only preview does not switch the evidence session.")); return; }
    const focused = focusEvidenceSession(bundle(), evidence);
    if (!focused) {
      const fallbackView: View = hasNavigableLiteratureGraph(bundle()) ? "graph" : "workflow";
      setStatus(fallbackView === "graph"
        ? text("该 Gap 引用的 EvidenceCard 缺少当前图谱中的明确论文—来源映射；请返回星图补齐工件。", "This Gap-linked EvidenceCard has no explicit paper-to-source mapping in the current graph; return to the map and complete the artifacts.")
        : text("该 Gap 引用的 EvidenceCard 缺少当前图谱中的明确论文—来源映射，且当前没有可导航图谱；请在舰桥重新导入或检索匹配文献。", "This Gap-linked EvidenceCard has no explicit paper-to-source mapping and no navigable graph is available; re-import or retrieve matching literature from the bridge."));
      setView(fallbackView);
      return;
    }
    setResearchSession(focused);
    const matchingPdf = pdfTasks().find((task) => task.candidate_document_id === evidence.provenance.documentId);
    if (matchingPdf) setPdfTask(matchingPdf);
    setStatus(text(`已定位 Gap 所引用的 EvidenceCard ${evidence.evidenceId}；请在阅读页核对其来源定位与条件。`, `Located Gap-linked EvidenceCard ${evidence.evidenceId}; verify its locator and conditions in the reader.`));
    setView("reader");
  }
  onMount(() => {
    if (!localApiEnabled()) return;
    void getLocalApiStatus().then((result) => {
      const enabled = Object.entries(result.providers).filter(([, value]) => value).map(([name]) => name).join(", ");
      setApiProviders(result.providers); setRetrievalSources((current) => { const available = SOURCES.filter((source) => result.providers[source.provider]).map((source) => source.id); return available.length ? available : current; }); setApiSummary(enabled ? text(`本地 API 预览可用：${enabled}。所有执行仍需单独批准。`, `Local API preview available: ${enabled}. Each execution still needs separate approval.`) : text("本地 API 已启动，但未配置服务商。", "Local API is running, but no provider is configured."));
    }).catch((error: unknown) => setApiSummary(error instanceof Error ? error.message : text("无法连接本地 API。", "Unable to reach the local API.")));
  });

  return <div class={`workbench theme-${theme()} view-${view()}`}>
    <Show when={view() === "launch"}><Launchpad onQuestion={beginLaunchMission} onPdf={beginPdfMission} onResume={resumeLaunch} onCandidates={localApiEnabled() ? requestQuestionCandidates : undefined} onPreviewStage={openLaunchPreview} candidatePdfTarget={candidatePdfTarget()} automaticExecutionAvailable={localApiEnabled()} language={language()} theme={theme()} onLanguage={(next) => { setLanguage(next); setUiLanguage(next); }} onTheme={setTheme} /></Show>
    <Show when={view() !== "launch"}>
    <aside class="research-rail" aria-label={text("研究任务导航", "Research task navigation")}>
      <a class="wordmark" href="/" onClick={(event) => { event.preventDefault(); returnToLaunch(); }} aria-label="CosMatter">Cos<span>Matter</span></a>
      <p class="rail-kicker">{text("材料科学证据航线", "MATERIALS EVIDENCE ROUTE")}</p>
      <Show when={launchPreview()}><p class="rail-preview-note">{text("只读预览：可查看阶段与空态，但不能修改任务或执行外部操作。", "Read-only preview: stages and empty states are viewable, but task changes and external actions are unavailable.")}</p></Show>
      <ol class="journey-track" aria-label={text("研究阶段", "Research stages")}>
        <For each={journey()}>{(stage, index) => <li class={`journey-${stage.state}`}><button type="button" aria-current={stage.view === view() ? "step" : undefined} title={journeyStateLabel(stage)} onClick={() => navigate(stage.view)}><span>{String(index() + 1).padStart(2, "0")}</span><div><strong>{language() === "zh" ? stage.zh : stage.en}</strong><small>{journeyStateLabel(stage)}</small></div></button></li>}</For>
      </ol>
      <section class="mission-identity" aria-label={text("当前任务", "Current mission")}>
        <small>{text("当前研究任务", "CURRENT MISSION")}</small><strong>{bundle().mission.material}</strong><span>{bundle().mission.property}</span><em>{bundle().status?.missionState ?? "LOCAL"}</em><Show when={taskArtifactLocked()}><b class="artifact-lock">{text("旧工件待重新核验", "ARTIFACTS REQUIRE RECHECK")}</b></Show>
      </section>
      <section class="rail-stats" aria-label={text("任务摘要", "Mission summary")}>
        <div><strong>{reviewablePaperCount(bundle())}</strong><span>{text("可审查文献", "reviewable papers")}</span></div>
        <div><strong>{auditableAcceptedEvidence(bundle()).length}</strong><span>{text("可追溯证据", "auditable evidence")}</span></div>
        <div><strong>{bundle().sourceMapSummary.segmentCount}</strong><span>{text("来源片段", "source segments")}</span></div>
      </section>
      <section class="rail-status" aria-live="polite" aria-label={text("航线提示", "Route relay")}><small>{text("当前航线提示", "ROUTE RELAY")}</small><p>{status()}</p><Show when={routeRecovery()}>{(recovery) => <button type="button" class="rail-recovery-action" onClick={() => navigate(recovery().view)}>{language() === "zh" ? recovery().zh : recovery().en}</button>}</Show></section><Show when={liveRunId() && localApiEnabled()}><section class="rail-execution" aria-label={text("本地任务控制", "Local task control")}><small>{text("受控执行", "CONTROLLED EXECUTION")}</small><p>{text("停止后不会再接收该任务的迟到结果；已登记工件保留供回看。", "After stopping, late results for this task are ignored; registered artifacts remain reviewable.")}</p><button type="button" onClick={stopCurrentRun}>{text("停止当前本地任务", "Stop current local task")}</button></section></Show>
      <Show when={view() === "discover" && !launchPreview()} fallback={view() === "discover" ? <p class="rail-preview-note">{text("预览模式下已隐藏受控执行、文件导入与本地任务修改。", "Controlled execution, file import, and local task changes are hidden in preview mode.")}</p> : null}>
        <p class="rail-definition-note">{text("任务输入与确认位于主工作区；侧栏仅保留导航和受控执行。", "Task inputs and confirmation are in the main workspace; this rail keeps navigation and controlled execution only.")}</p>
        <details class="mission-api" open={manualControlOpen()} onToggle={(event) => setManualControlOpen(event.currentTarget.open)}><summary>{text("高级：手动受控执行", "Advanced: manual controlled execution")}</summary><p>{text("此分步入口用于人工调试或逐步复现；常规研究请使用上方任务确认或起始页问题入口。它不会替代 EvidenceCard 的人工审核。", "This stepwise route is for manual debugging or reproducible execution. For ordinary research, use the mission confirmation above or the launch-page question entry. It never replaces human EvidenceCard review.")}</p><p>{apiSummary()}</p><button type="button" onClick={updateMission}>{text("仅更新本地任务边界", "Update local mission boundary only")}</button><Show when={localApiEnabled()} fallback={<small>{text("此浏览器处于本地预览模式，尚未连接执行 API。", "This browser is in local preview mode; no execution API is connected.")}</small>}><button class="primary-action" type="button" onClick={() => void launchLiveMission()}>{text("启动受控 API 任务", "Start controlled API mission")}</button><Show when={liveRunId()}><button type="button" disabled={!apiProviders().deepseek} onClick={() => void requestPlanDraft()}>{text("起草计划", "Draft plan")}</button><Show when={draftContent()}><label>{text("未受信草案", "Untrusted draft")}<textarea value={draftContent()} readOnly rows="4" /></label></Show><label>{text("人工复核计划 JSON", "Human-reviewed plan JSON")}<textarea value={reviewedPlan()} onInput={(event) => setReviewedPlan(event.currentTarget.value)} rows="5" /></label><button type="button" onClick={() => void approveReviewedPlan()}>{text("批准计划", "Approve plan")}</button><Show when={planApproved()}><fieldset><legend>{text("检索来源", "Retrieval sources")}</legend><For each={SOURCES}>{(source) => <label><input type="checkbox" checked={retrievalSources().includes(source.id)} disabled={!apiProviders()[source.provider]} onChange={() => toggleSource(source.id)} />{source.label}</label>}</For></fieldset><button class="primary-action" type="button" disabled={!retrievalSources().length} onClick={() => void executeApprovedQueries()}>{text("执行已批准检索", "Run approved retrieval")}</button></Show></Show></Show><section class="examples"><p>{text("示例问题", "Suggested questions")}</p><For each={examples()}>{(example) => <button type="button" onClick={() => updateQuestion(example)}>{example}</button>}</For></section><label class="import-control">{text("导入脱敏 UI JSON", "Import redacted UI JSON")}<input type="file" accept="application/json,.json" onChange={(event) => importBundle(event.currentTarget.files?.[0])} /></label></details>
      </Show>
      <div class="rail-footer"><div class="language-toggle" aria-label="Language"><button type="button" classList={{ active: language() === "zh" }} onClick={() => { setLanguage("zh"); setUiLanguage("zh"); }}>ZH</button><button type="button" classList={{ active: language() === "en" }} onClick={() => { setLanguage("en"); setUiLanguage("en"); }}>EN</button></div><label>{text("主题", "Theme")}<select value={theme()} onChange={(event) => setTheme(event.currentTarget.value as Theme)}><option value="light">{text("浅色", "Light")}</option><option value="dark">{text("深色", "Dark")}</option><option value="eye">{text("护眼", "Eye care")}</option></select></label></div>
    </aside>
    <Show when={view() === "discover"} fallback={view() === "workflow" ? <FleetCommand bundle={bundle()} locale={language()} selectedDocumentId={selectedDocumentId()} pdfTask={pdfTask()} pdfTasks={pdfTasks()} onSelectPdf={(task) => setPdfTask(task)} markdownUrl={pdfTask() && liveRunId() ? privateMarkdownUrl(liveRunId()!, pdfTask()!.document_id) : null} onRefreshPdf={pdfTask() ? refreshPdfTask : undefined} onConfirmPdfDoi={pdfTask() ? confirmManualPdfDoi : undefined} onExpandPdfCitations={pdfTask() ? expandPdfCitationGraph : undefined} onOpenTaskControl={openManualTaskControl} automaticMissionPending={automaticMissionPending()} automaticAuthorization={automaticAuthorization()} onNavigate={navigate} /> : view() === "graph" ? <GraphNetwork bundle={bundle()} theme={theme()} locale={language()} selectedDocumentId={selectedDocumentId()} pdfTask={pdfTask()} pdfTasks={pdfTasks()} screening={candidateScreening()} onLoadScreening={liveRunId() ? loadCandidateScreening : undefined} onSubmitScreening={liveRunId() ? submitCandidateScreening : undefined} onRequestFulltext={liveRunId() ? prepareCandidatePdf : undefined} onNavigate={navigate} onSelectPaper={choosePaper} onSelectEvidence={chooseEvidence} /> : view() === "reader" ? <PaperReader bundle={bundle()} session={researchSession()} pdfTask={pdfTask()} screeningAllowsSourceReview={selectedPaperScreenedForFulltext()} markdownUrl={pdfTask() && liveRunId() ? privateMarkdownUrl(liveRunId()!, pdfTask()!.document_id) : null} onRecordSourceMap={liveRunId() && pdfTask() ? recordPrivateSourceMap : undefined} onLoadSourceMap={liveRunId() && pdfTask() ? loadPrivateSourceMap : undefined} onRecordMaterialFacts={liveRunId() && pdfTask() ? recordPrivateMaterialFacts : undefined} onRecordEvidence={liveRunId() && pdfTask() ? recordPrivateEvidenceCard : undefined} onNavigate={navigate} onSelectEvidence={chooseEvidence} /> : <ResearchExpansion bundle={bundle()} session={researchSession()} onNavigate={navigate} onOpenTaskControl={openManualTaskControl} onBuildConditionMatrix={liveRunId() ? buildConditionMatrix : undefined} onBuildGapCandidates={liveRunId() ? buildGapCandidates : undefined} onFocusEvidence={focusGapEvidence} />}>
      <main class="discovery-stage mission-stage"><FleetDecoration kind="discover" state={fleetVisualState(bundle(), "discover")} />
        <header class="stage-header"><div><p class="stage-kicker">COSMATTER / {text("任务定义", "MISSION DEFINITION")}</p><h1>{text("从问题到可审计的证据航线", "From question to an auditable evidence route")}</h1><p>{bundle().mission.question}</p></div></header>
        <section class="mission-definition-form" aria-label={text("任务草稿", "Mission draft")}>
          <header><p class="stage-kicker">{text("任务草稿", "MISSION DRAFT")}</p><h2>{text("明确可比较的研究边界", "Define comparable research boundaries")}</h2><p>{text("先写清问题，再列出需要共同检索、抽取和核验的对象、维度与范围。以下修改仅在确认后成为当前任务。", "State the question, then list the objects, dimensions, and boundaries to retrieve, extract, and verify together. Changes become the current mission only after confirmation.")}</p></header>
          <label class="question-label"><span>{text("研究问题", "Research question")}</span><textarea ref={questionTextarea} value={question()} onInput={(event) => updateQuestion(event.currentTarget.value)} rows="3" placeholder={text("提出一个可由文献证据回答的问题", "Ask a question that can be answered from literature evidence")} /></label>
          <section class="scope-editor" aria-label={text("任务边界", "Task boundaries")}>
            <label><span>{text("研究对象（可多个）", "Research objects (multiple allowed)")}</span><textarea value={missionBoundary().material} onInput={(event) => updateMissionBoundary("material", event.currentTarget.value)} rows="2" placeholder={text("例如：BiFeO₃；BaTiO₃；SrTiO₃", "e.g. BiFeO₃; BaTiO₃; SrTiO₃")} /></label>
            <label><span>{text("研究目标／比较维度", "Research targets / comparison dimensions")}</span><textarea value={missionBoundary().property} onInput={(event) => updateMissionBoundary("property", event.currentTarget.value)} rows="2" placeholder={text("例如：相稳定性；铁电极化；磁有序", "e.g. phase stability; ferroelectric polarization; magnetic order")} /></label>
            <label><span>{text("研究边界／比较范围", "Research boundaries / comparison scope")}</span><textarea value={missionBoundary().scope} onInput={(event) => updateMissionBoundary("scope", event.currentTarget.value)} rows="2" placeholder={text("例如：外延薄膜；应变、厚度与氧分压", "e.g. epitaxial films; strain, thickness, and oxygen pressure")} /></label>
            <p>{text("使用分号、逗号或换行分隔多个对象与维度；确认后，系统将把它们作为同一研究任务的边界。", "Separate multiple objects or dimensions with semicolons, commas, or new lines. On confirmation, they become boundaries of one research task.")}</p>
          </section>
          <footer class="mission-definition-actions"><span classList={{ "draft-changed": !missionDraftReady() || missionDraftChanged(), "draft-synced": missionDraftReady() && !missionDraftChanged() }}>{!missionDraftReady() ? text(`还需填写：${missionDraftMissing().join("、")}`, `Still required: ${missionDraftMissing().join(", ")}`) : missionDraftChanged() ? text("存在尚未确认的任务变更", "Unconfirmed task changes") : text("草稿与当前任务已同步", "Draft matches the current mission")}</span><button class="primary-action" type="button" disabled={!missionDraftReady()} onClick={enterBridge}>{text("确认任务并进入受控编排", "Confirm mission and enter orchestration")}</button></footer>
        </section>
        <section class="mission-preview" aria-label={text("当前审计态势", "Current audit posture")}><div class="artifact-heading"><div><p class="stage-kicker">{text("当前审计态势", "CURRENT AUDIT POSTURE")}</p><h2>{text("由当前任务与导入工件派生", "Derived from the current task and imported artifacts")}</h2></div><Show when={taskArtifactLocked()}><p class="artifact-lock-notice">{text("任务边界已变更：下游阶段锁定，旧工件仅供回看。", "Task boundary changed: downstream stages are locked; old artifacts are review-only.")}</p></Show></div><div class="artifact-grid"><For each={artifactStatuses()}>{(card, index) => <article class={`artifact-card artifact-${card.state}`}><header><small>{String(index() + 1).padStart(2, "0")}</small><span>{artifactState(card)}</span></header><h2>{artifactTitle(card)}</h2><p>{artifactDetail(card)}</p><dl><For each={card.metrics}>{(metric) => <div><dt>{metricLabel(metric.key)}</dt><dd>{metric.value || (card.key === "brief" ? text("未填写", "Not set") : "—")}</dd></div>}</For></dl><footer>{artifactNext(card)}</footer></article>}</For></div></section>
        <footer class="stage-note">{text("本页只定义任务与边界。问题入口的一次授权可启动受控元数据检索；高级分步执行和任何 EvidenceCard 接受仍保留独立人工门禁。", "This page only defines task boundaries. One-time consent in question entry may start controlled metadata retrieval; advanced stepwise execution and every EvidenceCard acceptance retain separate human gates.")}</footer>
      </main>
    </Show>
    </Show>
  </div>;
}



