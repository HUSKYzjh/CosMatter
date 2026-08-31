import { describe, expect, it } from "vitest";

import { isLocalApiStatus, LOCAL_API_READ_TIMEOUT_MS, LOCAL_API_WRITE_TIMEOUT_MS, LocalApiRequestError, localApiHttpFailure, localApiTimeoutFailure } from "./localApi";

describe("local API request boundary", () => {
  it("distinguishes safe read timeouts from writes with an unknown outcome", () => {
    expect(localApiTimeoutFailure()).toBe("read_timeout");
    expect(localApiTimeoutFailure("GET")).toBe("read_timeout");
    expect(localApiTimeoutFailure("POST")).toBe("write_outcome_unknown");
    expect(localApiTimeoutFailure("PATCH")).toBe("write_outcome_unknown");
  });

  it("keeps finite, risk-calibrated timeout budgets and neutral error data", () => {
    expect(LOCAL_API_READ_TIMEOUT_MS).toBeGreaterThan(0);
    expect(LOCAL_API_WRITE_TIMEOUT_MS).toBeGreaterThan(LOCAL_API_READ_TIMEOUT_MS);
    expect(new LocalApiRequestError("write_outcome_unknown").failure).toBe("write_outcome_unknown");
  });

  it("treats a received write 5xx as an unknown outcome but not a validated client rejection", () => {
    expect(localApiHttpFailure("POST", 500)).toBe("write_outcome_unknown");
    expect(localApiHttpFailure("POST", 503)).toBe("write_outcome_unknown");
    expect(localApiHttpFailure("POST", 409)).toBe("transport");
    expect(localApiHttpFailure("GET", 500)).toBe("transport");
  });

  it("fails closed unless the capability snapshot has the fixed boolean-only surface", () => {
    const status = { api_mode: "loopback_only", providers: { deepseek: true, sciverse: true, mineru: false, openalex: true, crossref: true, crossref_polite_contact: false } };
    expect(isLocalApiStatus(status)).toBe(true);
    expect(isLocalApiStatus({ ...status, providers: { ...status.providers, token: true } })).toBe(false);
    expect(isLocalApiStatus({ ...status, providers: { ...status.providers, sciverse: "configured" } })).toBe(false);
  });
});
