import { createHash } from 'node:crypto'

import {
  CORE_FAMILY_BY_LAW,
  PROBLEM_TASK_CORE_PRIMITIVES,
  PROBLEM_TASK_PRIMITIVES,
  type ProblemTaskCorePrimitive,
  type ProblemTaskPrimitive,
  type ProblemTaskValueSort,
} from './problem-task-algebra'

export type CompositionGenomeNode = {
  id: string
  operator: ProblemTaskCorePrimitive
  law: ProblemTaskPrimitive
  /** A member of the small problem-level alphabet, such as L/R. */
  structuralSymbol?: string
  inputs: string[]
  output: ProblemTaskValueSort
  repeat?: number
}

export type CompositionGenome = {
  schema: 1
  input: ProblemTaskValueSort
  nodes: CompositionGenomeNode[]
  outputs: string[]
}

export type CompositionGenomeMetrics = {
  nodeCount: number
  repeatIndependentOperationCount: number
  expandedOperationCount: number
  edgeCount: number
  heterogeneousEdgeCount: number
  distinctLawTransitionCount: number
  structuralQuotientNodeCount: number
  distinctCompositionContextCount: number
  rootToOutputPathCount: number
  heterogeneousDepth: number
  branchCount: number
  mergeCount: number
  repetitionSiteCount: number
  coreAlphabet: ProblemTaskCorePrimitive[]
  structuralAlphabet: string[]
  taskLaws: ProblemTaskPrimitive[]
  maximumRepeatedBranchFraction: number
}

export type CompositionComplexityTarget = {
  minimumRepeatIndependentOperationCount: number
  minimumHeterogeneousEdgeCount: number
  minimumDistinctLawTransitionCount: number
  minimumStructuralQuotientNodeCount: number
  minimumDistinctCompositionContextCount: number
  minimumBranchCount: number
  minimumMergeCount: number
  minimumRootToOutputPathCount: number
  maximumRepeatedBranchFraction: number
  maximumCoreAlphabetSize: number
  maximumStructuralAlphabetSize: number
}

export type CompositionComplexityAudit = {
  passed: boolean
  metrics: CompositionGenomeMetrics
  failures: string[]
}

export const DEEP_COMPOSITION_TARGET: CompositionComplexityTarget = {
  minimumRepeatIndependentOperationCount: 100,
  minimumHeterogeneousEdgeCount: 80,
  minimumDistinctLawTransitionCount: 6,
  minimumStructuralQuotientNodeCount: 100,
  minimumDistinctCompositionContextCount: 32,
  minimumBranchCount: 8,
  minimumMergeCount: 8,
  minimumRootToOutputPathCount: 256,
  maximumRepeatedBranchFraction: 0.2,
  maximumCoreAlphabetSize: 5,
  maximumStructuralAlphabetSize: 8,
}

type NormalizedCompositionGenome = {
  schema: 1
  input: ProblemTaskValueSort
  nodes: Array<{
    operator: ProblemTaskCorePrimitive
    law: ProblemTaskPrimitive
    structuralSymbol?: string
    inputs: string[]
    output: ProblemTaskValueSort
    repetition: 'single' | 'repeated'
  }>
  outputs: string[]
}

const CORE_OPERATORS = new Set<ProblemTaskCorePrimitive>(PROBLEM_TASK_CORE_PRIMITIVES)
const TASK_LAWS = new Set<ProblemTaskPrimitive>(PROBLEM_TASK_PRIMITIVES)

