import { createHash } from 'node:crypto'
import type { ProblemDiagram } from './problem-artifact'

type FusionOperation = 'sum' | 'difference' | 'product'
type RootConfigurationObservable = 'trace_norm' | 'power_sums'

export type CertifiedFusionParent = {
  id: string
  statement: string
  answer?: string | null
  solution?: string | null
  certificate?: {
    verified: true
    id: string
    method?: string
  } | null
}

export type CertifiedProblemGenerationTraceNode = {
  id: string
  kind: 'premise' | 'derived' | 'bridge' | 'goal' | 'verification'
  label: string
  dependsOn: string[]
  parentIds: string[]
}

export type CertifiedProblemGenerationAudit = {
  schema: 1
  passed: boolean
  reversePlaybackOnly: boolean
  tracedParentIds: string[]
  minimalPremiseIds: string[]
  unusedPremiseIds: string[]
  proofStepCount: number
  checks: {
    exactSolvability: boolean
    independentVerification: boolean
    clauseCompleteness: boolean
    premiseMinimality: boolean
    allParentDependence: boolean
    crossParentComposition: boolean
    statementDiffersFromParents: boolean
    nontrivialProof: boolean
  }
  failures: string[]
  trace: CertifiedProblemGenerationTraceNode[]
}

type ParsedPolynomial = {
  parentId: string
  variable: string
  coefficients: bigint[]
  normalizedTex: string
}

export type CertifiedFusionCard = {
  id: string
  statement_tex: string
  answer_tex: string
  solution_tex: string
  solution_document_tex: string
  domain: string
  family_id: string
  tool: string
  morphism_chain: string[]
  proof_roadmap?: Array<{
    morphism_id: string
    label_ja: string
    source_ja: string
    target_ja: string
    role_ja: string
  }>
  proof_obligations?: Array<{
    id: string
    claim_ja: string
    status: 'verified'
  }>
  diagram: ProblemDiagram
  parent_ids: string[]
  verification: {
    method: string
    exact_backend: true
    independent_check: true
    samples: number[]
  }
  difficulty: { band: string; score: number }
  fusion_derivation: {
    passed: true
    reason: string
    ablationPassed: true
    assignments: Array<{
      parentId: string
      portId: string
      role: string
      matchedAnchors: string[]
      witnessSteps: string[]
    }>
    bridges: Array<{ id: string; witnessStep: string; consumes: string[]; produces: string }>
    intermediatePropositions: Array<{
      parentId: string
      morphism: string
      source: string
      target: string
      proposition: string
      proved: true
    }>
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
    structuralUniqueness: {
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
  search_evidence: {
    hypotheses_evaluated: number
    valid_hypotheses: number
    elapsed_ms: number
  }
  generation_audit?: CertifiedProblemGenerationAudit
}

type PolyZ = bigint[]

function trim(values: bigint[]): bigint[] {
  const result = [...values]
  while (result.length > 1 && result.at(-1) === 0n) result.pop()
  return result.length ? result : [0n]
}

function add(left: PolyZ, right: PolyZ): PolyZ {
  const size = Math.max(left.length, right.length)
  return trim(Array.from({ length: size }, (_, index) => (left[index] ?? 0n) + (right[index] ?? 0n)))
}

function scale(value: PolyZ, factor: bigint): PolyZ {
  return trim(value.map(coefficient => coefficient * factor))
}

function multiply(left: PolyZ, right: PolyZ): PolyZ {
  const result = Array<bigint>(left.length + right.length - 1).fill(0n)
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) result[i + j] += left[i] * right[j]
  }
  return trim(result)
}

function binomial(n: number, k: number): bigint {
  if (k < 0 || k > n) return 0n
  let value = 1n
  for (let index = 1; index <= Math.min(k, n - k); index += 1) {
    value = value * BigInt(n - index + 1) / BigInt(index)
  }
  return value
}

