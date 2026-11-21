import type { CandidateScreening, CandidateScreeningDecision } from "./localApi";

export const checkpointKey = (runId: string) => "cosmatter.screening-checkpoint:v1:" + runId;
export const hasChecklistRevision = (screening: CandidateScreening) => /^[a-f0-9]{64}$/.test(screening.checklist_revision ?? "");
const sizeLimit = 500_000;

export interface ScreeningCheckpoint {
  version: 1;
  run_id: string;
  mission_id: string;
  revision: string;
  candidates: string[];
  current: string;
  changes: CandidateScreeningDecision[];
}

export function encodeCheckpoint(screening: CandidateScreening, mission: string, current: string, changes: CandidateScreeningDecision[]): string {
  const candidates = screening.candidates.map(item => item.document_id);
  if (!mission || !hasChecklistRevision(screening) || !candidates.includes(current)
    || screening.candidate_count !== candidates.length || new Set(candidates).size !== candidates.length) {
    throw new Error("Invalid screening identity");
  }
  const saved: ScreeningCheckpoint = {
    version: 1, run_id: screening.run_id, mission_id: mission, revision: screening.checklist_revision!, candidates, current,
    changes: changes.map(({ document_id, decision, reason_codes }) => ({ document_id, decision, reason_codes })),
  };
  const encoded = JSON.stringify(saved);
  if (encoded.length > sizeLimit) throw new Error("Screening checkpoint exceeds the storage limit");
  return encoded;
}

export function readCheckpoint(raw: string, screening: CandidateScreening, mission: string,
  isDecision: (value: unknown) => value is CandidateScreeningDecision): ScreeningCheckpoint | null {
  if (raw.length > sizeLimit || !hasChecklistRevision(screening) || !mission) return null;
  let saved: Partial<ScreeningCheckpoint> | null;
  try { saved = JSON.parse(raw); } catch { return null; }
  if (!saved || saved.version !== 1 || saved.run_id !== screening.run_id || saved.mission_id !== mission
    || saved.revision !== screening.checklist_revision || !Array.isArray(saved.candidates) || !Array.isArray(saved.changes)) return null;
  const ids = new Set(screening.candidates.map(item => item.document_id));
  if (ids.size !== screening.candidates.length || ids.size !== screening.candidate_count
    || saved.candidates.length !== ids.size || new Set(saved.candidates).size !== ids.size
    || !saved.candidates.every(id => ids.has(id)) || !ids.has(saved.current ?? "")
    || saved.changes.length > ids.size || !saved.changes.every(item => isDecision(item) && ids.has(item.document_id))
    || new Set(saved.changes.map(item => item.document_id)).size !== saved.changes.length) return null;
  return saved as ScreeningCheckpoint;
}
