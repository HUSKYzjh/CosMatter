import { describe, expect, it } from "vitest";

import { ambientIndexFromSessionValue } from "./FleetDecoration";

describe("ambient session storage boundary", () => {
  it("uses only a valid numeric asset index", () => {
    expect(ambientIndexFromSessionValue("3", 5, () => 0)).toBe(3);
    expect(ambientIndexFromSessionValue("-1", 5, () => .6)).toBe(3);
    expect(ambientIndexFromSessionValue("3private-markdown", 5, () => .2)).toBe(1);
    expect(ambientIndexFromSessionValue("5", 5, () => .8)).toBe(4);
  });
});
