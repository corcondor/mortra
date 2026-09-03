import assert from 'node:assert/strict'
import test from 'node:test'

import {
  auditCompositionComplexity,
  compositionGenomeFingerprint,
  compositionGenomeMetrics,
  normalizeCompositionGenome,
  type CompositionGenome,
} from './composition-genome'

const branched: CompositionGenome = {
  schema: 1,
  input: 'algebraic-configuration',
  nodes: [
    { id: 'a', operator: 'transform', law: 'map', inputs: ['input'], output: 'polynomial', repeat: 100 },
    { id: 'b', operator: 'restrict', law: 'preimage', inputs: ['a'], output: 'index-set' },
    { id: 'c', operator: 'aggregate', law: 'fold', inputs: ['a'], output: 'scalar', repeat: 100 },
    { id: 'd', operator: 'combine', law: 'pair', inputs: ['b', 'c'], output: 'configuration' },
  ],
  outputs: ['d'],
}

test('measures branching, merging, and expanded executions', () => {
  assert.deepEqual(compositionGenomeMetrics(branched), {
    nodeCount: 4,
    repeatIndependentOperationCount: 4,
    expandedOperationCount: 202,
    edgeCount: 4,
    heterogeneousEdgeCount: 4,
    distinctLawTransitionCount: 4,
    structuralQuotientNodeCount: 4,
    distinctCompositionContextCount: 5,
    rootToOutputPathCount: 2,
    heterogeneousDepth: 3,
    branchCount: 1,
    mergeCount: 1,
    repetitionSiteCount: 2,
    coreAlphabet: ['transform', 'combine', 'restrict', 'aggregate'],
    structuralAlphabet: [],
    taskLaws: ['pair', 'map', 'fold', 'preimage'],
    maximumRepeatedBranchFraction: 100 / 202,
  })
})

test('renaming nodes and changing repeat counts cannot create a new structural species', () => {
  const renamed: CompositionGenome = {
    ...branched,
    nodes: [
      { id: 'seed', operator: 'transform', law: 'map', inputs: ['input'], output: 'polynomial', repeat: 2026 },
      { id: 'left', operator: 'restrict', law: 'preimage', inputs: ['seed'], output: 'index-set' },
      { id: 'right', operator: 'aggregate', law: 'fold', inputs: ['seed'], output: 'scalar', repeat: 2026 },
      { id: 'join', operator: 'combine', law: 'pair', inputs: ['left', 'right'], output: 'configuration' },
    ],
    outputs: ['join'],
  }
  assert.equal(compositionGenomeFingerprint(renamed), compositionGenomeFingerprint(branched))
})

test('renaming a finite structural alphabet preserves the structural species', () => {
  const leftRight: CompositionGenome = {
    schema: 1,
    input: 'configuration',
    nodes: [
      { id: 'a', operator: 'transform', law: 'map', structuralSymbol: 'L', inputs: ['input'], output: 'configuration' },
      { id: 'b', operator: 'transform', law: 'map', structuralSymbol: 'R', inputs: ['a'], output: 'configuration' },
    ],
    outputs: ['b'],
  }
  const zeroOne: CompositionGenome = {
    ...leftRight,
    nodes: [
      { ...leftRight.nodes[0], structuralSymbol: 'zero' },
      { ...leftRight.nodes[1], structuralSymbol: 'one' },
    ],
  }
  assert.equal(compositionGenomeFingerprint(leftRight), compositionGenomeFingerprint(zeroOne))
  assert.deepEqual(compositionGenomeMetrics(leftRight).structuralAlphabet, ['L', 'R'])
})

test('rejects a forward reference instead of fingerprinting an invalid graph', () => {
  assert.throws(() => normalizeCompositionGenome({
    schema: 1,
    input: 'typed-object',
    nodes: [{ id: 'a', operator: 'transform', law: 'map', inputs: ['missing'], output: 'scalar' }],
    outputs: ['a'],
  }), /unavailable input/)
})

test('does not confuse a large repeat count with deep compositional structure', () => {
  const audit = auditCompositionComplexity(branched)
  assert.equal(audit.passed, false)
  assert.match(audit.failures.join('; '), /repeatIndependentOperationCount=4 < 100/)
})

test('accepts a long typed graph built from the same five core operators', () => {
  const nodes: CompositionGenome['nodes'] = [{
    id: 'n0',
    operator: 'canonicalize',
    law: 'normalize',
    inputs: ['input'],
    output: 'scalar',
  }]
  let current = 'n0'
  for (let index = 1; index <= 70; index += 1) {
    const id = 'n' + index
    const even = index % 2 === 0
    nodes.push({
      id,
      operator: even ? 'canonicalize' : 'transform',
      law: even ? 'normalize' : 'map',
      inputs: [current],
      output: 'scalar',
    })
    current = id
  }
  for (let index = 0; index < 10; index += 1) {
    const left = 'left' + index
    const right = 'right' + index
    const join = 'join' + index
    nodes.push(
      { id: left, operator: 'restrict', law: 'preimage', inputs: [current], output: 'scalar' },
      { id: right, operator: 'aggregate', law: 'fold', inputs: [current], output: 'scalar' },
      { id: join, operator: 'combine', law: 'pair', inputs: [left, right], output: 'scalar' },
    )
    current = join
  }
  const audit = auditCompositionComplexity({
    schema: 1,
    input: 'scalar',
    nodes,
    outputs: [current],
  })
  assert.equal(audit.passed, true, audit.failures.join('; '))
  assert.equal(audit.metrics.repeatIndependentOperationCount, 101)
  assert.equal(audit.metrics.coreAlphabet.length, 5)
})

test('rejects a long graph whose local structure is only an alternating repetition', () => {
  const nodes: CompositionGenome['nodes'] = []
  let current = 'input'
  for (let index = 0; index < 160; index += 1) {
    const id = 'repeat-' + index
    nodes.push({
      id,
      operator: index % 2 ? 'canonicalize' : 'transform',
      law: index % 2 ? 'normalize' : 'map',
      inputs: [current],
      output: 'scalar',
    })
    current = id
  }
  const audit = auditCompositionComplexity({ schema: 1, input: 'scalar', nodes, outputs: [current] })
  assert.equal(audit.passed, false)
  assert.match(audit.failures.join('; '), /distinctCompositionContextCount=/)
})
