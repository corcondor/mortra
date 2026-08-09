import assert from 'node:assert/strict'
import test from 'node:test'
import {
  hasCompleteParentProof,
  isAutonomousResearchDue,
  runAutonomousSynthesis,
  type SynthesisStrategy,
} from './autonomous-synthesis'

const parents = [
  { id: 'map', statement: '一次分数変換 T(z)=\\frac{3z+2}{z+2} を反復する。' },
  { id: 'orbit', statement: 'z_1,\\ldots,z_n を z^n=1 の全ての解とする。' },
]

test('runs a typed strategy registry and returns verified cards', () => {
  const result = runAutonomousSynthesis(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.equal(result.state.continuing, false)
  assert.equal(result.attempts[0].strategy, 'arithmetic-geometry-relational-synthesis')
  assert.equal(result.attempts[0].applicable, false)
  assert.equal(result.attempts[1].strategy, 'primitive-law-cegis')
  assert.equal(result.attempts[1].applicable, false)
  assert.equal(result.attempts[2].strategy, 'typed-composite-program-synthesis')
  assert.equal(result.attempts[2].generated, 3)
  assert.equal(result.state.synthesized_programs?.length, 3)
})

test('routes unseen polynomial parents to the generic elimination backend', () => {
  const polynomialParents = [
    { id: 'p', statement: '方程式 $x^2-2=0$ の根を考える。' },
    { id: 'q', statement: '方程式 $y^2-3=0$ の根を考える。' },
  ]
  const result = runAutonomousSynthesis(polynomialParents, 1)
  assert.equal(result.cards.length, 1)
  assert.match(result.cards[0].family_id, /^discovered\.induced_algebraic_law\./)
  assert.deepEqual(result.attempts.map(attempt => [attempt.strategy, attempt.applicable]), [
    ['arithmetic-geometry-relational-synthesis', false],
    ['primitive-law-cegis', true],
  ])
})

test('routes geometry and integer endpoints to abstract relational synthesis', () => {
  const result = runAutonomousSynthesis([
    { id: 'geometry', statement: '三角形の外接円半径と内接円半径の関係を考える。' },
    { id: 'arithmetic', statement: '整数の整除性と素数性を考える。' },
  ], 3)
  assert.equal(result.cards.length, 3)
  assert.equal(result.attempts[0].strategy, 'arithmetic-geometry-relational-synthesis')
  assert.equal(result.attempts[0].generated, 3)
  assert.match(result.cards[2].family_id, /two-prime-sides/)
  assert.equal(result.state.induction_engine?.includes('sympy-relational-grammar'), true)
  assert.ok((result.state.synthesized_programs?.length ?? 0) > 0)
})

test('continuation becomes due only after its persisted wake time', () => {
  const state = { continuing: true, next_attempt_at: '2026-08-03T00:15:00.000Z' }
  assert.equal(isAutonomousResearchDue(state, new Date('2026-08-03T00:14:59.000Z')), false)
  assert.equal(isAutonomousResearchDue(state, new Date('2026-08-03T00:15:00.000Z')), true)
  assert.equal(isAutonomousResearchDue({ ...state, continuing: false }, new Date('2026-08-04T00:00:00Z')), false)
})

test('persists and expands the search frontier without claiming success', () => {
  const unknown = [
    { id: 'a', statement: '関数 f の積分で定まる数列を考える。' },
    { id: 'b', statement: '三角形の接線と重心を考える。' },
  ]
  const first = runAutonomousSynthesis(unknown, 2, null, [], new Date('2026-08-03T00:00:00Z'))
  const second = runAutonomousSynthesis(unknown, 2, first.state, [], new Date('2026-08-03T00:15:00Z'))
  assert.equal(first.cards.length, 0)
  assert.equal(first.state.continuing, true)
  assert.equal(second.state.round, 2)
  assert.ok(second.state.depth > first.state.depth)
  assert.ok(second.state.hypotheses_evaluated > first.state.hypotheses_evaluated)
  assert.ok(second.state.frontier.length > 0)
  assert.equal(first.state.stagnant_rounds, 0)
  assert.equal(second.state.stagnant_rounds, 0)
  assert.ok(first.state.local_expansions > 0)
  assert.ok((first.state.states_explored ?? 0) > 0)
  assert.equal(first.state.next_attempt_at, '2026-08-03T00:01:00.000Z')
})

test('a proposed solution cannot redefine the statement semantics', () => {
  const poisoned = [
    { id: 'a', statement: '素数 p について和を考える。', solution: '三角形の重心と面積の最小値を求める。' },
    { id: 'b', statement: '数列 a_n を考える。', solution: '一次分数変換 T(z) を反復する。' },
  ]
  const result = runAutonomousSynthesis(poisoned, 1)
  const operators = new Set(result.generalization.bindings.map(binding => binding.canonical))
  assert.equal(operators.has('Centroid'), false)
  assert.equal(operators.has('Measure'), false)
  assert.equal(operators.has('MobiusMap'), false)
  assert.equal(operators.has('PrimeRestriction'), true)
})

test('strategies are selected by their typed support contract, not problem ids', () => {
  const seen: string[] = []
  const strategies: SynthesisStrategy[] = [
    {
      id: 'not-applicable', version: 1,
      supports: () => ({ applicable: false, reason: 'wrong input sorts' }),
      execute: () => { throw new Error('must not run') },
    },
    {
      id: 'applicable', version: 1,
      supports: context => ({ applicable: context.parents.length === 2, reason: 'two typed inputs' }),
      execute: context => { seen.push(...context.parents.map(parent => String(parent.id))); return [] },
    },
  ]
  const opaqueParents = [
    { id: 'left', statement: '未知対象 A を考える。' },
    { id: 'right', statement: '未知対象 B を考える。' },
  ]
  const result = runAutonomousSynthesis(opaqueParents, 1, null, strategies)
  assert.deepEqual(seen, ['left', 'right'])
  assert.deepEqual(result.attempts.map(attempt => attempt.applicable), [false, true])
})

test('rejects a verified-looking card that drops one selected parent', () => {
  const seed = runAutonomousSynthesis(parents, 1)
  assert.equal(seed.cards.length, 1)
  const incomplete = {
    ...seed.cards[0],
    parent_ids: [parents[0].id],
    fusion_derivation: {
      ...seed.cards[0].fusion_derivation,
      assignments: seed.cards[0].fusion_derivation.assignments.slice(0, 1),
    },
  }
  assert.equal(hasCompleteParentProof(incomplete, parents), false)

  const strategy: SynthesisStrategy = {
    id: 'drops-parent',
    version: 1,
    supports: () => ({ applicable: true, reason: 'test candidate' }),
    execute: () => [incomplete],
  }
  const result = runAutonomousSynthesis(parents, 1, null, [strategy])
  assert.equal(result.cards.length, 0)
  assert.equal(result.attempts[0].generated, 0)
})

test('does not collapse two hard Sakumon endpoints to broad geometry and integer tags', () => {
  const hardParents = [
    {
      id: '5a8bd9fafc05',
      statement: '$xy$ 平面上の放物線 $C:y=x^2$ を考える。直線 $l:x-2y+57=0$ 上の点から3本の異なる法線を引き、その足が作る三角形の外接円半径 $R$ について $R^2$ の最小値を求めよ。',
    },
    {
      id: 'legacy_exam:02_kyoto:227b304d736fe9ec',
      statement: '整数行列 $A$ に対し $A^n=(a_n,b_n;c_n,d_n)$ とする。$c_n$ の漸化式を示し、素数 $p$ に関する整除性を証明せよ。',
    },
  ]
  const result = runAutonomousSynthesis(hardParents, 1)
  assert.equal(result.cards.length, 0)
  assert.equal(result.state.continuing, true)
  assert.equal(result.attempts.every(attempt => attempt.generated === 0), true)
})

test('synthesizes from two Sakumon polynomial endpoints without stored solutions', () => {
  const polynomialParents = [
    {
      id: 'mathos-5115e5e462',
      statement: '方程式 $x^3-2x^2-5x+1=0$ の3根を考える。',
    },
    {
      id: 'legacy_exam:01_tokyo:ad7a21d562abc25c',
      statement: '3次方程式 $y^3+3y^2-1=0$ の3根を考える。',
    },
  ]
  const result = runAutonomousSynthesis(polynomialParents, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(hasCompleteParentProof(result.cards[0], polynomialParents), true)
  assert.deepEqual(new Set(result.cards[0].parent_ids), new Set(polynomialParents.map(parent => parent.id)))
  assert.equal(result.cards[0].verification.exact_backend, true)
  assert.equal(result.cards[0].verification.independent_check, true)
})
