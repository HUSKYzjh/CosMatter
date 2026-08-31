import { For, Show, createEffect, createMemo, createSignal } from "solid-js";

import { FleetDecoration } from "./FleetDecoration";
import { fleetVisualState } from "./fleetVisualState";
import type { EvidenceCard, ImportedBundle, ResearchGapCandidate } from "./model";
import { preferredConditionCluster } from "./conditionClusterSelection";
import { conditionEvidenceLinks } from "./conditionEvidenceLinks";
import { evidenceGate, selectedEvidence, type ResearchSession } from "./researchSession";
import { gapCandidatesForEvidence } from "./gapLinking";
import { gapEvidenceReferences, hasAuditableGapEvidenceBasis } from "./gapEvidenceReferences";
import { hasExecutedGapCounterevidenceBoundary } from "./gapBoundaryReadiness";
import { isAuditableConditionContrast, researchExtensionReadiness } from "./researchExtensionReadiness";
import { safeOperationFeedback } from "./importFeedback";
import { researchExtensionNextAction } from "./researchExtensionNextAction";
import { counterevidenceReadiness, type CounterevidenceReadiness } from "./counterevidenceReadiness";
import { ReadOnlyPreviewContext } from "./ReadOnlyPreviewContext";
import { EvidenceMaturityPanel } from "./EvidenceMaturityPanel";
import { ConditionNormalizationPanel } from "./ConditionNormalizationPanel";
import { uiLanguage } from "./zh";

type View = "discover" | "workflow" | "graph" | "reader" | "horizon";
const EN: Record<string, string> = {
  "未选择条件簇": "No condition cluster selected",
  "当前证据同时被登记为两侧依据；需要人工复核矩阵。": "The current evidence is recorded on both sides; the matrix needs human review.",
  "当前证据被登记在支持侧。": "The current evidence is recorded on the supporting side.",
  "当前证据被登记在矛盾侧。": "The current evidence is recorded on the contradicting side.",
  "当前证据未被登记到这个条件簇。": "The current evidence is not recorded in this condition cluster.",
  "待人工复核候选": "Candidate pending human review",
  "问题": "Question",
  "支撑证据": "Supporting evidence",
  "未提供": "Not provided",
  "缺失或冲突": "Missing information or conflict",
  "可证伪假设": "Falsifiable hypothesis",
  "建议验证": "Suggested validation",
  "人工审核状态": "Human review status",
  "证据完整度": "Evidence completeness",
  "已标记人工复核": "Marked for human review",
  "标记人工复核": "Mark for human review",
  "尚未选择待核对论文。": "No paper is selected for verification.",
  "尚未选择与当前论文关联的已接受 EvidenceCard。": "No accepted EvidenceCard linked to the current paper is selected.",
  "所选 EvidenceCard 没有与当前论文对应的已审核来源映射。": "The selected EvidenceCard has no reviewed source-map link for the current paper.",
  "所选 EvidenceCard 缺少来源定位。": "The selected EvidenceCard is missing a source locator.",
  "当前工件没有来源映射片段。": "The current artifacts contain no source-map segment.",
  "研究拓展": "Research extension",
  "把条件矛盾保留为待核对候选": "Keep condition conflicts as candidates for review",
  "当前证据门禁": "Current evidence gate",
  "已选择带来源定位的已接受 EvidenceCard": "An accepted EvidenceCard with a source locator is selected",
  "研究拓展尚未解锁": "Research extension is not unlocked",
  "返回文献星图": "Return to literature map",
  "返回证据核对": "Return to evidence verification",
  "尚不能把候选作为后续研究方向": "Candidates cannot yet become follow-up directions",
  "请补齐当前会话的论文选择、已接受 EvidenceCard 和来源定位；本页不会以全局计数替代当前审计链路。": "Complete the current session's paper selection, accepted EvidenceCard, and source locator. This page never substitutes global counts for the active audit chain.",
  "条件未知项": "Condition unknowns",
  "本任务 Gap 候选": "Gap candidates in this task",
  "当前证据关联候选": "Candidates linked to current evidence",
  "当前证据": "Current evidence",
  "审计与评测": "Audit and evaluation",
  "以下指标只反映导入工件中的已记录评测；没有记录时不显示为系统性能。": "These indicators only reflect evaluation recorded in imported artifacts; missing records are not presented as system performance.",
  "来源定位覆盖": "Source-locator coverage",
  "未运行": "Not run",
  "证据溯源匹配": "Evidence-provenance match",
  "检索评测": "Retrieval evaluation",
  "标记人工复核仅保留在当前浏览器会话中，不会触发检索、模型调用或正式研究任务。": "Marking human review stays only in the current browser session and never triggers retrieval, model calls, or a formal research task.",
};
const tr = (zhText: string, enText?: string) => uiLanguage() === "zh" ? zhText : enText ?? EN[zhText] ?? zhText;

