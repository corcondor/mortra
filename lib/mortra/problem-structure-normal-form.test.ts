import assert from 'node:assert/strict'
import test from 'node:test'

import {
  problemStructureFingerprints,
  selectStructurallyDiverseProblems,
  type StructuralProblemCard,
} from './problem-structure-normal-form'

function card(options: {
  id: string
  parentIds: string[]
  observable: string
  query: string
  score: number
  kernel?: string
  tags?: string[]
  roles?: string[]
  taskAlgebra?: NonNullable<NonNullable<StructuralProblemCard['structure_blueprint']>['taskAlgebra']>
}): StructuralProblemCard {
  return {
    id: options.id,
    family_id: 'generated.example',
    difficulty: { score: options.score },
    morphism_chain: ['Elaborate', 'FiniteOrbit', options.observable],
    fusion_derivation: {
      assignments: options.parentIds.map((parentId, index) => ({
        parentId,
        portId: `${parentId}:port:${index}`,
        role: options.roles?.[index] ?? (index === 0 ? 'transition' : 'predicate'),
        witnessSteps: ['Elaborate'],
      })),
      bridges: [{
        witnessStep: 'FiniteOrbit',
        consumes: options.parentIds.map((parentId, index) => `${parentId}:port:${index}`),
        produces: options.observable,
      }],
      intermediatePropositions: options.parentIds.map((parentId, index) => ({
        parentId,
        morphism: 'Elaborate',
        source: index === 0 ? 'Recurrence' : 'Congruence',
        target: index === 0 ? 'Transition' : 'Predicate',
      })),
    },
    structure_blueprint: {
      version: 1,
      kernel: options.kernel ?? 'finite-generated-action',
      observable: options.observable,
      domain: 'recurrence-x-congruence',
      operators: ['Elaborate', 'FiniteOrbit', options.observable],
      tags: options.tags ?? [],
      morphismChain: ['Elaborate', 'FiniteOrbit', options.observable],
      proofCertificate: [{ verifier: 'exact finite enumeration' }],
      taskAlgebra: options.taskAlgebra,
      structuralUniqueness: {
        conditionSkeleton: ['second-order recurrence', 'linear congruence'],
        querySignature: options.query,
        quotientAction: 'residue-class quotient',
        freeParameters: ['modulus'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
      },
    },
  }
}

test('parent ids and numeric instances do not create a new structural class', () => {
  const left = card({ id: 'instance-7', parentIds: ['p7', 'q7'], observable: 'IndexSet', query: 'classify indices', score: 8 })
  const right = card({ id: 'instance-101', parentIds: ['p101', 'q101'], observable: 'IndexSet', query: 'classify indices', score: 9 })
  assert.equal(problemStructureFingerprints(left).kernel, problemStructureFingerprints(right).kernel)
  assert.equal(problemStructureFingerprints(left).program, problemStructureFingerprints(right).program)
  assert.equal(problemStructureFingerprints(left).task, problemStructureFingerprints(right).task)
})

test('a new observable is a new task but not a new mathematical kernel', () => {
  const indices = card({ id: 'indices', parentIds: ['a', 'b'], observable: 'IndexSet', query: 'classify indices', score: 8 })
  const period = card({ id: 'period', parentIds: ['a', 'b'], observable: 'MinimalPeriod', query: 'find minimal period', score: 8 })
  assert.equal(problemStructureFingerprints(indices).kernel, problemStructureFingerprints(period).kernel)
  assert.equal(problemStructureFingerprints(indices).program, problemStructureFingerprints(period).program)
  assert.notEqual(problemStructureFingerprints(indices).task, problemStructureFingerprints(period).task)
})

test('sine and cosine zero sets compile to one typed question program', () => {
  const sine = card({
    id: 'sine-zero',
    parentIds: ['a', 'b'],
    observable: 'sine_zero_index_set',
    query: 'classify all recurrence indices at which the rational-angle sine vanishes',
    score: 8,
  })
  const cosine = card({
    id: 'cosine-zero',
    parentIds: ['a', 'b'],
    observable: 'cosine_zero_index_set',
    query: 'classify all recurrence indices at which the rational-angle cosine vanishes',
    score: 8,
  })
  assert.equal(problemStructureFingerprints(sine).algebra, problemStructureFingerprints(cosine).algebra)
  assert.equal(problemStructureFingerprints(sine).task, problemStructureFingerprints(cosine).task)
})

test('trigonometric names do not split the minimal-period operation', () => {
  const sine = card({
    id: 'sine-period',
    parentIds: ['a', 'b'],
    observable: 'eventual_minimal_sine_period',
    query: 'minimal eventual sine period and one exact cycle',
    score: 8,
  })
  const cosine = card({
    id: 'cosine-period',
    parentIds: ['a', 'b'],
    observable: 'eventual_minimal_trigonometric_period',
    query: 'minimal eventual period and one exact cycle',
    score: 8,
  })
  assert.equal(problemStructureFingerprints(sine).algebra, problemStructureFingerprints(cosine).algebra)
  assert.equal(problemStructureFingerprints(sine).task, problemStructureFingerprints(cosine).task)
})

test('a preimage task and a period task remain distinct', () => {
  const zeros = card({
    id: 'zero-set',
    parentIds: ['a', 'b'],
    observable: 'sine_zero_index_set',
    query: 'classify all indices at which sine vanishes',
    score: 8,
  })
  const period = card({
    id: 'period',
    parentIds: ['a', 'b'],
    observable: 'eventual_minimal_sine_period',
    query: 'minimal eventual sine period and one exact cycle',
    score: 8,
  })
  assert.notEqual(problemStructureFingerprints(zeros).algebra, problemStructureFingerprints(period).algebra)
  assert.notEqual(problemStructureFingerprints(zeros).task, problemStructureFingerprints(period).task)
})

test('unelaborated tasks are not merged merely because their source sort agrees', () => {
  const left = card({ id: 'opaque-a', parentIds: ['a', 'b'], observable: 'UnmappedAlpha', query: 'first unknown query', score: 8 })
  const right = card({ id: 'opaque-b', parentIds: ['a', 'b'], observable: 'UnmappedBeta', query: 'second unknown query', score: 8 })
  assert.equal(problemStructureFingerprints(left).normalForm.task.algebra.complete, false)
  assert.notEqual(problemStructureFingerprints(left).algebra, problemStructureFingerprints(right).algebra)
  assert.notEqual(problemStructureFingerprints(left).task, problemStructureFingerprints(right).task)
})

test('engine-emitted task algebra does not depend on observable wording', () => {
  const taskAlgebra = {
    schema: 1 as const,
    input: 'algebraic-configuration' as const,
    operations: [
      { operator: 'pair' as const, output: 'configuration' as const },
      { operator: 'map' as const, output: 'configuration' as const },
      { operator: 'eliminate' as const, output: 'polynomial' as const },
      { operator: 'normalize' as const, output: 'polynomial' as const },
    ],
    output: 'polynomial' as const,
    complete: true as const,
  }
  const left = card({
    id: 'emitted-a',
    parentIds: ['a', 'b'],
    observable: 'completely-new-wording-a',
    query: 'unknown surface question a',
    score: 8,
    kernel: 'binary_operation_on_algebraic_root_configurations',
    taskAlgebra,
  })
  const right = card({
    id: 'emitted-b',
    parentIds: ['c', 'd'],
    observable: 'completely-new-wording-b',
    query: 'unknown surface question b',
    score: 8,
    kernel: 'binary_operation_on_algebraic_root_configurations',
    taskAlgebra,
  })
  const leftFingerprint = problemStructureFingerprints(left)
  const rightFingerprint = problemStructureFingerprints(right)
  assert.equal(leftFingerprint.normalForm.task.algebraOrigin, 'emitted')
  assert.equal(rightFingerprint.normalForm.task.algebraOrigin, 'emitted')
  assert.equal(leftFingerprint.algebra, rightFingerprint.algebra)
  assert.equal(leftFingerprint.coreAlgebra, rightFingerprint.coreAlgebra)
  assert.equal(leftFingerprint.task, rightFingerprint.task)
})

test('malformed emitted task algebra is rejected instead of being trusted', () => {
  const malformed = card({
    id: 'malformed',
    parentIds: ['a', 'b'],
    observable: 'unmapped-observable',
    query: 'unmapped-query',
    score: 8,
    taskAlgebra: {
      schema: 1,
      input: 'typed-object',
      operations: [{ operator: 'map', output: 'sequence' }],
      output: 'scalar',
      complete: true,
    },
  })
  const fingerprint = problemStructureFingerprints(malformed)
  assert.equal(fingerprint.normalForm.task.algebraOrigin, 'inferred')
  assert.equal(fingerprint.normalForm.task.algebra.complete, false)
})

test('selection gives each kernel a representative before surface variants', () => {
  const cards = [
    card({ id: 'orbit-a', parentIds: ['a', 'b'], observable: 'IndexSet', query: 'indices', score: 12 }),
    card({ id: 'orbit-b', parentIds: ['c', 'd'], observable: 'Period', query: 'period', score: 11 }),
    card({ id: 'quadratic', parentIds: ['e', 'f'], observable: 'Expectation', query: 'expectation', score: 7, kernel: 'quadratic-trace' }),
  ]
  assert.deepEqual(selectStructurallyDiverseProblems(cards, 2).map(item => item.id), ['orbit-a', 'quadratic'])
})

test('domain-specific finite-state names collapse to one generative kernel', () => {
  const trigonometric = card({
    id: 'trigonometric-orbit',
    parentIds: ['recurrence', 'angle'],
    observable: 'MinimalPeriod',
    query: 'find minimal period',
    score: 9,
    kernel: 'FiniteStateCyclicCharacterFusionIR',
    tags: ['finite_state', 'trigonometry'],
    roles: ['transition', 'observable'],
  })
  const pell = card({
    id: 'pell-product',
    parentIds: ['pell', 'recurrence'],
    observable: 'CongruenceIndexSet',
    query: 'classify equality states',
    score: 9,
    kernel: 'FiniteGeneratedActionProductIR',
    tags: ['finite-state', 'pell-equation'],
    roles: ['generating orbit', 'comparison orbit'],
  })

  assert.equal(problemStructureFingerprints(trigonometric).kernel, problemStructureFingerprints(pell).kernel)
  assert.notEqual(problemStructureFingerprints(trigonometric).program, problemStructureFingerprints(pell).program)
  assert.notEqual(problemStructureFingerprints(trigonometric).task, problemStructureFingerprints(pell).task)
})
