export declare class CalculationError extends Error {
    readonly code: string;
    constructor(code: string, message: string);
}
export declare function countPstOccupations(pb_fraction: string): {
    realizable: false;
    nearest_compositions: {
        pb_fraction: string;
        n_pb: number;
        n_sr: number;
    }[];
    material_system: string;
    supercell: number[];
    a_site_count: number;
    requested_pb_fraction: string;
    count_basis: string;
} | {
    arrangement_count: string;
    pb_fraction: string;
    n_pb: number;
    n_sr: number;
    realizable: true;
    material_system: string;
    supercell: number[];
    a_site_count: number;
    requested_pb_fraction: string;
    count_basis: string;
};
export type FieldInput = {
    axis: string;
    mechanical_boundary: string;
    observable: string;
    field_magnitude_V_per_m: number;
    mean_at_minus_field: number;
    mean_at_plus_field: number;
};
export declare function calculateFieldResponse(args: FieldInput): {
    interpretation: string;
    epsilon0_F_per_m?: number | undefined;
    schema_version: string;
    trust_status: string;
    axis: string;
    mechanical_boundary: string;
    observable: string;
    field_magnitude_V_per_m: number;
    mean_at_minus_field: number;
    mean_at_plus_field: number;
    input_unit: string;
    component: string;
    value: number;
    unit: string;
    formula: string;
};
