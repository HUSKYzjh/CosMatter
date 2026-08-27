import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard, type LiteratureGraphNode } from "./model";
import { readerSourceIntake, sourceMapTaskKey } from "./readerSourceIntake";
import { emptyResearchSession, selectPaper } from "./researchSession";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate", trustStatus: "candidate" };
const otherPaper: LiteratureGraphNode = { ...paper, nodeId: "paper:doc-2" };
const pdfTask = { document_id: "private-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "done" as const, file_name: "authorised.pdf", state: "done", doi: null, doi_status: "pending", markdown_ready: true, source_map_review_status: "recorded" as const, source_map_segment_count: 1, trust_status: "private" };
const evidence: EvidenceCard = { evidenceId: "ev-1", claim: "Claim", stance: "support", conditions: {}, quote: "Excerpt", reviewStatus: "accepted", provenance: { documentId: "doc-1", locator: "markdown_line:1-1", source: "reviewed", accessPolicy: "authorised" }, isSynthetic: false };

describe("readerSourceIntake", () => {
  it("permits private source registration only for the selected screened candidate", () => {
    const intake = readerSourceIntake(demoBundle, selectPaper(emptyResearchSession(), paper), pdfTask);
    expect(intake).toMatchObject({ selectedDocumentId: "doc-1", attachedDocumentId: "doc-1", matchingPrivatePdf: true, sourceMapRecorded: true, hasLinkedEvidence: false });
  });

  it("keeps a parsed matching PDF pending until its Source Map review is recorded", () => {
    const pending = readerSourceIntake(demoBundle, selectPaper(emptyResearchSession(), paper), { ...pdfTask, source_map_review_status: "absent", source_map_segment_count: 0 });
    expect(pending).toMatchObject({ matchingPrivatePdf: true, sourceMapRecorded: false, hasLinkedEvidence: false });
  });

  it("keeps a PDF linked to another paper out of the current evidence route", () => {
    const intake = readerSourceIntake(demoBundle, selectPaper(emptyResearchSession(), otherPaper), pdfTask);
    expect(intake.matchingPrivatePdf).toBe(false);
    expect(intake.attachedDocumentId).toBe("doc-1");
  });

  it("recognises imported graph-linked evidence without inventing a PDF link", () => {
    const bundle = { ...demoBundle, evidenceCards: [evidence], literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed", trustStatus: "accepted" }] } };
    const intake = readerSourceIntake(bundle, selectPaper(emptyResearchSession(), paper), null);
    expect(intake).toMatchObject({ matchingPrivatePdf: false, sourceMapRecorded: false, attachedDocumentId: null, hasLinkedEvidence: true });
  });

  it("does not bind a relation-root paper to a private PDF", () => {
    const relationRoot: LiteratureGraphNode = { ...paper, kind: "relation_root_paper" };
    const intake = readerSourceIntake(demoBundle, { ...emptyResearchSession(), selectedNode: relationRoot }, pdfTask);
    expect(intake.selectedDocumentId).toBeNull();
    expect(intake.matchingPrivatePdf).toBe(false);
  });
  it("changes the browser-only Source Map draft identity when the audited PDF changes", () => {
    expect(sourceMapTaskKey(pdfTask)).toContain("private-1");
    expect(sourceMapTaskKey({ ...pdfTask, document_id: "private-2" })).not.toBe(sourceMapTaskKey(pdfTask));
    expect(sourceMapTaskKey(null)).toBeNull();
  });
});
