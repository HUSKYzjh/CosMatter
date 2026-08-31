import { describe, expect, it } from "vitest";

import { previewAllowsRunAction } from "./previewExecutionPolicy";

describe("previewAllowsRunAction", () => {
  it("withholds local-run actions from read-only previews even when a run exists", () => {
    expect(previewAllowsRunAction(true, "run-live")).toBe(false);
    expect(previewAllowsRunAction(false, "run-live")).toBe(true);
    expect(previewAllowsRunAction(false, null)).toBe(false);
  });
});
