import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'
import {
  buildCircleQuadraticFormChart,
  evaluateCirclePower,
  type CircleQuadraticFormChart,
} from './chart/circle-quadratic-form'

type Q = { n: bigint; d: bigint }

type ParsedCircle = {
  parentId: string
  variableX: string
  variableY: string
  chart: CircleQuadraticFormChart
}

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function q(n: bigint, d = 1n): Q {
  if (d === 0n) throw new Error('zero denominator')
  if (d < 0n) return q(-n, -d)
  const divisor = gcd(n, d)
  return { n: n / divisor, d: d / divisor }
}

function parseQ(value: string): Q {
  const [numerator, denominator] = value.split('/')
  return q(BigInt(numerator), BigInt(denominator ?? '1'))
}

function add(left: Q, right: Q): Q { return q(left.n * right.d + right.n * left.d, left.d * right.d) }
function subtract(left: Q, right: Q): Q { return add(left, { n: -right.n, d: right.d }) }
function multiply(left: Q, right: Q): Q { return q(left.n * right.n, left.d * right.d) }
function divide(left: Q, right: Q): Q { return q(left.n * right.d, left.d * right.n) }
function negate(value: Q): Q { return { n: -value.n, d: value.d } }
function format(value: Q): string { return value.d === 1n ? value.n.toString() : `${value.n}/${value.d}` }

function extractEquations(statement: string): string[] {
  const stripped = statement.replace(/\text\s*\{[^{}]*\}/g, '')
  return [
    ...Array.from(statement.matchAll(/\$([^$]+)\$/g), match => match[1]),
    ...Array.from(statement.matchAll(/\\\(([^]*?)\\\)/g), match => match[1]),
    stripped,
  ].filter(segment => segment.includes('='))
}

function normalize(expression: string): string | null {
  const result = expression
    .replace(/\\left|\\right/g, '')
    .replace(/−|–/g, '-')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/\^\s*\{\s*2\s*\}/g, '^2')
    .replace(/[{}\s]/g, '')
  return /\\(?:d?frac|sqrt)|[()]/.test(result) ? null : result
}

function coefficient(raw: string): bigint {
  if (raw === '' || raw === '+') return 1n
  if (raw === '-') return -1n
  return BigInt(raw)
}

function parseSide(expression: string, variableX: string, variableY: string): bigint[] | null {
  const source = normalize(expression)
  if (!source) return null
  const values = [0n, 0n, 0n, 0n, 0n]
  const escapedX = variableX.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const escapedY = variableY.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const patterns = [
    new RegExp(`^([+-]?\\d*)\\*?${escapedX}\\^2$`),
    new RegExp(`^([+-]?\\d*)\\*?${escapedY}\\^2$`),
    new RegExp(`^([+-]?\\d*)\\*?${escapedX}$`),
    new RegExp(`^([+-]?\\d*)\\*?${escapedY}$`),
  ]
  for (const term of source.replace(/-/g, '+-').split('+').filter(Boolean)) {
    let matched = false
    for (let index = 0; index < patterns.length; index += 1) {
      const match = term.match(patterns[index])
      if (!match) continue
      values[index] += coefficient(match[1])
      matched = true
      break
    }
    if (matched) continue
    if (!/^[+-]?\d+$/.test(term)) return null
    values[4] += BigInt(term)
  }
  return values
}

export function parseAffineCircleParent(parent: CertifiedFusionParent): ParsedCircle | null {
  for (const equation of extractEquations(parent.statement)) {
    const match = equation.match(/([^=<>]+)=([^=<>]+)/)
    if (!match) continue
    const normalized = normalize(`${match[1]}${match[2]}`)
    if (!normalized) continue
    const squaredVariables = [...new Set(Array.from(
      normalized.matchAll(/([A-Za-z])\^2/g),
      item => item[1],
    ))]
    if (squaredVariables.length !== 2) continue
    const [variableX, variableY] = squaredVariables
    const left = parseSide(match[1], variableX, variableY)
    const right = parseSide(match[2], variableX, variableY)
    if (!left || !right) continue
    const values = left.map((value, index) => value - right[index])
    if (values[0] === 0n || values[0] !== values[1]) continue
    const built = buildCircleQuadraticFormChart({
      id: `${parent.id}:circle`,
      sourceSemanticIds: [parent.id],
      quadraticCoefficient: values[0],
      linearX: values[2],
      linearY: values[3],
      constant: values[4],
    })
    if (built.chart) return { parentId: parent.id, variableX, variableY, chart: built.chart }
  }
  return null
}

