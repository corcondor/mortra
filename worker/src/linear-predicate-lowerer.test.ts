import assert from 'node:assert/strict'
import test from 'node:test'
import { lowerLinearPredicateDocument, lowerLinearPredicateStatement } from './linear-predicate-lowerer'

test('lowers raw TeX equations and executes an affine query exactly', () => {
  const result = lowerLinearPredicateStatement(
    '実数 $x,y$ は $x+y=10$, $y=3$ を満たす。$x+2$ を求めよ。',
  )
  assert.equal(result.status, 'lowered')
  if (result.status !== 'lowered') return
  assert.equal(result.certificate.status, 'proved')
  assert.equal(result.certificate.value, '9')
  assert.equal(result.certificate.usedProvenance.length, 2)
})

test('one lowering morphism executes additive, valuation, and angle coordinates', () => {
  const documents = [
    {
      coordinate: 'additive' as const,
      relations: ['f-i-g=0', 'g=3', 'f=11'],
      goal: 'i',
      expected: 8,
    },
    {
      coordinate: 'log_multiplicative' as const,
      relations: ['v_a-v_b=0', 'v_b-v_c=0'],
      goal: 'v_a-v_c',
      expected: 0,
    },
    {
      coordinate: 'angle' as const,
      relations: ['d_a-d_b=\\frac{1}{2}', 'd_b-d_c=0'],
      goal: 'd_a-d_c',
      expected: '1/2',
    },
  ]
  for (const document of documents) {
    const result = lowerLinearPredicateDocument(document)
    assert.equal(result.status, 'lowered')
    if (result.status !== 'lowered') continue
    assert.equal(result.certificate.status, 'proved')
    assert.equal(result.certificate.expectedMatches, true)
    assert.ok(result.certificate.usedProvenance.length >= 2)
  }
})

test('surface and number changes preserve the executable lowering contract', () => {
  const cases = [
    { relations: ['x+y=17', 'y=5'], goal: 'x', expected: 12 },
    { relations: ['u+v=31', 'v=7'], goal: 'u', expected: 24 },
  ]
  const results = cases.map(item => lowerLinearPredicateDocument({ coordinate: 'additive', ...item }))
  for (const result of results) {
    assert.equal(result.status, 'lowered')
    if (result.status !== 'lowered') continue
    assert.equal(result.certificate.status, 'proved')
    assert.equal(result.certificate.expectedMatches, true)
    assert.equal(result.program.equations.length, 2)
  }
})

test('rejects nonlinear products instead of pretending a backend exists', () => {
  const result = lowerLinearPredicateDocument({
    coordinate: 'additive',
    relations: ['x\\cdot y=6'],
    goal: 'x',
  })
  assert.equal(result.status, 'nonlinear')
})
