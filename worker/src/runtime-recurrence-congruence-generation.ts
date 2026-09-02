import { createHash } from 'node:crypto'

import { enumerateFiniteOrbit } from '../../lib/mortra/finite-generated-action'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'

type RecurrenceSpec = {
  parentId: string
  sequence: string
  initial: readonly [number, number]
  coefficientCurrent: number
  coefficientPrevious: number
  constant: number
}

type CongruenceSpec = {
  parentId: string
  variable: string
  coefficient: number
  rhs: number
  modulus: number
}

type Orbit = {
  states: Array<readonly [number, number]>
  preperiod: number
  period: number
}

export type RuntimeRecurrenceCongruenceGeneration = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

function canonical(value: number, modulus: number): number {
  return ((value % modulus) + modulus) % modulus
}

function normalizeMath(text: string): string {
  return text
    .replace(/[−－]/g, '-')
    .replace(/\\equiv/g, '≡')
    .replace(/\\(?:cdot|times)/g, '*')
    .replace(/([A-Za-z])_\{([^{}]+)\}/g, '$1_($2)')
    .replace(/[＄$]|\\\(|\\\)|\\\[|\\\]/g, '')
    .replace(/\s+/g, '')
}

function signedInteger(value: string | undefined): number | null {
  if (value === undefined || value === '' || value === '+') return 1
  if (value === '-') return -1
  if (!/^[+-]?\d+$/.test(value)) return null
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) ? parsed : null
}

function parseRecurrence(parent: DiscoveryParent): RecurrenceSpec | null {
  const compact = normalizeMath(parent.statement ?? '')
  if (!/(?:数列|漸化式|sequence|recurrence)/i.test(compact)) return null
  const recurrence = compact.match(/([A-Za-z])_\(n\+2\)=([^。；;]+)/)
  if (!recurrence) return null
  const sequence = recurrence[1]
  let rhs = recurrence[2].replace(/(?:とする|で定める|を定める|である).*$/, '')
  rhs = rhs
    .replace(new RegExp(`${sequence}_\\(n\\+1\\)`, 'g'), 'U')
    .replace(new RegExp(`${sequence}_n`, 'g'), 'V')
    .replace(/\*/g, '')
  const signed = /^[+-]/.test(rhs) ? rhs : `+${rhs}`
  const terms = signed.match(/[+-][^+-]+/g)
  if (!terms?.length) return null
  let coefficientCurrent = 0
  let coefficientPrevious = 0
  let constant = 0
  for (const term of terms) {
    const sign = term[0] === '-' ? -1 : 1
    const body = term.slice(1)
    const variable = body.endsWith('U') ? 'U' : body.endsWith('V') ? 'V' : null
    const coefficientText = variable ? body.slice(0, -1) : body
    const coefficient = signedInteger(coefficientText)
    if (coefficient === null) return null
    if (variable === 'U') coefficientCurrent += sign * coefficient
    else if (variable === 'V') coefficientPrevious += sign * coefficient
    else constant += sign * coefficient
  }
  if (coefficientCurrent === 0 && coefficientPrevious === 0) return null
  const initialZero = compact.match(new RegExp(`${sequence}_\\(0\\)=([+-]?\\d+)`))
    ?? compact.match(new RegExp(`${sequence}_0=([+-]?\\d+)`))
  const initialOne = compact.match(new RegExp(`${sequence}_\\(1\\)=([+-]?\\d+)`))
    ?? compact.match(new RegExp(`${sequence}_1=([+-]?\\d+)`))
  if (!initialZero || !initialOne) return null
  const first = Number(initialZero[1])
  const second = Number(initialOne[1])
  if (![first, second, coefficientCurrent, coefficientPrevious, constant].every(Number.isSafeInteger)) return null
  return {
    parentId: String(parent.id),
    sequence,
    initial: [first, second],
    coefficientCurrent,
    coefficientPrevious,
    constant,
  }
}

