import assert from 'node:assert/strict'
import test from 'node:test'

import {
  auditCompositionComplexity,
  compositionGenomeFingerprint,
  compositionGenomeMetrics,
} from '../../lib/mortra/composition-genome'
import { problemStructureFingerprints } from '../../lib/mortra/problem-structure-normal-form'
import { hasCompleteParentProof } from './autonomous-synthesis'
import { auditEntranceExamPublication } from './entrance-exam-publication-audit'
import { capabilityOrigin } from './execution-certificate'
import {
  supportsBranchingMomentGeneration,
  analyzeMirrorForbiddenWordCoordinateGrammar,
  characteristicPolynomial,
  discoverMirrorForbiddenWordCoordinateGrammars,
  noRepeatedRightCoordinateTransferMatrix,
  symmetricMomentTransferMatrix,
  synthesizeRuntimeBranchingMomentProblems,
} from './runtime-branching-moment-generation'

const parent = [{
  id: 'integer-shears',
  statement: String.raw`整数の組に対する写像 \(L(a,b)=(a+b,b)\), \(R(a,b)=(a,a+b)\) を考える。`,
}]

const splitParents = [
  {
    id: 'left-integer-shear',
    statement: String.raw`整数の組に対する写像 \(L(x,y)=(x+y,y)\) を考える。`,
  },
  {
    id: 'right-integer-shear',
    statement: String.raw`整数の組に対する写像 \(R(u,v)=(u,u+v)\) を考える。`,
  },
]

function assertRenderableVisualExplanation(
  card: ReturnType<typeof synthesizeRuntimeBranchingMomentProblems>['cards'][number],
) {
  const visual = card.visual_explanation as {
    steps?: Array<{
      morphism?: { label_ja?: string }
      source_state?: { id?: string }
      target_state?: { id?: string }
      diagram?: { version?: number; kind?: string }
    }>
  }
  assert.ok(visual.steps?.length)
  for (const step of visual.steps) {
    assert.ok(step.morphism?.label_ja)
    assert.ok(step.source_state?.id)
    assert.ok(step.target_state?.id)
    assert.equal(step.diagram?.version, 1)
    assert.match(step.diagram?.kind ?? '', /^(plane|morphism|state|variation|calculus)$/)
  }
}

test('derives the fourth-moment transfer matrix from the two child maps', () => {
  assert.deepEqual(symmetricMomentTransferMatrix(4), [
    [3n, 8n, 12n],
    [2n, 5n, 6n],
    [1n, 2n, 2n],
  ])
})

test('derives the finite-state transfer instead of storing its characteristic roots', () => {
  const matrix = noRepeatedRightCoordinateTransferMatrix()
  assert.deepEqual(matrix, [
    [1n, 1n, 1n, 1n],
    [0n, 1n, 0n, 1n],
    [1n, 0n, 0n, 0n],
    [1n, 1n, 0n, 0n],
  ])
  assert.deepEqual(characteristicPolynomial(matrix), [1n, -2n, -2n, 2n, 1n])
})

test('generates a certified one-to-many problem with a deep composition witness', () => {
  const result = synthesizeRuntimeBranchingMomentProblems(parent, 1)
  assert.equal(result.applicable, true, result.reason)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.match(card.statement_tex, /\\mathcal S_n/)
  assert.match(card.answer_tex, /11\+\\sqrt\{113\}/)
  assert.match(card.solution_tex, /4C_n-A_n=2\(-1\)\^n/)
  assert.match(card.solution_tex, /A_\{n\+2\}=11A_\{n\+1\}-2A_n-12\(-1\)\^n/)
  assert.match(card.solution_tex, /X_\{n\+2\}=11X_\{n\+1\}-2X_n/)
  assert.equal(card.verification.samples.slice(0, 5).join(','), '2,34,358,3882,41974')
  assert.equal(hasCompleteParentProof(card, parent), true)
  assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  assert.equal(problemStructureFingerprints(card).normalForm.task.algebraOrigin, 'emitted')
  const genome = card.structure_blueprint.compositionGenome
  assert.ok(genome)
  const metrics = compositionGenomeMetrics(genome)
  assert.equal(metrics.repeatIndependentOperationCount, 897)
  assert.equal(metrics.structuralQuotientNodeCount, 897)
  assert.equal(metrics.distinctCompositionContextCount, 1_024)
  assert.equal(metrics.structuralAlphabet.length, 5)
  assert.equal(metrics.branchCount, 255)
  assert.equal(metrics.mergeCount, 255)
  assert.equal(metrics.rootToOutputPathCount, 384)
  assert.equal(metrics.coreAlphabet.length, 5)
  assert.equal(auditCompositionComplexity(genome).passed, true)
  assert.match(compositionGenomeFingerprint(genome), /^[0-9a-f]{64}$/)
  const publication = auditEntranceExamPublication(card)
  assert.equal(publication.passed, true, publication.errors.join('; '))
  const visual = card.visual_explanation as { steps?: unknown[] }
  assert.equal(visual.steps?.length, card.solution_tex.split(/\n\s*\n/).length)
  assertRenderableVisualExplanation(card)
})

