export const SERVER_UI_BUNDLE_MAX_BYTES = 5 * 1024 * 1024;

export interface ServerUiPreviewBundle {
  payload: unknown;
  byteLength: number;
}

export function serverUiPreviewRequested(search: string): boolean {
  const values = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).getAll("ui");
  return values.length === 1 && values[0] === "server";
}

/**
 * Load only the redacted bundle explicitly selected by the loopback preview
 * server.  The fixed relative path, omitted credentials, redirect refusal,
 * JSON media type, and size bound prevent this opt-in preview from becoming
 * a general URL/file loader.
 */
export async function fetchServerUiPreview(
  search: string,
  fetcher: typeof fetch = fetch,
): Promise<ServerUiPreviewBundle | null> {
  if (!serverUiPreviewRequested(search)) return null;
  const response = await fetcher("./ui.json", {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "omit",
    redirect: "error",
    cache: "no-store",
  });
  if (!response.ok) throw new Error("server-selected UI bundle is unavailable");
  if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get("content-type") ?? "")) {
    throw new Error("server-selected UI bundle media type is invalid");
  }
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > SERVER_UI_BUNDLE_MAX_BYTES) {
    throw new Error("server-selected UI bundle exceeds the size limit");
  }
  const raw = await response.text();
  const byteLength = new TextEncoder().encode(raw).byteLength;
  if (byteLength > SERVER_UI_BUNDLE_MAX_BYTES) throw new Error("server-selected UI bundle exceeds the size limit");
  return { payload: JSON.parse(raw) as unknown, byteLength };
}
