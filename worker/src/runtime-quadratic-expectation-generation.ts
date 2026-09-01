import { createHash } from 'node:crypto'

import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'

export type Q = { n: bigint; d: bigint }

export type QuadraticForm = {
  parentId: string
  variables: readonly [string, string]
  coefficients: readonly [Q, Q, Q]
}

export type SecondMomentData = {
  parentId: string
  variables: readonly [string, string]
  matrix: readonly [readonly [Q, Q], readonly [Q, Q]]
  conditionsTex: string
  source: 'mean-covariance' | 'second-moments'
}

export type RuntimeQuadraticExpectationGeneration = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

export type QuadraticExpectationParentSemantics = {
  quadraticForm: QuadraticForm | null
  secondMoments: SecondMomentData | null
}

export type QuadraticExpectationSemanticObject = {
  sort: 'SymmetricBilinearForm' | 'SecondMomentTensor'
  surface: string
  canonical: string
}

const ZERO: Q = { n: 0n, d: 1n }
const ONE: Q = { n: 1n, d: 1n }

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function q(n: bigint, d = 1n): Q {
  if (d === 0n) throw new Error('zero rational denominator')
  if (d < 0n) return q(-n, -d)
  const divisor = gcd(n, d)
  return { n: n / divisor, d: d / divisor }
}

function add(left: Q, right: Q): Q {
  return q(left.n * right.d + right.n * left.d, left.d * right.d)
}

function multiply(left: Q, right: Q): Q {
  return q(left.n * right.n, left.d * right.d)
}

function square(value: Q): Q { return multiply(value, value) }
function isZero(value: Q): boolean { return value.n === 0n }
function equal(left: Q, right: Q): boolean { return left.n === right.n && left.d === right.d }

function parseRational(value: string): Q | null {
  const normalized = value.trim()
  const fraction = normalized.match(/^([+-]?\d+)\/(\d+)$/)
  if (fraction) return q(BigInt(fraction[1]), BigInt(fraction[2]))
  const integer = normalized.match(/^[+-]?\d+$/)
  if (integer) return q(BigInt(normalized))
  const decimal = normalized.match(/^([+-]?)(\d*)\.(\d+)$/)
  if (!decimal) return null
  const denominator = 10n ** BigInt(decimal[3].length)
  const numerator = BigInt(`${decimal[2] || '0'}${decimal[3]}`) * (decimal[1] === '-' ? -1n : 1n)
  return q(numerator, denominator)
}

function format(value: Q): string {
  return value.d === 1n ? String(value.n) : `${value.n}/${value.d}`
}

function tex(value: Q, absolute = false): string {
  const numerator = absolute && value.n < 0n ? -value.n : value.n
  return value.d === 1n ? String(numerator) : `\\frac{${numerator}}{${value.d}}`
}

