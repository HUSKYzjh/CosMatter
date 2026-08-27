import type { ImportedBundle } from "./model";
import { zh } from "./zh";

export interface CounterevidenceReadiness {
  ready: boolean;
  plannedQueryCount: number;
  executedQueryCount: number;
  message: string;
  nextAction: string;
}

/** This is an operational UI gate, not evidence of a scientific conclusion. */
export function counterevidenceReadiness(bundle: ImportedBundle): CounterevidenceReadiness {
  const record = bundle.auditSummary.counterevidence;
  if (record.state === "ready") return { ready: true, plannedQueryCount: record.plannedQueryCount, executedQueryCount: record.executedQueryCount, message: "", nextAction: "" };
  if (record.state === "awaiting_counterevidence_execution") return { ready: false, plannedQueryCount: record.plannedQueryCount, executedQueryCount: record.executedQueryCount, message: zh("Every approved counterevidence query must run before condition comparison; candidate papers or a matrix alone do not attest this boundary.", "条件比较前，必须在已批准计划内完成每条反例检索；仅有候选文献或条件矩阵不足以证明该边界。"), nextAction: zh("Return to task control and run remaining counterevidence queries", "返回任务控制执行剩余反例检索") };
  return { ready: false, plannedQueryCount: 0, executedQueryCount: 0, message: zh("A human-reviewed plan with counterevidence queries is required before condition comparison; the system never infers a boundary from papers or Gap candidates.", "条件比较前，需要先人工批准含反例检索式的计划；系统不会从现有文献或 Gap 候选自动推断反例边界。"), nextAction: zh("Return to task control to approve and run counterevidence", "返回任务控制批准并执行反例检索") };
}
