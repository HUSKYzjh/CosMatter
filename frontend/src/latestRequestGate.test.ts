import { describe, expect, it } from "vitest";

import { createLatestRequestGate } from "./latestRequestGate";

describe("latest request gate", () => {
  it("rejects an older response for the same logical task", () => {
    const gate = createLatestRequestGate();
    const first = gate.begin();
    const second = gate.begin();
    expect(first()).toBe(false);
    expect(second()).toBe(true);
  });

  it("invalidates an in-flight response when its task is superseded", () => {
    const gate = createLatestRequestGate();
    const pending = gate.begin();
    gate.invalidate();
    expect(pending()).toBe(false);
  });
});
