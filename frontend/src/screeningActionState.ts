import type { CandidateScreening } from "./localApi";

/** A loaded checklist may be hidden once every candidate has a persisted decision. */
export function shouldPromptForScreening(hasReviewablePapers: boolean, screeningApiReady: boolean, screening: CandidateScreening | null): boolean {
  if (!hasReviewablePapers || !screeningApiReady) return false;
  if (!screening) return true;
  return screening.candidates.some((candidate) => (screening.decisions.find((decision) => decision.document_id === candidate.document_id)?.decision ?? "unreviewed") === "unreviewed");
}
