import type { Fact, Pt } from '../../proof-scene'

export type CoordinateProvenance = 'given_exact' | 'constructed_witness'

export type CandidateVerificationStatus =
  | 'certified'
  | 'rejected'
  | 'conjecture_only'
  | 'unverifiable'

export type GeometryCandidateCertificate = {
  status: CandidateVerificationStatus
  method: 'exact-rational-coordinate-identity'
  identities: string[]
  dependencies: string[]
  reason: string
}

export type GeometryCandidate = {
  id: string
  fact: Fact
  score: number
  normalizedResidual: number
  observedBy: 'semantic-spatial-inspection'
  certificate: GeometryCandidateCertificate
}

export type GeometryCandidateInspection = {
  candidates: GeometryCandidate[]
  consideredSegments: number
  consideredPoints: number
  truncated: boolean
}

type Segment = [string, string]
type Rational = { n: number; d: number }

const DEFAULT_VISUAL_TOLERANCE = 0.035
const DEFAULT_MAX_CANDIDATES = 64

function gcd(a: number, b: number): number {
  a = Math.abs(a)
  b = Math.abs(b)
  while (b) [a, b] = [b, a % b]
  return a || 1
}

function rational(n: number, d = 1): Rational | null {
  if (!Number.isSafeInteger(n) || !Number.isSafeInteger(d) || d === 0) return null
  if (d < 0) { n = -n; d = -d }
  const g = gcd(n, d)
  return { n: n / g, d: d / g }
}

function rationalFromNumber(value: number): Rational | null {
  if (!Number.isFinite(value)) return null
  const text = String(value).toLowerCase()
  const [mantissa, exponentText] = text.split('e')
  const exponent = exponentText ? Number(exponentText) : 0
  if (!Number.isInteger(exponent)) return null
  const sign = mantissa.startsWith('-') ? -1 : 1
  const unsigned = mantissa.replace(/^[+-]/, '')
  const [whole, fraction = ''] = unsigned.split('.')
  const digits = `${whole || '0'}${fraction}`.replace(/^0+(?=\d)/, '')
  const numerator = sign * Number(digits || '0')
  const scale = fraction.length - exponent
  if (!Number.isSafeInteger(numerator) || Math.abs(scale) > 12) return null
  if (scale <= 0) return rational(numerator * 10 ** -scale)
  return rational(numerator, 10 ** scale)
}

function qAdd(a: Rational, b: Rational): Rational | null {
  return rational(a.n * b.d + b.n * a.d, a.d * b.d)
}

function qSub(a: Rational, b: Rational): Rational | null {
  return rational(a.n * b.d - b.n * a.d, a.d * b.d)
}

function qMul(a: Rational, b: Rational): Rational | null {
  return rational(a.n * b.n, a.d * b.d)
}

function qSquare(a: Rational): Rational | null {
  return qMul(a, a)
}

function qRender(a: Rational): string {
  return a.d === 1 ? String(a.n) : `${a.n}/${a.d}`
}

function qZero(a: Rational | null): boolean {
  return a !== null && a.n === 0
}

function exactPoint(point: Pt): { x: Rational; y: Rational } | null {
  const x = rationalFromNumber(point.x)
  const y = rationalFromNumber(point.y)
  return x && y ? { x, y } : null
}

function exactVector(
  points: Record<string, Pt>,
  a: string,
  b: string,
): { x: Rational; y: Rational } | null {
  const p = exactPoint(points[a])
  const q = exactPoint(points[b])
  if (!p || !q) return null
  const x = qSub(q.x, p.x)
  const y = qSub(q.y, p.y)
  return x && y ? { x, y } : null
}

function qDot(u: { x: Rational; y: Rational }, v: { x: Rational; y: Rational }): Rational | null {
  const xx = qMul(u.x, v.x)
  const yy = qMul(u.y, v.y)
  return xx && yy ? qAdd(xx, yy) : null
}

function qCross(u: { x: Rational; y: Rational }, v: { x: Rational; y: Rational }): Rational | null {
  const xy = qMul(u.x, v.y)
  const yx = qMul(u.y, v.x)
  return xy && yx ? qSub(xy, yx) : null
}

function qLengthSquared(u: { x: Rational; y: Rational }): Rational | null {
  const xx = qSquare(u.x)
  const yy = qSquare(u.y)
  return xx && yy ? qAdd(xx, yy) : null
}

function segmentKey([a, b]: Segment): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

