import { ErrorBoundary, For, Show, Suspense, createEffect, createMemo, createSignal, lazy } from "solid-js";

import { CandidateScreeningPanel } from "./CandidateScreeningPanel";
import { CandidateFulltextQueue } from "./CandidateFulltextQueue";
import { SourceMarkdownLinkButton } from "./SourceMarkdownLinkButton";
import { EvidenceGraphExplorer } from "./EvidenceGraphExplorer";
import { GraphConnections } from "./GraphConnections";
import { ExtractionTablePanel, type ExtractionPaper } from "./ExtractionTablePanel";
import { GraphPaperSearch } from "./GraphPaperSearch";
import { graphDisplayLabel, graphDoi, searchableGraphNodes, searchGraph } from "./graphSearch";
import type { GraphCanvasControls, LiteratureGraphCanvasProps } from "./LiteratureGraphCanvas";
import { TOPIC_KEYS, isPaperNode, topicFor, type TopicKey } from "./literatureTopology";
import { literatureGraphMode } from "./literatureGraphMode";
import { displayPaperTitle } from "./paperTitle";
import { localPaperMapLink } from "./liveRunIdentity";
import { auditableAcceptedEvidence, documentIdForReviewablePaper, evidenceForPaper } from "./evidenceLinking";
import { graphEdgeStillExists, graphSelectionVisibility } from "./graphSelectionState";
import { graphNodeForSessionDocument } from "./graphSessionSelection";
import { readerRouteAfterCommittedSelection } from "./graphReaderHandoff";
import { candidatePdfAction, paperPdfIntake, pdfTaskForPaper } from "./paperPdfIntake";
import { paperWorkflowState, type PaperWorkflowState } from "./paperWorkflowState";
import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";
import { shouldPromptForScreening } from "./screeningActionState";
import { candidateScreeningProgress } from "./candidateScreeningProgress";
import { graphFootnote } from "./graphFootnote";
import { readingRoute, type ReadingRouteAction } from "./readingRoute";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import { RelationReconciliationPanel } from "./RelationReconciliationPanel";
import { CandidateDuplicateReconciliationPanel } from "./CandidateDuplicateReconciliationPanel";
import { ActionButton } from "./uiPrimitives";
import type { EvidenceCard, ImportedBundle, LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import type { CandidateScreening, CandidateScreeningCandidate, CandidateScreeningDecision, PdfTaskStatus, SavedSourceParseHealth, SavedSourceParseTask } from "./localApi";
import "./frontier-graph.css";

type NodeGroup = "mission" | "papers" | "evidence" | "conditions" | "references" | "structure";
type EdgeGroup = "discovery" | "evidence" | "conditions" | "bibliography" | "related" | "structure";
type NavigateView = "discover" | "workflow" | "reader" | "horizon";
const RawLiteratureGraphCanvas = lazy(() => import("./LiteratureGraphCanvas").then((module) => ({ default: module.LiteratureGraphCanvas })));
function LiteratureGraphCanvas(props: LiteratureGraphCanvasProps) {
  return <Show when={props.nodes().length} fallback={<section class="graph-canvas-loading" role="status"><small>NO VISIBLE GRAPH ELEMENTS</small><p>当前筛选没有可绘制节点；调整搜索或显示范围后，交互式图谱引擎才会加载。</p></section>}><ErrorBoundary fallback={(_error, reset) => <section class="graph-canvas-fallback" role="status"><small>INTERACTIVE GRAPH UNAVAILABLE</small><strong>交互式图谱暂不可用 / Interactive graph unavailable</strong><p>筛选和审计信息保持不变；未读取私有全文、未调用提供方，也未修改任务。</p><ActionButton size="sm" variant="secondary" onClick={reset}>重试载入画布 / Retry canvas</ActionButton></section>}><Suspense fallback={<section class="graph-canvas-loading" role="status"><small>LOADING INTERACTIVE GRAPH</small><p>图谱引擎仅在此工作区加载；当前不会读取私有全文或调用提供方。</p></section>}><RawLiteratureGraphCanvas {...props} /></Suspense></ErrorBoundary></Show>;
}

const NODE_GROUPS: Array<{ id: NodeGroup; zh: string; en: string; color: string }> = [
  { id: "mission", zh: "任务", en: "Mission", color: "var(--signal-blue)" },
  { id: "papers", zh: "论文", en: "Papers", color: "var(--signal-teal)" },
  { id: "evidence", zh: "已接受证据", en: "Accepted evidence", color: "var(--signal-violet)" },
  { id: "conditions", zh: "条件簇与矛盾", en: "Condition clusters & conflicts", color: "var(--signal-amber)" },
  { id: "references", zh: "书目元数据", en: "Reference metadata", color: "var(--signal-amber)" },
  { id: "structure", zh: "集合与结构", en: "Collections", color: "var(--signal-rose)" },
];
const EDGE_GROUPS: Array<{ id: EdgeGroup; zh: string; en: string }> = [
  { id: "discovery", zh: "候选路线", en: "Discovery routes" },
  { id: "evidence", zh: "证据溯源", en: "Evidence provenance" },
  { id: "conditions", zh: "条件支持／矛盾", en: "Condition support / contradiction" },
  { id: "bibliography", zh: "书目关联", en: "Bibliography" },
  { id: "related", zh: "题名建议", en: "Title suggestions" },
  { id: "structure", zh: "集合关系", en: "Structure" },
];
function nodeGroup(node: LiteratureGraphNode): NodeGroup {
  if (node.kind === "mission") return "mission";
  if (isPaperNode(node)) return "papers";
  if (["accepted_evidence", "evidence_card", "research_gap_candidate"].includes(node.kind)) return "evidence";
  if (node.kind === "condition_cluster") return "conditions";
  if (["openalex_work", "crossref_work", "citation_work"].includes(node.kind)) return "references";
  return "structure";
}
function edgeGroup(edge: LiteratureGraphEdge): EdgeGroup {
  if (edge.edgeType === "retrieval_candidate") return "discovery";
  if (["source_provenance", "gap_evidence_basis"].includes(edge.edgeType)) return "evidence";
  if (["condition_support", "condition_contradiction"].includes(edge.edgeType)) return "conditions";
  if (edge.edgeType === "title_similarity_suggestion") return "related";
  if (["citation_reference", "citation_cited_by", "algorithmic_related", "crossref_reference"].includes(edge.edgeType)) return "bibliography";
  return "structure";
}

export function GraphNetwork(props: { bundle: ImportedBundle; theme: string; locale: "zh" | "en"; runId?: string | null; selectedDocumentId?: string | null; linkedDocumentId?: string | null; linkedScreeningRevision?: string | null; evidenceLinkUnavailable?: boolean; pdfTask: PdfTaskStatus | null; pdfTasks?: PdfTaskStatus[]; sourceTasks?: SavedSourceParseTask[]; sourceHealth?: SavedSourceParseHealth; onRefreshSourceParses?: () => void; onLinkSourceMarkdown?: (runId: string, documentId: string, file: File) => Promise<void>; screening: CandidateScreening | null; onLoadScreening?: () => Promise<void>; onSubmitScreening?: (decisions: CandidateScreeningDecision[], revision?: string) => Promise<void>; onRequestFulltext?: (candidate: CandidateScreeningCandidate) => void; readOnlyPreview?: boolean; onExitPreview?: () => void; onNavigate: (view: NavigateView) => void; onSelectPaper: (node: LiteratureGraphNode) => boolean; onSelectEvidence: (evidence: EvidenceCard) => boolean }) {
  const [query, setQuery] = createSignal("");
  const [showSearchContext, setShowSearchContext] = createSignal(false);
  const setSearchQuery = (value: string) => {
    setShowSearchContext(false);
    setQuery(value);
  };
  const [selectedTopic, setSelectedTopic] = createSignal<TopicKey | "all">("all");
  const [advanced, setAdvanced] = createSignal(false);
  const [showMobileOptions, setShowMobileOptions] = createSignal(false);
  const [display, setDisplay] = createSignal<"map" | "table" | ExtractionPaper>("map");
  const tablePaper = createMemo(() => {
    const view = display();
    return typeof view === "object" ? view : null;
  });
  const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
  const [selectedEdge, setSelectedEdge] = createSignal<LiteratureGraphEdge | null>(null);
  const [focusSelection, setFocusSelection] = createSignal(false);
  // The graph remains the primary reading surface. Details appear only after a researcher asks for them or selects an object.
  const [inspectorOpen, setInspectorOpen] = createSignal(false);
  const [nodeTrail, setNodeTrail] = createSignal<string[]>([]);
  const [controls, setControls] = createSignal<GraphCanvasControls | null>(null);
  const [nodeVisibility, setNodeVisibility] = createSignal<Record<NodeGroup, boolean>>({ mission: true, papers: true, evidence: true, conditions: true, references: false, structure: false });
  const [edgeVisibility, setEdgeVisibility] = createSignal<Record<EdgeGroup, boolean>>({ discovery: true, evidence: true, conditions: true, bibliography: false, related: false, structure: false });
  const [citationAutoShown, setCitationAutoShown] = createSignal(false);
  const [sessionSelectionRestored, setSessionSelectionRestored] = createSignal(false);
  const [screeningFocusId, setScreeningFocusId] = createSignal<string | null>(null);
  const [screeningPanelOpen, setScreeningPanelOpen] = createSignal(Boolean(props.linkedScreeningRevision));
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const graph = () => props.bundle.literatureGraph;
  const nodesById = createMemo(() => new Map(graph().nodes.map(node => [node.nodeId, node])));
  function nodeLabel(id: string) {
    const node = nodesById().get(id);
    return node ? graphDisplayLabel(node) : id;
  }
  const lastVisited = createMemo(() => nodeTrail().map(id => nodesById().get(id)).filter(node => node !== undefined).at(-1));
  const graphScope = createMemo(() => JSON.stringify([props.runId, props.bundle.mission.missionId]));
  createEffect(() => { graphScope(); setNodeTrail([]); setDisplay("map"); });
  const searchable = createMemo(() => searchableGraphNodes(graph().nodes, props.bundle.evidenceCards));
  const searchMatches = createMemo(() => searchGraph(searchable(), query()));
  const selectedDoi = createMemo(() => {
    const record = searchable().find(node => node.nodeId === selectedNodeId());
    return record && graphDoi(record);
  });
  const matchIds = createMemo(() => new Set(searchMatches().map(node => node.nodeId)));
  const visibleNodes = createMemo(() => {
    const all = graph().nodes.filter((node) => nodeVisibility()[nodeGroup(node)] && (!isPaperNode(node) || selectedTopic() === "all" || topicFor(node) === selectedTopic()) && (showSearchContext() || !query().trim() || matchIds().has(node.nodeId)));
    if (!focusSelection() || !selectedNodeId()) return all;
    const neighbours = new Set([selectedNodeId()!]);
    graph().edges.forEach((edge) => { if (edge.sourceId === selectedNodeId()) neighbours.add(edge.targetId); if (edge.targetId === selectedNodeId()) neighbours.add(edge.sourceId); });
    return all.filter((node) => neighbours.has(node.nodeId));
  });
  const visibleIds = createMemo(() => new Set(visibleNodes().map((node) => node.nodeId)));
  const visibleEdges = createMemo(() => graph().edges.filter((edge) => edgeVisibility()[edgeGroup(edge)] && visibleIds().has(edge.sourceId) && visibleIds().has(edge.targetId)));
  const selectionState = createMemo(() => graphSelectionVisibility(selectedNodeId(), graph().nodes, visibleNodes()));
  const selectedNode = createMemo(() => selectedNodeId() ? graph().nodes.find((node) => node.nodeId === selectedNodeId()) ?? null : null);
  const selectedPaperHidden = createMemo(() => Boolean(selectedNode() && isPaperNode(selectedNode()!) && selectionState().exists && !selectionState().visible));
  const evidenceByPaper = createMemo(() => new Map(graph().nodes.filter(node => documentIdForReviewablePaper(node))
    .map(node => [node.nodeId, evidenceForPaper(props.bundle, node)])));
  const linkedEvidence = createMemo(() => evidenceByPaper().get(selectedNodeId() ?? "") ?? []);
  const readableCards = createMemo(() => new Map([...evidenceByPaper().values()].flat()
    .filter(card => card.provenance.locator.trim()).map(card => ["evidence:" + card.evidenceId, card])));
  const selectedCard = createMemo(() => {
    const node = selectedNode();
    return node && ["accepted_evidence", "evidence_card"].includes(node.kind) ? readableCards().get(node.nodeId) : undefined;
  });
  const conditionEvidence = createMemo(() => {
    const condition = selectedNode();
    if (!condition || condition.kind !== "condition_cluster") return [];
    return graph().edges.flatMap((edge) => {
      if (edge.targetId !== condition.nodeId || !["condition_support", "condition_contradiction"].includes(edge.edgeType)) return [];
      if (edge.trustStatus !== "derived_condition_comparison_not_scientific_conclusion") return [];
      const evidence = readableCards().get(edge.sourceId);
      return evidence ? [{ evidence, relation: edge.edgeType === "condition_support" ? "support" : "contradiction" }] : [];
    });
  });
  const acceptedEvidenceCount = createMemo(() => auditableAcceptedEvidence(props.bundle).length);
  const acceptedEvidenceProvenanceAudited = createMemo(() => evidenceProvenanceAuditComplete(props.bundle.auditSummary.evidenceProvenance, props.bundle.evidenceCards.length));
  const paperStates = createMemo<Record<string, PaperWorkflowState>>(() => Object.fromEntries(
    graph().nodes.map((node) => {
      const documentId = documentIdForReviewablePaper(node);
      const decision = documentId ? props.screening?.decisions.find((item) => item.document_id === documentId)?.decision ?? "unreviewed" : null;
      const evidenceCount = evidenceByPaper().get(node.nodeId)?.length ?? 0;
      const recorded = props.sourceTasks?.find((task) => task.document_id === documentId);
      const state = paperWorkflowState(node, props.pdfTasks ?? (props.pdfTask ? [props.pdfTask] : []), decision, evidenceCount, acceptedEvidenceProvenanceAudited(), recorded);
      return state ? [node.nodeId, state] : null;
    }).filter((entry): entry is [string, PaperWorkflowState] => entry !== null),
  ));
  const paperStateCounts = createMemo(() => Object.values(paperStates()).reduce<Record<PaperWorkflowState, number>>((counts, state) => ({ ...counts, [state]: (counts[state] ?? 0) + 1 }), { untracked: 0, screening: 0, included: 0, parsing: 0, source_recorded: 0, source_map: 0, evidence_review: 0, provenance_audit: 0, accepted_evidence: 0, failed: 0, excluded: 0 }));
  const matchingPdfTask = createMemo(() => pdfTaskForPaper(props.pdfTasks ?? (props.pdfTask ? [props.pdfTask] : []), selectedNode()));
  const paperPdf = createMemo(() => paperPdfIntake(matchingPdfTask(), selectedNode()));
  const inspectedSource = createMemo(() => props.sourceTasks?.find((task) => task.document_id === paperPdf().documentId) ?? null);
  const linkSourceMarkdown = createMemo(() => {
    const runId = props.runId;
    const link = props.onLinkSourceMarkdown;
    return runId && link ? (documentId: string, file: File) => link(runId, documentId, file) : undefined;
  });
  const inspectedPdfAction = createMemo(() => candidatePdfAction(matchingPdfTask(), inspectedSource()));
  const hasInspectedSavedParse = () => inspectedPdfAction() === "recorded_active" || inspectedPdfAction() === "recorded_done" || inspectedPdfAction() === "recorded_reader";
  const paperDocumentId = (node: LiteratureGraphNode | null): string | null => documentIdForReviewablePaper(node);
  const selectedPaperMapLink = createMemo(() => {
    const documentId = paperDocumentId(selectedNode());
    return props.runId && !props.readOnlyPreview && documentId ? localPaperMapLink(window.location.origin, props.runId, documentId) : null;
  });
  const screeningCandidate = createMemo(() => { const documentId = paperDocumentId(selectedNode()); return documentId ? props.screening?.candidates.find((candidate) => candidate.document_id === documentId) ?? null : null; });
  const screeningDecision = createMemo(() => { const candidate = screeningCandidate(); return candidate ? props.screening?.decisions.find((decision) => decision.document_id === candidate.document_id)?.decision ?? "unreviewed" : "unreviewed"; });
  const paperCount = createMemo(() => visibleNodes().filter(isPaperNode).length);
  const visibleReviewablePaperCount = createMemo(() => visibleNodes().filter((node) => Boolean(documentIdForReviewablePaper(node))).length);
  const reviewablePaperCount = createMemo(() => graph().nodes.filter((node) => Boolean(documentIdForReviewablePaper(node))).length);
  const screeningProgress = createMemo(() => candidateScreeningProgress(
    props.screening,
    reviewablePaperCount(),
    Boolean(props.onLoadScreening && props.onSubmitScreening),
  ));
  const screeningProgressLabel = () => {
    const progress = screeningProgress();
    if (progress.state === "not_loaded") return t("待载入人工筛选清单", "Human checklist not loaded");
    if (progress.state === "unavailable") return t("仅预览：本机筛选接口不可用", "Preview only: local screening is unavailable");
    if (progress.state === "in_progress") return t(`已审 ${progress.reviewedCount}/${progress.candidateCount}，尚余 ${progress.pendingCount}`, `Reviewed ${progress.reviewedCount}/${progress.candidateCount}; ${progress.pendingCount} remaining`);
    return t(`筛选已提交，${progress.includedCount} 篇获准全文核对`, `Screening submitted; ${progress.includedCount} approved for full-text review`);
  };
  const bibliographyCount = createMemo(() => visibleNodes().filter((node) => node.kind === "citation_work").length);
  const contentMode = createMemo(() => literatureGraphMode(graph().nodes, graph().edges));
  const hasReviewablePapers = createMemo(() => contentMode() === "evidence");
  const hasCitationMap = createMemo(() => graph().nodes.some((node) => node.kind === "citation_work") && graph().edges.some((edge) => ["citation_reference", "citation_cited_by"].includes(edge.edgeType)));
  const hasNavigableMap = createMemo(() => contentMode() !== "empty");
  const routePapers = createMemo(() => readingRoute(graph().nodes, paperStates(), 6, {
    material: props.bundle.mission.material,
    property: props.bundle.mission.property,
    scope: props.bundle.mission.scope,
    question: props.bundle.mission.question,
  }, props.bundle.researchGuide));
  const relationCounts = createMemo(() => graph().edges.reduce<Record<EdgeGroup, number>>((counts, edge) => ({ ...counts, [edgeGroup(edge)]: counts[edgeGroup(edge)] + 1 }), { discovery: 0, evidence: 0, conditions: 0, bibliography: 0, related: 0, structure: 0 }));
  const paperStateLabel = (state: PaperWorkflowState | undefined) => {
    const labels: Record<PaperWorkflowState, [string, string]> = {
      untracked: ["未纳入当前审核路径", "not in the current review path"], screening: ["待人工筛选", "human screening pending"], included: ["已纳入全文核对", "included for full-text review"], parsing: ["私有解析中", "private parsing"], source_recorded: ["解析完成待取回", "completed parse output available"], source_map: ["待登记来源定位", "source location pending"], evidence_review: ["待审核材料事实", "material-fact review pending"], provenance_audit: ["已接受卡片，待精确来源审计", "accepted card; exact provenance audit pending"], accepted_evidence: ["已关联接受证据", "accepted evidence linked"], failed: ["解析失败，待人工处理", "parsing failed; human action needed"], excluded: ["已人工排除", "human-excluded"],
    };
    return t(...(labels[state ?? "untracked"]));
  };
  const titleAnchorLabel = (match: "material-and-context" | "context" | "material" | "none") => ({
    "material-and-context": t("任务对象与维度双命中", "material + task-context title anchors"),
    material: t("仅对象命中 · 研究维度待核对", "material only · task context needs review"),
    context: t("仅维度命中 · 研究对象待核对", "task context only · material needs review"),
    none: t("题名未命中任务锚点 · 优先人工判读", "no task title anchor · review first"),
  }[match]);
  const researchTrackLabel = (track: "exact_material" | "mechanism_analogue" | "algorithm" | "unclassified_legacy", counterevidenceOnly: boolean) => {
    const labels = {
      exact_material: t("同体系", "exact material"),
      mechanism_analogue: t("机制类比", "mechanism analogue"),
      algorithm: t("算法路线", "algorithm route"),
      unclassified_legacy: t("旧版未分类", "legacy unclassified"),
    };
    return `${labels[track]}${counterevidenceOnly ? t(" · 仅反证", " · counterevidence only") : ""}`;
  };
  const routePolicySummary = () => {
    const policy = props.bundle.researchGuide?.routePolicy;
    if (!policy) return t(`本地回退 ${routePapers().length}/${reviewablePaperCount()} 个舰位`, `local fallback ${routePapers().length}/${reviewablePaperCount()} slots`);
    const counts = policy.selectedTrackCounts;
    const missing = policy.trackShortfallCounts;
    const shortfall = Object.values(missing).reduce((sum, value) => sum + value, 0);
    return t(`后端路线：同体系 ${counts.exact_material} · 机制类比 ${counts.mechanism_analogue} · 算法 ${counts.algorithm} · 仅反证 ${policy.selectedCounterevidenceCount}${shortfall ? ` · 缺口 ${shortfall}` : ""}`, `backend route: exact ${counts.exact_material} · analogue ${counts.mechanism_analogue} · algorithm ${counts.algorithm} · counter-only ${policy.selectedCounterevidenceCount}${shortfall ? ` · shortfall ${shortfall}` : ""}`);
  };
  const routeShortfallSummary = () => {
    const policy = props.bundle.researchGuide?.routePolicy;
    if (!policy || !policy.shortfallReasonCodes.length) return null;
    const missing = policy.trackShortfallCounts;
    const tracks = ["exact_material", "mechanism_analogue", "algorithm"] as const;
    const poolIsShort = tracks.some((track) => policy.availableTrackCounts[track] < policy.trackMinimums[track]);
    const action = poolIsShort
      ? policy.queryTrackPlanningStatus === "approved_independent_tracks"
        ? t("候选池也不足；补检索只能使用 FlightPlan 已批准的对应轨道索引。", "The candidate pool is also short; supplemental retrieval may use only the corresponding approved FlightPlan track indexes.")
        : t("候选池也不足且当前计划未登记独立轨道索引；必须先人工修订并批准计划。", "The candidate pool is also short and the current plan has no independent track indexes; revise and approve the plan first.")
      : t("候选池已有条目但路线容量或保留项阻止达标；请显式调整筛选或路线最低数。", "Candidates are available, but route capacity or preserved items prevent the target; explicitly revise screening or route minimums.");
    return t(`路线编组缺口：同体系 ${missing.exact_material}、机制类比 ${missing.mechanism_analogue}、算法 ${missing.algorithm}。${action}`, `Route-composition shortfall: exact ${missing.exact_material}, analogue ${missing.mechanism_analogue}, algorithm ${missing.algorithm}. ${action}`);
  };
  const routeActionLabel = (action: ReadingRouteAction) => ({
    "recover-pdf": t("恢复 PDF 解析", "recover PDF parsing"), "register-source-map": t("登记来源定位", "register source locations"),
    "review-evidence": t("审核材料事实与证据", "review facts and evidence"), "audit-provenance": t("完成精确来源审计", "complete exact provenance audit"),
    "verify-evidence": t("核对已接受证据", "verify accepted evidence"), "select-pdf": t("选择授权 PDF", "select an authorized PDF"),
    "screen-paper": t("完成人工筛选", "complete human screening"), "load-screening": t("载入人工筛选清单", "load the human checklist"),
    "wait-for-parse": t("等待私有解析", "wait for private parsing"),
    "inspect-saved-parse": t("查看解析记录", "inspect saved parse"),
  } satisfies Record<ReadingRouteAction, string>)[action];
  const screeningActionRequired = createMemo(() => shouldPromptForScreening(hasReviewablePapers(), Boolean(props.onLoadScreening && props.onSubmitScreening), props.screening));
  const hasPersistedScreening = createMemo(() => props.screening?.trust_status === "human_reviewed_candidate_screening_not_scientific_evidence");
  const openScreening = (documentId: string | null = null) => {
    setScreeningFocusId(documentId);
    setScreeningPanelOpen(true);
  };
  createEffect(() => { if (hasCitationMap() && !citationAutoShown()) { setNodeVisibility((current) => ({ ...current, references: true })); setEdgeVisibility((current) => ({ ...current, bibliography: true })); setCitationAutoShown(true); } });
  // Restore the session paper once; later graph inspection remains user-directed.
  createEffect(() => {
    if (sessionSelectionRestored()) return;
    const paper = graphNodeForSessionDocument(graph().nodes, props.selectedDocumentId);
    if (!props.selectedDocumentId || paper) {
      if (paper) {
        setSelectedNodeId(paper.nodeId);
        setSelectedEdge(null);
        if (props.linkedDocumentId === props.selectedDocumentId) setInspectorOpen(true);
      }
      setSessionSelectionRestored(true);
    }
  });
  createEffect(() => {
    if (selectedNodeId() && !selectionState().exists) { setSelectedNodeId(null); setFocusSelection(false); }
    if (!graphEdgeStillExists(selectedEdge(), graph().edges)) setSelectedEdge(null);
  });
  let searchInput: HTMLInputElement | undefined;
  let inspectorElement: HTMLElement | undefined;
  let screeningDrawer: HTMLDivElement | undefined;
  let focusedLinkedInspector = false;
  const focusInspector = (linkedLanding = false) => {
    const origin = document.activeElement;
    queueMicrotask(() => {
      const active = document.activeElement;
      const onLandingHeading = linkedLanding && active?.matches("h1.route-focus-heading");
      if (inspectorElement?.isConnected && (active === origin || onLandingHeading || (!origin?.isConnected && active === document.body))) {
        inspectorElement.focus();
      }
    });
  };
  const focusLinkedInspector = (element: HTMLElement) => {
    inspectorElement = element;
    if (focusedLinkedInspector || !props.linkedDocumentId || props.linkedDocumentId !== props.selectedDocumentId) return;
    focusedLinkedInspector = true;
    focusInspector(true);
  };
  const topicLabel = (topic: TopicKey) => ({ ferroelectric: t("铁电性", "Ferroelectricity"), piezoelectric: t("压电性", "Piezoelectricity"), thin_film: t("薄膜与界面", "Thin films & interfaces"), domain_microstructure: t("畴与微观结构", "Domains & microstructure"), simulation_method: t("模拟与方法", "Simulation & methods"), other: t("其他题名元数据", "Other title metadata") } satisfies Record<TopicKey, string>)[topic];
  const inspectNode = (id: string) => {
    const node = nodesById().get(id);
    setSelectedNodeId(node?.nodeId ?? null);
    setSelectedEdge(null);
    if (node) setInspectorOpen(true);
    if (node && documentIdForReviewablePaper(node)) props.onSelectPaper(node);
  };
  const selectNode = (id: string) => { setNodeTrail([]); inspectNode(id); };
  const revealNodeContext = (node: LiteratureGraphNode) => {
    setShowSearchContext(true);
    const group = nodeGroup(node);
    if (!nodeVisibility()[group]) setNodeVisibility(current => ({ ...current, [group]: true }));
    if (isPaperNode(node) && selectedTopic() !== "all" && topicFor(node) !== selectedTopic()) setSelectedTopic("all");
  };
  const followConnection = (node: LiteratureGraphNode) => {
    const previous = selectedNodeId();
    if (previous && previous !== node.nodeId) setNodeTrail(trail => [...trail.slice(-31), previous]);
    revealNodeContext(node);
    inspectNode(node.nodeId);
    focusInspector();
  };
  const backToNode = () => {
    const node = lastVisited();
    if (!node) return;
    setNodeTrail(trail => trail.slice(0, trail.lastIndexOf(node.nodeId)));
    revealNodeContext(node);
    inspectNode(node.nodeId);
    focusInspector();
  };
  const openEvidence = (card: EvidenceCard) => {
    if (props.onSelectEvidence(card)) props.onNavigate("reader");
  };
  const openReaderForPaper = (paper: LiteratureGraphNode) => {
    const target = readerRouteAfterCommittedSelection(props.onSelectPaper(paper));
    if (target) props.onNavigate(target);
  };
  const selectSearchMatch = (node: LiteratureGraphNode) => {
    revealNodeContext(node);
    selectNode(node.nodeId);
    focusInspector();
  };
  const openSearchChecklist = () => {
    openScreening();
    requestAnimationFrame(() => screeningDrawer?.focus());
  };
  const selectEdge = (edge: LiteratureGraphEdge) => { setNodeTrail([]); setSelectedEdge(edge); setSelectedNodeId(null); setInspectorOpen(true); };
  const revealSelectedPaper = () => {
    setQuery("");
    setSelectedTopic("all");
    setNodeVisibility((current) => ({ ...current, papers: true }));
    setFocusSelection(false);
  };

  const trustLabel = (status: string) => {
    const labels: Record<string, readonly [string, string]> = {
      retrieval_candidate_not_scientific_evidence: ["检索候选 · 待核对原文", "Search candidate · source review pending"],
      candidate_metadata: ["候选书目信息", "Candidate metadata"],
      mission_navigation: ["任务导航", "Mission navigation"],
      accepted_evidence: ["证据卡已接受", "Accepted evidence"],
      accepted_evidence_source: ["已接受证据的来源", "Source of accepted evidence"],
      public_relation_metadata_not_scientific_evidence: ["公开书目关系", "Public bibliographic relation"],
      public_bibliographic_reference_metadata_not_scientific_evidence: ["公开引文元数据", "Public citation metadata"],
    };
    return Object.hasOwn(labels, status) ? t(...labels[status]) : status.replaceAll("_", " ");
  };
  const nodeKindLabel = (kind: string) => {
    const labels: Record<string, readonly [string, string]> = {
      mission: ["研究任务", "Research mission"], candidate_paper: ["候选论文", "Candidate paper"],
      evidence_paper: ["证据来源论文", "Evidence source paper"], relation_root_paper: ["引文起始论文", "Citation seed"],
      structured_paper: ["已结构化论文", "Structured paper"], accepted_evidence: ["已接受证据卡", "Accepted evidence card"],
      evidence_card: ["证据卡", "Evidence card"], research_gap_candidate: ["待审核问题", "Proposed research question"],
      condition_cluster: ["条件簇", "Condition cluster"], paper_entity: ["论文条目", "Paper element"],
      openalex_work: ["OpenAlex 书目", "OpenAlex record"], crossref_work: ["Crossref 书目", "Crossref record"],
      citation_work: ["引文条目", "Citation record"],
    };
    return Object.hasOwn(labels, kind) ? t(...labels[kind]) : kind.replaceAll("_", " ");
  };
  const legendStates = createMemo(() => (Object.keys(paperStateCounts()) as PaperWorkflowState[]).filter(state => paperStateCounts()[state] > 0));
  const missionSubject = () => [props.bundle.mission.material, props.bundle.mission.property].filter(Boolean).join(" · ");
  return <main class="frontier-literature-workbench">
    <header class="stage-header graph-header">
      <div class="graph-heading-copy">
        <h1>{hasCitationMap() && !hasReviewablePapers() ? t("引文星图", "Citation atlas") : t("文献星图", "Literature atlas")}</h1>
        <Show when={props.bundle.mission.question.trim()} fallback={<p class="graph-mission">{missionSubject()}</p>}>
          <details class="graph-question">
            <summary><span>{t("研究问题", "Research question")}</span>{missionSubject()}</summary>
            <p>{props.bundle.mission.question}</p>
          </details>
        </Show>
      </div>
      <Show when={props.runId && !props.readOnlyPreview}>
        <div class="literature-display-switch" role="group" aria-label={t("文献展示方式", "Literature view")}>
          <ActionButton size="sm" aria-pressed={display() === "map"} onClick={() => setDisplay("map")}>{t("文献关系图", "Literature map")}</ActionButton>
          <ActionButton size="sm" aria-pressed={display() !== "map"} onClick={() => setDisplay("table")}>{t("跨文献证据对照", "Compare paper evidence")}</ActionButton>
        </div>
      </Show>
    </header>
    <Show when={props.readOnlyPreview}><ReadOnlyPreviewContext locale={props.locale} onExit={props.onExitPreview} /></Show>
    <Show when={props.runId && !props.readOnlyPreview && display() !== "map" ? props.runId : null} keyed>{id =>
      <ExtractionTablePanel runId={id} locale={props.locale} paper={tablePaper()} onViewAll={() => setDisplay("table")}
        onBackToMap={() => { setDisplay("map"); focusInspector(); }} />
    }</Show>
    <Show when={!props.runId || props.readOnlyPreview || display() === "map"}>
    <Show when={hasNavigableMap()}><GraphPaperSearch locale={props.locale} query={query()} setQuery={setSearchQuery}
      matches={searchMatches()} visibleIds={visibleIds()} selectedId={selectedNodeId()} coverage={graph().coverage}
      select={selectSearchMatch} inputRef={element => { searchInput = element; }}
      openChecklist={hasReviewablePapers() && props.runId && props.onLoadScreening && props.onSubmitScreening ? openSearchChecklist : undefined}>
      <div class="graph-options" classList={{ expanded: showMobileOptions() }}>
        <button class="graph-options-toggle" type="button" aria-label={t("图谱显示选项", "Map display options")} aria-expanded={showMobileOptions()}
          aria-controls="literature-display-options" onClick={() => setShowMobileOptions(!showMobileOptions())}>{t("筛选", "Filters")}</button>
        <section id="literature-display-options" class="graph-controls" aria-label={t("图谱筛选", "Map filters")}>
          <Show when={hasReviewablePapers()}>
            <label>{t("主题簇", "Topic cluster")}
              <select value={selectedTopic()} onChange={event => setSelectedTopic(event.currentTarget.value as TopicKey | "all")}>
                <option value="all">{t("全部论文", "All papers")}</option>
                <For each={TOPIC_KEYS}>{topic => <option value={topic}>{topicLabel(topic)}</option>}</For>
              </select>
            </label>
          </Show>
          <button type="button" classList={{ active: advanced() }} aria-expanded={advanced()} onClick={() => setAdvanced(!advanced())}>
            {advanced() ? t("收起高级筛选", "Hide advanced filters") : t("高级筛选", "Advanced filters")}
          </button>
          <button type="button" disabled={!selectedNodeId()} aria-pressed={focusSelection()} classList={{ active: focusSelection() }}
            onClick={() => setFocusSelection(!focusSelection())}>{t("聚焦选择", "Focus selection")}</button>
          <button type="button" classList={{ active: inspectorOpen() }} aria-expanded={inspectorOpen()} onClick={() => setInspectorOpen(!inspectorOpen())}>
            {inspectorOpen() ? t("收起检查器", "Hide inspector") : selectedNodeId() || selectedEdge() ? t("查看当前选择", "Inspect selection") : t("打开检查器", "Open inspector")}
          </button>
        </section>
      </div>
      <Show when={advanced()}><section class="advanced-filters">
        <div><strong>{t("节点类型", "Node types")}</strong>
          <For each={NODE_GROUPS}>{group => <label><input type="checkbox" checked={nodeVisibility()[group.id]}
            onChange={event => setNodeVisibility(current => ({ ...current, [group.id]: event.currentTarget.checked }))} />{t(group.zh, group.en)}</label>}</For>
        </div>
        <div><strong>{t("关系类型", "Relation types")}</strong>
          <For each={EDGE_GROUPS}>{group => <label><input type="checkbox" checked={edgeVisibility()[group.id]}
            onChange={event => setEdgeVisibility(current => ({ ...current, [group.id]: event.currentTarget.checked }))} />{t(group.zh, group.en)}</label>}</For>
        </div>
      </section></Show>
    </GraphPaperSearch></Show>
    <Show when={props.linkedDocumentId && !graphNodeForSessionDocument(graph().nodes, props.linkedDocumentId)}>
      <div class="graph-screening-cue" role="status"><p>{t("当前文献星图找不到链接指定的论文。", "The paper in this link is unavailable in the current literature map.")}</p></div>
    </Show>
    <Show when={props.evidenceLinkUnavailable && graphNodeForSessionDocument(graph().nodes, props.linkedDocumentId)}>
      <div class="graph-screening-cue" role="status"><p>{t("链接指定的 EvidenceCard 或其已审核来源关系在当前运行中不可用。", "The linked EvidenceCard or its reviewed source relationship is unavailable in this run.")}</p></div>
    </Show>
    <Show when={hasNavigableMap()} fallback={<section class="graph-empty"><small>{t("文献星图待建立", "LITERATURE MAP PENDING")}</small><h2>{t("尚无可审查的文献或书目子图", "No reviewable literature or bibliography subgraph yet")}</h2><Show when={paperCount() > 0} fallback={<p>{t("当前任务只有边界标记，尚未导入或检索到论文元数据；书目关系、全文和 EvidenceCard 不会被自动虚构。", "The current task has only a boundary marker. No paper metadata has been imported or retrieved, and bibliography, full text, and EvidenceCards are never fabricated.")}</p>}><p>{t(`当前图谱含 ${paperCount()} 个仅供导航或演示的论文式节点；它们未形成任务可审核文献，不能用于筛选、全文处理或 EvidenceCard。`, `The map contains ${paperCount()} paper-like navigation or demo node(s). They have not formed reviewable literature for this mission and cannot enter screening, full-text work, or EvidenceCard review.`)}</p></Show><ActionButton variant="primary" onClick={() => props.onNavigate("workflow")}>{t("返回舰桥查看工件状态", "Return to bridge and inspect artifact status")}</ActionButton></section>}>
    <Show when={selectedPaperHidden()}><section class="graph-hidden-selection" aria-live="polite"><div><small>{t("当前选择已被筛选隐藏", "CURRENT SELECTION HIDDEN")}</small><Show when={selectedNode()}>{node => <strong>{graphDisplayLabel(node())}</strong>}</Show><p>{t("该论文仍是本次阅读会话的选择，但当前搜索、主题或节点筛选未将其显示在画布中。", "This paper remains selected for the current reading session, but the current search, topic, or node filter hides it from the canvas.")}</p></div><ActionButton size="sm" variant="secondary" onClick={revealSelectedPaper}>{t("显示当前论文", "Reveal current paper")}</ActionButton></section></Show>
    <Show when={!props.runId && hasReviewablePapers() && props.onLoadScreening && props.onSubmitScreening && hasPersistedScreening() && !screeningPanelOpen()}>
      <ActionButton size="sm" onClick={() => openScreening()}>{t("查看已登记筛选", "View recorded screening")}</ActionButton>
    </Show>
    <Show when={hasReviewablePapers() && props.onLoadScreening && props.onSubmitScreening && screeningPanelOpen()}>
      <div class="graph-screening-drawer" ref={screeningDrawer} tabindex="-1">
        <CandidateScreeningPanel locale={props.locale} missionId={props.bundle.mission.missionId} screening={props.screening} load={props.onLoadScreening!} submit={props.onSubmitScreening!}
          focusDocumentId={screeningFocusId()} linkedRevision={props.linkedScreeningRevision} liveRunId={props.runId} onClose={() => setScreeningPanelOpen(false)} />
      </div>
    </Show>
    <section class="graph-workspace" classList={{ "inspector-open": inspectorOpen() }}>
      <section class="lens-canvas-region">
        <div class="lens-canvas-tools">
          <button type="button" class="graph-fit-view" onClick={() => controls()?.fit()}>{t("适配画布", "Fit canvas")}</button>
          <button type="button" aria-label={t("放大", "Zoom in")} onClick={() => controls()?.zoomIn()}>+</button>
          <button type="button" aria-label={t("缩小", "Zoom out")} onClick={() => controls()?.zoomOut()}>−</button>
        </div>
        <LiteratureGraphCanvas theme={() => props.theme} nodes={visibleNodes} edges={visibleEdges} selectedNodeId={selectedNodeId} selectedEdge={selectedEdge}
          onSelectNode={selectNode} onSelectEdge={selectEdge} onReady={setControls} paperStates={paperStates} />
        <div class="paper-workflow-legend" aria-label={t("论文工作流状态图例", "Paper workflow state legend")}>
          <Show when={legendStates().length}><small>{t("论文处理状态", "Paper status")}</small></Show>
          <For each={legendStates()}>{state =>
            <span class={`state-${state}`}><i aria-hidden="true" />{paperStateLabel(state)} <b>{paperStateCounts()[state]}</b></span>
          }</For>
        </div>
        <p class="lens-footnote">{graphFootnote({ locale: props.locale, hasCitationMap: hasCitationMap(), bibliographyCount: bibliographyCount(),
          paperLikeNodeCount: paperCount(), reviewablePaperCount: visibleReviewablePaperCount(), visibleEdgeCount: visibleEdges().length })}</p>
      </section>
      <Show when={inspectorOpen()}><aside class="evidence-inspector" ref={focusLinkedInspector} tabIndex={-1} aria-label={t("图谱检查器", "Map inspector")}>
        <Show when={lastVisited()}>{prior => <button type="button" class="graph-back-node" onClick={backToNode}>{t("返回上一节点", "Back to previous node")} · {graphDisplayLabel(prior())}</button>}</Show>
        <Show when={query().trim()}><button type="button" class="graph-search-return" onClick={() => searchInput?.focus()}>{t("返回检索结果", "Back to search results")}</button></Show><Show when={selectedNode()} fallback={<Show when={selectedEdge()} fallback={<><small>{t("检查器", "INSPECTOR")}</small><h2>{t("选择论文或关系", "Select a paper or relation")}</h2><p>{t("选中画布上的节点或关系即可查看来源。", "Select a node or link on the map to inspect its source.")}</p></>}>{(edge) => <><small>{t("关系", "RELATION")}</small><h2>{edge().edgeType.replaceAll("_", " ")}</h2><p>{edge().relationSource}</p><dl><div><dt>{t("起点", "Source")}</dt><dd><button class="graph-edge-endpoint" type="button" onClick={() => { const node = nodesById().get(edge().sourceId); if (node) followConnection(node); }}>{nodeLabel(edge().sourceId)}</button></dd></div><div><dt>{t("终点", "Target")}</dt><dd><button class="graph-edge-endpoint" type="button" onClick={() => { const node = nodesById().get(edge().targetId); if (node) followConnection(node); }}>{nodeLabel(edge().targetId)}</button></dd></div></dl></>}</Show>}>{(node) => <><small class="graph-record-kind" title={node().kind}>{nodeKindLabel(node().kind)}</small><h2>{graphDisplayLabel(node())}</h2><p class="graph-record-status">{trustLabel(node().trustStatus)}</p>
        <Show when={selectedCard()}>{card => <ActionButton size="sm" onClick={() => openEvidence(card())}>{t("在原文核对", "Verify in source")} · {card().provenance.locator}</ActionButton>}</Show>
        <Show when={props.runId && !props.readOnlyPreview && paperDocumentId(node())}>{id =>
          <div class="graph-paper-actions">
            <ActionButton size="sm" onClick={() => setDisplay({ documentId: id(), title: node().label })}>{t("核验这篇论文", "Verify this paper")}</ActionButton>
            <Show when={selectedPaperMapLink()}>{href => <a href={href()} target="_blank" rel="noopener" title={t("在新标签页打开这篇论文的星图位置", "Open this paper on the map in a new tab")}>{t("本篇星图链接", "Paper map link")} <span aria-hidden="true">↗</span></a>}</Show>
          </div>
        }</Show>
        <Show when={node().nodeId} keyed>{id => <GraphConnections nodeId={id} nodes={nodesById()} edges={graph().edges} locale={props.locale} onFollow={followConnection} />}</Show>
        <Show when={node().kind === "citation_work"}><p class="bibliography-boundary">{t("该节点是公开书目导航条目；请获得并核对原文后，才能建立来源定位或 EvidenceCard。", "This node is a public bibliography-navigation record. Obtain and verify the original text before creating a source location or EvidenceCard.")}</p></Show><Show when={isPaperNode(node()) && !paperDocumentId(node())}><p class="bibliography-boundary">{t("该对象保留题名或书目导航信息，但没有当前任务可审核的 document ID；不能绑定授权 PDF、来源定位或 EvidenceCard。", "This object retains title or bibliography-navigation metadata but has no reviewable document ID for the current mission; it cannot bind an authorised PDF, source location, or EvidenceCard.")}</p></Show><Show when={node().kind === "condition_cluster"}><section class="condition-cluster-inspector"><small>{t("条件比较工件", "CONDITION COMPARISON ARTIFACT")}</small><p>{t("该簇由已接受 EvidenceCard 的可比条件推导；支持与矛盾关系用于定位下一轮原文核对，不构成材料科学结论。", "This cluster is derived from comparable conditions on accepted EvidenceCards. Support and contradiction links guide the next source review; they are not a materials-science conclusion.")}</p><Show when={conditionEvidence().length} fallback={<p>{t("该条件簇尚未保留可展示的已接受证据连接。请回到阅读页核对来源定位与人工审核状态。", "This cluster has no displayable accepted-evidence links. Return to the reader to check source locations and human-review status.")}</p>}><For each={conditionEvidence()}>{(link) => <button type="button" classList={{ contradiction: link.relation === "contradiction" }} onClick={() => openEvidence(link.evidence)}><strong>{link.relation === "support" ? t("支持条件", "Supports condition") : t("矛盾条件", "Contradicts condition")}</strong><span>{link.evidence.evidenceId} · {link.evidence.provenance.documentId} · {link.evidence.provenance.locator}</span></button>}</For></Show></section></Show><dl class="graph-record-meta"><Show when={node().source}><div><dt>{t("元数据来源", "Metadata source")}</dt><dd>{node().source}</dd></div></Show><Show when={selectedDoi()}>{doi => <div><dt>DOI</dt><dd>{doi()}</dd></div>}</Show><Show when={node().publicationYear}><div><dt>{t("发表年份", "Publication year")}</dt><dd>{node().publicationYear}</dd></div></Show></dl><Show when={Boolean(paperDocumentId(node()))}><section class="evidence-handoff"><small>{linkedEvidence().length ? t("下一受控动作：核对已接受证据", "NEXT CONTROLLED ACTION: VERIFY ACCEPTED EVIDENCE") : hasInspectedSavedParse() ? t("已登记来源解析", "SAVED SOURCE PARSE") : paperPdf().state === "source-map" ? t("下一受控动作：登记来源定位", "NEXT CONTROLLED ACTION: REGISTER SOURCE LOCATIONS") : paperPdf().state === "evidence-review" ? t("下一受控动作：审核材料事实与 EvidenceCard", "NEXT CONTROLLED ACTION: REVIEW FACTS AND EVIDENCECARD") : paperPdf().state === "failed" ? t("下一受控动作：重新选择授权 PDF", "NEXT CONTROLLED ACTION: RETRY AUTHORIZED PDF") : paperPdf().state === "parsing" ? t("下一受控动作：等待私有解析", "NEXT CONTROLLED ACTION: WAIT FOR PRIVATE PARSING") : t("下一受控动作：建立来源关联", "NEXT CONTROLLED ACTION: ESTABLISH SOURCE LINK")}</small>
  <Show when={linkedEvidence().length}><><p>{t("当前论文已有显式来源映射的已接受 EvidenceCard。进入阅读页核对定位符和条件字段；书目关系本身不构成材料事实。", "This paper already has an accepted EvidenceCard with an explicit source-map link. Open the reader to verify its locator and conditions; bibliography alone is not a material fact.")}</p><ActionButton variant="primary" onClick={() => openReaderForPaper(node())}>{t("在阅读页核对来源", "Verify source in reader")}</ActionButton></></Show>
  <Show when={!linkedEvidence().length && hasInspectedSavedParse()}>
    <Show when={inspectedPdfAction() === "recorded_reader" && screeningDecision() === "include_for_fulltext"} fallback={<>
      <Show when={inspectedPdfAction() === "recorded_done" && screeningDecision() === "include_for_fulltext" && inspectedSource()?.can_link_markdown && linkSourceMarkdown()} fallback={
        <p>{inspectedPdfAction() === "recorded_active"
          ? t("DSH 轮询后可刷新进度。", "Refresh after polling through DSH.")
          : screeningDecision() !== "include_for_fulltext"
          ? t("请先完成当前候选的人工筛选。", "Complete human screening for this candidate first.")
          : t("来源解析已完成。请在终端取回 Markdown，再刷新解析记录。", "Source parsing is complete. Retrieve Markdown in the terminal, then refresh the parse record.")}</p>
      }>{(link) => <Show when={inspectedSource()?.document_id} keyed>{(documentId) =>
        <><p>{t("可关联之前取回的 Markdown 原文件。", "You can link the original saved Markdown file.")}</p>
          <SourceMarkdownLinkButton locale={props.locale} paperTitle={node().label} onLink={(file) => link()(documentId, file)} /></>
      }</Show>}</Show>
      <Show when={props.onRefreshSourceParses}><ActionButton size="sm" busy={props.sourceHealth === "loading"} busyLabel={t("正在读取…", "Reading…")} onClick={() => props.onRefreshSourceParses?.()}>{t("刷新该篇记录", "Refresh this record")}</ActionButton></Show>
    </>}>
      <p>{t("本机 Markdown 已与这篇论文关联，可进入阅读页核对原文和来源定位。", "Local Markdown is linked to this paper. Open the reader to verify its text and source locations.")}</p>
      <ActionButton variant="primary" onClick={() => openReaderForPaper(node())}>{t("进入阅读页核对来源", "Open reader to verify source")}</ActionButton>
    </Show>
  </Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "source-map"}><><p>{t("该论文的授权 PDF 已解析完成并已绑定当前候选。请进入阅读页，在本机 Markdown 中人工登记最小必要的来源定位。", "The authorized PDF for this paper is parsed and bound to the current candidate. Open the reader and register the minimum necessary source locations from local Markdown by human review.")}</p><ActionButton variant="primary" onClick={() => openReaderForPaper(node())}>{t("进入阅读页登记来源", "Open reader to register source")}</ActionButton></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "evidence-review"}><><p>{t("该论文已登记来源定位。请进入阅读页登记结构化材料事实，并在六项条件完整后人工接受 EvidenceCard。", "This paper already has recorded source locations. Open the reader and register structured material facts and, when all six conditions are complete, accept an EvidenceCard by human review.")}</p><ActionButton variant="primary" onClick={() => openReaderForPaper(node())}>{t("进入阅读页继续审核", "Open reader to continue review")}</ActionButton></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "parsing"}><><p>{t("该论文的授权 PDF 已绑定，但私有解析尚未完成。请返回舰桥查看 MinerU 状态；解析完成前不会显示 Markdown、来源定位或 EvidenceCard。", "An authorized PDF is attached to this paper, but private parsing is not complete. Return to the bridge to inspect MinerU status; Markdown, source locations, and EvidenceCards stay unavailable until completion.")}</p><ActionButton variant="primary" onClick={() => props.onNavigate("workflow")}>{t("返回舰桥查看解析状态", "Return to bridge for parsing status")}</ActionButton></></Show>  <Show when={!linkedEvidence().length && !hasInspectedSavedParse() && paperPdf().state === "failed"}><><p>{t("该论文此前关联的私有 PDF 解析失败。人工筛选记录仍然有效；请重新选择你有权处理的对应 PDF，系统不会把失败任务当作来源定位或证据。", "The previously attached private PDF for this paper failed to parse. The human screening record remains valid; choose the corresponding PDF you are authorized to process again. A failed task is never treated as a source location or evidence.")}</p><Show when={screeningCandidate()}>{(candidate) => <Show when={props.onRequestFulltext}><ActionButton variant="primary" onClick={() => props.onRequestFulltext?.(candidate())}>{t("重新选择授权 PDF", "Choose authorized PDF again")}</ActionButton></Show>}</Show><ActionButton size="sm" variant="secondary" onClick={() => props.onNavigate("workflow")}>{t("查看失败原因", "View failure reason")}</ActionButton></></Show>
  <Show when={!linkedEvidence().length && !hasInspectedSavedParse() && paperPdf().state === "none"}><Show when={screeningCandidate()} fallback={<><p>{t("此论文尚未进入当前任务的人工筛选清单，不能申请全文处理或接受 EvidenceCard。", "This paper is not in the current task’s human screening list; full-text processing and EvidenceCard acceptance are unavailable.")}</p><Show when={props.onLoadScreening}><ActionButton variant="primary" onClick={() => openScreening(paperDocumentId(node()) ?? null)}>{t("打开候选人工筛选", "Open candidate screening")}</ActionButton></Show></>}>{(candidate) => <><p>{screeningDecision() === "include_for_fulltext" ? t("该候选已被人工纳入全文核对，但尚未绑定对应的授权 PDF。下一步请选择你有权处理的 PDF。", "This candidate is human-included for full-text review but has no matching authorized PDF attached. Next choose a PDF you are authorized to process.") : screeningDecision() === "exclude" ? t("该候选已被人工排除，不能进入全文处理。若需调整，请在筛选清单中提交新的完整决定。", "This candidate is human-excluded and cannot enter full-text processing. Submit a revised complete decision in the screening checklist to change this.") : screeningDecision() === "needs_metadata_review" ? t("该候选仍需补充或核验书目信息，暂不能请求全文。", "This candidate still needs bibliographic metadata review and cannot request full text yet.") : t("此候选尚未完成人工筛选；请先记录决定与理由。", "This candidate has not completed human screening; record a decision and reason first.")}</p><Show when={screeningDecision() === "include_for_fulltext" && props.onRequestFulltext}><ActionButton variant="primary" onClick={() => props.onRequestFulltext?.(candidate())}>{t("选择授权 PDF", "Choose authorized PDF")}</ActionButton></Show><Show when={screeningDecision() !== "include_for_fulltext" && props.onLoadScreening}><ActionButton variant="primary" onClick={() => openScreening(candidate().document_id)}>{t("查看或修改人工筛选", "View or revise screening")}</ActionButton></Show></>}</Show></Show>
