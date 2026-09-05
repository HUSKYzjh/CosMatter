import { ErrorBoundary, For, Show, Suspense, createEffect, createMemo, createSignal, lazy } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { CandidateScreeningPanel } from "./CandidateScreeningPanel";
import { EvidenceGraphExplorer } from "./EvidenceGraphExplorer";
import { fleetVisualState } from "./fleetVisualState";
import type { GraphCanvasControls, LiteratureGraphCanvasProps } from "./LiteratureGraphCanvas";
import { TOPIC_KEYS, isPaperNode, topicFor, type TopicKey } from "./literatureTopology";
import { literatureGraphMode } from "./literatureGraphMode";
import { auditableAcceptedEvidence, documentIdForReviewablePaper, evidenceForPaper } from "./evidenceLinking";
import { graphEdgeStillExists, graphSelectionVisibility } from "./graphSelectionState";
import { graphNodeForSessionDocument } from "./graphSessionSelection";
import { readerRouteAfterCommittedSelection } from "./graphReaderHandoff";
import { paperPdfIntake, pdfTaskForPaper } from "./paperPdfIntake";
import { paperWorkflowState, type PaperWorkflowState } from "./paperWorkflowState";
import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";
import { shouldPromptForScreening } from "./screeningActionState";
import { candidateScreeningProgress } from "./candidateScreeningProgress";
import { graphFootnote } from "./graphFootnote";
import { readingRoute, type ReadingRouteAction } from "./readingRoute";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import { RelationReconciliationPanel } from "./RelationReconciliationPanel";
import type { EvidenceCard, ImportedBundle, LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import type { CandidateScreening, CandidateScreeningCandidate, CandidateScreeningDecision, PdfTaskStatus } from "./localApi";
import "./frontier-graph.css";

type NodeGroup = "mission" | "papers" | "evidence" | "conditions" | "references" | "structure";
type EdgeGroup = "discovery" | "evidence" | "conditions" | "bibliography" | "related" | "structure";
type NavigateView = "discover" | "workflow" | "reader" | "horizon";
const RawLiteratureGraphCanvas = lazy(() => import("./LiteratureGraphCanvas").then((module) => ({ default: module.LiteratureGraphCanvas })));
function LiteratureGraphCanvas(props: LiteratureGraphCanvasProps) {
  return <Show when={props.nodes().length} fallback={<section class="graph-canvas-loading" role="status"><small>NO VISIBLE GRAPH ELEMENTS</small><p>当前筛选没有可绘制节点；调整搜索或显示范围后，交互式图谱引擎才会加载。</p></section>}><ErrorBoundary fallback={(_error, reset) => <section class="graph-canvas-fallback" role="status"><small>INTERACTIVE GRAPH UNAVAILABLE</small><strong>交互式图谱暂不可用 / Interactive graph unavailable</strong><p>筛选和审计信息保持不变；未读取私有全文、未调用提供方，也未修改任务。</p><button type="button" onClick={reset}>重试载入画布 / Retry canvas</button></section>}><Suspense fallback={<section class="graph-canvas-loading" role="status"><small>LOADING INTERACTIVE GRAPH</small><p>图谱引擎仅在此工作区加载；当前不会读取私有全文或调用提供方。</p></section>}><RawLiteratureGraphCanvas {...props} /></Suspense></ErrorBoundary></Show>;
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
  if (["accepted_evidence", "research_gap_candidate"].includes(node.kind)) return "evidence";
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

export function GraphNetwork(props: { bundle: ImportedBundle; theme: string; locale: "zh" | "en"; runId?: string | null; selectedDocumentId?: string | null; pdfTask: PdfTaskStatus | null; pdfTasks?: PdfTaskStatus[]; screening: CandidateScreening | null; onLoadScreening?: () => Promise<void>; onSubmitScreening?: (decisions: CandidateScreeningDecision[]) => Promise<void>; onRequestFulltext?: (candidate: CandidateScreeningCandidate) => void; readOnlyPreview?: boolean; onExitPreview?: () => void; onNavigate: (view: NavigateView) => void; onSelectPaper: (node: LiteratureGraphNode) => boolean; onSelectEvidence: (evidence: EvidenceCard) => boolean }) {
  const [query, setQuery] = createSignal("");
  const [selectedTopic, setSelectedTopic] = createSignal<TopicKey | "all">("all");
  const [advanced, setAdvanced] = createSignal(false);
  const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
  const [selectedEdge, setSelectedEdge] = createSignal<LiteratureGraphEdge | null>(null);
  const [focusSelection, setFocusSelection] = createSignal(false);
  // The graph remains the primary reading surface. Details appear only after a researcher asks for them or selects an object.
  const [inspectorOpen, setInspectorOpen] = createSignal(false);
  const [controls, setControls] = createSignal<GraphCanvasControls | null>(null);
  const [nodeVisibility, setNodeVisibility] = createSignal<Record<NodeGroup, boolean>>({ mission: true, papers: true, evidence: true, conditions: true, references: false, structure: false });
  const [edgeVisibility, setEdgeVisibility] = createSignal<Record<EdgeGroup, boolean>>({ discovery: true, evidence: true, conditions: true, bibliography: false, related: false, structure: false });
  const [citationAutoShown, setCitationAutoShown] = createSignal(false);
  const [sessionSelectionRestored, setSessionSelectionRestored] = createSignal(false);
  const [screeningFocusId, setScreeningFocusId] = createSignal<string | null>(null);
  const [screeningPanelOpen, setScreeningPanelOpen] = createSignal(false);
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const graph = () => props.bundle.literatureGraph;
  const visibleNodes = createMemo(() => {
    const term = query().trim().toLocaleLowerCase();
    const all = graph().nodes.filter((node) => nodeVisibility()[nodeGroup(node)] && (!isPaperNode(node) || selectedTopic() === "all" || topicFor(node) === selectedTopic()) && (!term || `${node.label} ${node.source ?? ""}`.toLocaleLowerCase().includes(term)));
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
  const linkedEvidence = createMemo(() => evidenceForPaper(props.bundle, selectedNode()));
  const conditionEvidence = createMemo(() => {
    const condition = selectedNode();
    if (!condition || condition.kind !== "condition_cluster") return [];
    const evidenceById = new Map(props.bundle.evidenceCards.map((card) => [card.evidenceId, card]));
    return graph().edges.flatMap((edge) => {
      if (edge.targetId !== condition.nodeId || !["condition_support", "condition_contradiction"].includes(edge.edgeType)) return [];
      const evidence = evidenceById.get(edge.sourceId.replace(/^evidence:/, ""));
      return evidence ? [{ evidence, relation: edge.edgeType === "condition_support" ? "support" : "contradiction" }] : [];
    });
  });
  const acceptedEvidenceCount = createMemo(() => auditableAcceptedEvidence(props.bundle).length);
  const acceptedEvidenceProvenanceAudited = createMemo(() => evidenceProvenanceAuditComplete(props.bundle.auditSummary.evidenceProvenance, props.bundle.evidenceCards.length));
  const paperStates = createMemo<Record<string, PaperWorkflowState>>(() => Object.fromEntries(
    graph().nodes.map((node) => {
      const documentId = documentIdForReviewablePaper(node);
      const decision = documentId ? props.screening?.decisions.find((item) => item.document_id === documentId)?.decision ?? "unreviewed" : null;
      const evidenceCount = evidenceForPaper(props.bundle, node).length;
      const state = paperWorkflowState(node, props.pdfTasks ?? (props.pdfTask ? [props.pdfTask] : []), decision, evidenceCount, acceptedEvidenceProvenanceAudited());
      return state ? [node.nodeId, state] : null;
    }).filter((entry): entry is [string, PaperWorkflowState] => entry !== null),
  ));
  const paperStateCounts = createMemo(() => Object.values(paperStates()).reduce<Record<PaperWorkflowState, number>>((counts, state) => ({ ...counts, [state]: (counts[state] ?? 0) + 1 }), { untracked: 0, screening: 0, included: 0, parsing: 0, source_map: 0, evidence_review: 0, provenance_audit: 0, accepted_evidence: 0, failed: 0, excluded: 0 }));
  const matchingPdfTask = createMemo(() => pdfTaskForPaper(props.pdfTasks ?? (props.pdfTask ? [props.pdfTask] : []), selectedNode()));
  const paperPdf = createMemo(() => paperPdfIntake(matchingPdfTask(), selectedNode()));
  const paperDocumentId = (node: LiteratureGraphNode | null): string | null => documentIdForReviewablePaper(node);
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
  }));
  const relationCounts = createMemo(() => graph().edges.reduce<Record<EdgeGroup, number>>((counts, edge) => ({ ...counts, [edgeGroup(edge)]: counts[edgeGroup(edge)] + 1 }), { discovery: 0, evidence: 0, conditions: 0, bibliography: 0, related: 0, structure: 0 }));
  const paperStateLabel = (state: PaperWorkflowState | undefined) => {
    const labels: Record<PaperWorkflowState, [string, string]> = {
      untracked: ["未纳入当前审核路径", "not in the current review path"], screening: ["待人工筛选", "human screening pending"], included: ["已纳入全文核对", "included for full-text review"], parsing: ["私有解析中", "private parsing"], source_map: ["待登记来源定位", "source location pending"], evidence_review: ["待审核材料事实", "material-fact review pending"], provenance_audit: ["已接受卡片，待精确来源审计", "accepted card; exact provenance audit pending"], accepted_evidence: ["已关联接受证据", "accepted evidence linked"], failed: ["解析失败，待人工处理", "parsing failed; human action needed"], excluded: ["已人工排除", "human-excluded"],
    };
    return t(...(labels[state ?? "untracked"]));
  };
  const titleAnchorLabel = (match: "material-and-context" | "context" | "material" | "none") => ({
    "material-and-context": t("任务对象与维度双命中", "material + task-context title anchors"),
    material: t("仅对象命中 · 研究维度待核对", "material only · task context needs review"),
    context: t("仅维度命中 · 研究对象待核对", "task context only · material needs review"),
    none: t("题名未命中任务锚点 · 优先人工判读", "no task title anchor · review first"),
  }[match]);
  const routeActionLabel = (action: ReadingRouteAction) => ({
    "recover-pdf": t("恢复 PDF 解析", "recover PDF parsing"), "register-source-map": t("登记来源定位", "register source locations"),
    "review-evidence": t("审核材料事实与证据", "review facts and evidence"), "audit-provenance": t("完成精确来源审计", "complete exact provenance audit"),
    "verify-evidence": t("核对已接受证据", "verify accepted evidence"), "select-pdf": t("选择授权 PDF", "select an authorized PDF"),
    "screen-paper": t("完成人工筛选", "complete human screening"), "load-screening": t("载入人工筛选清单", "load the human checklist"),
    "wait-for-parse": t("等待私有解析", "wait for private parsing"),
  } satisfies Record<ReadingRouteAction, string>)[action];
  const screeningActionRequired = createMemo(() => shouldPromptForScreening(hasReviewablePapers(), Boolean(props.onLoadScreening && props.onSubmitScreening), props.screening));
  const firstUnreviewedCandidateId = createMemo(() => props.screening?.candidates.find((candidate) => (props.screening?.decisions.find((decision) => decision.document_id === candidate.document_id)?.decision ?? "unreviewed") === "unreviewed")?.document_id ?? null);
  const hasPersistedScreening = createMemo(() => props.screening?.trust_status === "human_reviewed_candidate_screening_not_scientific_evidence");
  const includedScreeningIds = createMemo(() => new Set((props.screening?.decisions ?? []).filter((decision) => decision.decision === "include_for_fulltext").map((decision) => decision.document_id)));
  const firstIncludedPaper = createMemo(() => !hasPersistedScreening() ? null : graph().nodes.find((node) => isPaperNode(node) && Boolean(paperDocumentId(node)) && includedScreeningIds().has(paperDocumentId(node)!)) ?? null);
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
      }
      setSessionSelectionRestored(true);
    }
  });
  createEffect(() => {
    if (selectedNodeId() && !selectionState().exists) { setSelectedNodeId(null); setFocusSelection(false); }
    if (!graphEdgeStillExists(selectedEdge(), graph().edges)) setSelectedEdge(null);
  });
  const topicLabel = (topic: TopicKey) => ({ ferroelectric: t("铁电性", "Ferroelectricity"), piezoelectric: t("压电性", "Piezoelectricity"), thin_film: t("薄膜与界面", "Thin films & interfaces"), domain_microstructure: t("畴与微观结构", "Domains & microstructure"), simulation_method: t("模拟与方法", "Simulation & methods"), other: t("其他题名元数据", "Other title metadata") } satisfies Record<TopicKey, string>)[topic];
  const selectNode = (id: string) => { const node = graph().nodes.find((item) => item.nodeId === id) ?? null; setSelectedNodeId(node?.nodeId ?? null); setSelectedEdge(null); if (node) setInspectorOpen(true); if (node && documentIdForReviewablePaper(node)) props.onSelectPaper(node); };
  const openReaderForPaper = (paper: LiteratureGraphNode) => {
    const target = readerRouteAfterCommittedSelection(props.onSelectPaper(paper));
    if (target) props.onNavigate(target);
  };
  const selectEdge = (edge: LiteratureGraphEdge) => { setSelectedEdge(edge); setSelectedNodeId(null); setInspectorOpen(true); };
  const revealSelectedPaper = () => {
    setQuery("");
    setSelectedTopic("all");
    setNodeVisibility((current) => ({ ...current, papers: true }));
    setFocusSelection(false);
  };

  return <main class="frontier-literature-workbench">
    <FleetDecoration kind="graph" state={fleetVisualState(props.bundle, "graph")} />
    <header class="stage-header graph-header"><div><p class="stage-kicker">COSMATTER / {hasCitationMap() && !hasReviewablePapers() ? t("书目引文导航", "BIBLIOGRAPHY NAVIGATION") : t("文献星图", "LITERATURE MAP")}</p><h1>{hasCitationMap() && !hasReviewablePapers() ? t("浏览引文关系，再选择待核对原文", "Browse citation relations, then choose original text to verify") : t("选择文献，再核对来源", "Select literature, then verify provenance")}</h1><p>{hasCitationMap() && !hasReviewablePapers() ? t("此图来自 DOI 的双向引文扩展，只表示公开书目信息；它不能替代原文、材料事实或 EvidenceCard。", "This map comes from bidirectional DOI citation expansion and shows public bibliographic metadata only; it cannot replace source text, materials facts, or EvidenceCards.") : t("图谱只展示候选、已接受证据和条件关系；题名相似或书目连接不是材料事实。", "The map shows candidates, accepted evidence, and condition relations; title similarity and bibliography are not material facts.")}</p></div></header>
    <Show when={props.readOnlyPreview}><ReadOnlyPreviewContext locale={props.locale} onExit={props.onExitPreview} /></Show>
    <section class="fleet-map-command" aria-label={t("星区指挥台", "Sector command deck")}><div class="fleet-command-call"><small>{t("星区指挥台", "SECTOR COMMAND DECK")}</small><strong>{props.bundle.mission.material} / {props.bundle.mission.property}</strong><span>{props.bundle.mission.scope}</span></div><div class="fleet-command-telemetry"><div><small>{t("星图节点", "STAR MAP NODES")}</small><strong>{graph().nodes.length}</strong></div><div><small>{t("已显现航线", "VISIBLE VECTORS")}</small><strong>{visibleEdges().length}</strong></div><div><small>{t("纸面候选", "PAPER CANDIDATES")}</small><strong>{reviewablePaperCount()}</strong></div></div><div class="fleet-command-boundary"><small>{t("审计协议", "AUDIT PROTOCOL")}</small><p>{t("航线只是当前工件之间的导航投影；只有来源定位和人工接受的 EvidenceCard 才能跨越证据门。", "Vectors are navigation projections between current artifacts; only source locations and human-accepted EvidenceCards cross the evidence gate.")}</p></div></section>
    <Show when={props.bundle.relationReconciliation}>{(reconciliation) => <RelationReconciliationPanel reconciliation={reconciliation()} locale={props.locale} />}</Show>
    <Show when={props.runId}>{(runId) => <EvidenceGraphExplorer runId={runId()} locale={props.locale} />}</Show>
    <Show when={hasReviewablePapers()}><section class="graph-route-status" aria-label={t("文献证据闭环状态", "Literature evidence-loop status")}>
      <div><small>{t("候选元数据", "METADATA CANDIDATES")}</small><strong>{reviewablePaperCount()}</strong><span>{t("仅供人工筛选，不是科学证据", "For human screening only; not scientific evidence")}</span></div>
      <i aria-hidden="true">→</i>
      <div classList={{ "route-pending": screeningProgress().state !== "completed" }}><small>{t("人工筛选", "HUMAN SCREENING")}</small><strong>{screeningProgressLabel()}</strong><span>{t("每篇均需决定与理由", "Each paper needs a decision and reason")}</span></div>
      <i aria-hidden="true">→</i>
