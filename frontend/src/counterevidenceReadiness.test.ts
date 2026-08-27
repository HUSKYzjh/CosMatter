import { describe, expect, it } from "vitest";

import { counterevidenceReadiness } from "./counterevidenceReadiness";
import { demoBundle, readBundle } from "./model";

describe("counterevidenceReadiness", () => {
  it("blocks comparison when no approved counterevidence plan is projected", () => {
    const readiness = counterevidenceReadiness(demoBundle);
    expect(readiness.ready).toBe(false);
    expect(readiness.nextAction).toContain("批准");
  });

  it("reports aggregate execution progress without query text", () => {
    const bundle = readBundle({ mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" }, audit_summary: { counterevidence: { state: "awaiting_counterevidence_execution", planned_query_count: 2, executed_query_count: 1 } } });
    expect(counterevidenceReadiness(bundle)).toMatchObject({ ready: false, plannedQueryCount: 2, executedQueryCount: 1 });
  });

  it("unlocks only an explicitly ready counterevidence boundary", () => {
    const bundle = readBundle({ mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" }, audit_summary: { counterevidence: { state: "ready", planned_query_count: 1, executed_query_count: 1 } } });
    expect(counterevidenceReadiness(bundle).ready).toBe(true);
  });
});