test('renaming the pair variables preserves the generated structure', () => {
  const renamed = [{
    id: 'renamed-integer-shears',
    statement: String.raw`写像 \(L(x,y)=(x+y,y)\), \(R(x,y)=(x,x+y)\) を考える。`,
  }]
  const original = synthesizeRuntimeBranchingMomentProblems(parent, 1).cards[0]
  const transformed = synthesizeRuntimeBranchingMomentProblems(renamed, 1).cards[0]
  assert.ok(original)
  assert.ok(transformed)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
  assert.equal(
    compositionGenomeFingerprint(transformed.structure_blueprint.compositionGenome!),
    compositionGenomeFingerprint(original.structure_blueprint.compositionGenome!),
  )
  assert.equal(transformed.answer_tex, original.answer_tex)
})

test('combines complementary shear maps from two indispensable parents', () => {
  const support = supportsBranchingMomentGeneration(splitParents)
  assert.equal(support.applicable, true, support.reason)
  assert.deepEqual(support.parentIds, ['left-integer-shear', 'right-integer-shear'])
  assert.deepEqual(support.mapAssignments?.map(item => [item.parentId, item.symbol]), [
    ['left-integer-shear', 'L'],
    ['right-integer-shear', 'R'],
  ])

  const result = synthesizeRuntimeBranchingMomentProblems(splitParents, 2)
  assert.equal(result.applicable, true, result.reason)
  assert.equal(result.cards.length, 2)
  for (const card of result.cards) {
    assert.deepEqual(card.parent_ids, ['left-integer-shear', 'right-integer-shear'])
    assert.deepEqual(
      card.fusion_derivation.assignments.map(item => item.parentId),
      ['left-integer-shear', 'right-integer-shear'],
    )
    assert.deepEqual(
      card.fusion_derivation.bridges[0].consumes,
      ['left-integer-shear-map', 'right-integer-shear-map'],
    )
    assert.equal(card.structure_blueprint.synthesizedLaw?.arity, 2)
    assert.equal(hasCompleteParentProof(card, splitParents), true)
    assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  }
})

test('rejects a two-parent request when either parent is dispensable', () => {
  const redundant = [
    parent[0],
    { id: 'duplicate-left', statement: String.raw`写像 \(L(s,t)=(s+t,t)\) を考える。` },
  ]
  const irrelevant = [
    parent[0],
    { id: 'unrelated', statement: String.raw`数列 \(a_{n+1}=2a_n+1\) を考える。` },
  ]
  assert.equal(supportsBranchingMomentGeneration(redundant).applicable, false)
  assert.equal(supportsBranchingMomentGeneration(irrelevant).applicable, false)
  assert.equal(synthesizeRuntimeBranchingMomentProblems(redundant, 1).cards.length, 0)
  assert.equal(synthesizeRuntimeBranchingMomentProblems(irrelevant, 1).cards.length, 0)
})

test('generates a second deep species by adding a finite-state branch restriction', () => {
  const result = synthesizeRuntimeBranchingMomentProblems(parent, 2)
  assert.equal(result.cards.length, 2)
  const second = result.cards[1]
  assert.equal(second.family_id, 'runtime.no_repeated_right_coordinate_sum_limit')
  assert.match(second.statement_tex, /R.*二つ続けて現れない/s)
  assert.match(second.answer_tex, /1\+\\sqrt2/)
  assert.equal(second.verification.samples.slice(0, 8).join(','), '6,14,35,84,204,492,1189,2870')
  const genome = second.structure_blueprint.compositionGenome
  assert.ok(genome)
  const metrics = compositionGenomeMetrics(genome)
  assert.equal(metrics.repeatIndependentOperationCount, 1_327)
  assert.equal(metrics.structuralQuotientNodeCount, 1_327)
  assert.equal(metrics.distinctCompositionContextCount, 97)
  assert.equal(metrics.structuralAlphabet.length, 5)
  assert.equal(metrics.branchCount, 287)
  assert.equal(metrics.mergeCount, 287)
  assert.equal(metrics.rootToOutputPathCount, 288)
  assert.equal(metrics.distinctLawTransitionCount, 8)
  assert.equal(auditCompositionComplexity(genome).passed, true)
  assert.equal(hasCompleteParentProof(second, parent), true)
  const publication = auditEntranceExamPublication(second)
  assert.equal(publication.passed, true, publication.errors.join('; '))
  const visual = second.visual_explanation as { steps?: unknown[] }
  assert.equal(visual.steps?.length, second.solution_tex.split(/\n\s*\n/).length)
  assertRenderableVisualExplanation(second)
})