<div classList={{ "route-ready": acceptedEvidenceCount() > 0 && acceptedEvidenceProvenanceAudited() }}><small>{t("已接受 EvidenceCard", "ACCEPTED EVIDENCECARD")}</small><strong>{acceptedEvidenceCount()}</strong><span>{acceptedEvidenceCount() ? acceptedEvidenceProvenanceAudited() ? t("已具有来源定位、人工审核和精确审计", "Source-located, human-reviewed, and exactly audited") : t("卡片已接受，仍待精确来源审计", "Cards are accepted but exact provenance audit remains pending") : t("全文与来源定位核对后才可建立", "Created only after full-text and provenance review")}</span></div>
    </section></Show>
    <Show when={hasReviewablePapers()}><section class="fleet-reading-route" aria-label={t("舰队阅读航道", "Fleet reading route")}>
      <header><div><small>{t("前沿编队", "FRONTIER FORMATION")}</small><h2>{t("以编队舰位穿越候选星区", "Traverse candidate sectors in fleet formation")}</h2><p>{t("舰位先按已登记的审核动作排序，再以当前任务的材料与研究维度题名锚点分流。锚点是本地可解释提示，不是模型或供应商评分，也不代表科学相关性；未命中项仍保留供反例审查。", "Formation slots are ordered first by registered review action, then triaged by local title anchors from the mission material and research context. Anchors are explainable local hints—not model/provider scores or scientific relevance—and unanchored items remain available for counterexample review.")}</p></div><span>{t(`编队部署 ${routePapers().length}/${reviewablePaperCount()} 个可审查舰位 · 当前星图 ${graph().nodes.length} 节点 / ${graph().edges.length} 关系`, `formation deployed ${routePapers().length}/${reviewablePaperCount()} reviewable slots · current star map ${graph().nodes.length} nodes / ${graph().edges.length} links`)}</span></header>
      <div class="fleet-reading-cards"><For each={routePapers()}>{(entry) => <button type="button" class={`fleet-formation-slot state-${entry.workflowState}`} classList={{ selected: selectedNodeId() === entry.nodeId }} onClick={() => selectNode(entry.nodeId)}><small>{t(`航线 ${String(entry.ordinal).padStart(2, "0")}`, `ROUTE ${String(entry.ordinal).padStart(2, "0")}`)}</small><strong>{entry.title}</strong><span>{entry.documentId}</span><i class={`route-anchor route-anchor-${entry.titleAnchorMatch}`}>{titleAnchorLabel(entry.titleAnchorMatch)}</i><em class={`route-state-${entry.workflowState}`}>{paperStateLabel(entry.workflowState)}</em><b>{routeActionLabel(entry.action)}</b></button>}</For></div>
      <aside class="fleet-relation-beacon" aria-label={t("关系航标", "Relation beacon")}><div><small>{t("关系航标", "RELATION BEACON")}</small><p>{t("下列计数来自当前图谱；书目连接、题名建议与来源溯源是不同类型的工件关系。点击可切换对应关系层，仅影响当前画布显示。", "Counts below come from the current graph; bibliography links, title suggestions, and source provenance are distinct artifact relations. Select a beacon to toggle its visible relationship layer on this canvas only.")}</p></div><nav aria-label={t("关系层开关", "Relationship layer toggles")}><button type="button" classList={{ active: edgeVisibility().discovery }} onClick={() => setEdgeVisibility((current) => ({ ...current, discovery: !current.discovery }))}><span>{t("候选路线", "Candidate routes")}</span><strong>{relationCounts().discovery}</strong></button><button type="button" classList={{ active: edgeVisibility().evidence }} onClick={() => setEdgeVisibility((current) => ({ ...current, evidence: !current.evidence }))}><span>{t("来源溯源", "Source provenance")}</span><strong>{relationCounts().evidence}</strong></button><button type="button" classList={{ active: edgeVisibility().conditions }} onClick={() => setEdgeVisibility((current) => ({ ...current, conditions: !current.conditions }))}><span>{t("条件关系", "Condition links")}</span><strong>{relationCounts().conditions}</strong></button><button type="button" classList={{ active: edgeVisibility().bibliography }} onClick={() => { const shouldShowReferences = !edgeVisibility().bibliography; setEdgeVisibility((current) => ({ ...current, bibliography: !current.bibliography })); if (shouldShowReferences) setNodeVisibility((current) => ({ ...current, references: true })); }}><span>{t("书目引文", "Bibliographic citations")}</span><strong>{relationCounts().bibliography}</strong></button><button type="button" classList={{ active: edgeVisibility().related }} onClick={() => setEdgeVisibility((current) => ({ ...current, related: !current.related }))}><span>{t("题名建议", "Title suggestions")}</span><strong>{relationCounts().related}</strong></button></nav></aside>
    </section></Show>
    <Show when={hasNavigableMap()} fallback={<section class="graph-empty"><small>{t("文献星图待建立", "LITERATURE MAP PENDING")}</small><h2>{t("尚无可审查的文献或书目子图", "No reviewable literature or bibliography subgraph yet")}</h2><Show when={paperCount() > 0} fallback={<p>{t("当前任务只有边界标记，尚未导入或检索到论文元数据；书目关系、全文和 EvidenceCard 不会被自动虚构。", "The current task has only a boundary marker. No paper metadata has been imported or retrieved, and bibliography, full text, and EvidenceCards are never fabricated.")}</p>}><p>{t(`当前图谱含 ${paperCount()} 个仅供导航或演示的论文式节点；它们未形成任务可审核文献，不能用于筛选、全文处理或 EvidenceCard。`, `The map contains ${paperCount()} paper-like navigation or demo node(s). They have not formed reviewable literature for this mission and cannot enter screening, full-text work, or EvidenceCard review.`)}</p></Show><button type="button" class="primary-action" onClick={() => props.onNavigate("workflow")}>{t("返回舰桥查看工件状态", "Return to bridge and inspect artifact status")}</button></section>}>
    <section class="graph-controls" aria-label={t("图谱筛选", "Map filters")}><label>{t("检索", "Search")}<input value={query()} onInput={(event) => setQuery(event.currentTarget.value)} placeholder={t("题名或来源", "title or source")} /></label><Show when={hasReviewablePapers()}><label>{t("主题簇", "Topic cluster")}<select value={selectedTopic()} onChange={(event) => setSelectedTopic(event.currentTarget.value as TopicKey | "all")}><option value="all">{t("全部论文", "All papers")}</option><For each={TOPIC_KEYS}>{(topic) => <option value={topic}>{topicLabel(topic)}</option>}</For></select></label></Show><button type="button" classList={{ active: advanced() }} onClick={() => setAdvanced((value) => !value)}>{advanced() ? t("收起高级筛选", "Hide advanced filters") : t("高级筛选", "Advanced filters")}</button><button type="button" onClick={() => controls()?.fit()}>{t("适配画布", "Fit canvas")}</button><button type="button" disabled={!selectedNodeId()} classList={{ active: focusSelection() }} onClick={() => setFocusSelection((value) => !value)}>{t("聚焦选择", "Focus selection")}</button><button type="button" classList={{ active: inspectorOpen() }} aria-expanded={inspectorOpen()} onClick={() => setInspectorOpen((value) => !value)}>{inspectorOpen() ? t("收起检查器", "Hide inspector") : selectedNodeId() || selectedEdge() ? t("查看当前选择", "Inspect selection") : t("打开检查器", "Open inspector")}</button></section>
    <Show when={screeningActionRequired()} fallback={<Show when={firstIncludedPaper()}>{(paper) => <section class="graph-screening-cue graph-fulltext-cue" aria-live="polite"><div><small>{t("当前首要动作", "CURRENT PRIMARY ACTION")}</small><strong>{t("从已纳入候选开始受控全文核对", "Start controlled full-text review from an included candidate")}</strong><p>{t(`人工筛选已提交。先在星图聚焦“${paper().label}”，再显式选择你有权处理的对应 PDF；全文处理不会自动开始。`, `Human screening is submitted. Focus “${paper().label}” in the map, then explicitly choose the corresponding PDF you are authorised to process; full-text work never starts automatically.`)}</p></div><button type="button" class="primary-action" onClick={() => selectNode(paper().nodeId)}>{t("定位首篇纳入文献", "Focus first included paper")}</button></section>}</Show>}><section class="graph-screening-cue" aria-live="polite"><div><small>{t("当前首要动作", "CURRENT PRIMARY ACTION")}</small><strong>{props.screening ? t("先完成候选文献的人审筛选", "Complete human screening of candidate literature first") : t("载入候选文献人工筛选清单", "Load the human screening checklist")}</strong><p>{props.screening ? t(`已返回 ${props.screening.candidate_count} 篇元数据候选。请逐篇记录纳入、排除或补元数据的理由；这一步不会下载全文或生成 EvidenceCard。`, `${props.screening.candidate_count} metadata candidates have returned. Record an include, exclude, or metadata-review reason for each; this does not download full text or create an EvidenceCard.`) : t("图谱中已有候选论文，但人工筛选清单尚未载入。载入后请逐篇记录决定与理由；这一步不会下载全文或生成 EvidenceCard。", "Candidate papers are present in the map, but the human screening checklist is not loaded. After loading it, record one decision and reason per paper; this does not download full text or create an EvidenceCard.")}</p></div><button type="button" class="primary-action" onClick={() => openScreening(firstUnreviewedCandidateId())}>{props.screening ? t("开始人工筛选", "Start human screening") : t("载入筛选清单", "Load screening checklist")}</button></section></Show>
    <Show when={selectedPaperHidden()}><section class="graph-hidden-selection" aria-live="polite"><div><small>{t("当前选择已被筛选隐藏", "CURRENT SELECTION HIDDEN")}</small><strong>{selectedNode()?.label ?? ""}</strong><p>{t("该论文仍是本次阅读会话的选择，但当前搜索、主题或节点筛选未将其显示在画布中。", "This paper remains selected for the current reading session, but the current search, topic, or node filter hides it from the canvas.")}</p></div><button type="button" onClick={revealSelectedPaper}>{t("显示当前论文", "Reveal current paper")}</button></section></Show>
    <Show when={hasReviewablePapers() && props.onLoadScreening && props.onSubmitScreening && screeningPanelOpen()}><section class="graph-screening-drawer" aria-label={t("候选文献人工筛选", "Candidate literature human screening")}><button type="button" class="screening-drawer-close" onClick={() => setScreeningPanelOpen(false)}>{t("收起筛选", "Hide screening")}</button><CandidateScreeningPanel locale={props.locale} screening={props.screening} load={props.onLoadScreening!} submit={props.onSubmitScreening!} onRequestFulltext={props.onRequestFulltext} focusDocumentId={screeningFocusId()} autoOpen /></section></Show>
    <Show when={advanced()}><section class="advanced-filters"><div><strong>{t("节点类型", "Node types")}</strong><For each={NODE_GROUPS}>{(group) => <label><input type="checkbox" checked={nodeVisibility()[group.id]} onChange={() => setNodeVisibility((current) => ({ ...current, [group.id]: !current[group.id] }))} />{t(group.zh, group.en)}</label>}</For></div><div><strong>{t("关系类型", "Relation types")}</strong><For each={EDGE_GROUPS}>{(group) => <label><input type="checkbox" checked={edgeVisibility()[group.id]} onChange={() => setEdgeVisibility((current) => ({ ...current, [group.id]: !current[group.id] }))} />{t(group.zh, group.en)}</label>}</For></div></section></Show>
