export function normalizeConfig(config = {}) {
    const baseUrl = config.baseUrl ?? 'http://127.0.0.1:8765';
    const parsed = new URL(baseUrl);
    if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
        throw new Error('CosMatter research plugin only permits a bare http://127.0.0.1 endpoint');
    }
    const timeoutMs = config.timeoutMs ?? 15_000;
    const maxResponseBytes = config.maxResponseBytes ?? 262_144;
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000)
        throw new Error('timeoutMs must be an integer between 100 and 30000');
    if (!Number.isInteger(maxResponseBytes) || maxResponseBytes < 4_096 || maxResponseBytes > 524_288)
        throw new Error('maxResponseBytes must be an integer between 4096 and 524288');
    return { baseUrl: parsed.toString().replace(/\/$/, ''), timeoutMs, maxResponseBytes };
}