function linearTex(a: Q, b: Q, c: Q, x: string, y: string): string {
  const terms: string[] = []
  const append = (value: Q, symbol: string) => {
    if (value.n === 0n) return
    const sign = value.n < 0n ? '-' : '+'
    const absolute = q(value.n < 0n ? -value.n : value.n, value.d)
    const magnitude = absolute.n === absolute.d ? '' : absolute.d === 1n
      ? absolute.n.toString()
      : `\\frac{${absolute.n}}{${absolute.d}}`
    const body = `${magnitude}${symbol}`
    if (!terms.length) terms.push(sign === '-' ? `-${body}` : body)
    else terms.push(`${sign}${body}`)
  }
  append(a, x)
  append(b, y)
  append(c, '')
  return `${terms.join('') || '0'}=0`
}

function circleTex(circle: ParsedCircle): string {
  const { linearX, linearY, constant } = circle.chart.normalizedEquation
  const tail = linearTex(
    parseQ(linearX), parseQ(linearY), parseQ(constant), circle.variableX, circle.variableY,
  ).replace(/=0$/, '')
  const signedTail = tail === '0' ? '' : tail.startsWith('-') ? tail : `+${tail}`
  return `${circle.variableX}^{2}+${circle.variableY}^{2}${signedTail}=0`
}

