import { auditableAcceptedEvidence, reviewablePaperCount } from "./evidenceLinking";
import { hasAuditableGapEvidenceBasis } from "./gapEvidenceReferences";
import type { PdfTaskStatus } from "./localApi";
import type { ImportedBundle } from "./model";

export type FlightRecordState = "complete" | "active" | "waiting" | "blocked";

export interface FlightRecordEntry {
  id: "brief" | "candidates" | "fulltext" | "source-map" | "facts" | "evidence" | "horizon";
  state: FlightRecordState;
  valueZh: string;
  valueEn: string;
  detailZh: string;
  detailEn: string;
}

const isActiveStage = (missionState: string, ids: readonly string[]) => ids.includes(missionState);
const recordState = (complete: boolean, active: boolean): FlightRecordState => complete ? "complete" : active ? "active" : "waiting";

/**
 * A read-only bridge ledger.  It derives every item from registered local
 * artifacts and never promotes an empty stage or installed capability to work
 * that has actually run.
 */
export function missionFlightRecorder(bundle: ImportedBundle, pdfTask: PdfTaskStatus | null): FlightRecordEntry[] {
  const missionState = bundle.status?.missionState ?? "LOCAL";
  const paperCount = reviewablePaperCount(bundle);
  const parsed = Boolean(pdfTask?.markdown_ready && pdfTask.audit_state === "done");
  const parseFailed = pdfTask?.state === "failed";
  const sourceCount = bundle.sourceMapSummary.segmentCount;
  const factCount = bundle.materialFactSummary.factCount;
  const evidenceCount = auditableAcceptedEvidence(bundle).length;
  const gapCount = bundle.researchGapCandidates.filter((candidate) => hasAuditableGapEvidenceBasis(candidate, bundle)).length;
  const extractActive = isActiveStage(missionState, ["EXTRACT"]);
  const evidenceActive = isActiveStage(missionState, ["VERIFY", "HUMAN_REVIEW"]);
  const horizonActive = isActiveStage(missionState, ["HAZARD_SCAN", "REPORT"]);

  return [
    {
      id: "brief", state: recordState(bundle.stations.length > 0, isActiveStage(missionState, ["LOCAL", "INTAKE", "NEED_SCOPE", "PLAN"])),
      valueZh: bundle.stations.length ? `${bundle.stations.length} 个任务站点` : "待登记", valueEn: bundle.stations.length ? `${bundle.stations.length} mission station(s)` : "pending",
      detailZh: "问题、对象与比较边界只作为任务简报，不是检索或科学结论。", detailEn: "Question, object, and comparison scope are a mission brief only, not retrieval or a scientific conclusion.",
    },
    {
      id: "candidates", state: recordState(paperCount > 0, isActiveStage(missionState, ["PLAN", "RETRIEVE", "SELECT", "MAP"])),
      valueZh: paperCount ? `${paperCount} 篇可审查文献` : "待获取", valueEn: paperCount ? `${paperCount} reviewable paper(s)` : "awaiting retrieval",
      detailZh: paperCount ? "候选书目与书目关系可供导航，但本身不构成材料证据。" : "受控检索或本地导入尚未登记可审查文献。", detailEn: paperCount ? "Candidate records and bibliographic links are navigable, but are not materials evidence." : "No reviewable paper has been registered through controlled retrieval or local import.",
    },
    {
      id: "fulltext", state: parseFailed ? "blocked" : recordState(parsed, Boolean(pdfTask) && !parsed),
      valueZh: parseFailed ? "解析失败" : parsed ? "私有 Markdown 已就绪" : pdfTask ? "解析中" : "未选择授权 PDF", valueEn: parseFailed ? "parse failed" : parsed ? "private Markdown ready" : pdfTask ? "parsing" : "no authorised PDF",
      detailZh: parseFailed ? "失败不会生成来源定位、材料事实或 EvidenceCard。" : parsed ? "全文只保留在本机私有缓存，需人工挑选必要短片段。" : "只有与人工纳入候选匹配的授权 PDF 可继续进入私有解析。", detailEn: parseFailed ? "Failure creates no source locator, material fact, or EvidenceCard." : parsed ? "Full text remains in local private cache; a human must choose necessary short excerpts." : "Only an authorised PDF matched to a human-included candidate may enter private parsing.",
    },
    {
      id: "source-map", state: sourceCount > 0 ? "complete" : parseFailed ? "blocked" : recordState(false, extractActive && parsed),
      valueZh: sourceCount ? `${sourceCount} 条来源定位` : "待人工定位", valueEn: sourceCount ? `${sourceCount} source locator(s)` : "human location pending",
      detailZh: sourceCount ? "仅登记短引文与定位符；不将全文传入界面工件。" : "需先在私有 Markdown 中人工核对定位符和必要短引文。", detailEn: sourceCount ? "Only short excerpts and locators are registered; full text does not enter UI artifacts." : "First verify locators and necessary short excerpts in private Markdown.",
    },
    {
      id: "facts", state: recordState(factCount > 0, extractActive && sourceCount > 0),
      valueZh: factCount ? `${factCount} 条材料事实` : "待条件化登记", valueEn: factCount ? `${factCount} material fact(s)` : "conditional registration pending",
      detailZh: factCount ? "事实仍是受来源片段约束的观察，不是 EvidenceCard 或科学结论。" : "每条事实必须绑定已审核片段，并显式记录限定条件。", detailEn: factCount ? "Facts remain source-bound observations, not EvidenceCards or scientific conclusions." : "Each fact must bind a reviewed excerpt and record qualifiers explicitly.",
    },
    {
      id: "evidence", state: recordState(evidenceCount > 0, evidenceActive && sourceCount > 0),
      valueZh: evidenceCount ? `${evidenceCount} 张 EvidenceCard` : "待人工接受", valueEn: evidenceCount ? `${evidenceCount} EvidenceCard(s)` : "human acceptance pending",
      detailZh: evidenceCount ? "已接受卡片仍受当前论文、来源定位与条件字段约束。" : "必须人工核对主张、条件和来源片段后才可接受。", detailEn: evidenceCount ? "Accepted cards remain bound to the current paper, source locator, and condition fields." : "A human must verify claim, conditions, and source excerpt before acceptance.",
    },
    {
      id: "horizon", state: recordState(gapCount > 0, horizonActive && evidenceCount > 0),
      valueZh: gapCount ? `${gapCount} 个 Gap 候选` : "待证据约束", valueEn: gapCount ? `${gapCount} Gap candidate(s)` : "evidence-bounded candidate pending",
      detailZh: gapCount ? "候选仍需检查反例边界与人工审核，不能自动视为研究结论。" : "只有已接受证据、条件差异和反例边界齐备后才可生成候选。", detailEn: gapCount ? "Candidates still require counterevidence-boundary checks and human review; they are not conclusions." : "Candidates require accepted evidence, condition differences, and a counterevidence boundary.",
    },
  ];
}
