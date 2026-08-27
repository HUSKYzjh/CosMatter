import type { ImportedBundle } from "./model";

export type FleetVisualMode = "idle" | "active" | "review" | "ready";
export type FleetVisualKind = "discover" | "workflow" | "graph" | "reader" | "horizon";

export interface FleetVisualState {
  progress: number;
  signal: number;
  density: number;
  mode: FleetVisualMode;
}

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const terminal = (value: string) => /done|complete|accepted|released|ready|pass/i.test(value);
const active = (value: string) => /active|running|queued|processing|retriev/i.test(value);
const review = (value: string) => /review|pending|waiting|approval|blocked/i.test(value);

function modeFor(hasData: boolean, hasActive: boolean, needsReview: boolean, isReady: boolean): FleetVisualMode {
  if (!hasData) return "idle";
  if (isReady) return "ready";
  if (needsReview) return "review";
  return hasActive ? "active" : "idle";
}

function stationState(bundle: ImportedBundle) {
  const values = [bundle.status?.missionState ?? "", ...bundle.stations.map((item) => item.status), ...bundle.timeline.map((item) => item.state)];
  const hasData = values.some(Boolean);
  const completed = values.filter(terminal).length;
  const operational = values.filter((value) => terminal(value) || active(value) || review(value)).length;
  return {
    hasData,
    active: values.some(active),
    review: values.some(review) || Boolean(bundle.status?.returnReason),
    progress: operational ? clamp(completed / operational) : 0,
  };
}

export function fleetVisualState(bundle: ImportedBundle, kind: FleetVisualKind): FleetVisualState {
  const station = stationState(bundle);
  const evidence = bundle.evidenceCards.length;
  const graphNodes = bundle.literatureGraph.nodes.length;
  const graphEdges = bundle.literatureGraph.edges.length;
  const reportAudit = bundle.auditSummary.reportEvidence;
  const provenanceAudit = bundle.auditSummary.evidenceProvenance;

  if (kind === "discover") {
    const hasData = station.hasData || graphNodes > 0 || evidence > 0;
    return {
      progress: station.progress,
      signal: station.active ? 0.72 : evidence ? 0.28 : 0,
      density: clamp((graphNodes + evidence) / 32),
      mode: modeFor(hasData, station.active, station.review, station.progress >= 1 && evidence > 0),
    };
  }

  if (kind === "workflow") {
    const hasData = station.hasData || bundle.timeline.length > 0;
    return {
      progress: station.progress,
      signal: hasData ? (station.active ? 0.72 : station.review ? 0.34 : 0.16) : 0,
      density: clamp((bundle.stations.length + bundle.timeline.length) / 18),
      mode: modeFor(hasData, station.active, station.review, station.progress >= 1),
    };
  }

  if (kind === "graph") {
    const hasData = graphNodes > 0 || graphEdges > 0;
    return {
      progress: clamp(graphEdges / Math.max(1, graphNodes * 2)),
      signal: hasData ? (evidence ? 0.4 : 0.14) : 0,
      density: clamp((graphNodes + graphEdges * 0.45) / 54),
      mode: modeFor(hasData, false, station.review, evidence > 0 && Boolean(provenanceAudit?.exactSourceMapMatchCount)),
    };
  }

  if (kind === "reader") {
    const hasData = bundle.sourceMapSummary.segmentCount > 0 || evidence > 0;
    const provenance = provenanceAudit?.exactSourceMapMatchRate ?? 0;
    return {
      progress: clamp(provenance),
      signal: evidence && provenance ? 0.44 : 0,
      density: clamp((bundle.sourceMapSummary.segmentCount + evidence) / 34),
      mode: modeFor(hasData, false, station.review, evidence > 0 && provenance >= 1),
    };
  }

  const hasData = bundle.researchGapCandidates.length > 0 || Boolean(reportAudit);
  const coverage = reportAudit?.gapCounterevidenceBoundaryRenderedCoverage ?? 0;
  const executed = reportAudit?.executedGapCounterevidenceBoundaryCount ?? 0;
  const complete = coverage >= 1 && executed > 0;
  return {
    progress: clamp((reportAudit?.manifestCoverage ?? 0) * coverage),
    signal: complete ? 0.46 : bundle.researchGapCandidates.length ? 0.2 : 0,
    density: clamp(bundle.researchGapCandidates.length / 10),
    mode: modeFor(hasData, false, bundle.researchGapCandidates.length > 0 && !complete, complete),
  };
}

export function fleetVisualStyle(state: FleetVisualState): string {
  return [
    `--fleet-progress: ${Math.round(state.progress * 22)}px`,
    `--fleet-signal: ${state.signal.toFixed(2)}`,
    `--fleet-density: ${Math.max(0.08, state.density).toFixed(2)}`,
    `--fleet-mode: ${state.mode}`,
  ].join("; ");
}
