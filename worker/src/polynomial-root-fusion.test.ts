import assert from 'node:assert/strict'
import test from 'node:test'
import {
  executePolynomialPairMap,
  executePolynomialRootInvariant,
  executeRationalMapOnRoots,
  extractPolynomial,
  extractRationalMap,
  polynomialPairMapBasis,
  supportsPolynomialRootFusion,
  synthesizePolynomialPairMapFusions,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'
import { auditPublicationContent } from './publication-content-audit'

const parents = [
  { id: 'left', statement: '方程式 $x^2-2=0$ の根について考える。' },
  { id: 'right', statement: '方程式 $y^2-3=0$ の根について考える。' },
]

test('constructs a new root-set problem by exact elimination', () => {
  const cards = synthesizePolynomialRootFusions(parents, 3, 1)
  assert.equal(cards.length, 3)
  assert.match(cards[0].answer_tex.replace(/\s/g, ''), /z\^\{4\}-10z\^\{2\}\+1/)
  assert.ok(cards.every(card => card.verification.exact_backend))
  assert.ok(cards.every(card => card.verification.independent_check))
  assert.ok(cards.every(card => card.fusion_derivation.ablationPassed))
  assert.ok(cards.every(card => card.parent_ids.join(',') === 'left,right'))
  assert.ok(cards.every(card => card.execution_certificate?.capability_origin === 'synthesized_proof_program'))
  assert.ok(cards.every(card => card.execution_certificate?.registered_composite_used === false))
  assert.ok(cards.every(card => card.statement_tex.includes('\\(f(x)=')))
  assert.ok(cards.every(card => card.solution_tex.includes('\\operatorname{Res}')))
  assert.ok(cards.every(card => (card.diagram as { kind?: string })?.kind === 'morphism'))
  assert.ok(cards.every(card => Array.isArray(card.proof_roadmap)))
  assert.ok(cards.every(card => card.proof_roadmap?.every(step => typeof step === 'object' && Boolean(step.label_ja))))
  assert.ok(cards.every(card => !(card.diagram as { nodes?: string[] }).nodes?.some(node => node.includes('\\\\'))))
  assert.ok(cards.every(card => card.proof_obligations?.every(obligation => /[\u3040-\u30ff\u3400-\u9fff]/.test(obligation.claim_ja))))
})

test('renaming variables keeps the same morphism certificate', () => {
  const renamed = [
    { id: 'a', statement: '方程式 $u^2-2=0$ の根について考える。' },
    { id: 'b', statement: '方程式 $v^2-3=0$ の根について考える。' },
  ]
  const original = synthesizePolynomialRootFusions(parents, 1, 1)[0]
  const transformed = synthesizePolynomialRootFusions(renamed, 1, 1)[0]
  assert.ok(original)
  assert.ok(transformed)
  assert.equal(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('coefficient changes are computed instead of returning a memorized answer', () => {
  const changed = [
    { id: 'left', statement: '方程式 $x^2-5=0$ の根について考える。' },
    { id: 'right', statement: '方程式 $y^2-7=0$ の根について考える。' },
  ]
  const original = synthesizePolynomialRootFusions(parents, 1, 1)[0]
  const transformed = synthesizePolynomialRootFusions(changed, 1, 1)[0]
  assert.ok(original)
  assert.ok(transformed)
  assert.notEqual(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('abstains unless two distinct parents provide executable polynomial inputs', () => {
  const unsupported = [
    { id: 'left', statement: '方程式 $x^2-2=0$ の根について考える。' },
    { id: 'right', statement: '関数 $f(x)$ の積分を求めよ。' },
  ]
  assert.equal(supportsPolynomialRootFusion(unsupported).applicable, false)
  assert.deepEqual(synthesizePolynomialRootFusions(unsupported, 1), [])
})

test('applies one generic bivariate polynomial-map proof program to several maps', () => {
  const cards = synthesizePolynomialPairMapFusions(parents, 4, 1)

  assert.equal(cards.length, 4)
  assert.equal(new Set(cards.map(card => card.answer_tex)).size, 4)
  assert.ok(cards.every(card => card.family_id === 'runtime.polynomial_pair_map'))
  assert.ok(cards.every(card => card.statement_tex.includes('H(u,v)=')))
  assert.ok(cards.every(card => !/H\(u,v\)=[^)]*\b[xy]\b/.test(card.statement_tex)))
  assert.ok(cards.every(card => card.solution_tex.includes('\\operatorname{Res}_x')))
  assert.ok(cards.every(card => card.solution_tex.includes('\\operatorname{Res}_y')))
  assert.ok(cards.every(card => card.solution_tex.includes('R(z)=')))
  assert.ok(cards.every(card => card.solution_tex.includes('\\gcd(R(z),R\'(z))=')))
  assert.ok(cards.every(card => card.verification.exact_backend && card.verification.independent_check))
  assert.ok(cards.every(card => card.fusion_derivation.ablationPassed))
  assert.ok(cards.every(card => auditPublicationContent(card).passed))
  assert.equal(new Set(cards.map(card => card.structure_blueprint.kernel)).size, 1)
  assert.equal(new Set(cards.map(card => JSON.stringify(card.structure_blueprint.taskAlgebra))).size, 1)
})

test('recomputes a generic pair map after either parent polynomial changes', () => {
  const left = extractPolynomial(parents[0], 0)
  const right = extractPolynomial(parents[1], 1)
  const changedLeft = extractPolynomial({
    id: 'left',
    statement: '方程式 $x^2-5=0$ の根について考える。',
  }, 0)
  const map = polynomialPairMapBasis()[1]

  assert.ok(left)
  assert.ok(right)
  assert.ok(changedLeft)
  const original = executePolynomialPairMap(left, right, map)
  const changed = executePolynomialPairMap(changedLeft, right, map)
  assert.ok(original)
  assert.ok(changed)
  assert.notEqual(changed.result_sympy, original.result_sympy)
  assert.equal(original.numeric_check, true)
  assert.equal(changed.numeric_check, true)
  assert.ok(original.elimination_result.length > 0)
  assert.ok(original.elimination_gcd.length > 0)
})

test('computes trace and norm from arbitrary exact polynomial coefficients', () => {
  const input = extractPolynomial({
    id: 'generic-polynomial',
    statement: '方程式 $2x^2+3x+5=0$ の根を考える。',
  }, 0)
  assert.ok(input)
  const trace = executePolynomialRootInvariant(input, 'trace')
  const norm = executePolynomialRootInvariant(input, 'norm')

  assert.equal(trace?.value_sympy, '-3/2')
  assert.equal(norm?.value_sympy, '5/2')
  assert.equal(trace?.numeric_check, true)
  assert.equal(norm?.numeric_check, true)
})

test('maps an arbitrary algebraic orbit through a fractional-linear transformation', () => {
  const map = extractRationalMap({
    id: 'map',
    statement: '一次分数変換 \\(T(z)=\\frac{2z+1}{z+1}\\) を考える。',
  }, 0)
  const orbit = extractPolynomial({
    id: 'orbit',
    statement: '\\(z^7=1\\) のすべての根を考える。',
  }, 1)
  assert.ok(map)
  assert.ok(orbit)

  const result = executeRationalMapOnRoots(map, orbit)
  assert.equal(result?.degree_result, 7)
  assert.equal(result?.determinant_sympy, '1')
  assert.equal(result?.numeric_check, true)
  assert.match(result?.result_sympy ?? '', /z\*\*7 - 21\*z\*\*6\/2/)
})

test('selects the designated minimal polynomial instead of an incidental root definition', () => {
  const input = extractPolynomial({
    id: 'minimal-polynomial',
    statement: String.raw`\(\alpha=\cos\frac{2\pi}{11}\) を根に持つ最小多項式は
      \(f(x)=32x^5+16x^4-32x^3-12x^2+6x+1\) である。`,
  }, 0)
  assert.ok(input)
  assert.equal(input.elaborator, 'mathjson-ir')
  assert.match(input.normalized, /32/)
  assert.match(input.normalized, /x/)
  assert.doesNotMatch(input.normalized, /alpha|\bf\b/)
  assert.equal(executePolynomialRootInvariant(input, 'trace')?.degree, 5)
})

test('does not reinterpret incidental assignments and curve equations as root sets', () => {
  const statements = [
    String.raw`正の整数 m を並べ、双曲線 \(x^2-3y^2=1\) の弧の面積を \(S_k\) とする。\(S_k\) を求めよ。`,
    String.raw`曲線 \(y=f_n(x)\) と直線 \(y=\frac12\) で囲まれる立体の体積を求めよ。`,
    String.raw`曲線 \(C_c:y=x^3-cx\) を考える。\(c=3\) のときの接点を求めよ。`,
  ]
  for (const [index, statement] of statements.entries()) {
    assert.equal(extractPolynomial({ id: `incidental-${index}`, statement }, index), null)
  }
})

test('rejects an ambiguous multivariate equation even when roots are mentioned', () => {
  assert.equal(extractPolynomial({
    id: 'ambiguous',
    statement: String.raw`方程式 \(x^2+y^2=1\) の根を考える。`,
  }, 0), null)
})

test('fuses bare Unicode Greek polynomial constraints without a registered route', () => {
  const unicodeParents = [
    { id: 'alpha-parent', statement: '実数 α は α^2-3α-7=0 を満たす。' },
    { id: 'beta-parent', statement: '実数 β は β^3+2β-5=0 を満たす。' },
  ]
  const support = supportsPolynomialRootFusion(unicodeParents)
  const cards = synthesizePolynomialRootFusions(unicodeParents, 3, 1)

  assert.equal(support.applicable, true)
  assert.equal(support.inputs.length, 2)
  assert.ok(support.inputs.every(input => input.elaborator === 'mathjson-ir'))
  assert.equal(cards.length, 3)
  assert.ok(cards.every(card => card.execution_certificate?.registered_composite_used === false))
  assert.ok(cards.every(card => card.verification.exact_backend === true))
  assert.ok(cards.every(card => card.fusion_derivation.ablationPassed === true))
})

test('recomputes a Unicode Greek fusion after a coefficient mutation', () => {
  const original = synthesizePolynomialRootFusions([
    { id: 'alpha-parent', statement: '実数 α は α^2-3α-7=0 を満たす。' },
    { id: 'beta-parent', statement: '実数 β は β^3+2β-5=0 を満たす。' },
  ], 1, 1)[0]
  const mutated = synthesizePolynomialRootFusions([
    { id: 'alpha-parent', statement: '実数 α は α^2-5α-7=0 を満たす。' },
    { id: 'beta-parent', statement: '実数 β は β^3+2β-11=0 を満たす。' },
  ], 1, 1)[0]

  assert.ok(original)
  assert.ok(mutated)
  assert.notEqual(mutated.answer_tex, original.answer_tex)
  assert.deepEqual(mutated.morphism_chain, original.morphism_chain)
})
