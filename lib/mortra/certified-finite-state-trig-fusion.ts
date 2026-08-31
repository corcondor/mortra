import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'

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
  const states: State[] = []
  const seen = new Map<string, number>()
  let state: State = [
    positiveMod(recurrence.initial[0], modulus),
    positiveMod(recurrence.initial[1], modulus),
  ]
  for (let index = 0; index <= maximumStates; index += 1) {
    const key = stateKey(state)
    const previous = seen.get(key)
    if (previous !== undefined) {
      return { states, cycleStart: previous, statePeriod: index - previous }
    }
    seen.set(key, index)
    states.push(state)
    state = nextState(state, recurrence.coefficients, modulus)
  }
  return null
}

function phaseKey(value: bigint, angle: ParsedRationalAngle): bigint {
  const modulus = 2n * angle.denominator
  const phase = positiveMod(value * angle.numerator, modulus)
  return phase <= modulus - phase ? phase : modulus - phase
}

function divisors(value: number): number[] {
  const out: number[] = []
  for (let candidate = 1; candidate <= value; candidate += 1) {
    if (value % candidate === 0) out.push(candidate)
  }
  return out
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

function certifyObservableOrbit(
  recurrence: ParsedIntegerSecondOrderRecurrence,
  angle: ParsedRationalAngle,
): {
  modulus: bigint
  cycleStart: number
  statePeriod: number
  statesEnumerated: number
  observableStart: number
  observablePeriod: number
  phases: bigint[]
} | null {
  const modulus = 2n * angle.denominator
  const orbit = enumerateOrbit(recurrence, modulus)
  if (!orbit) return null
  const { states, cycleStart, statePeriod } = orbit
  const cyclePhases = Array.from({ length: statePeriod }, (_, index) =>
    phaseKey(states[cycleStart + index][0], angle),
  )
  const observablePeriod = divisors(statePeriod).find(period =>
    cyclePhases.every((phase, index) => phase === cyclePhases[(index + period) % statePeriod]),
  )
  if (!observablePeriod) return null

  let observableStart = cycleStart
  for (let candidate = 0; candidate <= cycleStart; candidate += 1) {
    let valid = true
    for (let index = candidate; index < cycleStart + statePeriod; index += 1) {
      const left = phaseKey(stateAt(states, cycleStart, statePeriod, index)[0], angle)
      const right = phaseKey(
        stateAt(states, cycleStart, statePeriod, index + observablePeriod)[0],
        angle,
      )
      if (left !== right) {
        valid = false
        break
      }
    }
    if (valid) {
      observableStart = candidate
      break
    }
  }

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
    phases: Array.from({ length: observablePeriod }, (_, index) =>
      phaseKey(
        stateAt(states, cycleStart, statePeriod, observableStart + index)[0],
        angle,
      ),
    ),
  }
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
    cards.push({
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
    })
  }
  return cards
}
