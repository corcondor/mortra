import assert from 'node:assert/strict'
import test from 'node:test'

import { generalizeParents } from './generalization-kernel'
import {
  enumerateTypedTerms,
  semanticQueryTerminalMorphisms,
  type TypedProgramNode,
  type TypedTerm,
} from './typed-term-enumerator'
import { executeTypedPrograms, inspectTypedProgramExecution } from './typed-program-executor'

const parents = [
  { id: 'left', statement: '方程式 $x^2-2=0$ の根について考える。' },
  { id: 'right', statement: '方程式 $y^2-3=0$ の根について考える。' },
]

test('executes a cold enumerated AST instead of dispatching by problem family', () => {
  const generalized = generalizeParents(parents, 6, 10_000)
  const enumeration = enumerateTypedTerms(generalized.graphs, { maxDepth: 6, maxStates: 10_000 })
  const result = executeTypedPrograms(parents, enumeration.goals, 3)

  assert.equal(result.cards.length, 3)
  assert.match(result.cards[0].answer_tex.replace(/\s/g, ''), /z\^\{4\}-10z\^\{2\}\+1/)
  assert.ok(result.cards.every(card => card.family_id === 'runtime.typed_program'))
  assert.ok(result.cards.every(card => card.execution_certificate?.capability_origin === 'synthesized_proof_program'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
  assert.ok(result.cards.every(card => card.structure_blueprint.kernel === 'runtime_typed_program_interpreter'))
  assert.ok(result.cards.every(card => {
    const generated = card.execution_certificate?.generated_program as Record<string, unknown> | undefined
    return generated?.schema === 'mortra.typed-program.v1' && typeof generated.ast === 'object'
  }))
})

test('recomputes the generated program when coefficients change', () => {
  const changed = [
    { id: 'left', statement: '方程式 $x^2-5=0$ の根について考える。' },
    { id: 'right', statement: '方程式 $y^2-7=0$ の根について考える。' },
  ]
  const originalEnumeration = enumerateTypedTerms(generalizeParents(parents, 6, 10_000).graphs)
  const changedEnumeration = enumerateTypedTerms(generalizeParents(changed, 6, 10_000).graphs)
  const original = executeTypedPrograms(parents, originalEnumeration.goals, 1).cards[0]
  const transformed = executeTypedPrograms(changed, changedEnumeration.goals, 1).cards[0]

  assert.ok(original)
  assert.ok(transformed)
  assert.notEqual(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

function root(parentId: string): TypedProgramNode {
  return {
    kind: 'apply',
    morphism: 'RootExtraction',
    sources: ['Polynomial'],
    target: 'FiniteAlgebraicOrbit',
    backend: ['polynomial-solver'],
    preserves: ['multiplicity'],
    args: [{ kind: 'parent', parentId, sort: 'Polynomial' }],
  }
}

function sum(left: TypedProgramNode, right: TypedProgramNode): TypedProgramNode {
  return {
    kind: 'apply',
    morphism: 'RootMinkowskiSum',
    sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
    target: 'FiniteAlgebraicOrbit',
    backend: ['resultant', 'square-free-reduction'],
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support'],
    args: [left, right],
  }
}

function invariant(
  morphism: 'FieldTrace' | 'FieldNorm',
  argument: TypedProgramNode,
): TypedProgramNode {
  return {
    kind: 'apply',
    morphism,
    sources: ['FiniteAlgebraicOrbit'],
    target: 'Scalar',
    backend: ['vieta'],
    preserves: ['Galois-orbit'],
    args: [argument],
  }
}

test('executes one generated tree over three parents and ablates every parent', () => {
  const threeParents = [
    { id: 'p2', statement: '方程式 $x^2-2=0$ の根を考える。' },
    { id: 'p3', statement: '方程式 $y^2-3=0$ の根を考える。' },
    { id: 'p5', statement: '方程式 $z^2-5=0$ の根を考える。' },
  ]
  const program = sum(sum(root('p2'), root('p3')), root('p5'))
  const goal: TypedTerm = {
    id: 'three-parent-runtime-program',
    sort: 'FiniteAlgebraicOrbit',
    expression: 'runtime-three-parent-sum',
    parentMask: 7,
    parentIds: ['p2', 'p3', 'p5'],
    depth: 3,
    steps: [],
    constraints: [],
    program,
  }
  const result = executeTypedPrograms(threeParents, [goal], 1)

  assert.equal(result.cards.length, 1)
  assert.deepEqual(result.cards[0].parent_ids, ['p2', 'p3', 'p5'])
  assert.equal(result.cards[0].fusion_derivation.assignments.length, 3)
  const generated = result.cards[0].execution_certificate?.generated_program as {
    parent_ablation_outputs?: Record<string, string>
  }
  assert.deepEqual(Object.keys(generated.parent_ablation_outputs ?? {}).sort(), ['p2', 'p3', 'p5'])
})

test('executes a runtime-composed field trace and keeps both parents causal', () => {
  const asymmetricParents = [
    { id: 'left', statement: '方程式 $x^2+x-1=0$ の根を考える。' },
    { id: 'right', statement: '方程式 $y^2-y-1=0$ の根を考える。' },
  ]
  const program = invariant('FieldTrace', sum(root('left'), root('right')))
  const goal: TypedTerm = {
    id: 'runtime-field-trace',
    sort: 'Scalar',
    expression: 'runtime-field-trace',
    parentMask: 3,
    parentIds: ['left', 'right'],
    depth: 3,
    steps: [],
    constraints: [],
    program,
  }
  const result = executeTypedPrograms(asymmetricParents, [goal], 1)

  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '0')
  assert.match(result.cards[0].statement_tex, /sum/)
  assert.deepEqual(result.cards[0].parent_ids, ['left', 'right'])
  const generated = result.cards[0].execution_certificate?.generated_program as {
    parent_ablation_outputs?: Record<string, string>
    exact_trace?: Array<{ kind?: string }>
  }
  assert.deepEqual(Object.keys(generated.parent_ablation_outputs ?? {}).sort(), ['left', 'right'])
  assert.ok(generated.exact_trace?.some(step => step.kind === 'root-invariant'))
})

test('synthesizes a map-orbit summation without a registered composite route', () => {
  const mapOrbitParents = [
    { id: 'map-parent', statement: '一次分数変換 \\(T(z)=\\frac{2z+1}{z+1}\\) を反復する。' },
    { id: 'orbit-parent', statement: '\\(z^7=1\\) のすべての根を考える。' },
  ]
  const generalized = generalizeParents(mapOrbitParents, 6, 10_000)
  const enumeration = enumerateTypedTerms(generalized.graphs, { maxDepth: 6, maxStates: 10_000 })
  const result = executeTypedPrograms(mapOrbitParents, enumeration.goals, 1)

  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '\\frac{21}{2}')
  assert.ok(result.cards[0].morphism_chain.includes('MapOrbitEvaluation'))
  assert.ok(result.cards[0].morphism_chain.includes('FiniteSummation'))
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  const generated = result.cards[0].execution_certificate?.generated_program as {
    parent_ablation_outputs?: Record<string, string>
    exact_trace?: Array<{ kind?: string }>
  }
  assert.deepEqual(Object.keys(generated.parent_ablation_outputs ?? {}).sort(), ['map-parent', 'orbit-parent'])
  assert.ok(generated.exact_trace?.some(step => step.kind === 'rational-map-orbit'))
  assert.ok(generated.exact_trace?.some(step => step.kind === 'root-invariant'))
})

test('composes a fresh symbolic power orbit from current coefficients and renamings', () => {
  const symbolicParents = [
    { id: 'fresh-map', statement: '一次分数変換 \\(S(w)=\\frac{5w-1}{2w+3}\\) を考える。' },
    { id: 'fresh-orbit', statement: '\\(w_1,\\ldots,w_m\\) を \\(w^m=2\\) のすべての解とする。' },
  ]
  const generalized = generalizeParents(symbolicParents, 6, 10_000)
  const enumeration = enumerateTypedTerms(generalized.graphs, { maxDepth: 6, maxStates: 10_000 })
  const result = executeTypedPrograms(symbolicParents, enumeration.goals, 1)

  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.equal(card.execution_certificate?.capability_origin, 'synthesized_proof_program')
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.deepEqual(card.morphism_chain, ['MobiusMap', 'RootsOfUnity', 'MapOrbitEvaluation', 'FiniteSummation'])
  assert.match(card.answer_tex, /m/)
  assert.match(card.answer_tex, /2/)
  assert.match(card.solution_tex, /対数微分/)
  const generated = card.execution_certificate?.generated_program as {
    parent_ablation_outputs?: Record<string, string>
    exact_trace?: Array<{ kind?: string; numeric_samples?: number[] }>
  }
  assert.deepEqual(Object.keys(generated.parent_ablation_outputs ?? {}).sort(), ['fresh-map', 'fresh-orbit'])
  assert.ok(generated.exact_trace?.some(step => step.kind === 'symbolic-power-orbit'))
  const sumTrace = generated.exact_trace?.find(step => step.kind === 'power-orbit-summation')
  assert.ok(sumTrace)
  assert.ok((sumTrace.numeric_samples?.length ?? 0) >= 3)
})

test('reports an explicit obligation when a primitive handler is missing', () => {
  const unsupported: TypedProgramNode = {
    kind: 'apply',
    morphism: 'UnknownGeometricConstruction',
    sources: ['Polynomial'],
    target: 'Proof',
    backend: ['unknown'],
    preserves: [],
    args: [{ kind: 'parent', parentId: 'left', sort: 'Polynomial' }],
  }
  const support = inspectTypedProgramExecution(unsupported)
  assert.equal(support.executable, false)
  assert.deepEqual(support.unsupported, ['missing primitive handler UnknownGeometricConstruction'])
})

test('executes a query-directed bound expression through the typed runtime', () => {
  const expressionParents = [{
    id: 'typed-fresh-limit',
    statement: String.raw`\[\lim_{r\to\infty}\frac{\sum_{j=1}^{r}j}{r^2}\]を求めよ。`,
  }]
  const generalized = generalizeParents(expressionParents, 4, 5_000)
  const enumeration = enumerateTypedTerms(generalized.graphs, {
    maxDepth: 4,
    maxStates: 5_000,
    goalSorts: ['Scalar'],
  })
  const expressionGoal = enumeration.goals.find(goal =>
    goal.program.kind === 'apply' && goal.program.morphism === 'EvaluateExpression')
  assert.ok(expressionGoal)
  assert.equal(inspectTypedProgramExecution(expressionGoal.program).executable, true)

  const result = executeTypedPrograms(expressionParents, [expressionGoal], 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, String.raw`\(\frac{1}{2}\)`)
  assert.equal(result.cards[0].family_id, 'runtime.typed_expression_program')
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_expression_program')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
})

test('executes a query-directed constraint program synthesized from the current statement', () => {
  const parents = [{
    id: 'typed-fresh-linear',
    statement: String.raw`方程式 \(7x-5=30\) を解け。`,
  }]
  const generalized = generalizeParents(parents, 3, 1_000)
  const terminals = semanticQueryTerminalMorphisms(generalized.graphs, 'Scalar')
  const enumeration = enumerateTypedTerms(generalized.graphs, {
    maxDepth: 3,
    maxStates: 1_000,
    goalSorts: ['Scalar'],
    terminalMorphismsBySort: { Scalar: terminals },
  })
  const goal = enumeration.goals.find(candidate =>
    candidate.program.kind === 'apply' && candidate.program.morphism === 'SolveConstraintQuery')
  assert.ok(goal)
  assert.equal(inspectTypedProgramExecution(goal.program).executable, true)

  const result = executeTypedPrograms(parents, [goal], 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '5')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  assert.equal(result.cards[0].execution_certificate?.capability_origin, 'synthesized_linear_program')
})
