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
import {
  exactRationalCosineOfDoubleAngle,
  selectCertifiedRationalAngleQuadraticComparisons,
  verifyRationalAngleQuadraticCertificate,
  type RationalAngleQuadraticProjection,
} from './exact-rational-angle-order'

export { exactRationalCosineOfDoubleAngle } from './exact-rational-angle-order'

type TypedParents = {
  recurrenceParent: CertifiedFusionParent
  recurrence: ParsedPositiveRecurrence
  powerParent: CertifiedFusionParent
  power: ParsedTrigonometricPowerSum
  angleParent: CertifiedFusionParent
  angle: ParsedRationalAngle
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

function quadraticProjectionTex(
  angle: ParsedRationalAngle,
  projection: RationalAngleQuadraticProjection,
): string {
  const operator = projection === 'sine_squared' ? String.raw`\sin^2` : String.raw`\cos^2`
  return String.raw`${operator}\!\left(${angleTex(angle)}\right)`
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
  const certifiedThreshold = selectCertifiedRationalAngleQuadraticComparisons(
    typed.angle,
    typed.power.sum,
    evaluation.checked.map(item => item.value),
  )
  if (!certifiedThreshold) return []
  if (!verifyRationalAngleQuadraticCertificate(certifiedThreshold.certificate)) return []

  const comparisons = evaluation.checked.map((item, index) => ({
    ...item,
    relation: certifiedThreshold.comparisons[index].relation,
    passed: certifiedThreshold.comparisons[index].relation === 'greater',
  }))
  const answerIndices = comparisons.filter(item => item.passed).map(item => item.index)
  const thresholdTex = quadraticProjectionTex(
    typed.angle,
    certifiedThreshold.certificate.projection,
  )
  const exactThresholdTex = certifiedThreshold.certificate.exactValue
    ? rationalTex(certifiedThreshold.certificate.exactValue)
    : null
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
          comparisons.map(item => item.passed ? '>0' : '<0').join('&'),
        String.raw`\end{array}`,
        String.raw`\]`,
      ].join('\n')
    : String.raw`\[\text{直接比較すべき項はない。}\]`
  const statement = String.raw`数列 \(\{a_k\}\) を
\[${recurrenceDefinition}\]
で定める。実数 \(\theta\) と角 \(\varphi\) が
\[\sin\theta+\cos\theta=${sumTex},\qquad \varphi=${phiTex}\]
を満たすとする。
\[\sin^{a_k}\theta+\cos^{a_k}\theta>${thresholdTex}\]
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

\(\varphi=${phiTex}\) なので、倍角の恒等式
\[
\sin^2\varphi=\frac{1-\cos(2\varphi)}2,\qquad
\cos^2\varphi=\frac{1+\cos(2\varphi)}2
\]
により、比較基準を \(${thresholdTex}\) とする。${exactThresholdTex
    ? String.raw`この値は厳密に \(${exactThresholdTex}\) である。`
    : String.raw`この代数的数との大小は、Machin の公式による \(\pi\) の有理上下界と、余弦級数の交代級数剰余を用いて有理数の大小へ還元した。`}
漸化式で得られる指数を \((1)\) へ代入すると
${table}
となる。

残りの項については、元のべき和に対する検証済みの評価から、奇数 \(m\ge${evaluation.thresholds.odd}\) と偶数 \(m\ge${evaluation.thresholds.even}\) のいずれでも
\[|u_m|<${sumTex}<${thresholdTex}\]
である。表はこの評価を適用する前に必要な項をすべて含む。また、指数列は以後も増加する。したがって新しい解はなく、
\[k\in${integerSetTex(answerIndices)}\]
である。指数列は伴行列の累乗でも再生し、べき和は別の伴行列でも計算して、表の全項が一致することを確認した。`

  const morphisms = [
    ...baseCard.morphism_chain.filter(morphism => morphism !== 'AllParentAblation'),
    'RationalAngleQuadraticProjection',
    'CertifiedAlgebraicOrderComparison',
    'AllParentAblation',
  ]
  const structureId = `certified.three-parent-power-threshold.${hash({
    recurrence: {
      initial: typed.recurrence.initial.map(String),
      coefficients: typed.recurrence.coefficients.map(String),
    },
    sum: rationalText(typed.power.sum),
    angle: [String(typed.angle.numerator), String(typed.angle.denominator)],
    projection: certifiedThreshold.certificate.projection,
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
        morphism_id: 'RationalAngleQuadraticProjection',
        label_ja: '有理角を二次の三角量へ写す',
        source_ja: '第三の親問題に現れる角',
        target_ja: '厳密な代数的比較基準',
        role_ja: '倍角公式により、有理角を正の二次量へ可逆に変換します。',
      },
      {
        morphism_id: 'CertifiedAlgebraicOrderComparison',
        label_ja: 'べき和と代数的数を厳密比較する',
        source_ja: '漸化式で添字付けされたべき和',
        target_ja: '第三の親が定める不等式の解集合',
        role_ja: '有理上下界が分離するまで精密化し、各状態の符号を証明します。',
      },
    ],
    proof_obligations: [
      ...(baseCard.proof_obligations ?? []),
      { id: 'rational-angle-threshold', claim_ja: '第三の親問題から得た二次三角量の上下界が厳密に正しい', status: 'verified' },
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
      method: baseCard.verification.method + ' + exact algebraic rational-angle comparison + typed three-parent ablation',
      samples: [
        ...baseCard.verification.samples,
        Number(typed.angle.numerator),
        Number(typed.angle.denominator),
        certifiedThreshold.certificate.cosineTaylorTerms,
        answerIndices.length,
      ],
    },
    difficulty: {
      band: 'A_exact_three_parent_fusion',
      score: baseCard.difficulty.score + 1.1,
    },
    fusion_derivation: {
      passed: true,
      reason: 'the recurrence supplies the exponent orbit, the trigonometric parent supplies the power-sum transition, and the rational-angle parent supplies a certified algebraic comparison threshold',
      ablationPassed: true,
      assignments: [
        ...baseCard.fusion_derivation.assignments,
        {
          parentId: typed.angle.parentId,
          portId: 'rational_angle_quadratic_threshold',
          role: 'comparison threshold',
          matchedAnchors: [typed.angle.evidence],
          witnessSteps: ['RationalAngleQuadraticProjection', 'CertifiedAlgebraicOrderComparison'],
        },
      ],
      bridges: [{
        id: 'three-parent-threshold-pullback',
        witnessStep: 'CertifiedAlgebraicOrderComparison',
        consumes: ['exponent_orbit', 'power_sum_transition', 'rational_angle_quadratic_threshold'],
        produces: 'three_parent_indexed_power_sum_inequality',
      }],
      intermediatePropositions: [
        ...baseCard.fusion_derivation.intermediatePropositions,
        {
          parentId: typed.angle.parentId,
          morphism: 'RationalAngleQuadraticProjection',
          source: 'RationalAngle',
          target: 'CertifiedAlgebraicThreshold',
          proposition: `${certifiedThreshold.certificate.projection}(${typed.angle.numerator}/${typed.angle.denominator} pi)=${thresholdTex}`,
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      ...baseCard.structure_blueprint,
      id: structureId,
      observable: 'three_parent_indexed_power_sum_quadratic_angle_threshold_solution_set',
      operators: morphisms,
      tags: [...baseCard.structure_blueprint.tags, 'three-parent', 'rational-angle-threshold'],
      morphismChain: morphisms,
      proofCertificate: [
        ...proofCertificate,
        {
          id: 'rational-angle-threshold',
          claim: `${thresholdTex} lies in the independently replayed exact rational interval [${rationalText(certifiedThreshold.certificate.threshold.lower)}, ${rationalText(certifiedThreshold.certificate.threshold.upper)}]`,
          verifier: 'Machin pi interval + alternating cosine remainder + independent certificate replay',
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
          'rational-angle-derived-certified-algebraic-threshold',
        ],
        querySignature: 'classify recurrence-indexed power sums above an independent quadratic rational-angle threshold',
        normalForm: answer,
        freeParameters: [
          ...baseCard.structure_blueprint.structuralUniqueness.freeParameters,
          'rational angle with certified algebraic quadratic projection',
        ],
        numericInstanceConstants: [
          ...baseCard.structure_blueprint.structuralUniqueness.numericInstanceConstants,
          Number(typed.angle.numerator),
          Number(typed.angle.denominator),
          certifiedThreshold.certificate.projection === 'sine_squared' ? 0 : 1,
          certifiedThreshold.certificate.cosineTaylorTerms,
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