function ConditionComparisonBoard(props: { bundle: ImportedBundle; evidenceId: string; onFocusEvidence?: (evidence: EvidenceCard) => void }) {
  const [selectedCluster, setSelectedCluster] = createSignal(preferredConditionCluster(props.bundle.conditionMatrix, props.evidenceId));
  let previousEvidenceId = props.evidenceId;
  createEffect(() => {
    const preferred = preferredConditionCluster(props.bundle.conditionMatrix, props.evidenceId);
    const selectedStillExists = props.bundle.conditionMatrix.some((row) => row.conditionCluster === selectedCluster());
    if (props.evidenceId !== previousEvidenceId || !selectedStillExists) setSelectedCluster(preferred);
    previousEvidenceId = props.evidenceId;
  });
  const current = createMemo(() => props.bundle.conditionMatrix.find((row) => row.conditionCluster === selectedCluster()) ?? props.bundle.conditionMatrix[0] ?? null);
  const currentAuditable = createMemo(() => { const row = current(); return Boolean(row && isAuditableConditionContrast(row, props.bundle)); });
  const currentIncludesEvidence = createMemo(() => { const row = current(); return Boolean(row && [...row.supportingEvidenceIds, ...row.contradictingEvidenceIds].includes(props.evidenceId)); });
  const role = createMemo(() => {
    const row = current();
    if (!row) return "none";
    if (row.supportingEvidenceIds.includes(props.evidenceId) && row.contradictingEvidenceIds.includes(props.evidenceId)) return "both";
    if (row.supportingEvidenceIds.includes(props.evidenceId)) return "support";
    if (row.contradictingEvidenceIds.includes(props.evidenceId)) return "contradict";
    return "outside";
  });
  const roleCopy = () => ({
    none: tr("未选择条件簇", "No condition cluster selected"),
    both: tr("当前证据同时被登记为两侧依据；需要人工复核矩阵。", "The current evidence is recorded on both sides; the matrix needs human review."),
    support: tr("当前证据被登记在支持侧。", "The current evidence is recorded on the supporting side."),
    contradict: tr("当前证据被登记在矛盾侧。", "The current evidence is recorded on the contradicting side."),
    outside: tr("当前证据未被登记到这个条件簇。", "The current evidence is not registered in this condition cluster."),
  }[role()]);
  const evidenceLinks = (evidenceIds: readonly string[]) => conditionEvidenceLinks(evidenceIds, props.bundle.evidenceCards);
  const renderEvidenceLinks = (evidenceIds: readonly string[]) => <Show when={evidenceIds.length} fallback={<span>{tr("未登记", "not recorded")}</span>}><For each={evidenceLinks(evidenceIds)}>{(link) => link.evidence && props.onFocusEvidence ? <button type="button" class="condition-evidence-link" onClick={() => props.onFocusEvidence?.(link.evidence!)}><strong>{link.evidence.evidenceId}</strong><span>{link.evidence.provenance.documentId} · {link.evidence.provenance.locator}</span></button> : <span class="condition-evidence-missing">{link.evidenceId}{tr("（当前工件缺失）", " (missing from current artifacts)")}</span>}</For></Show>;
  return <section class="condition-comparison-board">
    <header><div><small>{tr("已导入条件比较", "IMPORTED CONDITION COMPARISON")}</small><h2>{tr("条件矩阵不是结论，而是比较边界", "The condition matrix is a comparison boundary, not a conclusion")}</h2><p>{tr("它仅列出已登记的证据 ID、差异字段和未知项；缺失字段不会被系统补写。", "It lists only recorded evidence IDs, differing fields, and unknowns; the system does not fill missing fields.")}</p></div><span>{props.bundle.conditionMatrix.length}</span></header>
    <div class="condition-cluster-tabs" role="group" aria-label={tr("条件簇", "Condition clusters")}><For each={props.bundle.conditionMatrix}>{(row) => <button type="button" classList={{ active: row.conditionCluster === current()?.conditionCluster }} onClick={() => setSelectedCluster(row.conditionCluster)}>{row.conditionCluster}</button>}</For></div>
    <Show when={current()}>{(row) => <><dl class="condition-cluster-detail"><div><dt>{tr("支持侧证据", "supporting evidence")}</dt><dd class="condition-evidence-links">{renderEvidenceLinks(row().supportingEvidenceIds)}</dd></div><div><dt>{tr("矛盾侧证据", "contradicting evidence")}</dt><dd class="condition-evidence-links">{renderEvidenceLinks(row().contradictingEvidenceIds)}</dd></div><div><dt>{tr("差异字段", "differing fields")}</dt><dd>{row().differingFields.join("；") || tr("未登记", "not recorded")}</dd></div><div><dt>{tr("未知项", "unknowns")}</dt><dd>{row().unknowns.join("；") || tr("未登记", "not recorded")}</dd></div></dl><p class="condition-current-evidence">{roleCopy()}</p><p classList={{ "condition-comparison-ready": currentAuditable() && currentIncludesEvidence(), "condition-comparison-pending": !currentAuditable() || !currentIncludesEvidence() }}>{currentAuditable() && currentIncludesEvidence() ? tr("该条件簇已显式连接当前 EvidenceCard 与不同文献的相反已接受证据，并记录了差异字段；它可用于受控比较，但不是科学结论。", "This cluster explicitly links the current EvidenceCard with accepted opposing evidence from different papers and records differing fields. It can support controlled comparison, not a scientific conclusion.") : currentAuditable() ? tr("该条件簇本身可用于受控比较，但当前 EvidenceCard 未被该行引用；请选择对应证据或返回星图核对关联。", "This cluster can support controlled comparison, but it does not cite the current EvidenceCard. Select the linked evidence or return to the map to inspect the relation.") : tr("该条件簇尚未构成可追溯对照：需连接不同文献的相反已接受证据，并记录至少一个差异字段。", "This cluster is not yet an auditable contrast: it must link accepted opposing evidence from different papers and record at least one differing field.")}</p></>}</Show>
  </section>;
}
function CandidateCard(props: { candidate: ResearchGapCandidate; counterevidence: CounterevidenceReadiness; basisReady: boolean; index: number; marked: boolean; evidenceCards: readonly EvidenceCard[]; onMark: () => void; onReturnToGraph: () => void; onFocusEvidence: (evidence: EvidenceCard) => void }) {
  const candidate = props.candidate;
  const boundaryReady = props.basisReady && hasExecutedGapCounterevidenceBoundary(candidate, props.counterevidence);
  const references = () => gapEvidenceReferences(candidate, props.evidenceCards);
  return <article class="gap-candidate"><header><span>{String(props.index + 1).padStart(2, "0")}</span><small>{boundaryReady ? tr("待人工复核候选 · 反例边界已登记", "Candidate pending human review · counterevidence boundary recorded") : tr("待人工复核候选 · 缺少可核验反例边界", "Candidate pending human review · counterevidence boundary unavailable")}</small></header><h2>{candidate.problemDescription}</h2><dl class="gap-evidence-fields"><div><dt>{tr("问题")}</dt><dd>{candidate.problemDescription}</dd></div><div><dt>{tr("支撑证据")}</dt><dd class="gap-evidence-links"><Show when={references().linked.length} fallback={<span>{tr("未提供")}</span>}><For each={references().linked}>{(evidence) => <button type="button" onClick={() => props.onFocusEvidence(evidence)}><strong>{evidence.evidenceId}</strong><span>{evidence.provenance.documentId} · {evidence.provenance.locator} · {evidence.stance}</span></button>}</For></Show><Show when={references().missingIds.length}><small>{tr(`以下证据 ID 未出现在当前导入工件中：${references().missingIds.join(", ")}。`, `These evidence IDs are missing from the current imported artifacts: ${references().missingIds.join(", ")}.`)}</small></Show></dd></div><div><dt>{tr("缺失或冲突")}</dt><dd>{candidate.conflictOrMissingEvidence.join("；") || tr("未提供")}</dd></div><div><dt>{tr("可证伪假设")}</dt><dd>{candidate.falsifiableHypothesis}</dd></div><div><dt>{tr("建议验证")}</dt><dd>{candidate.suggestedValidation.join("；")}</dd></div><div><dt>{tr("人工审核状态")}</dt><dd>{candidate.reviewStatus.replaceAll("_", " ")}</dd></div></dl><footer><span>{tr("证据完整度")}: {Math.round(candidate.evidenceCompleteness * 100)}% · {candidate.noveltyStatus} · {candidate.actionability}</span><div class="gap-candidate-actions"><button type="button" onClick={props.onReturnToGraph}>{tr("返回星图补文献", "Return to map")}</button><button type="button" classList={{ marked: props.marked }} onClick={props.onMark}>{props.marked ? tr("已标记人工复核") : tr("标记人工复核")}</button></div></footer></article>;
}