function factKey(fact: Fact): string {
  const a = fact.args
  if (fact.pred === 'perp' || fact.pred === 'para' || fact.pred === 'cong') {
    return `${fact.pred}(${[segmentKey([a[0], a[1]]), segmentKey([a[2], a[3]])].sort().join(',')})`
  }
  if (fact.pred === 'coll') return `coll(${[...a].sort().join(',')})`
  if (fact.pred === 'midp') return `midp(${a[0]};${segmentKey([a[1], a[2]])})`
  return `${fact.pred}(${a.join(',')})`
}

function segmentsOf(fact: Fact): Segment[] {
  const a = fact.args
  switch (fact.pred) {
    case 'perp':
    case 'para':
    case 'cong':
      return [[a[0], a[1]], [a[2], a[3]]]
    case 'coll':
      return [[a[0], a[1]], [a[0], a[2]], [a[1], a[2]]]
    case 'midp':
      return [[a[0], a[1]], [a[0], a[2]], [a[1], a[2]]]
    case 'eqangle':
      return [[a[0], a[1]], [a[2], a[3]], [a[4], a[5]], [a[6], a[7]]]
  }
}

function numericVector(points: Record<string, Pt>, [a, b]: Segment): Pt | null {
  const p = points[a]
  const q = points[b]
  return p && q ? { x: q.x - p.x, y: q.y - p.y } : null
}

function length(vector: Pt): number {
  return Math.hypot(vector.x, vector.y)
}

function verifyExactly(
  fact: Fact,
  points: Record<string, Pt>,
  provenance: CoordinateProvenance,
): GeometryCandidateCertificate {
  const dependencies = [...new Set(fact.args)]
  const unavailable = (reason: string): GeometryCandidateCertificate => ({
    status: 'unverifiable',
    method: 'exact-rational-coordinate-identity',
    identities: [],
    dependencies,
    reason,
  })
  if (dependencies.some(name => !points[name])) return unavailable('candidate references a point without coordinates')

  let identities: Rational[] | null = null
  const a = fact.args
  if (fact.pred === 'perp' || fact.pred === 'para' || fact.pred === 'cong') {
    const u = exactVector(points, a[0], a[1])
    const v = exactVector(points, a[2], a[3])
    if (!u || !v) return unavailable('coordinates cannot be represented as safe exact rationals')
    const lu = qLengthSquared(u)
    const lv = qLengthSquared(v)
    if (!lu || !lv || qZero(lu) || qZero(lv)) return unavailable('candidate contains a degenerate segment')
    if (fact.pred === 'perp') identities = [qDot(u, v)].filter((x): x is Rational => x !== null)
    if (fact.pred === 'para') identities = [qCross(u, v)].filter((x): x is Rational => x !== null)
    if (fact.pred === 'cong') {
      const delta = qSub(lu, lv)
      identities = delta ? [delta] : null
    }
  } else if (fact.pred === 'coll') {
    const u = exactVector(points, a[0], a[1])
    const v = exactVector(points, a[0], a[2])
    if (!u || !v) return unavailable('coordinates cannot be represented as safe exact rationals')
    const lu = qLengthSquared(u)
    const lv = qLengthSquared(v)
    if (!lu || !lv || qZero(lu) || qZero(lv)) return unavailable('candidate contains coincident points')
    const cross = qCross(u, v)
    identities = cross ? [cross] : null
  } else if (fact.pred === 'midp') {
    const m = exactPoint(points[a[0]])
    const p = exactPoint(points[a[1]])
    const q = exactPoint(points[a[2]])
    if (!m || !p || !q) return unavailable('coordinates cannot be represented as safe exact rationals')
    const two = rational(2)!
    const mx2 = qMul(m.x, two)
    const my2 = qMul(m.y, two)
    const pxq = qAdd(p.x, q.x)
    const pyq = qAdd(p.y, q.y)
    const dx = mx2 && pxq ? qSub(mx2, pxq) : null
    const dy = my2 && pyq ? qSub(my2, pyq) : null
    identities = dx && dy ? [dx, dy] : null
  } else {
    return unavailable(`exact verifier does not support ${fact.pred}`)
  }

  if (!identities || identities.length === 0) return unavailable('safe rational arithmetic overflowed')
  const rendered = identities.map(value => `${qRender(value)} = 0`)
  const valid = identities.every(qZero)
  if (!valid) {
    return {
      status: 'rejected',
      method: 'exact-rational-coordinate-identity',
      identities: rendered,
      dependencies,
      reason: 'the visual relation is approximate but its exact polynomial identity is nonzero',
    }
  }
  if (provenance !== 'given_exact') {
    return {
      status: 'conjecture_only',
      method: 'exact-rational-coordinate-identity',
      identities: rendered,
      dependencies,
      reason: 'the relation holds in one constructed witness, which is not a universal proof',
    }
  }
  return {
    status: 'certified',
    method: 'exact-rational-coordinate-identity',
    identities: rendered,
    dependencies,
    reason: 'the relation follows from exact coordinates supplied as mathematical givens',
  }
}

