import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-util-values'

const siteCount = 512

function exactFraction(input: string): [bigint, bigint] {
  const rational = /^(\d+)\/(\d+)$/.exec(input)
  if (rational) return [BigInt(rational[1]), BigInt(rational[2])]
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(input)) {
    throw new Error('Use an exact decimal or a fraction such as "0.5" or "1/3".')
  }
  const [whole, decimal = ''] = input.split('.')
  return [BigInt(whole + decimal), 10n ** BigInt(decimal.length)]
}

function occupancy(nPb: number) {
  // All k/512 fractions are exactly representable in binary and have finite decimal expansions.
  return { pb_fraction: String(nPb / siteCount), n_pb: nPb, n_sr: siteCount - nPb }
}

function countArrangements(nPb: number): string {
  const k = Math.min(nPb, siteCount - nPb)
  let count = 1n
  for (let i = 1; i <= k; i++) {
    count = count * BigInt(siteCount - i + 1) / BigInt(i)
  }
  return count.toString()
}

export const pstOccupancyTool = defineTool({
  name: 'cosmatter_pst_occupancy_count',
  description: 'Count distinct labeled A-site arrangements for fixed-composition (Pb_x Sr_(1-x))TiO3 in an 8×8×8 supercell. Returns exact Pb/Sr counts and a decimal integer C(512,n_Pb) before symmetry reduction. For an unrealizable x, gives the two neighboring compositions for the researcher to choose from. Local combinatorics only.',
  parameters: {
    pb_fraction: { type: 'string', required: true, description: 'Exact Pb fraction from 0 to 1, as a decimal or integer ratio, e.g. "0.5" or "1/3".' },
  },
  output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
  async execute({ pb_fraction }): Promise<Record<string, JsonValue>> {
    if (typeof pb_fraction !== 'string' || pb_fraction.length > 256) throw new Error('pb_fraction must be a string of up to 256 characters.')
    const input = pb_fraction.trim()
    const [numerator, denominator] = exactFraction(input)
    if (denominator === 0n || numerator > denominator) throw new Error('The Pb fraction must lie between 0 and 1 with a positive denominator.')
    const scaled = numerator * BigInt(siteCount)
    const lower = Number(scaled / denominator)
    const base = {
      material_system: '(Pb_x Sr_(1-x))TiO3', supercell: [8, 8, 8], a_site_count: siteCount,
      requested_pb_fraction: input, count_basis: 'labeled_a_sites_before_symmetry_reduction',
    }
    if (scaled % denominator !== 0n) {
      return { ...base, realizable: false, nearest_compositions: [occupancy(lower), occupancy(lower + 1)] }
    }
    return { ...base, realizable: true, ...occupancy(lower), arrangement_count: countArrangements(lower) }
  },
})
