import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'
import { planCertifiedFusions } from './certified-fusion-planner'
import { attachCertifiedGenerationAudit } from './certified-problem-generation-audit'

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
    id: 'three-parent-recurrence-power-angle',
    labelJa: '二階漸化式・三角冪和・有理角の三親合成',
    labelEn: 'three-parent composition of recurrence, trigonometric power sum, and rational angle',
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
  {
    id: 'finite-state-rational-angle-orbit',
    labelJa: '整数漸化式と有理角の有限状態合成',
    labelEn: 'finite-state composition of integer recurrences and rational angles',
  },
] as const

export function synthesizeCertifiedFusions(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  const requestedParentIds = [...new Set(parents.map(parent => parent.id))].sort()
  return planCertifiedFusions(parents, requested).cards
    .filter(card => {
      const cardParentIds = [...new Set(card.parent_ids)].sort()
      return cardParentIds.length === requestedParentIds.length
        && cardParentIds.every((parentId, index) => parentId === requestedParentIds[index])
    })
    .map(card => attachCertifiedGenerationAudit(card, parents))
    .filter(card => card.generation_audit?.passed)
}
