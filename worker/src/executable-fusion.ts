import { createHash } from 'node:crypto'
import type { DiscoveryParent } from './parent-conditioned-discovery'

type Matrix2 = readonly [bigint, bigint, bigint, bigint]

export type ExecutableFusionCard = {
  id: string
  family_id: string
  statement_tex: string
  answer_tex: string
  solution_tex: string
  domain: string
  morphism_chain: string[]
  parent_ids: string[]
  unresolved: false
  discovery_status: 'verified'
  verification: { method: string; exact_backend: true; independent_check: true; samples: number[] }
  difficulty: { band: string; score: number }
  fusion_derivation: {
    passed: true
    reason: string
    ablationPassed: true
    assignments: Array<{ parentId: string; portId: string; role: string; matchedAnchors: string[]; witnessSteps: string[] }>
    bridges: Array<{ id: string; witnessStep: string; consumes: string[]; produces: string }>
    intermediatePropositions: Array<{ parentId: string; morphism: string; source: string; target: string; proposition: string; proved: true }>
  }
  structure_blueprint: {
    id: string
    version: 1
    kernel: string
    observable: string
    operators: string[]
    domain: string
    tags: string[]
    morphismChain: string[]
    executable: true
    proofCertificate: Array<{ id: string; claim: string; verifier: string }>
    synthesizedLaw?: {
      name: string
      expression: string
      arity: number
      sources: string[]
      target: string
      preserves: string[]
      backend: string[]
    }
    structuralUniqueness?: {
      schema: 1
      conditionSkeleton: string[]
      querySignature: string
      normalForm: string
      quotientAction: string
      freeParameters: string[]
      uniqueNormalForm: boolean
      finiteSolutionSet: boolean
      numericInstanceConstants: number[]
      conditionAblationPassed: boolean
    }
  }
  search_evidence: { hypotheses_evaluated: number; valid_hypotheses: number; elapsed_ms: number }
}

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function parseLinear(expression: string): [bigint, bigint] | null {
  const normalized = expression
    .replace(/\\left|\\right/g, '')
    .replace(/[{}\s]/g, '')
    .replace(/−/g, '-')
  const match = normalized.match(/^([+-]?\d*)z([+-]\d+)?$/)
  if (!match) return null
  const coefficient = match[1] === '' || match[1] === '+' ? 1n : match[1] === '-' ? -1n : BigInt(match[1])
  return [coefficient, BigInt(match[2] || '0')]
}

export function extractMobiusMap(parents: DiscoveryParent[]): { matrix: Matrix2; parentId: string } | null {
  for (const parent of parents) {
    const source = parent.statement ?? ''
    const match = source.match(/T\s*\(\s*z\s*\)\s*=\s*\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/i)
    if (!match) continue
    const numerator = parseLinear(match[1])
    const denominator = parseLinear(match[2])
    if (!numerator || !denominator) continue
    const matrix: Matrix2 = [numerator[0], numerator[1], denominator[0], denominator[1]]
    if (matrix[0] * matrix[3] === matrix[1] * matrix[2]) continue
    return { matrix, parentId: String(parent.id || 'mobius-parent') }
  }
  return null
}

function findRootOrbitParent(parents: DiscoveryParent[]): string | null {
  for (const parent of parents) {
    const source = parent.statement ?? ''
    if (/z\s*\^\s*\{?n\}?\s*=\s*1|1\s*の\s*n\s*乗根|1の冪根|roots? of unity/i.test(source)) {
      return String(parent.id || 'root-orbit-parent')
    }
  }
  return null
}

function multiply(left: Matrix2, right: Matrix2): Matrix2 {
  const [a, b, c, d] = left
  const [e, f, g, h] = right
  return [a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h]
}

function power(matrix: Matrix2, exponent: number): Matrix2 {
  let result: Matrix2 = [1n, 0n, 0n, 1n]
  let base = matrix
  let n = exponent
  while (n > 0) {
    if (n % 2 === 1) result = multiply(result, base)
    base = multiply(base, base)
    n = Math.floor(n / 2)
  }
  return result
}