export function ResearchExpansion(props: { bundle: ImportedBundle; session: ResearchSession; onNavigate: (view: View) => void; onFocusEvidence?: (evidence: EvidenceCard) => void; onOpenTaskControl?: () => void; onBuildConditionMatrix?: () => Promise<void>; onBuildGapCandidates?: () => Promise<void>; readOnlyPreview?: boolean; onExitPreview?: () => void }) {
  const [marked, setMarked] = createSignal<string | null>(null);
  const [actionBusy, setActionBusy] = createSignal(false);
  const [actionError, setActionError] = createSignal<string | null>(null);
  const runAction = async (action: (() => Promise<void>) | undefined) => {
    if (!action || actionBusy()) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (error) {
      setActionError(safeOperationFeedback(error, tr("当前工件尚不满足此操作的前置条件。", "The current artifacts do not satisfy this action's prerequisites.")));
    } finally {
      setActionBusy(false);
    }
  };
  const gate = createMemo(() => evidenceGate(props.bundle, props.session));
  const evidence = createMemo(() => selectedEvidence(props.bundle, props.session));
  const candidates = () => props.bundle.researchGapCandidates;
  const counterevidence = createMemo(() => counterevidenceReadiness(props.bundle));
  const verifiedCandidateCount = createMemo(() => candidates().filter((candidate) => hasAuditableGapEvidenceBasis(candidate, props.bundle) && hasExecutedGapCounterevidenceBoundary(candidate, counterevidence())).length);
  const sessionCandidates = createMemo(() => gapCandidatesForEvidence(candidates(), evidence()));
  const comparison = createMemo(() => researchExtensionReadiness(props.bundle));
  const reason = createMemo(() => ({ paper: tr("尚未选择待核对论文。"), evidence: tr("尚未选择与当前论文关联的已接受 EvidenceCard。"), "source-link": tr("所选 EvidenceCard 没有与当前论文对应的已审核来源映射。"), locator: tr("所选 EvidenceCard 缺少来源定位。"), "source-map": tr("当前工件没有来源映射片段。"), "provenance-audit": tr("当前已接受 EvidenceCard 尚未全部通过精确来源映射审计。", "Accepted EvidenceCards have not all passed the exact source-map provenance audit.") }[gate().reason ?? "evidence"]));
  const evaluation = () => props.bundle.auditSummary.evaluation;
  const readiness = () => props.bundle.auditSummary.submissionReadiness;
  const comparisonReason = createMemo(() => ({
    evidence: tr("至少需要两张已接受 EvidenceCard，才可开始跨文献比较。", "At least two accepted EvidenceCards are required before an across-paper comparison."),
    "provenance-audit": tr("当前已接受 EvidenceCard 尚未全部通过精确来源映射审计；请先在证据核对页补齐来源定位与人工审核。", "Accepted EvidenceCards have not all passed the exact source-map provenance audit. Complete source location and human review first."),
    documents: tr("需要来自至少两篇不同文献的已接受 EvidenceCard；同一篇文献的多条卡片仍属于单篇观察。", "Accepted EvidenceCards must come from at least two different papers; multiple cards from one paper remain a single-paper observation."),
    comparison: tr("需要同时存在支持与矛盾的已接受证据；相同立场的多篇论文不等于条件冲突。", "Accepted evidence must include both supporting and contradicting positions; several papers with one stance are not a condition conflict."),
    conditions: tr("需要至少一条可追溯的条件矩阵行：它必须连接不同文献的支持侧与矛盾侧已接受证据，并列出至少一个差异字段。", "Add at least one auditable condition-matrix row: it must connect accepted supporting and contradicting evidence from different papers and list at least one differing field."),
  }[comparison().reason ?? "evidence"]));
  const nextAction = createMemo(() => researchExtensionNextAction(comparison(), counterevidence(), verifiedCandidateCount()));
  const nextActionCopy = createMemo(() => ({
    "comparison-evidence": { title: tr("先补齐跨文献对照", "Add across-paper comparison evidence first"), detail: comparisonReason(), button: tr("返回星图补充对照文献", "Return to map for comparison papers") },
    "provenance-audit": { title: tr("补齐精确来源审计", "Complete exact source-map audit"), detail: comparisonReason(), button: tr("返回证据核对补定位", "Return to evidence verification") },
    counterevidence: { title: tr("执行已批准的反例检索", "Run approved counterevidence retrieval"), detail: counterevidence().message, button: counterevidence().nextAction },
    "condition-matrix": { title: tr("建立条件比较边界", "Build the condition-comparison boundary"), detail: props.onBuildConditionMatrix ? comparisonReason() : `${comparisonReason()} ${tr("当前页面未连接本地受控执行接口；不会在浏览器内推断或生成矩阵。", "This page is not connected to a local controlled-execution interface; it will not infer or generate a matrix in the browser.")}`, button: props.onBuildConditionMatrix ? tr("生成确定性条件矩阵", "Build deterministic condition matrix") : tr("返回舰桥连接受控运行", "Return to bridge for controlled execution") },
    "gap-candidates": { title: tr("生成待人工复核的 Gap 候选", "Generate review-required Gap candidates"), detail: props.onBuildGapCandidates ? tr("已具备比较与反例边界；输出仍是待人工复核的候选，而非科学结论。", "Comparison and counterevidence boundaries are present. The output remains a human-review candidate, not a scientific conclusion.") : tr("已具备比较与反例边界，但当前页面未连接本地受控执行接口；不会在浏览器内生成候选。", "Comparison and counterevidence boundaries are present, but this page is not connected to a local controlled-execution interface; it will not generate candidates in the browser."), button: props.onBuildGapCandidates ? tr("生成待人工复核 Gap 候选", "Generate review-required Gap candidates") : tr("返回舰桥连接受控运行", "Return to bridge for controlled execution") },
    "review-candidates": { title: tr("复核当前 Gap 候选", "Review current Gap candidates"), detail: tr("现有候选将保留为待人工复核；可在下方逐项查看证据、冲突与可证伪假设。", "Existing candidates remain pending human review. Inspect their evidence, conflicts, and falsifiable hypotheses below."), button: "" },
  }[nextAction()]));
  const evidenceConvoy = createMemo(() => [
    {
      id: "source",
      target: gate().reason === "paper" ? "graph" as const : "reader" as const,
      state: gate().ready ? "secured" : "awaiting",
      label: tr("来源锁定", "SOURCE LOCK"),
      value: gate().ready ? evidence()!.evidenceId : tr("待核对", "pending"),
      detail: gate().ready ? `${evidence()!.provenance.documentId} · ${evidence()!.provenance.locator}` : reason(),
    },
    {
      id: "contrast",
      target: "graph" as const,
      state: comparison().ready ? "secured" : comparison().acceptedEvidenceCount >= 2 ? "inbound" : "awaiting",
      label: tr("相反证据", "OPPOSING EVIDENCE"),
      value: `${comparison().supportingEvidenceCount} ↔ ${comparison().contradictingEvidenceCount}`,
      detail: tr(`${comparison().distinctDocumentCount} 篇不同文献 · ${comparison().linkedConditionClusterCount}/${comparison().conditionClusterCount} 条可追溯条件簇`, `${comparison().distinctDocumentCount} distinct paper(s) · ${comparison().linkedConditionClusterCount}/${comparison().conditionClusterCount} auditable condition cluster(s)`),
    },
    {
      id: "counter",
      target: "workflow" as const,
      state: counterevidence().ready ? "secured" : counterevidence().plannedQueryCount ? "inbound" : "awaiting",
      label: tr("反例护航", "COUNTEREVIDENCE ESCORT"),
      value: `${counterevidence().executedQueryCount}/${counterevidence().plannedQueryCount}`,
      detail: counterevidence().ready ? tr("已执行的反例边界已登记", "Executed counterevidence boundary recorded") : counterevidence().nextAction,
    },
    {
      id: "gap",
      target: "horizon" as const,
      state: verifiedCandidateCount() ? "inbound" : "awaiting",
      label: tr("拓展候选", "HORIZON CANDIDATES"),
      value: `${sessionCandidates().length}/${verifiedCandidateCount()}`,
      detail: tr("当前证据关联 / 已核验边界", "linked to current evidence / verified boundary"),
    },
  ]);

  return <main class="discovery-stage expansion-stage">
    <FleetDecoration kind="horizon" state={fleetVisualState(props.bundle, "horizon")} />
    <header class="stage-header"><div><p class="stage-kicker">COSMATTER / {tr("研究拓展")}</p><h1>{tr("把条件矛盾保留为待核对候选")}</h1><p>{tr("研究缺口候选不是结论或推荐方向；只有人工审核后才能形成后续任务。", "Research Gap candidates are neither conclusions nor recommended directions; only human review can turn one into a follow-up task.")}</p></div></header>
    <Show when={props.readOnlyPreview}><ReadOnlyPreviewContext locale={uiLanguage()} onExit={props.onExitPreview} /></Show>
    <EvidenceMaturityPanel bundle={props.bundle} locale={uiLanguage()} />
    <Show when={props.bundle.conditionNormalization}>{(normalization) => <ConditionNormalizationPanel normalization={normalization()} locale={uiLanguage()} onFocusEvidence={props.onFocusEvidence} evidenceCards={props.bundle.evidenceCards} />}</Show>
    <section class="evidence-session expansion-gate"><div><small>{tr("当前证据门禁")}</small><strong>{gate().ready ? tr("已选择带来源定位的已接受 EvidenceCard") : tr("研究拓展尚未解锁")}</strong><span>{gate().ready ? `${evidence()!.evidenceId} · ${evidence()!.provenance.documentId} · ${evidence()!.provenance.locator}` : reason()}</span></div><button type="button" onClick={() => props.onNavigate(gate().reason === "paper" ? "graph" : "reader")}>{gate().reason === "paper" ? tr("返回文献星图") : tr("返回证据核对")}</button></section>
    <section class="evidence-convoy" aria-label={tr("证据护航线", "Evidence convoy")}>
      <header><small>{tr("舰队航迹 / 可审计交接", "FLEET VECTOR / AUDITABLE HANDOFF")}</small><span>{tr("仅投影已登记状态；点击舰位回到对应核对入口。", "Projects recorded status only; select a station to return to its review entry.")}</span></header>
      <div class="evidence-convoy-track">
        <For each={evidenceConvoy()}>{(station, index) => <button type="button" class={`convoy-station state-${station.state}`} onClick={() => props.onNavigate(station.target)}><span class="convoy-index">{String(index() + 1).padStart(2, "0")}</span><span class="convoy-ship" aria-hidden="true" /><span class="convoy-label">{station.label}</span><strong>{station.value}</strong><small>{station.detail}</small></button>}</For>
      </div>
    </section>
    <Show when={gate().ready} fallback={<section class="gap-empty"><h2>{tr("尚不能把候选作为后续研究方向")}</h2><p>{tr("请补齐当前会话的论文选择、已接受 EvidenceCard 和来源定位；本页不会以全局计数替代当前审计链路。")}</p></section>}>
      <section class="expansion-brief"><span>{tr("条件未知项")} <strong>{props.bundle.conditionMatrix.flatMap((row) => row.unknowns).length}</strong></span><span>{tr("已核验边界的 Gap 候选", "Gap candidates with verified boundaries")} <strong>{verifiedCandidateCount()}/{candidates().length}</strong></span><span>{tr("当前证据关联候选")} <strong>{sessionCandidates().length}</strong></span><span>{tr("当前证据")} <strong>{evidence()!.evidenceId}</strong></span></section>
      <section class="comparison-readiness" aria-live="polite">
        <div>
          <small>{tr("跨文献比较门禁", "CROSS-PAPER COMPARISON GATE")}</small>
          <strong>{comparison().ready ? tr("已具备受控比较的最低工件", "Minimum artifacts for a controlled comparison are present") : tr("当前仅可阅读已接受证据，尚不能解释为研究 Gap", "The current record supports evidence reading only, not a Research Gap interpretation")}</strong>
          <p>{!comparison().ready ? comparisonReason() : !counterevidence().ready ? counterevidence().message : tr("已记录相反立场、条件矩阵和已执行的反例边界；任何 Gap 候选仍需人工复核。", "Opposing positions, a condition matrix, and an executed counterevidence boundary are recorded; every Gap candidate still requires human review.")}</p>
        </div>
        <dl>
          <div><dt>{tr("已接受证据", "accepted evidence")}</dt><dd>{comparison().acceptedEvidenceCount}/2</dd></div>
          <div><dt>{tr("不同文献", "distinct papers")}</dt><dd>{comparison().distinctDocumentCount}/2</dd></div>
          <div><dt>{tr("支持 / 矛盾", "support / contradict")}</dt><dd>{comparison().supportingEvidenceCount} / {comparison().contradictingEvidenceCount}</dd></div>
          <div><dt>{tr("精确来源审计", "exact source-map audit")}</dt><dd>{props.bundle.auditSummary.evidenceProvenance ? props.bundle.auditSummary.evidenceProvenance.exactSourceMapMatchCount + "/" + props.bundle.auditSummary.evidenceProvenance.acceptedEvidenceCount : "0/" + comparison().acceptedEvidenceCount}</dd></div>
          <div><dt>{tr("可追溯条件簇", "linked condition clusters")}</dt><dd>{comparison().linkedConditionClusterCount}/{comparison().conditionClusterCount}</dd></div>
          <div><dt>{tr("反例检索", "counterevidence")}</dt><dd>{counterevidence().executedQueryCount}/{counterevidence().plannedQueryCount}</dd></div>
        </dl>
        <section class="extension-next-action" aria-live="polite">
          <div><small>{tr("唯一下一步", "SINGLE NEXT ACTION")}</small><strong>{nextActionCopy().title}</strong><p>{nextActionCopy().detail}</p></div>
          <Show when={nextAction() === "comparison-evidence"}><button type="button" class="primary-action" onClick={() => props.onNavigate("graph")}>{nextActionCopy().button}</button></Show>
          <Show when={nextAction() === "provenance-audit"}><button type="button" class="primary-action" onClick={() => props.onNavigate("reader")}>{nextActionCopy().button}</button></Show>
          <Show when={nextAction() === "counterevidence"}><button type="button" class="primary-action" onClick={() => { if (props.onOpenTaskControl) props.onOpenTaskControl(); else props.onNavigate("discover"); }}>{nextActionCopy().button}</button></Show>
          <Show when={nextAction() === "condition-matrix"}><Show when={props.onBuildConditionMatrix} fallback={<button type="button" class="primary-action" onClick={() => props.onNavigate("workflow")}>{nextActionCopy().button}</button>}><button type="button" class="primary-action" disabled={actionBusy()} onClick={() => void runAction(props.onBuildConditionMatrix)}>{actionBusy() ? tr("生成中…", "Generating…") : nextActionCopy().button}</button></Show></Show>
          <Show when={nextAction() === "gap-candidates"}><Show when={props.onBuildGapCandidates} fallback={<button type="button" class="primary-action" onClick={() => props.onNavigate("workflow")}>{nextActionCopy().button}</button>}><button type="button" class="primary-action" disabled={actionBusy()} onClick={() => void runAction(props.onBuildGapCandidates)}>{actionBusy() ? tr("生成中…", "Generating…") : nextActionCopy().button}</button></Show></Show>
        </section>
        <Show when={actionError()}>{(message) => <p class="comparison-action-error" role="alert">{tr("未生成新工件：", "No new artifact was generated: ")}{message()}</p>}</Show>
      </section>
      <Show when={props.bundle.conditionMatrix.length}><ConditionComparisonBoard bundle={props.bundle} evidenceId={evidence()!.evidenceId} onFocusEvidence={props.onFocusEvidence} /></Show>
      <Show when={sessionCandidates().length} fallback={<section class="gap-empty"><h2>{tr("当前证据尚无关联 Gap 候选")}</h2><p>{tr("这不代表没有研究缺口，只表示当前选中的 EvidenceCard 尚未被任何导入候选显式引用。")}</p></section>}><section class="proposal-grid gap-candidate-grid"><For each={sessionCandidates()}>{(candidate, index) => <CandidateCard candidate={candidate} counterevidence={counterevidence()} basisReady={hasAuditableGapEvidenceBasis(candidate, props.bundle)} index={index()} marked={marked() === candidate.gapId} evidenceCards={props.bundle.evidenceCards} onMark={() => setMarked(marked() === candidate.gapId ? null : candidate.gapId)} onReturnToGraph={() => props.onNavigate("graph")} onFocusEvidence={(item) => props.onFocusEvidence?.(item)} />}</For></section></Show>
      <details class="audit-details">
        <summary>{tr("审计与评测")}</summary>
        <p>{tr("以下指标只反映导入工件中的已记录评测；没有记录时不显示为系统性能。")}</p>
        <dl>
          <div><dt>{tr("来源定位覆盖")}</dt><dd>{props.bundle.auditSummary.reportEvidence ? `${Math.round(props.bundle.auditSummary.reportEvidence.acceptedEvidenceLocatorRenderedCoverage * 100)}%` : tr("未运行")}</dd></div>
          <div><dt>{tr("证据溯源匹配")}</dt><dd>{props.bundle.auditSummary.evidenceProvenance ? `${props.bundle.auditSummary.evidenceProvenance.exactSourceMapMatchCount}/${props.bundle.auditSummary.evidenceProvenance.acceptedEvidenceCount}` : tr("未运行")}</dd></div>
          <div><dt>{tr("检索评测")}</dt><dd>{evaluation().retrieval ? `P@${evaluation().retrieval!.k} ${Math.round(evaluation().retrieval!.precisionAtK * 100)}% / nDCG ${Math.round(evaluation().retrieval!.ndcgAtK * 100)}%` : tr("未提供")}</dd></div>
          <div><dt>{tr("冻结语料", "Frozen corpus")}</dt><dd>{readiness().frozenCorpus ? `${readiness().frozenCorpus!.frozenDocumentCount}/${readiness().frozenCorpus!.expectedDocumentCount}` : tr("未冻结", "Not frozen")}</dd></div>
          <div><dt>{tr("人工相关性标注", "Human relevance review")}</dt><dd>{readiness().humanAnnotation ? `${tr("未复核", "Unreviewed")} ${readiness().humanAnnotation!.relevanceCounts.unreviewed}` : tr("未提供", "Not provided")}</dd></div>
          <div><dt>{tr("书目来源覆盖", "Bibliographic-source coverage")}</dt><dd>{readiness().bibliographicSource ? `${readiness().bibliographicSource!.documentsWithReviewedBibliographicSource}/${readiness().bibliographicSource!.frozenDocumentCount}` : tr("未提供", "Not provided")}</dd></div>
        </dl>
      </details>
    </Show>
    <footer class="stage-note">{tr("标记人工复核仅保留在当前浏览器会话中，不会触发检索、模型调用或正式研究任务。")}</footer>
  </main>;
}

