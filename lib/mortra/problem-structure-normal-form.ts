import { createHash } from 'node:crypto'

import {
  compileProblemTaskAlgebra,
  normalizeExplicitProblemTaskAlgebra,
  type ProblemTaskAlgebra,
} from './problem-task-algebra'

type StructureBlueprint = {
  version?: number
  kernel?: string
  observable?: string
  domain?: string
  morphismChain?: string[]
  operators?: string[]
  tags?: string[]
  proofCertificate?: Array<{ verifier?: string }>
  taskAlgebra?: ProblemTaskAlgebra
  synthesizedLaw?: {
    name?: string
    arity?: number
    sources?: string[]
    target?: string
    preserves?: string[]
    backend?: string[]
  }
  structuralUniqueness?: {
    conditionSkeleton?: string[]
    querySignature?: string
    quotientAction?: string
    freeParameters?: string[]
    uniqueNormalForm?: boolean
    finiteSolutionSet?: boolean
  }
}

export type StructuralProblemCard = {
  id?: string
  family_id?: string
  morphism_chain?: string[]
  difficulty?: { score?: number }
  generation_audit?: { proofStepCount?: number }
  fusion_derivation?: {
    assignments?: Array<{
      parentId?: string
      portId?: string
      role?: string
      witnessSteps?: string[]
    }>
    bridges?: Array<{
      witnessStep?: string
      consumes?: string[]
      produces?: string
    }>
    intermediatePropositions?: Array<{
      parentId?: string
      morphism?: string
      source?: string
      target?: string
    }>
  }
  structure_blueprint?: StructureBlueprint
}

export type ProblemStructureNormalForm = {
  schema: 3
  kernel: {
    name: string
    domain: string
    basis: string[]
  }
  program: {
    inputRoles: string[]
    bridges: Array<{
      consumes: string[]
      produces: 'typed-output'
    }>
    derivedInputCount: number
    law: {
      name: string
      arity: number
      sources: string[]
      target: string
      preserves: string[]
      backend: string[]
    } | null
  }
  task: {
    observable: string
    algebra: ProblemTaskAlgebra
    algebraOrigin: 'emitted' | 'inferred'
    morphisms: string[]
    verifiers: string[]
    conditionSkeleton: string[]
    querySignature: string
    quotientAction: string
    freeParameterCount: number
    uniqueNormalForm: boolean | null
    finiteSolutionSet: boolean | null
  }
}

export type ProblemStructureFingerprints = {
  normalForm: ProblemStructureNormalForm
  /** Executable algebra only; independent of the source-domain elaboration. */
  kernel: string
  /** Executable algebra plus the typed parent-to-kernel compilation program. */
  program: string
  /** Full program plus the requested observable and proof obligations. */
  task: string
  /** The typed question program, independent of the source-domain program. */
  algebra: string
}

