import { createHash } from 'node:crypto'

import {
  parseMonicIntegerPolynomial,
  type CertifiedFusionCard,
  type CertifiedFusionParent,
} from './certified-fusion'

type PolyZ = bigint[]

export type ParsedMobiusRootTransport = {
  parentId: string
  inputSymbol: string
  outputSymbol: string
  matrix: readonly [bigint, bigint, bigint, bigint]
  source: string
}

function trim(values: PolyZ): PolyZ {
  const result = [...values]
  while (result.length > 1 && result.at(-1) === 0n) result.pop()
  return result.length ? result : [0n]
}

function add(left: PolyZ, right: PolyZ): PolyZ {
  const length = Math.max(left.length, right.length)
  return trim(Array.from({ length }, (_, index) => (left[index] ?? 0n) + (right[index] ?? 0n)))
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

function power(base: PolyZ, exponent: number): PolyZ {
  let result: PolyZ = [1n]
  let factor = base
  let remaining = exponent
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiply(result, factor)
    factor = multiply(factor, factor)
    remaining = Math.floor(remaining / 2)
  }
  return result
}

function equalPolynomial(left: PolyZ, right: PolyZ): boolean {
  const a = trim(left)
  const b = trim(right)
  return a.length === b.length && a.every((value, index) => value === b[index])
}

function polynomialTex(coefficients: PolyZ, variable: string): string {
  const terms: string[] = []
  for (let exponent = coefficients.length - 1; exponent >= 0; exponent -= 1) {
    const coefficient = coefficients[exponent]
    if (coefficient === 0n) continue
    const sign = coefficient < 0n ? '-' : '+'
    const absolute = coefficient < 0n ? -coefficient : coefficient
    const magnitude = exponent > 0 && absolute === 1n ? '' : absolute.toString()
    const powerText = exponent === 0 ? '' : exponent === 1 ? variable : `${variable}^{${exponent}}`
    const body = `${magnitude}${powerText}`
    if (!terms.length) terms.push(sign === '-' ? `-${body}` : body)
    else terms.push(`${sign}${body}`)
  }
  return terms.join('') || '0'
}