export function inspectSemanticGeometry(input: {
  points: Record<string, Pt>
  facts: Fact[]
  coordinateProvenance: CoordinateProvenance
  visualTolerance?: number
  maxCandidates?: number
}): GeometryCandidateInspection {
  const tolerance = input.visualTolerance ?? DEFAULT_VISUAL_TOLERANCE
  const maxCandidates = input.maxCandidates ?? DEFAULT_MAX_CANDIDATES
  const segmentMap = new Map<string, Segment>()
  for (const fact of input.facts) {
    for (const segment of segmentsOf(fact)) {
      if (segment[0] !== segment[1] && input.points[segment[0]] && input.points[segment[1]]) {
        segmentMap.set(segmentKey(segment), segment)
      }
    }
  }
  const initialPoints = [...new Set([...segmentMap.values()].flat())].sort()
  // Small semantic states can be inspected completely. Beyond eight points we
  // retain only segments named by premises or the goal, avoiding O(n^4) growth.
  if (initialPoints.length <= 8) {
    for (let i = 0; i < initialPoints.length; i++) {
      for (let j = i + 1; j < initialPoints.length; j++) {
        const segment: Segment = [initialPoints[i], initialPoints[j]]
        segmentMap.set(segmentKey(segment), segment)
      }
    }
  }
  const segments = [...segmentMap.values()]
  const pointNames = [...new Set(segments.flat())].sort()
  const raw: { fact: Fact; residual: number }[] = []

  const push = (fact: Fact, residual: number) => {
    if (Number.isFinite(residual) && residual <= tolerance) raw.push({ fact, residual })
  }

  for (let i = 0; i < segments.length; i++) {
    const u = numericVector(input.points, segments[i])
    if (!u || length(u) === 0) continue
    for (let j = i + 1; j < segments.length; j++) {
      const v = numericVector(input.points, segments[j])
      if (!v || length(v) === 0) continue
      const scale = length(u) * length(v)
      const args = [...segments[i], ...segments[j]]
      push({ pred: 'perp', args }, Math.abs(u.x * v.x + u.y * v.y) / scale)
      push({ pred: 'para', args }, Math.abs(u.x * v.y - u.y * v.x) / scale)
      push({ pred: 'cong', args }, Math.abs(length(u) - length(v)) / Math.max(length(u), length(v)))
    }
  }

  for (let i = 0; i < pointNames.length; i++) {
    for (let j = i + 1; j < pointNames.length; j++) {
      for (let k = j + 1; k < pointNames.length; k++) {
        const a = input.points[pointNames[i]]
        const b = input.points[pointNames[j]]
        const c = input.points[pointNames[k]]
        const u = { x: b.x - a.x, y: b.y - a.y }
        const v = { x: c.x - a.x, y: c.y - a.y }
        const scale = length(u) * length(v)
        if (scale > 0) push(
          { pred: 'coll', args: [pointNames[i], pointNames[j], pointNames[k]] },
          Math.abs(u.x * v.y - u.y * v.x) / scale,
        )
      }
    }
  }

  for (const [p, q] of segments) {
    const a = input.points[p]
    const b = input.points[q]
    const segmentLength = Math.hypot(b.x - a.x, b.y - a.y)
    if (segmentLength === 0) continue
    for (const middle of pointNames) {
      if (middle === p || middle === q) continue
      const m = input.points[middle]
      const residual = Math.hypot(m.x - (a.x + b.x) / 2, m.y - (a.y + b.y) / 2) / segmentLength
      push({ pred: 'midp', args: [middle, p, q] }, residual)
    }
  }

  const deduplicated = new Map<string, { fact: Fact; residual: number }>()
  for (const candidate of raw) {
    const key = factKey(candidate.fact)
    const previous = deduplicated.get(key)
    if (!previous || candidate.residual < previous.residual) deduplicated.set(key, candidate)
  }
  const ordered = [...deduplicated.values()].sort((a, b) =>
    a.residual - b.residual || factKey(a.fact).localeCompare(factKey(b.fact)),
  )
  const selected = ordered.slice(0, maxCandidates)
  return {
    candidates: selected.map(({ fact, residual }) => ({
      id: `visual.${factKey(fact)}`,
      fact,
      score: Math.max(0, 1 - residual / tolerance),
      normalizedResidual: residual,
      observedBy: 'semantic-spatial-inspection',
      certificate: verifyExactly(fact, input.points, input.coordinateProvenance),
    })),
    consideredSegments: segments.length,
    consideredPoints: pointNames.length,
    truncated: ordered.length > selected.length,
  }
}
