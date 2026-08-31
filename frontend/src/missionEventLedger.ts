import type { ImportedBundle, TimelineEntry } from "./model";

export type MissionEventState = "complete" | "active" | "waiting" | "blocked";
export interface MissionEventLedgerEntry extends TimelineEntry { stateClass: MissionEventState; ordinal: number; }

const terminal = (value: string) => /done|complete|recorded|accept|report|success/i.test(value);
const blocked = (value: string) => /fail|error|cancel|block|reject/i.test(value);
const active = (value: string) => /active|running|review|process|queue/i.test(value);

/** Preserves source order while exposing only recorded, bounded timeline entries. */
export function missionEventLedger(bundle: ImportedBundle, limit = 10): MissionEventLedgerEntry[] {
  const boundedLimit = Math.max(1, Math.min(24, Math.floor(limit)));
  return bundle.timeline.slice(-boundedLimit).reverse().map((entry, index) => ({
    ...entry,
    ordinal: bundle.timeline.length - index,
    stateClass: blocked(entry.state) ? "blocked" : terminal(entry.state) ? "complete" : active(entry.state) ? "active" : "waiting",
  }));
}
