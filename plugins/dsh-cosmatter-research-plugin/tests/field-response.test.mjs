import assert from 'node:assert/strict'
import test from 'node:test'
import { fieldResponseTool } from '../lib/field-response.js'

const fieldPair = { axis: 'z', mechanical_boundary: 'fixed_stress', field_magnitude_V_per_m: 1e6 }
const compute = args => fieldResponseTool.execute({ ...fieldPair, ...args }, {})

test('recovers a dielectric response from symmetric fields with a remanent offset', async () => {
  const deltaP = 100 * 8.8541878188e-12 * fieldPair.field_magnitude_V_per_m
  const result = await compute({ observable: 'polarization_C_per_m2', mechanical_boundary: 'fixed_strain',
    mean_at_plus_field: 0.2 + deltaP, mean_at_minus_field: 0.2 - deltaP })
  assert.equal(result.component, 'epsilon_r_33')
  assert.equal(result.unit, '1')
  assert.equal(result.mechanical_boundary, 'fixed_strain')
  assert.ok(Math.abs(result.value - 101) < 1e-9)
})

test('preserves the sign of the converse coefficient and converts m/V to pm/V', async () => {
  const args = { observable: 'normal_strain', mean_at_minus_field: 5e-5, mean_at_plus_field: -5e-5 }
  const result = await compute(args)
  assert.equal(result.component, 'd33')
  assert.equal(result.unit, 'pm/V')
  assert.equal(result.value, -50)
  for (const change of [{ mechanical_boundary: 'fixed_strain' }, { field_magnitude_V_per_m: 0 },
    { field_magnitude_V_per_m: -1 }, { mean_at_plus_field: NaN }, { axis: 'xy' }, { observable: 'percent' }]) {
    await assert.rejects(compute({ ...args, ...change }))
  }
})
