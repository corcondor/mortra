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
