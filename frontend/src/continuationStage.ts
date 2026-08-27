export type ContinuationView = "workflow" | "graph";

/**
 * A run package never restores ephemeral browser paper selection. Once its
 * audited readiness has reached human screening, reopen the literature map so
 * the researcher consciously selects the next document rather than landing
 * in an apparently ready reader.
 */
export function continuationStageLabel(stage: string | null | undefined, locale: "zh" | "en"): string {
  const labels: Record<string, readonly [string, string]> = {
    plan: ["计划人工复核", "plan review"],
    retrieval: ["受控检索", "controlled retrieval"],
    screening: ["候选筛选", "candidate screening"],
    parse: ["全文解析", "full-text parsing"],
    extraction: ["事实抽取", "fact extraction"],
    gap: ["Gap 候选核查", "Gap candidate review"],
    report: ["调研报告", "research report"],
    evaluation: ["评测与审计", "evaluation and audit"],
  };
  const key = (stage ?? "").trim().toLowerCase();
  return labels[key]?.[locale === "zh" ? 0 : 1] ?? (locale === "zh" ? "受控编排" : "controlled orchestration");
}

export function viewForRestoredRun(stage: string | null | undefined, artifactsHydrated: boolean): ContinuationView {
  return artifactsHydrated ? viewForContinuationStage(stage) : "workflow";
}

export function viewForContinuationStage(stage: string | null | undefined): ContinuationView {
  switch ((stage ?? "").trim().toLowerCase()) {
    case "screening":
    case "parse":
    case "extraction":
    case "gap":
    case "report":
    case "evaluation":
    // Accept earlier package vocabulary while preserving the same safe entry.
    case "map":
    case "select":
    case "extract":
    case "verify":
    case "human_review":
    case "extend":
      return "graph";
    default:
      return "workflow";
  }
}
