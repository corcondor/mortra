import assert from 'node:assert/strict'
import test from 'node:test'
import { executableMorphismAtlas } from './generalization-kernel'
import { enumerateTypedTerms } from './typed-term-enumerator'
import type { SemanticHypergraph } from './generalization-kernel'

function graph(id: string, roots: string[], goals: string[]): SemanticHypergraph {
  return {
    parent_id: id,
    nodes: [],
    edges: [],
    root_sorts: roots,
    query_sorts: goals,
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
}

test('promotes probe-verified morphisms into the one executable atlas', () => {
  const names = new Set(executableMorphismAtlas().map(rule => rule.name))
  for (const name of [
    'PrimeValuation',
    'ElementarySymmetricChart',
    'RecurrenceExtraction',
    'ConfigurationDiscretization',
    'PropositionCertification',
  ]) assert.ok(names.has(name), name)
  assert.equal(names.size, executableMorphismAtlas().length)
})

test('the shared atlas reaches held-out goals in four domains without family ids', () => {
  const cases = [
    graph('number', ['Integer', 'PrimeSpectrum'], ['IntegerInvariant']),
    graph('algebra', ['FiniteFamily'], ['Proposition']),
    graph('analysis', ['Sequence'], ['Real']),
    graph('combinatorics', ['GeometricConfiguration'], ['Integer']),
  ]
  for (const item of cases) {
    const result = enumerateTypedTerms([item], { maxDepth: 6, maxStates: 20_000, goalSorts: item.query_sorts })
    assert.ok(result.goals.length > 0, item.parent_id)
  }
})
