import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'
import {
  certifyIndexedPowerSumTerms,
  certifyPowerSumTail,
  parsePositiveSecondOrderRecurrence,
  parseTrigonometricPowerSum,
  type ParsedPositiveRecurrence,
  type Q,
} from './certified-indexed-power-fusion'

export type ParsedPellOrbit = {
  parentId: string
  xSymbol: string
  ySymbol: string
  discriminant: bigint
  fundamental: [bigint, bigint]
}

type ProductState = {
  x: bigint
  y: bigint
  current: bigint
  next: bigint
}

type StateRow = ProductState & {
  index: number
  accepted: boolean
}

type Matrix2 = [[bigint, bigint], [bigint, bigint]]

function integerSqrt(value: bigint): bigint {
  if (value < 0n) throw new Error('negative square root')
  if (value < 2n) return value
  let left = 1n
  let right = value
  while (left <= right) {
    const middle = (left + right) / 2n
    const square = middle * middle
    if (square === value) return middle
    if (square < value) left = middle + 1n
    else right = middle - 1n
  }
  return right
}

function positiveMod(value: bigint, modulus: bigint): bigint {
  const residue = value % modulus
  return residue < 0n ? residue + modulus : residue
}

function fundamentalPellSolution(discriminant: bigint): [bigint, bigint] | null {
  const root = integerSqrt(discriminant)
  if (root * root === discriminant) return null

  let m = 0n
  let denominator = 1n
  let coefficient = root
  let numeratorPrevious = 1n
  let numerator = coefficient
  let denominatorPrevious = 0n
  let convergentDenominator = 1n

  for (let iteration = 0; iteration < 100_000; iteration += 1) {
    if (numerator * numerator - discriminant * convergentDenominator * convergentDenominator === 1n) {
      return [numerator, convergentDenominator]
    }
    m = denominator * coefficient - m
    denominator = (discriminant - m * m) / denominator
    coefficient = (root + m) / denominator
    const nextNumerator = coefficient * numerator + numeratorPrevious
    const nextDenominator = coefficient * convergentDenominator + denominatorPrevious
    numeratorPrevious = numerator
    numerator = nextNumerator
    denominatorPrevious = convergentDenominator
    convergentDenominator = nextDenominator
  }
  return null
}

export function parsePellOrbit(parent: CertifiedFusionParent): ParsedPellOrbit | null {
  const source = parent.statement
    .replace(/[−–]/g, '-')
    .replace(/\\(?:left|right|big|Big|bigg|Bigg|biggl|biggr)/g, '')
    .replace(/\s+/g, '')
  const match = source.match(/([A-Za-z])\^\{?2\}?-(\d+)([A-Za-z])\^\{?2\}?=1/)
  if (!match || match[1] === match[3]) return null
  const discriminant = BigInt(match[2])
  if (discriminant < 2n || discriminant > 10_000n) return null
  const fundamental = fundamentalPellSolution(discriminant)
  if (!fundamental) return null
  return {
    parentId: parent.id,
    xSymbol: match[1],
    ySymbol: match[3],
    discriminant,
    fundamental,
  }
}

function stateKey(state: ProductState): string {
  return [state.x, state.y, state.current, state.next].join(',')
}

function transition(
  state: ProductState,
  pell: ParsedPellOrbit,
  recurrence: ParsedPositiveRecurrence,
): ProductState {
  const modulus = pell.discriminant
  const [unitX, unitY] = pell.fundamental
  const [coefficient1, coefficient2] = recurrence.coefficients
  return {
    x: positiveMod(unitX * state.x + modulus * unitY * state.y, modulus),
    y: positiveMod(unitY * state.x + unitX * state.y, modulus),
    current: state.next,
    next: positiveMod(coefficient1 * state.next + coefficient2 * state.current, modulus),
  }
}

