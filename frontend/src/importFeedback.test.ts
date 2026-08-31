import { describe, expect, it } from "vitest";

import { safeImportFeedback, safeMutationFeedback, safeOperationFeedback } from "./importFeedback";

describe("safe import feedback", () => {
  const fallback = "Unable to validate the selected file.";
  const rejected = "The package did not pass integrity checks.";

  it("keeps the integrity category without echoing internal validation details", () => {
    expect(safeImportFeedback(new Error("run package artifact digest does not match"), fallback, rejected)).toBe(rejected);
  });

  it("does not surface paths, URLs, or credentials returned by an importer", () => {
    for (const message of ["C:\\Users\\Agent\\private.json", "https://provider.invalid/request", "Authorization: Bearer private-token"]) {
      expect(safeImportFeedback(new Error(message), fallback, rejected)).toBe(fallback);
    }
  });

  it("never reflects an untrusted provider or loopback error into an operation status", () => {
    expect(safeOperationFeedback(new Error("https://provider.invalid/?token=private"), fallback)).toBe(fallback);
    expect(safeOperationFeedback(new Error("provider response body"), fallback)).toBe(fallback);
  });

  it("does not claim that a timed-out local write did not happen", () => {
    const timeout = Object.assign(new Error("request timed out"), { failure: "write_outcome_unknown" });
    expect(safeMutationFeedback(timeout, "unchanged", "outcome unknown")).toBe("outcome unknown");
    expect(safeMutationFeedback(new Error("provider detail"), "unchanged", "outcome unknown")).toBe("unchanged");
  });
});