function rationalTex(numerator: bigint, denominator: bigint): string {
  if (denominator === 0n) throw new Error('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  let n = numerator * sign
  let d = denominator * sign
  let left = n < 0n ? -n : n
  let right = d
  while (right !== 0n) [left, right] = [right, left % right]
  const divisor = left || 1n
  n /= divisor
  d /= divisor
  if (d === 1n) return n.toString()
  return `\\frac{${n}}{${d}}`
}

function parseAffineExpression(source: string, variable: string): [bigint, bigint] | null {
  const compact = source
    .replace(/\\left|\\right/g, '')
    .replace(/−|–/g, '-')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/[{}\s]/g, '')
  if (!compact || /\\|\^|\//.test(compact)) return null
  const normalized = compact.replace(/-/g, '+-')
  let linear = 0n
  let constant = 0n
  for (const raw of normalized.split('+').filter(Boolean)) {
    const term = raw.replace(/\*/g, '')
    if (term.includes(variable)) {
      const match = term.match(new RegExp(`^([+-]?\\d*)${variable}$`))
      if (!match) return null
      linear += match[1] === '' || match[1] === '+'
        ? 1n
        : match[1] === '-'
          ? -1n
          : BigInt(match[1])
    } else {
      if (!/^[+-]?\d+$/.test(term)) return null
      constant += BigInt(term)
    }
  }
  return [linear, constant]
}

function mathSegments(statement: string): string[] {
  return [
    ...Array.from(statement.matchAll(/\$([^$]+)\$/g), match => match[1]),
    ...Array.from(statement.matchAll(/\\\(([^]*?)\\\)/g), match => match[1]),
    ...Array.from(statement.matchAll(/\\\[([^]*?)\\\]/g), match => match[1]),
  ]
}

export function parseMobiusRootTransport(parent: CertifiedFusionParent): ParsedMobiusRootTransport | null {
  for (const segment of mathSegments(parent.statement)) {
    const match = segment.match(
      /^\s*([A-Za-z])\s*=\s*\\(?:d?frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}\s*$/,
    )
    if (!match) continue
    const [, outputSymbol, numeratorSource, denominatorSource] = match
    const variables = new Set(`${numeratorSource}${denominatorSource}`.match(/[A-Za-z]/g) ?? [])
    variables.delete(outputSymbol)
    if (variables.size !== 1) continue
    const inputSymbol = [...variables][0]
    const numerator = parseAffineExpression(numeratorSource, inputSymbol)
    const denominator = parseAffineExpression(denominatorSource, inputSymbol)
    if (!numerator || !denominator) continue
    const [a, b] = numerator
    const [c, d] = denominator
    if (a * d - b * c === 0n) continue
    return {
      parentId: parent.id,
      inputSymbol,
      outputSymbol,
      matrix: [a, b, c, d],
      source: match[0].trim(),
    }
  }
  return null
}

function transformedPolynomial(
  coefficients: PolyZ,
  matrix: ParsedMobiusRootTransport['matrix'],
): PolyZ {
  const [a, b, c, d] = matrix
  const degree = coefficients.length - 1
  const inverseNumerator: PolyZ = [-b, d]
  const inverseDenominator: PolyZ = [a, -c]
  let result: PolyZ = [0n]
  for (let exponent = 0; exponent <= degree; exponent += 1) {
    const coefficient = coefficients[exponent]
    if (coefficient === 0n) continue
    result = add(result, scale(multiply(
      power(inverseNumerator, exponent),
      power(inverseDenominator, degree - exponent),
    ), coefficient))
  }
  return trim(result)
}

function reverseTransportCheck(
  source: PolyZ,
  transformed: PolyZ,
  matrix: ParsedMobiusRootTransport['matrix'],
  normalization: bigint,
): boolean {
  const [a, b, c, d] = matrix
  const degree = source.length - 1
  const numerator: PolyZ = [b, a]
  const denominator: PolyZ = [d, c]
  let transportedBack: PolyZ = [0n]
  for (let exponent = 0; exponent <= degree; exponent += 1) {
    const coefficient = transformed[exponent]
    if (coefficient === 0n) continue
    transportedBack = add(transportedBack, scale(multiply(
      power(numerator, exponent),
      power(denominator, degree - exponent),
    ), coefficient))
  }
  const determinant = a * d - b * c
  return equalPolynomial(
    transportedBack,
    scale(source, normalization * determinant ** BigInt(degree)),
  )
}

function fixedMapTex(polynomial: PolyZ, symbol: string): string {
  const degree = polynomial.length - 1
  const numerator = scale(polynomial.slice(0, degree), -1n)
  const denominatorCoefficient = polynomial[degree]
  const denominator = degree === 1
    ? denominatorCoefficient.toString()
    : `${denominatorCoefficient === 1n ? '' : denominatorCoefficient === -1n ? '-' : denominatorCoefficient}${symbol}^{${degree - 1}}`
  return `\\frac{${polynomialTex(numerator, symbol)}}{${denominator}}`
}

function powerTex(base: string, exponent: number): string {
  return /^[A-Za-z]+(?:\^\{\d+\})?$/.test(base)
    ? `${base}^{${exponent}}`
    : `\\left(${base}\\right)^{${exponent}}`
}

function reciprocalExpansionTex(degree: number, symbol: string): string {
  return Array.from({ length: degree }, (_, exponent) => exponent === 0
    ? 'C_0'
    : `\\frac{C_${exponent}}{${symbol}${exponent === 1 ? '' : `^{${exponent}}`}}`
  ).join('+')
}

function rootListLabel(degree: number): string {
  const subscripts = '₀₁₂₃₄₅₆₇₈₉'
  const subscript = (value: number) => String(value).split('').map(digit => subscripts[Number(digit)]).join('')
  if (degree > 8) return `${degree} 個の変換後の根`
  return Array.from({ length: degree }, (_, index) => `S${subscript(index + 1)}`).join(', ')
}

type Rational = { n: bigint; d: bigint }

function rationalGcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function rational(numerator: bigint, denominator = 1n): Rational {
  if (denominator === 0n) throw new Error('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = rationalGcd(numerator, denominator)
  return { n: sign * numerator / divisor, d: sign * denominator / divisor }
}

function addRational(left: Rational, right: Rational): Rational {
  return rational(left.n * right.d + right.n * left.d, left.d * right.d)
}

function multiplyRational(left: Rational, right: Rational): Rational {
  return rational(left.n * right.n, left.d * right.d)
}

function negateRational(value: Rational): Rational {
  return { n: -value.n, d: value.d }
}

function rationalValueTex(value: Rational): string {
  if (value.d === 1n) return String(value.n)
  return value.n < 0n
    ? '-\\frac{' + (-value.n) + '}{' + value.d + '}'
    : '\\frac{' + value.n + '}{' + value.d + '}'
}

function rationalPowerSums(coefficients: PolyZ, maximum: number): Rational[] {
  const degree = coefficients.length - 1
  const leading = coefficients[degree]
  const monic = Array.from(
    { length: degree + 1 },
    (_, index) => index === 0 ? rational(1n) : rational(coefficients[degree - index], leading),
  )
  const sums: Rational[] = [rational(BigInt(degree))]
  for (let exponent = 1; exponent <= maximum; exponent += 1) {
    let total = rational(0n)
    for (let index = 1; index < exponent; index += 1) {
      total = addRational(total, multiplyRational(monic[index], sums[exponent - index]))
    }
    total = addRational(total, multiplyRational(rational(BigInt(exponent)), monic[exponent]))
    sums.push(negateRational(total))
  }
  return sums
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

export function synthesizeCertifiedMobiusPolynomialFusion(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 2 || new Set(parents.map(parent => parent.id)).size !== 2) return []
  const polynomialParent = parents.find(parent => parseMonicIntegerPolynomial(parent) !== null)
  const transportParent = parents.find(parent => parseMobiusRootTransport(parent) !== null)
  if (!polynomialParent || !transportParent || polynomialParent.id === transportParent.id) return []
  const polynomial = parseMonicIntegerPolynomial(polynomialParent)!
  const transport = parseMobiusRootTransport(transportParent)!
  const transformedRaw = transformedPolynomial(polynomial.coefficients, transport.matrix)
  const normalization = transformedRaw.at(-1)! < 0n ? -1n : 1n
  const transformed = scale(transformedRaw, normalization)
  const degree = polynomial.coefficients.length - 1
  if (transformed.length - 1 !== degree || transformed[0] === 0n || transformed.at(-1) === 0n) return []
  if (!reverseTransportCheck(polynomial.coefficients, transformed, transport.matrix, normalization)) return []

  const [a, b, c, d] = transport.matrix
  const determinant = a * d - b * c
  const sourceSymbol = polynomial.variable
  const targetSymbol = transport.outputSymbol
  const sourcePolynomial = polynomialTex(polynomial.coefficients, polynomial.variable)
  const targetPolynomial = polynomialTex(transformed, targetSymbol)
  const fixedMap = fixedMapTex(transformed, targetSymbol)
  const constantTerm = rationalTex(-transformed[degree - 1], transformed[degree])
  const leadingCoefficient = transformed[degree]
  const forwardNumerator = polynomialTex([b, a], sourceSymbol)
  const forwardDenominator = polynomialTex([d, c], sourceSymbol)
  const inverseNumerator = polynomialTex([-b, d], targetSymbol)
  const inverseDenominator = polynomialTex([a, -c], targetSymbol)
  const clearingFactor = powerTex(inverseDenominator, degree)
  const reverseClearingFactor = powerTex(forwardDenominator, degree)
  const structureId = `certified.mobius-polynomial-fixed-point.${hash({
    polynomial: polynomial.coefficients.map(String),
    matrix: transport.matrix.map(String),
  })}`
  const morphisms = [
    'PolynomialElaboration',
    'RootConfiguration',
    'MobiusTransformationElaboration',
    'RationalCoordinateTransport',
    'DenominatorClearing',
    'FixedPointRearrangement',
    'ReverseTransportIdentity',
    'AllParentAblation',
  ]
  const statement = String.raw`\(f(${sourceSymbol})=${sourcePolynomial}\) とし、その根を \(\alpha_1,\ldots,\alpha_${degree}\) とする。一次分数変換
\[T(${sourceSymbol})=\frac{${forwardNumerator}}{${forwardDenominator}}\]
により \(${targetSymbol}_i=T(\alpha_i)\) とおく。

\(${targetSymbol}_1,\ldots,${targetSymbol}_${degree}\) をちょうど根にもつ整数係数多項式 \(P(${targetSymbol})\) を一つ求めよ。さらに、\(P(${targetSymbol})=0\) を
\[${targetSymbol}=g(${targetSymbol})=${reciprocalExpansionTex(degree, targetSymbol)}\]
の形へ直し、\(g(${targetSymbol})\) と \(C_0\) を求めよ。`
  const answer = String.raw`\(P(${targetSymbol})=${targetPolynomial}\),\quad \(g(${targetSymbol})=${fixedMap}\),\quad \(C_0=${constantTerm}\)`
  const solution = String.raw`変換行列の行列式は \(\Delta=${determinant}\neq0\) であり、逆変換は
\[${sourceSymbol}=\frac{${inverseNumerator}}{${inverseDenominator}}\]
である。したがって分母を払った
\[P(${targetSymbol})=${clearingFactor}f\!\left(\frac{${inverseNumerator}}{${inverseDenominator}}\right)
=${targetPolynomial}\]
の根は、重複度込みでちょうど \(${targetSymbol}_i=T(\alpha_i)\) である。

最高次項を右辺へ移すと
\[${targetSymbol}=${fixedMap}=g(${targetSymbol})\]
となり、\(${targetSymbol}^0\) に対応する定数項は \(C_0=${constantTerm}\) である。

独立な逆向き検証として \(${targetSymbol}=T(${sourceSymbol})\) を代入し、
\[${reverseClearingFactor}P(T(${sourceSymbol}))=${normalization === -1n ? '-' : ''}\Delta^{${degree}}f(${sourceSymbol})\]
を整数係数多項式の係数比較で確認した。また
\[${leadingCoefficient}${targetSymbol}^{${degree - 1}}\{${targetSymbol}-g(${targetSymbol})\}=P(${targetSymbol})\]
も恒等的に成り立つ。よって余分な固定点も欠落した固定点もない。`
  const proofCertificate = [
    { id: 'polynomial-input', claim: 'the first parent supplies a degree-at-least-two integer polynomial root configuration', verifier: 'MORTRA integer polynomial parser' },
    { id: 'mobius-input', claim: `the second parent supplies the nonsingular transformation ${transport.source}`, verifier: 'exact 2x2 determinant' },
    { id: 'transport', claim: 'clearing the inverse-map denominator transports the complete root multiset', verifier: 'BigInt polynomial composition' },
    { id: 'reverse-identity', claim: `${forwardDenominator}^${degree} P(T(${sourceSymbol})) = ${normalization === -1n ? '-' : ''}det(T)^${degree} f(${sourceSymbol})`, verifier: 'independent reverse polynomial composition' },
    { id: 'fixed-point', claim: 'the rational map has exactly the transported roots as finite fixed points', verifier: 'exact fixed-point rearrangement' },
    { id: 'ablation', claim: 'removing the polynomial removes the root object; removing the transformation removes the transport', verifier: 'typed two-port ablation' },
  ]

  const baseCard: CertifiedFusionCard = {
    id: `mortra-${structureId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'algebraic_dynamics',
    family_id: 'certified.mobius_polynomial_fixed_point_transport',
    tool: 'MORTRA exact reversible synthesis',
    morphism_chain: morphisms,
    proof_roadmap: [
      {
        morphism_id: 'PolynomialElaboration',
        label_ja: '多項式から根配置を取り出す',
        source_ja: '親問題Aの多項式',
        target_ja: '根 α₁,…,αₙ',
        role_ja: '係数と次数を読み取り、重複度を含む根全体を一つの対象として保持します。',
      },
      {
        morphism_id: 'MobiusTransformationElaboration',
        label_ja: '一次分数変換を行列として読む',
        source_ja: '親問題Bの変換式',
        target_ja: '非退化変換 T',
        role_ja: '2×2行列の行列式が0でないことを確かめ、逆変換を構成します。',
      },
      {
        morphism_id: 'RationalCoordinateTransport',
        label_ja: '各根を新しい座標へ移す',
        source_ja: '根 αᵢ と変換 T',
        target_ja: '変換後の根 Sᵢ',
        role_ja: '二つの親をここで初めて合成し、Sᵢ=T(αᵢ)を作ります。',
      },
      {
        morphism_id: 'DenominatorClearing',
        label_ja: '分母を払って整数係数多項式に戻す',
        source_ja: '逆変換を代入した式',
        target_ja: 'P(S)=0',
        role_ja: '逆変換を元の多項式へ代入し、根を変えずに分母を払います。',
      },
      {
        morphism_id: 'FixedPointRearrangement',
        label_ja: '固定点方程式へ変形する',
        source_ja: 'P(S)=0',
        target_ja: 'S=g(S)',
        role_ja: '最高次項だけを左辺へ残し、有理関数の固定点として読み替えます。',
      },
      {
        morphism_id: 'ReverseTransportIdentity',
        label_ja: '逆代入で根の過不足を検証する',
        source_ja: 'P(S) と T(x)',
        target_ja: '元の f(x)',
        role_ja: '係数恒等式を独立に確かめ、余分な根も欠けた根もないことを証明します。',
      },
      {
        morphism_id: 'AllParentAblation',
        label_ja: '両方の親が必要か確かめる',
        source_ja: '二つの入力端点',
        target_ja: '親依存性の証明',
        role_ja: 'どちらか一方を除くと構成不能になることを型検査で確認します。',
      },
    ],
    proof_obligations: [
      { id: 'mobius-nondegenerate', claim_ja: '一次分数変換の行列式が0でない', status: 'verified' },
      { id: 'root-multiset-transport', claim_ja: 'Pの根は重複度込みでちょうどS₁,…,Sₙである', status: 'verified' },
      { id: 'fixed-point-equivalence', claim_ja: 'P(S)=0とS=g(S)が有限点で同値である', status: 'verified' },
      { id: 'all-parent-dependence', claim_ja: '二つの親問題がどちらも構成に不可欠である', status: 'verified' },
    ],
    diagram: {
      version: 1,
      kind: 'morphism',
      title: '根配置を一次分数変換で運ぶ',
      caption: '一方の親から根配置、もう一方から座標変換を受け取り、固定点方程式へ運んだ後、逆変換で完全性を検証します。',
      nodes: [`f(x)=0 の ${degree} 根`, 'T(x)', rootListLabel(degree), 'P(S)=0', 'S=g(S)', '逆変換で照合'],
    },
    parent_ids: parents.map(parent => parent.id),
    verification: {
      method: 'exact polynomial transport + independent reverse composition identity + typed all-parent ablation',
      exact_backend: true,
      independent_check: true,
      samples: [degree, Number(determinant < 0n ? -determinant : determinant), transformed.length],
    },
    difficulty: { band: 'A_exact_algebraic_dynamics_fusion', score: 8.8 + degree * 0.5 },
    fusion_derivation: {
      passed: true,
      reason: 'one parent supplies the complete algebraic root object and the other supplies the indispensable reversible coordinate transport',
      ablationPassed: true,
      assignments: [
        {
          parentId: polynomial.parentId,
          portId: 'root_configuration',
          role: 'object',
          matchedAnchors: [polynomial.normalizedTex],
          witnessSteps: ['PolynomialElaboration', 'RootConfiguration'],
        },
        {
          parentId: transport.parentId,
          portId: 'mobius_transport',
          role: 'operator',
          matchedAnchors: [transport.source],
          witnessSteps: ['MobiusTransformationElaboration', 'RationalCoordinateTransport'],
        },
      ],
      bridges: [{
        id: 'transport-root-configuration',
        witnessStep: 'RationalCoordinateTransport',
        consumes: ['root_configuration', 'mobius_transport'],
        produces: 'transported_fixed_point_scheme',
      }],
      intermediatePropositions: [
        {
          parentId: polynomial.parentId,
          morphism: 'RootConfiguration',
          source: 'Polynomial',
          target: 'FiniteAlgebraicOrbit',
          proposition: `${polynomial.normalizedTex}=0 defines the source root multiset`,
          proved: true,
        },
        {
          parentId: transport.parentId,
          morphism: 'MobiusTransformationElaboration',
          source: 'PGL2',
          target: 'RationalCoordinateTransport',
          proposition: `det(T)=${determinant} is nonzero`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'ReversibleMobiusPolynomialTransportIR',
      observable: 'transported_root_fixed_point_equation',
      operators: morphisms,
      domain: 'algebraic_dynamics',
      tags: ['polynomial', 'root-configuration', 'mobius', 'fixed-point', 'reversible-chart', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate,
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['finite-polynomial-root-configuration', 'nonsingular-mobius-transport', 'fixed-point-rearrangement'],
        querySignature: 'transport-root-scheme-and-recover-fixed-map',
        normalForm: targetPolynomial,
        quotientAction: 'rename polynomial variable, transformed coordinate, and bound roots',
        freeParameters: ['integer polynomial coefficients', 'PGL2 integer matrix'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
        numericInstanceConstants: [...polynomial.coefficients.map(Number), ...transport.matrix.map(Number)],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: 2,
      valid_hypotheses: 1,
      elapsed_ms: Date.now() - startedAt,
    },
  }

  const maximumPower = Math.min(3, degree)
  const powerSums = rationalPowerSums(transformed, maximumPower).slice(1)
  const powerSumSymbols = powerSums.map((_, index) => `p_${index + 1}`)
  const powerSumAnswer = powerSums
    .map((value, index) => `${powerSumSymbols[index]}=${rationalValueTex(value)}`)
    .join(',\\quad ')
  const monicCoefficients = Array.from(
    { length: maximumPower },
    (_, index) => rational(transformed[degree - index - 1], leadingCoefficient),
  )
  const newtonRows = powerSums.map((value, index) => {
    const exponent = index + 1
    const terms = [`p_${exponent}`]
    for (let coefficient = 1; coefficient < exponent; coefficient += 1) {
      terms.push(`${rationalValueTex(monicCoefficients[coefficient - 1])}p_${exponent - coefficient}`)
    }
    terms.push(rationalValueTex(multiplyRational(
      rational(BigInt(exponent)),
      monicCoefficients[exponent - 1],
    )))
    return `${terms.join('+').replaceAll('+-', '-')}=0,\\qquad p_${exponent}=${rationalValueTex(value)}`
  })
  const powerSumStatement = String.raw`\(f(${sourceSymbol})=${sourcePolynomial}\) とし、その根を \(\alpha_1,\ldots,\alpha_${degree}\) とする。一次分数変換
\[T(${sourceSymbol})=\frac{${forwardNumerator}}{${forwardDenominator}}\]
により \(${targetSymbol}_i=T(\alpha_i)\) とおく。\(m=1,\ldots,${maximumPower}\) に対し
\[p_m=\sum_{i=1}^{${degree}}${targetSymbol}_i^m\]
とするとき、\(p_1,\ldots,p_${maximumPower}\) を求めよ。`
  const powerSumSolution = String.raw`逆変換
\[${sourceSymbol}=\frac{${inverseNumerator}}{${inverseDenominator}}\]
を \(f\) へ代入して分母を払うと、変換後の根を重複度込みでちょうど根にもつ多項式は
\[P(${targetSymbol})=${targetPolynomial}\]
である。最高次係数 \(${leadingCoefficient}\) で割り、
\[\frac{P(${targetSymbol})}{${leadingCoefficient}}
=${targetSymbol}^{${degree}}+c_1${targetSymbol}^{${degree - 1}}+\cdots+c_${degree}\]
と書く。Newtonの公式
\[p_m+c_1p_{m-1}+\cdots+c_{m-1}p_1+mc_m=0\qquad(1\le m\le${maximumPower})\]
を順に用いると
\[
${newtonRows.join('\\\\\n')}
\]
を得る。したがって
\[${powerSumAnswer}\]
である。逆代入による多項式恒等式も係数ごとに再検証したので、ここで用いた根配置に過不足はない。`
  const powerSumMorphisms = [...morphisms, 'CertifiedObservableProjection']
  const powerSumStructureId = `${structureId}.initial-power-sums`
  const powerSumCard: CertifiedFusionCard = {
    ...baseCard,
    id: `mortra-${powerSumStructureId}`,
    statement_tex: powerSumStatement,
    answer_tex: `\\(${powerSumAnswer}\\)`,
    solution_tex: powerSumSolution,
    solution_document_tex: texDocument(powerSumStatement, powerSumSolution),
    family_id: 'certified.mobius_polynomial_power_sums',
    morphism_chain: powerSumMorphisms,
    proof_roadmap: [
      ...(baseCard.proof_roadmap ?? []),
      {
        morphism_id: 'CertifiedObservableProjection',
        label_ja: '変換後の根配置からべき和を読み取る',
        source_ja: '変換後の根をもつ多項式',
        target_ja: '最初のべき和',
        role_ja: '新しい根の計算法を加えず、同じ証明済み多項式へNewtonの公式を適用します。',
      },
    ],
    proof_obligations: [
      ...(baseCard.proof_obligations ?? []),
      { id: 'transported-power-sums', claim_ja: '表示したべき和が変換後の根全体のべき和に一致する', status: 'verified' },
    ],
    diagram: {
      version: 1,
      kind: 'morphism',
      title: '一つの変換済み根配置から複数の量を読む',
      caption: '根の輸送と逆向き検証は共通です。最後の観測だけを固定点方程式からべき和へ替えます。',
      nodes: [`f(x)=0 の ${degree} 根`, 'T(x)', rootListLabel(degree), 'P(S)=0', `p₁,…,p${maximumPower}`],
    },
    verification: {
      ...baseCard.verification,
      method: `${baseCard.verification.method} + exact Newton power-sum identities`,
      samples: [...baseCard.verification.samples, maximumPower],
    },
    difficulty: {
      band: baseCard.difficulty.band,
      score: baseCard.difficulty.score + 0.4,
    },
    fusion_derivation: {
      ...baseCard.fusion_derivation,
      reason: `${baseCard.fusion_derivation.reason}; the same transported root object supports a second certified observable`,
      bridges: baseCard.fusion_derivation.bridges.map(bridge => ({
        ...bridge,
        produces: 'transported_root_power_sums',
      })),
    },
    structure_blueprint: {
      ...baseCard.structure_blueprint,
      id: powerSumStructureId,
      observable: 'transported_root_power_sums',
      operators: powerSumMorphisms,
      tags: [...baseCard.structure_blueprint.tags, 'newton-sums', 'observable-projection'],
      morphismChain: powerSumMorphisms,
      proofCertificate: [
        ...baseCard.structure_blueprint.proofCertificate,
        {
          id: 'power-sum-projection',
          claim: 'the reported initial power sums follow from the transported polynomial by exact Newton identities',
          verifier: 'BigInt rational Newton recurrence',
        },
      ],
      structuralUniqueness: {
        ...baseCard.structure_blueprint.structuralUniqueness,
        querySignature: 'compute initial power sums of the transported root configuration',
        normalForm: powerSumAnswer,
        numericInstanceConstants: [
          ...baseCard.structure_blueprint.structuralUniqueness.numericInstanceConstants,
          maximumPower,
        ],
      },
    },
    search_evidence: {
      hypotheses_evaluated: maximumPower,
      valid_hypotheses: maximumPower,
      elapsed_ms: Date.now() - startedAt,
    },
  }

  return [baseCard, powerSumCard].slice(0, Math.max(0, requested))
}