function extractEquation(statement: string): string | null {
  const withoutTextCommands = statement
    .replace(/\\text\s*\{[^{}]*\}/g, '')
    .replace(/\\operatorname\s*\{[^{}]*\}/g, '')
  const segments = [
    ...Array.from(statement.matchAll(/\$([^$]+)\$/g), match => match[1]),
    ...Array.from(statement.matchAll(/\\\(([^]*?)\\\)/g), match => match[1]),
    ...Array.from(statement.matchAll(/\\\[([^]*?)\\\]/g), match => match[1]),
    withoutTextCommands,
  ]
  return segments.find(segment => /[^=<>]+=[^=<>]+/.test(segment)) ?? null
}

function normalizeExpression(expression: string): string | null {
  const normalized = expression
    .replace(/\\left|\\right/g, '')
    .replace(/−|–/g, '-')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/\^\s*\{\s*(\d+)\s*\}/g, '^$1')
    .replace(/[{}\s]/g, '')
  if (/\\(?:d?frac|sqrt)|[()/]/.test(normalized)) return null
  return normalized
}

function parseSide(expression: string, variable: string): bigint[] | null {
  const normalized = normalizeExpression(expression)
  if (!normalized) return null
  const terms = normalized.replace(/-/g, '+-').split('+').filter(Boolean)
  const coefficients: bigint[] = [0n]
  for (const rawTerm of terms) {
    const term = rawTerm.replace(/\*/g, '')
    if (!term.includes(variable)) {
      if (!/^[+-]?\d+$/.test(term)) return null
      coefficients[0] = (coefficients[0] ?? 0n) + BigInt(term)
      continue
    }
    const match = term.match(new RegExp(`^([+-]?\\d*)${variable}(?:\\^(\\d+))?$`))
    if (!match) return null
    const coefficient = match[1] === '' || match[1] === '+'
      ? 1n
      : match[1] === '-'
        ? -1n
        : BigInt(match[1])
    const exponent = Number(match[2] ?? 1)
    if (!Number.isInteger(exponent) || exponent < 0 || exponent > 6) return null
    while (coefficients.length <= exponent) coefficients.push(0n)
    coefficients[exponent] += coefficient
  }
  return trim(coefficients)
}

function polynomialTex(coefficients: bigint[], variable = 'x'): string {
  const terms: string[] = []
  for (let exponent = coefficients.length - 1; exponent >= 0; exponent -= 1) {
    const coefficient = coefficients[exponent]
    if (coefficient === 0n) continue
    const sign = coefficient < 0n ? '-' : '+'
    const absolute = coefficient < 0n ? -coefficient : coefficient
    const magnitude = exponent > 0 && absolute === 1n ? '' : absolute.toString()
    const power = exponent === 0 ? '' : exponent === 1 ? variable : `${variable}^{${exponent}}`
    const body = `${magnitude}${power}`
    if (!terms.length) terms.push(sign === '-' ? `-${body}` : body)
    else terms.push(`${sign}${body}`)
  }
  return terms.join('') || '0'
}

export function parseMonicIntegerPolynomial(parent: CertifiedFusionParent): ParsedPolynomial | null {
  const equation = extractEquation(parent.statement)
  if (!equation) return null
  const match = equation.match(/([^=<>]+)=([^=<>]+)/)
  if (!match) return null
  const variables = new Set(`${match[1]}${match[2]}`.match(/[A-Za-z]/g) ?? [])
  if (variables.size !== 1) return null
  const variable = [...variables][0]
  const left = parseSide(match[1], variable)
  const right = parseSide(match[2], variable)
  if (!left || !right) return null
  const coefficients = trim(Array.from(
    { length: Math.max(left.length, right.length) },
    (_, index) => (left[index] ?? 0n) - (right[index] ?? 0n),
  ))
  if (coefficients.length < 3 || coefficients.length > 5) return null
  const leading = coefficients.at(-1)
  const monic = leading === -1n ? coefficients.map(value => -value) : coefficients
  if (monic.at(-1) !== 1n) return null
  return {
    parentId: parent.id,
    variable,
    coefficients: monic,
    normalizedTex: polynomialTex(monic, variable),
  }
}