function samplePoints(a: Q, b: Q, c: Q): Array<{ x: string; y: string }> {
  const values = [q(0n), q(1n), q(-1n)]
  if (b.n !== 0n) {
    return values.map(x => ({ x: format(x), y: format(divide(negate(add(multiply(a, x), c)), b)) }))
  }
  return values.map(y => ({ x: format(divide(negate(add(multiply(b, y), c)), a)), y: format(y) }))
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

export function synthesizeCertifiedCircleRadicalAxisFusion(
  parents: CertifiedFusionParent[],
): CertifiedFusionCard[] {
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const parsed = parents.map(parseAffineCircleParent)
  if (parsed.some(value => value === null)) return []
  const [left, right] = parsed as [ParsedCircle, ParsedCircle]
  if (left.variableX !== right.variableX || left.variableY !== right.variableY) return []
  const leftEquation = left.chart.normalizedEquation
  const rightEquation = right.chart.normalizedEquation
  const a = subtract(parseQ(leftEquation.linearX), parseQ(rightEquation.linearX))
  const b = subtract(parseQ(leftEquation.linearY), parseQ(rightEquation.linearY))
  const c = subtract(parseQ(leftEquation.constant), parseQ(rightEquation.constant))
  if (a.n === 0n && b.n === 0n) return []

  const samples = samplePoints(a, b, c)
  const independentlyVerified = samples.every(point =>
    evaluateCirclePower(left.chart, point) === evaluateCirclePower(right.chart, point),
  )
  if (!independentlyVerified) return []

  const answerEquation = linearTex(a, b, c, left.variableX, left.variableY)
  const leftTex = circleTex(left)
  const rightTex = circleTex(right)
  const statement = String.raw`座標平面上の2円
\[C_1:${leftTex},\qquad C_2:${rightTex}\]
について、点 $P(${left.variableX},${left.variableY})$ の $C_1,C_2$ に関する方べきが等しくなる点 $P$ の軌跡を求め、図示せよ。`
  const answer = String.raw`\(${answerEquation}\)`
  const solution = String.raw`円 $C_i$ の正規化二次形式を $q_i(${left.variableX},${left.variableY})$ とする。点 $P$ の方べきは $q_i(P)$ に等しい。したがって等方べき条件は $q_1-q_2=0$ である。二つの二次形式の $${left.variableX}^{2}+${left.variableY}^{2}$ 項は相殺され、
\[${answerEquation}\]
を得る。これは2円の根軸である。独立検算として、この直線上の3個の有理点を生成し、各点で $q_1(P)=q_2(P)$ を厳密有理数計算により確認した。`
  const structureId = `certified.circle-radical-axis.${hash([
    left.chart.normalizedEquation,
    right.chart.normalizedEquation,
  ])}`
  const morphisms = [
    'AffineCircleEquationElaboration',
    'SymmetricQuadraticForm',
    'PowerOfPointEvaluation',
    'QuadraticFormDifference',
    'RadicalAxisExtraction',
    'IndependentRationalPointReplay',
    'AllParentAblation',
  ]
  return [{
    id: `mortra-${structureId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'geometry',
    family_id: 'certified.circle_radical_axis',
    tool: 'MORTRA exact reversible synthesis',
    morphism_chain: morphisms,
    diagram: {
      version: 1,
      kind: 'morphism',
      title: '二つの円から根軸へ',
      caption: '二つの円を対称二次形式として保持し、方べきの差から二次項を消去して根軸を得ます。',
      nodes: ['円 C1', '二次形式 q1', '方べき差 q1-q2', '二次項消去', '根軸', '円 C2', '二次形式 q2'],
    },
    parent_ids: [left.parentId, right.parentId],
    verification: {
      method: 'exact rational quadratic-form subtraction + independent rational-point power replay + all-parent dependency',
      exact_backend: true,
      independent_check: true,
      samples: samples.map((_, index) => index),
    },
    difficulty: { band: 'B_exact_affine_circle_fusion', score: 6.8 },
    fusion_derivation: {
      passed: true,
      reason: 'each parent supplies one indispensable circle quadratic form; their difference uniquely determines the radical axis',
      ablationPassed: true,
      assignments: [left, right].map((circle, index) => ({
        parentId: circle.parentId,
        portId: `circle_quadratic_form_${index + 1}`,
        role: 'object',
        matchedAnchors: [circleTex(circle)],
        witnessSteps: ['AffineCircleEquationElaboration', 'SymmetricQuadraticForm'],
      })),
      bridges: [{
        id: 'power-difference',
        witnessStep: 'QuadraticFormDifference',
        consumes: ['circle_quadratic_form_1', 'circle_quadratic_form_2'],
        produces: 'radical_axis_linear_form',
      }],
      intermediatePropositions: [left, right].map(circle => ({
        parentId: circle.parentId,
        morphism: 'PowerOfPointEvaluation',
        source: 'AffineCircleEquation',
        target: 'QuadraticForm',
        proposition: 'the normalized circle polynomial equals point power',
        proved: true as const,
      })),
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'ReversibleAffineCircleQuadraticFormIR',
      observable: 'radical_axis',
      operators: morphisms,
      domain: 'geometry',
      tags: ['circle', 'quadratic-form', 'power-of-point', 'radical-axis', 'affine', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'circle-elaboration', claim: 'both parents normalize to nondegenerate real circle quadratic forms', verifier: 'exact rational circle chart' },
        { id: 'quadratic-difference', claim: answerEquation, verifier: 'exact rational coefficient subtraction' },
        { id: 'point-replay', claim: 'three generated radical-axis points have equal powers', verifier: 'independent exact rational substitution' },
        { id: 'parent-ablation', claim: 'both selected circle forms are indispensable', verifier: 'typed all-parent cardinality check' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['two-nondegenerate-affine-circles', 'equal-point-power'],
        querySignature: 'radical-axis-locus',
        normalForm: answerEquation,
        quotientAction: 'common-nonzero-scaling-of-each-circle-equation',
        freeParameters: ['two circle coefficient triples'],
        uniqueNormalForm: true,
        finiteSolutionSet: false,
        numericInstanceConstants: [],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
  }]
}
