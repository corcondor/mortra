import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DEFAULT_SYNTHESIS_STRATEGIES,
  hasCompleteParentProof,
  isAutonomousResearchDue,
  runAutonomousSynthesis,
  type SynthesisStrategy,
} from './autonomous-synthesis'
import { registeredMorphismCertificate } from './execution-certificate'

const parents = [
  { id: 'map', statement: '一次分数変換 T(z)=\\frac{3z+2}{z+2} を反復する。' },
  { id: 'orbit', statement: 'z_1,\\ldots,z_n を z^n=1 の全ての解とする。' },
]

test('solves an unseen single problem from typed constraints instead of catalog replay', () => {
  const input = [{
    id: 'unseen-single-linear',
    statement: '実数 $x,y$ は $x+y=19$, $y=4$ を満たす。$x$ を求めよ。',
  }]
  const result = runAutonomousSynthesis(input, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '15')
  assert.equal(result.cards[0].family_id, 'certified.single_problem.exact_linear_invariant')
  assert.equal(result.cards[0].parent_ids[0], input[0].id)
  assert.equal(hasCompleteParentProof(result.cards[0], input), true)
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_linear_program')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  assert.equal(result.attempts[0].strategy, 'exact-single-problem-proof-synthesis')
  assert.equal(result.attempts[0].generated, 1)
})

test('generates one-to-many fresh problems from multiple current constraint systems', () => {
  const input = [
    {
      id: 'unseen-linear-left',
      statement: '実数 $x,y$ は $x+y=17$, $x-y=5$ を満たす。$x$ を求めよ。',
    },
    {
      id: 'unseen-linear-right',
      statement: '実数 $a,b$ は $2a+b=13$, $a-b=2$ を満たす。$b$ を求めよ。',
    },
  ]
  const result = runAutonomousSynthesis(input, 6)
  const attempt = result.attempts.find(item => item.strategy === 'runtime-linear-problem-generation')
  const generated = result.cards.filter(card => card.family_id === 'runtime.linear_constraint_composition')

  assert.equal(result.cards.length, 6)
  assert.ok(attempt)
  assert.ok((attempt?.generated ?? 0) > 0)
  assert.ok(generated.length > 0)
  assert.equal(new Set(generated.map(card => card.statement_tex)).size, generated.length)
  assert.ok(generated.every(card => hasCompleteParentProof(card, input)))
  assert.ok(generated.every(card => card.execution_certificate?.registered_composite_used === false))
})

test('preserves a single unresolved obligation for later rounds', () => {
  const input = [{
    id: 'unseen-single-nonlinear',
    statement: '実数 $x,y$ は $xy=6$ を満たす。$x$ の最大値を求めよ。',
  }]
  const result = runAutonomousSynthesis(input, 1, null, [], new Date('2026-09-01T00:00:00Z'))
  assert.equal(result.cards.length, 0)
  assert.equal(result.state.continuing, true)
  assert.ok(result.state.frontier.length > 0)
})

test('synthesizes a symbolic power orbit at runtime and has no registered-route fallback', () => {
  const result = runAutonomousSynthesis(parents, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.state.continuing, false)
  assert.equal(result.attempts[0].strategy, 'arithmetic-geometry-relational-synthesis')
  assert.equal(result.attempts[0].applicable, false)
  const typedAttempt = result.attempts.find(attempt => attempt.strategy === 'runtime-typed-program-execution')
  assert.equal(typedAttempt?.applicable, true)
  assert.equal(typedAttempt?.generated, 1)
  assert.equal(result.attempts.some(attempt => attempt.strategy === 'registered-composite-program-instantiation'), false)
  assert.equal(DEFAULT_SYNTHESIS_STRATEGIES.some(strategy => strategy.id === 'registered-composite-program-instantiation'), false)
  assert.equal(result.state.synthesized_programs?.length, 1)
  assert.equal(result.state.reused_parameterized_morphisms, 0)
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_proof_program')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  assert.deepEqual(result.cards[0].morphism_chain, [
    'MobiusMap',
    'RootsOfUnity',
    'MapOrbitEvaluation',
    'FiniteSummation',
  ])
})

