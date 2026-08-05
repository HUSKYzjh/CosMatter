import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";

export const TOPIC_KEYS = ["ferroelectric", "piezoelectric", "thin_film", "domain_microstructure", "simulation_method", "other"] as const;
export type TopicKey = typeof TOPIC_KEYS[number];

export const TOPIC_LABELS: Record<TopicKey, string> = {
  ferroelectric: "Ferroelectricity",
  piezoelectric: "Piezoelectricity",
  thin_film: "Thin films & interfaces",
  domain_microstructure: "Domains & microstructure",
  simulation_method: "Simulation & methods",
  other: "Other title metadata",
};

const PAPER_KINDS = new Set(["candidate_paper", "evidence_paper", "relation_root_paper", "structured_paper"]);
const STOP_WORDS = new Set([
  "about", "after", "among", "analysis", "based", "between", "data", "effect", "effects", "film", "films", "from", "into", "local", "material", "materials", "method", "methods", "model", "models", "paper", "properties", "property", "record", "research", "results", "study", "studies", "system", "systems", "than", "that", "their", "these", "thin", "this", "title", "using", "with", "within",
]);

function text(node: LiteratureGraphNode): string {
  return `${node.label} ${node.source ?? ""}`.toLocaleLowerCase();
}

function includesAny(value: string, terms: string[]): boolean {
  return terms.some((term) => value.includes(term));
}

/**
 * A deliberately small, explainable classifier. It reads display title/source metadata only;
 * it never interprets PDF content and its result is a navigation aid, not a scientific label.
 */
export function topicFor(node: LiteratureGraphNode): TopicKey {
  const value = text(node);
  if (includesAny(value, ["piezo", "pzt", "knn", "lead-free"])) return "piezoelectric";
  if (includesAny(value, ["domain", "fractal", "microstructure", "morphotropic", "grain boundary"])) return "domain_microstructure";
  if (includesAny(value, ["simulation", "molecular dynamics", "dft", "density functional", "potential", "algorithm", "nose-hoover", "monte carlo"])) return "simulation_method";
  if (includesAny(value, ["thin film", "epitax", "substrate", "interface", "superlattice", "strain", "thickness"])) return "thin_film";
  if (includesAny(value, ["ferroelectric", "bifeo", "polarization", "perovskite", "phase transition", "phase stability"])) return "ferroelectric";
  return "other";
}

export function isPaperNode(node: LiteratureGraphNode): boolean {
  return PAPER_KINDS.has(node.kind);
}

function titleTokens(node: LiteratureGraphNode): Set<string> {
  return new Set(
    node.label
      .toLocaleLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .split(" ")
      .filter((token) => token.length >= 5 && !STOP_WORDS.has(token)),
  );
}

export interface RelatedLiteraturePair {
  edge: LiteratureGraphEdge;
  sharedTerms: string[];
}

/**
 * Build sparse, local navigation links from shared meaningful title tokens. These are not
 * citations, semantic entailment, or evidence relations. Each paper may contribute at most two
 * links so a broad keyword cannot turn the canvas into a hairball.
 */
export function relatedLiteraturePairs(nodes: LiteratureGraphNode[]): RelatedLiteraturePair[] {
  const papers = nodes.filter(isPaperNode);
  const tokens = new Map(papers.map((node) => [node.nodeId, titleTokens(node)]));
  const candidates: Array<RelatedLiteraturePair & { score: number }> = [];
  for (let left = 0; left < papers.length; left += 1) {
    for (let right = left + 1; right < papers.length; right += 1) {
      const sharedTerms = [...(tokens.get(papers[left].nodeId) ?? new Set<string>())]
        .filter((term) => (tokens.get(papers[right].nodeId) ?? new Set<string>()).has(term))
        .sort();
      if (!sharedTerms.length) continue;
      candidates.push({
        score: sharedTerms.reduce((total, term) => total + term.length, 0),
        sharedTerms,
        edge: {
          sourceId: papers[left].nodeId,
          targetId: papers[right].nodeId,
          edgeType: "title_similarity_suggestion",
          relationSource: "shared title keywords",
          trustStatus: "algorithmic_title_similarity_navigation_only_not_evidence",
        },
      });
    }
  }
  const used = new Map<string, number>();
  return candidates
    .sort((a, b) => b.score - a.score || a.edge.sourceId.localeCompare(b.edge.sourceId) || a.edge.targetId.localeCompare(b.edge.targetId))
    .filter((pair) => {
      const sourceCount = used.get(pair.edge.sourceId) ?? 0;
      const targetCount = used.get(pair.edge.targetId) ?? 0;
      if (sourceCount >= 2 || targetCount >= 2) return false;
      used.set(pair.edge.sourceId, sourceCount + 1);
      used.set(pair.edge.targetId, targetCount + 1);
      return true;
    })
    .map(({ edge, sharedTerms }) => ({ edge, sharedTerms }));
}
