import assert from 'node:assert/strict'
import test from 'node:test'
import { induceArithmeticGeometryLemmas } from './arithmetic-geometry-inducer'

test('synthesizes an abstract radius-product divisibility lemma from two endpoints', () => {
  const result = induceArithmeticGeometryLemmas([
    { id: 'geometry', statement: '三角形の外接円半径 R と内接円半径 r の関係を考える。' },
    { id: 'arithmetic', statement: '正の整数と素数に関する整除条件を考える。' },
  ], 2, 1)
  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 2)
  assert.deepEqual(result.cards[0].parent_ids, ['geometry', 'arithmetic'])
  assert.match(result.cards[0].statement_tex, /Rr/)
  assert.match(result.cards[0].statement_tex, /\\mid/)
  assert.equal(result.cards[0].fusion_derivation.assignments.length, 2)
  assert.equal(result.cards[0].fusion_derivation.ablationPassed, true)
  assert.equal(result.cards[0].structure_blueprint.structuralUniqueness?.uniqueNormalForm, true)
  assert.equal(result.cards[0].structure_blueprint.structuralUniqueness?.finiteSolutionSet, false)
  assert.deepEqual(result.cards[0].structure_blueprint.structuralUniqueness?.numericInstanceConstants, [])
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_proof_program')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
})

test('derives integer topology lemmas from Euler and incidence relations', () => {
  const result = induceArithmeticGeometryLemmas([
    { id: 'topology', statement: '閉曲面の有限三角形分割と Euler 標数を考える。' },
    { id: 'number-theory', statement: '整数の最大公約数と素数条件を考える。' },
  ], 2, 1)
  assert.equal(result.applicable, true)
  assert.equal(result.modes.includes('topology'), true)
  assert.match(result.cards[0].statement_tex, /gcd|\\gcd/)
  assert.match(result.cards[0].answer_tex, /V-\\chi/)
  assert.ok(result.cards[0].morphism_chain.includes('IncidenceDoubleCounting'))
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'registered_parameterized_morphism')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, true)
})

test('rejects redundant or unrelated parent selections', () => {
  const redundant = induceArithmeticGeometryLemmas([
    { id: 'both', statement: '整数三角形の外接円半径の積が素数である。' },
    { id: 'extra', statement: '別の整数について考える。' },
  ], 1, 1)
  assert.equal(redundant.applicable, false)
  const unrelated = induceArithmeticGeometryLemmas([
    { id: 'analysis', statement: '関数を微分する。' },
    { id: 'sequence', statement: '数列の極限を求める。' },
  ], 1, 1)
  assert.equal(unrelated.applicable, false)
})

test('rejects broad-tag fusion when distinctive parent conditions are not consumed', () => {
  const result = induceArithmeticGeometryLemmas([
    {
      id: 'normal-triangle',
      statement: '放物線上への3本の法線の足を頂点とする三角形について、外接円半径の最小値を求めよ。',
    },
    {
      id: 'matrix-prime',
      statement: '整数行列 A の n 乗から漸化式を導き、ある素数が項を割り切ることを示せ。',
    },
  ], 3, 1)
  assert.equal(result.applicable, false)
  assert.equal(result.cards.length, 0)
})

test('registered abstract laws are excluded on the next round', () => {
  const parents = [
    { id: 'geometry', statement: '三角形の外接円半径と内接円半径を考える。' },
    { id: 'arithmetic', statement: '整数の整除性と素数性を考える。' },
  ]
  const first = induceArithmeticGeometryLemmas(parents, 1, 1)
  const law = first.cards[0].structure_blueprint.synthesizedLaw!
  const next = induceArithmeticGeometryLemmas(parents, 1, 1, [law])
  assert.equal(next.cards.length, 1)
  assert.notEqual(next.cards[0].structure_blueprint.synthesizedLaw!.expression, law.expression)
})

test('surface wording does not change the structural uniqueness certificate', () => {
  const first = induceArithmeticGeometryLemmas([
    { id: 'g1', statement: '三角形の外接円半径と内接円半径を考える。' },
    { id: 'a1', statement: '整数の整除性と素数性を考える。' },
  ], 1, 1)
  const renamed = induceArithmeticGeometryLemmas([
    { id: 'g2', statement: 'Let T be a triangle with circumradius R and inradius r.' },
    { id: 'a2', statement: 'Study prime and integer divisibility predicates.' },
  ], 1, 1)
  const left = first.cards[0].structure_blueprint.structuralUniqueness!
  const right = renamed.cards[0].structure_blueprint.structuralUniqueness!
  assert.equal(left.normalForm, right.normalForm)
  assert.equal(left.quotientAction, right.quotientAction)
  assert.deepEqual(left.conditionSkeleton, right.conditionSkeleton)
})
