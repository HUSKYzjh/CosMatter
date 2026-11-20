import { defineTool } from '@deepseek-ai/dsh-tools';
// CODATA 2022, F/m. Inputs use SI units, including dimensionless fractional strain.
const epsilon0 = 8.8541878188e-12;
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
        const { axis, mechanical_boundary, observable, field_magnitude_V_per_m: field, mean_at_minus_field: minus, mean_at_plus_field: plus } = args;
        if (axis !== 'x' && axis !== 'y' && axis !== 'z')
            throw new Error('Select one common field and measurement axis: x, y or z.');
        if (mechanical_boundary !== 'fixed_stress' && mechanical_boundary !== 'fixed_strain')
            throw new Error('Specify fixed_stress or fixed_strain.');
        if (observable !== 'polarization_C_per_m2' && observable !== 'normal_strain')
            throw new Error('Select polarization_C_per_m2 or normal_strain.');
        if (observable === 'normal_strain' && mechanical_boundary !== 'fixed_stress')
            throw new Error('Converse d requires a fixed-stress measurement with free strain.');
        if (!Number.isFinite(field) || field <= 0 || !Number.isFinite(minus) || !Number.isFinite(plus))
            throw new Error('Supply finite means and a finite positive electric-field magnitude (V/m).');
        const slope = ((plus - minus) / 2) / field;
        const dielectric = observable === 'polarization_C_per_m2';
        const value = dielectric ? 1 + slope / epsilon0 : slope * 1e12;
        if (!Number.isFinite(value))
            throw new Error('The supplied values exceed the supported numerical range.');
        const index = { x: 1, y: 2, z: 3 }[axis];
        return {
            schema_version: 'cosmatter.md-field-response/v1',
            trust_status: 'finite_difference_from_supplied_means',
            axis, mechanical_boundary, observable, field_magnitude_V_per_m: field,
            mean_at_minus_field: minus, mean_at_plus_field: plus,
            input_unit: dielectric ? 'C/m²' : '1', component: dielectric ? `epsilon_r_${index}${index}` : `d${index}${index}`,
            value, unit: dielectric ? '1' : 'pm/V',
            formula: dielectric ? '1 + (P(+E) - P(-E)) / (2 E epsilon0)' : '1e12 * (S(+E) - S(-E)) / (2 E)',
            ...(dielectric ? { epsilon0_F_per_m: epsilon0 } : {}),
            interpretation: 'Two-point slope at zero field. Check linearity across field magnitudes and uncertainty across equilibrated replicas.',
        };
    },
});
