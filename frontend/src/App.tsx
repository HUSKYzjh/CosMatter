import { For, Show, Suspense, createEffect, createMemo, createSignal, lazy, onCleanup, onMount, untrack } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { Launchpad, type LaunchMission, type LaunchPdfCandidateTarget } from "./Launchpad";
import { type LaunchPreviewStage } from "./launchStages";
import { launchMissionMissingFields } from "./launchMissionValidation";
import { continuationStageLabel, reconcileRestoredStage, viewForRestoredRun } from "./continuationStage";
import { fleetVisualState } from "./fleetVisualState";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import { previewAllowsRunAction } from "./previewExecutionPolicy";
import { hasNavigableLiteratureGraph, missionJourney, type JourneyStage } from "./missionJourney";
import { automaticGraphHandoffAlreadySettled, automaticGraphHandoffTarget } from "./automaticGraphHandoff";
import { automaticCancellationEnabled } from "./automaticCancellation";
import { reconcileRetrievalSources, type LocalApiCapabilityHealth } from "./localApiCapabilities";
import { liveBundleMatchesRun, runtimeProjectionsMatchRun } from "./liveRunIdentity";
import { operationRecovery, type OperationRecoveryKind } from "./operationRecovery";
import { deriveMissionArtifactStatus, taskBoundaryFingerprint, type MissionArtifactStatus } from "./missionArtifactStatus";
import { auditableAcceptedEvidence, documentIdForReviewablePaper, evidenceForPaper, reviewablePaperCount, reviewablePaperForDocumentId } from "./evidenceLinking";
import { focusEvidenceSession } from "./evidenceSessionFocus";
import { emptyResearchSession, evidenceGate, reconcileResearchSession, selectEvidence, selectPaper, type ResearchSession } from "./researchSession";
import { emptyBundleForMission, newLocalMissionId } from "./missionBundleFactory";
import { approveLivePlan, createLiveMission, createAutomaticMission, createPdfRun, cancelRun, draftAuthorizedPlan, diagnoseConditions, executeAuthorizedApprovedQuery, expandAuthorizedPdfCitations, generateGapCandidates, confirmPdfDoi, fetchLiveUiBundle, getCandidateScreening, getLocalApiStatus, getPdfSourceMapContext, getPdfStatus, getPdfTasks, getRunStatus, importRunPackage, localApiEnabled, privateMarkdownUrl, recordCandidateScreening, recordPdfEvidenceCard, recordPdfMaterialFacts, recordPdfSourceMap, requestQuestionCandidates, type CandidateScreening, type CandidateScreeningCandidate, type AutomaticExecutionStatus, type HarnessAuthorization, type CandidateScreeningDecision, type EvidenceReviewResult, type HumanEvidenceReviewInput, type HumanMaterialFactInput, type PdfTaskRegistry, type PdfTaskStatus, type PrivateSourceMapSegment, type RetrievalSource, type SourceMapRecordResult } from "./localApi";
import { demoBundle, readBundle, type EvidenceCard, type ImportedBundle, type LiteratureGraphNode } from "./model";
import { setUiLanguage, uiLanguage } from "./zh";
import { shouldPollPdfTask } from "./pdfTaskPolling";
import { pdfTaskSnapshotFreshness, type PdfTaskReadHealth } from "./pdfTaskFreshness";
import { pdfTaskForSession } from "./sessionPdfSelection";
import { queuedResumeCanCommit } from "./resumeRequestGate";
import { candidateFulltextGate } from "./candidateFulltextGate";
import { completedPrivateSourceMapMatchesPaper, screeningAllowsSourceReview } from "./currentPaperReviewRoute";
import { getFacilityContractCatalogue, getOperationalTelemetry, getReminderBoard, getStageContract, getWorkflowDag, isFacilityContractCatalogue, isLocalApiStatus, isReminderBoard, type FacilityCatalogueHealth, type FacilityContractManifest, type OperationalTelemetry, type ReminderBoard, type StageContract, type WorkflowDag } from "./localApi";
import { currentStage, runtimeProjectionAttention, runtimeProjectionReadable, type RuntimeProjectionHealth } from "./runtimeProjection";
import { runtimeProjectionSnapshotFreshness } from "./runtimeProjectionFreshness";
import { workflowDagRail } from "./workflowDagProjection";
import { trustedRuntimeProjections } from "./runtimeProjectionContract";
import { missionSessionHandoff } from "./missionSessionHandoff";
import { bfoTemplateLink, bfoTemplateLinkMatchesMission, type BfoTemplateLink } from "./bfoTemplateLink";
import { safeImportFeedback, safeMutationFeedback, safeOperationFeedback } from "./importFeedback";
import { createLatestRequestGate } from "./latestRequestGate";
import { createExclusiveSubmissionGate } from "./exclusiveSubmissionGate";
import { createOperationActivity, type OperationActivity } from "./operationActivity";
import { dispatchRecoveryItems } from "./dispatchRecovery";
import { stageRecoveryNavigation } from "./stageRecoveryNavigation";
import { ordinaryStatus, recoverableStatus } from "./statusRecovery";
type Theme = "light" | "dark" | "eye";
type View = "launch" | "discover" | "workflow" | "graph" | "reader" | "horizon";
type RouteRecovery = { view: View; zh: string; en: string; contextZh?: string; contextEn?: string };
type RootPdfMission = LaunchMission & { missionId: string };
type RootPdfRetry = { file: File; mission: RootPdfMission };
type LocalImportReceipt = { fileName: string; byteLength: number; importedAt: number; generatedAt: string | null; schemaVersion: string; visibleRecordCount: number; withheldAcceptedEvidenceCount: number };
const text = (zhText: string, enText: string) => uiLanguage() === "zh" ? zhText : enText;
const SOURCES: Array<{ id: RetrievalSource; label: string; provider: string }> = [
  { id: "sciverse", label: "Sciverse", provider: "sciverse" },
  { id: "openalex", label: "OpenAlex", provider: "openalex" },
  { id: "crossref", label: "Crossref", provider: "crossref" },
];
// Keep the launch surface small.  These workspaces load only after an explicit
// route transition; graph rendering performs a further lazy import for Cytoscape.
const FleetCommand = lazy(() => import("./FleetCommand").then((module) => ({ default: module.FleetCommand })));
const GraphNetwork = lazy(() => import("./GraphNetwork").then((module) => ({ default: module.GraphNetwork })));
const PaperReader = lazy(() => import("./PaperReader").then((module) => ({ default: module.PaperReader })));
const ResearchExpansion = lazy(() => import("./ResearchExpansion").then((module) => ({ default: module.ResearchExpansion })));