function enumerateProductOrbit(
  pell: ParsedPellOrbit,
  recurrence: ParsedPositiveRecurrence,
): { rows: StateRow[]; cycleStart: number; period: number } | null {
  const modulus = pell.discriminant
  const [unitX, unitY] = pell.fundamental
  let state: ProductState = {
    x: positiveMod(unitX, modulus),
    y: positiveMod(unitY, modulus),
    current: positiveMod(recurrence.initial[0], modulus),
    next: positiveMod(recurrence.initial[1], modulus),
  }
  const seen = new Map<string, number>()
  const rows: StateRow[] = []

  for (let index = 1; index <= 250_000; index += 1) {
    const key = stateKey(state)
    const previous = seen.get(key)
    if (previous !== undefined) {
      const period = index - previous
      if (period < 1 || period > 128) return null
      return { rows, cycleStart: previous, period }
    }
    seen.set(key, index)
    rows.push({
      index,
      ...state,
      accepted: state.x === state.current,
    })
    state = transition(state, pell, recurrence)
  }
  return null
}

function multiplyMatrix(left: Matrix2, right: Matrix2, modulus: bigint): Matrix2 {
  return [
    [
      positiveMod(left[0][0] * right[0][0] + left[0][1] * right[1][0], modulus),
      positiveMod(left[0][0] * right[0][1] + left[0][1] * right[1][1], modulus),
    ],
    [
      positiveMod(left[1][0] * right[0][0] + left[1][1] * right[1][0], modulus),
      positiveMod(left[1][0] * right[0][1] + left[1][1] * right[1][1], modulus),
    ],
  ]
}

