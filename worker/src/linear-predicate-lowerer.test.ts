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

test('lowers bare formulas embedded in Japanese prose', () => {
  const result = lowerLinearPredicateStatement(
    '実数 x,y は x+y=19, y=4 を満たす。x を求めよ。',
  )
  assert.equal(result.status, 'lowered')
  if (result.status !== 'lowered') return
  assert.equal(result.certificate.status, 'proved')
  assert.equal(result.certificate.value, '15')
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

test('compiles Japanese solve imperatives without a registered problem shape', () => {
  const result = lowerLinearPredicateStatement('方程式 $7x-5=30$ を解け。')
  assert.equal(result.status, 'lowered')
  if (result.status !== 'lowered') return
  assert.equal(result.certificate.status, 'proved')
  assert.equal(result.certificate.value, '5')
  assert.equal(result.elaboration?.goal_source, 'single_unknown')
  assert.equal(result.elaboration?.query_kind, 'compute')
})

test('separates a queried equality from its supporting constraints', () => {
  const result = lowerLinearPredicateStatement(
    '実数 $x,y$ は $x+y=10$, $y=3$ を満たす。このとき $x=7$ を示せ。',
  )
  assert.equal(result.status, 'lowered')
  if (result.status !== 'lowered') return
  assert.equal(result.program.equations.length, 2)
  assert.equal(result.certificate.status, 'proved')
  assert.equal(result.certificate.value, '0')
  assert.equal(result.certificate.expectedMatches, true)
  assert.equal(result.elaboration?.goal_source, 'query_relation')
  assert.equal(result.elaboration?.query_kind, 'prove')
})

test('infers an angle coordinate from the mathematical language', () => {
  const result = lowerLinearPredicateStatement(
    '角を表す量 $d_a,d_b,d_c$ が $d_a-d_b=\\frac{1}{2}$, $d_b-d_c=0$ を満たす。$d_a-d_c$ を求めよ。',
  )
  assert.equal(result.status, 'lowered')
  if (result.status !== 'lowered') return
  assert.equal(result.program.coordinate, 'angle')
  assert.equal(result.certificate.status, 'proved')
  assert.equal(result.certificate.value, '1/2')
})

test('alpha-renaming and changed constants recompute the answer', () => {
  const cases = [
    ['実数 $p,q$ は $p+q=23$, $q=8$ を満たす。$p$ を計算せよ。', '15'],
    ['実数 $u,v$ は $u+v=41$, $v=12$ を満たす。$u$ を求めなさい。', '29'],
  ] as const
  for (const [statement, expected] of cases) {
    const result = lowerLinearPredicateStatement(statement)
    assert.equal(result.status, 'lowered')
    if (result.status !== 'lowered') continue
    assert.equal(result.certificate.status, 'proved')
    assert.equal(result.certificate.value, expected)
  }
})
