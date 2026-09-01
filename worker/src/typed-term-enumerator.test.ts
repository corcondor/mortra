import assert from 'node:assert/strict'
import test from 'node:test'
import { buildSemanticHypergraph, generalizeParents, type SemanticHypergraph } from './generalization-kernel'
import { enumerateTypedTerms, semanticQueryTerminalMorphisms } from './typed-term-enumerator'

test('enumerates a full-provenance term by type, not by a remembered family id', () => {
  const parents = [
    { id: 'map-parent', statement: '一次分数変換 \\(T(z)=\\frac{2z+1}{z+1}\\) を反復する。' },
    { id: 'orbit-parent', statement: '\\(z^n=1\\) のすべての根を考える。' },
  ]
  const generalized = generalizeParents(parents, 6, 10_000)
  const result = enumerateTypedTerms(generalized.graphs, { maxDepth: 6, maxStates: 10_000 })
  const goal = result.goals.find(term => term.sort === 'Scalar')
  assert.ok(goal)
  assert.deepEqual(goal.parentIds, ['map-parent', 'orbit-parent'])
  assert.ok(goal.steps.some(step => step.morphism === 'MapOrbitEvaluation'))
  assert.ok(goal.steps.every(step => step.backend.length > 0))
  assert.equal(goal.program.kind, 'apply')
  assert.equal(goal.program.kind === 'apply' && goal.program.morphism, 'FiniteSummation')
})

test('does not manufacture a full-provenance goal when no typed bridge exists', () => {
  const parents = [
    { id: 'prime-parent', statement: '素数 p に対して命題を示せ。' },
    { id: 'curve-parent', statement: '曲線 C の接線を求めよ。' },
  ]
  const generalized = generalizeParents(parents, 5, 2_000)
  const result = enumerateTypedTerms(generalized.graphs, { maxDepth: 5, maxStates: 2_000 })
  assert.equal(result.goals.length, 0)
  assert.ok(result.terms.every(term => term.parentIds.length === 1))
  assert.ok(result.terms.every(term => term.program.kind === 'parent' || term.program.args.length > 0))
})

test('does not certify a given assumption as the requested proof', () => {
  const graph = buildSemanticHypergraph({
    id: 'non-vacuous-proof',
    statement: '整数 n に対し、n>0 ならば n^2>0 を示せ。',
  })
  const result = enumerateTypedTerms([graph], {
    maxDepth: 4,
    maxStates: 2_000,
    goalSorts: ['Proof'],
  })
  assert.equal(result.goals.length, 0)
  assert.equal(result.terms.filter(term => term.sort === 'Proof').length, 0)
  assert.ok(result.frontier.some(item =>
    item.morphism === 'PropositionCertification' &&
    item.missing.includes('GoalProposition') &&
    item.missing.includes('CertifiedProposition'),
  ))
})

test('retains separate identities for assumptions with the same proposition sort', () => {
  const graph = buildSemanticHypergraph({
    id: 'two-assumptions',
    statement: '実数 x,y に対し x+y=5 とする。x-y=1 とする。',
  })
  const result = enumerateTypedTerms([graph], { maxDepth: 2, maxStates: 500 })
  const assumptions = result.terms.filter(term =>
    term.depth === 0 && term.sort === 'AssumptionProposition')
  assert.equal(assumptions.length, 2)
  assert.equal(new Set(assumptions.map(term => term.id)).size, 2)
  assert.equal(new Set(assumptions.map(term =>
    term.program.kind === 'parent' ? term.program.bindingId : null)).size, 2)
})

test('creates a proof only from an explicit goal and a proof-bearing proposition', () => {
  const graph: SemanticHypergraph = {
    parent_id: 'verified-goal',
    nodes: [],
    edges: [],
    root_sorts: ['GoalProposition', 'CertifiedProposition'],
    query_sorts: ['Proof'],
    root_bindings: [
      {
        id: 'verified-goal:goal',
        role: 'goal',
        canonical: 'Relation[=,v0,v1]',
        sort: 'GoalProposition',
        surface: 'x=y',
        parent_id: 'verified-goal',
        proposition_canonical: 'Relation[=,v0,v1]',
      },
      {
        id: 'verified-goal:certificate',
        role: 'object',
        canonical: 'Certified[Relation[=,v0,v1],sha256:test]',
        sort: 'CertifiedProposition',
        surface: 'certificate for x=y',
        parent_id: 'verified-goal',
        proposition_canonical: 'Relation[=,v0,v1]',
        certificate_hash: 'sha256:test',
      },
    ],
    language_analysis: {
      token_count: 0,
      parse_count: 1,
      parse_truncated: false,
      clause_count: 1,
      quantifier_prefix: [],
      definitions: [],
      declarations: [],
      constraints: [],
      unresolved_references: [],
      diagnostics: [],
    },
  }
  const result = enumerateTypedTerms([graph], {
    maxDepth: 2,
    maxStates: 500,
    goalSorts: ['Proof'],
  })
  const proof = result.goals.find(term => term.sort === 'Proof')
  assert.ok(proof)
  assert.equal(proof.program.kind, 'apply')
  assert.equal(proof.program.kind === 'apply' && proof.program.morphism, 'PropositionCertification')
})

