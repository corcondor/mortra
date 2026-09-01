/**
 * Reusable morphisms promoted from held-out probe experiments.
 *
 * These are mathematical constructions, not problem families.  Synonymous
 * probe-local edges are intentionally collapsed here so every domain shares
 * one canonical atlas.
 */
export type VerifiedDomainMorphism = {
  name: string
  sources: string[]
  target: string
  preserves: string[]
  backend: string[]
  allows_cross_parent_fusion?: boolean
}

export const VERIFIED_DOMAIN_EXTENSIONS: readonly VerifiedDomainMorphism[] = [
  // Shared coercions and proof discharge.
  { name: 'RealAsScalar', sources: ['Real'], target: 'Scalar', preserves: ['value'], backend: ['identity'] },
  { name: 'ScalarAsArithmeticObject', sources: ['Scalar'], target: 'ArithmeticObject', preserves: ['value'], backend: ['identity'] },
  {
    name: 'PropositionCertification',
    sources: ['GoalProposition', 'CertifiedProposition'],
    target: 'Proof',
    preserves: ['truth', 'goal-identity', 'proof-certificate'],
    backend: ['goal-certificate-match'],
  },

  // Integer and arithmetic structure.
  { name: 'DivisorLattice', sources: ['Integer'], target: 'FiniteSet', preserves: ['divisor-lattice', 'prime-valuations'], backend: ['prime-valuation', 'integer-factorization'] },
  { name: 'PrimeValuation', sources: ['Integer', 'PrimeSpectrum'], target: 'IntegerInvariant', preserves: ['both-parent-provenance', 'prime-valuations'], backend: ['prime-valuation', 'legendre-formula'] },
  { name: 'ModularInversion', sources: ['FiniteSet', 'IntegerPair'], target: 'Integer', preserves: ['both-parent-provenance', 'unit-group-action', 'bezout-ideal'], backend: ['extended-euclidean-algorithm', 'modular-arithmetic'] },
  { name: 'ResidueOrbitOfSequence', sources: ['Sequence', 'FiniteSet'], target: 'Orbit', preserves: ['both-parent-provenance', 'congruence-class', 'periodicity'], backend: ['modular-arithmetic', 'recurrence-engine'] },
  { name: 'ArithmeticPredicateLift', sources: ['ArithmeticObject', 'IntegerPredicate'], target: 'Proposition', preserves: ['both-parent-provenance', 'integrality'], backend: ['integer-arithmetic', 'presburger-arithmetic'] },
  { name: 'PrimeArithmeticPredicateLift', sources: ['ArithmeticObject', 'PrimeSpectrum'], target: 'Proposition', preserves: ['both-parent-provenance', 'primality'], backend: ['primality-test', 'integer-arithmetic'] },
  { name: 'CongruencePredicateLift', sources: ['FiniteSet', 'IntegerPredicate'], target: 'Proposition', preserves: ['both-parent-provenance', 'congruence-class'], backend: ['modular-arithmetic', 'presburger-arithmetic'] },
  { name: 'CoprimalityProposition', sources: ['GCDValue', 'IntegerPredicate'], target: 'Proposition', preserves: ['both-parent-provenance', 'common-divisor-order'], backend: ['extended-euclidean-algorithm', 'presburger-arithmetic'] },
  { name: 'ParameterPairIndexing', sources: ['IntegerPair'], target: 'FiniteFamily', preserves: ['index-set', 'integrality'], backend: ['indexing'] },

  // Symmetry, inequalities, and algebraic realizability.
  { name: 'ElementarySymmetricChart', sources: ['FiniteFamily'], target: 'SymmetricCoordinates', preserves: ['symmetric-action', 'multiplicity'], backend: ['sympy.symmetrize'] },
  { name: 'VietaChart', sources: ['Polynomial'], target: 'SymmetricCoordinates', preserves: ['symmetric-action', 'root-coefficient-duality'], backend: ['vieta'] },
  { name: 'SymmetricConstraintSlice', sources: ['SymmetricCoordinates', 'PolynomialSystem'], target: 'SemialgebraicSet', preserves: ['both-parent-provenance', 'symmetric-action', 'feasible-set'], backend: ['groebner-basis', 'quantifier-elimination'] },
  { name: 'RealRootRealizabilityCone', sources: ['SymmetricCoordinates'], target: 'SemialgebraicSet', preserves: ['symmetric-action', 'realizability'], backend: ['newton-maclaurin', 'discriminant'] },
  { name: 'PowerMeanFiltration', sources: ['FiniteFamily'], target: 'MeanTower', preserves: ['symmetric-action', 'order'], backend: ['power-mean'] },
  { name: 'MeanTowerOrdering', sources: ['MeanTower'], target: 'Proposition', preserves: ['order'], backend: ['power-mean-inequality'] },
  { name: 'PositivstellensatzCertificate', sources: ['SemialgebraicSet'], target: 'CertifiedProposition', preserves: ['truth', 'feasible-set', 'proof-certificate'], backend: ['sos', 'cvc5'] },
  { name: 'RaviSubstitution', sources: ['TriangleMetricData'], target: 'FiniteFamily', preserves: ['triangle-inequality', 'positivity'], backend: ['linear-substitution'] },
  { name: 'RootPlaneRealization', sources: ['FiniteAlgebraicOrbit'], target: 'GeometricConfiguration', preserves: ['multiplicity', 'incidence'], backend: ['complex-plane-embedding'] },

  // Sequence, analysis, and limits.
  { name: 'SequenceTermFamily', sources: ['Sequence'], target: 'FiniteFamily', preserves: ['index-set', 'order', 'multiplicity'], backend: ['recurrence-engine', 'index-truncation'] },
  { name: 'IndexedIntegralSequence', sources: ['Function'], target: 'Sequence', preserves: ['index-set', 'linearity'], backend: ['symbolic-integration', 'recurrence-engine'] },
  { name: 'RecurrenceExtraction', sources: ['Sequence'], target: 'RecurrenceRelation', preserves: ['index-shift', 'initial-state'], backend: ['recurrence-engine', 'symbolic-identity'] },
  { name: 'RecurrenceSolution', sources: ['RecurrenceRelation'], target: 'ClosedFormSequence', preserves: ['index-shift', 'initial-state'], backend: ['sympy.rsolve', 'generating-function'] },
  { name: 'ClosedFormRealization', sources: ['ClosedFormSequence'], target: 'Sequence', preserves: ['index-set', 'value'], backend: ['identity'] },
  { name: 'ClosedFormTermFamily', sources: ['ClosedFormSequence'], target: 'FiniteFamily', preserves: ['index-set', 'multiplicity'], backend: ['recurrence-engine'] },
  { name: 'LimitOfClosedForm', sources: ['ClosedFormSequence'], target: 'Real', preserves: ['limit'], backend: ['sympy.limit'] },
  { name: 'MonotoneBoundedCertificate', sources: ['Sequence', 'Proposition'], target: 'ConvergenceCertificate', preserves: ['both-parent-provenance', 'order', 'boundedness'], backend: ['induction-engine', 'cvc5'] },
  { name: 'SqueezeCertificate', sources: ['Sequence', 'ClosedFormSequence'], target: 'ConvergenceCertificate', preserves: ['both-parent-provenance', 'order', 'limit'], backend: ['interval-arithmetic', 'sympy.limit'] },
  { name: 'CertifiedLimit', sources: ['Sequence', 'ConvergenceCertificate'], target: 'Real', preserves: ['both-parent-provenance', 'limit'], backend: ['limit-engine'] },
  { name: 'RiemannSumLimit', sources: ['FiniteFamily', 'Function'], target: 'Real', preserves: ['both-parent-provenance', 'measure-class', 'limit'], backend: ['symbolic-integration', 'limit-engine'] },
  { name: 'FunctionSeriesLimit', sources: ['Sequence', 'Function'], target: 'Function', preserves: ['both-parent-provenance', 'uniform-limit'], backend: ['series-engine'] },
  { name: 'InductionSchema', sources: ['Sequence', 'Proposition'], target: 'Proposition', preserves: ['both-parent-provenance', 'index-shift', 'truth'], backend: ['induction-engine', 'smt'] },

  // Finite structures, combinatorics, and probability.
  { name: 'ConfigurationDiscretization', sources: ['GeometricConfiguration'], target: 'FiniteSet', preserves: ['incidence', 'finite-support'], backend: ['incidence-enumeration'] },
  { name: 'OrbitAsFiniteSet', sources: ['FiniteAlgebraicOrbit'], target: 'FiniteSet', preserves: ['finite-support', 'multiplicity'], backend: ['identity'] },
  { name: 'SubsetFamilyConstruction', sources: ['FiniteSet'], target: 'FamilyOfSets', preserves: ['inclusion-order', 'finite-support'], backend: ['subset-enumeration'] },
  { name: 'ProductTrial', sources: ['FiniteSet', 'FiniteSet'], target: 'FiniteSet', preserves: ['both-parent-provenance', 'product-structure'], backend: ['cartesian-product'] },
  { name: 'FamilyUnderlyingSet', sources: ['FamilyOfSets'], target: 'FiniteSet', preserves: ['finite-support'], backend: ['identity'] },
  { name: 'SetIndexedFamily', sources: ['FiniteSet'], target: 'FiniteFamily', preserves: ['index-set'], backend: ['indexing'] },
  { name: 'InclusionExclusion', sources: ['FamilyOfSets'], target: 'Integer', preserves: ['cardinality', 'sieve-identity'], backend: ['inclusion-exclusion'] },
  { name: 'GeneratingFunctionEncoding', sources: ['FiniteFamily'], target: 'Polynomial', preserves: ['index-set', 'coefficient-sequence'], backend: ['generating-function'] },
  { name: 'CoefficientExtraction', sources: ['Polynomial'], target: 'FiniteFamily', preserves: ['coefficient-sequence'], backend: ['series-expansion'] },
  { name: 'UniformProbabilitySpace', sources: ['FiniteSet'], target: 'ProbabilitySpace', preserves: ['equal-likelihood', 'finite-support'], backend: ['uniform-measure'] },
  { name: 'EventExtraction', sources: ['ProbabilitySpace', 'Proposition'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['predicate-selection'] },
  { name: 'EventFromFamily', sources: ['ProbabilitySpace', 'FamilyOfSets'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['sigma-algebra'] },
  { name: 'ProbabilityMeasure', sources: ['ProbabilitySpace', 'Event'], target: 'Real', preserves: ['both-parent-provenance', 'measure-class', 'normalization'], backend: ['counting-measure', 'exact-rational'] },
  { name: 'RandomVariableFromFamily', sources: ['ProbabilitySpace', 'FiniteFamily'], target: 'RandomVariable', preserves: ['both-parent-provenance', 'measurability'], backend: ['pushforward'] },
  { name: 'LinearityOfExpectation', sources: ['RandomVariable'], target: 'Real', preserves: ['linearity', 'measure-class'], backend: ['exact-summation', 'indicator-decomposition'] },
  { name: 'TransitionRecurrence', sources: ['ProbabilitySpace', 'Sequence'], target: 'Sequence', preserves: ['both-parent-provenance', 'markov-transition'], backend: ['linear-recurrence'] },
  { name: 'CountingIdentityAssertion', sources: ['Integer', 'Integer'], target: 'Proposition', preserves: ['both-parent-provenance', 'cardinality'], backend: ['symbolic-identity', 'cvc5'] },
  { name: 'ProbabilityIdentityAssertion', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['both-parent-provenance', 'measure-class'], backend: ['symbolic-identity', 'cvc5'] },
  { name: 'OrderFiltration', sources: ['OrderedFamily'], target: 'FamilyOfSets', preserves: ['order', 'monotone-filtration'], backend: ['threshold-decomposition'] },
  { name: 'OrderStatisticSelection', sources: ['OrderedFamily', 'FiniteSet'], target: 'FiniteFamily', preserves: ['both-parent-provenance', 'order', 'index-set'], backend: ['order-statistics'] },
  { name: 'LinearIterationOrbit', sources: ['Matrix2'], target: 'Orbit', preserves: ['iteration', 'initial-state'], backend: ['matrix-power'] },
] as const
