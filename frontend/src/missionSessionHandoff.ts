import type { JourneyView } from "./missionJourney";

export type SessionHandoffState = "awaiting_paper" | "paper_selected" | "fulltext_authorized" | "private_fulltext_ready" | "source_map_recorded" | "evidence_audited";

export interface SessionHandoffContext {
  documentId: string | null;
  evidenceId: string | null;
  screeningAllowsSourceReview: boolean;
  privateFulltextReady: boolean;
  sourceMapRecorded: boolean;
  evidenceReady: boolean;
}

export interface SessionHandoff {
  state: SessionHandoffState;
  documentId: string | null;
  evidenceId: string | null;
  destination: JourneyView;
}

/** A narrow projection of the currently selected paper and EvidenceCard. */
export function missionSessionHandoff(context: SessionHandoffContext): SessionHandoff {
  if (!context.documentId) return { state: "awaiting_paper", documentId: null, evidenceId: null, destination: "graph" };
  if (context.evidenceReady) return { state: "evidence_audited", documentId: context.documentId, evidenceId: context.evidenceId, destination: "horizon" };
  if (context.sourceMapRecorded) return { state: "source_map_recorded", documentId: context.documentId, evidenceId: context.evidenceId, destination: "reader" };
  if (context.privateFulltextReady) return { state: "private_fulltext_ready", documentId: context.documentId, evidenceId: context.evidenceId, destination: "reader" };
  if (context.screeningAllowsSourceReview) return { state: "fulltext_authorized", documentId: context.documentId, evidenceId: context.evidenceId, destination: "graph" };
  return { state: "paper_selected", documentId: context.documentId, evidenceId: context.evidenceId, destination: "graph" };
}
