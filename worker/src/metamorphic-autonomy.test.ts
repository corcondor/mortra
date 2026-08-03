import assert from 'node:assert/strict'
import test from 'node:test'
import { synthesizePolynomialRootFusions } from './polynomial-root-fusion'

function generator(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0
    return state
  }
}

test('MathOS generates unseen coefficients and grades them without stored answers', () => {
  const next = generator(0x4d415448)
  const answers = new Set<string>()
  for (let caseIndex = 0; caseIndex < 4; caseIndex++) {
    const leftConstant = 2 + next() % 17
    let rightConstant = 2 + next() % 19
    if (rightConstant === leftConstant) rightConstant += 1
    const leftVariable = String.fromCharCode(117 + caseIndex)
    const rightVariable = String.fromCharCode(97 + caseIndex)
    const parents = [
      { id: `generated-left-${caseIndex}`, statement: `方程式 $${leftVariable}^2-${leftConstant}=0$ の根を考える。` },
      { id: `generated-right-${caseIndex}`, statement: `方程式 $${rightVariable}^2-${rightConstant}=0$ の根を考える。` },
    ]
    const card = synthesizePolynomialRootFusions(parents, 1, caseIndex + 1)[0]
    assert.ok(card, `case ${caseIndex} must produce one independently verified construction`)
    assert.equal(card.verification.exact_backend, true)
    assert.equal(card.verification.independent_check, true)
    assert.equal(card.fusion_derivation.ablationPassed, true)
    answers.add(card.answer_tex)
  }
  assert.equal(answers.size, 4)
})