function localImportReceipt(file: File, imported: ImportedBundle): LocalImportReceipt {
  return {
    fileName: file.name.slice(0, 160) || "ui.json",
    byteLength: Math.max(0, file.size),
    importedAt: Date.now(),
    generatedAt: imported.generatedAt,
    schemaVersion: imported.schemaVersion.slice(0, 80),
    visibleRecordCount: imported.stations.length + imported.facilities.length + imported.evidenceCards.length + imported.conditionMatrix.length + imported.researchGapCandidates.length + imported.literatureGraph.nodes.length,
    withheldAcceptedEvidenceCount: imported.importDiagnostics.withheldAcceptedEvidenceCount,
  };
}
function localImportSize(byteLength: number): string {
  if (byteLength < 1024) return `${byteLength} B`;
  return `${(byteLength / 1024).toFixed(1)} kB`;
}
function localImportTimestamp(value: string | null, locale: "zh" | "en"): string {
  if (!value) return locale === "zh" ? "工件未提供" : "Not supplied by artifact";
  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-GB", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

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
function journeyOutputLabel(stage: JourneyStage): string {
  return ({
    define: text("任务简报与可比较边界", "Mission brief and comparable boundary"),
    orchestrate: text("受控计划与任务站点", "Controlled plan and task stations"),
    map: text("可审查文献子图", "Reviewable literature subgraph"),
    verify: text("来源定位与已接受 EvidenceCard", "Source locations and accepted EvidenceCards"),
    extend: text("待人工复核的 Gap 候选", "Human-review Gap candidates"),
  } as const)[stage.id];
}
function sessionHandoffLabel(state: string): string {
  return ({
    awaiting_paper: text("等待选择文献", "Awaiting paper selection"),
    paper_selected: text("已选论文，尚未授权全文", "Paper selected; full text not authorised"),
    fulltext_authorized: text("全文核对已获人工授权", "Human-authorised for full-text review"),
    private_fulltext_ready: text("私有全文已就绪，待来源定位", "Private full text ready; source locations pending"),
    source_map_recorded: text("来源定位已登记，待证据审核", "Source locations recorded; evidence review pending"),
    evidence_audited: text("当前 EvidenceCard 已通过门禁", "Current EvidenceCard passed its gate"),
  } as Record<string, string>)[state] ?? state;
}
function sessionHandoffDetail(state: string): string {
  return ({
    awaiting_paper: text("先在文献星图显式选择一篇可审查论文；不会从图节点推断来源文档。", "Select a reviewable paper explicitly in the literature map; source documents are never inferred from graph nodes."),
    paper_selected: text("候选元数据仍仅用于导航。须有持久化的人工纳入决定，才能请求对应私有 PDF。", "Candidate metadata remains navigation-only. A persisted human inclusion decision is required before requesting its private PDF."),
    fulltext_authorized: text("该决定只允许处理对应的本机 PDF；不构成来源定位、材料事实或 EvidenceCard。", "This decision permits only the matching local PDF; it is not a Source Map, material fact, or EvidenceCard."),
    private_fulltext_ready: text("Markdown 仅在本机可用。请人工登记段落、表格或图注的来源定位。", "Markdown is available only locally. Register paragraph, table, or figure-caption locations by human review."),
    source_map_recorded: text("已登记来源定位仍需逐项审核材料事实与 EvidenceCard，不能自动升级为研究结论。", "Recorded source locations still require item-by-item material-fact and EvidenceCard review; they do not auto-upgrade into conclusions."),
    evidence_audited: text("当前选择已通过精确来源映射门禁；研究拓展仍只生成待人工复核的候选。", "The current selection passed the exact Source Map gate; research extension still produces human-review candidates only."),
  } as Record<string, string>)[state] ?? "";
}
function sessionHandoffAction(state: string): string {
  return ({
    awaiting_paper: text("打开文献星图", "Open literature map"),
    paper_selected: text("返回星图处理候选", "Return to map"),
    fulltext_authorized: text("返回星图选择授权 PDF", "Select authorised PDF in map"),
    private_fulltext_ready: text("进入证据核对", "Enter evidence verification"),
    source_map_recorded: text("继续证据审核", "Continue evidence review"),
    evidence_audited: text("进入研究拓展", "Enter research extension"),
  } as Record<string, string>)[state] ?? text("查看当前门禁", "Inspect current gate");
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
function runtimeStageLabel(stage: string): string {
  return ({ intake: text("任务定义", "Intake"), plan: text("计划审核", "Plan"), retrieval: text("受控检索", "Retrieval"), screening: text("候选筛选", "Screening"), parse: text("解析任务", "Parse"), extraction: text("来源与证据", "Extraction"), gap: text("Gap 候选", "Gap"), report: text("报告", "Report"), evaluation: text("人工评测", "Evaluation") } as Record<string, string>)[stage] ?? stage;
}
function runtimeStageStatusLabel(status: string): string {
  return ({ completed: text("已完成", "Complete"), ready: text("可进入", "Ready"), waiting_human_review: text("等待人工复核", "Waiting for review"), blocked: text("前置条件未满足", "Blocked") } as Record<string, string>)[status] ?? status;
}
function runtimeAttentionLabel(attention: string): string {
  return ({ runtime_safety_attention: text("运行关系审计需要注意；请查看本地审计工件。", "Runtime relationship audit needs attention; inspect the local audit artifact."), human_review_required: text("当前阶段等待人工复核；面板不会代替或执行该复核。", "The current stage awaits human review; this panel does not replace or perform it."), stage_blocked: text("当前阶段的前置工件或人工门尚未满足。", "The current stage is missing a prerequisite artifact or human gate."), external_dispatch_incomplete: text("存在未完成的外部调用记录；不会自动重试。", "An external dispatch remains incomplete; it will not be retried automatically."), external_dispatch_unknown: text("存在结果未知的外部调用；须先做受控状态核验。", "An external dispatch has an unknown outcome; perform a controlled status check first."), cost_latency_disclosure_invalid: text("人工成本/时延披露无效，未显示任何数值。", "The human cost/latency disclosure is invalid; no numbers are displayed.") } as Record<string, string>)[attention] ?? attention;
}
function dispatchOperationLabel(operation: string): string {
  return ({
    deepseek_plan_draft: text("DeepSeek 计划草案", "DeepSeek plan draft"),
    deepseek_graph_plan_draft: text("DeepSeek 图谱草案", "DeepSeek graph plan draft"),
    metadata_query: text("书目元数据查询", "Bibliographic metadata query"),
    citation_expansion: text("公开引文扩展", "Public citation expansion"),
    mineru_submit: text("MinerU PDF 提交", "MinerU PDF submission"),
    mineru_poll: text("MinerU 状态轮询", "MinerU status polling"),
  } as Record<string, string>)[operation] ?? operation;
}
function reminderActionLabel(action: string): string {
  return ({
    inspect_runtime_invariants: text("核对本机运行不变量", "Inspect local runtime invariants"),
    review_stage_boundary: text("核对阶段边界", "Review the stage boundary"),
    complete_human_review: text("完成所需人工复核", "Complete the required human review"),
    verify_dispatch_before_recovery: text("先核对中断调用，再决定恢复", "Inspect the interrupted dispatch before recovery"),
    verify_provider_outcome_before_recovery: text("先核验服务商结果，再决定恢复", "Verify provider outcome before recovery"),
    review_operational_todo: text("复核本机运维待办", "Review the local operational todo"),
  } as Record<string, string>)[action] ?? action;
}
function stageRecoveryLabel(target: "task-control" | "graph" | "reader" | "horizon"): string {
  return ({
    "task-control": text("打开受控任务审核", "Open controlled task review"),
    graph: text("打开文献星图审核", "Open literature-map review"),
    reader: text("打开来源定位审核", "Open source-map review"),
    horizon: text("打开研究拓展审核", "Open research-extension review"),
  } as const)[target];
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
  const [launchNotice, setLaunchNotice] = createSignal<string | null>(null);
  const [activeOperation, setActiveOperation] = createSignal<OperationActivity | null>(null);
  const [status, setStatusRaw] = createSignal(text("当前显示本地演示工件；尚未发起网络请求。", "Showing local demonstration artifacts; no network request has been made."));
  const [routeRecovery, setRouteRecovery] = createSignal<RouteRecovery | null>(null);
  function setStatus(message: string) {
    const next = ordinaryStatus<RouteRecovery>(message);
    setStatusRaw(next.message);
    setRouteRecovery(next.recovery);
  }
  function setStatusWithRecovery(message: string, recovery: RouteRecovery) {
    const next = recoverableStatus(message, recovery);
    setStatusRaw(next.message);
    setRouteRecovery(next.recovery);
  }
  const [automaticMissionPending, setAutomaticMissionPending] = createSignal(false);
  const [automaticGraphHandoffPending, setAutomaticGraphHandoffPending] = createSignal(false);
  const [automaticExecution, setAutomaticExecution] = createSignal<AutomaticExecutionStatus | null>(null);
  const [automaticCancellationRequested, setAutomaticCancellationRequested] = createSignal(false);
  const [automaticAuthorization, setAutomaticAuthorization] = createSignal<HarnessAuthorization | null>(null);
  const [apiSummary, setApiSummary] = createSignal(text("本地 API 未启用。", "Local API is disabled."));
  const [apiProviders, setApiProviders] = createSignal<Record<string, boolean>>({});
  const [apiCapabilityHealth, setApiCapabilityHealth] = createSignal<LocalApiCapabilityHealth>("disabled");
  const [retrievalSources, setRetrievalSources] = createSignal<RetrievalSource[]>(["crossref"]);
  const [liveRunId, setLiveRunId] = createSignal<string | null>(null);
  const [stageContract, setStageContract] = createSignal<StageContract | null>(null);
  const [workflowDag, setWorkflowDag] = createSignal<WorkflowDag | null>(null);
  const [operationalTelemetry, setOperationalTelemetry] = createSignal<OperationalTelemetry | null>(null);
  const [runtimeProjectionHealth, setRuntimeProjectionHealth] = createSignal<RuntimeProjectionHealth>("disabled");
  const [runtimeProjectionObservedAt, setRuntimeProjectionObservedAt] = createSignal<number | null>(null);
  const [runtimeProjectionRefreshBusy, setRuntimeProjectionRefreshBusy] = createSignal(false);
  const [runtimeFreshnessNow, setRuntimeFreshnessNow] = createSignal(Date.now());
  const [facilityContracts, setFacilityContracts] = createSignal<FacilityContractManifest[] | null>(null);
  const [facilityCatalogueHealth, setFacilityCatalogueHealth] = createSignal<FacilityCatalogueHealth>("disabled");
  const [reminderBoard, setReminderBoard] = createSignal<ReminderBoard | null>(null);
  const [candidateScreening, setCandidateScreening] = createSignal<CandidateScreening | null>(null);
  const [candidatePdfTarget, setCandidatePdfTarget] = createSignal<LaunchPdfCandidateTarget | null>(null);
  const [pdfSubmissionPending, setPdfSubmissionPending] = createSignal(false);
  const [rootPdfRetry, setRootPdfRetry] = createSignal<RootPdfRetry | null>(null);
  const [resumeSubmissionPending, setResumeSubmissionPending] = createSignal(false);
  const [uiImportPending, setUiImportPending] = createSignal(false);
  const [uiImportReceipt, setUiImportReceipt] = createSignal<LocalImportReceipt | null>(null);
  const [pdfTask, setPdfTask] = createSignal<PdfTaskStatus | null>(null);
  const [pdfTasks, setPdfTasks] = createSignal<PdfTaskStatus[]>([]);
  const [pdfTaskObservedAt, setPdfTaskObservedAt] = createSignal<Record<string, number>>({});
  const [pdfTaskReadHealth, setPdfTaskReadHealth] = createSignal<PdfTaskReadHealth>("disabled");
  const [pdfFreshnessNow, setPdfFreshnessNow] = createSignal(Date.now());
  const [draftContent, setDraftContent] = createSignal("");
  const [planDraftConsent, setPlanDraftConsent] = createSignal(false);
  const [queryExecutionConsent, setQueryExecutionConsent] = createSignal(false);
  const [reviewedPlan, setReviewedPlan] = createSignal("");
  const [planApproved, setPlanApproved] = createSignal(false);
  const [manualControlOpen, setManualControlOpen] = createSignal(false);
  const [railContextOpen, setRailContextOpen] = createSignal(true);
  const [approvedQueryCount, setApprovedQueryCount] = createSignal(0);
  const [approvedCounterQueryCount, setApprovedCounterQueryCount] = createSignal(0);
  const [researchSession, setResearchSession] = createSignal<ResearchSession>(emptyResearchSession());
  const [artifactBoundaryFingerprint, setArtifactBoundaryFingerprint] = createSignal(taskBoundaryFingerprint(demoBundle.mission));
  const [taskArtifactLocked, setTaskArtifactLocked] = createSignal(false);
  const [bfoFormationLink, setBfoFormationLink] = createSignal<BfoTemplateLink | null>(null);
  let routeFocusInitialized = false;
  let rejectNextGraphReaderNavigation = false;
  let facilityCatalogueRequestEpoch = 0;
  let localApiStatusRequestEpoch = 0;
  // On compact screens the rail starts collapsed; never hide an active local
  // operation behind that preference.
  createEffect(() => { if (activeOperation()) setRailContextOpen(true); });
  const selectedDocumentId = createMemo(() => documentIdForReviewablePaper(researchSession().selectedNode));
  const localApiUsable = createMemo(() => localApiEnabled() && apiCapabilityHealth() === "ready");
  const previewCanActOnRun = createMemo(() => previewAllowsRunAction(launchPreview(), liveRunId()));
  const previewPdfTask = createMemo(() => previewCanActOnRun() ? pdfTask() : null);
  const previewPdfTasks = createMemo(() => previewCanActOnRun() ? pdfTasks() : []);
  const selectedPdfTaskFreshness = createMemo(() => pdfTaskSnapshotFreshness(pdfTask(), pdfTaskReadHealth(), pdfTask() ? pdfTaskObservedAt()[pdfTask()!.document_id] ?? null : null, pdfFreshnessNow()));
  const activeBfoTemplateId = createMemo(() => bfoTemplateLinkMatchesMission(bfoFormationLink(), bundle().mission.missionId) ? bfoFormationLink()!.templateId : null);
  // A completed private PDF only unlocks this rail when it belongs to the selected candidate.
  // A screening decision may invite private full-text review, but is still not scientific evidence.
  const privateSourceMapIntakeAvailable = createMemo(() => completedPrivateSourceMapMatchesPaper(pdfTask(), selectedDocumentId()));
  const selectedPaperScreenedForFulltext = createMemo(() => screeningAllowsSourceReview(candidateScreening(), liveRunId(), selectedDocumentId()));
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
  const sessionHandoff = createMemo(() => missionSessionHandoff({
    documentId: selectedDocumentId(),
    evidenceId: researchSession().evidenceId,
    screeningAllowsSourceReview: selectedPaperScreenedForFulltext(),
    privateFulltextReady: completedPrivateSourceMapMatchesPaper(pdfTask(), selectedDocumentId()),
    sourceMapRecorded: Boolean(selectedDocumentId() && bundle().sourceMapSummary.documentIds.includes(selectedDocumentId()!)),
    evidenceReady: gate().ready,
  }));
  const journeyRelay = createMemo(() => {
    const stages = journey();
    const currentIndex = Math.max(0, stages.findIndex((stage) => stage.view === view()));
    const current = stages[currentIndex] ?? null;
    const next = stages.slice(currentIndex + 1).find((stage) => stage.state !== "complete") ?? null;
    return { current, next };
  });
  const artifactStatuses = createMemo(() => deriveMissionArtifactStatus(bundle(), taskArtifactLocked()));
  const runtimeStage = createMemo(() => currentStage(stageContract()));
  const runtimeProjectionReady = createMemo(() => runtimeProjectionReadable(runtimeProjectionHealth()));
  const runtimeSnapshotFreshness = createMemo(() => runtimeProjectionSnapshotFreshness(runtimeProjectionHealth(), runtimeProjectionObservedAt(), runtimeFreshnessNow()));
  const runtimeStageRecovery = createMemo(() => stageRecoveryNavigation(runtimeStage()));
  const runtimeDagRail = createMemo(() => workflowDagRail(workflowDag()));
  const runtimeAttention = createMemo(() => runtimeProjectionAttention(stageContract(), operationalTelemetry()));
  const dispatchRecovery = createMemo(() => dispatchRecoveryItems(operationalTelemetry()));
  const telemetryRequestCount = createMemo(() => operationalTelemetry()?.provider_operations.reduce((total, item) => total + item.request_count, 0) ?? 0);

  // Route changes replace the primary workspace. Lazy routes briefly render a
  // loading fallback, so wait for the destination workspace rather than
  // focusing a heading that will immediately be removed.
  createEffect(() => {
    view();
    if (!routeFocusInitialized) { routeFocusInitialized = true; return; }
    const workbench = document.querySelector<HTMLElement>(".workbench");
    if (!workbench) return;
    let completed = false;
    const focusDestinationHeading = () => {
      if (completed) return;
      const heading = workbench.querySelector<HTMLElement>("main:not(.route-loading) h1, .frontier-literature-workbench h1");
      if (!heading) return;
      completed = true;
      observer.disconnect();
      heading.tabIndex = -1;
      heading.classList.add("route-focus-heading");
      heading.focus({ preventScroll: true });
    };
    const observer = new MutationObserver(focusDestinationHeading);
    observer.observe(workbench, { childList: true, subtree: true });
    const frame = window.requestAnimationFrame(focusDestinationHeading);
    onCleanup(() => { observer.disconnect(); window.cancelAnimationFrame(frame); });
  });

  const gateCopy = () => ({
    paper: text("请先在文献星图选择一篇待核对论文。", "Select a paper in the literature map first."),
    evidence: text("请从导入工件中选择一张已接受 EvidenceCard。", "Select an accepted EvidenceCard from the imported artifact."),
    "source-link": text("所选 EvidenceCard 没有与当前论文对应的已审核来源映射。", "The selected EvidenceCard has no reviewed source-map link to the current paper."),
    locator: text("当前 EvidenceCard 缺少来源文档 ID 或定位符。", "The selected EvidenceCard lacks a source document ID or locator."),
    "source-map": text("所选 EvidenceCard 对应文献没有可审计的来源映射片段。", "The paper for the selected EvidenceCard has no auditable source-map segment."),
    "provenance-audit": text("当前已接受 EvidenceCard 尚未全部通过精确来源映射审计。", "Accepted EvidenceCards have not all passed the exact source-map provenance audit."),
  } as const);
  const hasHumanReviewedEvaluation = () => Object.values(bundle().auditSummary.evaluation).some(Boolean);

  function navigate(next: View) {
    if (next === "reader" && rejectNextGraphReaderNavigation) {
      rejectNextGraphReaderNavigation = false;
      return;
    }
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
    if (next === "horizon" && !gate().ready && !hasHumanReviewedEvaluation()) {
      setStatus(gateCopy()[gate().reason ?? "evidence"]);
      setRouteRecovery({
        view: gate().reason === "paper" ? "graph" : "reader",
        zh: gate().reason === "paper" ? "返回文献星图选择论文" : "返回证据核对补齐来源与 EvidenceCard",
        en: gate().reason === "paper" ? "Return to literature map and select a paper" : "Return to evidence verification and complete source/EvidenceCard review",
      });
      return;
    }
    const stage = journey().find((item) => item.view === next);
    if (stage?.state === "blocked" && !(next === "horizon" && hasHumanReviewedEvaluation())) {
      setStatus(language() === "zh" ? stage.reasonZh ?? "上一步尚未完成。" : stage.reasonEn ?? "The preceding stage is not ready.");
      const recovery = ({ workflow: { view: "discover", zh: "返回任务定义补齐边界", en: "Return to task definition and complete boundaries" }, graph: { view: "workflow", zh: "返回舰桥建立任务工件", en: "Return to bridge and create mission artifacts" }, reader: { view: "graph", zh: "返回文献星图选择论文", en: "Return to literature map and select a paper" }, horizon: { view: "reader", zh: "返回证据核对补齐审计链路", en: "Return to evidence verification and complete the audit chain" } } as Partial<Record<View, RouteRecovery>>)[next];
      setRouteRecovery(recovery ?? null);
      return;
    }
    setRouteRecovery(null);
    setView(next);
  }
  function openLaunchPreview(stage: LaunchPreviewStage) {
    // Effects stop scheduling remote refreshes in preview mode, but a request
    // that was already in flight must not update this read-only workspace.
    automaticRefreshGate.invalidate();
    runtimeProjectionRefreshGate.invalidate();
    pdfTaskRefreshGate.invalidate();
    pdfTasksRefreshGate.invalidate();
    facilityCatalogueRequestEpoch += 1;
    reminderBoardRequestEpoch += 1;
    setLaunchPreview(true);
    setResearchSession(emptyResearchSession());
    setView(stage);
    setStatus(text("当前为起始页只读预览：未创建任务、未上传文件、未调用模型或检索 API。", "This is a launch-page read-only preview: no task, upload, model, or retrieval API was started."));
  }

  function returnToLaunch() {
    setLaunchPreview(false);
    setView("launch");
    setStatus(liveRunId()
      ? text("已返回起始页；当前本机任务仍被保留，可随时返回查看。新任务或边界修改才会替换它。", "Returned to launch. The current local task is retained and can be reopened at any time; only a new task or boundary change replaces it.")
      : text("已返回起始页；选择入口并完成确认后才会执行任务。", "Returned to launch. A task runs only after an entry is selected and confirmed."));
  }

  function returnToActiveRunWorkspace() {
    if (!liveRunId()) return;
    setLaunchPreview(false);
    setRouteRecovery(null);
    setView("workflow");
    setStatus(text("已返回当前本机任务；仅查看已登记状态，不会自动重试或重新发起检索。", "Returned to the current local task. Only recorded status is shown; no retry or retrieval is started automatically."));
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
    if (changed) {
      supersedeActiveRun();
      setLiveRunId(null);
      // Candidate-linked intake targets and browser-held root-PDF retries are
      // scoped to the old mission.  Retaining either after a boundary change
      // could surface a misleading launch action or reuse the wrong mission
      // identity, even though the server would later reject most mismatches.
      clearRunScopedClientArtifacts();
      setBfoFormationLink(null);
    }
    setTaskArtifactLocked(changed);
    const boundaryStatus = changed
      ? text("任务边界已更新。旧图谱、证据和 Gap 已锁定供回看；请重新导入匹配工件或执行受控检索。", "Mission boundary updated. Old graph, evidence, and Gaps are retained but locked for review; re-import matching artifacts or run controlled retrieval.")
      : text("任务边界已确认；尚未调用模型、检索服务或第三方 API。", "Mission boundary confirmed; no model, retrieval service, or third-party API was called.");
    if (changed) setStatusWithRecovery(boundaryStatus, { view: "discover", zh: "返回任务定义，重新建立匹配工件", en: "Return to task definition and rebuild matching artifacts" });
    else setStatus(boundaryStatus);
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
  let automaticOperationId: number | null = null;
  let reminderBoardRequestEpoch = 0;
  const automaticRefreshGate = createLatestRequestGate();
  const runtimeProjectionRefreshGate = createLatestRequestGate();
  const pdfTaskRefreshGate = createLatestRequestGate();
  const pdfTasksRefreshGate = createLatestRequestGate();
  const pdfSubmissionGate = createExclusiveSubmissionGate();
  const resumeSubmissionGate = createExclusiveSubmissionGate();
  const uiImportSubmissionGate = createExclusiveSubmissionGate();
  const candidateScreeningSubmissionGate = createExclusiveSubmissionGate();
  const doiConfirmationGate = createExclusiveSubmissionGate();
  const sourceMapRecordingGate = createExclusiveSubmissionGate();
  const materialFactRecordingGate = createExclusiveSubmissionGate();
  const evidenceCardRecordingGate = createExclusiveSubmissionGate();
  const conditionMatrixGate = createExclusiveSubmissionGate();
  const gapCandidateGate = createExclusiveSubmissionGate();
  const liveMissionLaunchGate = createExclusiveSubmissionGate();
  const planDraftGate = createExclusiveSubmissionGate();
  const planApprovalGate = createExclusiveSubmissionGate();
  const queryExecutionGate = createExclusiveSubmissionGate();
  const citationExpansionGate = createExclusiveSubmissionGate();
  const automaticCancellationGate = createExclusiveSubmissionGate();
  const operationActivity = createOperationActivity();
  function beginActiveOperation(label: string, detail: string) {
    const next = operationActivity.start(label, detail);
    setActiveOperation(next);
    return next.id;
  }
  function finishActiveOperation(id: number) {
    setActiveOperation(operationActivity.finish(id));
  }
  function startAutomaticOperation() {
    automaticOperationId = beginActiveOperation(text("正在执行受控自动元数据检索", "Running controlled automatic metadata retrieval"), text("仅向已选书目服务发送任务边界；候选元数据仍不是已接受证据。", "Only the task boundary is sent to selected bibliographic services; candidate metadata is not accepted evidence."));
  }
  function finishAutomaticOperation() {
    if (automaticOperationId === null) return;
    finishActiveOperation(automaticOperationId);
    automaticOperationId = null;
  }
  function supersedeActiveRun() {
    taskEpoch += 1;
    automaticRefreshGate.invalidate();
    runtimeProjectionRefreshGate.invalidate();
    pdfTaskRefreshGate.invalidate();
    pdfTasksRefreshGate.invalidate();
    finishAutomaticOperation();
    setAutomaticMissionPending(false);
    setAutomaticGraphHandoffPending(false);
    setAutomaticExecution(null);
    setAutomaticCancellationRequested(false);
    setAutomaticAuthorization(null);
    setPlanDraftConsent(false);
    setQueryExecutionConsent(false);
    setStageContract(null);
    setWorkflowDag(null);
    setOperationalTelemetry(null);
    setRuntimeProjectionHealth("disabled");
    setRuntimeProjectionObservedAt(null);
    const priorRunId = liveRunId();
    if (priorRunId && localApiEnabled()) void cancelRun(priorRunId).catch(() => undefined);
    return taskEpoch;
  }
  async function refreshRuntimeProjections(runId: string, stillCurrent: () => boolean = () => liveRunId() === runId): Promise<StageContract | null> {
    // Polling and an explicit artifact refresh can overlap for one run.  Only
    // the newest complete trio may update the rail; an older response must not
    // overwrite the newer contract/DAG/telemetry with a stale snapshot.
    const isLatestRefresh = runtimeProjectionRefreshGate.begin();
    const current = () => isLatestRefresh() && stillCurrent() && liveRunId() === runId;
    if (["disabled", "unavailable"].includes(untrack(runtimeProjectionHealth))) setRuntimeProjectionHealth("loading");
    try {
      const [contract, dag, telemetry] = await Promise.all([getStageContract(runId), getWorkflowDag(runId), getOperationalTelemetry(runId)]);
      if (!current()) return null;
      if (!runtimeProjectionsMatchRun(runId, contract, dag, telemetry) || !trustedRuntimeProjections(runId, contract, dag, telemetry)) throw new Error("runtime projection contract mismatch");
      setStageContract(contract);
      setWorkflowDag(dag);
      setOperationalTelemetry(telemetry);
      setRuntimeProjectionObservedAt(Date.now());
      setRuntimeProjectionHealth("ready");
      return contract;
    } catch (error) {
      // A newer projection is already responsible for the rail.  Do not let
      // a superseded request erase its state through a caller's error path.
      if (!current()) return null;
      setRuntimeProjectionObservedAt(null);
      setRuntimeProjectionHealth("unavailable");
      throw error;
    }
  }
  async function refreshRuntimeProjectionsManually() {
    const runId = liveRunId();
    if (!runId || runtimeProjectionRefreshBusy()) return;
    setRuntimeProjectionRefreshBusy(true);
    try {
      await refreshRuntimeProjections(runId);
    } catch (error) {
      if (liveRunId() === runId) setStatus(safeOperationFeedback(error, text("无法立即刷新本机运行投影；已保留最后确认的快照。", "Unable to refresh the local runtime projection now; the last confirmed snapshot is retained.")));
    } finally {
      setRuntimeProjectionRefreshBusy(false);
    }
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
  function openArtifactNext(card: MissionArtifactStatus) {
    if (card.next === "complete-brief") {
      questionTextarea?.focus();
      setStatus(text("请补齐当前任务边界后再进入受控编排；此操作没有启动任务或外部调用。", "Complete the current task boundary before controlled orchestration; this action starts no task or external call."));
      return;
    }
    if (card.next === "import-conditions" || card.next === "reimport") {
      openManualTaskControl();
      return;
    }
    if (card.next === "orchestrate") {
      navigate("workflow");
      return;
    }
    if (card.next === "verify-source") {
      navigate(hasNavigableLiteratureGraph(bundle()) ? "graph" : "workflow");
      return;
    }
    navigate("workflow");
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
    // A browser-held PDF may only be retried while its original empty mission
    // shell is still current. Any explicit run switch drops that in-memory
    // file reference rather than allowing it to cross task boundaries.
    setRootPdfRetry(null);
    setPdfTask(null);
    setPdfTasks([]);
    setPdfTaskObservedAt({});
    setPdfTaskReadHealth("disabled");
    setResearchSession(emptyResearchSession());
    setDraftContent("");
    setReviewedPlan("");
    setPlanApproved(false);
    setApprovedQueryCount(0);
    setApprovedCounterQueryCount(0);
    setUiImportReceipt(null);
  }
  function openManualTaskControl() {
    if (launchPreview()) { setStatus(text("只读预览不允许打开手动执行控制。", "The read-only preview cannot open manual execution controls.")); return; }
    setManualControlOpen(true);
    setView("discover");
    setStatus(text("已打开高级手动受控执行。请先核对任务边界、计划、数据源与明确授权，再决定是否执行。", "Advanced manual control is open. Verify the task boundary, plan, sources, and explicit consent before deciding whether to execute."));
  }
  function openRuntimeStageRecovery() {
    const recovery = runtimeStageRecovery();
    if (!recovery) return;
    if (recovery.target === "task-control") { openManualTaskControl(); return; }
    navigate(recovery.target);
    setStatus(text("已打开当前阶段对应的本地审核界面；此导航不会提交任务、上传文件或调用外部服务。", "Opened the local review surface for the current stage. This navigation does not submit work, upload files, or call external services."));
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
    const [rawBundle, status] = await Promise.all([fetchLiveUiBundle(runId), getRunStatus(runId)]);
    const imported = readBundle(rawBundle, "loopback");
    if (!stillCurrent()) throw new Error("stale task result");
    if (!liveBundleMatchesRun(runId, status, imported)) throw new Error("live run bundle identity mismatch");
    applyImportedBundle(imported, preserveResearchSession);
    if (localApiEnabled()) {
      try {
        const screening = await getCandidateScreening(runId);
        if (!stillCurrent()) throw new Error("stale task result");
        if (screening.run_id !== runId) throw new Error("candidate screening identity mismatch");
        setCandidateScreening(screening);
      } catch (error) {
        if (!stillCurrent()) throw error;
        setCandidateScreening(null);
      }
      try {
        await refreshRuntimeProjections(runId, stillCurrent);
      } catch (error) {
        if (!stillCurrent()) throw error;
        setStageContract(null);
        setWorkflowDag(null);
        setOperationalTelemetry(null);
        setRuntimeProjectionObservedAt(null);
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
    if (screening.run_id !== runId) throw new Error("candidate screening identity mismatch");
    setCandidateScreening(screening);
  }

  async function submitCandidateScreening(decisions: CandidateScreeningDecision[]) {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可提交的本地任务。", "There is no local task available for submission."));
    if (!candidateScreeningSubmissionGate.tryStart()) {
      setStatus(text("正在登记候选筛选；请等待当前提交结束。", "Candidate screening is already being recorded; wait for the current submission to finish."));
      throw new Error("candidate screening submission already in progress");
    }
    const operationId = beginActiveOperation(text("正在登记候选筛选", "Recording candidate screening"), text("仅写入人工逐篇决定；“纳入”只开放后续受控全文流程。", "Only human paper-by-paper decisions are being recorded; inclusion only opens the later controlled full-text workflow."));
    const epoch = taskEpoch;
    try {
      const result = await recordCandidateScreening(runId, decisions);
      requireCurrentRun(runId, epoch);
      if (result.run_id !== runId) throw new Error("candidate screening result identity mismatch");
      const refreshedScreening = await getCandidateScreening(runId);
      requireCurrentRun(runId, epoch);
      if (refreshedScreening.run_id !== runId) throw new Error("candidate screening identity mismatch");
      setCandidateScreening(refreshedScreening);
      await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
      requireCurrentRun(runId, epoch);
      setStatus(text(`已提交 ${result.candidate_count} 篇候选论文的人工筛选；“纳入”仅开放后续受控全文流程。`, `Human screening was submitted for ${result.candidate_count} candidate paper(s); inclusion only opens a later controlled full-text workflow.`));
    } finally {
      candidateScreeningSubmissionGate.finish();
      finishActiveOperation(operationId);
    }
  }

  function prepareCandidatePdf(candidate: CandidateScreeningCandidate) {
    const runId = liveRunId();
    if (!runId) { setStatus(text("当前没有可关联候选的本地任务。", "There is no local task to link this candidate to.")); return; }
    const gate = candidateFulltextGate(candidateScreening(), runId, bundle().literatureGraph.nodes, candidate);
    if (!gate.ready) {
      const reason = ({ run: text("筛选记录不属于当前任务", "the screening record does not belong to the current task"), screening: text("人工筛选尚未完整提交并重新载入", "the human screening record is not persisted"), candidate: text("候选不属于当前筛选清单", "the candidate is not in the current screening checklist"), decision: text("该候选未被纳入全文核对", "the candidate is not included for full-text review"), paper: text("当前文献星图没有对应的可审查论文", "the current literature map has no matching reviewable paper") } as const)[gate.reason!];
      setStatus(text(`不能进入 PDF 入港：${reason}。请返回文献星图完成或刷新人工筛选。`, `PDF intake is blocked because ${reason}. Return to the literature map to complete or refresh human screening.`));
      return;
    }
    const paper = reviewablePaperForDocumentId(bundle().literatureGraph.nodes, candidate.document_id)!;
    setResearchSession(selectPaper(emptyResearchSession(), paper));
    setPdfTask(pdfTaskForSession(pdfTasks(), candidate.document_id));
    setCandidatePdfTarget({ runId, documentId: candidate.document_id, title: candidate.title });
    setView("launch");
    setStatus(text(`已选择“${candidate.title}”。请仅选择你有权处理的对应 PDF；提交时会再次核验该候选的人工纳入记录。`, `Selected “${candidate.title}”. Choose only the corresponding PDF you are authorized to process; the human inclusion record will be checked again on submission.`));
  }
  function upsertPdfTask(task: PdfTaskStatus, select = true) {
    setPdfTasks((current) => [...current.filter((item) => item.document_id !== task.document_id), task]);
    setPdfTaskObservedAt((current) => ({ ...current, [task.document_id]: Date.now() }));
    setPdfTaskReadHealth("ready");
    if (select) setPdfTask(task);
  }
  async function refreshPdfTask(runId = liveRunId(), documentId = pdfTask()?.document_id, stillCurrent: () => boolean = () => true, announce = true) {
    if (!runId || !documentId) throw new Error(text("当前没有已选择的 PDF 解析任务。", "There is no selected PDF parsing task."));
    const epoch = taskEpoch;
    const isLatestRefresh = pdfTaskRefreshGate.begin();
    const guard = () => isLatestRefresh() && stillCurrent() && currentRunGuard(runId, epoch)();
    if (untrack(pdfTaskReadHealth) !== "ready") setPdfTaskReadHealth("loading");
    let task: PdfTaskStatus;
    try {
      task = await getPdfStatus(runId, documentId);
    } catch (error) {
      if (guard()) setPdfTaskReadHealth("unavailable");
      throw error;
    }
    if (!guard()) throw new Error("stale task result");
    const remainsSelected = pdfTask()?.document_id === documentId;
    upsertPdfTask(task, remainsSelected);
    if (!remainsSelected) return;
    if (task.state === "failed") setStatus(safeOperationFeedback(task.error, text("PDF 解析失败；未生成 Markdown、来源定位或 EvidenceCard。请更换已授权 PDF 后重试。", "PDF parsing failed. No Markdown, source location, or EvidenceCard was created. Choose another authorized PDF and retry.")));
    else if (task.error) setStatus(text("本机 PDF 状态报告暂时异常；当前任务记录已保留。请刷新状态，不需要重新上传同一文件。", "The local PDF status report is temporarily abnormal. The task record is retained; refresh its status without re-uploading the same file."));
    else if (announce) setStatus(text(`PDF 解析状态：${task.state}；DOI：${task.doi_status}。`, `PDF parsing status: ${task.state}; DOI: ${task.doi_status}.`));
  }
  async function refreshPdfTasks(runId = liveRunId(), stillCurrent: () => boolean = () => true) {
    if (!runId) return [];
    const epoch = taskEpoch;
    const isLatestRefresh = pdfTasksRefreshGate.begin();
    if (untrack(pdfTaskReadHealth) !== "ready") setPdfTaskReadHealth("loading");
    let registry: PdfTaskRegistry;
    try {
      registry = await getPdfTasks(runId);
    } catch (error) {
      if (isLatestRefresh() && stillCurrent() && currentRunGuard(runId, epoch)()) setPdfTaskReadHealth("unavailable");
      throw error;
    }
    if (!isLatestRefresh() || !stillCurrent() || !currentRunGuard(runId, epoch)()) return [];
    if (registry.run_id !== runId) {
      setPdfTaskReadHealth("unavailable");
      throw new Error("PDF task registry identity mismatch");
    }
    setPdfTasks(registry.tasks);
    const observedAt = Date.now();
    setPdfTaskObservedAt(Object.fromEntries(registry.tasks.map((task) => [task.document_id, observedAt])));
    setPdfTaskReadHealth("ready");
    setPdfTask((selected) => registry.tasks.find((item) => item.document_id === selected?.document_id) ?? registry.tasks[0] ?? null);
    return registry.tasks;
  }

  createEffect(() => {
    const runId = liveRunId();
    const tasks = pdfTasks();
    if (launchPreview() || !localApiEnabled() || !runId || !tasks.some((task) => shouldPollPdfTask(runId, task))) return;
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try { await refreshPdfTasks(runId, () => liveRunId() === runId); } catch { /* Next poll may recover a transient local API failure. */ } finally { refreshing = false; }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    onCleanup(() => window.clearInterval(timer));
  });

  async function confirmManualPdfDoi(doi: string) {
    const runId = liveRunId();
    const selectedTask = pdfTask();
    if (!runId || !selectedTask) throw new Error(text("当前没有可确认 DOI 的 PDF 任务。", "There is no PDF task available for DOI confirmation."));
    const documentId = selectedTask.document_id;
    if (!doiConfirmationGate.tryStart()) {
      setStatus(text("正在确认 DOI；请等待当前请求结束。", "A DOI confirmation is already in progress; wait for the current request to finish."));
      throw new Error("DOI confirmation already in progress");
    }
    const operationId = beginActiveOperation(text("正在确认 DOI", "Confirming DOI"), text("仅为当前私有 PDF 登记人工确认的书目标识；不会创建材料证据。", "Only a human-confirmed bibliographic identifier is being recorded for the current private PDF; no material evidence is created."));
    const epoch = taskEpoch;
    try {
      const task = await confirmPdfDoi(runId, documentId, doi);
      requireCurrentRun(runId, epoch);
      const remainsSelected = pdfTask()?.document_id === documentId;
      upsertPdfTask(task, remainsSelected);
      setStatus(remainsSelected
        ? text(`已人工确认 DOI：${task.doi}。它仅用于书目引文导航，不构成材料证据。`, `Human-confirmed DOI: ${task.doi}. It is used only for bibliographic navigation, not materials evidence.`)
        : text(`已为先前选择的 PDF 登记 DOI：${task.doi}；当前 PDF 选择保持不变。`, `Recorded DOI ${task.doi} for the previously selected PDF; the current PDF selection was preserved.`));
    } finally {
      doiConfirmationGate.finish();
      finishActiveOperation(operationId);
    }
  }

  async function loadPrivateSourceMap(): Promise<SourceMapRecordResult> {
    const runId = liveRunId();
    const selectedTask = pdfTask();
    if (!runId || !selectedTask) throw new Error(text("当前没有可恢复来源定位的 PDF 任务。", "There is no PDF task available for Source Map recovery."));
    const documentId = selectedTask.document_id;
    const epoch = taskEpoch;
    const result = await getPdfSourceMapContext(runId, documentId);
    requireCurrentRun(runId, epoch);
    return result;
  }
  async function recordPrivateSourceMap(segments: PrivateSourceMapSegment[]): Promise<SourceMapRecordResult> {
    const runId = liveRunId();
    const selectedTask = pdfTask();
    if (!runId || !selectedTask) throw new Error(text("当前没有可登记来源定位的 PDF 任务。", "There is no PDF task available for Source Map recording."));
    const documentId = selectedTask.document_id;
    if (!sourceMapRecordingGate.tryStart()) {
      setStatus(text("正在登记来源定位；请等待当前提交结束。", "Source locations are already being recorded; wait for the current submission to finish."));
      throw new Error("source map recording already in progress");
    }
    const operationId = beginActiveOperation(text("正在登记来源定位", "Recording source locations"), text("仅将人工核对的短引文和定位符写入本地工件；不会接受 EvidenceCard。", "Only human-checked short excerpts and locators are being written to the local artifact; no EvidenceCard is accepted."));
    const epoch = taskEpoch;
    try {
      const result = await recordPdfSourceMap(runId, documentId, segments);
      requireCurrentRun(runId, epoch);
      await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
      // Refresh the PDF that actually received the Source Map.  A user may
      // have selected another task while the local write was in flight.
      await refreshPdfTask(runId, documentId, currentRunGuard(runId, epoch));
      requireCurrentRun(runId, epoch);
      setStatus(text(`已登记 ${result.segment_count} 条人工来源定位。它们仍不是 EvidenceCard；下一步是人工登记受控材料事实。`, `${result.segment_count} human-reviewed source locations were recorded. They are not EvidenceCards; human-reviewed material fact registration remains next.`));
      return result;
    } finally {
      sourceMapRecordingGate.finish();
      finishActiveOperation(operationId);
    }
  }
  async function recordPrivateMaterialFacts(facts: HumanMaterialFactInput[]) {
    const runId = liveRunId();
    const selectedTask = pdfTask();
    if (!runId || !selectedTask) throw new Error(text("当前没有可登记材料事实的 PDF 任务。", "There is no PDF task available for material-fact registration."));
    const documentId = selectedTask.document_id;
    if (!materialFactRecordingGate.tryStart()) {
      setStatus(text("正在登记材料事实；请等待当前提交结束。", "Material facts are already being recorded; wait for the current submission to finish."));
      throw new Error("material fact recording already in progress");
    }
    const operationId = beginActiveOperation(text("正在登记材料事实", "Recording material facts"), text("仅登记人工复核且绑定来源片段的事实；不会自动形成 EvidenceCard 或结论。", "Only human-reviewed facts bound to source segments are being recorded; no EvidenceCard or conclusion is created automatically."));
    const epoch = taskEpoch;
    try {
      const result = await recordPdfMaterialFacts(runId, documentId, facts);
      requireCurrentRun(runId, epoch);
      await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
      requireCurrentRun(runId, epoch);
      setStatus(text(`已登记 ${result.fact_count} 条人工复核的材料事实。它们不是 EvidenceCard，也不构成科学结论。`, `${result.fact_count} human-reviewed material facts were recorded. They are not EvidenceCards or scientific conclusions.`));
    } finally {
      materialFactRecordingGate.finish();
      finishActiveOperation(operationId);
    }
  }
  async function recordPrivateEvidenceCard(input: HumanEvidenceReviewInput): Promise<EvidenceReviewResult> {
    const runId = liveRunId();
    const selectedTask = pdfTask();
    if (!runId || !selectedTask) throw new Error(text("当前没有可接受 EvidenceCard 的 PDF 任务。", "There is no PDF task available for EvidenceCard acceptance."));
    const documentId = selectedTask.document_id;
    if (!evidenceCardRecordingGate.tryStart()) {
      setStatus(text("正在接受 EvidenceCard；请等待当前提交结束。", "An EvidenceCard is already being accepted; wait for the current submission to finish."));
      throw new Error("EvidenceCard acceptance already in progress");
    }
    const operationId = beginActiveOperation(text("正在接受 EvidenceCard", "Accepting EvidenceCard"), text("仅在人工核对主张、条件和来源片段后写入本地证据卡。", "A local EvidenceCard is written only after human review of its claim, conditions, and source segment."));
    const epoch = taskEpoch;
    try {
      const result = await recordPdfEvidenceCard(runId, documentId, input);
      requireCurrentRun(runId, epoch);
      const imported = await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch), true);
      requireCurrentRun(runId, epoch);
      const evidence = imported.evidenceCards.find((item) => item.evidenceId === result.evidence_id);
      const paper = reviewablePaperForDocumentId(imported.literatureGraph.nodes, result.document_id);
      const remainsSelected = pdfTask()?.document_id === documentId;
      if (remainsSelected && evidence && paper) setResearchSession(selectEvidence(selectPaper(emptyResearchSession(), paper), evidence));
      setStatus(remainsSelected
        ? text(`已人工接受 ${result.evidence_id}。该卡仅绑定当前文献与定位符；请在文献星图核对关联后，再进入研究拓展。`, `${result.evidence_id} was accepted by human review. It is bound only to this paper and locator; inspect its graph link before entering research extension.`)
        : text(`已为先前选择的 PDF 接受 ${result.evidence_id}；当前 PDF 与论文选择保持不变。`, `Accepted ${result.evidence_id} for the previously selected PDF; the current PDF and paper selection were preserved.`));
      return result;
    } finally {
      evidenceCardRecordingGate.finish();
      finishActiveOperation(operationId);
    }
  }
  async function buildConditionMatrix() {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可诊断的本地任务。", "There is no local task available for diagnostics."));
    if (!conditionMatrixGate.tryStart()) {
      setStatus(text("正在生成条件比较矩阵；请等待当前操作结束。", "A condition-comparison matrix is already being generated; wait for the current operation to finish."));
      throw new Error("condition matrix generation already in progress");
    }
    const operationId = beginActiveOperation(text("正在生成条件比较矩阵", "Generating condition-comparison matrix"), text("仅从已接受证据与登记条件生成确定性比较边界；不会推断科学结论。", "A deterministic comparison boundary is being generated only from accepted evidence and recorded conditions; no scientific conclusion is inferred."));
    const epoch = taskEpoch;
    try {
      const result = await diagnoseConditions(runId);
      requireCurrentRun(runId, epoch);
      await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
      requireCurrentRun(runId, epoch);
      setStatus(text(`已生成 ${result.matrix_row_count} 个确定性条件比较行；它们不是科学结论。`, `${result.matrix_row_count} deterministic condition-comparison row(s) were generated; they are not scientific conclusions.`));
    } finally {
      conditionMatrixGate.finish();
      finishActiveOperation(operationId);
    }
  }
  async function buildGapCandidates() {
    const runId = liveRunId();
    if (!runId) throw new Error(text("当前没有可生成候选的本地任务。", "There is no local task available for candidate generation."));
    if (!gapCandidateGate.tryStart()) {
      setStatus(text("正在生成 Gap 候选；请等待当前操作结束。", "Gap candidates are already being generated; wait for the current operation to finish."));
      throw new Error("Gap candidate generation already in progress");
    }
    const operationId = beginActiveOperation(text("正在生成 Gap 候选", "Generating Gap candidates"), text("输出仍是证据约束、待人工复核的候选；不会自动成为研究结论或新任务。", "The output remains evidence-bound and pending human review; it does not automatically become a research conclusion or a new mission."));
    const epoch = taskEpoch;
    try {
      const result = await generateGapCandidates(runId);
      requireCurrentRun(runId, epoch);
      await hydrateLiveRunBundle(runId, currentRunGuard(runId, epoch));
      requireCurrentRun(runId, epoch);
      setStatus(text(`已生成 ${result.candidate_count} 个证据约束候选，均需人工复核。`, `${result.candidate_count} evidence-bound candidate(s) were generated; all require human review.`));
    } finally {
      gapCandidateGate.finish();
      finishActiveOperation(operationId);
    }
  }
  async function expandPdfCitationGraph() {
    const runId = liveRunId();
    const task = pdfTask();
    if (!runId || !task?.markdown_ready || !["resolved", "human_confirmed"].includes(task.doi_status)) return;
    if (!window.confirm(text("我同意将该 DOI 发送至书目服务，仅扩展公开引文关系；不会上传私有 PDF/Markdown，也不会创建材料事实、Source Map 或 EvidenceCard。", "I authorize sending this DOI to bibliographic services only to expand public citation relations. No private PDF/Markdown is uploaded and no material fact, Source Map, or EvidenceCard is created."))) return;
    if (!citationExpansionGate.tryStart()) { setStatus(text("正在构建该 PDF 的引文图；请等待当前请求结束。", "A citation map is already being built for this PDF; wait for the current request to finish.")); return; }
    const operationId = beginActiveOperation(text("正在构建书目引文图", "Building bibliography citation map"), text("仅扩展 DOI 的公开书目关系；不创建材料事实、Source Map 或 EvidenceCard。", "Only public bibliographic relations for the DOI are being expanded; no material fact, Source Map, or EvidenceCard is created."));
    const epoch = taskEpoch;
    try {
      const result = await expandAuthorizedPdfCitations(runId, task.document_id, `browser-citation-expansion-${crypto.randomUUID()}`);
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
    } catch (error) {
      if (currentRunGuard(runId, epoch)()) showMutationRecovery("citation", error,
        text("无法构建引文图；已登记的私有 PDF 与工件保持不变。", "Unable to build the citation map; the registered private PDF and artifacts are unchanged."),
        text("构建引文图请求超时，结果未知；不会自动重试。请先在本机运行状态和服务商侧核验后，再创建新的明确授权调用。", "The citation-map request timed out and its outcome is unknown. It will not retry automatically; verify local run status and the provider before creating a new explicitly authorised call."));
    } finally { citationExpansionGate.finish(); finishActiveOperation(operationId); }
  }  async function refreshAutomaticMission(runId: string, stillCurrent: () => boolean = () => true) {
    const epoch = taskEpoch;
    const isLatestRefresh = automaticRefreshGate.begin();
    const guard = () => isLatestRefresh() && stillCurrent() && currentRunGuard(runId, epoch)();
    const summary = await getRunStatus(runId);
    if (!guard()) return;
    const automatic = summary.automatic_execution;
    // A durable cancellation marker is stronger than a stale queued/running
    // worker snapshot.  Stop polling immediately: the local worker will see
    // the marker before any later provider submission.
    if (summary.cancellation === "requested") {
      setAutomaticCancellationRequested(true);
      setAutomaticMissionPending(false);
      setAutomaticGraphHandoffPending(false);
      finishAutomaticOperation();
      setAutomaticExecution(automatic ?? null);
      setStatus(text("自动任务的取消请求已由本机登记；正在进行的 HTTP 请求无法被强制中断，但不会再提交后续提供方调用或写入迟到结果。", "The automatic task cancellation was recorded locally. An HTTP request already in flight cannot be force-stopped, but no later provider call or late result will be written."));
      return;
    }
    setAutomaticCancellationRequested(false);
    if (!automatic) {
      setAutomaticMissionPending(false);
      setAutomaticGraphHandoffPending(false);
      finishAutomaticOperation();
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
    finishAutomaticOperation();
    if (automatic.state === "cancelled") {
      setAutomaticCancellationRequested(true);
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
      if (guard() && screening.run_id === runId) setCandidateScreening(screening);
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

  async function cancelAutomaticMission() {
    const runId = liveRunId();
    const automatic = automaticExecution();
    if (!automaticCancellationEnabled(launchPreview(), runId, automatic?.state, automaticCancellationRequested())) {
      setStatus(text("当前自动任务不可取消：它可能尚未登记运行号、已结束，或处于只读预览。", "The current automatic task cannot be cancelled: it may not have a registered run ID, may already be terminal, or is in read-only preview."));
      return;
    }
    if (!window.confirm(text("确认取消当前自动元数据检索？本机会写入持久取消标记；已经在途的 HTTP 请求不能被强制终止，但不会再提交后续提供方调用或写入迟到结果。", "Cancel the current automatic metadata retrieval? The local service will write a durable cancellation marker. An HTTP request already in flight cannot be force-stopped, but no later provider call or late result will be written."))) return;
    if (!automaticCancellationGate.tryStart()) {
      setStatus(text("正在登记自动任务取消；请等待本机确认。", "Automatic-task cancellation is already being recorded; wait for the local confirmation."));
      return;
    }
    const operationId = beginActiveOperation(text("正在取消自动元数据检索", "Cancelling automatic metadata retrieval"), text("本机正在写入持久取消标记；它会阻止任何后续提供方提交。", "The local service is writing a durable cancellation marker that blocks every later provider submission."));
    const epoch = taskEpoch;
    const restoreGraphHandoff = automaticGraphHandoffPending();
    automaticRefreshGate.invalidate();
    setAutomaticCancellationRequested(true);
    setAutomaticMissionPending(false);
    setAutomaticGraphHandoffPending(false);
    try {
      const result = await cancelRun(runId!);
      if (!currentRunGuard(runId!, epoch)()) return;
      setAutomaticExecution(result.automatic_execution ?? automatic ?? null);
      finishAutomaticOperation();
      setStatus(text("自动任务取消请求已由本机登记。若已有 HTTP 请求在途，它完成后也会被取消标记拦截，不能写入候选、来源定位或 EvidenceCard。", "The automatic-task cancellation request is recorded locally. If an HTTP request is already in flight, the cancellation marker intercepts it on completion; it cannot write candidates, source locations, or EvidenceCards."));
    } catch (error) {
      if (currentRunGuard(runId!, epoch)()) {
        setAutomaticCancellationRequested(false);
        setAutomaticMissionPending(automatic?.state === "queued" || automatic?.state === "running");
        setAutomaticGraphHandoffPending(restoreGraphHandoff);
        showMutationRecovery("cancellation", error,
          text("无法登记自动任务取消；当前任务保持原状态并恢复只读轮询。", "Unable to record automatic-task cancellation. The task remains unchanged and read-only polling resumes."),
          text("取消请求超时，结果未知；不会假定任务仍在运行或已经取消。请先查看本机运行状态，期间不会自动重试取消。", "The cancellation request timed out and its outcome is unknown. The UI will not assume the task is still running or cancelled; inspect local run status, and cancellation will not retry automatically."));
      }
    } finally {
      automaticCancellationGate.finish();
      finishActiveOperation(operationId);
    }
  }

  createEffect(() => {
    const pending = automaticGraphHandoffPending();
    const automaticState = automaticExecution()?.state;
    const currentView = view() === "launch" ? "discover" : view() as Exclude<View, "launch">;
    const navigable = hasNavigableLiteratureGraph(bundle());
    if (automaticGraphHandoffAlreadySettled(pending, automaticState, currentView, navigable)) {
      setAutomaticGraphHandoffPending(false);
      return;
    }
    const target = automaticGraphHandoffTarget(
      pending,
      automaticState,
      currentView,
      navigable,
    );
    if (target) {
      setAutomaticGraphHandoffPending(false);
      setView(target);
    }
  });

  createEffect(() => {
    const runId = liveRunId();
    const automatic = automaticExecution();
    if (launchPreview() || !localApiEnabled() || !runId || !automatic || !["queued", "running"].includes(automatic.state)) return;
    let refreshing = false;
    const poll = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        await refreshAutomaticMission(runId, () => liveRunId() === runId);
      } catch (error) {
        if (liveRunId() === runId) setStatus(safeOperationFeedback(error, text("无法刷新自动任务状态；当前任务壳保持不变。", "Unable to refresh automatic task status; the current task shell is unchanged.")));
      } finally {
        refreshing = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 2500);
    onCleanup(() => window.clearInterval(timer));
  });
  createEffect(() => {
    if (launchPreview() || !localApiEnabled() || !liveRunId() || !pdfTask()) return;
    setPdfFreshnessNow(Date.now());
    const timer = window.setInterval(() => setPdfFreshnessNow(Date.now()), 5_000);
    onCleanup(() => window.clearInterval(timer));
  });
  function showMutationRecovery(kind: OperationRecoveryKind, error: unknown, fallback: string, unknownOutcome: string) {
    setStatusWithRecovery(safeMutationFeedback(error, fallback, unknownOutcome), operationRecovery(kind));
  }
  createEffect(() => {
    if (launchPreview() || !localApiEnabled()) { reminderBoardRequestEpoch += 1; setReminderBoard(null); return; }
    let disposed = false;
    const refresh = () => {
      const requestEpoch = ++reminderBoardRequestEpoch;
      void getReminderBoard().then((board) => { if (!disposed && requestEpoch === reminderBoardRequestEpoch) setReminderBoard(isReminderBoard(board) ? board : null); }).catch(() => { if (!disposed && requestEpoch === reminderBoardRequestEpoch) setReminderBoard(null); });
    };
    refresh();
    const timer = window.setInterval(refresh, 30_000);
    onCleanup(() => { disposed = true; reminderBoardRequestEpoch += 1; window.clearInterval(timer); });
  });
  async function refreshFacilityContracts() {
    const requestEpoch = ++facilityCatalogueRequestEpoch;
    if (!localApiEnabled()) {
      setFacilityContracts(null);
      setFacilityCatalogueHealth("disabled");
      return;
    }
    setFacilityCatalogueHealth("loading");
    let timeout: number | undefined;
    try {
      const catalogue = await Promise.race([
        getFacilityContractCatalogue(),
        new Promise<never>((_, reject) => { timeout = window.setTimeout(() => reject(new Error("facility catalogue request timed out")), 5_000); }),
      ]);
      if (requestEpoch !== facilityCatalogueRequestEpoch) return;
      if (!isFacilityContractCatalogue(catalogue)) throw new Error("invalid static facility catalogue");
      setFacilityContracts(catalogue.contracts);
      setFacilityCatalogueHealth("ready");
    } catch {
      if (requestEpoch !== facilityCatalogueRequestEpoch) return;
      setFacilityContracts(null);
      setFacilityCatalogueHealth("unavailable");
    } finally {
      if (timeout !== undefined) window.clearTimeout(timeout);
    }
  }
  createEffect(() => {
    if (launchPreview()) { facilityCatalogueRequestEpoch += 1; return; }
    void refreshFacilityContracts();
  });
  createEffect(() => {
    const runId = liveRunId();
    if (launchPreview()) { setStageContract(null); setWorkflowDag(null); setOperationalTelemetry(null); setRuntimeProjectionObservedAt(null); setRuntimeProjectionHealth("disabled"); return; }
    if (!localApiEnabled() || !runId) { setStageContract(null); setWorkflowDag(null); setOperationalTelemetry(null); setRuntimeProjectionObservedAt(null); setRuntimeProjectionHealth("disabled"); return; }
    if (untrack(runtimeProjectionHealth) === "disabled") setRuntimeProjectionHealth("loading");
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        await refreshRuntimeProjections(runId);
      } catch {
        if (liveRunId() === runId) { setStageContract(null); setWorkflowDag(null); setOperationalTelemetry(null); setRuntimeProjectionObservedAt(null); setRuntimeProjectionHealth("unavailable"); }
      } finally {
        refreshing = false;
      }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 10_000);
    onCleanup(() => window.clearInterval(timer));
  });
  createEffect(() => {
    if (launchPreview() || !localApiEnabled() || !liveRunId()) return;
    setRuntimeFreshnessNow(Date.now());
    const timer = window.setInterval(() => setRuntimeFreshnessNow(Date.now()), 5_000);
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
    const automaticAvailable = localApiUsable() && retrievalSources().length > 0;
    const missionEpoch = supersedeActiveRun();
    clearRunScopedClientArtifacts();
    setLiveRunId(null);
    applyImportedBundle(emptyBundleForMission(nextMission));
    setBfoFormationLink(bfoTemplateLink(nextMission.missionId, mission.templateId));
    setStatus(automaticAvailable
      ? text("任务已确认；正在登记一次已授权的自动元数据检索。完成前仅显示空任务壳，候选元数据仍不是证据。", "Mission confirmed; registering the one-time authorised metadata retrieval. Until it finishes, only an empty task shell is shown and candidate metadata is not evidence.")
      : text("任务已确认；当前仅建立空任务壳。可连接的本机 API 与至少一个书目来源可用后，才可进行受控检索或导入工件。", "Mission confirmed; only an empty task shell exists. Controlled retrieval or artifact import is available only after a reachable local API and at least one bibliographic source are available."));
    if (automaticAvailable) {
      setAutomaticCancellationRequested(false);
      setAutomaticMissionPending(true);
      setAutomaticGraphHandoffPending(true);
      startAutomaticOperation();
      void createAutomaticMission({ question: nextMission.question, material: nextMission.material, property: nextMission.property, scope: nextMission.scope, sources: retrievalSources() }).then((result) => {
        if (!isCurrentTask(missionEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
        const authorization = result.harness_authorization;
        if (!authorization || authorization.trust_status !== "authorization_checked_before_automatic_dispatch") {
          void cancelRun(result.run_id).catch(() => undefined);
          setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false);
          finishAutomaticOperation();
          setStatus(text("本机服务未返回自动检索的 Harness 授权审计；已请求取消该运行，当前仅保留空任务壳。", "The local service returned no Harness authorization audit for automatic retrieval. Cancellation was requested and only the empty mission shell is retained."));
          return;
        }
        setLiveRunId(result.run_id);
        setAutomaticAuthorization(authorization);
        const automatic = result.status.automatic_execution ?? { state: "queued", candidate_count: 0, failure_count: 0, planning_warning: false, trust_status: result.trust_status };
        setAutomaticExecution(automatic);
        setAutomaticMissionPending(["queued", "running"].includes(automatic.state));
        void refreshAutomaticMission(result.run_id, () => isCurrentTask(missionEpoch)).catch((error) => {
          if (isCurrentTask(missionEpoch)) { setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false); finishAutomaticOperation(); setStatus(safeOperationFeedback(error, text("无法刷新自动本地任务；当前保留空任务壳。", "Unable to refresh the automatic local task; the empty task shell is retained."))); }
        });
      }).catch((error: unknown) => { if (isCurrentTask(missionEpoch)) { setAutomaticMissionPending(false); setAutomaticGraphHandoffPending(false); finishAutomaticOperation(); setAutomaticExecution(null); showMutationRecovery("automatic", error,
        text("无法启动自动本地任务；当前保留空任务壳。", "Unable to start the automatic local task; the empty task shell is retained."),
        text("自动任务登记请求超时，结果未知；不会自动重试。当前仅保留空任务壳，请先检查本机运行目录或状态，再创建新的明确授权任务。", "The automatic-task registration request timed out and its outcome is unknown. It will not retry automatically; only the empty task shell remains. Inspect local run status before creating a new explicitly authorised task.")); } });
    }
    scheduleCurrentView(missionEpoch, "workflow");
  }
  function submitRootPdf(file: File, mission: RootPdfMission, pdfEpoch: number) {
    if (!pdfSubmissionGate.tryStart()) {
      setLaunchNotice(text("正在提交一个 PDF 解析任务；请等待当前请求结束。", "A PDF parsing task is already being submitted; wait for the current request to finish."));
      return;
    }
    setPdfSubmissionPending(true);
    const operationId = beginActiveOperation(text("正在提交私有 PDF", "Submitting private PDF"), text("文件仅通过本机环回服务进入解析队列；完整 Markdown 仍留在私有缓存。", "The file is entering the parsing queue only through the local loopback service; full Markdown remains in private storage."));
    void createPdfRun(file, mission).then((result) => {
      if (!isCurrentTask(pdfEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
      setRootPdfRetry(null);
      setLiveRunId(result.run_id);
      upsertPdfTask({ document_id: result.document_id, candidate_document_id: result.candidate_document_id ?? null, audit_document_id: result.candidate_document_id ?? result.document_id, audit_state: "pending", file_name: file.name, state: result.state, doi: null, doi_status: result.doi_status, markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence" });
      setStatus(text(`私有 PDF 任务 ${result.run_id} 当前为 ${result.state}；Markdown 始终位于本机私有缓存，等待 DOI 与书目工件。`, `Private PDF task ${result.run_id} is ${result.state}; Markdown remains in local private cache while DOI and bibliographic artifacts are pending.`));
      void refreshPdfTask(result.run_id).catch(() => undefined);
    }).catch((error: unknown) => {
      if (!isCurrentTask(pdfEpoch)) return;
      // Keep the original File and mission ID only in this browser session.
      // A deliberate retry therefore reaches the API's idempotency boundary
      // rather than silently creating another private-PDF mission.
      setRootPdfRetry({ file, mission });
      setView("launch");
      setStatus(safeOperationFeedback(error, text("未确认私有 PDF 是否已入队；已保留同一文件与任务身份。请在起始页明确选择“使用原任务重试”，不要重新选择文件。", "The private PDF submission outcome was not confirmed. The same file and task identity are retained. Explicitly choose “Retry original task” on the launch page; do not choose the file again.")));
    }).finally(() => { pdfSubmissionGate.finish(); setPdfSubmissionPending(false); finishActiveOperation(operationId); });
  }

  function retryRootPdfSubmission() {
    const retry = rootPdfRetry();
    if (!retry || !localApiUsable()) return;
    submitRootPdf(retry.file, retry.mission, taskEpoch);
  }

  function beginPdfMission(file: File, candidateTarget?: LaunchPdfCandidateTarget) {
    if (!localApiUsable()) {
      setStatus(text("PDF 入港需要可连接的本机环回 API；当前能力快照不可用，未创建解析任务，也不会上传文件。", "PDF intake requires a reachable local loopback API. The current capability snapshot is unavailable; no parsing task was created and no file was uploaded."));
      return;
    }
    if (candidateTarget) {
      if (!liveRunId() || liveRunId() !== candidateTarget.runId) {
        setStatus(text("候选全文入口已失效；请回到文献星图重新选择已人工纳入的候选。", "The candidate full-text entry has expired; return to the literature map and reselect a human-included candidate."));
        return;
      }
      const candidate = candidateScreening()?.candidates.find((item) => item.document_id === candidateTarget.documentId);
      const gate = candidate ? candidateFulltextGate(candidateScreening(), candidateTarget.runId, bundle().literatureGraph.nodes, candidate) : { ready: false as const, reason: "candidate" as const };
      if (!gate.ready) {
        setCandidatePdfTarget(null);
        setStatus(text("候选全文入口已失效：当前运行的人工筛选或文献图已变化。未上传文件；请回到文献星图重新选择已纳入候选。", "The candidate full-text entry has expired because the current run's screening or graph changed. No file was uploaded; return to the literature map and reselect an included candidate."));
        return;
      }
      if (!pdfSubmissionGate.tryStart()) {
        setLaunchNotice(text("正在提交一个 PDF 解析任务；请等待当前请求结束。", "A PDF parsing task is already being submitted; wait for the current request to finish."));
        return;
      }
      setPdfSubmissionPending(true);
      const operationId = beginActiveOperation(text("正在提交候选 PDF", "Submitting candidate PDF"), text("仅将已授权文件交给本机环回服务；MinerU 解析尚未产生证据。", "Only the authorized file is being handed to the local loopback service; MinerU parsing has not produced evidence."));
      const pdfEpoch = taskEpoch;
      void createPdfRun(file, bundle().mission, { runId: candidateTarget.runId, documentId: candidateTarget.documentId }).then((result) => {
        if (!isCurrentTask(pdfEpoch) || liveRunId() !== candidateTarget.runId) { void cancelRun(result.run_id).catch(() => undefined); return; }
        setCandidatePdfTarget(null);
        upsertPdfTask({ document_id: result.document_id, candidate_document_id: result.candidate_document_id ?? candidateTarget.documentId, audit_document_id: result.candidate_document_id ?? candidateTarget.documentId, audit_state: "pending", file_name: file.name, state: result.state, doi: null, doi_status: result.doi_status, markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence" });
        setStatus(text(`已将授权 PDF 关联到已人工纳入的候选“${candidateTarget.title}”；MinerU 任务当前为 ${result.state}。Markdown 始终位于本机私有缓存。`, `The authorized PDF is linked to the human-included candidate “${candidateTarget.title}”; the MinerU task is ${result.state}. Markdown remains in local private cache.`));
        setView("workflow");
        void refreshPdfTask(result.run_id).catch(() => undefined);
      }).catch((error: unknown) => { if (isCurrentTask(pdfEpoch) && liveRunId() === candidateTarget.runId) showMutationRecovery("candidate_pdf", error,
        text("无法提交候选 PDF 入港任务；未上传或创建可用来源工件。", "Unable to submit the candidate PDF intake task; no usable source artifact was uploaded or created."),
        text("候选 PDF 入港请求超时，结果未知；请先刷新本机任务状态，不要重新上传同一文件。", "The candidate-PDF intake request timed out and its outcome is unknown. Refresh local task status first; do not re-upload the same file.")); }).finally(() => { pdfSubmissionGate.finish(); setPdfSubmissionPending(false); finishActiveOperation(operationId); });
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
    clearRunScopedClientArtifacts();
    setLiveRunId(null);
    setBfoFormationLink(null);
    applyImportedBundle(emptyBundleForMission(nextMission));
    setStatus(text("已建立私有 PDF 任务壳；在 MinerU 解析、DOI 识别和引文工件返回前，不显示任何演示论文或来源定位。", "A private PDF task shell was created. No demo paper or source locator is shown before MinerU parsing, DOI recognition, and citation artifacts return."));
    submitRootPdf(file, nextMission, pdfEpoch);
    scheduleCurrentView(pdfEpoch, "workflow");
  }

  function resumeLaunch(file: File) {
    setLaunchNotice(null);
    if (!file.name.endsWith(".cosmatter-run.json")) {
      const message = text("续航入口只接受 .cosmatter-run.json；旧 UI JSON 请在工作台的只读导入中打开。", "Continuation accepts only .cosmatter-run.json; open legacy UI JSON through the workbench read-only import.");
      setLaunchNotice(message); setStatus(message); return;
    }
    if (!resumeSubmissionGate.tryStart()) {
      setLaunchNotice(text("正在校验并恢复一个运行包；请等待当前请求结束。", "A run package is already being validated and restored; wait for the current request to finish."));
      return;
    }
    setResumeSubmissionPending(true);
    const operationId = beginActiveOperation(text("正在恢复运行包", "Restoring run package"), text("正在本机校验并载入受控工件；不会重新发起自动检索。", "The package is being validated and controlled artifacts loaded locally; automatic retrieval will not restart."));
    const queuedTaskEpoch = taskEpoch;
    let resumeEpoch: number | null = null;
    void file.text().then(async (raw) => {
      if (!queuedResumeCanCommit(queuedTaskEpoch, taskEpoch)) return;
      const payload = JSON.parse(raw) as { mission?: { question?: string; material?: string; property_name?: string; scope?: string }; package_type?: string };
      if (payload.package_type !== "cosmatter_run" || !payload.mission?.question || !payload.mission.material || !payload.mission.property_name || !payload.mission.scope) throw new Error(text("运行包缺少可恢复的任务简报。", "The run package has no recoverable mission brief."));
      if (!localApiUsable()) throw new Error(text("续航需要可连接的本机环回 API。", "Continuation requires a reachable local loopback API."));
      if (!queuedResumeCanCommit(queuedTaskEpoch, taskEpoch)) return;
      // Restoring is local, but still validate it before retiring the active
      // run.  A rejected or corrupt package must leave the current mission
      // alive rather than turning a failed import into an implicit stop.
      const result = await importRunPackage(payload);
      if (!queuedResumeCanCommit(queuedTaskEpoch, taskEpoch)) { void cancelRun(result.run_id).catch(() => undefined); return; }
      const activeResumeEpoch = supersedeActiveRun();
      resumeEpoch = activeResumeEpoch;
      clearRunScopedClientArtifacts();
      setBfoFormationLink(null);
      setLiveRunId(result.run_id);
      let artifactsHydrated = false;
      let localContractAvailable = false;
      let restoredStage: string | null = result.next_stage;
      let restoredStageDiffersFromPackage = false;
      try {
        await hydrateLiveRunBundle(result.run_id, () => isCurrentTask(activeResumeEpoch));
        if (!isCurrentTask(activeResumeEpoch)) return;
        try { await refreshPdfTasks(result.run_id, () => isCurrentTask(activeResumeEpoch)); } catch { if (isCurrentTask(activeResumeEpoch)) { setPdfTask(null); setPdfTasks([]); setPdfTaskObservedAt({}); setPdfTaskReadHealth("unavailable"); } }
        artifactsHydrated = true;
        const contract = stageContract();
        if (contract) {
          localContractAvailable = true;
          const reconciliation = reconcileRestoredStage(result.next_stage, contract.next_stage, true);
          restoredStage = reconciliation.stage;
          restoredStageDiffersFromPackage = reconciliation.differsFromPackage;
        } else {
          // The package snapshot is still safe to describe, but cannot grant a
          // downstream landing view until the newly restored local contract is
          // available again.
          const reconciliation = reconcileRestoredStage(result.next_stage, null, false);
          restoredStage = reconciliation.stage;
        }
        const resumeStage = continuationStageLabel(restoredStage, language());
        const packageStage = continuationStageLabel(result.next_stage, language());
        if (localContractAvailable && restoredStageDiffersFromPackage) {
          setStatus(text(`运行包快照记录为“${packageStage}”，但恢复后的本机工件只能重新核验到“${resumeStage}”。已按本机契约停在对应审核入口；不会自动检索或跳过人工门。`, `The package snapshot recorded “${packageStage}”, but restored local artifacts can currently verify only “${resumeStage}”. The app is using that local contract and will not retrieve automatically or bypass human gates.`));
        } else if (localContractAvailable) {
          setStatus(text(`运行包已恢复为 ${result.run_id}；本机契约确认当前为“${resumeStage}”。不会重新发起自动检索。`, `Run package restored as ${result.run_id}; the local contract confirms “${resumeStage}”. No automatic retrieval will restart.`));
        } else {
          setStatus(text(`运行包已恢复为 ${result.run_id}，其审计快照为“${packageStage}”；本机阶段契约暂不可读取，已停在舰桥等待核验。不会重新发起自动检索。`, `Run package restored as ${result.run_id} with audited snapshot “${packageStage}”; the local stage contract is currently unavailable, so the bridge remains open pending verification. No automatic retrieval will restart.`));
        }
      } catch (error) {
        if (!isCurrentTask(activeResumeEpoch)) return;
        const detail = safeOperationFeedback(error, text("无法载入运行工件", "Unable to load run artifacts"));
        const fallbackMission = { missionId: newLocalMissionId(), question: payload.mission.question, material: payload.mission.material, property: payload.mission.property_name, scope: payload.mission.scope };
        applyImportedBundle(emptyBundleForMission(fallbackMission));
        setStatus(text(`运行包已登记，但工件未能载入：${detail}。已保留空任务壳，且不会重新发起自动检索。`, `Run package was registered but artifacts could not be loaded: ${detail}. An empty task shell is retained and no automatic retrieval was restarted.`));
      }
      setView(viewForRestoredRun(restoredStage, artifactsHydrated && localContractAvailable));
    }).catch((error: unknown) => {
      if (!queuedResumeCanCommit(resumeEpoch ?? queuedTaskEpoch, taskEpoch)) return;
      const message = safeImportFeedback(
        error,
        text("无法校验运行包。请使用由 CosMatter 导出的未修改 .cosmatter-run.json。", "Unable to validate the run package. Use an unmodified .cosmatter-run.json exported by CosMatter."),
        text("运行包未通过完整性或安全校验，未恢复任何任务。请使用原始导出文件。", "The run package did not pass integrity or safety checks; no task was restored. Use the original exported file."),
      );
      setLaunchNotice(message); setStatus(message);
    }).finally(() => { resumeSubmissionGate.finish(); setResumeSubmissionPending(false); finishActiveOperation(operationId); });
  }

  function importBundle(file: File | undefined) {
    if (!file) return;
    if (!uiImportSubmissionGate.tryStart()) {
      setStatus(text("正在读取一个脱敏 UI JSON；请等待当前导入结束。", "A redacted UI JSON is already being read; wait for the current import to finish."));
      return;
    }
    setUiImportPending(true);
    const operationId = beginActiveOperation(text("正在导入脱敏 UI JSON", "Importing redacted UI JSON"), text("仅在浏览器解析本地工件；不上传文件或启动任何提供方。", "The local artifact is being parsed only in this browser; no file upload or provider call is started."));
    const queuedTaskEpoch = taskEpoch;
    void file.text().then((raw) => {
      // Read and validate before changing the current run.  A malformed UI
      // artifact must not cancel a valid local mission merely because the user
      // selected it in the import control.
      if (!isCurrentTask(queuedTaskEpoch)) return;
      const imported = readBundle(JSON.parse(raw));
      if (!isCurrentTask(queuedTaskEpoch)) return;
      const importEpoch = supersedeActiveRun();
      clearRunScopedClientArtifacts();
      setBfoFormationLink(null);
      setLiveRunId(null);
      if (!isCurrentTask(importEpoch)) return;
      applyImportedBundle(imported);
      setUiImportReceipt(localImportReceipt(file, imported));
      setStatus(text(`已导入 ${file.name}；仅在浏览器解析本地 JSON 工件。`, `Imported ${file.name}; the local JSON artifact was parsed only in this browser.`));
    }).catch((error: unknown) => {
      if (!isCurrentTask(queuedTaskEpoch)) return;
      setStatus(safeImportFeedback(
        error,
        text("该 UI JSON 未通过格式校验；请使用 export-ui 生成的脱敏工件。", "This UI JSON did not pass format validation. Use a redacted artifact generated by export-ui."),
        text("该 UI JSON 被安全拒绝；当前任务和已显示工件未被修改。", "This UI JSON was rejected safely; the current task and displayed artifacts were not changed."),
      ));
    }).finally(() => { uiImportSubmissionGate.finish(); setUiImportPending(false); finishActiveOperation(operationId); });
  }

  async function launchLiveMission() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    if (!localApiUsable()) { setStatus(text("本机 API 当前不可用；请等待能力快照恢复后再启动受控任务。", "The local API is currently unavailable. Wait for the capability snapshot to recover before starting a controlled task.")); return; }
    if (!updateMission()) return;
    if (!liveMissionLaunchGate.tryStart()) { setStatus(text("正在启动一个受控本地任务；请等待当前请求结束。", "A controlled local mission is already being started; wait for the current request to finish.")); return; }
    setStatus(text("正在启动受控本地任务；不会保留旧任务工件。", "Starting the controlled local mission; artifacts from the previous task will not be retained."));
    const operationId = beginActiveOperation(text("正在启动受控本地任务", "Starting controlled local mission"), text("正在创建新的本地任务壳；任何旧工件都不会被带入新边界。", "Creating a new local task shell; no previous artifact will be carried into the new boundary."));
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
        setStatus(text(`已创建受控本地任务 ${result.run_id}，但空工件未能载入。界面不会保留旧任务数据。`, `Controlled local mission ${result.run_id} was created, but its empty artifacts could not be loaded. The UI will not retain data from the prior task.`));
        return;
      }
      requireCurrentRun(result.run_id, launchEpoch);
      setStatus(text(`已启动受控本地任务 ${result.run_id}；当前仅显示该任务的空工件，下一步可起草并人工批准检索计划。`, `Controlled local mission ${result.run_id} started. Only this task’s empty artifacts are shown; draft and approve a retrieval plan next.`));
    } catch (error) { showMutationRecovery("task_start", error,
      text("无法启动本地 API 任务。", "Unable to start the local API mission."),
      text("启动本地任务请求超时，结果未知；不会自动重试。请先刷新本机任务状态，再决定是否创建新任务。", "The local-task start request timed out and its outcome is unknown. It will not retry automatically; refresh local run status before deciding whether to create a new task.")); }
    finally { liveMissionLaunchGate.finish(); finishActiveOperation(operationId); }
  }
  async function requestPlanDraft() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId) return;
    if (!planDraftConsent()) { setStatus(text("请先明确授权将当前任务边界发送至 DeepSeek 生成未受信计划草案。", "Explicitly authorize sending the current task boundary to DeepSeek for an untrusted plan draft first.")); return; }
    if (!planDraftGate.tryStart()) { setStatus(text("正在起草计划；请等待当前请求结束。", "A plan draft is already being requested; wait for the current request to finish.")); return; }
    setStatus(text("正在请求未受信计划草案；不会自动批准或执行检索。", "Requesting an untrusted plan draft; it will not be approved or executed automatically."));
    const operationId = beginActiveOperation(text("正在起草计划", "Drafting plan"), text("返回内容仍是未受信建议，必须人工复核后才能批准。", "Returned content remains an untrusted suggestion and requires human review before approval."));
    const epoch = taskEpoch;
    try {
      const result = await draftAuthorizedPlan(runId, `browser-plan-draft-${crypto.randomUUID()}`);
      requireCurrentRun(runId, epoch);
      setDraftContent(result.content);
      setStatus(text("已取得未受信草案；必须人工复核后才能批准。", "An untrusted draft is available; human review is required before approval."));
    } catch (error) {
      if (currentRunGuard(runId, epoch)()) showMutationRecovery("plan", error,
        text("无法请求计划草案；当前任务与已登记工件保持不变。", "Unable to request a plan draft; the current task and registered artifacts are unchanged."),
        text("计划草案请求超时，结果未知；不会自动重试。请先查看本机调度审计与运行状态。", "The plan-draft request timed out and its outcome is unknown. It will not retry automatically; inspect the local dispatch audit and run status first."));
    } finally { setPlanDraftConsent(false); planDraftGate.finish(); finishActiveOperation(operationId); }
  }
  async function approveReviewedPlan() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId) return;
    if (!planApprovalGate.tryStart()) { setStatus(text("正在批准复核计划；请等待当前请求结束。", "The reviewed plan is already being approved; wait for the current request to finish.")); return; }
    setStatus(text("正在校验并批准人工复核计划；未提交检索。", "Validating and approving the human-reviewed plan; no retrieval has been submitted."));
    const operationId = beginActiveOperation(text("正在批准复核计划", "Approving reviewed plan"), text("仅在本机验证人工计划与任务边界；检索必须另行明确执行。", "The human plan is being validated locally against the task boundary; retrieval still requires a separate explicit action."));
    const epoch = taskEpoch;
    try {
      const result = await approveLivePlan(runId, JSON.parse(reviewedPlan()));
      requireCurrentRun(runId, epoch);
      setPlanApproved(true); setApprovedQueryCount(result.queries.length); setApprovedCounterQueryCount(result.counter_queries.length);
      setStatus(text(`已批准 ${result.queries.length} 条主检索式与 ${result.counter_queries.length} 条反例检索式。`, `${result.queries.length} primary and ${result.counter_queries.length} counterevidence queries were approved.`));
    } catch (error) {
      if (currentRunGuard(runId, epoch)()) showMutationRecovery("plan", error,
        text("无法批准复核计划。请检查 JSON 结构、任务边界与人工审批要求。", "Unable to approve the reviewed plan. Check its JSON structure, mission boundary, and human-approval requirements."),
        text("计划批准请求超时，结果未知；请刷新本机任务状态核验，而非重新提交同一计划。", "The plan-approval request timed out and its outcome is unknown. Refresh local task status to verify it instead of resubmitting the same plan."));
    } finally { planApprovalGate.finish(); finishActiveOperation(operationId); }
  }
  async function executeApprovedQueries() {
    if (launchPreview()) { setStatus(text("只读预览不允许执行受控任务或外部调用。", "The read-only preview does not permit controlled tasks or external calls.")); return; }
    const runId = liveRunId();
    if (!runId || !planApproved() || !approvedQueryCount() || !retrievalSources().length) return;
    if (!queryExecutionConsent()) { setStatus(text("请先明确授权将已批准检索式发送至所选书目服务。", "Explicitly authorize sending approved queries to the selected bibliographic services first.")); return; }
    if (!queryExecutionGate.tryStart()) { setStatus(text("正在执行已批准检索；请等待当前请求结束。", "Approved retrieval is already running; wait for the current request to finish.")); return; }
    setStatus(text("正在按人工批准的顺序执行检索；不会重复提交。", "Running the human-approved retrieval sequence; duplicate submission is blocked."));
    const operationId = beginActiveOperation(text("正在执行已批准检索", "Running approved retrieval"), text("正在依次执行人工批准的主检索与反例检索；重复提交已被拦截。", "Primary and counterevidence queries are running in human-approved order; duplicate submission is blocked."));
    const executionEpoch = taskEpoch;
    const stillCurrent = () => isCurrentTask(executionEpoch) && liveRunId() === runId;
    try {
      let received = 0;
      for (let index = 0; index < approvedQueryCount(); index += 1) {
        if (!stillCurrent()) { void cancelRun(runId).catch(() => undefined); return; }
        received += (await executeAuthorizedApprovedQuery(runId, index, retrievalSources(), false, `browser-primary-query-${crypto.randomUUID()}`)).candidate_count;
      }
      for (let index = 0; index < approvedCounterQueryCount(); index += 1) {
        if (!stillCurrent()) { void cancelRun(runId).catch(() => undefined); return; }
        received += (await executeAuthorizedApprovedQuery(runId, index, retrievalSources(), true, `browser-counter-query-${crypto.randomUUID()}`)).candidate_count;
      }
      await hydrateLiveRunBundle(runId, stillCurrent);
      if (!stillCurrent()) return;
      setStatus(text(`已完成 ${approvedQueryCount()} 条主检索与 ${approvedCounterQueryCount()} 条反例检索，收到 ${received} 条候选元数据（去重前）。`, `Completed ${approvedQueryCount()} primary and ${approvedCounterQueryCount()} counterevidence queries with ${received} candidate metadata records before deduplication.`));
      navigate("graph");
    } catch (error) {
      if (!stillCurrent()) return;
      showMutationRecovery("query", error,
        text("无法执行已批准检索；当前已登记工件保持不变。", "Unable to execute the approved retrieval; registered artifacts are unchanged."),
        text("受控检索请求超时，结果未知；不会自动重试。请先核验本机调度审计和提供方状态，再创建新的明确授权调用。", "The controlled retrieval request timed out and its outcome is unknown. It will not retry automatically; verify the local dispatch audit and provider status before creating a new explicitly authorised call."));
    } finally { setQueryExecutionConsent(false); queryExecutionGate.finish(); finishActiveOperation(operationId); }
  }
  function toggleSource(source: RetrievalSource) { setRetrievalSources((current) => current.includes(source) ? current.filter((item) => item !== source) : [...current, source]); }

  function choosePaper(node: LiteratureGraphNode): boolean {
    if (launchPreview()) { setStatus(text("只读预览不会写入选中文献或证据会话。", "The read-only preview does not save a selected paper or evidence session.")); return false; }
    if (!documentIdForReviewablePaper(node)) { setStatus(text("该节点仅用于书目或结构导航，不能作为当前任务的待核对论文。", "This node is for bibliography or structure navigation only and cannot become the current paper for verification.")); return false; }
    setResearchSession((current) => selectPaper(current, node));
    const documentId = documentIdForReviewablePaper(node);
    const matchingPdf = pdfTaskForSession(pdfTasks(), documentId);
    setPdfTask(matchingPdf);
    rejectNextGraphReaderNavigation = false;
    setStatus(matchingPdf
      ? text(`已选择待核对论文：“${node.label}”，并切换到其关联的私有 PDF。尚未建立来源定位。`, `Selected paper for verification: “${node.label}” and switched to its attached private PDF. No source locator has been asserted.`)
      : text(`已选择待核对论文：“${node.label}”。不同论文的私有 PDF 已移出当前会话；尚未建立来源定位。`, `Selected paper for verification: “${node.label}”. Private PDFs for other papers were removed from this session; no source locator has been asserted.`));
    return true;
  }

  function chooseEvidence(evidence: EvidenceCard): boolean {
    if (launchPreview()) { setStatus(text("只读预览不会写入选中文献或证据会话。", "The read-only preview does not save a selected paper or evidence session.")); return false; }
    const focused = focusEvidenceSession(bundle(), evidence);
    if (!focused) {
      rejectNextGraphReaderNavigation = view() === "graph";
      setStatus(text("该 EvidenceCard 在当前图谱中没有显式的已审核论文—来源关联，不能作为本次核对的证据。", "This EvidenceCard has no explicit reviewed paper-to-source link in the current map and cannot be used for verification."));
      return false;
    }
    setResearchSession(focused);
    const matchingPdf = pdfTaskForSession(pdfTasks(), evidence.provenance.documentId);
    setPdfTask(matchingPdf);
    rejectNextGraphReaderNavigation = false;
    setStatus(matchingPdf
      ? text(`已定位 EvidenceCard ${evidence.evidenceId} 所属论文，并切换到其关联 PDF；状态仅来自导入工件。`, `Focused EvidenceCard ${evidence.evidenceId}'s paper and switched to its attached PDF; status comes only from imported artifacts.`)
      : text(`已定位 EvidenceCard ${evidence.evidenceId} 所属论文；不同论文的私有 PDF 已移出当前会话，状态仅来自导入工件。`, `Focused EvidenceCard ${evidence.evidenceId}'s paper. Private PDFs for other papers were removed from this session; status comes only from imported artifacts.`));
    return true;
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
    const matchingPdf = pdfTaskForSession(pdfTasks(), evidence.provenance.documentId);
    setPdfTask(matchingPdf);
    setStatus(matchingPdf
      ? text(`已定位 Gap 所引用的 EvidenceCard ${evidence.evidenceId}，并切换到其关联 PDF；请在阅读页核对其来源定位与条件。`, `Located Gap-linked EvidenceCard ${evidence.evidenceId} and switched to its attached PDF; verify its locator and conditions in the reader.`)
      : text(`已定位 Gap 所引用的 EvidenceCard ${evidence.evidenceId}；不同论文的私有 PDF 已移出当前会话，请在阅读页核对导入来源与条件。`, `Located Gap-linked EvidenceCard ${evidence.evidenceId}. Private PDFs for other papers were removed from this session; verify imported provenance and conditions in the reader.`));
    setView("reader");
  }
  onMount(() => {
    if (window.matchMedia("(max-width: 560px)").matches) setRailContextOpen(false);
  });

  async function refreshLocalApiCapabilities() {
    const requestEpoch = ++localApiStatusRequestEpoch;
    if (!localApiEnabled()) {
      setApiCapabilityHealth("disabled");
      setApiProviders({});
      setApiSummary(text("本地 API 未启用。", "Local API is disabled."));
      return false;
    }
    if (untrack(apiCapabilityHealth) !== "ready") setApiCapabilityHealth("loading");
    try {
      const result = await getLocalApiStatus();
      if (requestEpoch !== localApiStatusRequestEpoch || launchPreview()) return;
      if (!isLocalApiStatus(result)) throw new Error("invalid local API capability snapshot");
      const enabled = Object.entries(result.providers).filter(([, value]) => value).map(([name]) => name).join(", ");
      setApiProviders(result.providers);
      setRetrievalSources((current) => reconcileRetrievalSources(current, result.providers));
      setApiCapabilityHealth("ready");
      setApiSummary(enabled
        ? text(`本地 API 能力快照已更新：${enabled}。所有执行仍需单独批准。`, `Local API capability snapshot updated: ${enabled}. Each execution still needs separate approval.`)
        : text("本地 API 可连接，但未配置服务商。", "The local API is reachable, but no provider is configured."));
    } catch (error) {
      if (requestEpoch !== localApiStatusRequestEpoch || launchPreview()) return;
      setApiProviders({});
      setApiCapabilityHealth("unavailable");
      setApiSummary(safeOperationFeedback(error, text("本地 API 暂不可连接；不会沿用旧提供方能力或提交新操作。", "The local API is temporarily unreachable. The UI will not retain stale provider capabilities or submit new operations.")));
    }
  }
  createEffect(() => {
    if (launchPreview() || !localApiEnabled()) {
      localApiStatusRequestEpoch += 1;
      setApiCapabilityHealth("disabled");
      setApiProviders({});
      setApiSummary(launchPreview()
        ? text("只读预览不连接本地 API。", "Read-only preview does not connect to the local API.")
        : text("本地 API 未启用。", "Local API is disabled."));
      return;
    }
    let disposed = false;
    const refresh = () => { if (!disposed) void refreshLocalApiCapabilities(); };
    refresh();
    const timer = window.setInterval(refresh, 30_000);
    onCleanup(() => { disposed = true; localApiStatusRequestEpoch += 1; window.clearInterval(timer); });
  });

  return <div class={`workbench theme-${theme()} view-${view()}`}>
    <Show when={view() === "launch"}><Launchpad onQuestion={beginLaunchMission} onPdf={beginPdfMission} onResume={resumeLaunch} onCandidates={localApiUsable() && apiProviders().deepseek ? requestQuestionCandidates : undefined} onPreviewStage={openLaunchPreview} candidatePdfTarget={candidatePdfTarget()} activeRunId={liveRunId()} onReturnToActiveRun={returnToActiveRunWorkspace} automaticExecutionAvailable={localApiUsable() && retrievalSources().length > 0} launchNotice={launchNotice()} onDismissLaunchNotice={() => setLaunchNotice(null)} pdfSubmissionPending={pdfSubmissionPending()} retryPdfSubmission={rootPdfRetry() ? { fileName: rootPdfRetry()!.file.name } : null} onRetryPdfSubmission={retryRootPdfSubmission} resumeSubmissionPending={resumeSubmissionPending()} language={language()} theme={theme()} onLanguage={(next) => { setLanguage(next); setUiLanguage(next); }} onTheme={setTheme} /></Show>
    <Show when={view() !== "launch"}>
    <aside class="research-rail" aria-label={text("研究任务导航", "Research task navigation")}>
      <a class="wordmark" href="/" onClick={(event) => { event.preventDefault(); returnToLaunch(); }} aria-label="CosMatter">Cos<span>Matter</span></a>
      <p class="rail-kicker">{text("材料科学证据航线", "MATERIALS EVIDENCE ROUTE")}</p>
      <Show when={launchPreview()}><p class="rail-preview-note">{text("只读预览：可查看阶段与空态，但不能修改任务或执行外部操作。", "Read-only preview: stages and empty states are viewable, but task changes and external actions are unavailable.")}</p></Show>
      <ol class="journey-track" aria-label={text("研究阶段", "Research stages")}>
        <For each={journey()}>{(stage, index) => <li class={`journey-${stage.state}`}><button type="button" aria-current={stage.view === view() ? "step" : undefined} title={journeyStateLabel(stage)} onClick={() => navigate(stage.view)}><span>{String(index() + 1).padStart(2, "0")}</span><div><strong>{language() === "zh" ? stage.zh : stage.en}</strong><small>{journeyStateLabel(stage)}</small></div></button></li>}</For>
      </ol>
      <details class="rail-context" open={railContextOpen()} onToggle={(event) => setRailContextOpen(event.currentTarget.open)}>
        <summary><span>{text("任务概览与本地状态", "Mission context and local status")}</span><small>{text("展开查看航线、审核锚点与本地状态", "Expand route, review anchor, and local status")}</small></summary>
      <Show when={journeyRelay().current}>{(current) => <section class="route-command-handoff" aria-label={text("当前航线交接", "Current route handoff")}>
        <header><small>{text("当前航线交接", "CURRENT ROUTE HANDOFF")}</small><span>{text("只投影当前任务门禁；不启动任何执行。", "Projects current task gates only; it starts no execution.")}</span></header>
        <div class="route-handoff-vector"><section class={`route-handoff-origin state-${current().state}`}><small>{text("当前舰位", "CURRENT STATION")}</small><strong>{language() === "zh" ? current().zh : current().en}</strong><span>{journeyOutputLabel(current())}</span></section><i aria-hidden="true">→</i><Show when={journeyRelay().next} fallback={<section class="route-handoff-destination state-complete"><small>{text("航线状态", "ROUTE STATE")}</small><strong>{text("等待人工复核", "Awaiting human review")}</strong><span>{text("当前链路没有自动完成动作。", "The current chain has no automatic completion action.")}</span></section>}>{(next) => <button type="button" class={`route-handoff-destination state-${launchPreview() && next().state === "blocked" ? "preview" : next().state}`} onClick={() => navigate(next().view)}><small>{launchPreview() && next().state === "blocked" ? text("预览下一空态", "PREVIEW EMPTY STATE") : next().state === "blocked" ? text("待补齐门禁", "GATE TO COMPLETE") : text("下一交接", "NEXT HANDOFF")}</small><strong>{language() === "zh" ? next().zh : next().en}</strong><span>{launchPreview() && next().state === "blocked" ? text("只读预览允许查看该阶段空态；不会创建任务、上传文件或执行外部操作。", "Read-only preview may show this stage's empty state; it creates no task, upload, or external action.") : next().state === "blocked" ? journeyStateLabel(next()) : journeyOutputLabel(next())}</span></button>}</Show></div>
      </section>}</Show>
      <section class="mission-identity" aria-label={text("当前任务", "Current mission")}>
        <small>{text("当前研究任务", "CURRENT MISSION")}</small><strong>{bundle().mission.material}</strong><span>{bundle().mission.property}</span><em>{bundle().status?.missionState ?? "LOCAL"}</em><Show when={taskArtifactLocked()}><b class="artifact-lock">{text("旧工件待重新核验", "ARTIFACTS REQUIRE RECHECK")}</b></Show>
      </section>
      <Show when={uiImportReceipt()}>{(receipt) => <section class="rail-import-receipt" aria-label={text("当前本地工件", "Current local artifact")}><small>{text("当前本地工件 / 浏览器内存", "CURRENT LOCAL ARTIFACT / BROWSER MEMORY")}</small><strong>{receipt().fileName}</strong><p>{text(`工件自述版本 ${receipt().schemaVersion} · ${localImportTimestamp(receipt().generatedAt, language())}`, `Artifact-declared version ${receipt().schemaVersion} · ${localImportTimestamp(receipt().generatedAt, language())}`)}</p><span>{text(`${localImportSize(receipt().byteLength)} · ${receipt().visibleRecordCount} 个可显示数据项`, `${localImportSize(receipt().byteLength)} · ${receipt().visibleRecordCount} visible record(s)`)}</span><Show when={receipt().withheldAcceptedEvidenceCount > 0}><p>{text(`已安全隐藏 ${receipt().withheldAcceptedEvidenceCount} 条不符合 UI 证据边界的已接受卡片；未显示其内容。`, `${receipt().withheldAcceptedEvidenceCount} declared accepted card(s) were safely withheld by the UI boundary; their content is not shown.`)}</p></Show></section>}</Show>
      <section class={`session-handoff state-${sessionHandoff().state}`} aria-label={text("当前审核锚点", "Current review anchor")}>
        <header><small>{text("当前审核锚点 / 只读", "CURRENT REVIEW ANCHOR / READ ONLY")}</small><span>{sessionHandoff().evidenceId ? text("EvidenceCard 已选", "EvidenceCard selected") : text("尚未选择 EvidenceCard", "No EvidenceCard selected")}</span></header>
        <strong>{sessionHandoffLabel(sessionHandoff().state)}</strong>
        <code>{sessionHandoff().documentId ?? text("未选择文献", "no paper selected")}</code>
        <p>{sessionHandoffDetail(sessionHandoff().state)}</p>
        <button type="button" onClick={() => navigate(sessionHandoff().destination)}>{sessionHandoffAction(sessionHandoff().state)}</button>
      </section>
      <section class="rail-stats" aria-label={text("任务摘要", "Mission summary")}>
        <div><strong>{reviewablePaperCount(bundle())}</strong><span>{text("可审查文献", "reviewable papers")}</span></div>
        <div><strong>{auditableAcceptedEvidence(bundle()).length}</strong><span>{text("可追溯证据", "auditable evidence")}</span></div>
        <div><strong>{bundle().sourceMapSummary.segmentCount}</strong><span>{text("来源片段", "source segments")}</span></div>
      </section>
      <Show when={activeOperation()}>{(operation) => <section class="rail-operation" role="status" aria-live="polite" aria-label={text("正在进行的本地操作", "Active local operation")}><small>{text("受控本地操作", "CONTROLLED LOCAL OPERATION")}</small><strong>{operation().label}</strong><p>{operation().detail}</p></section>}</Show>
      <section class="rail-status" aria-live="polite" aria-label={text("航线提示", "Route relay")}><small>{text("当前航线提示", "ROUTE RELAY")}</small><p>{status()}</p><Show when={routeRecovery()}>{(recovery) => <div class="rail-recovery"><small>{text("恢复 / 仅核验", "RECOVERY / REVIEW ONLY")}</small><Show when={recovery().contextZh}><p id="route-recovery-context">{language() === "zh" ? recovery().contextZh : recovery().contextEn}</p></Show><button type="button" class="rail-recovery-action" aria-describedby={recovery().contextZh ? "route-recovery-context" : undefined} onClick={() => navigate(recovery().view)}>{language() === "zh" ? recovery().zh : recovery().en}</button></div>}</Show></section>
      <Show when={localApiEnabled() && reminderBoard()}>{(board) => <section class="rail-runtime" aria-live="polite" aria-label={text("跨会话本地提醒", "Cross-session local reminders")}><small>{text("只读本地提醒", "READ-ONLY LOCAL REMINDERS")}</small><p>{board().reminder_count ? text(`待处理提醒：${board().reminder_count}。关闭页面不会自动处理。`, `${board().reminder_count} reminder(s) need attention. Closing this page does not process them.`) : text("没有已观察到的待处理提醒。", "No pending reminder is observed.")}</p><Show when={board().reminders.length}><ul><For each={board().reminders.slice(0, 4)}>{(reminder) => <li>{reminder.status === "overdue" ? text("已到期", "Overdue") : text("待处理", "Open")} · {reminder.stage ? runtimeStageLabel(reminder.stage) : reminderActionLabel(reminder.action_label)}</li>}</For></ul></Show><p>{text("提醒仅在本地读取时更新；它不是后台调度器，也不会发起检索、解析或重试。", "Reminders update only when read locally; this is not a background scheduler and never starts retrieval, parsing, or retry.")}</p></section>}</Show>
      <Show when={liveRunId() && localApiEnabled()}>
        <section class="rail-runtime" aria-live="polite" aria-label={text("本地运行状态", "Local runtime status")}>
          <small>{text("只读运行态势", "READ-ONLY RUNTIME")}</small>
          <p classList={{ "runtime-snapshot": true, [`state-${runtimeSnapshotFreshness().state}`]: true }}><strong>{runtimeSnapshotFreshness().state === "current"
            ? text("已核验本机快照", "verified local snapshot")
            : runtimeSnapshotFreshness().state === "aging"
              ? text("本机快照正在老化", "local snapshot is aging")
              : runtimeSnapshotFreshness().state === "unavailable"
                ? text("最新本机读取不可用", "latest local read unavailable")
                : text("等待本机完整快照", "awaiting complete local snapshot")}</strong> · {runtimeSnapshotFreshness().state === "current" || runtimeSnapshotFreshness().state === "aging"
              ? text(`三份同任务投影于 ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(runtimeSnapshotFreshness().observedAt!))} 完整读取；来源为本机阶段契约、固定 DAG 与运行遥测。`, `The run-bound contract, fixed DAG, and telemetry were read together at ${new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(runtimeSnapshotFreshness().observedAt!))}.`)
              : text("只有三份投影同时通过任务身份校验才会显示为当前状态；不会把目录能力或旧响应当作运行确认。", "Only a complete, identity-checked triple is shown as current; catalogue capability and old responses are never treated as runtime confirmation.")}</p>
          <button type="button" disabled={runtimeProjectionRefreshBusy()} onClick={() => void refreshRuntimeProjectionsManually()}>{runtimeProjectionRefreshBusy() ? text("正在刷新本机投影…", "Refreshing local projection…") : text("立即刷新本机运行态", "Refresh local runtime now")}</button>
          <p>{text("此操作只读取当前任务的阶段契约、固定 DAG 与遥测；不会执行检索、解析或重试。", "This reads only the current run's contract, fixed DAG, and telemetry; it does not execute retrieval, parsing, or retry.")}</p>
          <Show when={runtimeProjectionReady() && runtimeStage()} fallback={<p>{runtimeProjectionHealth() === "unavailable"
            ? text("本机运行投影暂不可读取；界面不会把缺失状态当作可执行阶段，并会在后续只读轮询中重试。", "The local runtime projection is temporarily unavailable. The UI will not treat missing state as an executable stage and will retry on later read-only polls.")
            : runtimeProjectionReady()
              ? text("本机阶段契约已读取，但未声明可进入的下一阶段；不会据此启动任何工作。", "The local stage contract is readable but declares no next stage; no work will start from this state.")
              : text("正在读取本地阶段契约；不会触发检索、解析或重试。", "Reading the local stage contract; no retrieval, parsing, or retry is triggered.")}</p>}>
            {(stage) => <><p><strong>{runtimeStageLabel(stage().stage)}</strong> · {runtimeStageStatusLabel(stage().status)}</p><dl><div><dt>{text("人工门", "Human gate")}</dt><dd>{stage().human_gate}</dd></div><div><dt>{text("恢复路线", "Recovery route")}</dt><dd>{stage().recovery_route}</dd></div><div><dt>{text("预期输出", "Expected outputs")}</dt><dd>{stage().expected_outputs.join(" · ")}</dd></div></dl></>}
          </Show>
          <Show when={runtimeStageRecovery()}>{(recovery) => <section class="runtime-stage-recovery" aria-label={text("阶段恢复导航", "Stage recovery navigation")}><small>{text("阶段恢复导航 / 不执行", "STAGE RECOVERY NAVIGATION / NO EXECUTION")}</small><p>{text("此入口只打开当前阶段对应的本地审核界面；仍须在该界面逐项确认人工门和授权。", "This opens only the local review surface for the current stage; its human gates and authorisations still require item-by-item confirmation there.")}</p><button type="button" onClick={openRuntimeStageRecovery}>{stageRecoveryLabel(recovery().target)}</button></section>}</Show>
          <section class="runtime-dag" aria-label={text("固定串行舰队交接", "Fixed serial fleet handoff")}>
            <header><small>{text("固定串行 DAG / 只读", "FIXED SERIAL DAG / READ ONLY")}</small><span>{runtimeDagRail().eligibleStage ? text(`当前仅 ${runtimeStageLabel(runtimeDagRail().eligibleStage!)} 具备就绪资格`, `Only ${runtimeStageLabel(runtimeDagRail().eligibleStage!)} is currently eligible`) : text("当前没有可自动执行的阶段", "No stage is automatically executable")}</span></header>
            <Show when={runtimeDagRail().state === "declared"} fallback={<p>{text("DAG 投影不可用或未通过固定结构校验；界面不会以不明运行计划替代它。", "The DAG projection is unavailable or did not pass fixed-shape validation; the UI will not substitute an unknown runtime plan.")}</p>}>
              <ol><For each={runtimeDagRail().stages}>{(stage, index) => <li classList={{ complete: stage.status === "completed", ready: stage.status === "ready", waiting: stage.status === "waiting_human_review", blocked: stage.status === "blocked" }}><span>{String(index() + 1).padStart(2, "0")}</span><strong>{runtimeStageLabel(stage.stage)}</strong><em>{runtimeStageStatusLabel(stage.status)}</em></li>}</For></ol>
              <p>{text("这是一份已声明的串行就绪视图：它不提交任务、不绕过人工门，也不授予任何 provider 调用权限。", "This is a declared serial readiness view: it submits no work, bypasses no human gate, and grants no provider-call authority.")}</p>
            </Show>
          </section>
          <Show when={runtimeAttention().length} fallback={<p>{text("未发现需要提示的运行状态；这不等于科学结论或 provider 可用性保证。", "No runtime attention item is present; this is not a scientific conclusion or provider availability guarantee.")}</p>}><ul><For each={runtimeAttention()}>{(attention) => <li>{runtimeAttentionLabel(attention)}</li>}</For></ul></Show>
          <Show when={dispatchRecovery().length > 0}><section class="runtime-dispatch-recovery" aria-label={text("外部调用恢复指引", "External dispatch recovery guidance")}><small>{text("外部调用恢复 / 只读", "EXTERNAL DISPATCH RECOVERY / READ ONLY")}</small><For each={dispatchRecovery()}>{(item) => <p><strong>{dispatchOperationLabel(item.operation)}</strong>{text(`：未完成 ${item.incompleteCount} 次；结果未知 ${item.unknownOutcomeCount} 次。`, `: ${item.incompleteCount} incomplete; ${item.unknownOutcomeCount} outcome(s) unknown.`)} {text("先检查本地审计记录；如可行，再在服务商侧核验状态。若仍无法确认，才由研究者创建新的、明确授权调用。不会自动重试。", "Check the local audit record first and, where possible, verify provider status. Only if the outcome remains unconfirmed may a researcher create a new explicitly authorised call. No automatic retry occurs.")}</p>}</For></section></Show>
          <Show when={operationalTelemetry()}>{(telemetry) => <p>{text(`已记录的本地 provider 调用：${telemetryRequestCount()}；成本/时延披露：${telemetry().cost_latency_status}。`, `Recorded local provider calls: ${telemetryRequestCount()}; cost/latency disclosure: ${telemetry().cost_latency_status}.`)}</p>}</Show>
        </section>
        <section class="rail-execution" aria-label={text("本地任务控制", "Local task control")}><small>{text("受控执行", "CONTROLLED EXECUTION")}</small><p>{text("停止后不会再接收该任务的迟到结果；已登记工件保留供回看。", "After stopping, late results for this task are ignored; registered artifacts remain reviewable.")}</p><button type="button" onClick={stopCurrentRun}>{text("停止当前本地任务", "Stop current local task")}</button></section>
       </Show>
      </details>
      <Show when={view() === "discover" && !launchPreview()} fallback={view() === "discover" ? <p class="rail-preview-note">{text("预览模式下已隐藏受控执行、文件导入与本地任务修改。", "Controlled execution, file import, and local task changes are hidden in preview mode.")}</p> : null}>
        <p class="rail-definition-note">{text("任务输入与确认位于主工作区；侧栏仅保留导航和受控执行。", "Task inputs and confirmation are in the main workspace; this rail keeps navigation and controlled execution only.")}</p>
        <Show when={liveRunId()}><label class="consent plan-draft-consent"><input type="checkbox" checked={planDraftConsent()} onChange={(event) => setPlanDraftConsent(event.currentTarget.checked)} />{text("我同意将当前任务边界发送至 DeepSeek，仅生成未受信计划草案；不会批准计划、检索或接受证据。勾选后可在“高级：手动受控执行”中起草。", "I authorize sending the current task boundary to DeepSeek only for an untrusted plan draft. This does not approve a plan, retrieve, or accept evidence. After checking, draft from Advanced manual control.")}</label></Show>
        <Show when={liveRunId() && planApproved()}><label class="consent query-execution-consent"><input type="checkbox" checked={queryExecutionConsent()} onChange={(event) => setQueryExecutionConsent(event.currentTarget.checked)} />{text("我同意将人工批准的检索式发送至所选书目服务，用于受控元数据检索；不会上传全文或接受 EvidenceCard。勾选后可在“高级：手动受控执行”中执行。", "I authorize sending the human-approved queries to selected bibliographic services for controlled metadata retrieval. This does not upload full text or accept EvidenceCards. After checking, run it from Advanced manual control.")}</label></Show>
        <details class="mission-api" open={manualControlOpen()} onToggle={(event) => setManualControlOpen(event.currentTarget.open)}><summary>{text("高级：手动受控执行", "Advanced: manual controlled execution")}</summary><p>{text("此分步入口用于人工调试或逐步复现；常规研究请使用上方任务确认或起始页问题入口。它不会替代 EvidenceCard 的人工审核。", "This stepwise route is for manual debugging or reproducible execution. For ordinary research, use the mission confirmation above or the launch-page question entry. It never replaces human EvidenceCard review.")}</p><p>{apiSummary()}</p><button type="button" onClick={updateMission}>{text("仅更新本地任务边界", "Update local mission boundary only")}</button><Show when={localApiUsable()} fallback={<small>{text("执行入口要求当前可连接的本机 API；不会沿用过期提供方能力。", "Execution controls require a currently reachable local API; stale provider capabilities are never reused.")}</small>}><button class="primary-action" type="button" onClick={() => void launchLiveMission()}>{text("启动受控 API 任务", "Start controlled API mission")}</button><Show when={liveRunId()}><button type="button" disabled={!apiProviders().deepseek} onClick={() => void requestPlanDraft()}>{text("起草计划", "Draft plan")}</button><Show when={draftContent()}><label>{text("未受信草案", "Untrusted draft")}<textarea value={draftContent()} readOnly rows="4" /></label></Show><label>{text("人工复核计划 JSON", "Human-reviewed plan JSON")}<textarea value={reviewedPlan()} onInput={(event) => setReviewedPlan(event.currentTarget.value)} rows="5" /></label><button type="button" onClick={() => void approveReviewedPlan()}>{text("批准计划", "Approve plan")}</button><Show when={planApproved()}><fieldset><legend>{text("检索来源", "Retrieval sources")}</legend><For each={SOURCES}>{(source) => <label><input type="checkbox" checked={retrievalSources().includes(source.id)} disabled={!apiProviders()[source.provider]} onChange={() => toggleSource(source.id)} />{source.label}</label>}</For></fieldset><button class="primary-action" type="button" disabled={!retrievalSources().length} onClick={() => void executeApprovedQueries()}>{text("执行已批准检索", "Run approved retrieval")}</button></Show></Show></Show><section class="examples"><p>{text("示例问题", "Suggested questions")}</p><For each={examples()}>{(example) => <button type="button" onClick={() => updateQuestion(example)}>{example}</button>}</For></section><label class="import-control" aria-busy={uiImportPending()}>{uiImportPending() ? text("正在导入脱敏 UI JSON…", "Importing redacted UI JSON…") : text("导入脱敏 UI JSON", "Import redacted UI JSON")}<input type="file" disabled={uiImportPending()} accept="application/json,.json" onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; importBundle(file); }} /></label><Show when={uiImportReceipt()}>{(receipt) => <section class="import-artifact-receipt" aria-label={text("已导入工件摘要", "Imported artifact summary")} aria-live="polite"><small>{text("本地导入回执 / 浏览器内存", "LOCAL IMPORT RECEIPT / BROWSER MEMORY")}</small><strong>{receipt().fileName}</strong><dl><div><dt>{text("工件自述版本", "Artifact-declared version")}</dt><dd>{receipt().schemaVersion}</dd></div><div><dt>{text("工件自述生成时间", "Artifact-declared time")}</dt><dd>{localImportTimestamp(receipt().generatedAt, language())}</dd></div><div><dt>{text("文件大小", "File size")}</dt><dd>{localImportSize(receipt().byteLength)}</dd></div><div><dt>{text("可显示数据项", "Visible records")}</dt><dd>{receipt().visibleRecordCount}</dd></div></dl><Show when={receipt().withheldAcceptedEvidenceCount > 0}><p>{text(`已安全隐藏 ${receipt().withheldAcceptedEvidenceCount} 条不符合 UI 证据边界的已接受卡片；未显示其内容。`, `${receipt().withheldAcceptedEvidenceCount} declared accepted card(s) were safely withheld by the UI boundary; their content is not shown.`)}</p></Show><p>{text("此回执仅显示用户明确选择的本地 JSON 自述元数据；不会验证完整性、作者身份或科学结论，也不会上传文件、读取路径或显示全文。", "This receipt displays only self-declared metadata from the user-selected local JSON. It does not verify integrity, authorship, or scientific conclusions, and does not upload the file, read paths, or show full text.")}</p></section>}</Show></details>
      </Show>
      <div class="rail-footer"><div class="language-toggle" aria-label="Language"><button type="button" classList={{ active: language() === "zh" }} onClick={() => { setLanguage("zh"); setUiLanguage("zh"); }}>ZH</button><button type="button" classList={{ active: language() === "en" }} onClick={() => { setLanguage("en"); setUiLanguage("en"); }}>EN</button></div><label>{text("主题", "Theme")}<select value={theme()} onChange={(event) => setTheme(event.currentTarget.value as Theme)}><option value="light">{text("浅色", "Light")}</option><option value="dark">{text("深色", "Dark")}</option><option value="eye">{text("护眼", "Eye care")}</option></select></label></div>
    </aside>
    <Suspense fallback={<main class="route-loading" aria-live="polite"><small>{text("正在切换工作区", "SWITCHING WORKSPACE")}</small><h1>{text("正在载入已选择的本地工作区", "Loading the selected local workspace")}</h1><p>{text("不会读取私有文件、调用提供方或改变任务。", "No private file is read, provider is called, or task is changed.")}</p></main>}>
      <Show when={view() === "discover"} fallback={view() === "workflow" ? <FleetCommand bundle={bundle()} locale={language()} facilityContracts={facilityContracts()} facilityCatalogueHealth={facilityCatalogueHealth()} onRefreshFacilityContracts={() => void refreshFacilityContracts()} bfoTemplateId={launchPreview() ? null : activeBfoTemplateId()} selectedDocumentId={launchPreview() ? null : selectedDocumentId()} pdfTask={previewPdfTask()} pdfTaskFreshness={selectedPdfTaskFreshness()} pdfTasks={previewPdfTasks()} onSelectPdf={previewCanActOnRun() ? (task) => setPdfTask(task) : undefined} markdownUrl={previewPdfTask() && liveRunId() ? privateMarkdownUrl(liveRunId()!, previewPdfTask()!.document_id) : null} onRefreshPdf={previewPdfTask() ? refreshPdfTask : undefined} onConfirmPdfDoi={previewPdfTask() ? confirmManualPdfDoi : undefined} onExpandPdfCitations={previewPdfTask() ? expandPdfCitationGraph : undefined} onOpenTaskControl={previewCanActOnRun() ? openManualTaskControl : undefined} automaticMissionPending={launchPreview() ? false : automaticMissionPending()} automaticCancellationRequested={launchPreview() ? false : automaticCancellationRequested()} onCancelAutomaticMission={automaticCancellationEnabled(launchPreview(), liveRunId(), automaticExecution()?.state, automaticCancellationRequested()) ? cancelAutomaticMission : undefined} automaticAuthorization={launchPreview() ? null : automaticAuthorization()} readOnlyPreview={launchPreview()} onExitPreview={returnToLaunch} onNavigate={navigate} /> : view() === "graph" ? <GraphNetwork bundle={bundle()} theme={theme()} locale={language()} runId={previewCanActOnRun() ? liveRunId() : null} selectedDocumentId={launchPreview() ? null : selectedDocumentId()} pdfTask={previewPdfTask()} pdfTasks={previewPdfTasks()} screening={candidateScreening()} onLoadScreening={previewCanActOnRun() ? loadCandidateScreening : undefined} onSubmitScreening={previewCanActOnRun() ? submitCandidateScreening : undefined} onRequestFulltext={previewCanActOnRun() ? prepareCandidatePdf : undefined} readOnlyPreview={launchPreview()} onExitPreview={returnToLaunch} onNavigate={navigate} onSelectPaper={choosePaper} onSelectEvidence={chooseEvidence} /> : view() === "reader" ? <PaperReader bundle={bundle()} session={researchSession()} pdfTask={previewPdfTask()} screeningAllowsSourceReview={previewCanActOnRun() && selectedPaperScreenedForFulltext()} markdownUrl={previewPdfTask() && liveRunId() ? privateMarkdownUrl(liveRunId()!, previewPdfTask()!.document_id) : null} onRecordSourceMap={previewPdfTask() ? recordPrivateSourceMap : undefined} onLoadSourceMap={previewPdfTask() ? loadPrivateSourceMap : undefined} onRecordMaterialFacts={previewPdfTask() ? recordPrivateMaterialFacts : undefined} onRecordEvidence={previewPdfTask() ? recordPrivateEvidenceCard : undefined} readOnlyPreview={launchPreview()} onExitPreview={returnToLaunch} onNavigate={navigate} onSelectEvidence={chooseEvidence} /> : <ResearchExpansion bundle={bundle()} session={researchSession()} onNavigate={navigate} onOpenTaskControl={previewCanActOnRun() ? openManualTaskControl : undefined} onBuildConditionMatrix={previewCanActOnRun() ? buildConditionMatrix : undefined} onBuildGapCandidates={previewCanActOnRun() ? buildGapCandidates : undefined} onFocusEvidence={focusGapEvidence} readOnlyPreview={launchPreview()} onExitPreview={returnToLaunch} />}>
      <main class="discovery-stage mission-stage"><FleetDecoration kind="discover" state={fleetVisualState(bundle(), "discover")} />
        <header class="stage-header"><div><p class="stage-kicker">COSMATTER / {text("任务定义", "MISSION DEFINITION")}</p><h1>{text("从问题到可审计的证据航线", "From question to an auditable evidence route")}</h1><p>{bundle().mission.question}</p></div></header>
        <Show when={launchPreview()}><ReadOnlyPreviewContext locale={language()} onExit={returnToLaunch} /></Show>
        <section class="mission-definition-form" aria-label={text("任务草稿", "Mission draft")}>
          <header><p class="stage-kicker">{text("任务草稿", "MISSION DRAFT")}</p><h2>{text("明确可比较的研究边界", "Define comparable research boundaries")}</h2><p>{text("先写清问题，再列出需要共同检索、抽取和核验的对象、维度与范围。以下修改仅在确认后成为当前任务。", "State the question, then list the objects, dimensions, and boundaries to retrieve, extract, and verify together. Changes become the current mission only after confirmation.")}</p></header>
          <label class="question-label"><span>{text("研究问题", "Research question")}</span><textarea ref={questionTextarea} value={question()} onInput={(event) => updateQuestion(event.currentTarget.value)} rows="3" placeholder={text("提出一个可由文献证据回答的问题", "Ask a question that can be answered from literature evidence")} /></label>
          <section class="scope-editor" aria-label={text("任务边界", "Task boundaries")}>
            <label><span>{text("研究对象（可多个）", "Research objects (multiple allowed)")}</span><textarea value={missionBoundary().material} onInput={(event) => updateMissionBoundary("material", event.currentTarget.value)} rows="2" placeholder={text("例如：BiFeO₃；BaTiO₃；SrTiO₃", "e.g. BiFeO₃; BaTiO₃; SrTiO₃")} /></label>
            <label><span>{text("研究目标／比较维度", "Research targets / comparison dimensions")}</span><textarea value={missionBoundary().property} onInput={(event) => updateMissionBoundary("property", event.currentTarget.value)} rows="2" placeholder={text("例如：相稳定性；铁电极化；磁有序", "e.g. phase stability; ferroelectric polarization; magnetic order")} /></label>
            <label><span>{text("研究边界／比较范围", "Research boundaries / comparison scope")}</span><textarea value={missionBoundary().scope} onInput={(event) => updateMissionBoundary("scope", event.currentTarget.value)} rows="2" placeholder={text("例如：外延薄膜；应变、厚度与氧分压", "e.g. epitaxial films; strain, thickness, and oxygen pressure")} /></label>
            <p>{text("使用分号、逗号或换行分隔多个对象与维度；确认后，系统将把它们作为同一研究任务的边界。", "Separate multiple objects or dimensions with semicolons, commas, or new lines. On confirmation, they become boundaries of one research task.")}</p>
          </section>
          <footer class="mission-definition-actions"><span classList={{ "draft-changed": !missionDraftReady() || missionDraftChanged(), "draft-synced": missionDraftReady() && !missionDraftChanged() }}>{launchPreview() ? text("只读预览：任务确认已锁定", "Read-only preview: mission confirmation is locked") : !missionDraftReady() ? text(`还需填写：${missionDraftMissing().join("、")}`, `Still required: ${missionDraftMissing().join(", ")}`) : missionDraftChanged() ? text("存在尚未确认的任务变更", "Unconfirmed task changes") : text("草稿与当前任务已同步", "Draft matches the current mission")}</span><button class="primary-action" type="button" disabled={launchPreview() || !missionDraftReady()} onClick={enterBridge}>{launchPreview() ? text("只读预览：不能确认任务", "Read-only preview: confirmation unavailable") : text("确认任务并进入受控编排", "Confirm mission and enter orchestration")}</button></footer>
        </section>
        <section class="mission-preview" aria-label={text("当前审计态势", "Current audit posture")}><div class="artifact-heading"><div><p class="stage-kicker">{text("当前审计态势", "CURRENT AUDIT POSTURE")}</p><h2>{text("由当前任务与导入工件派生", "Derived from the current task and imported artifacts")}</h2></div><Show when={taskArtifactLocked()}><p class="artifact-lock-notice">{text("任务边界已变更：下游阶段锁定，旧工件仅供回看。", "Task boundary changed: downstream stages are locked; old artifacts are review-only.")}</p></Show></div><div class="artifact-grid"><For each={artifactStatuses()}>{(card, index) => <article class={`artifact-card artifact-${card.state}`}><header><small>{String(index() + 1).padStart(2, "0")}</small><span>{artifactState(card)}</span></header><h2>{artifactTitle(card)}</h2><p>{artifactDetail(card)}</p><dl><For each={card.metrics}>{(metric) => <div><dt>{metricLabel(metric.key)}</dt><dd>{metric.value || (card.key === "brief" ? text("未填写", "Not set") : "—")}</dd></div>}</For></dl><footer><button type="button" onClick={() => openArtifactNext(card)}>{artifactNext(card)}</button><small>{text("仅打开对应本地界面；不执行检索、解析或外部调用。", "Opens only the corresponding local view; it executes no retrieval, parsing, or external call.")}</small></footer></article>}</For></div></section>
        <footer class="stage-note">{text("本页只定义任务与边界。问题入口的一次授权可启动受控元数据检索；高级分步执行和任何 EvidenceCard 接受仍保留独立人工门禁。", "This page only defines task boundaries. One-time consent in question entry may start controlled metadata retrieval; advanced stepwise execution and every EvidenceCard acceptance retain separate human gates.")}</footer>
      </main>
      </Show>
    </Suspense>
    </Show>
  </div>;
}



