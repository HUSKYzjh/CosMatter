import { defineTool } from '@deepseek-ai/dsh-tools';
import { countPstOccupations } from './material-calculations.js';
export const pstOccupancyTool = defineTool({
    name: 'cosmatter_pst_occupancy_count',
    description: 'Count distinct labeled A-site arrangements for fixed-composition (Pb_x Sr_(1-x))TiO3 in an 8×8×8 supercell. Returns exact Pb/Sr counts and a decimal integer C(512,n_Pb) before symmetry reduction. For an unrealizable x, gives the two neighboring compositions for the researcher to choose from. Local combinatorics only.',
    parameters: {
        pb_fraction: { type: 'string', required: true, description: 'Exact Pb fraction from 0 to 1, as a decimal or integer ratio, e.g. "0.5" or "1/3".' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute({ pb_fraction }) {
        return countPstOccupations(pb_fraction);
    },
});
