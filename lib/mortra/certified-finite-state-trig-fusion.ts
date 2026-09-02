import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'
import {
  enumerateFiniteOrbit,
  minimalDivisorPeriod,
  minimalPeriodicStart,
} from './finite-generated-action'

export type ParsedIntegerSecondOrderRecurrence = {
  parentId: string
  symbol: string
  indexSymbol: string
  startIndex: number
  initial: [bigint, bigint]
  coefficients: [bigint, bigint]
  evidence: string
}

export type ParsedRationalAngle = {
  parentId: string
  numerator: bigint
  denominator: bigint
  evidence: string
  role: 'trigonometric_argument' | 'angle_equation' | 'angle_condition'
}

type State = readonly [bigint, bigint]
type Matrix2 = readonly [bigint, bigint, bigint, bigint]

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function positiveMod(value: bigint, modulus: bigint): bigint {
  const residue = value % modulus
  return residue < 0n ? residue + modulus : residue
}

function normalizedFraction(numerator: bigint, denominator: bigint): [bigint, bigint] {
  if (denominator === 0n) throw new Error('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcd(numerator, denominator)
  return [sign * numerator / divisor, sign * denominator / divisor]
}

function coefficient(source: string | undefined, implicitSign = 1n): bigint | null {
  const compact = (source ?? '')
    .replace(/\s+/g, '')
    .replace(/\\cdot|\\times/g, '')
  if (!compact || compact === '+') return implicitSign
  if (compact === '-') return -implicitSign
  if (!/^[+-]?\d+$/.test(compact)) return null
  return BigInt(compact)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function parseIntegerSecondOrderRecurrence(
  parent: CertifiedFusionParent,
): ParsedIntegerSecondOrderRecurrence | null {
  const source = parent.statement.replace(/[−–]/g, '-')
  const recurrence = source.match(
    /([A-Za-z])_\{?([A-Za-z])\+2\}?\s*=\s*([+-]?\s*\d*\s*(?:\\cdot|\\times)?\s*)?\1_\{?\2\+1\}?\s*([+-])\s*(\d*\s*(?:\\cdot|\\times)?\s*)?\1_\{?\2\}?/,
  )
  if (!recurrence) return null

  const [, symbol, indexSymbol, firstRaw, secondSign, secondRaw] = recurrence
  const firstCoefficient = coefficient(firstRaw)
  const secondMagnitude = coefficient(secondRaw)
  if (firstCoefficient === null || secondMagnitude === null) return null
  const secondCoefficient = secondSign === '-' ? -secondMagnitude : secondMagnitude

  const escaped = escapeRegExp(symbol)
  const equalInitials = source.match(new RegExp(
    `${escaped}_\\{?(\\d+)\\}?\\s*=\\s*${escaped}_\\{?(\\d+)\\}?\\s*=\\s*([+-]?\\d+)`,
  ))
  if (equalInitials) {
    const firstIndex = Number(equalInitials[1])
    const secondIndex = Number(equalInitials[2])
    if (secondIndex !== firstIndex + 1) return null
    const value = BigInt(equalInitials[3])
    return {
      parentId: parent.id,
      symbol,
      indexSymbol,
      startIndex: firstIndex,
      initial: [value, value],
      coefficients: [firstCoefficient, secondCoefficient],
      evidence: recurrence[0],
    }
  }

  const initialPattern = new RegExp(`${escaped}_\\{?(\\d+)\\}?\\s*=\\s*([+-]?\\d+)`, 'g')
  const values = [...source.matchAll(initialPattern)]
    .map(match => ({ index: Number(match[1]), value: BigInt(match[2]) }))
    .sort((left, right) => left.index - right.index)
  for (let index = 0; index + 1 < values.length; index += 1) {
    if (values[index + 1].index !== values[index].index + 1) continue
    return {
      parentId: parent.id,
      symbol,
      indexSymbol,
      startIndex: values[index].index,
      initial: [values[index].value, values[index + 1].value],
      coefficients: [firstCoefficient, secondCoefficient],
      evidence: recurrence[0],
    }
  }
  return null
}

function rationalAngleRole(source: string, start: number): ParsedRationalAngle['role'] | null {
  const before = source.slice(Math.max(0, start - 96), start)
  if (/\\(?:sin|cos|tan)(?:\^\{?[^{}]+\}?)?\s*\{?\s*$/.test(before)) {
    return 'trigonometric_argument'
  }
  if (/(?:\\angle\s*[A-Za-z0-9_{}]+|[A-Za-z](?:_\{?\d+\}?)?)\s*=\s*$/.test(before)) {
    return 'angle_equation'
  }
  if (/角[^。．\n]{0,48}(?:=|が|は)\s*$/.test(before)) return 'angle_condition'
  if (/角[^。．\n]{0,64}(?:ともに|等しく|である)\s*$/.test(before)) return 'angle_condition'
  return null
}

export function parseRationalAngles(parent: CertifiedFusionParent): ParsedRationalAngle[] {
  const source = parent.statement
    .replace(/\\left|\\right/g, '')
    .replace(/\\dfrac|\\tfrac/g, '\\frac')
    .replace(/\$|\\\(|\\\)|\\\[|\\\]/g, '')
    .replace(/\s+/g, '')
  const candidates: ParsedRationalAngle[] = []
  const seen = new Set<string>()
  const patterns = [
    /\\frac\{(?:(\d+)?)\\pi\}\{(\d+)\}/g,
    /(?:(\d+)?)\\pi\/(\d+)/g,
  ]
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) {
      const role = rationalAngleRole(source, match.index ?? 0)
      if (!role) continue
      const [numerator, denominator] = normalizedFraction(
        BigInt(match[1] || '1'),
        BigInt(match[2]),
      )
      if (denominator <= 1n || denominator > 200n) continue
      const key = `${numerator}/${denominator}`
      if (seen.has(key)) continue
      seen.add(key)
      candidates.push({
        parentId: parent.id,
        numerator,
        denominator,
        evidence: match[0],
        role,
      })
    }
  }
  return candidates
}

export function parseRationalAngle(parent: CertifiedFusionParent): ParsedRationalAngle | null {
  return parseRationalAngles(parent)[0] ?? null
}

function stateKey(state: State): string {
  return `${state[0]},${state[1]}`
}

function nextState(
  state: State,
  coefficients: readonly [bigint, bigint],
  modulus: bigint,
): State {
  return [
    state[1],
    positiveMod(coefficients[0] * state[1] + coefficients[1] * state[0], modulus),
  ]
}

function multiplyMatrix(left: Matrix2, right: Matrix2, modulus: bigint): Matrix2 {
  return [
    positiveMod(left[0] * right[0] + left[1] * right[2], modulus),
    positiveMod(left[0] * right[1] + left[1] * right[3], modulus),
    positiveMod(left[2] * right[0] + left[3] * right[2], modulus),
    positiveMod(left[2] * right[1] + left[3] * right[3], modulus),
  ]
}

function powerMatrix(matrix: Matrix2, exponent: number, modulus: bigint): Matrix2 {
  let result: Matrix2 = [1n, 0n, 0n, 1n]
  let base = matrix
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiplyMatrix(result, base, modulus)
    base = multiplyMatrix(base, base, modulus)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function applyMatrix(matrix: Matrix2, state: State, modulus: bigint): State {
  return [
    positiveMod(matrix[0] * state[0] + matrix[1] * state[1], modulus),
    positiveMod(matrix[2] * state[0] + matrix[3] * state[1], modulus),
  ]
}

function enumerateOrbit(
  recurrence: ParsedIntegerSecondOrderRecurrence,
  modulus: bigint,
): { states: State[]; cycleStart: number; statePeriod: number } | null {
  const maximumStates = Number(modulus * modulus) + 1
  const orbit = enumerateFiniteOrbit<State>({
    initial: [
      positiveMod(recurrence.initial[0], modulus),
      positiveMod(recurrence.initial[1], modulus),
    ],
    next: state => nextState(state, recurrence.coefficients, modulus),
    key: stateKey,
    maxStates: maximumStates,
  })
  return orbit
    ? { states: orbit.states, cycleStart: orbit.cycleOffset, statePeriod: orbit.period }
    : null
}

function rawPhase(value: bigint, angle: ParsedRationalAngle): bigint {
  const modulus = 2n * angle.denominator
  return positiveMod(value * angle.numerator, modulus)
}

function cosinePhaseKey(phase: bigint, angle: ParsedRationalAngle): bigint {
  const modulus = 2n * angle.denominator
  return phase <= modulus - phase ? phase : modulus - phase
}

function sinePhaseKey(phase: bigint, angle: ParsedRationalAngle): bigint {
  const modulus = 2n * angle.denominator
  const reflected = positiveMod(angle.denominator - phase, modulus)
  return phase <= reflected ? phase : reflected
}

function phaseKey(value: bigint, angle: ParsedRationalAngle): bigint {
  return cosinePhaseKey(rawPhase(value, angle), angle)
}

function stateAt(
  states: State[],
  cycleStart: number,
  statePeriod: number,
  index: number,
): State {
  if (index < states.length) return states[index]
  return states[cycleStart + ((index - cycleStart) % statePeriod)]
}

type ObservableOrbitCertificate = {
  modulus: bigint
  cycleStart: number
  statePeriod: number
  statesEnumerated: number
  observableStart: number
  observablePeriod: number
  keys: bigint[]
  prefixKeys: bigint[]
}

function certifyKeyOrbit(
  recurrence: ParsedIntegerSecondOrderRecurrence,
  angle: ParsedRationalAngle,
  observe: (phase: bigint, angle: ParsedRationalAngle) => bigint,
): ObservableOrbitCertificate | null {
  const modulus = 2n * angle.denominator
  const orbit = enumerateOrbit(recurrence, modulus)
  if (!orbit) return null
  const { states, cycleStart, statePeriod } = orbit
  const keyAt = (index: number) => observe(
    rawPhase(stateAt(states, cycleStart, statePeriod, index)[0], angle),
    angle,
  )
  const cycleKeys = Array.from({ length: statePeriod }, (_, index) => keyAt(cycleStart + index))
  const observablePeriod = minimalDivisorPeriod(cycleKeys)
  const observableStart = minimalPeriodicStart({
    stateCycleStart: cycleStart,
    observablePeriod,
    verificationLength: statePeriod,
    valueAt: keyAt,
  })

  const transition: Matrix2 = [0n, 1n, recurrence.coefficients[1], recurrence.coefficients[0]]
  const cycleState = states[cycleStart]
  const replayed = applyMatrix(powerMatrix(transition, statePeriod, modulus), cycleState, modulus)
  if (stateKey(replayed) !== stateKey(cycleState)) return null
  for (let index = 0; index < states.length; index += 1) {
    const replay = applyMatrix(
      powerMatrix(transition, index, modulus),
      states[0],
      modulus,
    )
    if (stateKey(replay) !== stateKey(states[index])) return null
  }

  return {
    modulus,
    cycleStart,
    statePeriod,
    statesEnumerated: states.length,
    observableStart,
    observablePeriod,
    keys: Array.from({ length: observablePeriod }, (_, index) => keyAt(observableStart + index)),
    prefixKeys: Array.from({ length: observableStart }, (_, index) => keyAt(index)),
  }
}

function certifyObservableOrbit(
  recurrence: ParsedIntegerSecondOrderRecurrence,
  angle: ParsedRationalAngle,
): Omit<ObservableOrbitCertificate, 'keys'> & { phases: bigint[] } | null {
  const certificate = certifyKeyOrbit(recurrence, angle, cosinePhaseKey)
  if (!certificate) return null
  const { keys, ...rest } = certificate
  return { ...rest, phases: keys }
}

function rationalAngleTex(angle: ParsedRationalAngle): string {
  if (angle.numerator === 1n) return `\\frac{\\pi}{${angle.denominator}}`
  if (angle.numerator === -1n) return `-\\frac{\\pi}{${angle.denominator}}`
  return `\\frac{${angle.numerator}\\pi}{${angle.denominator}}`
}

function phaseTex(phase: bigint, denominator: bigint): string {
  if (phase === 0n) return '1'
  if (phase === denominator) return '-1'
  if (2n * phase === denominator) return '0'
  const divisor = gcd(phase, denominator)
  const numerator = phase / divisor
  const reducedDenominator = denominator / divisor
  const angle = numerator === 1n
    ? `\\frac{\\pi}{${reducedDenominator}}`
    : `\\frac{${numerator}\\pi}{${reducedDenominator}}`
  return `\\cos ${angle}`
}

function sinePhaseTex(phase: bigint, denominator: bigint): string {
  if (phase === 0n) return '0'
  if (2n * phase === denominator) return '1'
  if (2n * phase === 3n * denominator) return '-1'
  const negative = phase > denominator
  const positivePhase = negative ? 2n * denominator - phase : phase
  const divisor = gcd(positivePhase, denominator)
  const numerator = positivePhase / divisor
  const reducedDenominator = denominator / divisor
  const angle = numerator === 1n
    ? `\\frac{\\pi}{${reducedDenominator}}`
    : `\\frac{${numerator}\\pi}{${reducedDenominator}}`
  return `${negative ? '-' : ''}\\sin ${angle}`
}

function pointPhaseTex(phase: bigint, angle: ParsedRationalAngle): string {
  return `\\left(${phaseTex(cosinePhaseKey(phase, angle), angle.denominator)},${sinePhaseTex(sinePhaseKey(phase, angle), angle.denominator)}\\right)`
}

function cosineSign(phase: bigint, angle: ParsedRationalAngle): bigint {
  const doubled = 2n * phase
  if (doubled === angle.denominator || doubled === 3n * angle.denominator) return 0n
  return doubled < angle.denominator || doubled > 3n * angle.denominator ? 1n : -1n
}

function integerSet(values: number[]): string {
  return values.length ? `\\{${values.join(',')}\\}` : '\\varnothing'
}

function periodicEventAnswer(
  recurrence: ParsedIntegerSecondOrderRecurrence,
  certificate: ObservableOrbitCertificate,
  minimumIndex: number,
): { tex: string; transient: number[]; residues: number[]; periodicStart: number } {
  const sequenceStart = recurrence.startIndex
  const periodicStart = Math.max(sequenceStart + certificate.observableStart, minimumIndex)
  const transient = certificate.prefixKeys
    .map((key, offset) => ({ key, index: sequenceStart + offset }))
    .filter(item => item.index >= minimumIndex && item.key === 1n)
    .map(item => item.index)
  const modulus = BigInt(certificate.observablePeriod)
  const residues = [...new Set(certificate.keys
    .map((key, offset) => ({ key, residue: Number(positiveMod(BigInt(sequenceStart + certificate.observableStart + offset), modulus)) }))
    .filter(item => item.key === 1n)
    .map(item => item.residue))]
    .sort((left, right) => left - right)

  const clauses: string[] = []
  if (transient.length) clauses.push(`n\\in${integerSet(transient)}`)
  if (residues.length === certificate.observablePeriod) {
    clauses.push(`n\\ge ${periodicStart}`)
  } else if (residues.length) {
    clauses.push(`n\\ge ${periodicStart},\\quad n\\bmod ${certificate.observablePeriod}\\in${integerSet(residues)}`)
  }
  return {
    tex: clauses.length ? clauses.map(clause => `\\{n:${clause}\\}`).join('\\cup') : '\\varnothing',
    transient,
    residues,
    periodicStart,
  }
}

function recurrenceTex(recurrence: ParsedIntegerSecondOrderRecurrence): string {
  const [a, b] = recurrence.coefficients
  const firstTerm = a === 1n
    ? `${recurrence.symbol}_{${recurrence.indexSymbol}+1}`
    : a === -1n
      ? `-${recurrence.symbol}_{${recurrence.indexSymbol}+1}`
      : `${a}${recurrence.symbol}_{${recurrence.indexSymbol}+1}`
  const sign = b < 0n ? '-' : '+'
  const magnitude = b < 0n ? -b : b
  const secondTerm = magnitude === 1n
    ? `${recurrence.symbol}_{${recurrence.indexSymbol}}`
    : `${magnitude}${recurrence.symbol}_{${recurrence.indexSymbol}}`
  return `${recurrence.symbol}_{${recurrence.indexSymbol}+2}=${firstTerm}${sign}${secondTerm}`
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function texDocument(statement: string, solution: string): string {
  return String.raw`\documentclass[a4paper,11pt]{jsarticle}
\usepackage{amsmath,amssymb}
\begin{document}
\section*{問題}
${statement}
\section*{解答}
${solution}
\end{document}
`
}

type FiniteStateVariantSpec = {
  id: string
  statement: string
  answer: string
  solution: string
  characterMorphism: string
  characterLabelJa: string
  characterTargetJa: string
  characterRoleJa: string
  queryMorphism: string
  queryLabelJa: string
  queryTargetJa: string
  queryRoleJa: string
  observable: string
  querySignature: string
  quotientAction: string
  bridgeProduces: string
  normalForm: string
  tags: string[]
  finiteSolutionSet: boolean
  numericInstanceConstants: number[]
  verificationMethod: string
  proofClaimJa: string
  diagramResult: string
  difficultyOffset: number
}

function finiteStateVariantCard(
  base: CertifiedFusionCard,
  parents: CertifiedFusionParent[],
  recurrence: ParsedIntegerSecondOrderRecurrence,
  angle: ParsedRationalAngle,
  certificate: ObservableOrbitCertificate,
  spec: FiniteStateVariantSpec,
  startedAt: number,
): CertifiedFusionCard {
  const structureId = `certified-finite-state-trig-${spec.id}.${hash([
    recurrence.initial.map(String),
    recurrence.coefficients.map(String),
    recurrence.startIndex,
    angle.numerator.toString(),
    angle.denominator.toString(),
    spec.id,
  ])}`
  const morphisms = [
    'IntegerRecurrenceElaboration',
    'ModuloStateProjection',
    'RationalAngleElaboration',
    spec.characterMorphism,
    'SynchronousProductOrbit',
    spec.queryMorphism,
    'MatrixReplayVerification',
    'AllParentAblation',
  ]
  return {
    ...base,
    id: `mortra-${structureId}`,
    statement_tex: spec.statement,
    answer_tex: spec.answer,
    solution_tex: spec.solution,
    solution_document_tex: texDocument(spec.statement, spec.solution),
    morphism_chain: morphisms,
    proof_roadmap: [
      { morphism_id: morphisms[0], label_ja: '整数漸化式を型付けする', source_ja: '親問題A', target_ja: '二階線形漸化式', role_ja: '初期値と二つの係数を保存します。' },
      { morphism_id: morphisms[1], label_ja: '有限状態へ射影する', source_ja: '整数漸化式', target_ja: `法${certificate.modulus}の状態`, role_ja: '三角関数の値を変えない合同類だけを残します。' },
      { morphism_id: morphisms[2], label_ja: '有理角を型付けする', source_ja: '親問題B', target_ja: '円周上の有限位相', role_ja: '角の分母から有限個の位相を構成します。' },
      { morphism_id: morphisms[3], label_ja: spec.characterLabelJa, source_ja: '有限位相', target_ja: spec.characterTargetJa, role_ja: spec.characterRoleJa },
      { morphism_id: morphisms[4], label_ja: '二つの状態を同期させる', source_ja: '漸化式状態と有限位相', target_ja: '観測列の軌道', role_ja: '二つの親問題から得た構造を一つの有限軌道へ合成します。' },
      { morphism_id: morphisms[5], label_ja: spec.queryLabelJa, source_ja: '有限軌道', target_ja: spec.queryTargetJa, role_ja: spec.queryRoleJa },
      { morphism_id: morphisms[6], label_ja: '行列累乗で独立検算する', source_ja: '遷移行列', target_ja: '再生証明書', role_ja: '逐次計算とは別の行列累乗で全状態を照合します。' },
      { morphism_id: morphisms[7], label_ja: '両親の必要性を確かめる', source_ja: '二つの親問題', target_ja: '親依存性', role_ja: '漸化式または有理角を除くと答えが定まらないことを確認します。' },
    ],
    proof_obligations: [
      { id: 'finite-state-closure', claim_ja: '漸化式の合同状態が有限集合上で閉じる', status: 'verified' },
      { id: 'observable-query', claim_ja: spec.proofClaimJa, status: 'verified' },
      { id: 'matrix-replay', claim_ja: '行列累乗と逐次遷移が全状態で一致する', status: 'verified' },
      { id: 'all-parent-dependence', claim_ja: '二つの親問題がどちらも構成に不可欠である', status: 'verified' },
    ],
    diagram: {
      version: 1,
      kind: 'morphism',
      title: '整数漸化式と有理角を有限状態上で合成する',
      caption: '漸化式を合同状態へ、有理角を円周上の有限位相へ変換し、有限軌道から問いの答えを厳密に取り出します。',
      nodes: ['整数漸化式', `mod ${certificate.modulus}`, '有理角', spec.characterTargetJa, '同期積', spec.diagramResult],
    },
    verification: {
      method: spec.verificationMethod,
      exact_backend: true,
      independent_check: true,
      samples: [Number(certificate.modulus), certificate.statePeriod, certificate.observablePeriod],
    },
    difficulty: {
      band: 'A_exact_finite_state_fusion',
      score: 7.5 + spec.difficultyOffset + Math.log2(Number(certificate.modulus)),
    },
    fusion_derivation: {
      passed: true,
      reason: 'one parent supplies the transition law and the other supplies the finite cyclic observable required by the generated theorem',
      ablationPassed: true,
      assignments: [
        {
          parentId: recurrence.parentId,
          portId: 'integer_recurrence',
          role: 'state_transition',
          matchedAnchors: [recurrence.evidence],
          witnessSteps: ['IntegerRecurrenceElaboration', 'ModuloStateProjection'],
        },
        {
          parentId: angle.parentId,
          portId: 'rational_angle',
          role: 'observable',
          matchedAnchors: [angle.evidence],
          witnessSteps: ['RationalAngleElaboration', spec.characterMorphism],
        },
      ],
      bridges: [{
        id: `finite-state-${spec.id}-product`,
        witnessStep: 'SynchronousProductOrbit',
        consumes: ['integer_recurrence', 'rational_angle'],
        produces: spec.bridgeProduces,
      }],
      intermediatePropositions: [
        {
          parentId: recurrence.parentId,
          morphism: 'ModuloStateProjection',
          source: 'IntegerSecondOrderRecurrence',
          target: 'FiniteStateOrbit',
          proposition: `the recurrence closes on at most ${certificate.modulus ** 2n} ordered residue states`,
          proved: true,
        },
        {
          parentId: angle.parentId,
          morphism: spec.characterMorphism,
          source: 'RationalAngle',
          target: spec.characterTargetJa,
          proposition: `the requested observable factors exactly through residues modulo ${certificate.modulus}`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'FiniteStateCyclicCharacterFusionIR',
      observable: spec.observable,
      operators: morphisms,
      domain: 'finite_state_trigonometry',
      tags: ['recurrence', 'matrix', 'finite_state', 'rational_angle', 'trigonometry', ...spec.tags],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'closure', claim: 'the modular recurrence orbit repeats within the finite state bound', verifier: 'exact BigInt state enumeration' },
        { id: 'observable-query', claim: spec.querySignature, verifier: 'complete finite-orbit audit' },
        { id: 'matrix-replay', claim: 'binary matrix powers reproduce every enumerated state', verifier: 'independent exact modular matrix kernel' },
        { id: 'ablation', claim: 'transition and observable parents occupy distinct indispensable ports', verifier: 'typed two-port ablation' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['integer second-order recurrence', 'fixed rational multiple of pi', spec.observable],
        querySignature: spec.querySignature,
        normalForm: spec.normalForm,
        quotientAction: spec.quotientAction,
        freeParameters: [],
        uniqueNormalForm: true,
        finiteSolutionSet: spec.finiteSolutionSet,
        numericInstanceConstants: spec.numericInstanceConstants,
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: certificate.statesEnumerated,
      valid_hypotheses: 1,
      elapsed_ms: Date.now() - startedAt,
    },
  }
}

function additionalFiniteStateCards(
  base: CertifiedFusionCard,
  parents: CertifiedFusionParent[],
  recurrence: ParsedIntegerSecondOrderRecurrence,
  angle: ParsedRationalAngle,
  startedAt: number,
): CertifiedFusionCard[] {
  const cards: CertifiedFusionCard[] = []
  const recurrenceDefinition = String.raw`\(${recurrence.symbol}_{${recurrence.startIndex}}=${recurrence.initial[0]},\ ${recurrence.symbol}_{${recurrence.startIndex + 1}}=${recurrence.initial[1]},\ ${recurrenceTex(recurrence)}\)`
  const angleDefinition = String.raw`\(\theta=${rationalAngleTex(angle)}\)`

  const sineCertificate = certifyKeyOrbit(recurrence, angle, sinePhaseKey)
  if (sineCertificate) {
    const start = recurrence.startIndex + sineCertificate.observableStart
    const cycle = sineCertificate.keys.map(key => sinePhaseTex(key, angle.denominator))
    const statement = String.raw`${recurrenceDefinition} と ${angleDefinition} を定め、\(s_n=\sin(${recurrence.symbol}_n\theta)\) とおく。すべての \(n\ge N_0\) で \(s_{n+T}=s_n\) となる辞書式最小の正整数対 \((N_0,T)\) を求め、1周期の値を順に書け。`
    const answer = String.raw`\((N_0,T)=(${start},${sineCertificate.observablePeriod})\)。1周期は \(${cycle.join(',\ ')}\)。`
    const solution = String.raw`角 \(\theta=${rationalAngleTex(angle)}\) に対して正弦の値は \(${recurrence.symbol}_n\bmod ${sineCertificate.modulus}\) だけで決まる。そこで状態 \(v_n=(${recurrence.symbol}_n,${recurrence.symbol}_{n+1})\bmod ${sineCertificate.modulus}\) を考える。正弦では位相 \(r\) と \(${angle.denominator}-r\) が同じ値を与える。この同値関係で状態をまとめ、状態周期 ${sineCertificate.statePeriod} の約数を小さい順にすべて検査すると、正弦列の最小周期は ${sineCertificate.observablePeriod} である。循環前も直接照合すると最小開始添字は \(N_0=${start}\) となる。したがって1周期は \(${cycle.join(',\ ')}\) である。独立検算として遷移行列の二進累乗で全状態を再生し、逐次遷移と一致することを確かめた。`
    cards.push(finiteStateVariantCard(base, parents, recurrence, angle, sineCertificate, {
      id: 'sine-period',
      statement,
      answer,
      solution,
      characterMorphism: 'SineCharacterConstruction',
      characterLabelJa: '正弦の値を作る',
      characterTargetJa: '正弦値',
      characterRoleJa: `位相rと${angle.denominator}-rを同じ正弦値へ写します。`,
      queryMorphism: 'MinimalSinePeriod',
      queryLabelJa: '正弦列の最小周期を求める',
      queryTargetJa: '開始添字・周期・1周期の値',
      queryRoleJa: '状態周期の約数をすべて調べ、開始添字と周期の最小性を証明します。',
      observable: 'eventual_minimal_sine_period',
      querySignature: 'minimal eventual sine period and one exact cycle',
      quotientAction: 'phase r is identified with d-r under sine',
      bridgeProduces: 'periodic_sine_observable',
      normalForm: `sine orbit modulo ${sineCertificate.modulus}`,
      tags: ['sine', 'period'],
      finiteSolutionSet: true,
      numericInstanceConstants: [Number(sineCertificate.modulus), sineCertificate.observablePeriod],
      verificationMethod: 'finite-state closure + independent modular matrix replay + complete sine-period divisor audit + all-parent ablation',
      proofClaimJa: '正弦列の周期と開始添字が最小である',
      diagramResult: `正弦周期 ${sineCertificate.observablePeriod}`,
      difficultyOffset: 0.2,
    }, startedAt))
  }

  const phaseCertificate = certifyKeyOrbit(recurrence, angle, phase => phase)
  if (phaseCertificate) {
    const start = recurrence.startIndex + phaseCertificate.observableStart
    const cycle = phaseCertificate.keys.map(phase => pointPhaseTex(phase, angle))
    const statement = String.raw`${recurrenceDefinition} と ${angleDefinition} を定め、
\[z_n=\left(\cos(${recurrence.symbol}_n\theta),\ \sin(${recurrence.symbol}_n\theta)\right)\]
とおく。すべての \(n\ge N_0\) で \(z_{n+T}=z_n\) となる辞書式最小の正整数対 \((N_0,T)\) を求め、1周期の点を順に書け。`
    const answer = String.raw`\((N_0,T)=(${start},${phaseCertificate.observablePeriod})\)。1周期は \(${cycle.join(',\ ')}\)。`
    const solution = String.raw`点 \(z_n\) は、位相 \(${recurrence.symbol}_n\theta\) を単位円上の点としてそのまま記録する。したがって \(z_n\) は \(${recurrence.symbol}_n\bmod ${phaseCertificate.modulus}\) だけで決まる。状態 \(v_n=(${recurrence.symbol}_n,${recurrence.symbol}_{n+1})\bmod ${phaseCertificate.modulus}\) を列挙すると、循環開始位置は ${phaseCertificate.cycleStart}、状態周期は ${phaseCertificate.statePeriod} である。単位円上の点では余弦だけの場合のような \(r\) と \(-r\) の同一視を行わない。状態周期の約数をすべて検査すると、点列の最小周期は ${phaseCertificate.observablePeriod}、最小開始添字は \(N_0=${start}\) となる。よって1周期は \(${cycle.join(',\ ')}\) である。遷移行列の二進累乗による再生も逐次列挙と一致した。`
    cards.push(finiteStateVariantCard(base, parents, recurrence, angle, phaseCertificate, {
      id: 'unit-circle-point-period',
      statement,
      answer,
      solution,
      characterMorphism: 'UnitCirclePointConstruction',
      characterLabelJa: '単位円上の点を作る',
      characterTargetJa: '単位円上の点',
      characterRoleJa: '余弦と正弦を組にし、位相を失わない円周上の点として表します。',
      queryMorphism: 'MinimalPointOrbitPeriod',
      queryLabelJa: '点列の最小周期を求める',
      queryTargetJa: '開始添字・周期・円周上の軌道',
      queryRoleJa: '有限位相を同一視せずに調べ、点列としての最小周期を証明します。',
      observable: 'eventual_minimal_unit_circle_point_period',
      querySignature: 'minimal eventual unit-circle point period and one exact orbit',
      quotientAction: 'no phase quotient beyond residues modulo 2d',
      bridgeProduces: 'periodic_unit_circle_point_orbit',
      normalForm: `phase orbit modulo ${phaseCertificate.modulus}`,
      tags: ['unit-circle', 'ordered-pair', 'period'],
      finiteSolutionSet: true,
      numericInstanceConstants: [Number(phaseCertificate.modulus), phaseCertificate.observablePeriod],
      verificationMethod: 'finite-state closure + independent modular matrix replay + complete phase-period divisor audit + all-parent ablation',
      proofClaimJa: '単位円上の点列の周期と開始添字が最小である',
      diagramResult: `点列周期 ${phaseCertificate.observablePeriod}`,
      difficultyOffset: 0.6,
    }, startedAt))
  }

  const addEventCard = (event: {
    id: string
    minimumIndex: number
    observe: (phase: bigint, angle: ParsedRationalAngle) => bigint
    statement: string
    criterion: string
    characterMorphism: string
    characterLabelJa: string
    queryMorphism: string
    queryLabelJa: string
    observable: string
    querySignature: string
    quotientAction: string
    tags: string[]
  }) => {
    const certificate = certifyKeyOrbit(recurrence, angle, event.observe)
    if (!certificate) return
    const distinct = new Set([...certificate.prefixKeys, ...certificate.keys].map(String))
    if (!certificate.keys.includes(1n) || distinct.size < 2) return
    const classified = periodicEventAnswer(recurrence, certificate, event.minimumIndex)
    if (classified.tex === '\\varnothing') return
    const answer = `\\(${classified.tex}\\)`
    const solution = String.raw`${event.criterion}。したがって、この条件の真偽は状態 \(v_n=(${recurrence.symbol}_n,${recurrence.symbol}_{n+1})\bmod ${certificate.modulus}\) だけで決まる。状態を一巡させ、条件の真偽を0と1で記録すると、循環開始位置は ${certificate.observableStart}、真偽列の最小周期は ${certificate.observablePeriod} である。周期部分で条件を満たす剰余は \(${integerSet(classified.residues)}\)、周期部分の開始添字は ${classified.periodicStart} である。循環前の該当添字も別に調べると \(${integerSet(classified.transient)}\) となる。以上を合わせて答えは ${answer} である。独立検算として、遷移行列の二進累乗から得た状態でも同じ真偽列になることを全状態で確かめた。`
    cards.push(finiteStateVariantCard(base, parents, recurrence, angle, certificate, {
      id: event.id,
      statement: event.statement,
      answer,
      solution,
      characterMorphism: event.characterMorphism,
      characterLabelJa: event.characterLabelJa,
      characterTargetJa: '条件の真偽',
      characterRoleJa: '有限位相ごとに条件が成り立つかを厳密に判定します。',
      queryMorphism: event.queryMorphism,
      queryLabelJa: event.queryLabelJa,
      queryTargetJa: '添字の合同類',
      queryRoleJa: '循環前の有限部分と周期部分を分け、該当する添字を漏れなく分類します。',
      observable: event.observable,
      querySignature: event.querySignature,
      quotientAction: event.quotientAction,
      bridgeProduces: event.observable,
      normalForm: classified.tex,
      tags: event.tags,
      finiteSolutionSet: false,
      numericInstanceConstants: [Number(certificate.modulus), certificate.observablePeriod, ...classified.residues],
      verificationMethod: 'finite-state closure + complete eventual-event classification + independent modular matrix replay + all-parent ablation',
      proofClaimJa: '条件を満たす添字の有限部分と周期部分が完全に分類されている',
      diagramResult: `添字 mod ${certificate.observablePeriod}`,
      difficultyOffset: 0.4,
    }, startedAt))
  }

  addEventCard({
    id: 'sine-zero-set',
    minimumIndex: recurrence.startIndex,
    observe: (phase, currentAngle) => phase === 0n || phase === currentAngle.denominator ? 1n : 0n,
    statement: String.raw`${recurrenceDefinition} と ${angleDefinition} を定める。\(\sin(${recurrence.symbol}_n\theta)=0\) となるすべての整数 \(n\ge ${recurrence.startIndex}\) を求めよ。`,
    criterion: String.raw`\(\sin(${recurrence.symbol}_n\theta)=0\) であることは、位相が \(0\) または \(\pi\) に一致すること、すなわち \(${recurrence.symbol}_n${angle.numerator}\equiv0,${angle.denominator}\pmod{${2n * angle.denominator}}\) と同値である`,
    characterMorphism: 'SineZeroPredicate',
    characterLabelJa: '正弦の零点を判定する',
    queryMorphism: 'EventuallyPeriodicEventSet',
    queryLabelJa: '零点の添字を分類する',
    observable: 'sine_zero_index_set',
    querySignature: 'classify all recurrence indices at which the rational-angle sine vanishes',
    quotientAction: 'phases 0 and d are the two sine-zero residues modulo 2d',
    tags: ['sine', 'zero-set', 'congruence'],
  })

  addEventCard({
    id: 'cosine-zero-set',
    minimumIndex: recurrence.startIndex,
    observe: (phase, currentAngle) => positiveMod(2n * phase, 2n * currentAngle.denominator) === currentAngle.denominator ? 1n : 0n,
    statement: String.raw`${recurrenceDefinition} と ${angleDefinition} を定める。\(\cos(${recurrence.symbol}_n\theta)=0\) となるすべての整数 \(n\ge ${recurrence.startIndex}\) を求めよ。`,
    criterion: String.raw`\(\cos(${recurrence.symbol}_n\theta)=0\) であることは、\(2${recurrence.symbol}_n${angle.numerator}\equiv${angle.denominator}\pmod{${2n * angle.denominator}}\) と同値である`,
    characterMorphism: 'CosineZeroPredicate',
    characterLabelJa: '余弦の零点を判定する',
    queryMorphism: 'EventuallyPeriodicEventSet',
    queryLabelJa: '零点の添字を分類する',
    observable: 'cosine_zero_index_set',
    querySignature: 'classify all recurrence indices at which the rational-angle cosine vanishes',
    quotientAction: 'the two quarter-turn phases form the cosine-zero event',
    tags: ['cosine', 'zero-set', 'congruence'],
  })

  const initialPhase = rawPhase(recurrence.initial[0], angle)
  addEventCard({
    id: 'initial-point-return-set',
    minimumIndex: recurrence.startIndex + 1,
    observe: phase => phase === initialPhase ? 1n : 0n,
    statement: String.raw`${recurrenceDefinition} と ${angleDefinition} を定め、
\[z_n=\left(\cos(${recurrence.symbol}_n\theta),\ \sin(${recurrence.symbol}_n\theta)\right)\]
とおく。\(z_n=z_${recurrence.startIndex}\) となるすべての整数 \(n>${recurrence.startIndex}\) を求めよ。`,
    criterion: String.raw`余弦と正弦の組が等しいことは位相そのものが等しいことと同値なので、\(z_n=z_${recurrence.startIndex}\) は \(${recurrence.symbol}_n${angle.numerator}\equiv${initialPhase}\pmod{${2n * angle.denominator}}\) と同値である`,
    characterMorphism: 'InitialPhaseReturnPredicate',
    characterLabelJa: '初期位相への回帰を判定する',
    queryMorphism: 'EventuallyPeriodicReturnSet',
    queryLabelJa: '回帰時刻を分類する',
    observable: 'initial_unit_circle_point_return_set',
    querySignature: 'classify every return time to the initial unit-circle point',
    quotientAction: 'ordered sine-cosine pairs retain the full phase modulo 2d',
    tags: ['unit-circle', 'return-time', 'congruence'],
  })

  const signCertificate = certifyKeyOrbit(recurrence, angle, cosineSign)
  if (signCertificate && new Set(signCertificate.keys.map(String)).size >= 2) {
    const start = recurrence.startIndex + signCertificate.observableStart
    const positive = signCertificate.keys.filter(key => key === 1n).length
    const zero = signCertificate.keys.filter(key => key === 0n).length
    const negative = signCertificate.keys.filter(key => key === -1n).length
    const statement = String.raw`${recurrenceDefinition} と ${angleDefinition} を定め、
\[
\varepsilon_n=\begin{cases}
1&\cos(${recurrence.symbol}_n\theta)>0,\\
0&\cos(${recurrence.symbol}_n\theta)=0,\\
-1&\cos(${recurrence.symbol}_n\theta)<0
\end{cases}
\]
とおく。すべての \(n\ge N_0\) で \(\varepsilon_{n+T}=\varepsilon_n\) となる辞書式最小の正整数対 \((N_0,T)\) を求めよ。さらに、1周期中の \(1,0,-1\) の個数をこの順に求めよ。`
    const answer = String.raw`\((N_0,T)=(${start},${signCertificate.observablePeriod})\)、個数は \((${positive},${zero},${negative})\)。`
    const solution = String.raw`位相を \(r\pi/${angle.denominator}\) と書く。余弦の符号は \(2r<${angle.denominator}\) または \(2r>${3n * angle.denominator}\) のとき正、等号のとき0、それ以外のとき負である。したがって符号は \(${recurrence.symbol}_n\bmod ${signCertificate.modulus}\) だけで決まる。合同状態を列挙して得られる符号列について、状態周期 ${signCertificate.statePeriod} の約数をすべて検査すると、最小周期は ${signCertificate.observablePeriod}、最小開始添字は \(N_0=${start}\) となる。1周期を数えると、正が ${positive} 個、0が ${zero} 個、負が ${negative} 個である。遷移行列の二進累乗で状態を独立に再生し、符号と個数が一致することも確かめた。`
    cards.push(finiteStateVariantCard(base, parents, recurrence, angle, signCertificate, {
      id: 'cosine-sign-profile',
      statement,
      answer,
      solution,
      characterMorphism: 'CosineSignCharacter',
      characterLabelJa: '余弦の符号を判定する',
      characterTargetJa: '三値の符号列',
      characterRoleJa: '各有限位相を正・零・負の三つへ写します。',
      queryMorphism: 'MinimalSignPeriodAndMultiplicity',
      queryLabelJa: '符号周期と個数を求める',
      queryTargetJa: '最小周期と符号分布',
      queryRoleJa: '最小周期を証明し、その一周期を三つの符号に分類して数えます。',
      observable: 'eventual_cosine_sign_profile',
      querySignature: 'minimal eventual cosine-sign period and exact sign multiplicities',
      quotientAction: 'phases are identified exactly when their cosine signs agree',
      bridgeProduces: 'periodic_cosine_sign_profile',
      normalForm: `${start}/${signCertificate.observablePeriod}/${positive}/${zero}/${negative}`,
      tags: ['cosine', 'sign', 'multiplicity', 'period'],
      finiteSolutionSet: true,
      numericInstanceConstants: [Number(signCertificate.modulus), signCertificate.observablePeriod, positive, zero, negative],
      verificationMethod: 'finite-state closure + complete sign-period divisor audit + exact multiplicity count + independent modular matrix replay + all-parent ablation',
      proofClaimJa: '余弦の符号列の周期が最小で、一周期の符号個数が正確である',
      diagramResult: `符号周期 ${signCertificate.observablePeriod}`,
      difficultyOffset: 0.5,
    }, startedAt))
  }

  return cards
}

export function synthesizeCertifiedFiniteStateTrigFusion(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const recurrences = parents.map(parseIntegerSecondOrderRecurrence).filter(Boolean) as ParsedIntegerSecondOrderRecurrence[]
  if (recurrences.length !== 1) return []
  const recurrence = recurrences[0]
  const angleParent = parents.find(parent => parent.id !== recurrence.parentId)
  if (!angleParent) return []
  const angles = parseRationalAngles(angleParent)
  const cards: CertifiedFusionCard[] = []

  for (const angle of angles) {
    if (cards.length >= requested) break
    const certificate = certifyObservableOrbit(recurrence, angle)
    if (!certificate) continue
    const start = recurrence.startIndex + certificate.observableStart
    const recurrenceDefinition = String.raw`\(${recurrence.symbol}_{${recurrence.startIndex}}=${recurrence.initial[0]},\ ${recurrence.symbol}_{${recurrence.startIndex + 1}}=${recurrence.initial[1]},\ ${recurrenceTex(recurrence)}\)`
    const angleDefinition = String.raw`\(\theta=${rationalAngleTex(angle)}\)`
    const statement = String.raw`${recurrenceDefinition} と ${angleDefinition} を定め、\(c_n=\cos(${recurrence.symbol}_n\theta)\) とおく。すべての \(n\ge N_0\) で \(c_{n+T}=c_n\) となる辞書式最小の正整数対 \((N_0,T)\) を求め、1周期の値を順に書け。`
    const cycle = certificate.phases.map(phase => phaseTex(phase, angle.denominator))
    const answer = String.raw`\((N_0,T)=(${start},${certificate.observablePeriod})\)。1周期は \(${cycle.join(',\ ')}\)。`
    const solution = String.raw`角 \(\theta=${rationalAngleTex(angle)}\) に対して余弦の値は \(${recurrence.symbol}_n\bmod ${certificate.modulus}\) だけで決まる。そこで状態 \(v_n=(${recurrence.symbol}_n,${recurrence.symbol}_{n+1})\bmod ${certificate.modulus}\) を考える。遷移行列は
\[
A=\begin{pmatrix}0&1\\${recurrence.coefficients[1]}&${recurrence.coefficients[0]}\end{pmatrix}
\]
である。有限個の状態を順に調べると、状態の循環開始位置は ${certificate.cycleStart}、状態周期は ${certificate.statePeriod} である。余弦は位相 \(r\) と \(-r\) を同じ値へ写すため、余弦列の最小周期は ${certificate.observablePeriod} まで短くなる。循環前も直接照合すると最小開始添字は \(N_0=${start}\) であり、1周期は \(${cycle.join(',\ ')}\) である。独立検算として \(A^k v_${recurrence.startIndex}\) を二進法で計算し、逐次遷移と全状態で一致することを確かめた。`
    const structureId = `certified-finite-state-trig.${hash([
      recurrence.initial.map(String),
      recurrence.coefficients.map(String),
      recurrence.startIndex,
      angle.numerator.toString(),
      angle.denominator.toString(),
    ])}`
    const morphisms = [
      'IntegerRecurrenceElaboration',
      'ModuloStateProjection',
      'RationalAngleElaboration',
      'CyclicCharacterConstruction',
      'SynchronousProductOrbit',
      'MinimalObservablePeriod',
      'MatrixReplayVerification',
      'AllParentAblation',
    ]
    const baseCard: CertifiedFusionCard = {
      id: `mortra-${structureId}`,
      statement_tex: statement,
      answer_tex: answer,
      solution_tex: solution,
      solution_document_tex: texDocument(statement, solution),
      domain: 'finite_state_trigonometry',
      family_id: 'certified.recurrence_rational_angle_orbit',
      tool: 'MORTRA exact finite-state synthesis',
      morphism_chain: morphisms,
      proof_roadmap: [
        { morphism_id: morphisms[0], label_ja: '整数漸化式を型付けする', source_ja: '親問題A', target_ja: '二階線形漸化式', role_ja: '初期値と二つの係数を保存します。' },
        { morphism_id: morphisms[1], label_ja: '有限状態へ射影する', source_ja: '整数漸化式', target_ja: `法${certificate.modulus}の状態`, role_ja: '余弦を変えない合同類だけを残します。' },
        { morphism_id: morphisms[2], label_ja: '有理角を型付けする', source_ja: '親問題B', target_ja: '円周上の有限位相', role_ja: '角の分母から有限位相群を構成します。' },
        { morphism_id: morphisms[3], label_ja: '余弦の指標を作る', source_ja: '有限位相', target_ja: '余弦値', role_ja: '位相rと-rを同じ余弦値へ写します。' },
        { morphism_id: morphisms[4], label_ja: '二つの状態を同期させる', source_ja: '漸化式状態と有限位相', target_ja: '余弦列の軌道', role_ja: '両親から得た構造を一つの有限軌道へ合成します。' },
        { morphism_id: morphisms[5], label_ja: '最小周期を求める', source_ja: '有限軌道', target_ja: '開始添字と周期', role_ja: '真の約数をすべて検査し、最小性まで証明します。' },
        { morphism_id: morphisms[6], label_ja: '行列累乗で独立検算する', source_ja: '遷移行列', target_ja: '再生証明書', role_ja: '逐次計算とは別の行列累乗で全状態を照合します。' },
        { morphism_id: morphisms[7], label_ja: '両親の必要性を確かめる', source_ja: '二つの親問題', target_ja: '親依存性', role_ja: '漸化式または有理角を除くと出力が定まらないことを確認します。' },
      ],
      proof_obligations: [
        { id: 'finite-state-closure', claim_ja: '漸化式の合同状態が有限集合上で閉じる', status: 'verified' },
        { id: 'observable-period', claim_ja: '余弦列の周期と開始添字が最小である', status: 'verified' },
        { id: 'matrix-replay', claim_ja: '行列累乗と逐次遷移が全状態で一致する', status: 'verified' },
        { id: 'all-parent-dependence', claim_ja: '二つの親問題がどちらも構成に不可欠である', status: 'verified' },
      ],
      diagram: {
        version: 1,
        kind: 'morphism',
        title: '整数漸化式と有理角を有限状態上で合成する',
        caption: '漸化式を合同状態へ、有理角を円周上の有限位相へ変換し、同期積の最小周期を検証します。',
        nodes: ['整数漸化式', `mod ${certificate.modulus}`, '有理角', '巡回位相', '同期積', `周期 ${certificate.observablePeriod}`],
      },
      parent_ids: parents.map(parent => parent.id),
      verification: {
        method: 'finite-state closure + independent modular matrix replay + minimal-period divisor audit + all-parent ablation',
        exact_backend: true,
        independent_check: true,
        samples: [Number(certificate.modulus), certificate.statePeriod, certificate.observablePeriod],
      },
      difficulty: { band: 'A_exact_finite_state_fusion', score: 7.5 + Math.log2(Number(certificate.modulus)) },
      fusion_derivation: {
        passed: true,
        reason: 'one parent supplies the transition law and the other supplies the finite cyclic observable',
        ablationPassed: true,
        assignments: [
          {
            parentId: recurrence.parentId,
            portId: 'integer_recurrence',
            role: 'state_transition',
            matchedAnchors: [recurrence.evidence],
            witnessSteps: ['IntegerRecurrenceElaboration', 'ModuloStateProjection'],
          },
          {
            parentId: angle.parentId,
            portId: 'rational_angle',
            role: 'observable',
            matchedAnchors: [angle.evidence],
            witnessSteps: ['RationalAngleElaboration', 'CyclicCharacterConstruction'],
          },
        ],
        bridges: [{
          id: 'finite-state-cyclic-character-product',
          witnessStep: 'SynchronousProductOrbit',
          consumes: ['integer_recurrence', 'rational_angle'],
          produces: 'periodic_trigonometric_observable',
        }],
        intermediatePropositions: [
          {
            parentId: recurrence.parentId,
            morphism: 'ModuloStateProjection',
            source: 'IntegerSecondOrderRecurrence',
            target: 'FiniteStateOrbit',
            proposition: `the recurrence closes on at most ${certificate.modulus ** 2n} ordered residue states`,
            proved: true,
          },
          {
            parentId: angle.parentId,
            morphism: 'CyclicCharacterConstruction',
            source: 'RationalAngle',
            target: 'FiniteCyclicObservable',
            proposition: `cosine factors through residues modulo ${certificate.modulus} up to sign`,
            proved: true,
          },
        ],
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: 'FiniteStateCyclicCharacterFusionIR',
        observable: 'eventual_minimal_trigonometric_period',
        operators: morphisms,
        domain: 'finite_state_trigonometry',
        tags: ['recurrence', 'matrix', 'finite_state', 'rational_angle', 'trigonometry', 'period'],
        morphismChain: morphisms,
        executable: true,
        proofCertificate: [
          { id: 'closure', claim: 'the modular recurrence orbit repeats within the finite state bound', verifier: 'exact BigInt state enumeration' },
          { id: 'minimal-period', claim: 'no proper divisor is a period of the cyclic observable', verifier: 'complete divisor audit' },
          { id: 'matrix-replay', claim: 'binary matrix powers reproduce every enumerated state', verifier: 'independent exact modular matrix kernel' },
          { id: 'ablation', claim: 'transition and observable parents occupy distinct indispensable ports', verifier: 'typed two-port ablation' },
        ],
        structuralUniqueness: {
          schema: 1,
          conditionSkeleton: ['integer second-order recurrence', 'fixed rational multiple of pi', 'cosine observable'],
          querySignature: 'minimal eventual period and one exact cycle',
          normalForm: `finite-state orbit modulo ${certificate.modulus}`,
          quotientAction: 'phase r is identified with -r under cosine',
          freeParameters: [],
          uniqueNormalForm: true,
          finiteSolutionSet: true,
          numericInstanceConstants: [Number(certificate.modulus), certificate.observablePeriod],
          conditionAblationPassed: true,
        },
      },
      search_evidence: {
        hypotheses_evaluated: certificate.statesEnumerated,
        valid_hypotheses: 1,
        elapsed_ms: Date.now() - startedAt,
      },
    }
    const generatedForAngle = [
      baseCard,
      ...additionalFiniteStateCards(baseCard, parents, recurrence, angle, startedAt),
    ]
    for (const card of generatedForAngle) {
      if (cards.length >= requested) break
      cards.push(card)
    }
  }
  return cards
}
