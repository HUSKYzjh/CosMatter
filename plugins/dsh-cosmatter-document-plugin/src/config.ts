export interface CosMatterDocumentConfig { baseUrl?: string; timeoutMs?: number; maxResponseBytes?: number }
export interface NormalizedConfig { baseUrl: string; timeoutMs: number; maxResponseBytes: number }

export function normalizeConfig(config: CosMatterDocumentConfig = {}): NormalizedConfig {
  const parsed = new URL(config.baseUrl ?? 'http://127.0.0.1:8765')
  if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) throw new Error('CosMatter document plugin only permits a bare http://127.0.0.1 endpoint')
  const timeoutMs = config.timeoutMs ?? 15_000; const maxResponseBytes = config.maxResponseBytes ?? 65_536
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000) throw new Error('timeoutMs must be an integer between 100 and 30000')
  if (!Number.isInteger(maxResponseBytes) || maxResponseBytes < 4_096 || maxResponseBytes > 131_072) throw new Error('maxResponseBytes must be an integer between 4096 and 131072')
  return { baseUrl: parsed.toString().replace(/\/$/, ''), timeoutMs, maxResponseBytes }
}
