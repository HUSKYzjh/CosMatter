import type { EvidenceMarkdownLocation, MarkdownLineRange, PrivateMarkdownLine } from "./localApi";

export type ReaderEvidenceLocation = EvidenceMarkdownLocation & { quote: string };

/** Split a uniquely matched, verified quotation without changing the displayed source text. */
export function matchReaderEvidenceQuote(lines: PrivateMarkdownLine[], range: MarkdownLineRange, quote: string) {
  const cited = lines.filter(line => line.number >= range.start && line.number <= range.end);
  if (!quote || cited.length !== range.end - range.start + 1 || cited.some(line => line.truncated)) return null;
  const text = cited.map(line => line.text).join("\n");
  const match = text.indexOf(quote);
  if (match === -1 || text.indexOf(quote, match + 1) !== -1) return null;

  const parts = new Map<number, { before: string; quote: string; after: string }>();
  let offset = 0;
  for (const line of cited) {
    const start = Math.max(0, match - offset);
    const end = Math.min(line.text.length, match + quote.length - offset);
    if (start < end) {
      parts.set(line.number, { before: line.text.slice(0, start), quote: line.text.slice(start, end), after: line.text.slice(end) });
    }
    offset += line.text.length + 1;
  }
  return parts;
}