</section></Show><Show when={Boolean(paperDocumentId(node())) && linkedEvidence().length > 0}><section class="imported-evidence-list"><small>{t("与当前论文显式关联的已接受证据", "ACCEPTED EVIDENCE LINKED TO THIS PAPER")}</small><p>{t("打开证据卡，查看这篇论文中已核对的原文定位。", "Open a card to inspect its verified source location in this paper.")}</p><For each={linkedEvidence()}>{(evidence) => <button type="button" onClick={() => openEvidence(evidence)}><strong>{evidence.evidenceId}</strong><span>{evidence.provenance.documentId} · {evidence.provenance.locator}</span></button>}</For></section></Show></>}</Show></aside></Show></section>
    </Show>
    <Show when={hasNavigableMap() && screeningActionRequired() && !screeningPanelOpen()}><section class="graph-screening-cue" aria-live="polite"><div><small>{t("当前首要动作", "CURRENT PRIMARY ACTION")}</small><strong>{props.screening ? t("先完成候选文献的人审筛选", "Complete human screening of candidate literature first") : t("载入候选文献人工筛选清单", "Load the human screening checklist")}</strong><p>{props.screening ? t(`已返回 ${props.screening.candidate_count} 篇元数据候选。请逐篇记录纳入、排除或补元数据的理由；这一步不会下载全文或生成 EvidenceCard。`, `${props.screening.candidate_count} metadata candidates have returned. Record an include, exclude, or metadata-review reason for each; this does not download full text or create an EvidenceCard.`) : t("图谱中已有候选论文，但人工筛选清单尚未载入。载入后请逐篇记录决定与理由；这一步不会下载全文或生成 EvidenceCard。", "Candidate papers are present in the map, but the human screening checklist is not loaded. After loading it, record one decision and reason per paper; this does not download full text or create an EvidenceCard.")}</p></div><ActionButton variant="primary" onClick={() => openScreening()}>{props.screening ? t("开始人工筛选", "Start human screening") : t("载入筛选清单", "Load screening checklist")}</ActionButton></section></Show>
    <section class="fleet-map-command" aria-label={t("星区指挥台", "Sector command deck")}><div class="fleet-command-call"><small>{t("星区指挥台", "SECTOR COMMAND DECK")}</small><strong>{props.bundle.mission.material} / {props.bundle.mission.property}</strong><span>{props.bundle.mission.scope}</span></div><div class="fleet-command-telemetry"><div><small>{t("星图节点", "STAR MAP NODES")}</small><strong>{graph().nodes.length}</strong></div><div><small>{t("已显现航线", "VISIBLE VECTORS")}</small><strong>{visibleEdges().length}</strong></div><div><small>{t("纸面候选", "PAPER CANDIDATES")}</small><strong>{reviewablePaperCount()}</strong></div></div><div class="fleet-command-boundary"><small>{t("审计协议", "AUDIT PROTOCOL")}</small><p>{t("航线只是当前工件之间的导航投影；只有来源定位和人工接受的 EvidenceCard 才能跨越证据门。", "Vectors are navigation projections between current artifacts; only source locations and human-accepted EvidenceCards cross the evidence gate.")}</p></div></section>
    <Show when={props.bundle.candidateDuplicateQueue}>{(queue) => <CandidateDuplicateReconciliationPanel queue={queue()} reconciliation={props.bundle.candidateDuplicateReconciliation} graph={props.bundle.literatureGraph} locale={props.locale} />}</Show>
    <Show when={props.bundle.relationReconciliation}>{(reconciliation) => <RelationReconciliationPanel reconciliation={reconciliation()} locale={props.locale} />}</Show>
    <Show when={props.runId} keyed>{runId => <EvidenceGraphExplorer runId={runId} missionId={props.bundle.mission.missionId} locale={props.locale} />}</Show>
    <Show when={hasReviewablePapers()}><section class="graph-route-status" aria-label={t("文献证据闭环状态", "Literature evidence-loop status")}>
      <div><small>{t("候选元数据", "METADATA CANDIDATES")}</small><strong>{reviewablePaperCount()}</strong><span>{t("仅供人工筛选，不是科学证据", "For human screening only; not scientific evidence")}</span></div>
      <i aria-hidden="true">→</i>
      <div classList={{ "route-pending": screeningProgress().state !== "completed" }}><small>{t("人工筛选", "HUMAN SCREENING")}</small><strong>{screeningProgressLabel()}</strong><span>{t("每篇均需决定与理由", "Each paper needs a decision and reason")}</span></div>
      <i aria-hidden="true">→</i>
