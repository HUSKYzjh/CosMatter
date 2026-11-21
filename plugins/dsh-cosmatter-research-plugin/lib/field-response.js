import { defineTool } from '@deepseek-ai/dsh-tools';
import { calculateFieldResponse } from './material-calculations.js';
export const fieldResponseTool = defineTool({
    name: 'cosmatter_md_field_response',
    description: 'Compute a longitudinal central finite-field estimate from supplied equilibrated MD means at symmetric fields -E and +E on the same axis, at the same temperature and on the same polarization branch. For relative permittivity supply polarization in C/m². For the converse piezoelectric d coefficient supply fractional normal strain at fixed stress. Offline arithmetic only.',
    parameters: {
        axis: { type: 'string', required: true, description: 'Common field and measurement axis: x, y or z.' },
        mechanical_boundary: { type: 'string', required: true, description: 'fixed_stress or fixed_strain.' },
        observable: { type: 'string', required: true, description: 'polarization_C_per_m2 or normal_strain. Use strain as a fraction, not percent.' },
        field_magnitude_V_per_m: { type: 'number', required: true, description: 'Positive magnitude E shared by -E and +E, in V/m.' },
        mean_at_minus_field: { type: 'number', required: true },
        mean_at_plus_field: { type: 'number', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(args) {
        return calculateFieldResponse(args);
    },
});
