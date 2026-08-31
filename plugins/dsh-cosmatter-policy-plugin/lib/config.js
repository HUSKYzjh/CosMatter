export function normalizeConfig(config = {}) {
    const parsed = new URL(config.baseUrl ?? 'http://127.0.0.1:8765');
    if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash)
        throw new Error('CosMatter policy plugin only permits a bare http://127.0.0.1 endpoint');
    const timeoutMs = config.timeoutMs ?? 5_000;
    const maxCatalogueBytes = config.maxCatalogueBytes ?? 524_288;
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000)
        throw new Error('timeoutMs must be an integer between 100 and 30000');
    if (!Number.isInteger(maxCatalogueBytes) || maxCatalogueBytes < 1_024 || maxCatalogueBytes > 1_048_576)
        throw new Error('maxCatalogueBytes is invalid');
    return { baseUrl: parsed.toString().replace(/\/$/, ''), timeoutMs, maxCatalogueBytes };
}