test('rejects a valid certificate for a proposition other than the requested goal', () => {
  const graph: SemanticHypergraph = {
    parent_id: 'mismatched-certificate',
    nodes: [],
    edges: [],
    root_sorts: ['GoalProposition', 'CertifiedProposition'],
    query_sorts: ['Proof'],
    root_bindings: [
      {
        id: 'mismatched-certificate:goal',
        role: 'goal',
        canonical: 'Relation[=,v0,v1]',
        sort: 'GoalProposition',
        surface: 'x=y',
        parent_id: 'mismatched-certificate',
        proposition_canonical: 'Relation[=,v0,v1]',
      },
      {
        id: 'mismatched-certificate:certificate',
        role: 'object',
        canonical: 'Certified[Relation[=,v0,0],sha256:test]',
        sort: 'CertifiedProposition',
        surface: 'certificate for x=0',
        parent_id: 'mismatched-certificate',
        proposition_canonical: 'Relation[=,v0,0]',
        certificate_hash: 'sha256:test',
      },
    ],
    language_analysis: {
      token_count: 0,
      parse_count: 1,
      parse_truncated: false,
      clause_count: 1,
      quantifier_prefix: [],
      definitions: [],
      declarations: [],
      constraints: [],
      unresolved_references: [],
      diagnostics: [],
    },
  }
  const result = enumerateTypedTerms([graph], {
    maxDepth: 2,
    maxStates: 500,
    goalSorts: ['Proof'],
  })
  assert.equal(result.goals.length, 0)
})

test('does not treat an unrelated scalar route as an extremum answer', () => {
  const graph = buildSemanticHypergraph({
    id: 'maximum-triangle-area',
    statement: '三角形 ABC の面積 S の最大値を求めよ。',
  })
  const terminals = semanticQueryTerminalMorphisms([graph], 'Scalar')
  assert.deepEqual(terminals, ['ExtremalObservation', 'Extremum'])

  const unconstrained = enumerateTypedTerms([graph], {
    maxDepth: 4,
    maxStates: 2_000,
    goalSorts: ['Scalar'],
  })
  assert.ok(unconstrained.goals.some(goal =>
    goal.steps.some(step => step.morphism === 'RaviSubstitution')))

  const queryDirected = enumerateTypedTerms([graph], {
    maxDepth: 4,
    maxStates: 2_000,
    goalSorts: ['Scalar'],
    terminalMorphismsBySort: { Scalar: terminals },
  })
  assert.equal(queryDirected.goals.some(goal =>
    goal.steps.some(step => step.morphism === 'RaviSubstitution')), false)
  assert.ok(queryDirected.frontier.some(item =>
    item.morphism === 'Extremum' && item.missing.includes('OrderedFamily')))
})

test('uses the freshly parsed binder AST as the terminal compute operation', () => {
  const graph = buildSemanticHypergraph({
    id: 'renamed-binders',
    statement: String.raw`\[\lim_{s\to\infty}\{\sum_{i=1}^{s}i-s^2\}\]を求めよ。`,
  })
  const terminals = semanticQueryTerminalMorphisms([graph], 'Scalar')
  assert.deepEqual(terminals, ['EvaluateExpression'])
  const result = enumerateTypedTerms([graph], {
    maxDepth: 2,
    maxStates: 500,
    goalSorts: ['Scalar'],
    terminalMorphismsBySort: { Scalar: terminals },
  })
  assert.equal(result.goals.length, 1)
  assert.equal(result.goals[0].program.kind, 'apply')
  assert.equal(result.goals[0].program.kind === 'apply' && result.goals[0].program.morphism, 'EvaluateExpression')
})

test('requires a freshly synthesized constraint program for a generic scalar query', () => {
  const solvable = buildSemanticHypergraph({
    id: 'fresh-linear-query',
    statement: String.raw`方程式 \(7x-5=30\) を解け。`,
  })
  const unresolved = buildSemanticHypergraph({
    id: 'unrelated-scalar-route',
    statement: String.raw`多項式 \(x^2+x+1\) の根を \(a,b\) とする。\(a^3+b\) を求めよ。`,
  })
  assert.deepEqual(semanticQueryTerminalMorphisms([solvable], 'Scalar'), ['SolveConstraintQuery'])
  assert.deepEqual(semanticQueryTerminalMorphisms([unresolved], 'Scalar'), ['SolveConstraintQuery'])

  const solvedTerms = enumerateTypedTerms([solvable], {
    maxDepth: 2,
    maxStates: 500,
    goalSorts: ['Scalar'],
    terminalMorphismsBySort: { Scalar: ['SolveConstraintQuery'] },
  })
  assert.equal(solvedTerms.goals.length, 1)
  assert.equal(
    solvedTerms.goals[0].program.kind === 'apply' && solvedTerms.goals[0].program.morphism,
    'SolveConstraintQuery',
  )

  const unresolvedTerms = enumerateTypedTerms([unresolved], {
    maxDepth: 4,
    maxStates: 2_000,
    goalSorts: ['Scalar'],
    terminalMorphismsBySort: { Scalar: ['SolveConstraintQuery'] },
  })
  assert.equal(unresolvedTerms.goals.length, 0)
  assert.ok(unresolvedTerms.frontier.some(item =>
    item.morphism === 'SolveConstraintQuery' && item.missing.includes('ExecutableConstraintIR')))
})

test('does not accept an unrelated finite set as the answer to a classification query', () => {
  const graph = buildSemanticHypergraph({
    id: 'fresh-classification',
    statement: String.raw`整数 \(x\) で条件 \(x^2<10\) を満たすものをすべて求めよ。`,
  })
  const terminals = semanticQueryTerminalMorphisms([graph], 'FiniteSet')
  assert.deepEqual(terminals, ['EnumerateConstraintSolutions'])
  const enumeration = enumerateTypedTerms([graph], {
    maxDepth: 4,
    maxStates: 2_000,
    goalSorts: ['FiniteSet'],
    terminalMorphismsBySort: { FiniteSet: terminals },
  })
  assert.equal(enumeration.goals.length, 0)
  assert.ok(enumeration.frontier.some(item =>
    item.morphism === 'EnumerateConstraintSolutions' && item.missing.includes('ExecutableConstraintIR')))
})
