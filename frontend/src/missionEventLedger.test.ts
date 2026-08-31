import { describe, expect, it } from "vitest";

import { missionEventLedger } from "./missionEventLedger";
import { demoBundle, type ImportedBundle } from "./model";

const withTimeline = (timeline: ImportedBundle["timeline"]): ImportedBundle => ({ ...demoBundle, timeline });

describe("mission event ledger", () => {
  it("keeps the latest recorded events in reverse chronological source order", () => {
    const entries = missionEventLedger(withTimeline([
      { stationType: "PLAN", action: "plan approved", state: "done", occurredAt: "2026-01-01T00:00:00Z" },
      { stationType: "RETRIEVE", action: "query queued", state: "queued", occurredAt: "2026-01-02T00:00:00Z" },
      { stationType: "EXTRACT", action: "parse failed", state: "failed", occurredAt: "2026-01-03T00:00:00Z" },
    ]));
    expect(entries.map((entry) => entry.action)).toEqual(["parse failed", "query queued", "plan approved"]);
    expect(entries.map((entry) => entry.stateClass)).toEqual(["blocked", "active", "complete"]);
  });

  it("does not fabricate events for a mission without a recorded timeline", () => {
    expect(missionEventLedger(withTimeline([]))).toEqual([]);
  });

  it("bounds the displayed history without altering recorded event content", () => {
    const entries = missionEventLedger(withTimeline(Array.from({ length: 14 }, (_, index) => ({ stationType: `S${index}`, action: `event ${index}`, state: "waiting", occurredAt: "" }))), 3);
    expect(entries).toHaveLength(3);
    expect(entries.map((entry) => entry.action)).toEqual(["event 13", "event 12", "event 11"]);
  });
});
