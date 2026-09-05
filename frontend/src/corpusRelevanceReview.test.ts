import { describe, expect, it } from "vitest";

import {
  BLANK_HUMAN_GOLD_STATUS,
  CORPUS_ACCESS_BOUNDARY,
  CORPUS_MANIFEST_STATUS,
  DOCUMENT_ACCESS_POLICY,
  REVIEWED_HUMAN_GOLD_STATUS,
  bindManifestToHumanGold,
  corpusRelevanceReadiness,
  exportHumanGoldDraft,
  parseCorpusManifest,
  parseHumanGoldDraft,
  type CorpusManifest,
  type HumanGoldDraft,
} from "./corpusRelevanceReview";

function gold(): HumanGoldDraft {
  return {
    schema_version: "1.0",
    mission_id: "mission-1",
    corpus_id: "bfo-3",
    trust_status: BLANK_HUMAN_GOLD_STATUS,
    annotation_instructions: {
      retrieval_relevance: "Mark relevance after reading the authorized paper.",
      evidence_annotations: "Record bounded evidence annotations.",
      material_fact_annotations: "Record reviewed material facts.",
      comparison_annotations: "Record bounded comparisons.",
      gap_annotations: "Record bounded gap reviews.",
    },
    documents: ["doc-1", "doc-2", "doc-3"].map((documentId) => ({
      document_id: documentId,
      retrieval_relevance: "unreviewed",
      evidence_annotations: [],
      material_fact_annotations: [],
      comparison_annotations: [],
      gap_annotations: [],
    })),
  };
}

function manifest(): CorpusManifest {
  return {
    schema_version: "1.0",
    mission_id: "mission-1",
    corpus_id: "bfo-3",
    material: "BiFeO3",
    trust_status: CORPUS_MANIFEST_STATUS,
    access_boundary: CORPUS_ACCESS_BOUNDARY,
    documents: ["doc-1", "doc-2", "doc-3"].map((documentId, index) => ({
      document_id: documentId,
      title: `Bounded paper ${index + 1}`,
      doi: index === 0 ? "10.1000/example" : null,
      access_policy: DOCUMENT_ACCESS_POLICY,
    })),
  };
}

describe("human corpus relevance review", () => {
  it("parses the generated gold shape and reports incomplete relevance", () => {
    const parsed = parseHumanGoldDraft(gold());
    expect(corpusRelevanceReadiness(parsed)).toEqual({
      documentCount: 3,
      reviewedCount: 0,
      counts: { unreviewed: 3, relevant: 0, partially_relevant: 0, not_relevant: 0 },
      readyForAttestation: false,
    });
  });

  it("sets reviewed trust only after complete labels, a relevant paper, and attestation", () => {
    const complete = gold();
    complete.documents[0].evidence_annotations = [{ evidence_id: "keep-opaque" }];
    complete.documents[0].retrieval_relevance = "relevant";
    complete.documents[1].retrieval_relevance = "partially_relevant";
    complete.documents[2].retrieval_relevance = "not_relevant";
    expect(exportHumanGoldDraft(complete, false).trust_status).toBe(BLANK_HUMAN_GOLD_STATUS);
    const exported = exportHumanGoldDraft(complete, true);
    expect(exported.trust_status).toBe(REVIEWED_HUMAN_GOLD_STATUS);
    expect(exported.documents[0].evidence_annotations).toEqual([{ evidence_id: "keep-opaque" }]);
    complete.documents[0].retrieval_relevance = "not_relevant";
    expect(exportHumanGoldDraft(complete, true).trust_status).toBe(BLANK_HUMAN_GOLD_STATUS);
  });

  it("binds optional bibliography metadata only to an exact gold document set", () => {
    expect(bindManifestToHumanGold(gold(), parseCorpusManifest(manifest())).documents[0].title).toBe("Bounded paper 1");
    const wrong = manifest();
    wrong.documents[0].document_id = "other";
    expect(() => bindManifestToHumanGold(gold(), wrong)).toThrow(/document IDs/);
  });

  it("rejects extra fields, duplicate IDs, and reviewed files with an unreviewed row", () => {
    expect(() => parseHumanGoldDraft({ ...gold(), local_path: "C:/private" })).toThrow(/Unsupported/);
    const duplicate = gold();
    duplicate.documents[1].document_id = duplicate.documents[0].document_id;
    expect(() => parseHumanGoldDraft(duplicate)).toThrow(/identity/);
    const falseReview = gold();
    falseReview.trust_status = REVIEWED_HUMAN_GOLD_STATUS;
    expect(() => parseHumanGoldDraft(falseReview)).toThrow(/cannot contain unreviewed/);
    const noRelevant = gold();
    noRelevant.trust_status = REVIEWED_HUMAN_GOLD_STATUS;
    noRelevant.documents.forEach((item) => { item.retrieval_relevance = "not_relevant"; });
    expect(() => parseHumanGoldDraft(noRelevant)).toThrow(/at least one relevant/);
    const blankDoi = manifest();
    blankDoi.documents[0].doi = "";
    expect(() => parseCorpusManifest(blankDoi)).toThrow(/document fields/);
  });

  it("accepts a 250-document review boundary and rejects a larger file", () => {
    const bounded = gold();
    bounded.documents = Array.from({ length: 250 }, (_, index) => ({
      ...structuredClone(bounded.documents[0]),
      document_id: `doc-${index + 1}`,
    }));
    expect(parseHumanGoldDraft(bounded).documents).toHaveLength(250);
    bounded.documents.push({ ...structuredClone(bounded.documents[0]), document_id: "doc-251" });
    expect(() => parseHumanGoldDraft(bounded)).toThrow(/1 to 250/);
  });
});