function parseCongruence(parent: DiscoveryParent): CongruenceSpec | null {
  const compact = normalizeMath(parent.statement ?? '')
  if (!/(?:合同|≡|pmod|mod)/i.test(compact)) return null
  const match = compact.match(
    /([+-]?\d*)\*?([A-Za-z])≡([+-]?\d+)(?:\\pmod\{?(\d+)\}?|\(mod(\d+)\)|mod(\d+))/i,
  )
  if (!match) return null
  const coefficient = signedInteger(match[1])
  const rhs = Number(match[3])
  const modulus = Number(match[4] ?? match[5] ?? match[6])
  if (coefficient === null || !Number.isSafeInteger(rhs) || !Number.isSafeInteger(modulus) || modulus < 2 || modulus > 100_000) {
    return null
  }
  return {
    parentId: String(parent.id),
    variable: match[2],
    coefficient,
    rhs,
    modulus,
  }
}

function nextState(
  state: readonly [number, number],
  recurrence: RecurrenceSpec,
  modulus: number,
): readonly [number, number] {
  const raw = BigInt(recurrence.coefficientCurrent) * BigInt(state[1])
    + BigInt(recurrence.coefficientPrevious) * BigInt(state[0])
    + BigInt(recurrence.constant)
  const modulusBig = BigInt(modulus)
  return [
    state[1],
    Number(((raw % modulusBig) + modulusBig) % modulusBig),
  ]
}

function buildOrbit(
  recurrence: RecurrenceSpec,
  modulus: number,
  shift: number,
  maxStates = 100_000,
): Orbit | null {
  let state: readonly [number, number] = [
    canonical(recurrence.initial[0], modulus),
    canonical(recurrence.initial[1], modulus),
  ]
  for (let index = 0; index < shift; index++) state = nextState(state, recurrence, modulus)
  const orbit = enumerateFiniteOrbit({
    initial: state,
    next: current => nextState(current, recurrence, modulus),
    key: current => `${current[0]},${current[1]}`,
    maxStates,
  })
  return orbit
    ? { states: orbit.states, preperiod: orbit.cycleOffset, period: orbit.period }
    : null
}

function multiplyMatrix(left: number[][], right: number[][], modulus: number): number[][] {
  return left.map((row, i) => right[0].map((_, j) => {
    let value = 0n
    for (let k = 0; k < row.length; k++) {
      value += BigInt(left[i][k]) * BigInt(right[k][j])
    }
    return Number(((value % BigInt(modulus)) + BigInt(modulus)) % BigInt(modulus))
  }))
}

function matrixPower(matrix: number[][], exponent: number, modulus: number): number[][] {
  let result: number[][] = matrix.map((row, i) => row.map((_, j) => i === j ? 1 : 0))
  let base = matrix.map(row => [...row])
  let power = exponent
  while (power > 0) {
    if (power % 2 === 1) result = multiplyMatrix(result, base, modulus)
    power = Math.floor(power / 2)
    if (power) base = multiplyMatrix(base, base, modulus)
  }
  return result
}

function matrixStateAt(recurrence: RecurrenceSpec, modulus: number, index: number): readonly [number, number] {
  const matrix = [
    [0, 1, 0],
    [canonical(recurrence.coefficientPrevious, modulus), canonical(recurrence.coefficientCurrent, modulus), canonical(recurrence.constant, modulus)],
    [0, 0, 1],
  ]
  const power = matrixPower(matrix, index, modulus)
  const initial = [canonical(recurrence.initial[0], modulus), canonical(recurrence.initial[1], modulus), 1]
  const output = power.map(row => row.reduce(
    (sum, coefficient, column) => canonical(sum + coefficient * initial[column], modulus),
    0,
  ))
  return [output[0], output[1]]
}

function accepted(value: number, congruence: CongruenceSpec): boolean {
  return canonical(congruence.coefficient * value - congruence.rhs, congruence.modulus) === 0
}

function acceptanceSignature(orbit: Orbit, congruence: CongruenceSpec): string {
  return orbit.states.map(state => accepted(state[0], congruence) ? '1' : '0').join('') +
    `:${orbit.preperiod}:${orbit.period}`
}

