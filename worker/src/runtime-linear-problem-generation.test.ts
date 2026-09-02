import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof } from './autonomous-synthesis'
import { synthesizeRuntimeLinearProblems } from './runtime-linear-problem-generation'

const freshParents = [
  {
    id: 'fresh-affine-left',
    statement: '実数 $x,y$ は $x+y=17$, $x-y=5$ を満たす。$x$ を求めよ。',
  },
  {
    id: 'fresh-affine-right',
    statement: '実数 $a,b$ は $2a+b=13$, $a-b=2$ を満たす。$b$ を求めよ。',
  },
]

test('generates many exact problems from fresh current constraints without a registered route', () => {
  const result = synthesizeRuntimeLinearProblems(freshParents, 6)
  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 6)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 6)
  assert.equal(new Set(result.cards.map(card => card.answer_tex)).size, 6)

  for (const card of result.cards) {
    assert.equal(card.family_id, 'runtime.linear_constraint_composition')
    assert.equal(card.execution_certificate?.capability_origin, 'synthesized_linear_program')
    assert.equal(card.execution_certificate?.registered_composite_used, false)
    assert.equal(hasCompleteParentProof(card, freshParents), true)
    assert.deepEqual(new Set(card.parent_ids), new Set(freshParents.map(parent => parent.id)))
    assert.match(card.statement_tex, /u_\{1,1\}/)
    assert.match(card.statement_tex, /実数 \\\(u_\{1,1\}/)
    assert.match(card.statement_tex, /u_\{2,2\}\\\) が/)
    assert.match(card.statement_tex, /\\quad/)
    assert.doesNotMatch(card.statement_tex, /:quad/)
    assert.match(card.solution_tex, /線形結合/)

    const program = card.execution_certificate?.generated_program as {
      schema: string
      parent_blocks: Array<{ parent_id: string; target_contribution: Record<string, string> }>
      ablations: Array<{ parent_id: string; status: string }>
      counterfactuals: Array<{ parent_id: string; value_before: string; value_after: string }>
      proof_coefficients: string[]
    }
    assert.equal(program.schema, 'mortra.runtime-linear-problem-generation.v1')
    assert.equal(program.parent_blocks.length, 2)
    assert.ok(program.parent_blocks.every(block => Object.keys(block.target_contribution).length > 0))
    assert.ok(program.ablations.every(ablation => ablation.status !== 'proved'))
    assert.ok(program.counterfactuals.every(counterfactual =>
      counterfactual.value_before !== counterfactual.value_after))
    assert.ok(program.proof_coefficients.some(coefficient => coefficient !== '0'))
  }
})

test('a fresh parent constant changes the generated exact answer', () => {
  const baseline = synthesizeRuntimeLinearProblems(freshParents, 1)
  const changed = synthesizeRuntimeLinearProblems([
    freshParents[0],
    {
      ...freshParents[1],
      statement: '実数 $a,b$ は $2a+b=29$, $a-b=2$ を満たす。$b$ を求めよ。',
    },
  ], 1)
  assert.equal(baseline.cards.length, 1)
  assert.equal(changed.cards.length, 1)
  assert.notEqual(changed.cards[0].answer_tex, baseline.cards[0].answer_tex)
  assert.notEqual(
    changed.cards[0].execution_certificate?.input_parent_sha256,
    baseline.cards[0].execution_certificate?.input_parent_sha256,
  )
})

test('one fresh affine parent supports one-to-many coordinate synthesis', () => {
  const parent = [{
    id: 'single-unseen-affine',
    statement: '実数 $t$ が $11t-7=48$ を満たすとき、$t$ を求めよ。',
  }]
  const result = synthesizeRuntimeLinearProblems(parent, 4)
  assert.equal(result.cards.length, 4)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 4)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, parent)))
})

test('does not pretend nonlinear input is covered by the affine generator', () => {
  const result = synthesizeRuntimeLinearProblems([{
    id: 'fresh-nonlinear',
    statement: '正の実数 $x,y$ が $xy=14$ を満たすとき、$x+y$ の最小値を求めよ。',
  }], 3)
  assert.equal(result.applicable, false)
  assert.equal(result.cards.length, 0)
  assert.match(result.reason, /not an executable additive constraint system/)
})
