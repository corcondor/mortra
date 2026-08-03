import assert from 'node:assert/strict'
import test from 'node:test'
import { extractMobiusMap, synthesizeExecutableFusions } from './executable-fusion'

const parents = [
  {
    id: 'graph-parent',
    statement: 'Möbius変換 T(z) = \\frac{3z+2}{z+2} を反復する。',
    solution: '有向グラフの隣接行列を考える。',
  },
  {
    id: 'root-parent',
    statement: 'z_1,\\ldots,z_n を方程式 z^n = 1 の全ての解とする。',
    solution: '根多項式と対数微分を用いる。',
  },
]

test('extracts an unseen Mobius map from the selected parent statement', () => {
  assert.deepEqual(extractMobiusMap(parents), { matrix: [3n, 2n, 1n, 2n], parentId: 'graph-parent' })
})

test('synthesizes requested verified problems instead of pending structures', () => {
  const cards = synthesizeExecutableFusions(parents, 3)
  assert.equal(cards.length, 3)
  assert.deepEqual(cards.map(card => card.parent_ids), [
    ['graph-parent', 'root-parent'], ['graph-parent', 'root-parent'], ['graph-parent', 'root-parent'],
  ])
  assert.ok(cards.every(card => card.answer_tex && card.discovery_status === 'verified' && !card.unresolved))
  assert.ok(cards.every(card => card.structure_blueprint.proofCertificate.length >= 6))
  assert.match(cards[0].statement_tex, /z\^n=1/)
  assert.match(cards[0].statement_tex, /\\sum/)
  assert.doesNotMatch(cards[0].statement_tex, /\\su2/)
  assert.match(cards[0].answer_tex, /11/)
  assert.doesNotMatch(cards[0].answer_tex, /-\\frac\{-/)
})

test('does not invent a bridge when either structural input is absent', () => {
  assert.deepEqual(synthesizeExecutableFusions([parents[0], { id: 'other', statement: '三角形の面積を求めよ。' }], 3), [])
})

test('rejects an iterate with a pole on the unit root orbit', () => {
  const singularParents = [
    { id: 'map', statement: 'T(z) = \\frac{z+2}{z-1}' },
    parents[1],
  ]
  assert.deepEqual(synthesizeExecutableFusions(singularParents, 3), [])
})