<section class="graph-workspace" classList={{ "inspector-open": inspectorOpen() }}><section class="lens-canvas-region"><div class="lens-canvas-tools"><button type="button" aria-label={t("放大", "Zoom in")} onClick={() => controls()?.zoomIn()}>+</button><button type="button" aria-label={t("缩小", "Zoom out")} onClick={() => controls()?.zoomOut()}>−</button></div><LiteratureGraphCanvas theme={() => props.theme} nodes={visibleNodes} edges={visibleEdges} selectedNodeId={selectedNodeId} selectedEdge={selectedEdge} onSelectNode={selectNode} onSelectEdge={selectEdge} onReady={setControls} paperStates={paperStates} /><div class="paper-workflow-legend" aria-label={t("论文工作流状态图例", "Paper workflow state legend")}><small>{t("论文环表示来源处理状态", "PAPER RING = SOURCE-WORKFLOW STATE")}</small><span class="state-screening">{t(`待筛选 ${paperStateCounts().screening}`, `screen ${paperStateCounts().screening}`)}</span><span class="state-included">{t(`待全文 ${paperStateCounts().included}`, `full text ${paperStateCounts().included}`)}</span><span class="state-parsing">{t(`解析中 ${paperStateCounts().parsing}`, `parsing ${paperStateCounts().parsing}`)}</span><span class="state-source_map">{t(`待定位 ${paperStateCounts().source_map}`, `locate ${paperStateCounts().source_map}`)}</span><span class="state-evidence_review">{t(`待证据审核 ${paperStateCounts().evidence_review}`, `review ${paperStateCounts().evidence_review}`)}</span><span class="state-provenance_audit">{t(`待精确审计 ${paperStateCounts().provenance_audit}`, `audit ${paperStateCounts().provenance_audit}`)}</span><span class="state-accepted_evidence">{t(`已接受证据 ${paperStateCounts().accepted_evidence}`, `accepted ${paperStateCounts().accepted_evidence}`)}</span><Show when={paperStateCounts().failed}><span class="state-failed">{t(`失败 ${paperStateCounts().failed}`, `failed ${paperStateCounts().failed}`)}</span></Show></div><p class="lens-footnote">{graphFootnote({ locale: props.locale, hasCitationMap: hasCitationMap(), bibliographyCount: bibliographyCount(), paperLikeNodeCount: paperCount(), reviewablePaperCount: visibleReviewablePaperCount(), visibleEdgeCount: visibleEdges().length })}</p></section>
      <Show when={inspectorOpen()}><aside class="evidence-inspector" aria-label={t("图谱检查器", "Map inspector")}><Show when={selectedNode()} fallback={<Show when={selectedEdge()} fallback={<><small>{t("检查器", "INSPECTOR")}</small><h2>{t("选择论文或关系", "Select a paper or relation")}</h2><p>{t("默认关闭详情，保留星图的可读性。", "Details stay closed by default so the map remains readable.")}</p></>}>{(edge) => <><small>{t("关系", "RELATION")}</small><h2>{edge().edgeType.replaceAll("_", " ")}</h2><p>{edge().relationSource}</p><dl><div><dt>{t("起点", "Source")}</dt><dd>{edge().sourceId}</dd></div><div><dt>{t("终点", "Target")}</dt><dd>{edge().targetId}</dd></div></dl></>}</Show>}>{(node) => <><small>{t("已选对象", "SELECTED ARTIFACT")}</small><h2>{node().label}</h2><p>{node().trustStatus.replaceAll("_", " ")}</p><Show when={node().kind === "citation_work"}><p class="bibliography-boundary">{t("该节点是公开书目导航条目；请获得并核对原文后，才能建立来源定位或 EvidenceCard。", "This node is a public bibliography-navigation record. Obtain and verify the original text before creating a source location or EvidenceCard.")}</p></Show><Show when={isPaperNode(node()) && !paperDocumentId(node())}><p class="bibliography-boundary">{t("该对象保留题名或书目导航信息，但没有当前任务可审核的 document ID；不能绑定授权 PDF、来源定位或 EvidenceCard。", "This object retains title or bibliography-navigation metadata but has no reviewable document ID for the current mission; it cannot bind an authorised PDF, source location, or EvidenceCard.")}</p></Show><Show when={node().kind === "condition_cluster"}><section class="condition-cluster-inspector"><small>{t("条件比较工件", "CONDITION COMPARISON ARTIFACT")}</small><p>{t("该簇由已接受 EvidenceCard 的可比条件推导；支持与矛盾关系用于定位下一轮原文核对，不构成材料科学结论。", "This cluster is derived from comparable conditions on accepted EvidenceCards. Support and contradiction links guide the next source review; they are not a materials-science conclusion.")}</p><Show when={conditionEvidence().length} fallback={<p>{t("该条件簇尚未保留可展示的已接受证据连接。请回到阅读页核对来源定位与人工审核状态。", "This cluster has no displayable accepted-evidence links. Return to the reader to check source locations and human-review status.")}</p>}><For each={conditionEvidence()}>{(link) => <button type="button" classList={{ contradiction: link.relation === "contradiction" }} onClick={() => { props.onSelectEvidence(link.evidence); props.onNavigate("reader"); }}><strong>{link.relation === "support" ? t("支持条件", "Supports condition") : t("矛盾条件", "Contradicts condition")}</strong><span>{link.evidence.evidenceId} · {link.evidence.provenance.documentId} · {link.evidence.provenance.locator}</span></button>}</For></Show></section></Show><dl><div><dt>{t("类型", "Type")}</dt><dd>{node().kind.replaceAll("_", " ")}</dd></div><Show when={node().source}><div><dt>{t("元数据来源", "Metadata source")}</dt><dd>{node().source}</dd></div></Show><Show when={node().publicationYear}><div><dt>{t("发表年份", "Publication year")}</dt><dd>{node().publicationYear}</dd></div></Show></dl><Show when={Boolean(paperDocumentId(node()))}><section class="evidence-handoff"><small>{linkedEvidence().length ? t("下一受控动作：核对已接受证据", "NEXT CONTROLLED ACTION: VERIFY ACCEPTED EVIDENCE") : paperPdf().state === "source-map" ? t("下一受控动作：登记来源定位", "NEXT CONTROLLED ACTION: REGISTER SOURCE LOCATIONS") : paperPdf().state === "evidence-review" ? t("下一受控动作：审核材料事实与 EvidenceCard", "NEXT CONTROLLED ACTION: REVIEW FACTS AND EVIDENCECARD") : paperPdf().state === "failed" ? t("下一受控动作：重新选择授权 PDF", "NEXT CONTROLLED ACTION: RETRY AUTHORIZED PDF") : paperPdf().state === "parsing" ? t("下一受控动作：等待私有解析", "NEXT CONTROLLED ACTION: WAIT FOR PRIVATE PARSING") : t("下一受控动作：建立来源关联", "NEXT CONTROLLED ACTION: ESTABLISH SOURCE LINK")}</small>
  <Show when={linkedEvidence().length}><><p>{t("当前论文已有显式来源映射的已接受 EvidenceCard。进入阅读页核对定位符和条件字段；书目关系本身不构成材料事实。", "This paper already has an accepted EvidenceCard with an explicit source-map link. Open the reader to verify its locator and conditions; bibliography alone is not a material fact.")}</p><button type="button" class="primary-action" onClick={() => openReaderForPaper(node())}>{t("在阅读页核对来源", "Verify source in reader")}</button></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "source-map"}><><p>{t("该论文的授权 PDF 已解析完成并已绑定当前候选。请进入阅读页，在本机 Markdown 中人工登记最小必要的来源定位。", "The authorized PDF for this paper is parsed and bound to the current candidate. Open the reader and register the minimum necessary source locations from local Markdown by human review.")}</p><button type="button" class="primary-action" onClick={() => openReaderForPaper(node())}>{t("进入阅读页登记来源", "Open reader to register source")}</button></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "evidence-review"}><><p>{t("该论文已登记来源定位。请进入阅读页登记结构化材料事实，并在六项条件完整后人工接受 EvidenceCard。", "This paper already has recorded source locations. Open the reader and register structured material facts and, when all six conditions are complete, accept an EvidenceCard by human review.")}</p><button type="button" class="primary-action" onClick={() => openReaderForPaper(node())}>{t("进入阅读页继续审核", "Open reader to continue review")}</button></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "parsing"}><><p>{t("该论文的授权 PDF 已绑定，但私有解析尚未完成。请返回舰桥查看 MinerU 状态；解析完成前不会显示 Markdown、来源定位或 EvidenceCard。", "An authorized PDF is attached to this paper, but private parsing is not complete. Return to the bridge to inspect MinerU status; Markdown, source locations, and EvidenceCards stay unavailable until completion.")}</p><button type="button" class="primary-action" onClick={() => props.onNavigate("workflow")}>{t("返回舰桥查看解析状态", "Return to bridge for parsing status")}</button></></Show>  <Show when={!linkedEvidence().length && paperPdf().state === "failed"}><><p>{t("该论文此前关联的私有 PDF 解析失败。人工筛选记录仍然有效；请重新选择你有权处理的对应 PDF，系统不会把失败任务当作来源定位或证据。", "The previously attached private PDF for this paper failed to parse. The human screening record remains valid; choose the corresponding PDF you are authorized to process again. A failed task is never treated as a source location or evidence.")}</p><Show when={screeningCandidate()}>{(candidate) => <Show when={props.onRequestFulltext}><button type="button" class="primary-action" onClick={() => props.onRequestFulltext?.(candidate())}>{t("重新选择授权 PDF", "Choose authorized PDF again")}</button></Show>}</Show><button type="button" onClick={() => props.onNavigate("workflow")}>{t("查看失败原因", "View failure reason")}</button></></Show>
  <Show when={!linkedEvidence().length && paperPdf().state === "none"}><Show when={screeningCandidate()} fallback={<><p>{t("此论文尚未进入当前任务的人工筛选清单，不能申请全文处理或接受 EvidenceCard。", "This paper is not in the current task’s human screening list; full-text processing and EvidenceCard acceptance are unavailable.")}</p><Show when={props.onLoadScreening}><button type="button" class="primary-action" onClick={() => openScreening(paperDocumentId(node()) ?? null)}>{t("打开候选人工筛选", "Open candidate screening")}</button></Show></>}>{(candidate) => <><p>{screeningDecision() === "include_for_fulltext" ? t("该候选已被人工纳入全文核对，但尚未绑定对应的授权 PDF。下一步请选择你有权处理的 PDF。", "This candidate is human-included for full-text review but has no matching authorized PDF attached. Next choose a PDF you are authorized to process.") : screeningDecision() === "exclude" ? t("该候选已被人工排除，不能进入全文处理。若需调整，请在筛选清单中提交新的完整决定。", "This candidate is human-excluded and cannot enter full-text processing. Submit a revised complete decision in the screening checklist to change this.") : screeningDecision() === "needs_metadata_review" ? t("该候选仍需补充或核验书目信息，暂不能请求全文。", "This candidate still needs bibliographic metadata review and cannot request full text yet.") : t("此候选尚未完成人工筛选；请先记录决定与理由。", "This candidate has not completed human screening; record a decision and reason first.")}</p><Show when={screeningDecision() === "include_for_fulltext" && props.onRequestFulltext}><button type="button" class="primary-action" onClick={() => props.onRequestFulltext?.(candidate())}>{t("选择授权 PDF", "Choose authorized PDF")}</button></Show><Show when={screeningDecision() !== "include_for_fulltext" && props.onLoadScreening}><button type="button" class="primary-action" onClick={() => openScreening(candidate().document_id)}>{t("查看或修改人工筛选", "View or revise screening")}</button></Show></>}</Show></Show>
</section></Show><Show when={Boolean(paperDocumentId(node())) && linkedEvidence().length > 0}><section class="imported-evidence-list"><small>{t("与当前论文显式关联的已接受证据", "ACCEPTED EVIDENCE LINKED TO THIS PAPER")}</small><p>{t("只显示图谱中存在 source_provenance 路径的证据卡；未出现卡片表示该论文仍无已审核来源关联。", "Only EvidenceCards with a source_provenance path in this map are shown. An empty list means this paper has no reviewed source link yet.")}</p><For each={linkedEvidence()}>{(evidence) => <button type="button" onClick={() => props.onSelectEvidence(evidence)}><strong>{evidence.evidenceId}</strong><span>{evidence.provenance.documentId} · {evidence.provenance.locator}</span></button>}</For></section></Show></>}</Show></aside></Show></section>
    </Show>
    <footer class="stage-note">{t("论文选择、EvidenceCard 选择和来源定位是独立的审计事实；缺失关联必须显式显示。", "Paper selection, EvidenceCard selection, and source location are separate audit facts; missing linkage is shown explicitly.")}</footer>
  </main>;
}