function perturbRecurrence(
  recurrence: RecurrenceSpec,
  congruence: CongruenceSpec,
  shift: number,
  baseline: string,
): { field: string; delta: number; signature: string } | null {
  const variants: Array<{ field: string; value: RecurrenceSpec }> = [
    { field: 'a_0', value: { ...recurrence, initial: [recurrence.initial[0] + 1, recurrence.initial[1]] } },
    { field: 'a_1', value: { ...recurrence, initial: [recurrence.initial[0], recurrence.initial[1] + 1] } },
    { field: 'coefficient_current', value: { ...recurrence, coefficientCurrent: recurrence.coefficientCurrent + 1 } },
    { field: 'coefficient_previous', value: { ...recurrence, coefficientPrevious: recurrence.coefficientPrevious + 1 } },
    { field: 'constant', value: { ...recurrence, constant: recurrence.constant + 1 } },
  ]
  for (const variant of variants) {
    const orbit = buildOrbit(variant.value, congruence.modulus, shift)
    if (!orbit) continue
    const signature = acceptanceSignature(orbit, congruence)
    if (signature !== baseline) return { field: variant.field, delta: 1, signature }
  }
  return null
}

function perturbCongruence(
  recurrence: RecurrenceSpec,
  congruence: CongruenceSpec,
  shift: number,
  baseline: string,
): { field: string; delta: number; signature: string } | null {
  const variants = [
    { field: 'rhs', value: { ...congruence, rhs: congruence.rhs + 1 } },
    { field: 'coefficient', value: { ...congruence, coefficient: congruence.coefficient + 1 } },
  ]
  for (const variant of variants) {
    const orbit = buildOrbit(recurrence, congruence.modulus, shift)
    if (!orbit) continue
    const signature = acceptanceSignature(orbit, variant.value)
    if (signature !== baseline) return { field: variant.field, delta: 1, signature }
  }
  return null
}

function recurrenceTex(recurrence: RecurrenceSpec): string {
  const signed = (value: number, body: string, first: boolean): string => {
    if (value === 0) return ''
    const magnitude = Math.abs(value)
    const coefficient = magnitude === 1 ? '' : String(magnitude)
    if (first) return `${value < 0 ? '-' : ''}${coefficient}${body}`
    return `${value < 0 ? '-' : '+'}${coefficient}${body}`
  }
  const parts: string[] = []
  const append = (value: number, body: string) => {
    const part = signed(value, body, parts.length === 0)
    if (part) parts.push(part)
  }
  append(recurrence.coefficientCurrent, `${recurrence.sequence}_{n+1}`)
  append(recurrence.coefficientPrevious, `${recurrence.sequence}_n`)
  append(recurrence.constant, '')
  return parts.join('') || '0'
}