function powerSums(polynomial: bigint[], maximum: number): bigint[] {
  const degree = polynomial.length - 1
  const descending = [...polynomial].reverse()
  const sums = Array<bigint>(maximum + 1).fill(0n)
  sums[0] = BigInt(degree)
  for (let order = 1; order <= maximum; order += 1) {
    let value = 0n
    for (let index = 1; index <= Math.min(order - 1, degree); index += 1) {
      value += descending[index] * sums[order - index]
    }
    if (order <= degree) value += BigInt(order) * descending[order]
    sums[order] = -value
  }
  return sums
}

function composedPowerSums(left: bigint[], right: bigint[], operation: FusionOperation): bigint[] {
  const totalDegree = (left.length - 1) * (right.length - 1)
  const leftSums = powerSums(left, totalDegree)
  const rightSums = powerSums(right, totalDegree)
  const result = Array<bigint>(totalDegree + 1).fill(0n)
  result[0] = BigInt(totalDegree)
  for (let order = 1; order <= totalDegree; order += 1) {
    if (operation === 'product') {
      result[order] = leftSums[order] * rightSums[order]
      continue
    }
    for (let leftOrder = 0; leftOrder <= order; leftOrder += 1) {
      const rightOrder = order - leftOrder
      const sign = operation === 'difference' && rightOrder % 2 === 1 ? -1n : 1n
      result[order] += sign * binomial(order, leftOrder) * leftSums[leftOrder] * rightSums[rightOrder]
    }
  }
  return result
}

function polynomialFromPowerSums(sums: bigint[]): bigint[] | null {
  const degree = sums.length - 1
  const descending = Array<bigint>(degree + 1).fill(0n)
  descending[0] = 1n
  for (let order = 1; order <= degree; order += 1) {
    let numerator = sums[order]
    for (let index = 1; index < order; index += 1) numerator += descending[index] * sums[order - index]
    const divisor = BigInt(order)
    if ((-numerator) % divisor !== 0n) return null
    descending[order] = -numerator / divisor
  }
  return trim(descending.reverse())
}

function substitutedPolynomial(polynomial: bigint[], operation: FusionOperation): PolyZ[] {
  const degree = polynomial.length - 1
  const coefficients = Array.from({ length: degree + 1 }, () => [0n] as PolyZ)
  for (let exponent = 0; exponent <= degree; exponent += 1) {
    const base = polynomial[exponent]
    if (base === 0n) continue
    if (operation === 'product') {
      const xExponent = degree - exponent
      const zExponent = exponent
      const term = Array<bigint>(zExponent + 1).fill(0n)
      term[zExponent] = base
      coefficients[xExponent] = add(coefficients[xExponent], term)
      continue
    }
    for (let xExponent = 0; xExponent <= exponent; xExponent += 1) {
      const zExponent = exponent - xExponent
      const parity = operation === 'sum' ? xExponent : zExponent
      const factor = parity % 2 === 0 ? 1n : -1n
      const term = Array<bigint>(zExponent + 1).fill(0n)
      term[zExponent] = base * binomial(exponent, xExponent) * factor
      coefficients[xExponent] = add(coefficients[xExponent], term)
    }
  }
  return coefficients.map(trim)
}

function determinant(matrix: PolyZ[][]): PolyZ {
  const size = matrix.length
  let states = new Map<number, PolyZ>([[0, [1n]]])
  for (let row = 0; row < size; row += 1) {
    const next = new Map<number, PolyZ>()
    for (const [mask, value] of states) {
      for (let column = 0; column < size; column += 1) {
        if (mask & (1 << column)) continue
        const inversions = Array.from({ length: size }, (_, index) => index)
          .filter(index => (mask & (1 << index)) !== 0 && index > column).length
        const signed = scale(multiply(value, matrix[row][column]), inversions % 2 === 0 ? 1n : -1n)
        const nextMask = mask | (1 << column)
        next.set(nextMask, add(next.get(nextMask) ?? [0n], signed))
      }
    }
    states = next
  }
  return trim(states.get((1 << size) - 1) ?? [0n])
}