<div classList={{ "route-ready": acceptedEvidenceCount() > 0 && acceptedEvidenceProvenanceAudited() }}><small>{t("已接受 EvidenceCard", "ACCEPTED EVIDENCECARD")}</small><strong>{acceptedEvidenceCount()}</strong><span>{acceptedEvidenceCount() ? acceptedEvidenceProvenanceAudited() ? t("已具有来源定位、人工审核和精确审计", "Source-located, human-reviewed, and exactly audited") : t("卡片已接受，仍待精确来源审计", "Cards are accepted but exact provenance audit remains pending") : t("全文与来源定位核对后才可建立", "Created only after full-text and provenance review")}</span></div>
    </section></Show>
    <Show when={hasReviewablePapers()}><section class="fleet-reading-route" aria-label={t("舰队阅读航道", "Fleet reading route")}>
      <header><div><small>{t("前沿编队", "FRONTIER FORMATION")}</small><h2>{t("舰队阅读顺序", "Fleet reading order")}</h2><p>{props.bundle.researchGuide ? t("舰位先按已登记的审核动作排序，同一动作内采用后端审核路线的三轨次序。三轨来自题名与任务边界的确定性元数据规则，不是相关性判断、性质预测或科学结论；仅反证条目不会被当作主证据。", "Formation slots are ordered first by registered review action, then follow the backend review guide's three-track order within each action. Tracks are deterministic title-and-mission metadata rules—not relevance judgments, property predictions, or scientific conclusions; counter-only records cannot become primary evidence.") : t("尚无经过校验的后端阅读路线；当前仅用任务材料与研究维度的本地题名锚点打破同一审核动作内的平局。锚点不是模型或供应商评分，也不代表科学相关性。", "No validated backend reading guide is available. Local task-title anchors only break ties within equal review actions; they are not model/provider scores or scientific relevance.")}</p></div><span>{routePolicySummary()} · {t(`星图 ${graph().nodes.length} 节点 / ${graph().edges.length} 关系`, `map ${graph().nodes.length} nodes / ${graph().edges.length} links`)}</span></header>
      <Show when={routeShortfallSummary()}>{(summary) => <p class="route-shortfall-warning" role="status">{summary()}</p>}</Show>
      <div class="fleet-reading-cards"><For each={routePapers()}>{(entry) => <button type="button" class={`fleet-formation-slot state-${entry.workflowState}`} classList={{ selected: selectedNodeId() === entry.nodeId }} onClick={() => { selectNode(entry.nodeId); focusInspector(); }}><small>{t(`航线 ${String(entry.ordinal).padStart(2, "0")}`, `ROUTE ${String(entry.ordinal).padStart(2, "0")}`)}</small><strong>{displayPaperTitle(entry.title)}</strong><span>{entry.documentId}</span><Show when={entry.researchTrack} fallback={<i class={`route-anchor route-anchor-${entry.titleAnchorMatch}`}>{titleAnchorLabel(entry.titleAnchorMatch)}</i>}>{(track) => <i class={`route-track route-track-${track()}`}>{researchTrackLabel(track(), entry.routeEligibility === "counterevidence_only")}</i>}</Show><em class={`route-state-${entry.workflowState}`}>{paperStateLabel(entry.workflowState)}</em><b>{routeActionLabel(entry.action)}</b></button>}</For></div>
      <aside class="fleet-relation-beacon" aria-label={t("关系航标", "Relation beacon")}><div><small>{t("关系航标", "RELATION BEACON")}</small><p>{t("下列计数来自当前图谱；书目连接、题名建议与来源溯源是不同类型的工件关系。点击可切换对应关系层，仅影响当前画布显示。", "Counts below come from the current graph; bibliography links, title suggestions, and source provenance are distinct artifact relations. Select a beacon to toggle its visible relationship layer on this canvas only.")}</p></div><nav aria-label={t("关系层开关", "Relationship layer toggles")}><button type="button" classList={{ active: edgeVisibility().discovery }} onClick={() => setEdgeVisibility((current) => ({ ...current, discovery: !current.discovery }))}><span>{t("候选路线", "Candidate routes")}</span><strong>{relationCounts().discovery}</strong></button><button type="button" classList={{ active: edgeVisibility().evidence }} onClick={() => setEdgeVisibility((current) => ({ ...current, evidence: !current.evidence }))}><span>{t("来源溯源", "Source provenance")}</span><strong>{relationCounts().evidence}</strong></button><button type="button" classList={{ active: edgeVisibility().conditions }} onClick={() => setEdgeVisibility((current) => ({ ...current, conditions: !current.conditions }))}><span>{t("条件关系", "Condition links")}</span><strong>{relationCounts().conditions}</strong></button><button type="button" classList={{ active: edgeVisibility().bibliography }} onClick={() => { const shouldShowReferences = !edgeVisibility().bibliography; setEdgeVisibility((current) => ({ ...current, bibliography: !current.bibliography })); if (shouldShowReferences) setNodeVisibility((current) => ({ ...current, references: true })); }}><span>{t("书目引文", "Bibliographic citations")}</span><strong>{relationCounts().bibliography}</strong></button><button type="button" classList={{ active: edgeVisibility().related }} onClick={() => setEdgeVisibility((current) => ({ ...current, related: !current.related }))}><span>{t("题名建议", "Title suggestions")}</span><strong>{relationCounts().related}</strong></button></nav></aside>
    </section></Show>
    <Show when={hasNavigableMap()}>
    <Show when={props.onRequestFulltext && props.onRefreshSourceParses}>
      <CandidateFulltextQueue locale={props.locale} screening={props.screening} nodes={graph().nodes}
        pdfTasks={props.pdfTasks ?? []} sourceTasks={props.sourceTasks ?? []} sourceHealth={props.sourceHealth ?? "idle"}
        refresh={props.onRefreshSourceParses!} choosePdf={props.onRequestFulltext!} openReader={openReaderForPaper} linkMarkdown={linkSourceMarkdown()}
        openBridge={(paper) => { if (props.onSelectPaper(paper)) props.onNavigate("workflow"); }} />
    </Show>
    </Show>
    <footer class="stage-note">{t("论文选择、EvidenceCard 选择和来源定位是独立的审计事实；缺失关联必须显式显示。", "Paper selection, EvidenceCard selection, and source location are separate audit facts; missing linkage is shown explicitly.")}</footer>
    </Show>
  </main>;
}
