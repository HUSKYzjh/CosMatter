import { expect, it } from "vitest";

import { actionButtonClass } from "./uiPrimitives";

it("builds stable action classes without dropping a caller hook", () => {
  expect(actionButtonClass("danger", "sm", "mission-cancel")).toBe("cm-action cm-action--danger cm-action--sm mission-cancel");
  expect(actionButtonClass("primary", "lg")).toBe("cm-action cm-action--primary cm-action--lg");
});