function resultantPolynomial(left: bigint[], right: bigint[], operation: FusionOperation): PolyZ | null {
  const leftDegree = left.length - 1
  const rightInX = substitutedPolynomial(right, operation)
  const rightDegree = rightInX.length - 1
  const size = leftDegree + rightDegree
  if (size > 12) return null
  const leftDescending = [...left].reverse().map(value => [value] as PolyZ)
  const rightDescending = [...rightInX].reverse()
  const matrix = Array.from({ length: size }, () => Array.from({ length: size }, () => [0n] as PolyZ))
  for (let row = 0; row < rightDegree; row += 1) {
    for (let index = 0; index <= leftDegree; index += 1) matrix[row][row + index] = leftDescending[index]
  }
  for (let row = 0; row < leftDegree; row += 1) {
    for (let index = 0; index <= rightDegree; index += 1) matrix[rightDegree + row][row + index] = rightDescending[index]
  }
  const result = determinant(matrix)
  if (result.at(-1) === -1n) return result.map(value => -value)
  return result.at(-1) === 1n ? result : null
}

function equalPolynomial(left: bigint[], right: bigint[]): boolean {
  const a = trim(left)
  const b = trim(right)
  return a.length === b.length && a.every((value, index) => value === b[index])
}

function operationTex(operation: FusionOperation): string {
  if (operation === 'sum') return '\\alpha_i+\\beta_j'
  if (operation === 'difference') return '\\alpha_i-\\beta_j'
  return '\\alpha_i\\beta_j'
}