function clean(value: unknown): string {
  return String(value ?? '')
    .normalize('NFKC')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

function sorted(values: unknown[] | undefined): string[] {
  return [...new Set((values ?? []).map(clean).filter(Boolean))].sort()
}

function compactToken(value: unknown): string {
  return clean(value).replace(/[^a-z0-9]+/g, '')
}

const MORPHISM_BASIS: Array<[RegExp, string]> = [
  [/ablation|dependenc|minimalpremise/, 'dependence-check'],
  [/independent|replay|reverse.*(?:identity|check)|certificate|verification|audit/, 'verify'],
  [/tailbound|bound|majori|estimate/, 'bound'],
  [/period|solutionset|classif|maximum|minimum|threshold|zeroindex|returnset|fixedpoint|projection/, 'query'],
  [/character|predicate|powersum|trace|norm|expectation|observable/, 'observe'],
  [/orbit|stateaction|matrixaction|indexgeneration|iteration/, 'iterate'],
  [/product|pullback|pairing|compose|synchron|subsequence/, 'compose'],
  [/quotient|modulo|modular|residue/, 'quotient'],
  [/transport|substitut|coordinate|mobius|affine.*map/, 'transport'],
  [/eliminat|denominatorclear|rearrang|normaliz|resultant|groebner/, 'normalize'],
  [/elaborat|extract|configuration|construction|parse|typing/, 'elaborate'],
]

function basisOperation(value: unknown): string {
  const token = compactToken(value)
  for (const [pattern, operation] of MORPHISM_BASIS) {
    if (pattern.test(token)) return operation
  }
  return token ? 'domain-operation' : ''
}

function basisProgram(values: unknown[] | undefined): string[] {
  const result: string[] = []
  for (const value of values ?? []) {
    const operation = basisOperation(value)
    if (operation && operation !== result.at(-1)) result.push(operation)
  }
  return result
}

function conceptualKernelName(blueprint: StructureBlueprint, fallback: unknown): string {
  const tags = new Set((blueprint.tags ?? []).map(compactToken))
  const kernel = compactToken(blueprint.kernel ?? fallback)
  const law = compactToken(blueprint.synthesizedLaw?.name)
  if (
    tags.has('finitestate')
    || law.includes('finiteorbit')
    || kernel.includes('finitegeneratedaction')
    || kernel.includes('finitestatecyclic')
  ) return 'finite-generated-action-observable'
  if (
    tags.has('reversiblechart')
    || kernel.includes('reversiblemobius')
    || kernel.includes('reversiblepolynomialroot')
  ) return 'reversible-coordinate-transport'
  if (
    tags.has('subsequence')
    || kernel.includes('generatedindex')
    || kernel.includes('indexedpowersum')
  ) return 'generated-index-observable'
  return clean(blueprint.kernel || fallback)
}

function kernelBasis(name: string, operators: unknown[] | undefined): string[] {
  if (name === 'finite-generated-action-observable') {
    return ['elaborate', 'finite-carrier', 'iterate', 'observe', 'verify']
  }
  if (name === 'reversible-coordinate-transport') {
    return ['elaborate', 'transport', 'normalize', 'observe', 'verify']
  }
  if (name === 'generated-index-observable') {
    return ['elaborate', 'iterate', 'compose', 'observe', 'bound', 'verify']
  }
  return sorted(basisProgram(operators).filter(operation =>
    !['query', 'observe', 'verify', 'dependence-check', 'domain-operation'].includes(operation)
  ))
}

function verifierBasis(value: unknown): string {
  const token = compactToken(value)
  if (/matrix|companion/.test(token)) return 'matrix-replay'
  if (/finite|orbit|enumerat|divisor/.test(token)) return 'finite-exhaustion'
  if (/polynomial|resultant|groebner|coefficient/.test(token)) return 'polynomial-identity'
  if (/rational|bigint|integer|modular/.test(token)) return 'exact-arithmetic'
  if (/ablation|dependency|premise/.test(token)) return 'dependence-check'
  return token ? 'domain-verifier' : ''
}

function digest(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

/**
 * Build a normal form for the generating proof program, not for its wording or
 * numeric instance. Parent ids, symbols, constants, answers and prose are
 * deliberately absent so alpha-renaming and parameter changes cannot create a
 * new structural class.
 */
export function normalizeProblemStructure(card: StructuralProblemCard): ProblemStructureNormalForm {
  const blueprint = card.structure_blueprint ?? {}
  const derivation = card.fusion_derivation ?? {}
  const assignments = derivation.assignments ?? []
  const roleByPort = new Map(assignments.map(assignment => [
    clean(assignment.portId),
    clean(assignment.role) || 'typed-input',
  ]))

  const bridges = (derivation.bridges ?? [])
    .map(bridge => ({
      consumes: sorted((bridge.consumes ?? []).map(port => roleByPort.get(clean(port)) ?? 'typed-input')),
      // Concrete output names frequently encode the selected question. The
      // kernel only needs the typed bridge topology; the observable remains in
      // the task normal form below.
      produces: 'typed-output' as const,
    }))
    .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)))

  const synthesizedLaw = blueprint.synthesizedLaw
  const law = synthesizedLaw
    ? {
        name: clean(synthesizedLaw.name),
        arity: Number(synthesizedLaw.arity ?? 0),
        sources: sorted(synthesizedLaw.sources),
        target: clean(synthesizedLaw.target),
        preserves: sorted(synthesizedLaw.preserves),
        backend: sorted(synthesizedLaw.backend),
      }
    : null
  const uniqueness = blueprint.structuralUniqueness
  const operators = blueprint.morphismChain ?? blueprint.operators ?? card.morphism_chain ?? []
  const kernelName = conceptualKernelName(blueprint, card.family_id)
  const emittedAlgebra = normalizeExplicitProblemTaskAlgebra(blueprint.taskAlgebra)
  const algebra = emittedAlgebra ?? compileProblemTaskAlgebra({
      kernel: kernelName,
      observable: blueprint.observable,
      querySignature: uniqueness?.querySignature,
    })

  return {
    schema: 3,
    kernel: {
      name: kernelName,
      domain: kernelName === 'finite-generated-action-observable'
        ? 'finite-dynamical-system'
        : clean(blueprint.domain),
      basis: kernelBasis(kernelName, operators),
    },
    program: {
      inputRoles: sorted(assignments.map(assignment => assignment.role)),
      bridges,
      derivedInputCount: (derivation.intermediatePropositions ?? []).length,
      law,
    },
    task: {
      observable: clean(blueprint.observable),
      algebra,
      algebraOrigin: emittedAlgebra ? 'emitted' : 'inferred',
      morphisms: basisProgram(operators),
      verifiers: sorted((blueprint.proofCertificate ?? []).map(certificate => verifierBasis(certificate.verifier))),
      conditionSkeleton: sorted(uniqueness?.conditionSkeleton),
      querySignature: clean(uniqueness?.querySignature),
      quotientAction: clean(uniqueness?.quotientAction),
      freeParameterCount: uniqueness?.freeParameters?.length ?? 0,
      uniqueNormalForm: uniqueness?.uniqueNormalForm ?? null,
      finiteSolutionSet: uniqueness?.finiteSolutionSet ?? null,
    },
  }
}

