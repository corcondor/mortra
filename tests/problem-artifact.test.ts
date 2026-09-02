import test from 'node:test'
import assert from 'node:assert/strict'

import { buildProblemDiagram } from '../lib/mortra/problem-artifact'
import { validateCalculusAnalysis, type CertifiedCalculusAnalysis } from '../lib/mortra/calculus-analysis'
import { diagramMathToPlainText } from '../lib/mortra/diagram-text'
import { generateLiveProblem } from '../lib/mathos-live'

test('SVG math annotations use readable Unicode instead of raw TeX', () => {
  assert.equal(
    diagramMathToPlainText('2+2\\sqrt{2},\\quad x\\to\\infty'),
    '2+2\u221a2, x\u2192\u221e',
  )
  assert.equal(diagramMathToPlainText('(-\\infty,1-\\sqrt{2})'), '(-\u221e,1-\u221a2)')
  assert.equal(
    diagramMathToPlainText('A(z)=\\sum_{n\\ge0}a_n z^n'),
    'A(z)=\u03a3[n\u22650]a[n] z^n',
  )
  assert.equal(diagramMathToPlainText('\\alpha+\\beta, \\theta, \\varphi'), '\u03b1+\u03b2, \u03b8, \u03c6')
})

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

test('root-triangle fusion draws the triangle together with its in- and circumcircles', () => {
  const diagram = buildProblemDiagram({
    familyId: 'runtime.root_triangle.polynomial.radius_ratio',
    domain: 'geometry_algebra',
    parameters: {
      rootA: 4.2,
      rootB: 5.1,
      rootC: 6.3,
      semiperimeter: 7.8,
      areaSquared: 109.870236,
    },
    morphismChain: ['VietaFirstSum', 'HeronFactorization', 'RadiusRatio'],
  })

  assert.equal(diagram.kind, 'plane')
  if (diagram.kind !== 'plane') return
  assert.equal(diagram.shapes.filter(shape => shape.kind === 'circle').length, 2)
  assert.ok(diagram.shapes.some(shape => shape.kind === 'polyline' && shape.closed))
  assert.match(diagram.caption, /3根/)
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

test('calculus artifacts use a backend-produced domain partition rather than a quadratic shortcut', () => {
  const calculusAnalysis: CertifiedCalculusAnalysis = {
    version: 1,
    variable: 't',
    functionTex: '\\frac{t+1}{t-1}',
    derivativeTex: '-\\frac{2}{(t-1)^2}',
    domainTex: '\\mathbb{R}\\setminus\\{1\\}',
    columns: [
      { role: 'interval', label: '(-\\infty,1)', derivative: '-', behavior: 'decrease', functionLabel: '' },
      { role: 'singularity', label: '1', x: 1, derivative: 'undefined', behavior: 'discontinuous', functionLabel: '不定義' },
      { role: 'interval', label: '(1,+\\infty)', derivative: '-', behavior: 'decrease', functionLabel: '' },
    ],
    plot: {
      viewport: { xMin: -4, xMax: 6, yMin: -5, yMax: 7 },
      segments: [
        [{ x: -4, y: 0.6 }, { x: 0, y: -1 }, { x: 0.8, y: -9 }],
        [{ x: 1.2, y: 11 }, { x: 2, y: 3 }, { x: 6, y: 1.4 }],
      ],
      keyPoints: [{ x: 1, y: 0, label: 't=1', role: 'singularity' }],
    },
    certificate: {
      method: 'exact_rational_derivative_sign_partition',
      checks: [{ id: 'domain', claim: 'denominator is nonzero exactly when t != 1', status: 'verified' }],
    },
  }
  const diagram = buildProblemDiagram({
    familyId: 'runtime.calculus.rational_variation',
    calculusAnalysis,
  })

  assert.deepEqual(validateCalculusAnalysis(calculusAnalysis), [])
  assert.equal(diagram.kind, 'calculus')
  if (diagram.kind !== 'calculus') return
  assert.equal(diagram.variation.variableLabel, 't')
  assert.deepEqual(diagram.variation.rows[0].cells, ['-', 'undefined', '-'])
  assert.equal(diagram.plot.shapes.filter(shape => shape.kind === 'polyline').length, 2)
})

test('live calculus generation returns statement, solution, sign chart, graph and certificate atomically', () => {
  const problem = generateLiveProblem({
    domain: 'analysis',
    focusTags: ['calculus', 'derivative', 'variation', 'function_graph', 'extremum'],
  })

  assert.ok(problem)
  assert.equal(problem?.familyId, 'runtime.calculus.polynomial_variation')
  assert.ok(problem?.statementTex.includes('増減表'))
  assert.ok(problem?.answerTex.includes('\\max f='))
  assert.ok(problem?.solutionTex.includes("f'(x)="))
  assert.ok(problem?.calculusAnalysis)
  assert.equal(problem?.calculusAnalysis?.certificate.checks.length, 5)

  const diagram = buildProblemDiagram({
    familyId: problem?.familyId,
    domain: problem?.domain,
    parameters: problem?.parameters,
    morphismChain: problem?.morphismChain,
    calculusAnalysis: problem?.calculusAnalysis,
  })
  assert.equal(diagram.kind, 'calculus')
  if (diagram.kind !== 'calculus') return
  assert.equal(diagram.variation.columns.length, 7)
  assert.equal(diagram.plot.shapes.filter(shape => shape.kind === 'point').length, 4)
})
