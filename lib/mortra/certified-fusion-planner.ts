import {
  parseMonicIntegerPolynomial,
  synthesizeCertifiedPolynomialFusions,
  type CertifiedFusionCard,
  type CertifiedFusionParent,
} from './certified-fusion'
import {
  parseAffineCircleParent,
  synthesizeCertifiedCircleRadicalAxisFusion,
} from './certified-circle-fusion'
import {
  parseMobiusRootTransport,
  synthesizeCertifiedMobiusPolynomialFusion,
} from './certified-mobius-polynomial-fusion'
import {
  parsePositiveSecondOrderRecurrence,
  parseTrigonometricPowerSum,
  synthesizeCertifiedIndexedPowerSumFusion,
} from './certified-indexed-power-fusion'
import {
  parsePellOrbit,
  synthesizeCertifiedPellIndexedPowerSumFusion,
  synthesizeCertifiedPellRecurrenceFusion,
} from './certified-pell-recurrence-fusion'
import {
  parseCertifiedExactScalar,
  synthesizeCertifiedAnswerRecurrenceFusion,
} from './certified-answer-recurrence-fusion'
import {
  parseIntegerSecondOrderRecurrence,
  parseRationalAngles,
  synthesizeCertifiedFiniteStateTrigFusion,
} from './certified-finite-state-trig-fusion'

export type CertifiedFusionEndpointKind =
  | 'polynomial.root_configuration'
  | 'transform.mobius'
  | 'geometry.affine_circle'
  | 'sequence.positive_second_order'
  | 'sequence.integer_second_order'
  | 'trigonometry.power_sum'
  | 'angle.rational_phase'
  | 'number_theory.pell_orbit'
  | 'scalar.certified_exact'

export type CertifiedFusionEndpoint = {
  parentId: string
  kind: CertifiedFusionEndpointKind
  evidence: string
}

export type CertifiedFusionChartAttempt = {
  chartId: string
  parentIds: [string, string]
  inputKinds: [CertifiedFusionEndpointKind, CertifiedFusionEndpointKind]
  produced: number
}

export type CertifiedFusionPlan = {
  cards: CertifiedFusionCard[]
  endpoints: CertifiedFusionEndpoint[]
  attempts: CertifiedFusionChartAttempt[]
}

type FusionEngine = (
  parents: CertifiedFusionParent[],
  requested: number,
) => CertifiedFusionCard[]

type FusionChart = {
  id: string
  inputKinds: readonly [CertifiedFusionEndpointKind, CertifiedFusionEndpointKind]
  engine: FusionEngine
}

function endpoint(
  parentId: string,
  kind: CertifiedFusionEndpointKind,
  evidence: string,
): CertifiedFusionEndpoint {
  return { parentId, kind, evidence }
}

/**
 * Extract every reusable mathematical interface exposed by one parent.
 * Charts consume these interfaces instead of problem identifiers or corpus positions.
 */
