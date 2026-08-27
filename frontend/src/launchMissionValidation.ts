export interface LaunchMissionBoundary {
  question: string;
  material: string;
  property: string;
  scope: string;
}

export type LaunchMissionField = keyof LaunchMissionBoundary;

const PLACEHOLDER_PATTERNS = [
  /待人工确认/u, /待由.+规范化/u, /待确认/u, /未指定/u, /待补充/u,
  /inferred from the prompt/i, /normalize after source location/i, /confirm manually/i,
  /not specified/i, /to be confirmed/i, /to be completed/i,
];

/**
 * A launch candidate remains only an untrusted suggestion until every task
 * boundary is explicit. This check deliberately rejects the visible fallback
 * placeholders rather than allowing them to become retrieval filters.
 */
export function launchMissionMissingFields(mission: LaunchMissionBoundary): LaunchMissionField[] {
  return (Object.keys(mission) as LaunchMissionField[]).filter((field) => {
    const value = mission[field].trim();
    return !value || PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(value));
  });
}

export function isLaunchMissionReady(mission: LaunchMissionBoundary): boolean {
  return launchMissionMissingFields(mission).length === 0;
}
