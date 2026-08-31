export interface CosMatterMissionConfig {
  baseUrl?: string
  timeoutMs?: number
}

export interface NormalizedConfig {
  baseUrl: string
  timeoutMs: number
}

export function normalizeConfig(config: CosMatterMissionConfig = {}): NormalizedConfig {
  const baseUrl = config.baseUrl ?? 'http://127.0.0.1:8765'
  const parsed = new URL(baseUrl)
  if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error('CosMatter mission plugin only permits a bare http://127.0.0.1 endpoint')
  }
  const timeoutMs = config.timeoutMs ?? 5_000
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000) throw new Error('timeoutMs must be an integer between 100 and 30000')
  return { baseUrl: parsed.toString().replace(/\/$/, ''), timeoutMs }
}
