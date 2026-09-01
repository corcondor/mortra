import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof } from './autonomous-synthesis'
import { capabilityOrigin } from './execution-certificate'
import { runPublicRuntimeGeneration } from './public-runtime-generation'
import { auditLatticePickChart, synthesizeRuntimeLatticePickProblems } from './runtime-lattice-pick-generation'

const parents = [
  {
    id: 'pick-polygon',
    statement: '格子点を頂点とする単純な凸多角形について、面積、内部格子点数、境界格子点数の関係を証明せよ。',
  },
  {
    id: 'coprime-line',
    statement: '互いに素な正の整数 a,b に対し、直線 ax+by=ab の第1象限内の線分上にある格子点を分類し、その個数を求めよ。',
  },
]

test('connects a Pick invariant and a coprime affine segment exactly', () => {
  const result = synthesizeRuntimeLatticePickProblems(parents, 1)
  assert.equal(result.applicable, true)
  assert.ok(result.hypothesesEvaluated > 100)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.equal(card.family_id, 'runtime.lattice_pick_diophantine')
  assert.match(card.answer_tex, /a\+b\+1/)
  assert.match(card.answer_tex, /\(a-1\)\(b-1\)/)
  assert.equal(hasCompleteParentProof(card, parents), true)
  assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.equal((card.diagram as { kind?: string }).kind, 'plane')
  assert.equal((card.visual_explanation as { steps?: unknown[] }).steps?.length, 4)
})

test('independent enumeration validates the chart over many unseen coprime pairs', () => {
  const rows = auditLatticePickChart(24)
  assert.ok(rows.length > 250)
  for (const row of rows) {
    assert.equal(row.segmentPoints, 2)
    assert.equal(row.boundaryPoints, row.first + row.second + 1)
    assert.equal(row.interiorPoints, (row.first - 1) * (row.second - 1) / 2)
    assert.equal(row.floorSum, row.interiorPoints)
  }
})

test('generates three structurally distinct questions from one proved chart', () => {
  const result = synthesizeRuntimeLatticePickProblems(parents, 5)
  assert.equal(result.cards.length, 3)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 3)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, parents)))
})

test('preserves renamed coefficient and coordinate symbols in English inputs', () => {
  const renamed = [
    {
      id: 'pick-English',
      statement: "Prove Pick's theorem relating the area, interior lattice points, and boundary lattice points of a lattice polygon.",
    },
    {
      id: 'segment-English',
      statement: 'For coprime positive integers r,s, classify the lattice points on the first-quadrant segment rX+sY=rs.',
    },
  ]
  const result = synthesizeRuntimeLatticePickProblems(renamed, 1)
  assert.equal(result.cards.length, 1)
  assert.match(result.cards[0].statement_tex, /r,s/)
  assert.match(result.cards[0].statement_tex, /\(s,0\)/)
  assert.match(result.cards[0].solution_tex, /rX\+sY=rs/)
  assert.equal(hasCompleteParentProof(result.cards[0], renamed), true)
})

test('public generation resolves the formerly queued lattice fusion immediately', () => {
  const result = runPublicRuntimeGeneration(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.ok(result.cards.every(card => card.family_id === 'runtime.lattice_pick_diophantine'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
})

test('abstains when coprimality or the Pick relation is absent', () => {
  const missingCoprime = synthesizeRuntimeLatticePickProblems([
    parents[0],
    { id: 'line-only', statement: '正の整数 a,b に対し、直線 ax+by=ab の第1象限内の線分上にある格子点を求めよ。' },
  ], 1)
  const missingPick = synthesizeRuntimeLatticePickProblems([
    { id: 'polygon-only', statement: '格子点を頂点とする凸多角形を考える。' },
    parents[1],
  ], 1)
  assert.equal(missingCoprime.cards.length, 0)
  assert.equal(missingPick.cards.length, 0)
})
