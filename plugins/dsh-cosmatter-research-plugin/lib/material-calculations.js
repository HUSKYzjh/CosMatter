// Shared by the browser workbench and native DSH tools.
export class CalculationError extends Error {
    code;
    constructor(code, message) {
        super(message);
        this.code = code;
    }
}
const siteCount = 512;
function exactFraction(input) {
    const rational = /^(\d+)\/(\d+)$/.exec(input);
    if (rational)
        return [BigInt(rational[1]), BigInt(rational[2])];
    if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(input)) {
        throw new CalculationError('fraction_format', 'Use an exact decimal or a fraction such as "0.5" or "1/3".');
    }
    const [whole, decimal = ''] = input.split('.');
    return [BigInt(whole + decimal), 10n ** BigInt(decimal.length)];
}
function occupancy(nPb) {
    // All k/512 fractions are exactly representable in binary and have finite decimal expansions.
    return { pb_fraction: String(nPb / siteCount), n_pb: nPb, n_sr: siteCount - nPb };
}
function countArrangements(nPb) {
    const k = Math.min(nPb, siteCount - nPb);
    let count = 1n;
    for (let i = 1; i <= k; i++) {
        count = count * BigInt(siteCount - i + 1) / BigInt(i);
    }
    return count.toString();
}
export function countPstOccupations(pb_fraction) {
    if (typeof pb_fraction !== 'string' || pb_fraction.length > 256)
        throw new CalculationError('fraction_length', 'pb_fraction must be a string of up to 256 characters.');
    const input = pb_fraction.trim();
    const [numerator, denominator] = exactFraction(input);
    if (denominator === 0n || numerator > denominator)
        throw new CalculationError('fraction_range', 'The Pb fraction must lie between 0 and 1 with a positive denominator.');
    const scaled = numerator * BigInt(siteCount);
    const lower = Number(scaled / denominator);
    const base = {
        material_system: '(Pb_x Sr_(1-x))TiO3', supercell: [8, 8, 8], a_site_count: siteCount,
        requested_pb_fraction: input, count_basis: 'labeled_a_sites_before_symmetry_reduction',
    };
    if (scaled % denominator !== 0n) {
        return { ...base, realizable: false, nearest_compositions: [occupancy(lower), occupancy(lower + 1)] };
    }
    return { ...base, realizable: true, ...occupancy(lower), arrangement_count: countArrangements(lower) };
}
// CODATA 2022, F/m. All inputs use SI units, including fractional strain.
const epsilon0 = 8.8541878188e-12;
export function calculateFieldResponse(args) {
    const { axis, mechanical_boundary, observable, field_magnitude_V_per_m: field, mean_at_minus_field: minus, mean_at_plus_field: plus } = args;
    if (axis !== 'x' && axis !== 'y' && axis !== 'z')
        throw new CalculationError('axis', 'Select one common field and measurement axis: x, y or z.');
    if (mechanical_boundary !== 'fixed_stress' && mechanical_boundary !== 'fixed_strain')
        throw new CalculationError('boundary', 'Specify fixed_stress or fixed_strain.');
    if (observable !== 'polarization_C_per_m2' && observable !== 'normal_strain')
        throw new CalculationError('observable', 'Select polarization_C_per_m2 or normal_strain.');
    if (observable === 'normal_strain' && mechanical_boundary !== 'fixed_stress')
        throw new CalculationError('clamped_strain', 'Converse d requires a fixed-stress measurement with free strain.');
    if (!Number.isFinite(field) || field <= 0 || !Number.isFinite(minus) || !Number.isFinite(plus))
        throw new CalculationError('finite_fields', 'Supply finite means and a finite positive electric-field magnitude (V/m).');
    const slope = ((plus - minus) / 2) / field;
    const dielectric = observable === 'polarization_C_per_m2';
    const value = dielectric ? 1 + slope / epsilon0 : slope * 1e12;
    if (!Number.isFinite(value))
        throw new CalculationError('numeric_range', 'The supplied values exceed the supported numerical range.');
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
}
