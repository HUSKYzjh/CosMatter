import type { EvidenceCard, LiteratureGraphNode } from "./model";
import { documentIdForReviewablePaper } from "./evidenceLinking";
import { isPaperNode } from "./literatureTopology";
import { displayPaperTitle } from "./paperTitle";

function normalized(value: string) {
  return value.normalize("NFKC").trim().toLowerCase();
}

export function graphDisplayLabel(node: LiteratureGraphNode): string {
  return isPaperNode(node) ? displayPaperTitle(node.label) : node.label;
}

export function graphDoi(node: LiteratureGraphNode): string | undefined {
  if (node.doi) return node.doi;
  if (node.kind === "citation_work" || node.kind === "crossref_work") {
    const id = node.label.replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, "");
    if (/^10\.[^\s/]+\/\S+$/i.test(id)) return id;
  }
  return undefined;
}

export function searchableGraphNodes(nodes: LiteratureGraphNode[], evidence: EvidenceCard[]): LiteratureGraphNode[] {
  const dois = new Map<string, Set<string>>();
  for (const card of evidence) {
    if (!card.provenance.doi) continue;
    const doi = normalized(card.provenance.doi).replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/, "");
    if (!/^10\.[^\s/]+\/\S+$/.test(doi)) continue;
    const id = card.provenance.documentId;
    const recorded = dois.get(id) ?? new Set();
    recorded.add(doi);
    dois.set(id, recorded);
  }
  return nodes.map(node => {
    if (graphDoi(node)) return node;
    const id = documentIdForReviewablePaper(node);
    const recorded = id ? dois.get(id) : undefined;
    return recorded?.size === 1 ? { ...node, doi: [...recorded][0] } : node;
  });
}

export function searchGraph(nodes: LiteratureGraphNode[], input: string): LiteratureGraphNode[] {
  const query = normalized(input);
  if (!query) return [];
  const phrase = query.replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/, "");
  if (!phrase) return [];
  const terms = phrase.split(/\s+/u);
  const matches: Array<{ node: LiteratureGraphNode; rank: number }> = [];
  for (const node of nodes) {
    const doi = normalized(graphDoi(node) ?? "");
    const id = normalized(node.nodeId);
    const titles = [normalized(node.label), normalized(graphDisplayLabel(node))];
    const metadata = [...titles, id, doi, normalized(node.source ?? ""), node.publicationYear ?? ""].join(" ");
    if (!terms.every(term => metadata.includes(term))) continue;
    let rank = 3;
    if (phrase === doi || phrase === id || phrase === id.replace(/^paper:/, "") || titles.includes(phrase)) rank = 0;
    else if (titles.some(title => title.startsWith(phrase))) rank = 1;
    else if (titles.some(title => title.includes(phrase))) rank = 2;
    matches.push({ node, rank });
  }
  return matches.sort((a, b) => a.rank - b.rank).map(match => match.node);
}