export function problemStructureFingerprints(card: StructuralProblemCard): ProblemStructureFingerprints {
  const normalForm = normalizeProblemStructure(card)
  const proofObligations = {
    verifiers: normalForm.task.verifiers,
    freeParameterCount: normalForm.task.freeParameterCount,
    uniqueNormalForm: normalForm.task.uniqueNormalForm,
    finiteSolutionSet: normalForm.task.finiteSolutionSet,
  }
  return {
    normalForm,
    kernel: digest(normalForm.kernel),
    program: digest({ kernel: normalForm.kernel, program: normalForm.program }),
    task: digest({
      kernel: normalForm.kernel,
      program: normalForm.program,
      algebra: normalForm.task.algebra,
      proofObligations,
    }),
    algebra: digest(normalForm.task.algebra),
  }
}

function candidateOrder(left: StructuralProblemCard, right: StructuralProblemCard): number {
  return Number(right.difficulty?.score ?? 0) - Number(left.difficulty?.score ?? 0)
    || Number(right.generation_audit?.proofStepCount ?? right.morphism_chain?.length ?? 0)
      - Number(left.generation_audit?.proofStepCount ?? left.morphism_chain?.length ?? 0)
    || clean(left.id).localeCompare(clean(right.id))
}

/**
 * Select one strongest representative per kernel first, then one per remaining
 * task. This prevents one prolific surface family from filling a batch.
 */
export function selectStructurallyDiverseProblems<T extends StructuralProblemCard>(
  cards: readonly T[],
  limit: number,
): T[] {
  if (limit <= 0) return []
  const taskRepresentatives = new Map<string, T>()
  const fingerprints = new Map<T, ProblemStructureFingerprints>()
  for (const card of cards) {
    const signature = problemStructureFingerprints(card)
    fingerprints.set(card, signature)
    const current = taskRepresentatives.get(signature.task)
    if (!current || candidateOrder(card, current) < 0) taskRepresentatives.set(signature.task, card)
  }

  const representatives = [...taskRepresentatives.values()].sort(candidateOrder)
  const selected: T[] = []
  const selectedTasks = new Set<string>()
  const selectedKernels = new Set<string>()

  for (const card of representatives) {
    const signature = fingerprints.get(card) ?? problemStructureFingerprints(card)
    if (selectedKernels.has(signature.kernel)) continue
    selected.push(card)
    selectedTasks.add(signature.task)
    selectedKernels.add(signature.kernel)
    if (selected.length >= limit) return selected
  }
  for (const card of representatives) {
    const signature = fingerprints.get(card) ?? problemStructureFingerprints(card)
    if (selectedTasks.has(signature.task)) continue
    selected.push(card)
    selectedTasks.add(signature.task)
    if (selected.length >= limit) break
  }
  return selected
}