test('discovers solvable mirror-symmetric grammars instead of storing their answers', () => {
  const discovery = discoverMirrorForbiddenWordCoordinateGrammars(3)
  assert.equal(discovery.hypothesesEvaluated, 4)
  assert.deepEqual(
    discovery.analyses.map(analysis => analysis.forbiddenWords),
    [['LLL', 'RRR'], ['LRL', 'RLR']],
  )
  assert.deepEqual(
    discovery.rejected.map(item => item.forbiddenWords),
    [['LLR', 'RRL'], ['LRR', 'RLL']],
  )
  for (const analysis of discovery.analyses) {
    assert.deepEqual(analysis.samples, analysis.independentlyEnumeratedSamples)
    assert.equal(analysis.dominantRoot.degree, 3)
    assert.match(analysis.dominantRoot.exactTex, /\\sqrt\[3\]/)
    assert.doesNotMatch(analysis.dominantRoot.exactTex, /(^|[^\\])sqrt/)
  }
})

test('publishes two distinct generated grammars with exact proofs and diagrams', () => {
  const result = synthesizeRuntimeBranchingMomentProblems(parent, 4)
  assert.equal(result.cards.length, 4)
  assert.equal(result.hypothesesEvaluated, 6)
  const generated = result.cards.slice(2)
  assert.deepEqual(
    generated.map(card => card.family_id),
    [
      'runtime.mirror_forbidden_word_coordinate_sum_limit',
      'runtime.mirror_forbidden_word_coordinate_sum_limit',
    ],
  )
  assert.notEqual(generated[0].statement_tex, generated[1].statement_tex)
  assert.notEqual(generated[0].answer_tex, generated[1].answer_tex)
  assert.match(generated[0].statement_tex, /LLL.*RRR/s)
  assert.match(generated[1].statement_tex, /LRL.*RLR/s)
  assert.match(generated[0].solution_tex, /A_n=\\begin\{pmatrix\}2&2&2&2\\end\{pmatrix\}/)
  assert.match(generated[0].solution_tex, /X_n=3A_n-2\(-1\)\^n/)
  assert.match(generated[1].solution_tex, /X_n=7A_n-8\(-1\)\^n/)
  assert.doesNotMatch(generated[0].solution_tex, /(^|[^\\])left\(/)
  assert.doesNotMatch(generated[0].solution_tex, /A_n=2&2/)

  const fingerprints = generated.map(card =>
    compositionGenomeFingerprint(card.structure_blueprint.compositionGenome!))
  assert.equal(new Set(fingerprints).size, 2)
  for (const card of generated) {
    assert.equal(hasCompleteParentProof(card, parent), true)
    assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
    assert.equal(auditCompositionComplexity(card.structure_blueprint.compositionGenome!).passed, true)
    const publication = auditEntranceExamPublication(card)
    assert.equal(publication.passed, true, publication.errors.join('; '))
    const visual = card.visual_explanation as { steps?: unknown[] }
    assert.equal(visual.steps?.length, 6)
    assert.equal(visual.steps?.length, card.solution_tex.split(/\n\s*\n/).length)
    assertRenderableVisualExplanation(card)
  }
})

test('the generated analysis is invariant under exchanging the generator names', () => {
  const direct = analyzeMirrorForbiddenWordCoordinateGrammar(['LLL', 'RRR'])
  const exchanged = analyzeMirrorForbiddenWordCoordinateGrammar(['RRR', 'LLL'])
  assert.deepEqual(exchanged.quotientMatrix, direct.quotientMatrix)
  assert.deepEqual(exchanged.samples, direct.samples)
  assert.equal(exchanged.dominantRoot.exactTex, direct.dominantRoot.exactTex)
})

test('rejects a different child map instead of reusing the completed answer', () => {
  const altered = [{
    id: 'altered-shears',
    statement: String.raw`写像 \(L(a,b)=(a+b,b)\), \(R(a,b)=(a,a+2b)\) を考える。`,
  }]
  assert.equal(supportsBranchingMomentGeneration(altered).applicable, false)
  assert.equal(synthesizeRuntimeBranchingMomentProblems(altered, 1).cards.length, 0)
  assert.equal(synthesizeRuntimeBranchingMomentProblems([], 1).cards.length, 0)
})
