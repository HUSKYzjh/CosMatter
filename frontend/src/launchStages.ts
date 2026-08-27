export type LaunchMode = "question" | "pdf" | "resume";
export type LaunchPreviewStage = "discover" | "workflow" | "graph" | "reader" | "horizon";

export interface LaunchStage {
  id: LaunchPreviewStage;
  zh: string;
  en: string;
  inputZh: string;
  inputEn: string;
  outputZh: string;
  outputEn: string;
  gateZh: string;
  gateEn: string;
}

export const LAUNCH_STAGES: readonly LaunchStage[] = [
  { id: "discover", zh: "任务定义", en: "Task definition", inputZh: "问题、对象与比较边界", inputEn: "Question, objects, and comparison boundary", outputZh: "任务简报", outputEn: "Mission brief", gateZh: "需人工确认", gateEn: "Human confirmation required" },
  { id: "workflow", zh: "受控编排", en: "Controlled orchestration", inputZh: "已确认任务与授权范围", inputEn: "Confirmed task and authorization", outputZh: "检索计划", outputEn: "Retrieval plan", gateZh: "计划与数据源待核准", gateEn: "Plan and sources require approval" },
  { id: "graph", zh: "文献星图", en: "Literature map", inputZh: "候选文献与书目信息", inputEn: "Candidate literature and bibliography", outputZh: "可审查文献子图", outputEn: "Reviewable literature subgraph", gateZh: "书目关系不是科学证据", gateEn: "Bibliographic links are not evidence" },
  { id: "reader", zh: "证据核对", en: "Evidence verification", inputZh: "选中文献或私有 Markdown", inputEn: "Selected paper or private Markdown", outputZh: "来源定位与待审核 EvidenceCard", outputEn: "Source locator and review-pending EvidenceCard", gateZh: "需来源定位与人工审核", gateEn: "Locator and human review required" },
  { id: "horizon", zh: "研究拓展", en: "Research extension", inputZh: "已接受 EvidenceCard 与条件矛盾", inputEn: "Accepted EvidenceCards and condition conflicts", outputZh: "待核对 Gap 候选", outputEn: "Review-pending Gap candidates", gateZh: "候选不等于科学结论", gateEn: "Candidates are not conclusions" },
] as const;

export function stageForLaunchMode(mode: LaunchMode): LaunchPreviewStage {
  if (mode === "pdf") return "reader";
  if (mode === "resume") return "workflow";
  return "discover";
}

export function launchModeStatus(mode: LaunchMode, locale: "zh" | "en"): string {
  const status = mode === "question"
    ? ["问题入口：确认后进入受控编排。", "Question entry: confirmation leads to controlled orchestration."]
    : mode === "pdf"
      ? ["PDF 入口：私有解析后进入来源定位。", "PDF entry: private parsing leads to source location."]
      : ["续航入口：校验运行包后恢复首个可执行阶段。", "Resume entry: validation restores the first executable stage."];
  return status[locale === "zh" ? 0 : 1];
}