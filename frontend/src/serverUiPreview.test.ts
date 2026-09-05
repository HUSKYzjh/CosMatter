import { describe, expect, it, vi } from "vitest";

import { SERVER_UI_BUNDLE_MAX_BYTES, fetchServerUiPreview, serverUiPreviewRequested } from "./serverUiPreview";

describe("server-selected UI preview", () => {
  it("requires one exact ui=server opt-in", () => {
    expect(serverUiPreviewRequested("?ui=server&api=local")).toBe(true);
    expect(serverUiPreviewRequested("?ui=manual")).toBe(false);
    expect(serverUiPreviewRequested("?ui=server&ui=server")).toBe(false);
    expect(serverUiPreviewRequested("?next=https://example.test/ui.json")).toBe(false);
  });

  it("loads only the fixed same-origin JSON route without credentials or redirects", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ schema_version: "1.0" }), {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    }));

    await expect(fetchServerUiPreview("?ui=server", fetcher)).resolves.toMatchObject({
      payload: { schema_version: "1.0" },
    });
    expect(fetcher).toHaveBeenCalledWith("./ui.json", expect.objectContaining({
      method: "GET",
      credentials: "omit",
      redirect: "error",
      cache: "no-store",
    }));
  });

  it("does not fetch without opt-in and rejects non-JSON or oversized content", async () => {
    const unusedFetcher = vi.fn();
    await expect(fetchServerUiPreview("?api=local", unusedFetcher as typeof fetch)).resolves.toBeNull();
    expect(unusedFetcher).not.toHaveBeenCalled();

    await expect(fetchServerUiPreview("?ui=server", async () => new Response("<html></html>", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    }))).rejects.toThrow("media type");
    await expect(fetchServerUiPreview("?ui=server", async () => new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json", "Content-Length": String(SERVER_UI_BUNDLE_MAX_BYTES + 1) },
    }))).rejects.toThrow("size limit");
  });
});
