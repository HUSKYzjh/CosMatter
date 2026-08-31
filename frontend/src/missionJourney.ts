import type { ImportedBundle } from "./model";
import { reviewablePaperCount } from "./evidenceLinking";
import { researchExtensionReadiness } from "./researchExtensionReadiness";
import { counterevidenceReadiness } from "./counterevidenceReadiness";
import { hasExecutedGapCounterevidenceBoundary } from "./gapBoundaryReadiness";

export type JourneyView = "discover" | "workflow" | "graph" | "reader" | "horizon";
export type JourneyState = "current" | "complete" | "ready" | "blocked";

/**
 * Frontend-only state for the active evidence-review session. These flags do
 * not assert that an artifact exists; they make the rail disclose the same
 * paper-specific prerequisites that the reader and extension pages enforce.
 */
export interface JourneySessionGate {
  paperSelected: boolean;
  evidenceReady: boolean;
  /** Current paper has a persisted human include decision for source review. */
  screeningAllowsSourceReview?: boolean;
  /** Current paper already exposes an accepted, provenance-linked EvidenceCard. */
  paperHasAcceptedEvidence?: boolean;
}

/** A graph is navigable only when it contains reviewable papers or an actual DOI citation relation. */
export function hasNavigableLiteratureGraph(bundle: ImportedBundle): boolean {
  const reviewable = reviewablePaperCount(bundle) > 0;
  const bibliography = bundle.literatureGraph.nodes.some((node) => node.kind === "citation_work")
    && bundle.literatureGraph.edges.some((edge) => edge.edgeType === "citation_reference" || edge.edgeType === "citation_cited_by");
  return reviewable || bibliography;
}

export interface JourneyStage {
  id: "define" | "orchestrate" | "map" | "verify" | "extend";
  view: JourneyView;
  zh: string;
  en: string;
  state: JourneyState;
  reasonZh?: string;
  reasonEn?: string;
}

/** A fresh mission shell has only question_intake; that is not yet an orchestration result. */
export function hasOrchestrationArtifact(bundle: ImportedBundle): boolean {
  return Boolean(bundle.fleet)
    || bundle.facilities.length > 0
    || bundle.timeline.length > 0
    || bundle.stations.some((station) => station.stationType !== "question_intake");
}

export function missionJourney(
  bundle: ImportedBundle,
  question: string,
  current: JourneyView,
  taskArtifactLocked = false,
  privateSourceMapReady = false,
  session: JourneySessionGate = { paperSelected: false, evidenceReady: false },
  missionConfirmed = true,
): JourneyStage[] {
  const defined = missionConfirmed && Boolean(question.trim() && bundle.mission.question.trim() && bundle.mission.material.trim() && bundle.mission.property.trim() && bundle.mission.scope.trim());
  const orchestrated = hasOrchestrationArtifact(bundle);
  const mapped = reviewablePaperCount(bundle) > 0;
  const graphReady = hasNavigableLiteratureGraph(bundle);
  const sourceMapIntakeReady = privateSourceMapReady;
  const verificationPrerequisite = session.evidenceReady || sourceMapIntakeReady || Boolean(session.screeningAllowsSourceReview) || Boolean(session.paperHasAcceptedEvidence);
  const comparison = researchExtensionReadiness(bundle);
  const counterevidence = counterevidenceReadiness(bundle);
  // A candidate becomes a completed extension only after both comparison and the approved counterevidence boundary are recorded.
  const extended = comparison.ready && counterevidence.ready && bundle.researchGapCandidates.some((candidate) => hasExecutedGapCounterevidenceBoundary(candidate, counterevidence));
  const staleReasonZh = "任务边界已改变；请重新导入匹配工件或执行受控检索。";
  const staleReasonEn = "The task boundary changed. Re-import matching artifacts or run controlled retrieval.";
  const stages: Array<Omit<JourneyStage, "state"> & { ready: boolean; complete: boolean; reasonZh?: string; reasonEn?: string }> = [
    { id: "define", view: "discover", zh: "任务定义", en: "Define", ready: defined, complete: defined, reasonZh: "请填写研究问题、对象、比较维度与范围。", reasonEn: "Enter the research question, objects, comparison dimensions, and scope." },
    { id: "orchestrate", view: "workflow", zh: "受控编排", en: "Orchestrate", ready: defined, complete: orchestrated, reasonZh: "请先确认完整任务简报。", reasonEn: "Confirm the complete mission brief first." },
    { id: "map", view: "graph", zh: "文献星图", en: "Map", ready: !taskArtifactLocked && graphReady, complete: mapped && session.paperSelected, reasonZh: taskArtifactLocked ? staleReasonZh : "受控编排尚未产生候选论文或 DOI 书目子图。", reasonEn: taskArtifactLocked ? staleReasonEn : "Controlled orchestration has not produced candidate papers or a DOI bibliography subgraph." },
    {
      id: "verify", view: "reader", zh: "证据核对", en: "Verify",
      ready: !taskArtifactLocked && mapped && session.paperSelected && verificationPrerequisite,
      complete: session.evidenceReady,
      reasonZh: taskArtifactLocked ? staleReasonZh : !mapped ? "请先形成可审查文献子图。" : !session.paperSelected ? "请先在文献星图选择一篇待核对论文。" : !verificationPrerequisite ? "当前论文尚未被人工纳入全文核对，也没有与其匹配的来源工件。" : undefined,
      reasonEn: taskArtifactLocked ? staleReasonEn : !mapped ? "Create an auditable literature subgraph first." : !session.paperSelected ? "Select a paper for verification in the literature map first." : !verificationPrerequisite ? "The current paper is not human-included for full-text review and has no matching source artifact." : undefined,
    },
    {
      id: "extend", view: "horizon", zh: "研究拓展", en: "Extend",
      ready: !taskArtifactLocked && session.evidenceReady,
      complete: extended,
      reasonZh: taskArtifactLocked ? staleReasonZh : "请先在当前会话选择一张带来源定位的已接受 EvidenceCard。",
      reasonEn: taskArtifactLocked ? staleReasonEn : "Select an accepted EvidenceCard with a source locator in the current session first.",
    },
  ];
  return stages.map((stage) => ({
    ...stage,
    state: stage.view === current ? "current" : stage.ready ? (stage.complete ? "complete" : "ready") : "blocked",
  }));
}




