const UNSAFE_ERROR_SURFACE = /(?:https?|file|ssh):\/\/|[a-z]:[\\/]|(?:api[ _-]?(?:key|token)|authorization|cookie|password|secret|bearer|sk[-_]|sv[-_]|gho[_-])/i;

/**
 * Import failures can originate in a local file or a loopback API.  Keep the
 * useful category while never reflecting paths, URLs, or credentials into the
 * browser UI.
 */
export function safeImportFeedback(error: unknown, fallback: string, rejected: string): string {
  const message = error instanceof Error ? error.message.replace(/\s+/g, " ").trim() : "";
  if (!message || message.length > 280 || UNSAFE_ERROR_SURFACE.test(message)) return fallback;
  if (/(?:run package|artifact|digest|hash|private|unsafe|mismatch|schema)/i.test(message)) return rejected;
  return fallback;
}

/** Provider and loopback errors are untrusted display data; never reflect them. */
export function safeOperationFeedback(_error: unknown, fallback: string): string {
  return fallback;
}

/** A client-aborted write may already have reached the local service. */
export function safeMutationFeedback(error: unknown, fallback: string, unknownOutcome: string): string {
  return error instanceof Error && "failure" in error && (error as { failure?: unknown }).failure === "write_outcome_unknown"
    ? unknownOutcome
    : safeOperationFeedback(error, fallback);
}
