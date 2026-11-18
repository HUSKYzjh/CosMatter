import { describe, expect, it, vi } from "vitest";

import { getStageContract, isLocalApiStatus, LOCAL_API_READ_TIMEOUT_MS, LOCAL_API_WRITE_TIMEOUT_MS, LocalApiRequestError, localApiHttpFailure, localApiTimeoutFailure } from "./localApi";

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

  it("keeps the short continuation timeout active through the response body", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("window", globalThis);
    vi.stubGlobal("fetch", async (_path: string, { signal }: RequestInit) => ({
      ok: true,
      json: () => new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(signal.reason), { once: true })),
    }));
    try {
      const outcome = expect(getStageContract("run_1", 10)).rejects.toMatchObject({ failure: "read_timeout" });
      await vi.advanceTimersByTimeAsync(10);
      await outcome;
    } finally {
      vi.unstubAllGlobals();
      vi.useRealTimers();
    }
  });

  it("treats a received write 5xx as an unknown outcome but not a validated client rejection", () => {
    expect(localApiHttpFailure("POST", 500)).toBe("write_outcome_unknown");
    expect(localApiHttpFailure("POST", 503)).toBe("write_outcome_unknown");
    expect(localApiHttpFailure("POST", 409)).toBe("transport");
    expect(localApiHttpFailure("GET", 500)).toBe("transport");
  });

  it("fails closed unless the capability snapshot has the fixed boolean-only surface", () => {
    const status = { api_mode: "loopback_only", providers: { deepseek: true, sciverse: true, mineru: false, openalex: true, crossref: true, crossref_polite_contact: false }, operation_contracts: { schema_version: "cosmatter.operation-parameter-contracts/v1", trust_status: "static_parameter_contracts_not_execution_authorization", operations: { sciverse_read_content: { type: "object", additionalProperties: false, required: ["offset", "limit"], properties: { offset: { type: "integer", minimum: 0, default: 0 }, limit: { type: "integer", minimum: 200, maximum: 4000, default: 2000 } } } } } };
    expect(isLocalApiStatus(status)).toBe(true);
    expect(isLocalApiStatus({ ...status, providers: { ...status.providers, token: true } })).toBe(false);
    expect(isLocalApiStatus({ ...status, providers: { ...status.providers, sciverse: "configured" } })).toBe(false);
    expect(isLocalApiStatus({ ...status, operation_contracts: { ...status.operation_contracts, operations: { sciverse_read_content: { ...status.operation_contracts.operations.sciverse_read_content, properties: { ...status.operation_contracts.operations.sciverse_read_content.properties, limit: { type: "integer", minimum: 1, maximum: 8192, default: 8192 } } } } } })).toBe(false);
  });
});
