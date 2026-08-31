import { describe, expect, it } from "vitest";

import { automaticGraphHandoffAlreadySettled, automaticGraphHandoffTarget } from "./automaticGraphHandoff";

describe("automaticGraphHandoffTarget", () => {
  it("waits for the bridge when retrieval finishes during launch", () => {
    expect(automaticGraphHandoffTarget(true, "succeeded", "discover", true)).toBeNull();
    expect(automaticGraphHandoffTarget(true, "succeeded", "workflow", true)).toBe("graph");
  });

  it("does not hand off failed, cancelled, empty, or non-pending tasks", () => {
    expect(automaticGraphHandoffTarget(true, "failed", "workflow", true)).toBeNull();
    expect(automaticGraphHandoffTarget(true, "cancelled", "workflow", true)).toBeNull();
    expect(automaticGraphHandoffTarget(true, "succeeded", "workflow", false)).toBeNull();
    expect(automaticGraphHandoffTarget(false, "succeeded", "workflow", true)).toBeNull();
  });

  it("settles a one-time handoff when the researcher already opened the graph", () => {
    expect(automaticGraphHandoffAlreadySettled(true, "succeeded", "graph", true)).toBe(true);
    expect(automaticGraphHandoffAlreadySettled(true, "succeeded", "workflow", true)).toBe(false);
    expect(automaticGraphHandoffAlreadySettled(true, "succeeded", "graph", false)).toBe(false);
  });
});
