import type { FacilityContractManifest } from "./localApi";
import type { ImportedBundle } from "./model";

export interface FacilityContractDeckItem {
  facilityType: string;
  labelZh: string;
  labelEn: string;
  status: string;
  inputSchema: string[];
  outputSchema: string[];
  failureModes: string[];
  humanReviewRequired: boolean;
}

export interface FacilityContractCoverage {
  assignedCount: number;
  mappedCount: number;
  unmappedCount: number;
  humanReviewCount: number;
}

/** Fixed user-facing names for the closed local facility catalogue. */
const FACILITY_LABELS: Readonly<Record<string, { labelZh: string; labelEn: string }>> = {
  sector_cartography: { labelZh: "文献星图测绘仪", labelEn: "Literature Cartography" },
  timeline_observatory: { labelZh: "任务时间线观测台", labelEn: "Timeline Observatory" },
  citation_array: { labelZh: "引文关系阵列", labelEn: "Citation Array" },
  source_locator: { labelZh: "来源定位器", labelEn: "Source Locator" },
  evidence_comparator: { labelZh: "证据比较台", labelEn: "Evidence Comparator" },
  condition_recorder: { labelZh: "条件记录仪", labelEn: "Condition Recorder" },
  trajectory_overlay: { labelZh: "航迹叠加仪", labelEn: "Trajectory Overlay" },
  condition_differential: { labelZh: "条件差分舱", labelEn: "Condition Differential" },
  counterevidence_detector: { labelZh: "反证探测器", labelEn: "Counterevidence Detector" },
  blind_spot_scan: { labelZh: "盲点扫描仪", labelEn: "Blind-spot Scanner" },
  variable_combination_scan: { labelZh: "变量组合扫描仪", labelEn: "Variable Combination Scanner" },
  hypothesis_triage: { labelZh: "假设分诊器", labelEn: "Hypothesis Triage" },
  experiment_mission_design: { labelZh: "实验验证任务设计器", labelEn: "Experimental Mission Designer" },
  computation_mission_design: { labelZh: "计算验证任务设计器", labelEn: "Computational Mission Designer" },
  falsification_monitor: { labelZh: "证伪监测器", labelEn: "Falsification Monitor" },
};

const safeTextList = (value: unknown, limit: number) => Array.isArray(value)
  && value.length > 0
  && value.length <= limit
  && value.every((item) => typeof item === "string" && item.length > 0 && item.length <= 80)
  ? [...value] as string[] : null;

/** Join only fixed local catalogue entries to the current mission's facilities. */
export function facilityContractDeck(
  facilities: ImportedBundle["facilities"],
  contracts: FacilityContractManifest[] | null,
): FacilityContractDeckItem[] {
  if (!contracts || contracts.length > 15 || new Set(contracts.map((item) => item.facility_type)).size !== contracts.length) return [];
  const byType = new Map<string, FacilityContractDeckItem>();
  for (const contract of contracts) {
    const inputSchema = safeTextList(contract.input_schema, 8);
    const outputSchema = safeTextList(contract.output_schema, 8);
    const failureModes = safeTextList(contract.failure_modes, 8);
    const labels = typeof contract.facility_type === "string" ? FACILITY_LABELS[contract.facility_type] : undefined;
    if (!labels || contract.facility_type.length === 0 || contract.facility_type.length > 80 || contract.execution_boundary !== "static_contract_only_not_execution_authorization" || !inputSchema || !outputSchema || !failureModes || typeof contract.human_review_required !== "boolean") continue;
    byType.set(contract.facility_type, { facilityType: contract.facility_type, ...labels, status: "", inputSchema, outputSchema, failureModes, humanReviewRequired: contract.human_review_required });
  }
  return facilities.flatMap((facility) => {
    const contract = byType.get(facility.facilityType);
    return contract ? [{ ...contract, status: facility.status.slice(0, 80) }] : [];
  });
}

/** Summarise the current mission's visible contract coverage without inferring execution. */
export function facilityContractCoverage(
  facilities: ImportedBundle["facilities"],
  deck: FacilityContractDeckItem[],
): FacilityContractCoverage {
  return {
    assignedCount: facilities.length,
    mappedCount: deck.length,
    unmappedCount: Math.max(0, facilities.length - deck.length),
    humanReviewCount: deck.filter((item) => item.humanReviewRequired).length,
  };
}
