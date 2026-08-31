import { FLEETS, type FleetRecord } from "./fleetRegistry";
import type { ImportedBundle } from "./model";

export type FleetRouteState = "active" | "next" | "standby" | "framework";

export interface FleetRouteEntry {
  fleet: FleetRecord;
  state: FleetRouteState;
  stageCount: number;
  detailZh: string;
  detailEn: string;
}

const operationalFleetIds = ["pioneer", "observatory", "constellation", "diagnostics", "sentinel", "horizon", "synthesis"] as const;
const frameworkFleetIds = ["dft", "potential", "dynamics"] as const;
const stageFleetIds: Record<string, readonly string[]> = {
  LOCAL: ["pioneer"], INTAKE: ["pioneer"], NEED_SCOPE: ["pioneer"],
  PLAN: ["pioneer", "observatory"], RETRIEVE: ["observatory"], SELECT: ["observatory"], EXTRACT: ["observatory", "sentinel"],
  MAP: ["constellation"], HAZARD_SCAN: ["diagnostics", "sentinel"], VERIFY: ["sentinel"], HUMAN_REVIEW: ["sentinel"], REPORT: ["horizon"],
};
const route = ["LOCAL", "INTAKE", "NEED_SCOPE", "PLAN", "RETRIEVE", "SELECT", "EXTRACT", "MAP", "HAZARD_SCAN", "VERIFY", "HUMAN_REVIEW", "REPORT"] as const;

const fleetById = (id: string) => FLEETS.find((fleet) => fleet.id === id)!;
const waitingCopy = (fleet: FleetRecord) => ({
  detailZh: `${fleet.zh}保留在待命编队中；不会在未到达其阶段时启动工具或外部操作。`,
  detailEn: `${fleet.en} remains in the standby formation; no tool or external operation starts before its stage is reached.`,
});

/**
 * Derives the bridge route from the registered mission state only.  This is a
 * coordination view: it never treats installed capability as an active run.
 */
export function fleetOrchestration(bundle: ImportedBundle): FleetRouteEntry[] {
  const missionState = bundle.status?.missionState ?? "LOCAL";
  const currentIndex = Math.max(0, route.indexOf(missionState as typeof route[number]));
  const activeIds = new Set(stageFleetIds[missionState] ?? []);
  const nextIds = new Set<string>();
  for (let index = currentIndex + 1; index < route.length && nextIds.size === 0; index += 1) {
    for (const fleetId of stageFleetIds[route[index]]) if (!activeIds.has(fleetId)) nextIds.add(fleetId);
  }

  const operational = operationalFleetIds.map((id) => {
    const fleet = fleetById(id);
    if (activeIds.has(id)) return {
      fleet, state: "active" as const, stageCount: 1,
      detailZh: `当前阶段 ${missionState} 已将该舰队纳入任务编排；产物仍须通过旗舰门禁登记。`,
      detailEn: `The current ${missionState} stage includes this fleet in the mission plan; outputs still require flagship-gate registration.`,
    };
    if (nextIds.has(id)) return {
      fleet, state: "next" as const, stageCount: 1,
      detailZh: `下一交接将移交至该舰队；它尚未执行，也不会预先调用工具。`,
      detailEn: `The next handoff is routed to this fleet. It has not run and no tool is pre-invoked.`,
    };
    if (id === "synthesis") return {
      fleet, state: "standby" as const, stageCount: 0,
      detailZh: "仅在已审核 Research Gap 需要转为实验验证计划时，由研究者显式启用；不会自动设计或执行实验。",
      detailEn: "Available only when a reviewed Research Gap is explicitly turned into an experimental validation plan; it never designs or executes experiments automatically.",
    };
    return { fleet, state: "standby" as const, stageCount: 0, ...waitingCopy(fleet) };
  });

  const frameworks = frameworkFleetIds.map((id) => {
    const fleet = fleetById(id);
    return {
      fleet, state: "framework" as const, stageCount: 0,
      detailZh: `${fleet.zh}当前仅提供任务与审计模板，未接入执行引擎。`,
      detailEn: `${fleet.en} currently provides task and audit templates only; no execution engine is connected.`,
    };
  });
  return [...operational, ...frameworks];
}
