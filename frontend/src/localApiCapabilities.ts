import type { RetrievalSource } from "./localApi";

export type LocalApiCapabilityHealth = "disabled" | "loading" | "ready" | "unavailable";

const sources: Array<{ id: RetrievalSource; provider: string }> = [
  { id: "sciverse", provider: "sciverse" },
  { id: "openalex", provider: "openalex" },
  { id: "crossref", provider: "crossref" },
];

export function availableRetrievalSources(providers: Record<string, boolean>): RetrievalSource[] {
  return sources.filter((source) => providers[source.provider] === true).map((source) => source.id);
}

/** Retain a user's viable selection; use the available set only when none remains. */
export function reconcileRetrievalSources(current: RetrievalSource[], providers: Record<string, boolean>): RetrievalSource[] {
  const available = availableRetrievalSources(providers);
  const retained = current.filter((source) => available.includes(source));
  return retained.length ? retained : available;
}