export function elaborateCertifiedFusionParent(
  parent: CertifiedFusionParent,
): CertifiedFusionEndpoint[] {
  const endpoints: CertifiedFusionEndpoint[] = []
  const polynomial = parseMonicIntegerPolynomial(parent)
  if (polynomial) endpoints.push(endpoint(parent.id, 'polynomial.root_configuration', polynomial.normalizedTex))
  const mobius = parseMobiusRootTransport(parent)
  if (mobius) endpoints.push(endpoint(parent.id, 'transform.mobius', mobius.source))
  const circle = parseAffineCircleParent(parent)
  if (circle) endpoints.push(endpoint(parent.id, 'geometry.affine_circle', parent.statement))
  const positiveRecurrence = parsePositiveSecondOrderRecurrence(parent)
  if (positiveRecurrence) endpoints.push(endpoint(parent.id, 'sequence.positive_second_order', parent.statement))
  const integerRecurrence = parseIntegerSecondOrderRecurrence(parent)
  if (integerRecurrence) endpoints.push(endpoint(parent.id, 'sequence.integer_second_order', integerRecurrence.evidence))
  const powerSum = parseTrigonometricPowerSum(parent)
  if (powerSum) endpoints.push(endpoint(parent.id, 'trigonometry.power_sum', parent.statement))
  for (const angle of parseRationalAngles(parent)) {
    endpoints.push(endpoint(parent.id, 'angle.rational_phase', angle.evidence))
  }
  const pell = parsePellOrbit(parent)
  if (pell) endpoints.push(endpoint(parent.id, 'number_theory.pell_orbit', parent.statement))
  const scalar = parseCertifiedExactScalar(parent)
  if (scalar) endpoints.push(endpoint(parent.id, 'scalar.certified_exact', scalar.tex))

  const seen = new Set<string>()
  return endpoints.filter(item => {
    const key = `${item.kind}\u0000${item.evidence}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const CHARTS: readonly FusionChart[] = [
  {
    id: 'polynomial-root-configuration',
    inputKinds: ['polynomial.root_configuration', 'polynomial.root_configuration'],
    engine: synthesizeCertifiedPolynomialFusions,
  },
  {
    id: 'mobius-polynomial-fixed-point-transport',
    inputKinds: ['polynomial.root_configuration', 'transform.mobius'],
    engine: (parents, requested) => synthesizeCertifiedMobiusPolynomialFusion(parents).slice(0, requested),
  },
  {
    id: 'circle-quadratic-form',
    inputKinds: ['geometry.affine_circle', 'geometry.affine_circle'],
    engine: (parents, requested) => synthesizeCertifiedCircleRadicalAxisFusion(parents).slice(0, requested),
  },
  {
    id: 'recurrence-indexed-power-sum',
    inputKinds: ['sequence.positive_second_order', 'trigonometry.power_sum'],
    engine: (parents, requested) => synthesizeCertifiedIndexedPowerSumFusion(parents).slice(0, requested),
  },
  {
    id: 'finite-state-rational-angle-orbit',
    inputKinds: ['sequence.integer_second_order', 'angle.rational_phase'],
    engine: synthesizeCertifiedFiniteStateTrigFusion,
  },
  {
    id: 'pell-recurrence-state-product',
    inputKinds: ['number_theory.pell_orbit', 'sequence.positive_second_order'],
    engine: (parents, requested) => synthesizeCertifiedPellRecurrenceFusion(parents).slice(0, requested),
  },
  {
    id: 'pell-indexed-power-sum',
    inputKinds: ['number_theory.pell_orbit', 'trigonometry.power_sum'],
    engine: (parents, requested) => synthesizeCertifiedPellIndexedPowerSumFusion(parents).slice(0, requested),
  },
  {
    id: 'verified-answer-companion-recurrence',
    inputKinds: ['scalar.certified_exact', 'scalar.certified_exact'],
    engine: synthesizeCertifiedAnswerRecurrenceFusion,
  },
]

function matchingParentPairs(
  chart: FusionChart,
  endpoints: CertifiedFusionEndpoint[],
): Array<[string, string]> {
  const [leftKind, rightKind] = chart.inputKinds
  const left = [...new Set(endpoints.filter(item => item.kind === leftKind).map(item => item.parentId))]
  const right = [...new Set(endpoints.filter(item => item.kind === rightKind).map(item => item.parentId))]
  const pairs: Array<[string, string]> = []
  const seen = new Set<string>()
  for (const leftId of left) {
    for (const rightId of right) {
      if (leftId === rightId) continue
      const key = leftKind === rightKind
        ? [leftId, rightId].sort().join('\u0000')
        : `${leftId}\u0000${rightId}`
      if (seen.has(key)) continue
      seen.add(key)
      pairs.push([leftId, rightId])
    }
  }
  return pairs
}

export function planCertifiedFusions(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionPlan {
  const limit = Math.max(0, requested)
  const parentById = new Map(parents.map(parent => [parent.id, parent]))
  const endpoints = parents.flatMap(elaborateCertifiedFusionParent)
  const attempts: CertifiedFusionChartAttempt[] = []
  const cards: CertifiedFusionCard[] = []
  const seenCards = new Set<string>()

  if (limit === 0 || parentById.size < 2) return { cards, endpoints, attempts }

  for (const chart of CHARTS) {
    for (const [leftId, rightId] of matchingParentPairs(chart, endpoints)) {
      const left = parentById.get(leftId)
      const right = parentById.get(rightId)
      if (!left || !right) continue
      const remaining = limit - cards.length
      if (remaining <= 0) return { cards, endpoints, attempts }
      const generated = chart.engine([left, right], remaining)
      attempts.push({
        chartId: chart.id,
        parentIds: [leftId, rightId],
        inputKinds: [...chart.inputKinds],
        produced: generated.length,
      })
      for (const card of generated) {
        if (seenCards.has(card.structure_blueprint.id)) continue
        seenCards.add(card.structure_blueprint.id)
        cards.push(card)
        if (cards.length >= limit) return { cards, endpoints, attempts }
      }
    }
  }
  return { cards, endpoints, attempts }
}
