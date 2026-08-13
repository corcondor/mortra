import { semanticId, type SemanticId } from '../world/world-types'
import {
  auditDiagramContract,
  type DiagramContract,
  type DiagramContractViolation,
} from './diagram-contract'

export type PolynomialTerm = {
  coefficient: number
  powers: number[]
}

export type FiniteRecurrenceSpec = {
  id: string
  sourceSemanticIds: SemanticId[]
  modulus: number
  initial: number[]
  update: { terms: PolynomialTerm[] }
  targetIndex: string
  source?: string
}

export type ResidueState = {
  id: SemanticId
  index: number
  values: number[]
}

export type TransitionEdge = {
  id: SemanticId
  from: SemanticId
  to: SemanticId
  emitted: number
}

export type FiniteStateStructure = {
  modulus: number
  order: number
  initialState: SemanticId
  transitions: TransitionEdge[]
  repeatFrom: SemanticId
  repeatAt: SemanticId
  preperiod: number
  period: number
}

export type FiniteStateRewrite = {
  kind: 'reachable-subgraph' | 'cycle-quotient' | 'index-reduction'
  input: string
  output: string
  precondition: string
}

export type FiniteStateInvariant = {
  kind: 'recurrence-transition' | 'residue-class' | 'determinism' | 'periodicity'
  statement: string
}

export type FiniteStateDiagram = DiagramContract<
  'finite-state-transition',
  ResidueState,
  FiniteStateStructure,
  FiniteStateRewrite,
  FiniteStateInvariant
>

export type FiniteStateSolution = {
  status: 'certified' | 'abstained' | 'invalid'
  answer?: number
  requestedIndex: string
  reducedIndex?: number
  diagram?: FiniteStateDiagram
  errors: string[]
  operations: number
}

export type FiniteStateArtifact = {
  id: SemanticId
  kind: 'interactive-finite-state-diagram'
  references: SemanticId[]
  semanticTransport: {
    status: 'certified'
    encoded: string[]
    forgotten: string[]
    legalRewrites: FiniteStateRewrite[]
    invariants: FiniteStateInvariant[]
  }
  designHeuristic: {
    status: 'heuristic'
    layout: 'tail-then-cycle'
    note: string
  }
  states: Array<ResidueState & { x: number; y: number; phase: 'tail' | 'cycle' }>
  transitions: TransitionEdge[]
  query: {
    requestedIndex: string
    reducedIndex: number
    answer: number
  }
  period: { preperiod: number; length: number }
}

const integer = (value: number) => Number.isInteger(value) && Number.isFinite(value)

function canonical(value: number, modulus: number): number {
  return ((value % modulus) + modulus) % modulus
}

function stateKey(values: number[]): string {
  return values.join(',')
}

