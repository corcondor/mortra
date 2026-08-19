import test from 'node:test'
import assert from 'node:assert/strict'

import { buildProblemDiagram } from '../lib/mortra/problem-artifact'

test('geometry families produce an explanatory plane figure', () => {
  const diagram = buildProblemDiagram({
    familyId: 'construct.axis_intercept_segment_swept_region',
    domain: 'geometry',
    parameters: { c: 8 },
    morphismChain: ['MovingIntercepts', 'SweptRegion', 'AreaIntegral'],
  })

  assert.equal(diagram.kind, 'plane')
  if (diagram.kind !== 'plane') return
  assert.ok(diagram.shapes.some(shape => shape.kind === 'polyline' && shape.fill))
  assert.match(diagram.caption, /通過/)
})

test('probability families produce a state transition figure', () => {
  const diagram = buildProblemDiagram({
    familyId: 'construct.gambler_ruin_probability',
    domain: 'probability',
    parameters: { N: 12, k: 5, pa: 2, pb: 1 },
    morphismChain: ['AbsorbingWalk', 'BoundaryRecurrence', 'RatioClosedForm'],
  })

  assert.equal(diagram.kind, 'state')
  if (diagram.kind !== 'state') return
  assert.ok(diagram.states.some(state => state.active && state.label === '5'))
  assert.ok(diagram.states.filter(state => state.terminal).length === 2)
  assert.ok(diagram.transitions.length > 0)
})

test('analysis families produce the function curves used by the estimate', () => {
  const diagram = buildProblemDiagram({
    familyId: 'runtime.integral_state.endpoint_squeeze',
    domain: 'analysis',
    parameters: { lambda: 3 },
    morphismChain: ['DefineIntegralState', 'BoundPositiveRemainder', 'SqueezeEndpointConcentration'],
  })

  assert.equal(diagram.kind, 'plane')
  if (diagram.kind !== 'plane') return
  assert.equal(diagram.shapes.filter(shape => shape.kind === 'polyline').length, 3)
  assert.match(diagram.caption, /挟み撃ち/)
})

test('unknown families fall back to the actual morphism chain', () => {
  const diagram = buildProblemDiagram({
    familyId: 'runtime.unknown',
    domain: 'number_theory',
    morphismChain: ['IntegerObject', 'ModularReduction', 'FiniteCaseSplit', 'Conclusion'],
  })

  assert.equal(diagram.kind, 'morphism')
  if (diagram.kind !== 'morphism') return
  assert.deepEqual(diagram.nodes, ['IntegerObject', 'ModularReduction', 'FiniteCaseSplit', 'Conclusion'])
})

test('quadratic extrema produce a variation table from coefficients', () => {
  const diagram = buildProblemDiagram({
    familyId: 'construct.quadratic_extremum',
    parameters: { a: 1, b: -4, c: 7 },
  })

  assert.equal(diagram.kind, 'variation')
  if (diagram.kind !== 'variation') return
  assert.deepEqual(diagram.columns, ['-∞', '2', '+∞'])
  assert.deepEqual(diagram.rows[0].cells, ['-', '0', '+'])
  assert.equal(diagram.rows[1].cells[1], '3')
})
