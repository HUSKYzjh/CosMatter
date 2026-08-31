export function normalizeConfig(config = {}) {
    const parsed = new URL(config.baseUrl ?? 'http://127.0.0.1:8765');
    if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash)
        throw new Error('CosMatter observability plugin only permits a bare http://127.0.0.1 endpoint');
    const timeoutMs = config.timeoutMs ?? 5_000;
    const maxResponseBytes = config.maxResponseBytes ?? 65_536;
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000)
        throw new Error('timeoutMs must be an integer between 100 and 30000');
    if (!Number.isInteger(maxResponseBytes) || maxResponseBytes < 1_024 || maxResponseBytes > 1_048_576)
        throw new Error('maxResponseBytes is invalid');
    return { baseUrl: parsed.toString().replace(/\/$/, ''), timeoutMs, maxResponseBytes };
}