function smallHash(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function modPow(base: bigint, exponent: number, modulus: bigint): bigint {
  let result = BigInt(1)
  let factor = ((base % modulus) + modulus) % modulus
  let power = exponent
  while (power > 0) {
    if (power % 2 === 1) result = (result * factor) % modulus
    factor = (factor * factor) % modulus
    power = Math.floor(power / 2)
  }
  return result
}

export function validateFiniteRecurrence(spec: FiniteRecurrenceSpec): string[] {
  const errors: string[] = []
  if (!spec.id.trim()) errors.push('id is required')
  if (!spec.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  if (!integer(spec.modulus) || spec.modulus < 2 || spec.modulus > 1_000_000) {
    errors.push('modulus must be an integer in [2, 1000000]')
  }
  if (!spec.initial.length) errors.push('initial state must not be empty')
  if (!spec.initial.every(integer)) errors.push('initial values must be integers')
  if (!spec.update.terms.length) errors.push('update polynomial must not be empty')
  for (const term of spec.update.terms) {
    if (!integer(term.coefficient)) errors.push('coefficients must be integers')
    if (term.powers.length !== spec.initial.length) errors.push('polynomial arity must equal recurrence order')
    if (!term.powers.every(power => integer(power) && power >= 0)) {
      errors.push('powers must be non-negative integers')
    }
  }
  try {
    if (BigInt(spec.targetIndex) < BigInt(0)) errors.push('targetIndex must be non-negative')
  } catch {
    errors.push('targetIndex must be an integer string')
  }
  return [...new Set(errors)]
}

export function evaluateUpdate(spec: FiniteRecurrenceSpec, state: number[]): number {
  const modulus = BigInt(spec.modulus)
  let total = BigInt(0)
  for (const term of spec.update.terms) {
    let value = BigInt(term.coefficient)
    for (let index = 0; index < state.length; index += 1) {
      value = (value * modPow(BigInt(state[index]), term.powers[index], modulus)) % modulus
    }
    total = (total + value) % modulus
  }
  return Number((total + modulus) % modulus)
}

export function transitionState(spec: FiniteRecurrenceSpec, state: number[]): number[] {
  return [...state.slice(1), evaluateUpdate(spec, state)]
}

export function buildFiniteStateDiagram(
  spec: FiniteRecurrenceSpec,
  options: { maxStates?: number } = {},
): { diagram?: FiniteStateDiagram; errors: string[]; operations: number } {
  const errors = validateFiniteRecurrence(spec)
  if (errors.length) return { errors, operations: 0 }

  const maxStates = options.maxStates ?? 200_000
  const canonicalInitial = spec.initial.map(value => canonical(value, spec.modulus))
  const seen = new Map<string, number>()
  const states: ResidueState[] = []
  const transitions: TransitionEdge[] = []
  let current = canonicalInitial
  let operations = 0

  while (!seen.has(stateKey(current))) {
    if (states.length >= maxStates) {
      return { errors: [`reachable orbit exceeded maxStates=${maxStates}`], operations }
    }
    const index = states.length
    const key = stateKey(current)
    const id = semanticId(`${spec.id}:state:${key}`)
    seen.set(key, index)
    states.push({ id, index, values: current })
    const next = transitionState(spec, current)
    transitions.push({
      id: semanticId(`${spec.id}:edge:${key}->${stateKey(next)}`),
      from: id,
      to: semanticId(`${spec.id}:state:${stateKey(next)}`),
      emitted: next[next.length - 1],
    })
    current = next
    operations += 1
  }

  const repeatAtIndex = seen.get(stateKey(current))
  if (repeatAtIndex === undefined) return { errors: ['cycle detection invariant failed'], operations }
  const preperiod = repeatAtIndex
  const period = states.length - repeatAtIndex
  const trace = states.map(state => state.values).join('|')
  const claim = `reachable orbit enters a cycle after ${preperiod} steps with period ${period}`
  const diagram: FiniteStateDiagram = {
    id: semanticId(`${spec.id}:finite-state-diagram`),
    kind: 'finite-state-transition',
    sourceSemanticIds: spec.sourceSemanticIds,
    encoded: [
      'residue state of the last k sequence terms',
      'deterministic polynomial transition over Z/mZ',
      'reachable orbit and first repeated state',
    ],
    forgotten: [
      'integer magnitude before reduction modulo m',
      'closed form over the original coefficient domain',
      'states outside the orbit reachable from the given initial state',
    ],
    carriers: states,
    structure: {
      modulus: spec.modulus,
      order: spec.initial.length,
      initialState: states[0].id,
      transitions,
      repeatFrom: states[states.length - 1].id,
      repeatAt: states[repeatAtIndex].id,
      preperiod,
      period,
    },
    legalRewrites: [
      {
        kind: 'reachable-subgraph',
        input: `(Z/${spec.modulus}Z)^${spec.initial.length}`,
        output: `${states.length} reachable states`,
        precondition: 'the initial state and deterministic transition are fixed',
      },
      {
        kind: 'cycle-quotient',
        input: `orbit states ${preperiod},...,${states.length - 1}`,
        output: `Z/${period}Z action after the preperiod`,
        precondition: 'two complete typed states are equal',
      },
      {
        kind: 'index-reduction',
        input: 'n >= preperiod',
        output: `preperiod + ((n-preperiod) mod ${period})`,
        precondition: 'cycle certificate has been independently checked',
      },
    ],
    invariants: [
      { kind: 'recurrence-transition', statement: 'every edge is exactly one recurrence evaluation' },
      { kind: 'residue-class', statement: `all coordinates are canonical residues modulo ${spec.modulus}` },
      { kind: 'determinism', statement: 'every reachable state has exactly one outgoing transition' },
      { kind: 'periodicity', statement: claim },
    ],
    ambiguities: [
      {
        kind: 'quotient-collision',
        detail: 'different integer sequences can induce the same residue orbit',
        recoverableWith: ['the unreduced recurrence', 'integer initial values'],
      },
    ],
    certificates: [{
      id: semanticId(`${spec.id}:cycle-certificate:${smallHash(trace)}`),
      claim,
      status: 'certified',
      method: 'exact finite-state transition replay',
      consumed: spec.sourceSemanticIds,
      detail: `trace=${smallHash(trace)}; states=${states.length}`,
    }],
    provenance: {
      source: spec.source ?? 'typed recurrence specification',
      constructedBy: 'MORTRA finite-state diagram compiler',
      constructedFrom: spec.sourceSemanticIds,
    },
    parameters: { modulus: spec.modulus, order: spec.initial.length, reachableStates: states.length },
    timeline: states.map(state => ({ step: state.index, semanticId: state.id, operation: 'apply recurrence' })),
  }
  return { diagram, errors: [], operations }
}

export function verifyFiniteStateDiagram(
  spec: FiniteRecurrenceSpec,
  diagram: FiniteStateDiagram,
): { certified: boolean; errors: string[] } {
  const errors: string[] = [...auditDiagramContract(diagram).map(item => `${item.kind}: ${item.detail}`)]
  const specErrors = validateFiniteRecurrence(spec)
  errors.push(...specErrors)
  if (specErrors.length) return { certified: false, errors }
  if (diagram.kind !== 'finite-state-transition') errors.push('wrong diagram kind')
  if (diagram.structure.modulus !== spec.modulus) errors.push('modulus changed during transport')
  if (diagram.structure.order !== spec.initial.length) errors.push('recurrence order changed during transport')
  if (diagram.carriers.length !== diagram.structure.transitions.length) {
    errors.push('deterministic orbit must have one transition per reachable state')
  }

  const states = new Map(diagram.carriers.map(state => [state.id, state]))
  const outgoing = new Map<SemanticId, number>()
  for (const edge of diagram.structure.transitions) {
    const from = states.get(edge.from)
    const to = states.get(edge.to)
    if (!from || !to) {
      errors.push(`edge ${edge.id} references a missing state`)
      continue
    }
    outgoing.set(edge.from, (outgoing.get(edge.from) ?? 0) + 1)
    const expected = transitionState(spec, from.values)
    if (stateKey(expected) !== stateKey(to.values)) errors.push(`edge ${edge.id} violates the recurrence`)
    if (edge.emitted !== expected[expected.length - 1]) errors.push(`edge ${edge.id} has a false emitted value`)
  }
  for (const state of diagram.carriers) {
    if (outgoing.get(state.id) !== 1) errors.push(`state ${state.id} is not deterministic`)
    if (state.values.some(value => value < 0 || value >= spec.modulus)) {
      errors.push(`state ${state.id} is not canonical modulo ${spec.modulus}`)
    }
  }
  const repeatFrom = states.get(diagram.structure.repeatFrom)
  const repeatAt = states.get(diagram.structure.repeatAt)
  if (!repeatFrom || !repeatAt) errors.push('cycle endpoints are missing')
  if (repeatFrom && repeatAt) {
    const next = transitionState(spec, repeatFrom.values)
    if (stateKey(next) !== stateKey(repeatAt.values)) errors.push('declared cycle does not close')
    if (repeatAt.index !== diagram.structure.preperiod) errors.push('preperiod index is inconsistent')
    if (diagram.carriers.length - repeatAt.index !== diagram.structure.period) errors.push('period length is inconsistent')
  }
  return { certified: errors.length === 0, errors }
}

export function solveWithFiniteStateDiagram(
  spec: FiniteRecurrenceSpec,
  options: { maxStates?: number } = {},
): FiniteStateSolution {
  const built = buildFiniteStateDiagram(spec, options)
  if (!built.diagram) {
    return {
      status: built.errors.some(error => error.startsWith('reachable orbit exceeded')) ? 'abstained' : 'invalid',
      requestedIndex: spec.targetIndex,
      errors: built.errors,
      operations: built.operations,
    }
  }
  const verification = verifyFiniteStateDiagram(spec, built.diagram)
  if (!verification.certified) {
    return {
      status: 'invalid', requestedIndex: spec.targetIndex,
      diagram: built.diagram, errors: verification.errors, operations: built.operations,
    }
  }
  const target = BigInt(spec.targetIndex)
  const preperiod = BigInt(built.diagram.structure.preperiod)
  const period = BigInt(built.diagram.structure.period)
  const reduced = target < BigInt(built.diagram.carriers.length)
    ? Number(target)
    : Number(preperiod + ((target - preperiod) % period))
  return {
    status: 'certified',
    answer: built.diagram.carriers[reduced].values[0],
    requestedIndex: spec.targetIndex,
    reducedIndex: reduced,
    diagram: built.diagram,
    errors: [],
    operations: built.operations,
  }
}

export function solveByDirectIteration(
  spec: FiniteRecurrenceSpec,
  stepBudget = 10_000,
): FiniteStateSolution {
  const errors = validateFiniteRecurrence(spec)
  if (errors.length) return { status: 'invalid', requestedIndex: spec.targetIndex, errors, operations: 0 }
  const target = BigInt(spec.targetIndex)
  const requiredTransitions = target >= BigInt(spec.initial.length)
    ? target - BigInt(spec.initial.length) + BigInt(1)
    : BigInt(0)
  if (requiredTransitions > BigInt(stepBudget)) {
    let state = spec.initial.map(value => canonical(value, spec.modulus))
    for (let index = 0; index < stepBudget; index += 1) state = transitionState(spec, state)
    return {
      status: 'abstained', requestedIndex: spec.targetIndex,
      errors: [`direct iteration exhausted stepBudget=${stepBudget}`], operations: stepBudget,
    }
  }
  if (target < BigInt(spec.initial.length)) {
    return {
      status: 'certified', answer: canonical(spec.initial[Number(target)], spec.modulus),
      requestedIndex: spec.targetIndex, reducedIndex: Number(target), errors: [], operations: 0,
    }
  }
  let state = spec.initial.map(value => canonical(value, spec.modulus))
  let operations = 0
  const transitions = Number(target) - spec.initial.length + 1
  for (let index = 0; index < transitions; index += 1) {
    state = transitionState(spec, state)
    operations += 1
  }
  return {
    status: 'certified', answer: state[state.length - 1], requestedIndex: spec.targetIndex,
    reducedIndex: Number(target), errors: [], operations,
  }
}

export function compileFiniteStateArtifact(solution: FiniteStateSolution): FiniteStateArtifact {
  if (solution.status !== 'certified' || !solution.diagram || solution.answer === undefined
    || solution.reducedIndex === undefined) {
    throw new Error('only certified finite-state solutions can become artifacts')
  }
  const diagram = solution.diagram
  const tailLength = diagram.structure.preperiod
  const cycleLength = diagram.structure.period
  const states = diagram.carriers.map(state => {
    if (state.index < tailLength) {
      return { ...state, x: 80 + state.index * 92, y: 130, phase: 'tail' as const }
    }
    const angle = ((state.index - tailLength) / cycleLength) * Math.PI * 2 - Math.PI / 2
    const centerX = 520 + Math.min(tailLength, 4) * 18
    return {
      ...state,
      x: centerX + Math.cos(angle) * 150,
      y: 170 + Math.sin(angle) * 118,
      phase: 'cycle' as const,
    }
  })
  return {
    id: semanticId(`${diagram.id}:artifact`),
    kind: 'interactive-finite-state-diagram',
    references: [...diagram.sourceSemanticIds, ...diagram.carriers.map(state => state.id)],
    semanticTransport: {
      status: 'certified',
      encoded: diagram.encoded,
      forgotten: diagram.forgotten,
      legalRewrites: diagram.legalRewrites,
      invariants: diagram.invariants,
    },
    designHeuristic: {
      status: 'heuristic',
      layout: 'tail-then-cycle',
      note: '座標は可読性のための配置であり、数学的証明には使わない。',
    },
    states,
    transitions: diagram.structure.transitions,
    query: {
      requestedIndex: solution.requestedIndex,
      reducedIndex: solution.reducedIndex,
      answer: solution.answer,
    },
    period: { preperiod: tailLength, length: cycleLength },
  }
}

export function diagramViolations(diagram: FiniteStateDiagram): DiagramContractViolation[] {
  return auditDiagramContract(diagram)
}