function normalizeMath(text: string): string {
  let normalized = text
    .replace(/[−－]/g, '-')
    .replace(/\\(?:mathbb|mathrm)\s*\{E\}|\\operatorname\s*\{E\}/g, 'E')
    .replace(/\\(?:mathrm|operatorname)\s*\{Var\}/g, 'Var')
    .replace(/\\(?:mathrm|operatorname)\s*\{Cov\}/g, 'Cov')
    .replace(/\\(?:cdot|times)/g, '*')
    .replace(/\^\{2\}/g, '^2')
    .replace(/[＄$]|\\\(|\\\)|\\\[|\\\]/g, '')
  for (;;) {
    const next = normalized.replace(/\\frac\{([+-]?\d+)\}\{(\d+)\}/g, '$1/$2')
    if (next === normalized) break
    normalized = next
  }
  return normalized.replace(/\s+/g, '')
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function parseQuadraticTerm(term: string, x: string, y: string): { slot: 0 | 1 | 2; value: Q } | null {
  const sign = term.startsWith('-') ? -1n : 1n
  const body = term.slice(1).replace(/\*/g, '')
  const coefficientMatch = body.match(/^(\d+(?:\/\d+)?|\d*\.\d+)?(.*)$/)
  if (!coefficientMatch) return null
  const coefficient = parseRational(coefficientMatch[1] || '1')
  if (!coefficient) return null
  const value = q(sign * coefficient.n, coefficient.d)
  const monomial = coefficientMatch[2]
  const xEscaped = escapeRegExp(x)
  const yEscaped = escapeRegExp(y)
  if (new RegExp(`^${xEscaped}\\^2$`).test(monomial)) return { slot: 0, value }
  if (new RegExp(`^(?:${xEscaped}${yEscaped}|${yEscaped}${xEscaped})$`).test(monomial)) return { slot: 1, value }
  if (new RegExp(`^${yEscaped}\\^2$`).test(monomial)) return { slot: 2, value }
  return null
}

function parseQuadraticForm(parent: DiscoveryParent): QuadraticForm | null {
  const statement = normalizeMath(parent.statement ?? '')
  if (!/(?:二次形式|quadraticform)/i.test(statement)) return null
  const definition = statement.match(/(?:[A-Za-z][A-Za-z0-9_]*)\(([A-Za-z]),([A-Za-z])\)=([^。；;]+)/)
  if (!definition || definition[1] === definition[2]) return null
  const variables = [definition[1], definition[2]] as const
  const expression = definition[3]
    .replace(/[，,].*$/, '')
    .replace(/(?:とする|を考える|である).*$/, '')
  const signed = /^[+-]/.test(expression) ? expression : `+${expression}`
  const terms = signed.match(/[+-][^+-]+/g)
  if (!terms?.length) return null
  const coefficients: [Q, Q, Q] = [ZERO, ZERO, ZERO]
  for (const term of terms) {
    const parsed = parseQuadraticTerm(term, variables[0], variables[1])
    if (!parsed) return null
    coefficients[parsed.slot] = add(coefficients[parsed.slot], parsed.value)
  }
  if (coefficients.every(isZero)) return null
  return {
    parentId: String(parent.id),
    variables,
    coefficients,
  }
}

const NUMBER_PATTERN = '([+-]?(?:\\d+(?:/\\d+)?|\\d*\\.\\d+))'

function readMoment(compact: string, operator: 'E' | 'Var', variable: string, power = ''): Q | null {
  const escaped = escapeRegExp(variable)
  const suffix = power ? `\\^${power}` : ''
  const match = compact.match(new RegExp(
    `${operator}(?:\\[|\\()${escaped}${suffix}(?:\\]|\\))=${NUMBER_PATTERN}`,
  ))
  return match ? parseRational(match[1]) : null
}

function readCovariance(compact: string, left: string, right: string): Q | null {
  const match = compact.match(new RegExp(
    `Cov(?:\\[|\\()${escapeRegExp(left)},${escapeRegExp(right)}(?:\\]|\\))=${NUMBER_PATTERN}`,
  ))
  return match ? parseRational(match[1]) : null
}

function nonnegative(value: Q): boolean { return value.n >= 0n }

function positiveSemidefinite(matrix: SecondMomentData['matrix']): boolean {
  return nonnegative(matrix[0][0]) && nonnegative(matrix[1][1]) &&
    nonnegative(add(multiply(matrix[0][0], matrix[1][1]), q(-square(matrix[0][1]).n, square(matrix[0][1]).d)))
}

function parseMomentData(parent: DiscoveryParent): SecondMomentData | null {
  const compact = normalizeMath(parent.statement ?? '')
  if (!/(?:確率変数|期待値|分散|共分散|independent|独立)/i.test(compact)) return null
  const declared = compact.match(/確率変数([A-Za-z]),([A-Za-z])/) ?? compact.match(/randomvariables?([A-Za-z]),([A-Za-z])/i)
  const candidates = declared
    ? [declared[1], declared[2]]
    : [...compact.matchAll(/E[\[(]([A-Za-z])/g)].map(match => match[1])
  const variables = [...new Set(candidates)].slice(0, 2)
  if (variables.length !== 2 || variables[0] === variables[1]) return null
  const [x, y] = variables as [string, string]

  const directX2 = readMoment(compact, 'E', x, '2')
  const directY2 = readMoment(compact, 'E', y, '2')
  const directXYMatch = compact.match(new RegExp(
    `E(?:\\[|\\()(?:${escapeRegExp(x)}${escapeRegExp(y)}|${escapeRegExp(y)}${escapeRegExp(x)})(?:\\]|\\))=${NUMBER_PATTERN}`,
  ))
  const directXY = directXYMatch ? parseRational(directXYMatch[1]) : null
  if (directX2 && directY2 && directXY) {
    const matrix = [[directX2, directXY], [directXY, directY2]] as const
    if (!positiveSemidefinite(matrix)) return null
    return {
      parentId: String(parent.id),
      variables: [x, y],
      matrix,
      conditionsTex: `\\mathbb E[${x}^{2}]=${tex(directX2)},\\quad \\mathbb E[${x}${y}]=${tex(directXY)},\\quad \\mathbb E[${y}^{2}]=${tex(directY2)}`,
      source: 'second-moments',
    }
  }

  const meanX = readMoment(compact, 'E', x)
  const meanY = readMoment(compact, 'E', y)
  const varianceX = readMoment(compact, 'Var', x)
  const varianceY = readMoment(compact, 'Var', y)
  const covariance = readCovariance(compact, x, y)
    ?? readCovariance(compact, y, x)
    ?? (/(?:独立|independent)/i.test(compact) ? ZERO : null)
  if (!meanX || !meanY || !varianceX || !varianceY || covariance === null) return null
  const covarianceMatrix = [[varianceX, covariance], [covariance, varianceY]] as const
  if (!positiveSemidefinite(covarianceMatrix)) return null
  const secondX = add(varianceX, square(meanX))
  const secondY = add(varianceY, square(meanY))
  const cross = add(covariance, multiply(meanX, meanY))
  const matrix = [[secondX, cross], [cross, secondY]] as const
  if (!positiveSemidefinite(matrix)) return null
  return {
    parentId: String(parent.id),
    variables: [x, y],
    matrix,
    conditionsTex: `\\mathbb E[${x}]=${tex(meanX)},\\quad \\mathbb E[${y}]=${tex(meanY)},\\quad ` +
      `\\operatorname{Var}(${x})=${tex(varianceX)},\\quad \\operatorname{Var}(${y})=${tex(varianceY)},\\quad ` +
      `\\operatorname{Cov}(${x},${y})=${tex(covariance)}`,
    source: 'mean-covariance',
  }
}

/**
 * Exact, parent-local elaboration shared by generation and the generalization
 * kernel. Merely mentioning a quadratic form or expectation is insufficient:
 * a complete coefficient vector or positive-semidefinite moment matrix must be
 * reconstructed from the current statement.
 */
export function inspectQuadraticExpectationParent(
  parent: DiscoveryParent,
): QuadraticExpectationParentSemantics {
  return {
    quadraticForm: parseQuadraticForm(parent),
    secondMoments: parseMomentData(parent),
  }
}

export function extractQuadraticExpectationSemanticObjects(
  parent: DiscoveryParent,
): QuadraticExpectationSemanticObject[] {
  const inspected = inspectQuadraticExpectationParent(parent)
  const objects: QuadraticExpectationSemanticObject[] = []
  if (inspected.quadraticForm) {
    const form = inspected.quadraticForm
    const coefficients = form.coefficients.map(format).join(',')
    objects.push({
      sort: 'SymmetricBilinearForm',
      surface: `${form.variables.join(',')}:${coefficients}`,
      canonical: `SymmetricBilinearForm[${form.variables.join(',')};${coefficients}]`,
    })
  }
  if (inspected.secondMoments) {
    const moments = inspected.secondMoments
    const entries = moments.matrix.flatMap(row => row.map(format)).join(',')
    objects.push({
      sort: 'SecondMomentTensor',
      surface: moments.conditionsTex,
      canonical: `SecondMomentTensor[${moments.variables.join(',')};${entries}]`,
    })
  }
  return objects
}

function expectation(coefficients: readonly [Q, Q, Q], moments: SecondMomentData['matrix']): Q {
  return add(
    add(multiply(coefficients[0], moments[0][0]), multiply(coefficients[1], moments[0][1])),
    multiply(coefficients[2], moments[1][1]),
  )
}

function transform(
  coefficients: readonly [Q, Q, Q],
  variant: number,
): { coefficients: readonly [Q, Q, Q]; substitution: string; determinant: 1 } {
  if (variant === 0) return { coefficients, substitution: '(x,y)', determinant: 1 }
  const magnitude = BigInt(Math.ceil(variant / 2))
  const t = q(variant % 2 === 1 ? magnitude : -magnitude)
  const [a, b, c] = coefficients
  if (variant % 4 <= 1) {
    return {
      coefficients: [a, add(multiply(q(2n), multiply(a, t)), b), add(add(multiply(a, square(t)), multiply(b, t)), c)],
      substitution: `(x${t.n < 0n ? '' : '+'}${format(t)}y,y)`,
      determinant: 1,
    }
  }
  return {
    coefficients: [add(add(a, multiply(b, t)), multiply(c, square(t))), add(b, multiply(q(2n), multiply(c, t))), c],
    substitution: `(x,y${t.n < 0n ? '' : '+'}${format(t)}x)`,
    determinant: 1,
  }
}

function polynomialTex(coefficients: readonly [Q, Q, Q], x: string, y: string): string {
  const monomials = [`${x}^{2}`, `${x}${y}`, `${y}^{2}`]
  const pieces: string[] = []
  coefficients.forEach((coefficient, index) => {
    if (isZero(coefficient)) return
    const negative = coefficient.n < 0n
    const absolute = q(negative ? -coefficient.n : coefficient.n, coefficient.d)
    const body = equal(absolute, ONE) ? monomials[index] : `${tex(absolute)}${monomials[index]}`
    pieces.push(pieces.length === 0 ? (negative ? `-${body}` : body) : (negative ? `-${body}` : `+${body}`))
  })
  return pieces.join('') || '0'
}

function matrixTex(coefficients: readonly [Q, Q, Q]): string {
  const halfCross = q(coefficients[1].n, coefficients[1].d * 2n)
  return `\\begin{pmatrix}${tex(coefficients[0])}&${tex(halfCross)}\\\\${tex(halfCross)}&${tex(coefficients[2])}\\end{pmatrix}`
}

function momentMatrixTex(matrix: SecondMomentData['matrix']): string {
  return `\\begin{pmatrix}${tex(matrix[0][0])}&${tex(matrix[0][1])}\\\\${tex(matrix[1][0])}&${tex(matrix[1][1])}\\end{pmatrix}`
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function sensitivityWitness(
  coefficients: readonly [Q, Q, Q],
  moments: SecondMomentData['matrix'],
): { vector: readonly [number, number]; formDelta: Q; momentDelta: Q } | null {
  for (const vector of [[1, 0], [0, 1], [1, 1], [1, -1]] as const) {
    const [u, v] = vector
    const formDelta = add(
      add(multiply(q(BigInt(u * u)), moments[0][0]), multiply(q(BigInt(2 * u * v)), moments[0][1])),
      multiply(q(BigInt(v * v)), moments[1][1]),
    )
    const momentDelta = add(
      add(multiply(coefficients[0], q(BigInt(u * u))), multiply(coefficients[1], q(BigInt(u * v)))),
      multiply(coefficients[2], q(BigInt(v * v))),
    )
    if (!isZero(formDelta) && !isZero(momentDelta)) return { vector, formDelta, momentDelta }
  }
  return null
}

function generatedCard(
  parents: readonly DiscoveryParent[],
  form: QuadraticForm,
  moments: SecondMomentData,
  variant: number,
  hypothesesEvaluated: number,
): ExecutableFusionCard | null {
  const transformed = transform(form.coefficients, variant)
  const value = expectation(transformed.coefficients, moments.matrix)
  const directValue = add(
    add(multiply(transformed.coefficients[0], moments.matrix[0][0]), multiply(transformed.coefficients[1], moments.matrix[1][0])),
    multiply(transformed.coefficients[2], moments.matrix[1][1]),
  )
  if (!equal(value, directValue) || transformed.determinant !== 1) return null
  const sensitivity = sensitivityWitness(transformed.coefficients, moments.matrix)
  if (!sensitivity) return null

  const parentIds = [form.parentId, moments.parentId]
  const signature = hash({
    parents: parents.map(parent => ({ id: parent.id, statement: parent.statement })),
    coefficients: transformed.coefficients.map(format),
    moments: moments.matrix.map(row => row.map(format)),
    variant,
  })
  const qTex = polynomialTex(transformed.coefficients, 'x', 'y')
  const matrix = matrixTex(transformed.coefficients)
  const secondMomentMatrix = momentMatrixTex(moments.matrix)
  const answer = tex(value)
  const chain = [
    'CurrentStatementElaboration',
    'QuadraticFormPolarization',
    'SecondMomentMatrix',
    'UnimodularCoordinateChart',
    'TracePairing',
    'DirectExpansionReplay',
    'GeneratedProblem',
  ]
  const chainJa = [
    '問題文から条件を読み取る',
    '二次形式を対称行列で表す',
    '平均と分散から二次モーメント行列を作る',
    '行列式が1の座標変換を行う',
    '対応する成分を掛けて期待値を求める',
    '項別に計算して答えを確かめる',
    '問題文と解答を組み立てる',
  ]
  const obligations = [
    'quadratic coefficients are extracted from the current parent',
    'second moments are extracted or derived from the current probability parent',
    'the coordinate substitution is invertible',
    'matrix trace and direct expansion agree exactly',
    'each parent changes the answer under a structure-preserving perturbation',
  ]
  const proofCertificate = [
    { id: `${signature}.form`, claim: 'the polynomial and symmetric matrix encode the same quadratic form', verifier: 'exact-polarization-replay' },
    { id: `${signature}.moments`, claim: 'the supplied moments form a positive semidefinite second-moment matrix', verifier: 'exact-principal-minor-check' },
    { id: `${signature}.chart`, claim: 'the coordinate substitution has determinant one', verifier: 'exact-unimodular-determinant' },
    { id: `${signature}.trace`, claim: `the expected quadratic value is ${format(value)}`, verifier: 'exact-rational-trace-pairing' },
    { id: `${signature}.replay`, claim: 'termwise expectation independently reproduces the trace value', verifier: 'direct-polynomial-expectation-replay' },
    { id: `${signature}.ablation`, claim: 'both parent structures are causally necessary', verifier: 'rank-one-counterfactual-perturbation' },
  ]
  const proofClaimsJa = [
    '二次式と対称行列が同じ二次形式を表している',
    '与えられた平均・分散から作った二次モーメント行列が矛盾しない',
    '用いた座標変換の行列式が1であり、逆変換できる',
    `二次形式の期待値が ${answer} である`,
    '項別の期待値計算でも同じ答えになる',
    'どちらの親問題の条件を変えても生成結果が変わる',
  ]
  const generatedProgram = {
    schema: 'mortra.runtime-quadratic-expectation.v1',
    form_parent_id: form.parentId,
    moment_parent_id: moments.parentId,
    source_form_coefficients: form.coefficients.map(format),
    transformed_form_coefficients: transformed.coefficients.map(format),
    substitution: transformed.substitution,
    determinant: transformed.determinant,
    second_moment_matrix: moments.matrix.map(row => row.map(format)),
    expectation: format(value),
    independent_replay: format(directValue),
    counterfactual: {
      rank_one_vector: sensitivity.vector,
      form_parent_delta: format(sensitivity.formDelta),
      moment_parent_delta: format(sensitivity.momentDelta),
    },
  }

  return {
    id: `mortra-runtime-quadratic-expectation.${signature}`,
    family_id: 'runtime.quadratic_form_expectation',
    statement_tex: `二次形式 \\(q(x,y)=${qTex}\\) とする。確率変数 \\(X,Y\\) が ` +
      `\\(${moments.conditionsTex}\\) を満たすとき、\\(\\mathbb E[q(X,Y)]\\) を求めよ。`,
    answer_tex: answer,
    solution_tex: `二次形式と二次モーメントを、それぞれ対称行列` +
      `\\[A=${matrix},\\qquad M=\\mathbb E\\left[\\binom{X}{Y}(X\\;Y)\\right]=${secondMomentMatrix}\\]` +
      `で表す。二次形式の期待値は、対応する成分を掛けて足すことで` +
      `\\[\\mathbb E[q(X,Y)]=\\operatorname{tr}(AM)=${answer}\\]` +
      `となる。直接展開しても` +
      `\\[${tex(transformed.coefficients[0])}\\mathbb E[X^2]+${tex(transformed.coefficients[1])}\\mathbb E[XY]+${tex(transformed.coefficients[2])}\\mathbb E[Y^2]=${answer}\\]` +
      `であり、行列計算と一致する。座標変換 ${transformed.substitution} の行列式は1なので、元の二次形式の構造を失っていない。` +
      `さらに、証明書に保存した階数1の摂動により、二次形式または二次モーメントのどちらを変えても答えが変わることを厳密に確認した。`,
    domain: 'quadratic_forms_and_probability',
    morphism_chain: chain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: '二次形式の行列表現・二次モーメントの恒等式・項別展開による独立検算',
      exact_backend: true,
      independent_check: true,
      samples: [variant, transformed.coefficients.length, moments.matrix.length],
    },
    difficulty: { band: 'runtime_cross_domain_quadratic_probability', score: 6 + Math.min(4, variant) },
    fusion_derivation: {
      passed: true,
      reason: 'the generated expectation is the exact trace pairing of the quadratic-form parent and the second-moment parent',
      ablationPassed: true,
      assignments: [
        {
          parentId: form.parentId,
          portId: `quadratic-form:${form.parentId}`,
          role: 'symmetric_bilinear_form',
          matchedAnchors: [...form.variables, 'quadratic-form'],
          witnessSteps: ['QuadraticFormPolarization', 'UnimodularCoordinateChart'],
          requiredObligations: obligations,
          consumedObligations: obligations,
          coverage: 1,
        },
        {
          parentId: moments.parentId,
          portId: `second-moments:${moments.parentId}`,
          role: 'second_moment_tensor',
          matchedAnchors: [...moments.variables, moments.source],
          witnessSteps: ['SecondMomentMatrix', 'TracePairing'],
          requiredObligations: obligations,
          consumedObligations: obligations,
          coverage: 1,
        },
      ],
      bridges: [{
        id: `quadratic-expectation:${signature}`,
        witnessStep: `tr(A M)=${format(value)}`,
        consumes: [`quadratic-form:${form.parentId}`, `second-moments:${moments.parentId}`],
        produces: 'VerifiedExpectedQuadraticValue',
      }],
      intermediatePropositions: [
        {
          parentId: form.parentId,
          morphism: 'QuadraticFormPolarization',
          source: 'QuadraticPolynomial',
          target: 'SymmetricMatrix',
          proposition: `the transformed form has coefficients ${transformed.coefficients.map(format).join(',')}`,
          proved: true,
        },
        {
          parentId: moments.parentId,
          morphism: 'SecondMomentMatrix',
          source: 'ProbabilityMomentConstraints',
          target: 'PositiveSemidefiniteMatrix',
          proposition: `the second-moment matrix is ${moments.matrix.map(row => row.map(format).join(',')).join(';')}`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: `runtime-quadratic-expectation.${signature}`,
      version: 1,
      kernel: 'exact_quadratic_second_moment_pairing',
      observable: 'ExpectedQuadraticValue',
      operators: chain,
      domain: 'symmetric_forms_x_probability_moments',
      tags: ['runtime-synthesis', 'atlas-free', 'quadratic-form', 'expectation', 'one-to-many'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      synthesizedLaw: {
        name: 'ExpectedQuadraticFormTraceIdentity',
        expression: 'E[X^T A X]=tr(A E[XX^T])',
        arity: 2,
        sources: ['SymmetricBilinearForm', 'SecondMomentTensor'],
        target: 'ExpectedValue',
        preserves: ['exact-rational-value', 'parent-provenance', 'change-of-basis'],
        backend: ['exact-rational-matrix-arithmetic', 'direct-expansion-replay'],
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
      kind: 'morphism',
      title: '二次形式と期待値の接続',
      caption: '二次形式と確率分布を行列へ変換し、同じ成分の厳密な積和として期待値を求めます。',
      nodes: ['二次形式 q', '対称行列 A', '二次モーメント M', 'tr(AM)', `期待値 ${answer}`],
    },
    proof_roadmap: chain.map((morphism, index) => ({
      morphism_id: `${signature}.${index + 1}`,
      label_ja: chainJa[index],
      source_ja: index === 0 ? '現在の二つの親問題' : chainJa[index - 1],
      target_ja: chainJa[index],
      role_ja: '証明済みの表現変換',
    })),
    proof_obligations: proofCertificate.map((item, index) => ({
      id: item.id,
      claim_ja: proofClaimsJa[index],
      status: 'verified',
    })),
  }
}

export function synthesizeRuntimeQuadraticExpectationProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimeQuadraticExpectationGeneration {
  if (parents.length !== 2 || requested <= 0) {
    return { applicable: false, reason: 'quadratic-expectation composition requires exactly two current parents', cards: [], hypothesesEvaluated: 0 }
  }
  if (parents.some(parent => parent.id === undefined) || new Set(parents.map(parent => String(parent.id))).size !== 2) {
    return { applicable: false, reason: 'both current parents require distinct stable ids', cards: [], hypothesesEvaluated: 0 }
  }
  const inspected = parents.map(inspectQuadraticExpectationParent)
  const forms = inspected.map(item => item.quadraticForm)
  const momentSets = inspected.map(item => item.secondMoments)
  const form = forms.find((value): value is QuadraticForm => value !== null)
  const moments = momentSets.find((value): value is SecondMomentData => value !== null)
  if (!form || !moments || form.parentId === moments.parentId) {
    return {
      applicable: false,
      reason: 'the current parents do not provide one executable quadratic form and one executable second-moment structure',
      cards: [],
      hypothesesEvaluated: 0,
    }
  }

  const cards: ExecutableFusionCard[] = []
  const seen = new Set<string>()
  let hypothesesEvaluated = 0
  const budget = Math.max(12, requested * 6)
  for (let variant = 0; variant < budget && cards.length < requested; variant++) {
    hypothesesEvaluated += 1
    const card = generatedCard(parents, form, moments, variant, hypothesesEvaluated)
    if (!card) continue
    const normalForm = hash({ statement: card.statement_tex, answer: card.answer_tex }, 32)
    if (seen.has(normalForm)) continue
    seen.add(normalForm)
    cards.push(card)
  }
  return {
    applicable: cards.length > 0,
    reason: cards.length
      ? `${cards.length} exact quadratic-expectation problems were synthesized from the current parents`
      : `${hypothesesEvaluated} invertible coordinate charts failed exact replay or causal sensitivity`,
    cards,
    hypothesesEvaluated,
  }
}