function digest(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function checkedRepeat(value: number | undefined): number {
  const repeat = value ?? 1
  if (!Number.isSafeInteger(repeat) || repeat < 1) {
    throw new Error('composition genome repeat must be a positive safe integer')
  }
  return repeat
}

/**
 * Validate and alpha-normalize a composition graph. Concrete constants and
 * repeat counts are intentionally removed from the fingerprint: changing a
 * number cannot manufacture a new structural species.
 */
export function normalizeCompositionGenome(genome: CompositionGenome): NormalizedCompositionGenome {
  if (genome.schema !== 1 || !genome.nodes.length || !genome.outputs.length) {
    throw new Error('composition genome must contain nodes and at least one output')
  }

  const renamed = new Map<string, string>()
  const renamedSymbols = new Map<string, string>()
  const normalized: NormalizedCompositionGenome['nodes'] = []
  for (const [index, node] of genome.nodes.entries()) {
    if (!node.id || renamed.has(node.id)) throw new Error(`duplicate or empty composition node id: ${node.id}`)
    if (!CORE_OPERATORS.has(node.operator)) throw new Error(`unknown composition operator: ${node.operator}`)
    if (!TASK_LAWS.has(node.law)) throw new Error(`unknown composition law: ${node.law}`)
    if (CORE_FAMILY_BY_LAW[node.law] !== node.operator) {
      throw new Error(`composition law ${node.law} does not belong to ${node.operator}`)
    }
    checkedRepeat(node.repeat)
    const inputs = node.inputs.map(input => {
      if (input === 'input') return 'input'
      const mapped = renamed.get(input)
      if (!mapped) throw new Error(`composition node ${node.id} refers to unavailable input ${input}`)
      return mapped
    })
    const canonicalId = `n${index}`
    renamed.set(node.id, canonicalId)
    normalized.push({
      operator: node.operator,
      law: node.law,
      structuralSymbol: node.structuralSymbol
        ? (() => {
            const existing = renamedSymbols.get(node.structuralSymbol)
            if (existing) return existing
            const canonical = `s${renamedSymbols.size}`
            renamedSymbols.set(node.structuralSymbol, canonical)
            return canonical
          })()
        : undefined,
      inputs,
      output: node.output,
      repetition: checkedRepeat(node.repeat) > 1 ? 'repeated' : 'single',
    })
  }

  const outputs = genome.outputs.map(output => {
    const mapped = renamed.get(output)
    if (!mapped) throw new Error(`composition genome output does not exist: ${output}`)
    return mapped
  })
  return { schema: 1, input: genome.input, nodes: normalized, outputs }
}

export function compositionGenomeFingerprint(genome: CompositionGenome): string {
  return digest(normalizeCompositionGenome(genome))
}

export function compositionGenomeMetrics(genome: CompositionGenome): CompositionGenomeMetrics {
  normalizeCompositionGenome(genome)
  const outdegree = new Map<string, number>()
  const depth = new Map<string, number>()
  const pathCount = new Map<string, number>()
  const nodeById = new Map(genome.nodes.map(node => [node.id, node]))
  const lawTransitions = new Set<string>()
  const quotientSignature = new Map<string, string>()
  const quotientSignatures = new Set<string>()
  const contexts = new Map<string, Set<string>>()
  const distinctContexts = new Set<string>()
  let expandedOperationCount = 0
  let largestRepeatedBlock = 0
  let edgeCount = 0
  let heterogeneousEdgeCount = 0
  const structuralAlphabet = [...new Set(genome.nodes.flatMap(node =>
    node.structuralSymbol ? [node.structuralSymbol] : []))]
  const canonicalSymbol = new Map(structuralAlphabet.map((symbol, index) => [symbol, `s${index}`]))

  for (const node of genome.nodes) {
    const repeat = checkedRepeat(node.repeat)
    expandedOperationCount += repeat
    if (repeat > 1) largestRepeatedBlock = Math.max(largestRepeatedBlock, repeat)
    for (const input of node.inputs) {
      if (input === 'input') continue
      outdegree.set(input, (outdegree.get(input) ?? 0) + 1)
      edgeCount += 1
      const parent = nodeById.get(input)
      if (parent && parent.law !== node.law) {
        heterogeneousEdgeCount += 1
        lawTransitions.add(parent.law + '->' + node.law)
      }
    }
    const parentDepth = node.inputs.reduce(
      (maximum, input) => Math.max(maximum, input === 'input' ? 0 : depth.get(input) ?? 0),
      0,
    )
    depth.set(node.id, parentDepth + 1)
    pathCount.set(node.id, node.inputs.reduce(
      (sum, input) => sum + (input === 'input' ? 1 : pathCount.get(input) ?? 0),
      0,
    ))

    const token = [
      node.operator,
      node.law,
      node.output,
      node.structuralSymbol ? canonicalSymbol.get(node.structuralSymbol) : '',
      repeat > 1 ? 'repeated' : 'single',
    ].join(':')
    const parentSignatures = node.inputs.map(input =>
      input === 'input' ? 'input' : quotientSignature.get(input) ?? 'missing')
    const nodeSignature = digest([token, parentSignatures])
    quotientSignature.set(node.id, nodeSignature)
    quotientSignatures.add(nodeSignature)

    const nodeContexts = new Set<string>()
    for (const input of node.inputs) {
      const parentContexts = input === 'input' ? new Set(['']) : contexts.get(input) ?? new Set([''])
      for (const parentContext of parentContexts) {
        const parts = parentContext ? parentContext.split('/') : []
        const context = [...parts, token].slice(-8).join('/')
        nodeContexts.add(context)
        distinctContexts.add(context)
      }
    }
    contexts.set(node.id, nodeContexts)
  }

  return {
    nodeCount: genome.nodes.length,
    repeatIndependentOperationCount: genome.nodes.length,
    expandedOperationCount,
    edgeCount,
    heterogeneousEdgeCount,
    distinctLawTransitionCount: lawTransitions.size,
    structuralQuotientNodeCount: quotientSignatures.size,
    distinctCompositionContextCount: distinctContexts.size,
    rootToOutputPathCount: genome.outputs.reduce((sum, output) => sum + (pathCount.get(output) ?? 0), 0),
    heterogeneousDepth: Math.max(...genome.outputs.map(output => depth.get(output) ?? 0)),
    branchCount: [...outdegree.values()].filter(value => value > 1).length,
    mergeCount: genome.nodes.filter(node => node.inputs.length > 1).length,
    repetitionSiteCount: genome.nodes.filter(node => checkedRepeat(node.repeat) > 1).length,
    coreAlphabet: PROBLEM_TASK_CORE_PRIMITIVES.filter(operator =>
      genome.nodes.some(node => node.operator === operator)),
    structuralAlphabet,
    taskLaws: PROBLEM_TASK_PRIMITIVES.filter(law => genome.nodes.some(node => node.law === law)),
    maximumRepeatedBranchFraction: expandedOperationCount
      ? largestRepeatedBlock / expandedOperationCount
      : 0,
  }
}

export function auditCompositionComplexity(
  genome: CompositionGenome,
  target: CompositionComplexityTarget = DEEP_COMPOSITION_TARGET,
): CompositionComplexityAudit {
  const metrics = compositionGenomeMetrics(genome)
  const failures: string[] = []
  const minimumChecks: Array<[keyof CompositionGenomeMetrics, number]> = [
    ['repeatIndependentOperationCount', target.minimumRepeatIndependentOperationCount],
    ['heterogeneousEdgeCount', target.minimumHeterogeneousEdgeCount],
    ['distinctLawTransitionCount', target.minimumDistinctLawTransitionCount],
    ['structuralQuotientNodeCount', target.minimumStructuralQuotientNodeCount],
    ['distinctCompositionContextCount', target.minimumDistinctCompositionContextCount],
    ['branchCount', target.minimumBranchCount],
    ['mergeCount', target.minimumMergeCount],
    ['rootToOutputPathCount', target.minimumRootToOutputPathCount],
  ]
  for (const [key, minimum] of minimumChecks) {
    const actual = metrics[key]
    if (typeof actual === 'number' && actual < minimum) {
      failures.push(String(key) + '=' + actual + ' < ' + minimum)
    }
  }
  if (metrics.maximumRepeatedBranchFraction > target.maximumRepeatedBranchFraction) {
    failures.push(
      'maximumRepeatedBranchFraction='
      + metrics.maximumRepeatedBranchFraction
      + ' > '
      + target.maximumRepeatedBranchFraction,
    )
  }
  if (metrics.coreAlphabet.length > target.maximumCoreAlphabetSize) {
    failures.push('coreAlphabetSize=' + metrics.coreAlphabet.length + ' > ' + target.maximumCoreAlphabetSize)
  }
  if (metrics.structuralAlphabet.length > target.maximumStructuralAlphabetSize) {
    failures.push(
      'structuralAlphabetSize=' + metrics.structuralAlphabet.length + ' > ' + target.maximumStructuralAlphabetSize,
    )
  }
  return { passed: failures.length === 0, metrics, failures }
}