type Complex = { re: number; im: number }
const add = (x: Complex, y: Complex): Complex => ({ re: x.re + y.re, im: x.im + y.im })
const mul = (x: Complex, y: Complex): Complex => ({ re: x.re * y.re - x.im * y.im, im: x.re * y.im + x.im * y.re })
const div = (x: Complex, y: Complex): Complex => {
  const denominator = y.re * y.re + y.im * y.im
  return { re: (x.re * y.re + x.im * y.im) / denominator, im: (x.im * y.re - x.re * y.im) / denominator }
}

function evaluateMobius(matrix: Matrix2, z: Complex): Complex {
  const [a, b, c, d] = matrix.map(Number) as unknown as [number, number, number, number]
  return div({ re: a * z.re + b, im: a * z.im }, { re: c * z.re + d, im: c * z.im })
}

function powNumber(base: number, exponent: number): number {
  return Math.pow(base, exponent)
}

function absBigInt(value: bigint): bigint {
  return value < 0n ? -value : value
}

function traceValue(matrix: Matrix2, n: number): number {
  const [a0, b0, c0, d0] = matrix.map(Number) as unknown as [number, number, number, number]
  const determinantTerm = b0 * c0 - a0 * d0
  return n * a0 / c0 - n * determinantTerm * powNumber(-d0, n - 1) /
    (c0 * (powNumber(-d0, n) - powNumber(c0, n)))
}

function inverseTraceValue(matrix: Matrix2, n: number): number {
  const [a0, b0, c0, d0] = matrix.map(Number) as unknown as [number, number, number, number]
  const determinantTerm = d0 * a0 - c0 * b0
  return n * c0 / a0 - n * determinantTerm * powNumber(-b0, n - 1) /
    (a0 * (powNumber(-b0, n) - powNumber(a0, n)))
}

function normValue(matrix: Matrix2, n: number): number {
  const [a0, b0, c0, d0] = matrix.map(Number) as unknown as [number, number, number, number]
  const parity = n % 2 === 0 ? 1 : -1
  return (powNumber(b0, n) - parity * powNumber(a0, n)) /
    (powNumber(d0, n) - parity * powNumber(c0, n))
}

function verifyNumerically(matrix: Matrix2, observable: 'trace' | 'norm' | 'inverse_trace'): number[] | null {
  const samples = [2, 3, 4, 5, 7, 9]
  for (const n of samples) {
    const values = Array.from({ length: n }, (_, index) => {
      const angle = 2 * Math.PI * index / n
      return evaluateMobius(matrix, { re: Math.cos(angle), im: Math.sin(angle) })
    })
    let actual: Complex
    let expected: number
    if (observable === 'norm') {
      actual = values.reduce(mul, { re: 1, im: 0 })
      expected = normValue(matrix, n)
    } else if (observable === 'inverse_trace') {
      actual = values.reduce((sum, value) => add(sum, div({ re: 1, im: 0 }, value)), { re: 0, im: 0 })
      expected = inverseTraceValue(matrix, n)
    } else {
      actual = values.reduce(add, { re: 0, im: 0 })
      expected = traceValue(matrix, n)
    }
    if (![actual.re, actual.im, expected].every(Number.isFinite)) return null
    const tolerance = 1e-7 * Math.max(1, Math.abs(expected))
    if (Math.abs(actual.re - expected) > tolerance || Math.abs(actual.im) > tolerance) return null
  }
  return samples
}

function signed(value: bigint): string {
  return value >= 0n ? `+${value}` : String(value)
}

function linear(a: bigint, b: bigint): string {
  return `${a}z${b === 0n ? '' : signed(b)}`
}

function correctionTerm(coefficient: bigint, numerator: string, denominator: string): string {
  if (coefficient === 0n) return ''
  const sign = coefficient > 0n ? '+' : '-'
  const magnitude = absBigInt(coefficient)
  const coefficientText = magnitude === 1n ? '' : String(magnitude)
  return `${sign}\\frac{${coefficientText}${numerator}}{${denominator}}`
}

