export type MaterialFactScalar = string | number | null;

const NUMERIC_LITERAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

/**
 * Preserve reviewer text while serializing a standalone finite numeric entry
 * as a JSON number.  This lets the loopback unit-normalization guard inspect
 * explicitly supplied value/unit pairs without guessing from prose.
 */
export function materialFactScalar(value: string): MaterialFactScalar {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!NUMERIC_LITERAL.test(trimmed)) return trimmed;
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : trimmed;
}
