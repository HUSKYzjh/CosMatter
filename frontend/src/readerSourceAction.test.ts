import { describe, expect, it } from "vitest";

import { readerSourceAction } from "./readerSourceAction";

const base = { hasLinkedEvidence: false, hasMatchingPrivatePdf: false, privatePdfParsing: false, privatePdfFailed: false, hasOtherPaperPdf: false, screeningAllowsSourceReview: false };

describe("readerSourceAction", () => {
  it("keeps imported evidence as the highest-priority reader action", () => {
    expect(readerSourceAction({ ...base, hasLinkedEvidence: true, screeningAllowsSourceReview: true })).toBe("review_imported_evidence");
  });

  it("asks to record locations only for a matching private PDF", () => {
    expect(readerSourceAction({ ...base, hasMatchingPrivatePdf: true })).toBe("record_source_locations");
  });
  it("does not expose source-location entry while private parsing is pending or failed", () => {
    expect(readerSourceAction({ ...base, privatePdfParsing: true, hasMatchingPrivatePdf: true })).toBe("await_private_parsing");
    expect(readerSourceAction({ ...base, privatePdfFailed: true, hasMatchingPrivatePdf: true })).toBe("retry_authorized_pdf");
  });

  it("makes a mismatched PDF an alignment task, not evidence for the current paper", () => {
    expect(readerSourceAction({ ...base, hasOtherPaperPdf: true, screeningAllowsSourceReview: true })).toBe("align_selected_paper");
  });

  it("asks an included candidate to choose an authorised PDF instead of repeating screening", () => {
    expect(readerSourceAction({ ...base, screeningAllowsSourceReview: true })).toBe("choose_authorized_pdf");
    expect(readerSourceAction(base)).toBe("complete_screening");
  });
});

