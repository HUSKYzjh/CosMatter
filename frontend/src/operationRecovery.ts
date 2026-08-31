export type OperationRecoveryKind = "automatic" | "cancellation" | "citation" | "candidate_pdf" | "task_start" | "plan" | "query";
export type OperationRecovery = {
  view: "discover" | "workflow" | "graph";
  zh: string;
  en: string;
  contextZh: string;
  contextEn: string;
};

/** Recovery links navigate to a review surface only; none retries an operation. */
export function operationRecovery(kind: OperationRecoveryKind): OperationRecovery {
  switch (kind) {
    case "candidate_pdf":
      return {
        view: "graph",
        zh: "返回文献星图核验候选与 PDF",
        en: "Return to the literature map to verify the candidate and PDF",
        contextZh: "核验候选条目、PDF 任务和来源工件是否已经登记；不重新上传或解析。",
        contextEn: "Verify whether the candidate, PDF task, and source artifacts were recorded; do not re-upload or parse again.",
      };
    case "citation":
      return {
        view: "workflow",
        zh: "打开舰桥查看本地运行状态",
        en: "Open the bridge to inspect local run status",
        contextZh: "核验本机运行状态和调度审计是否已记录引文图；不重新发起构建。",
        contextEn: "Check local run state and dispatch audit for a recorded citation map; do not build it again.",
      };
    case "automatic":
      return {
        view: "workflow",
        zh: "打开舰桥查看本地运行状态",
        en: "Open the bridge to inspect local run status",
        contextZh: "核验任务壳与调度审计是否已登记；不自动重试外部检索。",
        contextEn: "Check whether the mission shell and dispatch audit were recorded; no external retrieval is retried automatically.",
      };
    case "cancellation":
      return {
        view: "workflow",
        zh: "打开舰桥查看本地运行状态",
        en: "Open the bridge to inspect local run status",
        contextZh: "核验取消标记和当前运行态；不重复提交取消请求。",
        contextEn: "Check the cancellation marker and current run state; do not submit cancellation again.",
      };
    case "task_start":
      return {
        view: "discover",
        zh: "打开手动受控审核",
        en: "Open controlled task review",
        contextZh: "核验是否已创建本地任务壳，再决定是否由研究者新建任务。",
        contextEn: "Check whether a local mission shell was created before deciding whether the researcher should start a new one.",
      };
    case "plan":
      return {
        view: "discover",
        zh: "打开手动受控审核",
        en: "Open controlled task review",
        contextZh: "核验当前任务、计划草案与审批记录；不重复提交同一计划。",
        contextEn: "Check the current mission, plan draft, and approval record; do not resubmit the same plan.",
      };
    case "query":
      return {
        view: "discover",
        zh: "打开手动受控审核",
        en: "Open controlled task review",
        contextZh: "核验本机调度审计和提供方状态，再由研究者决定是否创建新调用。",
        contextEn: "Check the local dispatch audit and provider status before the researcher decides whether to create a new call.",
      };
  }
}