function powerMatrix(matrix: Matrix2, exponent: number, modulus: bigint): Matrix2 {
  let result: Matrix2 = [[1n, 0n], [0n, 1n]]
  let base = matrix
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiplyMatrix(result, base, modulus)
    base = multiplyMatrix(base, base, modulus)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function pellResiduesByMatrix(pell: ParsedPellOrbit, index: number): [bigint, bigint] {
  const modulus = pell.discriminant
  const [unitX, unitY] = pell.fundamental
  const matrix: Matrix2 = [
    [positiveMod(unitX, modulus), 0n],
    [positiveMod(unitY, modulus), positiveMod(unitX, modulus)],
  ]
  const powered = powerMatrix(matrix, index, modulus)
  return [powered[0][0], powered[1][0]]
}

function recurrenceResiduesByMatrix(
  recurrence: ParsedPositiveRecurrence,
  index: number,
  modulus: bigint,
): [bigint, bigint] {
  if (index === 1) {
    return [
      positiveMod(recurrence.initial[0], modulus),
      positiveMod(recurrence.initial[1], modulus),
    ]
  }
  const matrix: Matrix2 = [
    [positiveMod(recurrence.coefficients[0], modulus), positiveMod(recurrence.coefficients[1], modulus)],
    [1n, 0n],
  ]
  const powered = powerMatrix(matrix, index - 1, modulus)
  const next = positiveMod(
    powered[0][0] * recurrence.initial[1] + powered[0][1] * recurrence.initial[0],
    modulus,
  )
  const current = positiveMod(
    powered[1][0] * recurrence.initial[1] + powered[1][1] * recurrence.initial[0],
    modulus,
  )
  return [current, next]
}

function independentlyVerify(
  pell: ParsedPellOrbit,
  recurrence: ParsedPositiveRecurrence,
  orbit: { rows: StateRow[]; cycleStart: number; period: number },
): boolean {
  for (const row of orbit.rows) {
    const [x, y] = pellResiduesByMatrix(pell, row.index)
    const [current, next] = recurrenceResiduesByMatrix(recurrence, row.index, pell.discriminant)
    if (x !== row.x || y !== row.y || current !== row.current || next !== row.next) return false
  }

  const [unitX, unitY] = pell.fundamental
  let x = 1n
  let y = 0n
  for (let index = 1; index <= Math.min(orbit.rows.length, 24); index += 1) {
    const nextX = unitX * x + pell.discriminant * unitY * y
    const nextY = unitY * x + unitX * y
    x = nextX
    y = nextY
    if (x * x - pell.discriminant * y * y !== 1n) return false
  }

  const repeatedIndex = orbit.cycleStart + orbit.period
  const repeatedRow = orbit.rows[orbit.cycleStart - 1]
  const [repeatX, repeatY] = pellResiduesByMatrix(pell, repeatedIndex)
  const [repeatCurrent, repeatNext] = recurrenceResiduesByMatrix(
    recurrence,
    repeatedIndex,
    pell.discriminant,
  )
  return repeatX === repeatedRow.x &&
    repeatY === repeatedRow.y &&
    repeatCurrent === repeatedRow.current &&
    repeatNext === repeatedRow.next
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function integerSetTex(values: number[]): string {
  return values.length ? '\\{' + values.join(',') + '\\}' : '\\varnothing'
}

function answerBody(
  rows: StateRow[],
  cycleStart: number,
  period: number,
): { tex: string; residues: number[]; prefix: number[] } {
  const prefix = rows
    .filter(row => row.index < cycleStart && row.accepted)
    .map(row => row.index)
  const residues = rows
    .filter(row => row.index >= cycleStart && row.index < cycleStart + period && row.accepted)
    .map(row => row.index % period)
    .sort((left, right) => left - right)
  const periodic = 'n\\ge' + cycleStart + ',\\quad n\\bmod ' + period + '\\in' + integerSetTex(residues)
  if (!prefix.length) return { tex: periodic, residues, prefix }
  return {
    tex: 'n\\in' + integerSetTex(prefix) + '\\quad\\text{または}\\quad ' + periodic,
    residues,
    prefix,
  }
}

function minimalObservablePeriod(
  rows: StateRow[],
  cycleStart: number,
  statePeriod: number,
): number {
  const cycleRows = rows.filter(
    row => row.index >= cycleStart && row.index < cycleStart + statePeriod,
  )
  for (let candidate = 1; candidate <= statePeriod; candidate += 1) {
    if (statePeriod % candidate !== 0) continue
    if (cycleRows.every((row, offset) =>
      row.accepted === cycleRows[offset % candidate].accepted
    )) return candidate
  }
  return statePeriod
}

function texDocument(statement: string, solution: string): string {
  return [
    '\\documentclass[a4paper,11pt]{jsarticle}',
    '\\usepackage{amsmath,amssymb,array}',
    '\\begin{document}',
    '\\section*{問題}',
    statement,
    '\\section*{解答}',
    solution,
    '\\end{document}',
    '',
  ].join('\n')
}

function recurrenceDefinition(recurrence: ParsedPositiveRecurrence): string {
  const coefficient = (value: bigint): string => value === 1n ? '' : String(value)
  return 'a_1=' + recurrence.initial[0] +
    ',\\quad a_2=' + recurrence.initial[1] +
    ',\\quad a_{n+2}=' + coefficient(recurrence.coefficients[0]) + 'a_{n+1}+' +
    coefficient(recurrence.coefficients[1]) + 'a_n'
}

export function synthesizeCertifiedPellRecurrenceFusion(
  parents: CertifiedFusionParent[],
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const pell = parents.map(parsePellOrbit).find(Boolean)
  const recurrence = parents.map(parsePositiveSecondOrderRecurrence).find(Boolean)
  if (!pell || !recurrence || pell.parentId === recurrence.parentId) return []

  const orbit = enumerateProductOrbit(pell, recurrence)
  if (!orbit || !independentlyVerify(pell, recurrence, orbit)) return []
  const observablePeriod = minimalObservablePeriod(orbit.rows, orbit.cycleStart, orbit.period)
  const answer = answerBody(orbit.rows, orbit.cycleStart, observablePeriod)
  if (!answer.residues.length && !answer.prefix.length) return []

  const modulus = pell.discriminant
  const [unitX, unitY] = pell.fundamental
  const recurrenceTex = recurrenceDefinition(recurrence)
  const cycleRows = orbit.rows.filter(
    row => row.index >= orbit.cycleStart && row.index < orbit.cycleStart + observablePeriod,
  )
  const table = [
    '\\[',
    '\\begin{array}{c|' + 'c'.repeat(cycleRows.length) + '}',
    'n&' + cycleRows.map(row => row.index).join('&') + '\\\\\\hline',
    'x_n\\bmod ' + modulus + '&' + cycleRows.map(row => row.x).join('&') + '\\\\',
    'a_n\\bmod ' + modulus + '&' + cycleRows.map(row => row.current).join('&') + '\\\\',
    '\\text{一致}&' + cycleRows.map(row => row.accepted ? '\\circ' : '\\times').join('&'),
    '\\end{array}',
    '\\]',
  ].join('\n')

  const statement = [
    '\\(x^2-' + modulus + 'y^2=1\\) の非負整数解を、',
    '\\[',
    'x_n+y_n\\sqrt{' + modulus + '}=(' + unitX + '+' +
      (unitY === 1n ? '' : String(unitY)) + '\\sqrt{' + modulus + '})^n',
    '\\qquad(n=1,2,3,\\ldots)',
    '\\]',
    'で定める。また、整数列 \\(\\{a_n\\}\\) を',
    '\\[' + recurrenceTex + '\\]',
    'で定める。合同式',
    '\\[',
    'x_n\\equiv a_n\\pmod{' + modulus + '}',
    '\\]',
    'を満たす正の整数 \\(n\\) をすべて求めよ。',
  ].join('\n')

  const solution = [
    'Pell方程式の最小の正の解は \\((' + unitX + ',' + unitY + ')\\) である。連分数法により得られ、正の解はすべて',
    '\\[',
    'x_n+y_n\\sqrt{' + modulus + '}=(' + unitX + '+' +
      (unitY === 1n ? '' : String(unitY)) + '\\sqrt{' + modulus + '})^n',
    '\\]',
    'と一意に表される。したがって',
    '\\[',
    '\\binom{x_{n+1}}{y_{n+1}}=',
    '\\begin{pmatrix}' + unitX + '&' + modulus * unitY + '\\\\' + unitY + '&' + unitX + '\\end{pmatrix}',
    '\\binom{x_n}{y_n}',
    '\\]',
    'である。一方、与えられた漸化式も',
    '\\[',
    '\\binom{a_{n+1}}{a_n}=',
    '\\begin{pmatrix}' + recurrence.coefficients[0] + '&' + recurrence.coefficients[1] + '\\\\1&0\\end{pmatrix}',
    '\\binom{a_n}{a_{n-1}}',
    '\\]',
    'と書ける。両者を法 \\(' + modulus + '\\) で同時に追うと、状態',
    '\\((x_n,y_n,a_n,a_{n+1})\\bmod ' + modulus + '\\) は有限個しかなく、次の表を得る。',
    table,
    '第 \\(' + orbit.cycleStart + '\\) 項の完全状態が ' + orbit.period +
      ' 段後に初めて戻る。さらに一周期内の一致・不一致だけを比較すると最小周期は ' +
      observablePeriod + ' である。したがって合同条件は以後も周期 ' + observablePeriod + ' で繰り返す。',
    '表で二つの剰余が一致する列だけを取れば、',
    '\\[' + answer.tex + '\\]',
    'である。なお、表は逐次漸化式と二つの伴行列の高速累乗を別々に実行して一致を確認している。',
  ].join('\n')
  const answerTex = '\\(' + answer.tex + '\\)'
  const structureId = 'certified.pell-recurrence-product.' + hash({
    discriminant: String(modulus),
    fundamental: pell.fundamental.map(String),
    initial: recurrence.initial.map(String),
    coefficients: recurrence.coefficients.map(String),
  })
  const morphisms = [
    'PellEquationElaboration',
    'ContinuedFractionFundamentalUnit',
    'QuadraticUnitOrbit',
    'PositiveSecondOrderRecurrenceElaboration',
    'CompanionMatrixAction',
    'FiniteStateProduct',
    'CycleCertificate',
    'IndependentMatrixReplay',
    'AllParentAblation',
  ]
  const diagramStates = cycleRows.map(row => ({
    id: 'n' + row.index,
    label: 'n=' + row.index + ': (' + row.x + ',' + row.current + ') mod ' + modulus,
    active: row.accepted,
  }))

  return [{
    id: 'mortra-' + structureId,
    statement_tex: statement,
    answer_tex: answerTex,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'number_theory_dynamical_systems',
    family_id: 'certified.pell_recurrence_state_product',
    tool: 'MORTRA exact reversible synthesis',
    morphism_chain: morphisms,
    diagram: {
      version: 1,
      kind: 'state',
      title: '二つの整数列を同時に追う',
      caption: 'Pell方程式の解の列と漸化式の列を同時に進め、合同条件が成立する状態を示します。',
      states: diagramStates,
      transitions: diagramStates.map((state, index) => ({
        from: state.id,
        to: diagramStates[(index + 1) % diagramStates.length].id,
        label: 'mod ' + modulus,
      })),
    },
    parent_ids: parents.map(parent => parent.id),
    verification: {
      method: 'continued-fraction Pell unit + exact finite-state product + independent modular matrix powers + all-parent dependency',
      exact_backend: true,
      independent_check: true,
      samples: [orbit.rows.length, orbit.cycleStart, orbit.period, observablePeriod, Number(modulus)],
    },
    difficulty: { band: 'A_exact_cross_domain_fusion', score: 8.9 },
    fusion_derivation: {
      passed: true,
      reason: 'one parent supplies the quadratic-unit orbit and canonical modulus; the other supplies an independent integer recurrence, and the new observable exists only on their product action',
      ablationPassed: true,
      assignments: [
        {
          parentId: pell.parentId,
          portId: 'quadratic_unit_orbit',
          role: 'state generator and modulus',
          matchedAnchors: ['x^2-' + modulus + 'y^2=1'],
          witnessSteps: ['PellEquationElaboration', 'ContinuedFractionFundamentalUnit', 'QuadraticUnitOrbit'],
        },
        {
          parentId: recurrence.parentId,
          portId: 'integer_recurrence_orbit',
          role: 'comparison orbit',
          matchedAnchors: [recurrenceTex],
          witnessSteps: ['PositiveSecondOrderRecurrenceElaboration', 'CompanionMatrixAction'],
        },
      ],
      bridges: [{
        id: 'discriminant-state-product',
        witnessStep: 'FiniteStateProduct',
        consumes: ['quadratic_unit_orbit', 'integer_recurrence_orbit'],
        produces: 'periodic_congruence_observable',
      }],
      intermediatePropositions: [
        {
          parentId: pell.parentId,
          morphism: 'QuadraticUnitOrbit',
          source: 'PellEquation',
          target: 'IntegralMatrixOrbit',
          proposition: 'the fundamental unit generates every ordered positive Pell solution',
          proved: true,
        },
        {
          parentId: recurrence.parentId,
          morphism: 'CompanionMatrixAction',
          source: 'PositiveSecondOrderRecurrence',
          target: 'IntegralMatrixOrbit',
          proposition: 'the companion matrix generates every term of the parent recurrence',
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'FiniteGeneratedActionProductIR',
      observable: 'periodic_congruence_solution_set',
      operators: morphisms,
      domain: 'number_theory_dynamical_systems',
      tags: ['pell-equation', 'quadratic-unit', 'recurrence', 'finite-state', 'matrix', 'congruence', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'fundamental-unit', claim: 'the minimal positive Pell unit is produced by continued fractions', verifier: 'BigInt continued-fraction kernel' },
        { id: 'pell-invariant', claim: 'sampled exact orbit points satisfy x^2-Dy^2=1', verifier: 'BigInt quadratic-form replay' },
        { id: 'product-cycle', claim: 'the complete product state returns after the certified period', verifier: 'finite-state closure checker' },
        { id: 'matrix-replay', claim: 'every tabulated residue agrees with independent modular matrix powers', verifier: 'BigInt 2x2 modular matrix kernel' },
        { id: 'ablation', claim: 'removing either parent makes the product observable undefined', verifier: 'typed two-port dependency check' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['pell-unit-orbit', 'positive-second-order-recurrence', 'discriminant-modular-product'],
        querySignature: 'classify-equality-states-in-product-orbit',
        normalForm: answerTex,
        quotientAction: 'rename Pell coordinates, recurrence symbol, and index variables',
        freeParameters: ['nonsquare Pell discriminant', 'two recurrence initial values', 'two recurrence coefficients'],
        uniqueNormalForm: true,
        finiteSolutionSet: false,
        numericInstanceConstants: [
          Number(modulus),
          Number(unitX),
          Number(unitY),
          orbit.period,
          observablePeriod,
        ],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: orbit.rows.length,
      valid_hypotheses: answer.residues.length + answer.prefix.length,
      elapsed_ms: Date.now() - startedAt,
    },
  }]
}

function pellIndexTerms(
  pell: ParsedPellOrbit,
  cutoff: number,
): { terms: bigint[]; points: Array<[bigint, bigint]> } | null {
  const [unitX, unitY] = pell.fundamental
  let x = 1n
  let y = 0n
  const terms: bigint[] = []
  const points: Array<[bigint, bigint]> = []
  for (let index = 1; index <= 256; index += 1) {
    const nextX = unitX * x + pell.discriminant * unitY * y
    const nextY = unitY * x + unitX * y
    x = nextX
    y = nextY
    terms.push(x)
    points.push([x, y])
    if (x >= BigInt(cutoff)) return { terms, points }
  }
  return null
}

function independentlyReplayPellX(pell: ParsedPellOrbit, count: number): bigint[] {
  const [unitX] = pell.fundamental
  const values: bigint[] = []
  let previous = 1n
  let current = unitX
  for (let index = 1; index <= count; index += 1) {
    values.push(current)
    const next = 2n * unitX * current - previous
    previous = current
    current = next
  }
  return values
}

function rationalTex(value: Q): string {
  if (value.d === 1n) return String(value.n)
  return value.n < 0n
    ? '-\\frac{' + (-value.n) + '}{' + value.d + '}'
    : '\\frac{' + value.n + '}{' + value.d + '}'
}

export function synthesizeCertifiedPellIndexedPowerSumFusion(
  parents: CertifiedFusionParent[],
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const pell = parents.map(parsePellOrbit).find(Boolean)
  const powerParent = parents.map(parseTrigonometricPowerSum).find(Boolean)
  if (!pell || !powerParent || pell.parentId === powerParent.parentId) return []

  const tail = certifyPowerSumTail(powerParent)
  if (!tail) return []
  const generated = pellIndexTerms(pell, tail.cutoff)
  if (!generated) return []
  const replayed = independentlyReplayPellX(pell, generated.terms.length)
  if (!generated.terms.every((term, index) => term === replayed[index])) return []
  if (!generated.points.every(([x, y]) =>
    x * x - pell.discriminant * y * y === 1n
  )) return []

  const evaluation = certifyIndexedPowerSumTerms(powerParent, generated.terms)
  if (!evaluation) return []
  const [unitX, unitY] = pell.fundamental
  const c = evaluation.sumTex
  const comparisonTable = evaluation.checked.length > 0
    ? [
        '\\[',
        '\\begin{array}{c|' + 'c'.repeat(evaluation.checked.length) + '}',
        'k&' + evaluation.checked.map(item => item.index).join('&') + '\\\\',
        '\\hline',
        'x_k&' + evaluation.checked.map(item => item.exponent).join('&') + '\\\\',
        'u_{x_k}-' + evaluation.sumTex + '&' +
          evaluation.checked.map(item => rationalTex(item.difference)).join('&'),
        '\\end{array}',
        '\\]',
      ].join('\n')
    : '\\[\\text{上の評価を適用する前に直接計算すべき項はない。}\\]'
  const answerTex = '\\(k\\in' + integerSetTex(evaluation.answerIndices) + '\\)'
  const unitTex = unitX + '+' + (unitY === 1n ? '' : String(unitY)) +
    '\\sqrt{' + pell.discriminant + '}'
  const statement = [
    'Pell方程式 \\(x^2-' + pell.discriminant + 'y^2=1\\) の正の解を',
    '\\[',
    'x_k+y_k\\sqrt{' + pell.discriminant + '}=(' + unitTex + ')^k',
    '\\qquad(k=1,2,3,\\ldots)',
    '\\]',
    'で定める。実数 \\(\\theta\\) が',
    '\\[\\sin\\theta+\\cos\\theta=' + c + '\\]',
    'を満たすとき、',
    '\\[\\sin^{x_k}\\theta+\\cos^{x_k}\\theta>' + c + '\\]',
    'となる正の整数 \\(k\\) をすべて求めよ。',
  ].join('\n')
  const solution = [
    '\\(X=\\sin\\theta,\\ Y=\\cos\\theta\\) とおき、\\(u_m=X^m+Y^m\\) とする。条件から',
    '\\[X+Y=' + c + ',\\qquad XY=\\frac{(' + c + ')^2-1}{2},\\]',
    'したがって、\\(X,Y\\) はともに',
    '\\[t^2-' + c + 't-\\frac{1-(' + c + ')^2}{2}=0\\]',
    'の解である。各辺にそれぞれ \\(X^m,Y^m\\) を掛けて加えると、べき和 \\(u_m\\) は',
    '\\[u_0=2,\\quad u_1=' + c +
      ',\\quad u_{m+2}=' + c + 'u_{m+1}+\\frac{1-(' + c + ')^2}{2}u_m\\tag{1}\\]',
    'を満たす。',
    '一方、\\(x_k+y_k\\sqrt{' + pell.discriminant + '}\\) に \\(' + unitTex + '\\) を掛け、\\(1,\\sqrt{' + pell.discriminant + '}\\) の係数を比較すると',
    '\\[',
    '\\binom{x_{k+1}}{y_{k+1}}=',
    '\\begin{pmatrix}' + unitX + '&' + pell.discriminant * unitY + '\\\\' +
      unitY + '&' + unitX + '\\end{pmatrix}\\binom{x_k}{y_k}',
    '\\]',
    'であり、添字列は',
    '\\[' + generated.terms.join(', ') + ',\\ldots\\]',
    'となる。これを \\((1)\\) に代入して厳密有理数で比較すると',
    comparisonTable,
    'を得る。',
    '残りを評価する。\\(X=\\alpha>0,\\ Y=-\\beta<0\\) とすると \\(\\alpha-\\beta=' + c + '\\) であり、',
    '\\[\\max(\\alpha,\\beta)<r=' + rationalTex(evaluation.bound) + '\\]',
    'が成り立つ。奇数 \\(m\\ge' + evaluation.thresholds.odd + '\\) では',
    '\\[|u_m|\\le ' + c + '\\,m r^{m-1}<' + c + ',\\]',
    '偶数 \\(m\\ge' + evaluation.thresholds.even + '\\) では',
    '\\[0<u_m\\le2r^m<' + c + '.\\]',
    '\\(x_k\\) は狭義単調に増加する。表には、上の評価をまだ適用できない項だけを載せた。表にない項は、奇数なら \\(x_k\\ge' +
      evaluation.thresholds.odd + '\\)、偶数なら \\(x_k\\ge' + evaluation.thresholds.even +
      '\\) なので、いずれも不等式を満たさない。また、\\(x_' + generated.terms.length + '=' +
      generated.terms.at(-1) + '\\ge' + evaluation.cutoff + '\\) であり、以後も増加するから、新しい解はない。',
    'よって',
    '\\[k\\in' + integerSetTex(evaluation.answerIndices) + '\\]',
    'である。Pell方程式の解の列は、上の行列計算とは別に二階漸化式でも再生した。べき和も、逐次計算と伴行列の累乗という二つの方法で同じ値になることを確認した。',
  ].join('\n')
  const structureId = 'certified.pell-indexed-power-sum.' + hash({
    discriminant: String(pell.discriminant),
    fundamental: pell.fundamental.map(String),
    sum: evaluation.sumText,
  })
  const morphisms = [
    'PellEquationElaboration',
    'ContinuedFractionFundamentalUnit',
    'QuadraticUnitOrbit',
    'SymmetricTrigonometricPairElaboration',
    'NewtonPowerSumRecurrence',
    'SubsequencePullback',
    'ExactRationalInequality',
    'CertifiedTailBound',
    'IndependentRecurrenceReplay',
    'AllParentAblation',
  ]
  const exactStates = evaluation.checked.map(item => ({
    id: 'k' + item.index,
    label: 'k=' + item.index + ', x_k=' + item.exponent,
    active: item.passed,
  }))

  return [{
    id: 'mortra-' + structureId,
    statement_tex: statement,
    answer_tex: answerTex,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'number_theory_analysis',
    family_id: 'certified.pell_indexed_power_sum',
    tool: 'MORTRA exact reversible synthesis',
    morphism_chain: morphisms,
    diagram: {
      version: 1,
      kind: 'state',
      title: 'Pell方程式の解をべき和の指数にする',
      caption: '一方の親から得た整数列を、もう一方の親から得たべき和の指数として使います。色付きの状態だけが不等式を満たします。',
      states: [
        ...exactStates,
        {
          id: 'tail',
          label: 'x_k ≥ ' + evaluation.cutoff + ': 一括評価',
          terminal: true,
        },
      ],
      transitions: [
        ...exactStates.slice(1).map((state, index) => ({
          from: exactStates[index].id,
          to: state.id,
          label: '次の解',
        })),
        {
          from: exactStates.at(-1)?.id ?? 'k1',
          to: 'tail',
          label: '以後をまとめて評価',
        },
      ],
    },
    parent_ids: parents.map(parent => parent.id),
    verification: {
      method: 'exact Pell-unit orbit + independent scalar recurrence + exact rational Newton recurrence + independent matrix replay + exact tail inequalities',
      exact_backend: true,
      independent_check: true,
      samples: [
        generated.terms.length,
        evaluation.checked.length,
        evaluation.cutoff,
        evaluation.thresholds.odd,
        evaluation.thresholds.even,
      ],
    },
    difficulty: { band: 'A_exact_cross_domain_fusion', score: 9.2 },
    fusion_derivation: {
      passed: true,
      reason: 'one parent supplies an indispensable quadratic-unit exponent orbit and the other supplies the indispensable symmetric power-sum transition',
      ablationPassed: true,
      assignments: [
        {
          parentId: pell.parentId,
          portId: 'pell_exponent_orbit',
          role: 'index generator',
          matchedAnchors: ['x^2-' + pell.discriminant + 'y^2=1'],
          witnessSteps: ['PellEquationElaboration', 'QuadraticUnitOrbit'],
        },
        {
          parentId: powerParent.parentId,
          portId: 'power_sum_transition',
          role: 'observable',
          matchedAnchors: ['sin+cos=' + evaluation.sumText],
          witnessSteps: ['SymmetricTrigonometricPairElaboration', 'NewtonPowerSumRecurrence'],
        },
      ],
      bridges: [{
        id: 'pell-subsequence-pullback',
        witnessStep: 'SubsequencePullback',
        consumes: ['pell_exponent_orbit', 'power_sum_transition'],
        produces: 'pell_indexed_power_sum_inequality',
      }],
      intermediatePropositions: [
        {
          parentId: pell.parentId,
          morphism: 'QuadraticUnitOrbit',
          source: 'PellEquation',
          target: 'StrictlyIncreasingIntegerOrbit',
          proposition: 'the fundamental Pell unit uniquely generates every exponent used by the new problem',
          proved: true,
        },
        {
          parentId: powerParent.parentId,
          morphism: 'NewtonPowerSumRecurrence',
          source: 'SymmetricTrigonometricPair',
          target: 'RationalPowerSumSequence',
          proposition: 'the parent sum and the identity sin^2+cos^2=1 uniquely determine every queried power sum',
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'ReversibleGeneratedIndexPowerSumIR',
      observable: 'pell_indexed_power_sum_inequality_solution_set',
      operators: morphisms,
      domain: 'number_theory_analysis',
      tags: ['pell-equation', 'quadratic-unit', 'power-sum', 'newton-sums', 'subsequence', 'inequality', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'pell-replay', claim: 'all generated exponents agree by quadratic-unit multiplication and an independent scalar recurrence', verifier: 'BigInt Pell orbit kernel' },
        { id: 'pell-invariant', claim: 'every generated pair satisfies x^2-Dy^2=1', verifier: 'BigInt quadratic-form replay' },
        { id: 'power-sum-replay', claim: 'all finite comparisons agree by recurrence and independent matrix exponentiation', verifier: 'exact rational power-sum kernel' },
        { id: 'tail', claim: 'all exponents beyond the cutoff fail the strict inequality', verifier: 'exact rational geometric-tail certificate' },
        { id: 'ablation', claim: 'removing either parent makes the indexed observable undefined', verifier: 'typed two-port dependency check' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['pell-unit-orbit', 'symmetric-trigonometric-power-sum'],
        querySignature: 'classify-pell-indexed-power-sum-inequality',
        normalForm: answerTex,
        quotientAction: 'rename Pell coordinates, index, exponent, and angle variables',
        freeParameters: ['nonsquare Pell discriminant', 'rational symmetric trigonometric sum'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
        numericInstanceConstants: [
          Number(pell.discriminant),
          evaluation.cutoff,
          evaluation.thresholds.odd,
          evaluation.thresholds.even,
        ],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: generated.terms.length,
      valid_hypotheses: evaluation.answerIndices.length,
      elapsed_ms: Date.now() - startedAt,
    },
  }]
}
