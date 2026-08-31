import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'

export type Q = { n: bigint; d: bigint }

export type ParsedPositiveRecurrence = {
  parentId: string
  symbol: string
  indexSymbol: string
  initial: [bigint, bigint]
  coefficients: [bigint, bigint]
}

export type ParsedTrigonometricPowerSum = {
  parentId: string
  angleToken: string
  exponentSymbol: string
  sum: Q
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

function add(left: Q, right: Q): Q {
  return q(left.n * right.d + right.n * left.d, left.d * right.d)
}

function subtract(left: Q, right: Q): Q {
  return q(left.n * right.d - right.n * left.d, left.d * right.d)
}

function multiply(left: Q, right: Q): Q {
  return q(left.n * right.n, left.d * right.d)
}

function scale(value: Q, factor: bigint): Q {
  return q(value.n * factor, value.d)
}

function power(value: Q, exponent: number): Q {
  let result = q(1n)
  let base = value
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiply(result, base)
    base = multiply(base, base)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function compare(left: Q, right: Q): number {
  const difference = left.n * right.d - right.n * left.d
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}

function equal(left: Q, right: Q): boolean {
  return left.n === right.n && left.d === right.d
}

function qText(value: Q): string {
  return value.d === 1n ? value.n.toString() : `${value.n}/${value.d}`
}

function qTex(value: Q): string {
  return value.d === 1n ? value.n.toString() : `\\frac{${value.n}}{${value.d}}`
}

function linearCombinationTex(terms: Array<{ coefficient: bigint; variable: string }>): string {
  const nonzeroTerms = terms.filter(term => term.coefficient !== 0n)
  if (nonzeroTerms.length === 0) return '0'
  return nonzeroTerms.map((term, index) => {
    const negative = term.coefficient < 0n
    const magnitude = negative ? -term.coefficient : term.coefficient
    const coefficient = magnitude === 1n ? '' : String(magnitude)
    const sign = index === 0 ? (negative ? '-' : '') : (negative ? '-' : '+')
    return `${sign}${coefficient}${term.variable}`
  }).join('')
}

function parseRational(source: string): Q | null {
  const compact = source.replace(/\s+/g, '')
  const latex = compact.match(/^\\(?:d?frac)\{([+-]?\d+)\}\{(\d+)\}$/)
  if (latex) return q(BigInt(latex[1]), BigInt(latex[2]))
  const slash = compact.match(/^([+-]?\d+)\/(\d+)$/)
  if (slash) return q(BigInt(slash[1]), BigInt(slash[2]))
  return /^[+-]?\d+$/.test(compact) ? q(BigInt(compact)) : null
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function parsePositiveSecondOrderRecurrence(
  parent: CertifiedFusionParent,
): ParsedPositiveRecurrence | null {
  const source = parent.statement.replace(/[−–]/g, '-')
  const recurrence = source.match(
    /([A-Za-z])_\{?([A-Za-z])\+2\}?\s*=\s*(?:(\d+)\s*(?:\\cdot|\\times)?\s*)?\1_\{?\2\+1\}?\s*\+\s*(?:(\d+)\s*(?:\\cdot|\\times)?\s*)?\1_\{?\2\}?/,
  )
  if (!recurrence) return null
  const [, symbol, indexSymbol, leftCoefficient = '1', rightCoefficient = '1'] = recurrence
  const escaped = escapeRegExp(symbol)
  const equalInitials = source.match(new RegExp(
    `${escaped}_\\{?1\\}?\\s*=\\s*${escaped}_\\{?2\\}?\\s*=\\s*([+-]?\\d+)`,
  ))
  let first: bigint
  let second: bigint
  if (equalInitials) {
    first = BigInt(equalInitials[1])
    second = first
  } else {
    const firstMatch = source.match(new RegExp(`${escaped}_\\{?1\\}?\\s*=\\s*([+-]?\\d+)`))
    const secondMatch = source.match(new RegExp(`${escaped}_\\{?2\\}?\\s*=\\s*([+-]?\\d+)`))
    if (!firstMatch || !secondMatch) return null
    first = BigInt(firstMatch[1])
    second = BigInt(secondMatch[1])
  }
  const a = BigInt(leftCoefficient)
  const b = BigInt(rightCoefficient)
  if (first <= 0n || second < first || a < 1n || b < 1n) return null
  return {
    parentId: parent.id,
    symbol,
    indexSymbol,
    initial: [first, second],
    coefficients: [a, b],
  }
}

export function parseTrigonometricPowerSum(
  parent: CertifiedFusionParent,
): ParsedTrigonometricPowerSum | null {
  const source = parent.statement.replace(/[−–]/g, '-')
  const relation = source.match(
    /\\sin\s*(\\[A-Za-z]+|[A-Za-z])\s*\+\s*\\cos\s*\1\s*=\s*(\\(?:d?frac)\s*\{[+-]?\d+\}\s*\{\d+\}|[+-]?\d+(?:\s*\/\s*\d+)?)/,
  )
  if (!relation) return null
  const sum = parseRational(relation[2])
  if (!sum || compare(sum, q(0n)) <= 0 || compare(sum, q(1n)) >= 0) return null
  const power = source.match(/\\sin\s*\^\s*\{?([A-Za-z])\}?/)
  if (!power || !/\\cos\s*\^/.test(source) || !/>/.test(source)) return null
  const queryRationals = [...source.matchAll(
    />\s*(\\(?:d?frac)\s*\{[+-]?\d+\}\s*\{\d+\}|[+-]?\d+(?:\s*\/\s*\d+)?)/g,
  )]
  if (!queryRationals.some(match => {
    const parsed = parseRational(match[1])
    return parsed ? equal(parsed, sum) : false
  })) return null
  return {
    parentId: parent.id,
    angleToken: relation[1],
    exponentSymbol: power[1],
    sum,
  }
}

function findRootMagnitudeUpperBound(sum: Q): Q | null {
  const discriminant = subtract(q(2n), multiply(sum, sum))
  for (const denominator of [100n, 1_000n, 10_000n, 100_000n, 1_000_000n]) {
    let low = 1n
    let high = denominator - 1n
    let found: bigint | null = null
    while (low <= high) {
      const middle = (low + high) / 2n
      const candidate = q(middle, denominator)
      const shifted = subtract(scale(candidate, 2n), sum)
      const valid = compare(shifted, q(0n)) > 0 &&
        compare(multiply(shifted, shifted), discriminant) > 0
      if (valid) {
        found = middle
        high = middle - 1n
      } else {
        low = middle + 1n
      }
    }
    if (found !== null) return q(found, denominator)
  }
  return null
}

function findTailThresholds(sum: Q, bound: Q): { odd: number; even: number } | null {
  let odd = 0
  for (let exponent = 3; exponent <= 999; exponent += 2) {
    const current = scale(power(bound, exponent - 1), BigInt(exponent))
    const ratio = multiply(q(BigInt(exponent + 2), BigInt(exponent)), power(bound, 2))
    if (compare(current, q(1n)) < 0 && compare(ratio, q(1n)) < 0) {
      odd = exponent
      break
    }
  }
  let even = 0
  for (let exponent = 2; exponent <= 1_000; exponent += 2) {
    if (compare(scale(power(bound, exponent), 2n), sum) < 0) {
      even = exponent
      break
    }
  }
  return odd && even ? { odd, even } : null
}

export function generatePositiveRecurrenceTerms(
  spec: ParsedPositiveRecurrence,
  cutoff: number,
): bigint[] | null {
  const [a, b] = spec.coefficients
  const terms = [...spec.initial]
  while (terms.at(-1)! < BigInt(cutoff) && terms.length < 256) {
    terms.push(a * terms.at(-1)! + b * terms.at(-2)!)
  }
  return terms.at(-1)! >= BigInt(cutoff) ? terms : null
}

type QMatrix = [[Q, Q], [Q, Q]]

function multiplyQMatrix(left: QMatrix, right: QMatrix): QMatrix {
  return [
    [
      add(multiply(left[0][0], right[0][0]), multiply(left[0][1], right[1][0])),
      add(multiply(left[0][0], right[0][1]), multiply(left[0][1], right[1][1])),
    ],
    [
      add(multiply(left[1][0], right[0][0]), multiply(left[1][1], right[1][0])),
      add(multiply(left[1][0], right[0][1]), multiply(left[1][1], right[1][1])),
    ],
  ]
}

function powerQMatrix(matrix: QMatrix, exponent: number): QMatrix {
  let result: QMatrix = [[q(1n), q(0n)], [q(0n), q(1n)]]
  let base = matrix
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiplyQMatrix(result, base)
    base = multiplyQMatrix(base, base)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function powerSumSequential(sum: Q, product: Q, maximum: number): Q[] {
  const values = [q(2n), sum]
  for (let exponent = 2; exponent <= maximum; exponent += 1) {
    values.push(subtract(multiply(sum, values[exponent - 1]), multiply(product, values[exponent - 2])))
  }
  return values
}

function powerSumByMatrix(sum: Q, product: Q, exponent: number): Q {
  if (exponent === 0) return q(2n)
  if (exponent === 1) return sum
  const matrix: QMatrix = [[sum, q(-product.n, product.d)], [q(1n), q(0n)]]
  const powered = powerQMatrix(matrix, exponent - 1)
  return add(multiply(powered[0][0], sum), scale(powered[0][1], 2n))
}

type ZMatrix = [[bigint, bigint], [bigint, bigint]]

function multiplyZMatrix(left: ZMatrix, right: ZMatrix): ZMatrix {
  return [
    [left[0][0] * right[0][0] + left[0][1] * right[1][0], left[0][0] * right[0][1] + left[0][1] * right[1][1]],
    [left[1][0] * right[0][0] + left[1][1] * right[1][0], left[1][0] * right[0][1] + left[1][1] * right[1][1]],
  ]
}

function powerZMatrix(matrix: ZMatrix, exponent: number): ZMatrix {
  let result: ZMatrix = [[1n, 0n], [0n, 1n]]
  let base = matrix
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiplyZMatrix(result, base)
    base = multiplyZMatrix(base, base)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function recurrenceTermByMatrix(spec: ParsedPositiveRecurrence, index: number): bigint {
  if (index === 1) return spec.initial[0]
  if (index === 2) return spec.initial[1]
  const matrix: ZMatrix = [[spec.coefficients[0], spec.coefficients[1]], [1n, 0n]]
  const powered = powerZMatrix(matrix, index - 2)
  return powered[0][0] * spec.initial[1] + powered[0][1] * spec.initial[0]
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function texDocument(statement: string, solution: string): string {
  return String.raw`\documentclass[a4paper,11pt]{jsarticle}
\usepackage{amsmath,amssymb,array}
\begin{document}
\section*{問題}
${statement}
\section*{解答}
${solution}
\end{document}
`
}

function integerSetTex(values: number[]): string {
  return values.length ? `\\{${values.join(',')}\\}` : '\\varnothing'
}

export type CertifiedIndexedPowerSumEvaluation = {
  sum: Q
  bound: Q
  thresholds: { odd: number; even: number }
  cutoff: number
  checked: Array<{
    index: number
    exponent: bigint
    value: Q
    difference: Q
    passed: boolean
  }>
  answerIndices: number[]
  sumText: string
  sumTex: string
  tableTex: string
}

export type CertifiedPowerSumTail = {
  bound: Q
  thresholds: { odd: number; even: number }
  cutoff: number
}

export function certifyPowerSumTail(
  powerParent: ParsedTrigonometricPowerSum,
): CertifiedPowerSumTail | null {
  const bound = findRootMagnitudeUpperBound(powerParent.sum)
  if (!bound) return null
  const thresholds = findTailThresholds(powerParent.sum, bound)
  if (!thresholds) return null
  return {
    bound,
    thresholds,
    cutoff: Math.max(thresholds.odd, thresholds.even),
  }
}

export function certifyIndexedPowerSumTerms(
  powerParent: ParsedTrigonometricPowerSum,
  terms: bigint[],
): CertifiedIndexedPowerSumEvaluation | null {
  const tail = certifyPowerSumTail(powerParent)
  if (!tail) return null
  const { bound, thresholds, cutoff } = tail
  if (!terms.length || terms.at(-1)! < BigInt(cutoff)) return null
  if (terms.some((term, index) =>
    term <= 0n || (index > 0 && term < terms[index - 1])
  )) return null

  const exactTerms = terms
    .map((exponent, index) => ({ exponent, index: index + 1 }))
    .filter(({ exponent }) => exponent % 2n === 0n
      ? exponent < BigInt(thresholds.even)
      : exponent < BigInt(thresholds.odd))
  const maximumExponent = Number(exactTerms.reduce(
    (maximum, item) => item.exponent > maximum ? item.exponent : maximum,
    0n,
  ))
  const product = q(
    powerParent.sum.n * powerParent.sum.n - powerParent.sum.d * powerParent.sum.d,
    2n * powerParent.sum.d * powerParent.sum.d,
  )
  const sums = powerSumSequential(powerParent.sum, product, maximumExponent)
  const comparisons = exactTerms.map(({ exponent, index }) => {
    const numericExponent = Number(exponent)
    const sequential = sums[numericExponent]
    const independent = powerSumByMatrix(powerParent.sum, product, numericExponent)
    if (!equal(sequential, independent)) return null
    return {
      index,
      exponent,
      value: sequential,
      difference: subtract(sequential, powerParent.sum),
      passed: compare(sequential, powerParent.sum) > 0,
    }
  })
  if (comparisons.some(value => value === null)) return null
  const checked = comparisons as CertifiedIndexedPowerSumEvaluation['checked']
  const answerIndices = checked.filter(item => item.passed).map(item => item.index)
  const comparisonCells = checked.map(item =>
    item.difference.n > 0n ? '>0' : item.difference.n < 0n ? '<0' : '=0'
  )
  const sumTex = qTex(powerParent.sum)
  const tableTex = [
    '\\[',
    '\\begin{array}{c|' + 'c'.repeat(checked.length) + '}',
    'k&' + checked.map(item => item.index).join('&') + '\\\\',
    '\\hline',
    'b_k&' + checked.map(item => item.exponent).join('&') + '\\\\',
    'u_{b_k}-' + sumTex + '&' + comparisonCells.join('&'),
    '\\end{array}',
    '\\]',
  ].join('\n')
  return {
    sum: powerParent.sum,
    bound,
    thresholds,
    cutoff,
    checked,
    answerIndices,
    sumText: qText(powerParent.sum),
    sumTex,
    tableTex,
  }
}

export type IndexedPowerVariantContext = {
  definitionTex: string
  indexSymbol: string
  exponentTex: string
  exponentSequenceJa: string
  independentReplayJa: string
}

function comparisonTable(
  evaluation: CertifiedIndexedPowerSumEvaluation,
  indexLabel: string,
  exponentLabel: string,
  label: string,
  cells: string[],
): string {
  if (!evaluation.checked.length) return String.raw`\[\text{直接比較すべき項はない。}\]`
  return String.raw`\[
\begin{array}{c|${'c'.repeat(evaluation.checked.length)}}
${indexLabel}&${evaluation.checked.map(item => item.index).join('&')}\\\hline
${exponentLabel}&${evaluation.checked.map(item => item.exponent).join('&')}\\
${label}&${cells.join('&')}
\end{array}
\]`
}

function indexedPowerVariant(
  base: CertifiedFusionCard,
  evaluation: CertifiedIndexedPowerSumEvaluation,
  context: IndexedPowerVariantContext,
  spec: {
    id: string
    observable: string
    querySignature: string
    statement: string
    answer: string
    conclusion: string
    tableLabel: string
    tableCells: string[]
    active: (item: CertifiedIndexedPowerSumEvaluation['checked'][number]) => boolean
    validHypotheses: number
    finiteSolutionSet: boolean
    difficultyOffset: number
    certificateClaim: string
  },
  startedAt: number,
): CertifiedFusionCard {
  const c = evaluation.sumTex
  const table = comparisonTable(
    evaluation,
    context.indexSymbol,
    context.exponentTex,
    spec.tableLabel,
    spec.tableCells,
  )
  const solution = String.raw`\(X=\sin\theta,\ Y=\cos\theta\) とおき、\(u_m=X^m+Y^m\) とする。条件から
\[
u_0=2,\qquad u_1=${c},\qquad
u_{m+2}=${c}u_{m+1}+\frac{1-(${c})^2}{2}u_m.\tag{1}
\]
${context.exponentSequenceJa}を \((1)\) の添字へ代入し、厳密有理数で計算すると
${table}
を得る。

一方、\(X=\alpha>0,\ Y=-\beta<0\) と番号を付けると、検証済みの上界 \(r=${qTex(evaluation.bound)}<1\) により、奇数 \(m\ge${evaluation.thresholds.odd}\) では
\[|u_m|\le ${c}\,m r^{m-1}<${c},\]
偶数 \(m\ge${evaluation.thresholds.even}\) では
\[0<u_m\le2r^m<${c}\]
となる。したがって表の外では \(u_m=${c}\) にも \(u_m>${c}\) にもならない。${spec.conclusion}
${context.independentReplayJa}でも同じ表と結論を得た。`
  const morphisms = [...base.morphism_chain, 'CertifiedObservableProjection']
  const exactStates = evaluation.checked.map(item => ({
    id: `${context.indexSymbol}${item.index}`,
    label: `${context.indexSymbol}=${item.index}, ${context.exponentTex}=${item.exponent}`,
    active: spec.active(item),
  }))
  const structureId = `${base.structure_blueprint.id}.${spec.id}`
  return {
    ...base,
    id: `mortra-${structureId}`,
    statement_tex: spec.statement,
    answer_tex: spec.answer,
    solution_tex: solution,
    solution_document_tex: texDocument(spec.statement, solution),
    morphism_chain: morphisms,
    proof_roadmap: [
      ...(base.proof_roadmap ?? []),
      {
        morphism_id: 'CertifiedObservableProjection',
        label_ja: '同じ証明済み状態から問いを取り出す',
        source_ja: '添字付きべき和と有限尾部証明',
        target_ja: '等号・最大値・最終通過位置',
        role_ja: '新しい計算法を足さず、同じ厳密状態へ別の観測条件を適用します。',
      },
    ],
    diagram: {
      version: 1,
      kind: 'state',
      title: '一つのべき和軌道から別の問いを読む',
      caption: '指数列とべき和の証明済み状態は共通です。色付きの状態だけが今回の問いに該当します。',
      states: [...exactStates, { id: 'tail', label: `${context.exponentTex} \ge ${evaluation.cutoff}: 一括評価`, terminal: true }],
      transitions: [
        ...exactStates.slice(1).map((state, index) => ({
          from: exactStates[index].id,
          to: state.id,
          label: '次の項',
        })),
        { from: exactStates.at(-1)?.id ?? 'start', to: 'tail', label: '以後を一括証明' },
      ],
    },
    verification: {
      ...base.verification,
      method: `${base.verification.method} + reusable certified observable projection`,
      samples: [...base.verification.samples, spec.validHypotheses],
    },
    difficulty: {
      band: base.difficulty.band,
      score: base.difficulty.score + spec.difficultyOffset,
    },
    fusion_derivation: {
      ...base.fusion_derivation,
      reason: `${base.fusion_derivation.reason}; the query is a reusable projection of the same certified orbit`,
      bridges: base.fusion_derivation.bridges.map(bridge => ({
        ...bridge,
        produces: spec.observable,
      })),
    },
    structure_blueprint: {
      ...base.structure_blueprint,
      id: structureId,
      observable: spec.observable,
      operators: morphisms,
      tags: [...base.structure_blueprint.tags, 'observable-projection'],
      morphismChain: morphisms,
      proofCertificate: [
        ...base.structure_blueprint.proofCertificate,
        { id: `observable-${spec.id}`, claim: spec.certificateClaim, verifier: 'exact rational orbit query' },
      ],
      structuralUniqueness: {
        ...base.structure_blueprint.structuralUniqueness,
        querySignature: spec.querySignature,
        normalForm: spec.answer,
        finiteSolutionSet: spec.finiteSolutionSet,
        numericInstanceConstants: [
          ...base.structure_blueprint.structuralUniqueness.numericInstanceConstants,
          spec.validHypotheses,
        ],
      },
    },
    search_evidence: {
      hypotheses_evaluated: evaluation.checked.length,
      valid_hypotheses: spec.validHypotheses,
      elapsed_ms: Date.now() - startedAt,
    },
  }
}

export function synthesizeIndexedPowerObservableVariants(
  base: CertifiedFusionCard,
  evaluation: CertifiedIndexedPowerSumEvaluation,
  context: IndexedPowerVariantContext,
  startedAt: number,
): CertifiedFusionCard[] {
  const equalIndices = evaluation.checked
    .filter(item => item.difference.n === 0n)
    .map(item => item.index)
  const lastGreaterIndex = evaluation.answerIndices.at(-1) ?? 0
  const cutoffIndex = lastGreaterIndex + 1
  const cutoffConclusion = lastGreaterIndex > 0
    ? `厳密な不等式が最後に成り立つのは \\(${context.indexSymbol}=${lastGreaterIndex}\\) であるから、求める最小値は \\(K=${cutoffIndex}\\) である。`
    : `厳密な不等式は初項から一度も成り立たないので、求める最小値は \\(K=1\\) である。`
  const equalityAnswer = `\\(${context.indexSymbol}\\in${integerSetTex(equalIndices)}\\)`
  const cutoffAnswer = `\\(K=${cutoffIndex}\\)`
  const variants: CertifiedFusionCard[] = [
    indexedPowerVariant(base, evaluation, context, {
      id: 'equality-set',
      observable: 'indexed_power_sum_equality_solution_set',
      querySignature: 'classify every generated index attaining the parent symmetric sum',
      statement: `${context.definitionTex}\n\\[\\sin^{${context.exponentTex}}\\theta+\\cos^{${context.exponentTex}}\\theta=${evaluation.sumTex}\\]\nとなる正の整数 \\(${context.indexSymbol}\\) をすべて求めよ。`,
      answer: equalityAnswer,
      conclusion: `よって等号が成り立つ添字は \\[${context.indexSymbol}\\in${integerSetTex(equalIndices)}\\] で尽くされる。`,
      tableLabel: `u_{${context.exponentTex}}-${evaluation.sumTex}`,
      tableCells: evaluation.checked.map(item => qTex(item.difference)),
      active: item => item.difference.n === 0n,
      validHypotheses: equalIndices.length,
      finiteSolutionSet: true,
      difficultyOffset: 0.2,
      certificateClaim: 'all equality indices are exhausted before the strict tail bound',
    }, startedAt),
    indexedPowerVariant(base, evaluation, context, {
      id: 'eventual-cutoff',
      observable: 'indexed_power_sum_last_threshold_crossing',
      querySignature: 'find the minimal index after the final strict threshold crossing',
      statement: `${context.definitionTex}\nすべての \\(${context.indexSymbol}\\ge K\\) に対して\n\\[\\sin^{${context.exponentTex}}\\theta+\\cos^{${context.exponentTex}}\\theta\\le${evaluation.sumTex}\\]\nとなる最小の正整数 \\(K\\) を求めよ。`,
      answer: cutoffAnswer,
      conclusion: cutoffConclusion,
      tableLabel: `u_{${context.exponentTex}}-${evaluation.sumTex}`,
      tableCells: evaluation.checked.map(item => qTex(item.difference)),
      active: item => item.passed,
      validHypotheses: cutoffIndex,
      finiteSolutionSet: true,
      difficultyOffset: 0.4,
      certificateClaim: 'the final strict crossing and the minimal eventual cutoff are certified exactly',
    }, startedAt),
  ]

  if (evaluation.checked.length) {
    const maximum = evaluation.checked.reduce(
      (current, item) => compare(item.value, current) > 0 ? item.value : current,
      evaluation.checked[0].value,
    )
    if (compare(maximum, evaluation.sum) >= 0) {
      const maximumIndices = evaluation.checked
        .filter(item => equal(item.value, maximum))
        .map(item => item.index)
      const maximumTex = qTex(maximum)
      const answer = `\\(\\max u_{${context.exponentTex}}=${maximumTex},\\quad ${context.indexSymbol}\\in${integerSetTex(maximumIndices)}\\)`
      variants.push(indexedPowerVariant(base, evaluation, context, {
        id: 'global-maximum',
        observable: 'indexed_power_sum_global_maximum',
        querySignature: 'determine the exact global maximum and every attaining generated index',
        statement: `${context.definitionTex}\n数列\n\\[v_${context.indexSymbol}=\\sin^{${context.exponentTex}}\\theta+\\cos^{${context.exponentTex}}\\theta\\]\nの最大値と、その値をとるすべての正整数 \\(${context.indexSymbol}\\) を求めよ。`,
        answer,
        conclusion: `表の最大値は \\(${maximumTex}\\) であり、尾部では \\(|u_m|<${evaluation.sumTex}\\le${maximumTex}\\) だから、全体の最大値も \\(${maximumTex}\\) である。等号は \\(${context.indexSymbol}\\in${integerSetTex(maximumIndices)}\\) に限る。`,
        tableLabel: `u_{${context.exponentTex}}-${maximumTex}`,
        tableCells: evaluation.checked.map(item => qTex(subtract(item.value, maximum))),
        active: item => equal(item.value, maximum),
        validHypotheses: maximumIndices.length,
        finiteSolutionSet: true,
        difficultyOffset: 0.7,
        certificateClaim: 'the finite exact maximum dominates the rigorously bounded infinite tail',
      }, startedAt))
    }
  }
  return variants
}

export function synthesizeCertifiedIndexedPowerSumFusion(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const recurrence = parents.map(parsePositiveSecondOrderRecurrence).find(Boolean)
  const powerParent = parents.map(parseTrigonometricPowerSum).find(Boolean)
  if (!recurrence || !powerParent || recurrence.parentId === powerParent.parentId) return []

  const preliminaryBound = findRootMagnitudeUpperBound(powerParent.sum)
  if (!preliminaryBound) return []
  const preliminaryThresholds = findTailThresholds(powerParent.sum, preliminaryBound)
  if (!preliminaryThresholds) return []
  const preliminaryCutoff = Math.max(preliminaryThresholds.odd, preliminaryThresholds.even)
  const terms = generatePositiveRecurrenceTerms(recurrence, preliminaryCutoff)
  if (!terms) return []
  if (!terms.every((term, index) => recurrenceTermByMatrix(recurrence, index + 1) === term)) return []
  const evaluation = certifyIndexedPowerSumTerms(powerParent, terms)
  if (!evaluation) return []
  const {
    answerIndices,
    bound,
    checked,
    cutoff,
    sumTex: c,
    thresholds,
  } = evaluation
  const [initial1, initial2] = recurrence.initial
  const [coefficient1, coefficient2] = recurrence.coefficients
  const recurrenceRightHandSide = linearCombinationTex([
    { coefficient: coefficient1, variable: 'a_{k+1}' },
    { coefficient: coefficient2, variable: 'a_k' },
  ])
  const recurrenceTex = `a_1=${initial1},\\ a_2=${initial2},\\ a_{k+2}=${recurrenceRightHandSide}`
  const comparisonCells = checked.map(item => item.difference.n > 0n ? '>0' : item.difference.n < 0n ? '<0' : '=0')
  const table = checked.length > 0 ? String.raw`\[
\begin{array}{c|${'c'.repeat(checked.length)}}
k&${checked.map(item => item.index).join('&')}\\\hline
a_k&${checked.map(item => item.exponent).join('&')}\\
u_{a_k}-${c}&${comparisonCells.join('&')}
\end{array}
\]` : String.raw`\[\text{直接計算すべき項はない。}\]`
  const statement = `数列 \\(\\{a_k\\}\\) を
\\[${recurrenceTex}\\]
で定める。実数 \\(\\theta\\) が
\\[\\sin\\theta+\\cos\\theta=${c}\\]
を満たすとき、
\\[\\sin^{a_k}\\theta+\\cos^{a_k}\\theta>${c}\\]
となる正の整数 \\(k\\) をすべて求めよ。`
  const solution = `\\(x=\\sin\\theta,\\ y=\\cos\\theta\\) とおき、\\(u_m=x^m+y^m\\) とする。条件から
  \\[x+y=${c},\\qquad xy=\\frac{(${c})^2-1}{2},\\]
  したがって、\\(x,y\\) はともに
  \\[t^2-${c}t-\\frac{1-(${c})^2}{2}=0\\]
  の解である。各辺にそれぞれ \\(x^m,y^m\\) を掛けて加えると、べき和 \\(u_m\\) は
  \\[u_0=2,\\quad u_1=${c},\\quad u_{m+2}=${c}u_{m+1}+\\frac{1-(${c})^2}{2}u_m\\tag{1}\\]
を得る。一方、第一の親問題から得た添字列は
\\[${terms.map(String).join(', ')},\\ldots\\]
である。\\((1)\\)を厳密有理数で計算すると
${table}
となる。

残りが有限計算の外へ逃げないことを示す。\\(x=\\alpha>0,\\ y=-\\beta<0\\) と番号を付けると、\\(\\alpha-\\beta=${c}\\) である。二次方程式から
\\[\\max(\\alpha,\\beta)<r=${qTex(bound)}\\]
が従う。実際、\\((2r-${c})^2>2-(${c})^2\\) は整数の大小比較で確認できる。奇数 \\(m\\ge ${thresholds.odd}\\) では
\\[|u_m|=\\alpha^m-\\beta^m\\le ${c}\\,m r^{m-1}<${c},\\]
偶数 \\(m\\ge ${thresholds.even}\\) では
\\[0<u_m\\le2r^m<${c}.\\]
  添字列は正で単調に増加し、第2項以後は狭義単調である。表には、上の評価をまだ適用できない項だけを載せた。表にない項は、奇数なら \\(a_k\\ge${thresholds.odd}\\)、偶数なら \\(a_k\\ge${thresholds.even}\\) なので、いずれも不等式を満たさない。また、\\(a_${terms.length}=${terms.at(-1)}\\ge${cutoff}\\) であり、添字列は以後も増加するから、新しい解は生じない。したがって答えは
\\[k\\in${integerSetTex(answerIndices)}\\]
である。なお、\\((1)\\)による逐次計算とは独立に、冪和の \\(2\\times2\\) 伴行列と添字列の伴行列を高速累乗し、表の全項が一致することを確認した。`
  const answer = `\\(k\\in${integerSetTex(answerIndices)}\\)`
  const structureId = `certified.indexed-power-sum.${hash({
    recurrence: {
      initial: recurrence.initial.map(String),
      coefficients: recurrence.coefficients.map(String),
    },
    sum: qText(powerParent.sum),
  })}`
  const morphisms = [
    'PositiveSecondOrderRecurrenceElaboration',
    'CompanionMatrixIndexGeneration',
    'SymmetricTrigonometricPairElaboration',
    'NewtonPowerSumRecurrence',
    'SubsequencePullback',
    'ExactRationalInequality',
    'CertifiedTailBound',
    'IndependentMatrixReplay',
    'AllParentAblation',
  ]
  const exactStates = checked.map(item => ({
    id: `k${item.index}`,
    label: `k=${item.index}, a_k=${item.exponent}`,
    active: item.passed,
  }))
  const baseCard: CertifiedFusionCard = {
    id: `mortra-${structureId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'number_theory_analysis',
    family_id: 'certified.recurrence_indexed_power_sum',
    tool: 'MORTRA exact reversible synthesis',
    morphism_chain: morphisms,
    proof_roadmap: [
      {
        morphism_id: 'PositiveSecondOrderRecurrenceElaboration',
        label_ja: '整数列の定義を読み取る',
        source_ja: '一方の親問題にある二階漸化式',
        target_ja: '初期値と二つの係数',
        role_ja: '添字として使う整数列を、問題文の記号名に依存しない形へ直します。',
      },
      {
        morphism_id: 'CompanionMatrixIndexGeneration',
        label_ja: '添字列を正確に生成する',
        source_ja: '二階漸化式',
        target_ja: '増加する整数の軌道',
        role_ja: '逐次計算と行列の累乗を独立に行い、同じ整数列になることを確かめます。',
      },
      {
        morphism_id: 'SymmetricTrigonometricPairElaboration',
        label_ja: '正弦と余弦を対称式として読む',
        source_ja: 'もう一方の親問題にある正弦と余弦の和',
        target_ja: '和と積が既知の二数',
        role_ja: 'sin²θ+cos²θ=1を使い、正弦と余弦の積も厳密に定めます。',
      },
      {
        morphism_id: 'NewtonPowerSumRecurrence',
        label_ja: 'すべてのべき和を一つの漸化式で表す',
        source_ja: '正弦と余弦の和と積',
        target_ja: 'u_m=sin^mθ+cos^mθ',
        role_ja: '指数ごとの個別計算を避け、共通の二階漸化式を導きます。',
      },
      {
        morphism_id: 'SubsequencePullback',
        label_ja: '整数列をべき和の指数へ入れる',
        source_ja: '整数の軌道とべき和の列',
        target_ja: 'u_{a_k}',
        role_ja: '二つの親問題を合成し、生成された整数だけを指数として取り出します。',
      },
      {
        morphism_id: 'ExactRationalInequality',
        label_ja: '必要な有限個の項を比較する',
        source_ja: '添字付きべき和',
        target_ja: '等号と不等号の真偽',
        role_ja: '小数近似を使わず、分数の整数比較で各候補を判定します。',
      },
      {
        morphism_id: 'CertifiedTailBound',
        label_ja: '残りの無限個の項をまとめて除く',
        source_ja: '絶対値が1未満の二つの根',
        target_ja: '有限の検査で十分であるという証明',
        role_ja: '奇数と偶数を分けた上界により、表の後に新しい解がないことを示します。',
      },
      {
        morphism_id: 'IndependentMatrixReplay',
        label_ja: '別の計算法で全候補を検算する',
        source_ja: '二つの伴行列',
        target_ja: '同一の指数列とべき和',
        role_ja: '逐次漸化式とは別に行列の累乗を使い、有限表を再現します。',
      },
      {
        morphism_id: 'AllParentAblation',
        label_ja: '二つの親がともに必要か確かめる',
        source_ja: '指数を与える親とべき和を与える親',
        target_ja: '親依存性の証明',
        role_ja: 'どちらか一方を除くと添字付きの問いを定義できないことを型検査で確認します。',
      },
    ],
    diagram: {
      version: 1,
      kind: 'state',
      title: '漸化式の項をべき和の指数にする',
      caption: '一方の親から得た整数列を、もう一方の親から得たべき和の指数として使います。色付きの状態だけが不等式を満たします。',
      states: [...exactStates, { id: 'tail', label: `a_k ≥ ${cutoff}: 一括評価`, terminal: true }],
      transitions: [
        ...exactStates.slice(1).map((state, index) => ({
          from: exactStates[index].id,
          to: state.id,
          label: '次の項',
        })),
        { from: exactStates.at(-1)?.id ?? 'k1', to: 'tail', label: '以後をまとめて評価' },
      ],
    },
    parent_ids: parents.map(parent => parent.id),
    verification: {
      method: 'exact rational Newton recurrence + independent companion-matrix replay + exact rational tail inequalities + all-parent dependency',
      exact_backend: true,
      independent_check: true,
      samples: [checked.length, cutoff, thresholds.odd, thresholds.even],
    },
    difficulty: { band: 'A_exact_cross_domain_fusion', score: 9.4 },
    fusion_derivation: {
      passed: true,
      reason: 'one parent supplies the indispensable exponent orbit and the other supplies the indispensable symmetric power-sum transition; neither port alone determines the indexed inequality',
      ablationPassed: true,
      assignments: [
        {
          parentId: recurrence.parentId,
          portId: 'exponent_orbit',
          role: 'index generator',
          matchedAnchors: [recurrenceTex],
          witnessSteps: ['PositiveSecondOrderRecurrenceElaboration', 'CompanionMatrixIndexGeneration'],
        },
        {
          parentId: powerParent.parentId,
          portId: 'power_sum_transition',
          role: 'observable',
          matchedAnchors: [`sin+cos=${qText(powerParent.sum)}`],
          witnessSteps: ['SymmetricTrigonometricPairElaboration', 'NewtonPowerSumRecurrence'],
        },
      ],
      bridges: [{
        id: 'subsequence-pullback',
        witnessStep: 'SubsequencePullback',
        consumes: ['exponent_orbit', 'power_sum_transition'],
        produces: 'indexed_power_sum_inequality',
      }],
      intermediatePropositions: [
        {
          parentId: recurrence.parentId,
          morphism: 'CompanionMatrixIndexGeneration',
          source: 'PositiveSecondOrderRecurrence',
          target: 'StrictlyIncreasingIntegerOrbit',
          proposition: 'the parent recurrence uniquely generates every exponent used by the new problem',
          proved: true,
        },
        {
          parentId: powerParent.parentId,
          morphism: 'NewtonPowerSumRecurrence',
          source: 'SymmetricTrigonometricPair',
          target: 'RationalPowerSumSequence',
          proposition: 'the parent sum and the identity sin^2+cos^2=1 uniquely determine every power sum',
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'ReversibleGeneratedIndexPowerSumIR',
      observable: 'indexed_power_sum_inequality_solution_set',
      operators: morphisms,
      domain: 'number_theory_analysis',
      tags: ['recurrence', 'companion-matrix', 'power-sum', 'newton-sums', 'inequality', 'subsequence', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'recurrence-replay', claim: 'all generated exponents agree with independent companion-matrix powers', verifier: 'BigInt 2x2 matrix kernel' },
        { id: 'power-sum-replay', claim: 'all finite comparisons agree by recurrence and independent matrix exponentiation', verifier: 'exact rational 2x2 matrix kernel' },
        { id: 'tail', claim: `all exponents at least ${cutoff} fail the strict inequality`, verifier: 'exact rational geometric-tail certificate' },
        { id: 'ablation', claim: 'removing either parent makes the indexed observable undefined', verifier: 'typed two-port dependency check' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['positive-second-order-recurrence', 'symmetric-trigonometric-power-sum'],
        querySignature: 'classify-recurrence-indexed-power-sum-inequality',
        normalForm: answer,
        quotientAction: 'rename recurrence, index, exponent, and angle variables',
        freeParameters: ['two initial values', 'two recurrence coefficients', 'rational symmetric sum'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
        numericInstanceConstants: [cutoff, thresholds.odd, thresholds.even],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: Date.now() - startedAt,
    },
  }
  return [
    baseCard,
    ...synthesizeIndexedPowerObservableVariants(baseCard, evaluation, {
      definitionTex: `数列 \\(\\{a_k\\}\\) を\n\\[${recurrenceTex}\\]\nで定める。実数 \\(\\theta\\) が\n\\[\\sin\\theta+\\cos\\theta=${c}\\]\nを満たすとする。`,
      indexSymbol: 'k',
      exponentTex: 'a_k',
      exponentSequenceJa: '漸化式で定まる指数列 \\(a_k\\)',
      independentReplayJa: 'べき和の伴行列と添字列の伴行列による独立計算',
    }, startedAt),
  ].slice(0, Math.max(0, requested))
}
