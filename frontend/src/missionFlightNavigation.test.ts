import { describe, expect, it } from "vitest";

import { flightRecordDestination } from "./missionFlightNavigation";

const empty = { paperCount: 0, hasReviewContext: false, hasEvidence: false, hasGapCandidate: false };

describe("mission flight navigation", () => {
  it("keeps unavailable stations non-navigable", () => {
    expect(flightRecordDestination("candidates", empty)).toBeNull();
    expect(flightRecordDestination("source-map", empty)).toBeNull();
    expect(flightRecordDestination("horizon", empty)).toBeNull();
  });

  it("routes only to local workbenches supported by registered context", () => {
    expect(flightRecordDestination("brief", empty)).toBe("discover");
    expect(flightRecordDestination("candidates", { ...empty, paperCount: 1 })).toBe("graph");
    expect(flightRecordDestination("facts", { ...empty, hasReviewContext: true })).toBe("reader");
    expect(flightRecordDestination("horizon", { ...empty, hasEvidence: true })).toBe("horizon");
  });
});
