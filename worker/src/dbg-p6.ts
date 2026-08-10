import { enumerateTypedTerms } from './typed-term-enumerator.ts'
import { executableMorphismAtlas } from './generalization-kernel.ts'
import type { HyperMorphismSchema, SemanticHypergraph } from './generalization-kernel.ts'

const g: SemanticHypergraph = {
  parent_id: 'P6', nodes: [], edges: [],
  root_sorts: ['Sequence', 'Integer'], query_sorts: ['FiniteSet', 'IntegerPredicate'],
  language_analysis: {
    token_count: 0, parse_count: 1, parse_truncated: false, clause_count: 1,
    quantifier_prefix: [], definitions: [], declarations: [],
    constraints: [], unresolved_references: [], diagnostics: [],
  },
} as never

const A = (name: string, sources: string[], target: string): HyperMorphismSchema =>
  ({ name, sources, target, preserves: [], backend: ['x'] })
const FULL: HyperMorphismSchema[] = [
  A('IntegerPairFormation', ['Integer', 'Integer'], 'IntegerPair'),
  A('PrimeRestriction', ['Integer'], 'PrimeSpectrum'),
  A('IntegerAsArithmeticObject', ['Integer'], 'ArithmeticObject'),
  A('ScalarAsArithmeticObject', ['Scalar'], 'ArithmeticObject'),
  A('IntegerAsReal', ['Integer'], 'Real'),
  A('ScalarAsReal', ['Scalar'], 'Real'),
  A('SequenceIndexing', ['Sequence'], 'FiniteFamily'),
  A('DivisorLattice', ['Integer'], 'FiniteSet'),
  A('PrimeValuation', ['Integer', 'PrimeSpectrum'], 'IntegerInvariant'),
  A('ModularInversion', ['FiniteSet', 'IntegerPair'], 'Integer'),
  A('InvariantAsInteger', ['IntegerInvariant'], 'Integer'),
  A('ResidueOrbitOfSequence', ['Sequence', 'FiniteSet'], 'Orbit'),
  A('ArithmeticPredicateLift', ['ArithmeticObject', 'IntegerPredicate'], 'Proposition'),
  A('PrimeArithmeticPredicateLift', ['ArithmeticObject', 'PrimeSpectrum'], 'Proposition'),
  A('CongruencePredicateLift', ['FiniteSet', 'IntegerPredicate'], 'Proposition'),
  A('CoprimalityProposition', ['GCDValue', 'IntegerPredicate'], 'Proposition'),
  A('PropositionCertification', ['Proposition'], 'Proof'),
]
const ADD = process.env.MIN
  ? [A('ResidueOrbitOfSequence', ['Sequence', 'FiniteSet'], 'Orbit'), A('ScalarAsArithmeticObject', ['Scalar'], 'ArithmeticObject')]
  : FULL
const r = enumerateTypedTerms([g], {
  maxDepth: 8, maxStates: 200_000, goalSorts: ['FiniteSet', 'IntegerPredicate'],
  rules: [...executableMorphismAtlas(), ...ADD],
})
console.log('探索項', r.terms.length, 'goals', r.goals.length)
const bySort = new Map<string, number>()
for (const t of r.terms) bySort.set(t.sort, (bySort.get(t.sort) ?? 0) + 1)
console.log([...bySort.entries()].sort())
console.log('\nOrbit 項:')
for (const t of r.terms.filter(t => t.sort === 'Orbit')) console.log(' ', t.depth, t.expression)
console.log('\nIntegerPredicate 項:')
for (const t of r.terms.filter(t => t.sort === 'IntegerPredicate')) console.log(' ', t.depth, t.expression)
console.log('\nFiniteSet 項:')
for (const t of r.terms.filter(t => t.sort === 'FiniteSet')) console.log(' ', t.depth, t.expression)
