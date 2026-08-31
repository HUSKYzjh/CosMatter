export interface CosMatterGraphConfig {
  /** A loopback-only CosMatter preview API endpoint. */
  baseUrl?: string
  timeoutMs?: number
  maxGraphBytes?: number
}

export interface NormalizedConfig {
  baseUrl: URL
  timeoutMs: number
  maxGraphBytes: number
}

export function normalizeConfig(config: CosMatterGraphConfig = {}): NormalizedConfig {
  const baseUrl = new URL(config.baseUrl ?? 'http://127.0.0.1:8765')
  if (baseUrl.protocol !== 'http:' || baseUrl.hostname !== '127.0.0.1') {
    throw new Error('CosMatter graph plugin permits only http://127.0.0.1 loopback endpoints')
  }
  const timeoutMs = config.timeoutMs ?? 5000
  const maxGraphBytes = config.maxGraphBytes ?? 524288
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30000) {
    throw new Error('timeoutMs must be an integer between 100 and 30000')
  }
  if (!Number.isInteger(maxGraphBytes) || maxGraphBytes < 4096 || maxGraphBytes > 1048576) {
    throw new Error('maxGraphBytes must be an integer between 4096 and 1048576')
  }
  return { baseUrl, timeoutMs, maxGraphBytes }
}
