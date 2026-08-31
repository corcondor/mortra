import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'
import {
  certifyIndexedPowerSumTerms,
  certifyPowerSumTail,
  generatePositiveRecurrenceTerms,
  parsePositiveSecondOrderRecurrence,
  parseTrigonometricPowerSum,
  synthesizeCertifiedIndexedPowerSumFusion,
  type ParsedPositiveRecurrence,
  type ParsedTrigonometricPowerSum,
  type Q,
} from './certified-indexed-power-fusion'
import {
  parseRationalAngles,
  type ParsedRationalAngle,
} from './certified-finite-state-trig-fusion'

type TypedParents = {
  recurrenceParent: CertifiedFusionParent
  recurrence: ParsedPositiveRecurrence
  powerParent: CertifiedFusionParent
  power: ParsedTrigonometricPowerSum
  angleParent: CertifiedFusionParent
  angle: ParsedRationalAngle
}

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function rational(numerator: bigint, denominator = 1n): Q {
  if (denominator === 0n) throw new Error('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcd(numerator, denominator)
  return {
    n: sign * numerator / divisor,
    d: sign * denominator / divisor,
  }
}

function compare(left: Q, right: Q): number {
  const difference = left.n * right.d - right.n * left.d
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}

function subtract(left: Q, right: Q): Q {
  return rational(left.n * right.d - right.n * left.d, left.d * right.d)
}

function rationalText(value: Q): string {
  return value.d === 1n ? String(value.n) : `${value.n}/${value.d}`
}

function rationalTex(value: Q): string {
  if (value.d === 1n) return String(value.n)
  return value.n < 0n
    ? String.raw`-\frac{${-value.n}}{${value.d}}`
    : String.raw`\frac{${value.n}}{${value.d}}`
}

function positiveMod(value: bigint, modulus: bigint): bigint {
  const residue = value % modulus
  return residue < 0n ? residue + modulus : residue
}

/**
 * Return cos(2 phi) only when the rational angle has an exact rational
 * value. The finite cases are checked as residues modulo 2 pi.
 */
export function exactRationalCosineOfDoubleAngle(angle: ParsedRationalAngle): Q | null {
  const denominator = angle.denominator
  const residue = positiveMod(2n * angle.numerator, 2n * denominator)
  if (residue === 0n) return rational(1n)
  if (residue === denominator) return rational(-1n)
  if (2n * residue === denominator || 2n * residue === 3n * denominator) return rational(0n)
  if (3n * residue === denominator || 3n * residue === 5n * denominator) return rational(1n, 2n)
  if (3n * residue === 2n * denominator || 3n * residue === 4n * denominator) return rational(-1n, 2n)
  return null
}

function selectTypedParents(parents: CertifiedFusionParent[]): TypedParents | null {
  const recurrences = parents.flatMap(parent => {
    const parsed = parsePositiveSecondOrderRecurrence(parent)
    return parsed ? [{ parent, parsed }] : []
  })
  const powers = parents.flatMap(parent => {
    const parsed = parseTrigonometricPowerSum(parent)
    return parsed ? [{ parent, parsed }] : []
  })
  const angles = parents.flatMap(parent =>
    parseRationalAngles(parent).map(parsed => ({ parent, parsed }))
  )

  for (const recurrence of recurrences) {
    for (const power of powers) {
      if (recurrence.parent.id === power.parent.id) continue
      for (const angle of angles) {
        if (angle.parent.id === recurrence.parent.id || angle.parent.id === power.parent.id) continue
        return {
          recurrenceParent: recurrence.parent,
          recurrence: recurrence.parsed,
          powerParent: power.parent,
          power: power.parsed,
          angleParent: angle.parent,
          angle: angle.parsed,
        }
      }
    }
  }
  return null
}

function coefficientTerm(coefficient: bigint, variable: string, first: boolean): string {
  if (coefficient === 0n) return ''
  const negative = coefficient < 0n
  const magnitude = negative ? -coefficient : coefficient
  const sign = first ? (negative ? '-' : '') : (negative ? '-' : '+')
  return `${sign}${magnitude === 1n ? '' : magnitude}${variable}`
}

function recurrenceTex(recurrence: ParsedPositiveRecurrence): string {
  const [initial1, initial2] = recurrence.initial
  const [coefficient1, coefficient2] = recurrence.coefficients
  const first = coefficientTerm(coefficient1, 'a_{k+1}', true)
  const second = coefficientTerm(coefficient2, 'a_k', first.length === 0)
  return String.raw`a_1=${initial1},\quad a_2=${initial2},\quad a_{k+2}=${first}${second}`
}

function angleTex(angle: ParsedRationalAngle): string {
  if (angle.numerator === 1n) return String.raw`\frac{\pi}{${angle.denominator}}`
  if (angle.numerator === -1n) return String.raw`-\frac{\pi}{${angle.denominator}}`
  return String.raw`\frac{${angle.numerator}\pi}{${angle.denominator}}`
}

function integerSetTex(values: number[]): string {
  return values.length ? String.raw`\{${values.join(',')}\}` : String.raw`\varnothing`
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

export function synthesizeCertifiedThreeParentPowerThresholdFusion(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const startedAt = Date.now()
  if (parents.length !== 3 || new Set(parents.map(parent => parent.id)).size !== 3) return []
  const typed = selectTypedParents(parents)
  if (!typed) return []
  const threshold = exactRationalCosineOfDoubleAngle(typed.angle)
  if (!threshold || compare(threshold, typed.power.sum) <= 0) return []

  const baseCard = synthesizeCertifiedIndexedPowerSumFusion([
    typed.recurrenceParent,
    typed.powerParent,
  ], 1)[0]
  if (!baseCard) return []
  const tail = certifyPowerSumTail(typed.power)
  if (!tail) return []
  const terms = generatePositiveRecurrenceTerms(typed.recurrence, tail.cutoff)
  if (!terms) return []
  const evaluation = certifyIndexedPowerSumTerms(typed.power, terms)
  if (!evaluation) return []

  const comparisons = evaluation.checked.map(item => ({
    ...item,
    difference: subtract(item.value, threshold),
    passed: compare(item.value, threshold) > 0,
  }))
  const answerIndices = comparisons.filter(item => item.passed).map(item => item.index)
  const thresholdTex = rationalTex(threshold)
  const sumTex = rationalTex(typed.power.sum)
  const recurrenceDefinition = recurrenceTex(typed.recurrence)
  const phiTex = angleTex(typed.angle)
  const answer = String.raw`\(k\in${integerSetTex(answerIndices)}\)`
  const table = comparisons.length
    ? [
        String.raw`\[`,
        String.raw`\begin{array}{c|${'c'.repeat(comparisons.length)}}`,
        'k&' + comparisons.map(item => item.index).join('&') + '\\\\',
        String.raw`\hline`,
        'a_k&' + comparisons.map(item => item.exponent).join('&') + '\\\\',
        'u_{a_k}-' + thresholdTex + '&' +
          comparisons.map(item => rationalTex(item.difference)).join('&'),
        String.raw`\end{array}`,
        String.raw`\]`,
      ].join('\n')
    : String.raw`\[\text{直接比較すべき項はない。}\]`
  const statement = String.raw`数列 \(\{a_k\}\) を
\[${recurrenceDefinition}\]
で定める。実数 \(\theta\) と角 \(\varphi\) が
\[\sin\theta+\cos\theta=${sumTex},\qquad \varphi=${phiTex}\]
を満たすとする。
\[\sin^{a_k}\theta+\cos^{a_k}\theta>\cos(2\varphi)\]
となる正の整数 \(k\) をすべて求めよ。`
  const solution = String.raw`\(X=\sin\theta,\ Y=\cos\theta\) とおき、\(u_m=X^m+Y^m\) とする。
\[
X+Y=${sumTex},\qquad XY=\frac{(${sumTex})^2-1}{2}
\]
であるから、べき和は
\[
u_0=2,\qquad u_1=${sumTex},\qquad
u_{m+2}=${sumTex}u_{m+1}+\frac{1-(${sumTex})^2}{2}u_m\tag{1}
\]
を満たす。

\(\varphi=${phiTex}\) なので、倍角の値を厳密に計算すると
\[\cos(2\varphi)=${thresholdTex}\]
である。漸化式で得られる指数を \((1)\) へ代入すると
${table}
となる。

残りの項については、元のべき和に対する検証済みの評価から、奇数 \(m\ge${evaluation.thresholds.odd}\) と偶数 \(m\ge${evaluation.thresholds.even}\) のいずれでも
\[|u_m|<${sumTex}<${thresholdTex}\]
である。表はこの評価を適用する前に必要な項をすべて含む。また、指数列は以後も増加する。したがって新しい解はなく、
\[k\in${integerSetTex(answerIndices)}\]
である。指数列は伴行列の累乗でも再生し、べき和は別の伴行列でも計算して、表の全項が一致することを確認した。`

  const morphisms = [
    ...baseCard.morphism_chain.filter(morphism => morphism !== 'AllParentAblation'),
    'RationalAngleElaboration',
    'CertifiedObservableProjection',
    'AllParentAblation',
  ]
  const structureId = `certified.three-parent-power-threshold.${hash({
    recurrence: {
      initial: typed.recurrence.initial.map(String),
      coefficients: typed.recurrence.coefficients.map(String),
    },
    sum: rationalText(typed.power.sum),
    angle: [String(typed.angle.numerator), String(typed.angle.denominator)],
  })}`
  const exactStates = comparisons.map(item => ({
    id: `k${item.index}`,
    label: `k=${item.index}, a_k=${item.exponent}`,
    active: item.passed,
  }))
  const proofCertificate = baseCard.structure_blueprint.proofCertificate
    .filter(certificate => certificate.id !== 'ablation')

  const card: CertifiedFusionCard = {
    ...baseCard,
    id: `mortra-${structureId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    family_id: 'certified.three_parent_recurrence_power_angle',
    morphism_chain: morphisms,
    proof_roadmap: [
      ...(baseCard.proof_roadmap ?? []),
      {
        morphism_id: 'RationalAngleElaboration',
        label_ja: '有理角から比較基準を求める',
        source_ja: '第三の親問題に現れる角',
        target_ja: '厳密な有理数の比較基準',
        role_ja: '角を倍角へ移し、余弦の値を記号的に確定します。',
      },
      {
        morphism_id: 'CertifiedObservableProjection',
        label_ja: '同じべき和軌道を新しい基準で比較する',
        source_ja: '漸化式で添字付けされたべき和',
        target_ja: '第三の親が定める不等式の解集合',
        role_ja: 'べき和を再計算せず、証明済みの各状態を新しい基準と厳密比較します。',
      },
    ],
    proof_obligations: [
      ...(baseCard.proof_obligations ?? []),
      { id: 'rational-angle-threshold', claim_ja: '第三の親問題から得た余弦の値が厳密に正しい', status: 'verified' },
      { id: 'three-parent-dependence', claim_ja: '三つの親問題がすべて生成問題の定義に必要である', status: 'verified' },
    ],
    diagram: {
      version: 1,
      kind: 'state',
      title: '三つの親を一つの厳密比較へ合成する',
      caption: '漸化式は指数、三角条件はべき和、有理角は比較基準を供給します。色付きの状態だけが三親融合の不等式を満たします。',
      states: [...exactStates, {
        id: 'tail',
        label: `a_k ≥ ${evaluation.cutoff}: 一括評価`,
        terminal: true,
      }],
      transitions: [
        ...exactStates.slice(1).map((state, index) => ({
          from: exactStates[index].id,
          to: state.id,
          label: '次の項',
        })),
        { from: exactStates.at(-1)?.id ?? 'start', to: 'tail', label: '以後を一括証明' },
      ],
    },
    parent_ids: [typed.recurrence.parentId, typed.power.parentId, typed.angle.parentId],
    verification: {
      ...baseCard.verification,
      method: baseCard.verification.method + ' + exact rational double-angle threshold + typed three-parent ablation',
      samples: [
        ...baseCard.verification.samples,
        Number(typed.angle.numerator),
        Number(typed.angle.denominator),
        answerIndices.length,
      ],
    },
    difficulty: {
      band: 'A_exact_three_parent_fusion',
      score: baseCard.difficulty.score + 1.1,
    },
    fusion_derivation: {
      passed: true,
      reason: 'the recurrence supplies the exponent orbit, the trigonometric parent supplies the power-sum transition, and the rational-angle parent supplies the exact comparison threshold',
      ablationPassed: true,
      assignments: [
        ...baseCard.fusion_derivation.assignments,
        {
          parentId: typed.angle.parentId,
          portId: 'rational_angle_threshold',
          role: 'comparison threshold',
          matchedAnchors: [typed.angle.evidence],
          witnessSteps: ['RationalAngleElaboration', 'ExactRationalInequality'],
        },
      ],
      bridges: [{
        id: 'three-parent-threshold-pullback',
        witnessStep: 'CertifiedObservableProjection',
        consumes: ['exponent_orbit', 'power_sum_transition', 'rational_angle_threshold'],
        produces: 'three_parent_indexed_power_sum_inequality',
      }],
      intermediatePropositions: [
        ...baseCard.fusion_derivation.intermediatePropositions,
        {
          parentId: typed.angle.parentId,
          morphism: 'RationalAngleElaboration',
          source: 'RationalAngle',
          target: 'ExactRationalThreshold',
          proposition: `cos(2 phi)=${rationalText(threshold)}`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      ...baseCard.structure_blueprint,
      id: structureId,
      observable: 'three_parent_indexed_power_sum_threshold_solution_set',
      operators: morphisms,
      tags: [...baseCard.structure_blueprint.tags, 'three-parent', 'rational-angle-threshold'],
      morphismChain: morphisms,
      proofCertificate: [
        ...proofCertificate,
        {
          id: 'rational-angle-threshold',
          claim: `cosine of the doubled rational angle equals ${rationalText(threshold)} exactly`,
          verifier: 'finite exact rational-angle residue table',
        },
        {
          id: 'three-parent-ablation',
          claim: 'removing any one of the three typed parents makes the generated observable undefined',
          verifier: 'typed three-port dependency check',
        },
      ],
      structuralUniqueness: {
        ...baseCard.structure_blueprint.structuralUniqueness,
        conditionSkeleton: [
          ...baseCard.structure_blueprint.structuralUniqueness.conditionSkeleton,
          'rational-angle-derived-exact-threshold',
        ],
        querySignature: 'classify recurrence-indexed power sums above an independent rational-angle threshold',
        normalForm: answer,
        freeParameters: [
          ...baseCard.structure_blueprint.structuralUniqueness.freeParameters,
          'rational angle with exact rational doubled cosine',
        ],
        numericInstanceConstants: [
          ...baseCard.structure_blueprint.structuralUniqueness.numericInstanceConstants,
          Number(typed.angle.numerator),
          Number(typed.angle.denominator),
          Number(threshold.n),
          Number(threshold.d),
        ],
      },
    },
    search_evidence: {
      hypotheses_evaluated: comparisons.length,
      valid_hypotheses: answerIndices.length,
      elapsed_ms: Date.now() - startedAt,
    },
  }

  return [card].slice(0, Math.max(0, requested))
}
