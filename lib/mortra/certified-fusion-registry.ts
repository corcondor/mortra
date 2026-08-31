import {
  synthesizeCertifiedPolynomialFusions,
  type CertifiedFusionCard,
  type CertifiedFusionParent,
} from './certified-fusion'
import { synthesizeCertifiedCircleRadicalAxisFusion } from './certified-circle-fusion'
import { synthesizeCertifiedMobiusPolynomialFusion } from './certified-mobius-polynomial-fusion'
import { synthesizeCertifiedIndexedPowerSumFusion } from './certified-indexed-power-fusion'
import {
  synthesizeCertifiedPellIndexedPowerSumFusion,
  synthesizeCertifiedPellRecurrenceFusion,
} from './certified-pell-recurrence-fusion'
import { synthesizeCertifiedAnswerRecurrenceFusion } from './certified-answer-recurrence-fusion'

export const CERTIFIED_FUSION_CAPABILITIES = [
  {
    id: 'polynomial-root-configuration',
    labelJa: '一変数多項式の根配置どうし',
    labelEn: 'univariate polynomial root configurations',
  },
  {
    id: 'circle-quadratic-form',
    labelJa: '座標平面上の円どうし',
    labelEn: 'affine circle quadratic forms',
  },
  {
    id: 'mobius-polynomial-fixed-point-transport',
    labelJa: '多項式の根配置と一次分数変換',
    labelEn: 'polynomial root configurations and Mobius transports',
  },
  {
    id: 'recurrence-indexed-power-sum',
    labelJa: '二階漸化式と三角冪和',
    labelEn: 'second-order recurrences and trigonometric power sums',
  },
  {
    id: 'pell-recurrence-state-product',
    labelJa: 'Pell軌道と二階漸化式',
    labelEn: 'Pell orbits and second-order recurrences',
  },
  {
    id: 'pell-indexed-power-sum',
    labelJa: 'Pell軌道と三角冪和',
    labelEn: 'Pell orbits and trigonometric power sums',
  },
  {
    id: 'verified-answer-companion-recurrence',
    labelJa: '検証済み厳密解どうしの二階漸化式合成',
    labelEn: 'companion recurrence from two certified exact answers',
  },
] as const

type CertifiedFusionEngine = (
  parents: CertifiedFusionParent[],
  requested: number,
) => CertifiedFusionCard[]

const ENGINES: readonly CertifiedFusionEngine[] = [
  synthesizeCertifiedPolynomialFusions,
  (parents, requested) => synthesizeCertifiedMobiusPolynomialFusion(parents).slice(0, requested),
  (parents, requested) => synthesizeCertifiedCircleRadicalAxisFusion(parents).slice(0, requested),
  (parents, requested) => synthesizeCertifiedIndexedPowerSumFusion(parents).slice(0, requested),
  (parents, requested) => synthesizeCertifiedPellRecurrenceFusion(parents).slice(0, requested),
  (parents, requested) => synthesizeCertifiedPellIndexedPowerSumFusion(parents).slice(0, requested),
  synthesizeCertifiedAnswerRecurrenceFusion,
]

export function synthesizeCertifiedFusions(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const cards: CertifiedFusionCard[] = []
  const seen = new Set<string>()
  for (const engine of ENGINES) {
    for (const card of engine(parents, Math.max(0, requested - cards.length))) {
      if (seen.has(card.structure_blueprint.id)) continue
      seen.add(card.structure_blueprint.id)
      cards.push(card)
      if (cards.length >= requested) return cards
    }
  }
  return cards
}
