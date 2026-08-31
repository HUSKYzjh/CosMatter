import { describe, expect, it } from "vitest";

import { createExclusiveSubmissionGate } from "./exclusiveSubmissionGate";

describe("exclusive submission gate", () => {
  it("allows only one submission until the active request finishes", () => {
    const gate = createExclusiveSubmissionGate();
    expect(gate.tryStart()).toBe(true);
    expect(gate.tryStart()).toBe(false);
    gate.finish();
    expect(gate.tryStart()).toBe(true);
  });

  it("can be released after a failed request", () => {
    const gate = createExclusiveSubmissionGate();
    expect(gate.tryStart()).toBe(true);
    gate.finish();
    expect(gate.tryStart()).toBe(true);
  });
});