function operationJapanese(operation: FusionOperation): string {
  if (operation === 'sum') return '和'
  if (operation === 'difference') return '差'
  return '積'
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

function integerTex(value: bigint): string {
  return value < 0n ? `-${String(-value)}` : String(value)
}

function observableProjectionCard(
  base: CertifiedFusionCard,
  left: ParsedPolynomial,
  right: ParsedPolynomial,
  operation: FusionOperation,
  polynomial: bigint[],
  directPowerSums: bigint[],
  projection: RootConfigurationObservable,
  ordinal: number,
): CertifiedFusionCard | null {
  const degree = polynomial.length - 1
  const resultantPowerSums = powerSums(polynomial, Math.min(3, degree))
  if (!resultantPowerSums.every((value, index) => value === directPowerSums[index])) return null

  const observable = operationTex(operation)
  const rootSymbol = '\\gamma'
  const projectionMorphism = projection === 'trace_norm'
    ? 'VietaTraceNormProjection'
    : 'NewtonMomentProjection'
  const morphisms = [...base.morphism_chain, projectionMorphism]
  const projectionId = `${base.structure_blueprint.id}.${projection}`
  const proofCertificate = [
    ...base.structure_blueprint.proofCertificate,
    {
      id: projection,
      claim: projection === 'trace_norm'
        ? 'trace and norm agree between Vieta projection and the independently eliminated polynomial'
        : 'the first power sums agree between direct parent-moment composition and the independently eliminated polynomial',
      verifier: projection === 'trace_norm'
        ? 'BigInt Vieta coefficient projection + Sylvester resultant'
        : 'BigInt Newton recurrence on two independently constructed coefficient paths',
    },
  ]

  let statement: string
  let answer: string
  let solution: string
  let family: string
  let querySignature: string
  let observableName: string

  if (projection === 'trace_norm') {
    const trace = resultantPowerSums[1]
    const norm = degree % 2 === 0 ? polynomial[0] : -polynomial[0]
    statement = String.raw`\(f(x)=${polynomialTex(left.coefficients)}\), \(g(x)=${polynomialTex(right.coefficients)}\) とする。\(f\) の根を重複度込みで \(\alpha_1,\ldots,\alpha_${left.coefficients.length - 1}\)、\(g\) の根を \(\beta_1,\ldots,\beta_${right.coefficients.length - 1}\) とする。\(${rootSymbol}_{ij}=${observable}\) とおくとき、\[T=\sum_{i=1}^{${left.coefficients.length - 1}}\sum_{j=1}^{${right.coefficients.length - 1}}${rootSymbol}_{ij},\qquad N=\prod_{i=1}^{${left.coefficients.length - 1}}\prod_{j=1}^{${right.coefficients.length - 1}}${rootSymbol}_{ij}\]\(T,N\) を求めよ。`
    answer = String.raw`\(T=${integerTex(trace)},\quad N=${integerTex(norm)}\)`
    solution = String.raw`まず親問題の二つの根配置を ${operationJapanese(operation)}で合成する。直接Newton和を合成すると、第1べき和は \(T=${integerTex(directPowerSums[1])}\) となる。一方、同じ根配置を終結式で消去して得たモニック多項式は \[P(z)=${polynomialTex(polynomial, 'z')}\] である。Vietaの公式より、\(z^{${degree - 1}}\) の係数から \(T=${integerTex(trace)}\)、定数項から \(N=${integerTex(norm)}\) を得る。直接合成した第1べき和とVietaの値は一致する。`
    family = `certified.polynomial_root_${operation}_trace_norm`
    querySignature = `compute-trace-and-norm-of-root-${operation}-configuration`
    observableName = `root_multiset_${operation}_trace_norm`
  } else {
    const maximum = Math.min(3, degree)
    const moments = resultantPowerSums.slice(1, maximum + 1)
    const definitions = moments
      .map((_, index) => String.raw`s_${index + 1}=\sum_{i,j}${rootSymbol}_{ij}^{${index + 1}}`)
      .join(String.raw`,\qquad `)
    const values = moments
      .map((value, index) => String.raw`s_${index + 1}=${integerTex(value)}`)
      .join(String.raw`,\quad `)
    statement = String.raw`\(f(x)=${polynomialTex(left.coefficients)}\), \(g(x)=${polynomialTex(right.coefficients)}\) とする。\(f\) の根を重複度込みで \(\alpha_1,\ldots,\alpha_${left.coefficients.length - 1}\)、\(g\) の根を \(\beta_1,\ldots,\beta_${right.coefficients.length - 1}\) とし、\(${rootSymbol}_{ij}=${observable}\) とおく。\[${definitions}\]を求めよ。`
    answer = String.raw`\(${values}\)`
    solution = String.raw`各親多項式の係数からNewton和を求める。${operationJapanese(operation)}の二項展開を用いると、親のべき和だけから \[${values}\] を得る。独立検証として、終結式で \(\alpha_i,\beta_j\) を消去すると \[P(z)=${polynomialTex(polynomial, 'z')}\] となる。この係数列へNewtonの恒等式を適用しても同じ \(s_1,\ldots,s_${maximum}\) が得られる。`
    family = `certified.polynomial_root_${operation}_power_sums`
    querySignature = `compute-initial-power-sums-of-root-${operation}-configuration`
    observableName = `root_multiset_${operation}_initial_power_sums`
  }

  return {
    ...base,
    id: `mortra-${projectionId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    family_id: family,
    morphism_chain: morphisms,
    diagram: {
      version: 1,
      kind: 'morphism',
      title: projection === 'trace_norm' ? '合成根配置のトレースとノルム' : '合成根配置のべき和',
      caption: projection === 'trace_norm'
        ? '同じ有限根配置を、Newton和とVietaの係数射の二経路で読み取ります。'
        : '親のべき和を直接合成した値と、終結式の係数から再生した値を照合します。',
      nodes: morphisms,
    },
    verification: {
      ...base.verification,
      method: projection === 'trace_norm'
        ? 'exact parent power sums + independent Sylvester resultant + Vieta trace/norm projection'
        : 'exact parent power-sum composition + independent Sylvester resultant + Newton replay',
    },
    difficulty: {
      band: 'A_exact_algebraic_fusion',
      score: base.difficulty.score + (projection === 'trace_norm' ? 0.6 : 1.1),
    },
    structure_blueprint: {
      ...base.structure_blueprint,
      id: projectionId,
      observable: observableName,
      operators: morphisms,
      morphismChain: morphisms,
      tags: [...base.structure_blueprint.tags, projection === 'trace_norm' ? 'vieta-invariants' : 'newton-moments'],
      proofCertificate,
      structuralUniqueness: {
        ...base.structure_blueprint.structuralUniqueness,
        querySignature,
        normalForm: answer,
      },
    },
    search_evidence: {
      ...base.search_evidence,
      hypotheses_evaluated: base.search_evidence.hypotheses_evaluated + ordinal,
      valid_hypotheses: base.search_evidence.valid_hypotheses + ordinal,
    },
  }
}

export function synthesizeCertifiedPolynomialFusions(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const parsed = parents.map(parseMonicIntegerPolynomial)
  if (parsed.some(value => value === null)) return []
  const [left, right] = parsed as [ParsedPolynomial, ParsedPolynomial]
  const operations: FusionOperation[] = ['sum', 'product', 'difference']
  const cards: CertifiedFusionCard[] = []
  const composedConfigurations: Array<{
    operation: FusionOperation
    polynomial: bigint[]
    directPowerSums: bigint[]
    base: CertifiedFusionCard
  }> = []

  for (const operation of operations) {
    if (cards.length >= requested) break
    const directPowerSums = composedPowerSums(left.coefficients, right.coefficients, operation)
    const newton = polynomialFromPowerSums(directPowerSums)
    const resultant = resultantPolynomial(left.coefficients, right.coefficients, operation)
    if (!newton || !resultant || !equalPolynomial(newton, resultant)) continue

    const leftDegree = left.coefficients.length - 1
    const rightDegree = right.coefficients.length - 1
    const observable = operationTex(operation)
    const outputTex = polynomialTex(newton, 'z')
    const structureId = `certified-root-fusion.${operation}.${hash([
      left.coefficients.map(String), right.coefficients.map(String), operation,
    ])}`
    const morphisms = [
      'PolynomialElaboration',
      'RootConfiguration',
      operation === 'sum' ? 'RootMinkowskiSum' : operation === 'difference' ? 'RootMinkowskiDifference' : 'RootPointwiseProduct',
      'NewtonPowerSumElimination',
      'SylvesterResultantVerification',
      'AllParentAblation',
    ]
    const statement = String.raw`\(f(x)=${polynomialTex(left.coefficients)}\), \(g(x)=${polynomialTex(right.coefficients)}\) とする。\(f\) の根を重複度込みで \(\alpha_1,\ldots,\alpha_${leftDegree}\)、\(g\) の根を \(\beta_1,\ldots,\beta_${rightDegree}\) とする。次のモニック多項式を展開せよ。\[P(z)=\prod_{i=1}^{${leftDegree}}\prod_{j=1}^{${rightDegree}}\left(z-(${observable})\right)\]`
    const answer = String.raw`\(P(z)=${outputTex}\)`
    const eliminationInput = operation === 'sum'
      ? String.raw`\(g(z-x)\)`
      : operation === 'difference'
        ? String.raw`\(g(x-z)\)`
        : String.raw`\(x^{${rightDegree}}g(z/x)\)`
    const solution = String.raw`\(f,g\) の係数からNewton和を再帰的に求める。二項定理により、\(${observable}\) の第 \(k\) 乗和は両親のNewton和だけで表される。そこからNewtonの恒等式を逆向きに用いると \[P(z)=${outputTex}\] を得る。独立検証として、\(f(x)\) と ${eliminationInput} のSylvester行列式を整数係数で計算し、同じ係数列になることを確認した。`
    const proofCertificate = [
      { id: 'elaboration', claim: 'both selected parents elaborate to distinct monic integer polynomial constraints', verifier: 'MORTRA polynomial IR' },
      { id: 'newton', claim: 'the output coefficients follow from exact Newton sums', verifier: 'BigInt Newton identity kernel' },
      { id: 'resultant', claim: 'independent elimination yields the identical monic polynomial', verifier: 'BigInt Sylvester determinant' },
      { id: 'ablation', claim: 'both degree-at-least-two parent root configurations occupy indispensable input ports and determine the output degree product', verifier: 'typed all-parent cardinality check' },
    ]
    const base: CertifiedFusionCard = {
      id: `mortra-${structureId}`,
      statement_tex: statement,
      answer_tex: answer,
      solution_tex: solution,
      solution_document_tex: texDocument(statement, solution),
      domain: 'algebraic_geometry',
      family_id: `certified.polynomial_root_${operation}`,
      tool: 'MORTRA exact reversible synthesis',
      morphism_chain: morphisms,
      diagram: {
        version: 1,
        kind: 'morphism',
        title: '二つの根配置から一つの多項式へ',
        caption: '二つの親問題を別々の入力として保ち、根配置の二項演算をNewton和と終結式の二経路で検証します。',
        nodes: [`f の ${leftDegree} 根`, operationJapanese(operation), `g の ${rightDegree} 根`, 'Newton和', '終結式照合', `P(z)`],
      },
      parent_ids: [left.parentId, right.parentId],
      verification: {
        method: 'exact BigInt Newton sums + independent Sylvester resultant + all-parent dependency',
        exact_backend: true,
        independent_check: true,
        samples: [leftDegree, rightDegree, newton.length - 1],
      },
      difficulty: { band: 'A_exact_algebraic_fusion', score: 7 + (newton.length - 1) * 0.45 },
      fusion_derivation: {
        passed: true,
        reason: `each parent supplies an indispensable root configuration: output degree ${leftDegree * rightDegree} is the product of parent degrees ${leftDegree} and ${rightDegree}`,
        ablationPassed: true,
        assignments: [left, right].map((input, index) => ({
          parentId: input.parentId,
          portId: `root_configuration_${index + 1}`,
          role: 'object',
          matchedAnchors: [input.normalizedTex],
          witnessSteps: ['PolynomialElaboration', 'RootConfiguration'],
        })),
        bridges: [{
          id: `root-${operation}`,
          witnessStep: morphisms[2],
          consumes: ['root_configuration_1', 'root_configuration_2'],
          produces: 'composed_root_multiset',
        }],
        intermediatePropositions: [left, right].map(input => ({
          parentId: input.parentId,
          morphism: 'RootConfiguration',
          source: 'Polynomial',
          target: 'FiniteAlgebraicOrbit',
          proposition: `${input.normalizedTex}=0 defines a finite algebraic root multiset`,
          proved: true as const,
        })),
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: 'ReversiblePolynomialRootFusionIR',
        observable: `root_multiset_${operation}_polynomial`,
        operators: morphisms,
        domain: 'algebraic_geometry',
        tags: ['polynomial', 'root-configuration', operation, 'newton-sums', 'resultant', 'no-llm'],
        morphismChain: morphisms,
        executable: true,
        proofCertificate,
        structuralUniqueness: {
          schema: 1,
          conditionSkeleton: ['monic-polynomial-root-configuration', 'binary-root-operation'],
          querySignature: `expand-product-over-root-${operation}`,
          normalForm: outputTex,
          quotientAction: 'rename-bound-root-variables',
          freeParameters: ['parent polynomial coefficients'],
          uniqueNormalForm: true,
          finiteSolutionSet: true,
          numericInstanceConstants: [leftDegree, rightDegree],
          conditionAblationPassed: true,
        },
      },
      search_evidence: {
        hypotheses_evaluated: operations.indexOf(operation) + 1,
        valid_hypotheses: cards.length + 1,
        elapsed_ms: Date.now() - startedAt,
      },
    }
    cards.push(base)
    composedConfigurations.push({ operation, polynomial: newton, directPowerSums, base })
  }

  const projections: RootConfigurationObservable[] = ['trace_norm', 'power_sums']
  for (const projection of projections) {
    for (const configuration of composedConfigurations) {
      if (cards.length >= requested) return cards
      const projected = observableProjectionCard(
        configuration.base,
        left,
        right,
        configuration.operation,
        configuration.polynomial,
        configuration.directPowerSums,
        projection,
        cards.length + 1,
      )
      if (projected) cards.push(projected)
    }
  }
  return cards
}