test('routes unseen polynomial parents to the generic elimination backend', () => {
  const polynomialParents = [
    { id: 'p', statement: '方程式 $x^2-2=0$ の根を考える。' },
    { id: 'q', statement: '方程式 $y^2-3=0$ の根を考える。' },
  ]
  const result = runAutonomousSynthesis(polynomialParents, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].family_id, 'runtime.polynomial_root_sum')
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_proof_program')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  assert.equal(result.state.composite_cache_mode, 'not_consulted')
  assert.deepEqual(result.attempts.map(attempt => [attempt.strategy, attempt.applicable]), [
    ['arithmetic-geometry-relational-synthesis', false],
    ['runtime-polynomial-root-generation', true],
  ])
})

test('persisted composite laws cannot add reachability to cold synthesis', () => {
  const input = [
    { id: 'cold-left', statement: '方程式 $x^2-11=0$ の根を考える。' },
    { id: 'cold-right', statement: '方程式 $y^2-13=0$ の根を考える。' },
  ]
  const cold = runAutonomousSynthesis(input, 1)
  const withIrrelevantCache = runAutonomousSynthesis(
    input,
    1,
    null,
    DEFAULT_SYNTHESIS_STRATEGIES,
    new Date(),
    [{
      name: 'CachedCompositeThatMustNotAddReachability',
      expression: 'x_0**97+x_1**89',
      arity: 2,
      sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
      target: 'FiniteAlgebraicOrbit',
      preserves: ['cached-only'],
      backend: ['none'],
    }],
  )
  assert.equal(cold.cards.length, 1)
  assert.equal(withIrrelevantCache.cards.length, 1)
  assert.equal(withIrrelevantCache.cards[0].answer_tex, cold.cards[0].answer_tex)
  assert.equal(withIrrelevantCache.enumeration.terms.length, cold.enumeration.terms.length)
  assert.equal(withIrrelevantCache.enumeration.goals.length, cold.enumeration.goals.length)
  assert.equal(withIrrelevantCache.state.composite_cache_mode, 'duplicate_exclusion_only')
  assert.equal(withIrrelevantCache.cards[0].execution_certificate?.registered_composite_used, false)
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
  assert.ok(result.cards.every(card =>
    card.execution_certificate?.capability_origin === 'synthesized_proof_program'))
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
  assert.ok((first.state.local_expansions ?? 0) > 0)
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

test('rejects a card whose generation origin is not certified', () => {
  const seed = runAutonomousSynthesis(parents, 1).cards[0]
  const uncertified = { ...seed, execution_certificate: undefined }
  const strategy: SynthesisStrategy = {
    id: 'missing-origin',
    version: 1,
    supports: () => ({ applicable: true, reason: 'test fixture' }),
    execute: () => [uncertified],
  }
  const result = runAutonomousSynthesis(parents, 1, null, [strategy])
  assert.equal(result.cards.length, 0)
  assert.equal(result.state.synthesized_programs?.length, 0)
})

test('never delivers a registered completed route as autonomous generation', () => {
  const seed = runAutonomousSynthesis(parents, 1).cards[0]
  const replay = {
    ...seed,
    execution_certificate: registeredMorphismCertificate({
      parents,
      program: { route: 'stored-composite' },
      checks: ['research replay only'],
    }),
  }
  const strategy: SynthesisStrategy = {
    id: 'registered-replay-fixture',
    version: 1,
    supports: () => ({ applicable: true, reason: 'test fixture' }),
    execute: () => [replay],
  }

  const result = runAutonomousSynthesis(parents, 1, null, [strategy])
  assert.equal(result.cards.length, 0)
  assert.equal(result.attempts[0].generated, 0)
  assert.match(result.attempts[0].reason, /cannot count as autonomous generation/)
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
  assert.equal(result.attempts.some(attempt => attempt.strategy === 'registered-composite-program-instantiation'), false)
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

test('generates many nonlinear algebraic questions from two unseen root systems', () => {
  const polynomialParents = [
    { id: 'unseen-root-left', statement: '方程式 $x^2-3x-7=0$ のすべての根を考える。' },
    { id: 'unseen-root-right', statement: '方程式 $y^3+2y-5=0$ のすべての根を考える。' },
  ]
  const result = runAutonomousSynthesis(polynomialParents, 6)
  assert.equal(result.cards.length, 6)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 6)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, polynomialParents)))
  assert.ok(result.cards.every(card => card.execution_certificate?.capability_origin === 'synthesized_proof_program'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
  assert.ok(result.cards.every(card => card.verification.exact_backend && card.verification.independent_check))
  assert.ok(result.cards.some(card => card.morphism_chain.includes('RootMinkowskiSum')))
  assert.ok(result.cards.some(card => card.morphism_chain.includes('RootPointwiseProduct')))
})