function solutionSetTex(orbit: Orbit, congruence: CongruenceSpec): string {
  const transient = orbit.states
    .map((state, index) => ({ state, index }))
    .filter(item => item.index < orbit.preperiod && accepted(item.state[0], congruence))
    .map(item => String(item.index))
  const periodic = orbit.states
    .map((state, index) => ({ state, index }))
    .filter(item => item.index >= orbit.preperiod && accepted(item.state[0], congruence))
    .map(item => `${item.index}+${orbit.period}k`)
  const pieces: string[] = []
  if (transient.length) pieces.push(`\\{${transient.join(',')}\\}`)
  if (periodic.length) pieces.push(...periodic.map(value => `\\{${value}\\mid k\\in\\mathbb Z_{\\ge0}\\}`))
  return pieces.join('\\cup') || '\\varnothing'
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function generatedCard(
  parents: readonly DiscoveryParent[],
  recurrence: RecurrenceSpec,
  congruence: CongruenceSpec,
  shift: number,
  hypothesesEvaluated: number,
): ExecutableFusionCard | null {
  const orbit = buildOrbit(recurrence, congruence.modulus, shift)
  if (!orbit || orbit.period <= 0) return null
  const startState = matrixStateAt(recurrence, congruence.modulus, shift)
  if (startState[0] !== orbit.states[0][0] || startState[1] !== orbit.states[0][1]) return null
  const replayIndices = [...new Set([
    0,
    orbit.preperiod,
    orbit.states.length - 1,
    ...orbit.states.map((_, index) => index).filter(index => accepted(orbit.states[index][0], congruence)),
  ])].filter(index => index >= 0 && index < orbit.states.length)
  for (const index of replayIndices) {
    const matrixState = matrixStateAt(recurrence, congruence.modulus, shift + index)
    if (matrixState[0] !== orbit.states[index][0] || matrixState[1] !== orbit.states[index][1]) return null
  }
  const closingState = nextState(orbit.states[orbit.states.length - 1], recurrence, congruence.modulus)
  if (closingState[0] !== orbit.states[orbit.preperiod][0] || closingState[1] !== orbit.states[orbit.preperiod][1]) return null
  const baseline = acceptanceSignature(orbit, congruence)
  const recurrencePerturbation = perturbRecurrence(recurrence, congruence, shift, baseline)
  const congruencePerturbation = perturbCongruence(recurrence, congruence, shift, baseline)
  if (!recurrencePerturbation || !congruencePerturbation) return null

  const solution = solutionSetTex(orbit, congruence)
  const shiftedTerm = shift === 0 ? `${recurrence.sequence}_n` : `${recurrence.sequence}_{n+${shift}}`
  const signature = hash({
    parents: parents.map(parent => ({ id: parent.id, statement: parent.statement })),
    shift,
    orbit: orbit.states,
    preperiod: orbit.preperiod,
    period: orbit.period,
    solution,
  })
  const parentIds = [recurrence.parentId, congruence.parentId]
  const chain = [
    'CurrentStatementElaboration',
    'CompanionStateConstruction',
    'FiniteModularOrbit',
    'CongruenceAcceptancePredicate',
    'OrbitPredicatePullback',
    'PeriodCompletenessCertificate',
    'GeneratedProblem',
  ]
  const obligations = [
    'the recurrence is elaborated from the current parent',
    'the congruence is elaborated from the current parent',
    'the modular state orbit closes exactly',
    'every accepted state and every rejected state in one complete orbit is checked',
    'matrix powers independently replay the accepted indices',
    'perturbing either parent changes the solution set',
  ]
  const proofCertificate = [
    { id: `${signature}.recurrence`, claim: 'the recurrence equals the companion-state action', verifier: 'exact-modular-state-replay' },
    { id: `${signature}.orbit`, claim: `the orbit has preperiod ${orbit.preperiod} and period ${orbit.period}`, verifier: 'complete-finite-state-enumeration' },
    { id: `${signature}.predicate`, claim: 'the congruence predicate is checked on every state in the complete orbit', verifier: 'exact-modular-residual' },
    { id: `${signature}.matrix`, claim: 'binary matrix powers reproduce all selected orbit states', verifier: 'independent-companion-matrix-replay' },
    { id: `${signature}.ablation`, claim: 'both parents are necessary for the classified index set', verifier: 'structure-preserving-parent-perturbation' },
  ]
  const generatedProgram = {
    schema: 'mortra.runtime-recurrence-congruence.v1',
    recurrence_parent_id: recurrence.parentId,
    congruence_parent_id: congruence.parentId,
    recurrence: {
      sequence: recurrence.sequence,
      initial: recurrence.initial,
      coefficient_current: recurrence.coefficientCurrent,
      coefficient_previous: recurrence.coefficientPrevious,
      constant: recurrence.constant,
    },
    congruence: {
      coefficient: congruence.coefficient,
      rhs: congruence.rhs,
      modulus: congruence.modulus,
    },
    shift,
    orbit: {
      states: orbit.states,
      preperiod: orbit.preperiod,
      period: orbit.period,
      acceptance_signature: baseline,
    },
    solution_tex: solution,
    independent_matrix_replay_indices: replayIndices,
    counterfactuals: {
      recurrence: recurrencePerturbation,
      congruence: congruencePerturbation,
    },
  }

  return {
    id: `mortra-runtime-recurrence-congruence.${signature}`,
    family_id: 'runtime.recurrence_congruence_orbit',
    statement_tex: `整数列 \\(${recurrence.sequence}_0=${recurrence.initial[0]},\\ ${recurrence.sequence}_1=${recurrence.initial[1]},\\ ` +
      `${recurrence.sequence}_{n+2}=${recurrenceTex(recurrence)}\\) を考える。非負整数 \\(n\\) のうち、` +
      `\\[${congruence.coefficient}${shiftedTerm}\\equiv ${congruence.rhs}\\pmod{${congruence.modulus}}\\]` +
      `を満たすものをすべて求めよ。`,
    answer_tex: `\\(${solution}\\)`,
    solution_tex: `状態を \\(v_n=(${recurrence.sequence}_{n+${shift}},${recurrence.sequence}_{n+${shift + 1}})\\pmod{${congruence.modulus}}\\) とおく。` +
      `漸化式から状態遷移は一意に定まり、状態を重複が現れるまで列挙すると、前周期は ${orbit.preperiod}、周期は ${orbit.period} である。` +
      `従って、最初の ${orbit.states.length} 状態を調べれば、その後のすべての状態も尽くされる。各状態で ` +
      `\\(${congruence.coefficient}${shiftedTerm}-${congruence.rhs}\\) を ${congruence.modulus} で割った余りを調べると、` +
      `\\[n\\in ${solution}\\]` +
      `を得る。周期の閉鎖は状態対の完全一致で確認した。また、受理された添字では伴随行列の二進累乗を別に計算し、逐次計算と一致することを確認した。`,
    domain: 'recurrence_and_modular_arithmetic',
    morphism_chain: chain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'complete modular state orbit + exact congruence predicate + independent matrix-power replay',
      exact_backend: true,
      independent_check: true,
      samples: [orbit.states.length, orbit.preperiod, orbit.period, replayIndices.length],
    },
    difficulty: { band: 'runtime_cross_domain_finite_action', score: 6 + Math.log2(Math.max(2, orbit.states.length)) + shift / 4 },
    fusion_derivation: {
      passed: true,
      reason: 'the congruence predicate is pulled back along the recurrence action and classified on its complete finite orbit',
      ablationPassed: true,
      assignments: [
        {
          parentId: recurrence.parentId,
          portId: `recurrence:${recurrence.parentId}`,
          role: 'finite_generated_action',
          matchedAnchors: [recurrence.sequence, 'recurrence-state', 'companion-matrix'],
          witnessSteps: ['CompanionStateConstruction', 'FiniteModularOrbit'],
          requiredObligations: obligations,
          consumedObligations: obligations,
          coverage: 1,
        },
        {
          parentId: congruence.parentId,
          portId: `congruence:${congruence.parentId}`,
          role: 'acceptance_predicate',
          matchedAnchors: [congruence.variable, `mod-${congruence.modulus}`, 'linear-congruence'],
          witnessSteps: ['CongruenceAcceptancePredicate', 'OrbitPredicatePullback'],
          requiredObligations: obligations,
          consumedObligations: obligations,
          coverage: 1,
        },
      ],
      bridges: [{
        id: `orbit-predicate-pullback:${signature}`,
        witnessStep: `accept(v_n) iff ${congruence.coefficient}${shiftedTerm}=${congruence.rhs} mod ${congruence.modulus}`,
        consumes: [`recurrence:${recurrence.parentId}`, `congruence:${congruence.parentId}`],
        produces: 'CertifiedIndexSet',
      }],
      intermediatePropositions: [
        {
          parentId: recurrence.parentId,
          morphism: 'FiniteModularOrbit',
          source: 'IntegerRecurrence',
          target: 'FiniteGeneratedAction',
          proposition: `the state orbit has ${orbit.states.length} representatives and period ${orbit.period}`,
          proved: true,
        },
        {
          parentId: congruence.parentId,
          morphism: 'CongruenceAcceptancePredicate',
          source: 'LinearCongruence',
          target: 'StatePredicate',
          proposition: `a state is accepted exactly when its first coordinate satisfies the current congruence`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: `runtime-recurrence-congruence.${signature}`,
      version: 1,
      kernel: 'finite_generated_action_with_acceptance_predicate',
      observable: 'CertifiedIndexSet',
      operators: chain,
      domain: 'recurrence_x_residue_class',
      tags: ['runtime-synthesis', 'atlas-free', 'recurrence', 'congruence', 'finite-state', 'one-to-many'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      synthesizedLaw: {
        name: 'FiniteOrbitPredicatePullback',
        expression: 'indices(T^n(v0) in P) are transient points plus periodic residue classes',
        arity: 2,
        sources: ['FiniteGeneratedAction', 'DecidableStatePredicate'],
        target: 'SemilinearIndexSet',
        preserves: ['exact-modular-state', 'period-completeness', 'all-parent-provenance'],
        backend: ['finite-state-enumeration', 'binary-matrix-power-replay'],
      },
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesEvaluated,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
    diagram: {
      version: 1,
      kind: 'state',
      title: '漸化式の有限状態軌道',
      caption: `状態対を法 ${congruence.modulus} で追跡し、合同条件を満たす状態だけを受理します。`,
      states: [
        { id: 'start', label: `v0: ${orbit.states[0][0]}, ${orbit.states[0][1]}`, active: true },
        { id: 'orbit', label: `${orbit.states.length} states` },
        { id: 'cycle', label: `period: ${orbit.period}` },
        { id: 'accepted', label: `accepted: ${orbit.states.filter(state => accepted(state[0], congruence)).length}`, terminal: true },
      ],
      transitions: [
        { from: 'start', to: 'orbit', label: 'T' },
        { from: 'orbit', to: 'cycle', label: 'first repeated state' },
        { from: 'cycle', to: 'accepted', label: 'congruence filter' },
      ],
    },
    proof_roadmap: chain.map((morphism, index) => ({
      morphism_id: `${signature}.${index + 1}`,
      label_ja: morphism,
      source_ja: index === 0 ? '現在の二つの親問題' : chain[index - 1],
      target_ja: morphism,
      role_ja: '証明済みの表現変換',
    })),
    proof_obligations: proofCertificate.map(item => ({ id: item.id, claim_ja: item.claim, status: 'verified' })),
  }
}

export function synthesizeRuntimeRecurrenceCongruenceProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimeRecurrenceCongruenceGeneration {
  if (parents.length !== 2 || requested <= 0) {
    return { applicable: false, reason: 'recurrence-congruence composition requires exactly two current parents', cards: [], hypothesesEvaluated: 0 }
  }
  if (parents.some(parent => parent.id === undefined) || new Set(parents.map(parent => String(parent.id))).size !== 2) {
    return { applicable: false, reason: 'both current parents require distinct stable ids', cards: [], hypothesesEvaluated: 0 }
  }
  const recurrences = parents.map(parseRecurrence)
  const congruences = parents.map(parseCongruence)
  const recurrence = recurrences.find((value): value is RecurrenceSpec => value !== null)
  const congruence = congruences.find((value): value is CongruenceSpec => value !== null)
  if (!recurrence || !congruence || recurrence.parentId === congruence.parentId) {
    return {
      applicable: false,
      reason: 'the current parents do not provide one executable second-order recurrence and one executable linear congruence',
      cards: [],
      hypothesesEvaluated: 0,
    }
  }

  const cards: ExecutableFusionCard[] = []
  const seen = new Set<string>()
  let hypothesesEvaluated = 0
  const budget = Math.max(16, requested * 8)
  for (let shift = 0; shift < budget && cards.length < requested; shift++) {
    hypothesesEvaluated += 1
    const card = generatedCard(parents, recurrence, congruence, shift, hypothesesEvaluated)
    if (!card) continue
    const normalForm = hash({ statement: card.statement_tex, answer: card.answer_tex }, 32)
    if (seen.has(normalForm)) continue
    seen.add(normalForm)
    cards.push(card)
  }
  return {
    applicable: cards.length > 0,
    reason: cards.length
      ? `${cards.length} recurrence-congruence problems were synthesized from complete modular orbits`
      : `${hypothesesEvaluated} orbit-predicate pullbacks failed exact closure or parent sensitivity`,
    cards,
    hypothesesEvaluated,
  }
}
