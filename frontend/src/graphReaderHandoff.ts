/**
 * Entering the reader is only safe after the graph action has committed its
 * matching paper/evidence session. A rejected selection must leave the user
 * on the map instead of rendering a stale reader session.
 */
export function readerRouteAfterCommittedSelection(selectionCommitted: boolean): "reader" | null {
  return selectionCommitted ? "reader" : null;
}
