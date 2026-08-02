import assert from 'node:assert/strict'
import test from 'node:test'
import { discoverParentStructures } from './parent-conditioned-discovery'

const integral = (id: string, variable = 'a_n', upper = '1') => ({
  id,
  statement: `数列 ${variable}=\\int_0^${upper}x^n dx の極限を求めよ。`,
})
const congruence = (id: string, variable = 'x', residue = '1') => ({
  id,
  statement: `素数 p に対し ${variable}^2\\equiv-${residue}\\pmod p の可解性を示せ。`,
})

test('unknown parents are lifted from their operators instead of a remembered family', () => {
  const result = discoverParentStructures([integral('i'), congruence('n')], 3)
  assert.equal(result.discovered, 3)
  assert.match(result.cards[0].structure_blueprint.observable, /IntegralFunctional/)
  assert.match(result.cards[0].structure_blueprint.observable, /IntegerStructure/)
  assert.deepEqual(result.cards[0].parent_ids, ['i', 'n'])
  assert.equal(result.cards[0].unresolved, true)
})

test('surface variable and numeric changes preserve the abstract lift', () => {
  const first = discoverParentStructures([integral('i1'), congruence('n1')])
  const second = discoverParentStructures([integral('i2', 'b_k', '2'), congruence('n2', 'y', '2')])
  assert.deepEqual(
    first.parent_graphs.map(graph => graph.semantic_roots),
    second.parent_graphs.map(graph => graph.semantic_roots),
  )
})

test('all selected parents remain distinct proof inputs', () => {
  const result = discoverParentStructures([integral('i'), congruence('n'), { id: 'g', statement: '三角形の重心の軌跡が囲む面積を求めよ。' }])
  const derivation = result.cards[0].fusion_derivation
  assert.equal(derivation.ablationPassed, true)
  assert.equal(derivation.assignments.length, 3)
  assert.equal(new Set(derivation.assignments.map(item => item.parentId)).size, 3)
})
