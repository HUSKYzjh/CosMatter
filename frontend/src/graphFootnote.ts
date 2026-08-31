export interface GraphFootnoteInput {
  locale: "zh" | "en";
  hasCitationMap: boolean;
  bibliographyCount: number;
  paperLikeNodeCount: number;
  reviewablePaperCount: number;
  visibleEdgeCount: number;
}

/** Describe visible map records without promoting navigation or demo nodes to reviewable papers. */
export function graphFootnote(input: GraphFootnoteInput): string {
  const x = (zh: string, en: string) => input.locale === "zh" ? zh : en;
  if (input.hasCitationMap && input.reviewablePaperCount === 0) {
    return x(`当前显示 ${input.bibliographyCount} 个书目条目、${input.visibleEdgeCount} 条引文关系。`, `Showing ${input.bibliographyCount} bibliographic entries and ${input.visibleEdgeCount} citation relations.`);
  }
  if (input.paperLikeNodeCount > 0 && input.reviewablePaperCount === 0) {
    return x(`当前显示 ${input.paperLikeNodeCount} 个仅供导航或演示的论文式节点；它们没有当前任务可审核的 document ID，不能用于人工筛选、全文处理或 EvidenceCard。`, `Showing ${input.paperLikeNodeCount} paper-like navigation or demo node(s). They have no reviewable document ID for this mission and cannot enter screening, full-text work, or EvidenceCard review.`);
  }
  if (input.paperLikeNodeCount > input.reviewablePaperCount) {
    return x(`当前显示 ${input.paperLikeNodeCount} 个论文式节点，其中 ${input.reviewablePaperCount} 篇可审查；其余仅供导航或演示。可见关系 ${input.visibleEdgeCount} 条。`, `Showing ${input.paperLikeNodeCount} paper-like node(s), including ${input.reviewablePaperCount} reviewable paper(s); the rest are navigation or demo records. ${input.visibleEdgeCount} relation(s) are visible.`);
  }
  return x(`当前显示 ${input.reviewablePaperCount} 篇可审查论文、${input.visibleEdgeCount} 条可见关系。`, `Showing ${input.reviewablePaperCount} reviewable paper(s) and ${input.visibleEdgeCount} visible relation(s).`);
}
