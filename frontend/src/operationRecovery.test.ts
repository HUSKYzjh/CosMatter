import { describe, expect, it } from "vitest";

import { operationRecovery } from "./operationRecovery";

describe("operation recovery", () => {
  it("routes each failed operation to a review surface rather than a retry", () => {
    expect(operationRecovery("automatic").view).toBe("workflow");
    expect(operationRecovery("cancellation").view).toBe("workflow");
    expect(operationRecovery("citation").view).toBe("workflow");
    expect(operationRecovery("candidate_pdf").view).toBe("graph");
    expect(operationRecovery("task_start").view).toBe("discover");
    expect(operationRecovery("plan").view).toBe("discover");
    expect(operationRecovery("query").view).toBe("discover");
  });

  it("names the specific audit to perform and explicitly avoids duplicate dispatch", () => {
    expect(operationRecovery("candidate_pdf").contextEn).toContain("do not re-upload");
    expect(operationRecovery("cancellation").contextEn).toContain("do not submit cancellation again");
    expect(operationRecovery("query").contextEn).toContain("provider status");
  });
});
