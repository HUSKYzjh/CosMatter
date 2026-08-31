import { describe, expect, it } from "vitest";

import { automaticCancellationEnabled } from "./automaticCancellation";

describe("automatic cancellation control", () => {
  it("only exposes cancellation for a live queued or running automatic mission", () => {
    expect(automaticCancellationEnabled(false, "run_001", "queued", false)).toBe(true);
    expect(automaticCancellationEnabled(false, "run_001", "running", false)).toBe(true);
  });

  it("keeps previews, terminal states, missing runs, and an already-recorded request non-actionable", () => {
    expect(automaticCancellationEnabled(true, "run_001", "running", false)).toBe(false);
    expect(automaticCancellationEnabled(false, null, "running", false)).toBe(false);
    expect(automaticCancellationEnabled(false, "run_001", "succeeded", false)).toBe(false);
    expect(automaticCancellationEnabled(false, "run_001", "failed", false)).toBe(false);
    expect(automaticCancellationEnabled(false, "run_001", "cancelled", false)).toBe(false);
    expect(automaticCancellationEnabled(false, "run_001", "queued", true)).toBe(false);
  });
});
