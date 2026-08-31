import { normalizeConfig, type CosMatterMissionConfig, type NormalizedConfig } from './config.js'

export interface MissionInput {
  question: string
  material: string
  property: string
  scope: string
  run_id?: string
  mission_type?: string
}

export interface MissionCreated {
  run_id: string
  mission_id: string
  fleet_type: string
  mission_type: string
  state: 'INTAKE'
}

const safeRunId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/
const sensitiveKey = /(token|secret|password|authorization|api[_-]?key|path|quote|content)/i

function bounded(value: string, field: string, max: number): string {
  if (!value.trim() || value.trim().length > max) throw new Error(`${field} is invalid`)
  return value.trim()
}

export class CosMatterMissionClient {
  readonly config: NormalizedConfig

  constructor(config: CosMatterMissionConfig = {}, private readonly request: typeof fetch = fetch) {
    this.config = normalizeConfig(config)
  }

  async create(input: MissionInput, signal?: AbortSignal): Promise<MissionCreated> {
    const payload: MissionInput = {
      question: bounded(input.question, 'question', 3_000),
      material: bounded(input.material, 'material', 300),
      property: bounded(input.property, 'property', 300),
      scope: bounded(input.scope, 'scope', 1_000),
    }
    if (input.run_id !== undefined) {
      if (!safeRunId.test(input.run_id)) throw new Error('run_id is invalid')
      payload.run_id = input.run_id
    }
    if (input.mission_type !== undefined) payload.mission_type = bounded(input.mission_type, 'mission_type', 80)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.config.timeoutMs)
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    try {
      const response = await this.request(new URL('/api/missions', this.config.baseUrl), {
        method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(payload), signal: controller.signal,
      })
      const value: unknown = await response.json()
      if (!response.ok) throw new Error(`CosMatter mission creation failed with HTTP ${response.status}`)
      return validateMissionCreated(value)
    } finally {
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
    }
  }
}

export function validateMissionCreated(value: unknown): MissionCreated {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('CosMatter mission response is invalid')
  const result = value as Record<string, unknown>
  if (Object.keys(result).some(key => sensitiveKey.test(key))) throw new Error('CosMatter mission response contains a forbidden field')
  if (!safeRunId.test(String(result.run_id)) || !/^mission_[a-z0-9_]{8,128}$/i.test(String(result.mission_id)) || typeof result.fleet_type !== 'string' || typeof result.mission_type !== 'string' || result.state !== 'INTAKE') {
    throw new Error('CosMatter mission response is invalid')
  }
  return result as unknown as MissionCreated
}
