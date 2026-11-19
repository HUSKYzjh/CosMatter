export interface LaunchMissionBoundary {
  question: string;
  material: string;
  property: string;
  scope: string;
}

export type LaunchMissionField = keyof LaunchMissionBoundary;

export const UNCONFIRMED_RESEARCH_OBJECT = {
  zh: "输入中的研究对象，待人工确认",
  en: "Research object in the prompt; confirm manually",
} as const;

const PLACEHOLDER_VALUES = new Set([
  "待人工确认", "待确认", "未指定", "待补充", "待由来源定位后规范化", "由输入问题识别，待人工确认",
  "inferred from the prompt", "inferred from the prompt; confirm manually", "normalize after source location",
  "confirm manually", "not specified", "to be confirmed", "to be completed",
  ...Object.values(UNCONFIRMED_RESEARCH_OBJECT),
].map(value => value.toLowerCase()));

/**
 * A launch candidate remains only an untrusted suggestion until every task
 * boundary is explicit. This check deliberately rejects the visible fallback
 * placeholders rather than allowing them to become retrieval filters.
 */
export function launchMissionMissingFields(mission: LaunchMissionBoundary): LaunchMissionField[] {
  return (["question", "material", "property", "scope"] as const).filter((field) => {
    const value = mission[field].trim().toLowerCase().replace(/[。.!！?？]+$/u, "").trimEnd();
    if (!value || PLACEHOLDER_VALUES.has(value)) return true;
    // The local generator also inserts its unconfirmed material directly in each proposed question.
    return field === "question" && Object.values(UNCONFIRMED_RESEARCH_OBJECT).some(label => value.includes(label.toLowerCase()));
  });
}

export function isLaunchMissionReady(mission: LaunchMissionBoundary): boolean {
  return launchMissionMissingFields(mission).length === 0;
}