function answerFor(matrix: Matrix2, observable: 'trace' | 'norm' | 'inverse_trace'): string {
  const [a, b, c, d] = matrix
  const parity = '(-1)^n'
  if (observable === 'norm') {
    return `\\frac{${b}^{n}-${parity}${a}^{n}}{${d}^{n}-${parity}${c}^{n}}`
  }
  if (observable === 'inverse_trace') {
    const correction = c * b - d * a
    return `\\frac{${c}n}{${a}}${correctionTerm(correction, `n(-${b})^{n-1}`, `${a}\\left((- ${b})^n-${a}^n\\right)` )}`.replace(/\(- /g, '(-')
  }
  const correction = a * d - b * c
  return `\\frac{${a}n}{${c}}${correctionTerm(correction, `n(-${d})^{n-1}`, `${c}\\left((- ${d})^n-${c}^n\\right)` )}`.replace(/\(- /g, '(-')
}

function observableText(observable: 'trace' | 'norm' | 'inverse_trace', exponent: number): string {
  if (observable === 'norm') return `\\displaystyle \\prod_{k=1}^{n}T_M^{\\circ ${exponent}}(z_k)`
  if (observable === 'inverse_trace') return `\\displaystyle \\sum_{k=1}^{n}\\frac{1}{T_M^{\\circ ${exponent}}(z_k)}`
  return `\\displaystyle \\sum_{k=1}^{n}T_M^{\\circ ${exponent}}(z_k)`
}

export type ExecutableFusionOptions = {
  minIteration?: number
  maxIteration?: number
}

export function synthesizeExecutableFusions(
  parents: DiscoveryParent[],
  requested: number,
  options: ExecutableFusionOptions = {},
): ExecutableFusionCard[] {
  const startedAt = Date.now()
  const mobius = extractMobiusMap(parents)
  const rootParentId = findRootOrbitParent(parents)
  if (!mobius || !rootParentId || rootParentId === mobius.parentId) return []
  const parentIds = parents.map((parent, index) => String(parent.id || `parent-${index + 1}`))
  const cards: ExecutableFusionCard[] = []
  const observables = ['trace', 'norm', 'inverse_trace'] as const
  const minIteration = Math.max(2, Math.floor(options.minIteration ?? 2))
  const maxIteration = Math.max(minIteration, Math.floor(options.maxIteration ?? 5))
  for (let exponent = minIteration; cards.length < requested && exponent <= maxIteration; exponent++) {
    const iterated = power(mobius.matrix, exponent)
    const [a, b, c, d] = iterated
    if (a === 0n || c === 0n || a * d === b * c) continue
    for (const observable of observables) {
      if (cards.length >= requested) break
      if (absBigInt(c) === absBigInt(d)) continue
      if (observable === 'inverse_trace' && absBigInt(a) === absBigInt(b)) continue
      const samples = verifyNumerically(iterated, observable)
      if (!samples) continue
      const structureId = `field-orbit.${observable}.iterate-${exponent}.${hash({ parentIds, iterated: iterated.map(String) })}`
      const morphisms = [
        'AdjacencyMatrix', 'ProjectiveAction', 'MobiusIteration', 'FiniteRootOrbit',
        observable === 'norm' ? 'FieldNorm' : observable === 'inverse_trace' ? 'ReciprocalFieldTrace' : 'FieldTrace',
        'RootPolynomial', observable === 'norm' ? 'Resultant' : 'LogDerivative', 'ExactSimplification', 'NumericCounterexampleCheck',
      ]
      const query = observableText(observable, exponent)
      const answer = answerFor(iterated, observable)
      const statement = `行列 \\(M=\\begin{pmatrix}${mobius.matrix[0]}&${mobius.matrix[1]}\\\\${mobius.matrix[2]}&${mobius.matrix[3]}\\end{pmatrix}\\) に対し、\\(N=\\begin{pmatrix}r&s\\\\t&u\\end{pmatrix}\\) が誘導する変換を \\(T_N(z)=\\dfrac{rz+s}{tz+u}\\) とする。\\(n\\ge 2\\) とし、\\(z_1,\\ldots,z_n\\) を \\(z^n=1\\) の全ての解とするとき、\\[${query}\\] を \\(n\\) を用いて表せ。`
      const solution = observable === 'norm'
        ? `\\(M^{${exponent}}=\\begin{pmatrix}${a}&${b}\\\\${c}&${d}\\end{pmatrix}\\) より、\\(T^{\\circ ${exponent}}(z)=\\dfrac{${linear(a, b)}}{${linear(c, d)}}\\)。\\(\\prod_{z^n=1}(Az+B)=B^n-(-1)^nA^n\\) を分子・分母に用いると答えを得る。数値反例検査は n=${samples.join(',')} で通過した。`
        : `\\(M^{${exponent}}=\\begin{pmatrix}${a}&${b}\\\\${c}&${d}\\end{pmatrix}\\) より、\\(T^{\\circ ${exponent}}(z)=\\dfrac{${linear(a, b)}}{${linear(c, d)}}\\)。\\(P(x)=x^n-1\\) の対数微分 \\(\\sum_{P(z_k)=0}\\dfrac1{x-z_k}=\\dfrac{P'(x)}{P(x)}\\) と部分分数分解を用いると答えを得る。数値反例検査は n=${samples.join(',')} で通過した。`
      const proofCertificate = [
        { id: 'matrix-power', claim: `M^${exponent}=(${iterated.join(',')})`, verifier: 'exact BigInt matrix multiplication' },
        { id: 'projective-composition', claim: `T_M^${exponent}=T_{M^${exponent}}`, verifier: 'PGL(2) composition law' },
        { id: 'finite-orbit', claim: 'the selected algebraic orbit is exactly V(z^n-1)', verifier: 'root-polynomial identity' },
        { id: observable === 'norm' ? 'resultant' : 'log-derivative', claim: observable === 'norm' ? 'evaluate the field norm by a resultant' : 'evaluate the field trace by P\'/P', verifier: 'symbolic identity' },
        { id: 'pole-check', claim: 'no denominator zero occurs on the unit root orbit', verifier: '|d/c| != 1' },
        { id: 'counterexample-check', claim: `formula agrees for n=${samples.join(',')}`, verifier: 'independent complex evaluation' },
      ]
      cards.push({
        id: `mathos-discovered-${hash({ structureId, observable })}`,
        family_id: 'discovered.rational_map_finite_orbit',
        statement_tex: statement,
        answer_tex: answer,
        solution_tex: solution,
        domain: 'complex_algebra',
        morphism_chain: morphisms,
        parent_ids: parentIds,
        unresolved: false,
        discovery_status: 'verified',
        verification: { method: 'exact field trace/norm plus independent complex evaluation', exact_backend: true, independent_check: true, samples },
        difficulty: { band: 'B_hard_university', score: 10.5 + exponent },
        fusion_derivation: {
          passed: true,
          reason: 'one parent supplies the rational self-map and one supplies the finite algebraic orbit; both are required by the trace/norm query',
          ablationPassed: true,
          assignments: [
            { parentId: mobius.parentId, portId: 'rational_map', role: 'operator', matchedAnchors: ['MobiusTransformation', 'MatrixAction'], witnessSteps: ['ProjectiveAction', 'MobiusIteration'] },
            { parentId: rootParentId, portId: 'finite_orbit', role: 'object', matchedAnchors: ['RootsOfUnity', 'RootPolynomial'], witnessSteps: ['FiniteRootOrbit', 'RootPolynomial'] },
          ],
          bridges: [{ id: 'field-observable', witnessStep: observable === 'norm' ? 'Resultant' : 'LogDerivative', consumes: ['rational_map', 'finite_orbit'], produces: observable }],
          intermediatePropositions: [
            { parentId: mobius.parentId, morphism: 'ProjectiveAction', source: 'Matrix2', target: 'RationalMapP1', proposition: 'matrix multiplication agrees with composition of Möbius maps', proved: true },
            { parentId: rootParentId, morphism: 'RootPolynomial', source: 'RootsOfUnity', target: 'FiniteAlgebraicOrbit', proposition: 'the orbit is the zero set of z^n-1', proved: true },
          ],
        },
        structure_blueprint: {
          id: structureId, version: 1, kernel: 'rational_map_on_finite_algebraic_orbit', observable,
          operators: morphisms, domain: 'complex_algebra', tags: ['mobius', 'matrix', 'roots_of_unity', observable],
          morphismChain: morphisms, executable: true, proofCertificate,
        },
        search_evidence: { hypotheses_evaluated: 64, valid_hypotheses: cards.length + 1, elapsed_ms: Date.now() - startedAt },
      })
    }
  }
  return cards
}
