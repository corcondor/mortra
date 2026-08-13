/**
 * Bounded Euclidean construction synthesis.
 *
 * A goal does not select a memorised construction. Each predicate is lowered
 * to its geometric locus, and the unknown point is obtained by intersecting
 * compatible loci. The same operation log is consumed by the verifier, WebGL
 * renderer, and robot-path adapter.
 */

export type Vec2 = { x: number; y: number }

export type PointObject = {
  kind: 'point'
  id: string
  label: string
  x: number
  y: number
}

export type LineObject = {
  kind: 'line'
  id: string
  label: string
  /** Normalised equation ax + by + c = 0. */
  a: number
  b: number
  c: number
}

export type CircleObject = {
  kind: 'circle'
  id: string
  label: string
  cx: number
  cy: number
  radius: number
}

export type ConstructionObject = PointObject | LineObject | CircleObject

export type ConstructionOperation =
  | 'given-point'
  | 'line-through'
  | 'circle-center-through'
  | 'intersect-line-line'
  | 'intersect-line-circle'
  | 'intersect-circle-circle'
  | 'select-witness'

export type ConstructionStep = {
  id: string
  operation: ConstructionOperation
  label: string
  reason: string
  inputs: string[]
  produced: ConstructionObject[]
  depth: number
  residual: number
  verification: 'replayed-numeric'
}

export type PointConstraint =
  | { kind: 'equidistant'; a: string; b: string }
  | { kind: 'on-line'; a: string; b: string }
  | { kind: 'on-circle'; center: string; through: string }

export type ConstructionGoal = {
  id: string
  label: string
  unknown: string
  givens: Record<string, Vec2>
  constraints: PointConstraint[]
}

export type ConstructionPlan = {
  id: string
  label: string
  unknown: string
  constraints: PointConstraint[]
  steps: ConstructionStep[]
  objects: Record<string, ConstructionObject>
  witnessIds: string[]
  status: 'verified' | 'unsatisfied'
  verification: 'independent-numeric-replay'
}

export type PlanVerification = {
  passed: boolean
  maxResidual: number
  steps: Array<{ id: string; passed: boolean; residual: number }>
}

type Locus = { kind: 'line' | 'circle'; id: string }

const EPS = 1e-7

const sq = (value: number) => value * value
const distance = (a: Vec2, b: Vec2) => Math.hypot(a.x - b.x, a.y - b.y)
const pointOf = (point: PointObject): Vec2 => ({ x: point.x, y: point.y })

function canonicalLine(a: Vec2, b: Vec2) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const norm = Math.hypot(dx, dy)
  if (norm < EPS) return null
  let la = -dy / norm
  let lb = dx / norm
  let lc = -(la * a.x + lb * a.y)
  if (la < -EPS || (Math.abs(la) <= EPS && lb < 0)) {
    la = -la
    lb = -lb
    lc = -lc
  }
  return { a: la, b: lb, c: lc }
}

function lineLine(left: LineObject, right: LineObject): Vec2[] {
  const determinant = left.a * right.b - right.a * left.b
  if (Math.abs(determinant) < EPS) return []
  return [{
    x: (left.b * right.c - right.b * left.c) / determinant,
    y: (left.c * right.a - right.c * left.a) / determinant,
  }]
}

function lineCircle(line: LineObject, circle: CircleObject): Vec2[] {
  const signed = line.a * circle.cx + line.b * circle.cy + line.c
  const foot = {
    x: circle.cx - signed * line.a,
    y: circle.cy - signed * line.b,
  }
  const heightSquared = sq(circle.radius) - sq(signed)
  if (heightSquared < -EPS) return []
  if (Math.abs(heightSquared) <= EPS) return [foot]
  const offset = Math.sqrt(Math.max(0, heightSquared))
  return [
    { x: foot.x - line.b * offset, y: foot.y + line.a * offset },
    { x: foot.x + line.b * offset, y: foot.y - line.a * offset },
  ]
}

function circleCircle(left: CircleObject, right: CircleObject): Vec2[] {
  const dx = right.cx - left.cx
  const dy = right.cy - left.cy
  const d = Math.hypot(dx, dy)
  if (d < EPS || d > left.radius + right.radius + EPS
      || d < Math.abs(left.radius - right.radius) - EPS) return []
  const along = (sq(left.radius) - sq(right.radius) + sq(d)) / (2 * d)
  const heightSquared = sq(left.radius) - sq(along)
  if (heightSquared < -EPS) return []
  const base = {
    x: left.cx + (along * dx) / d,
    y: left.cy + (along * dy) / d,
  }
  if (Math.abs(heightSquared) <= EPS) return [base]
  const height = Math.sqrt(Math.max(0, heightSquared))
  return [
    { x: base.x - (height * dy) / d, y: base.y + (height * dx) / d },
    { x: base.x + (height * dy) / d, y: base.y - (height * dx) / d },
  ]
}

function objectDifference(expected: ConstructionObject, actual: ConstructionObject) {
  if (expected.kind !== actual.kind) return Number.POSITIVE_INFINITY
  if (expected.kind === 'point' && actual.kind === 'point') {
    return distance(expected, actual)
  }
  if (expected.kind === 'line' && actual.kind === 'line') {
    return Math.max(
      Math.abs(expected.a - actual.a),
      Math.abs(expected.b - actual.b),
      Math.abs(expected.c - actual.c),
    )
  }
  if (expected.kind === 'circle' && actual.kind === 'circle') {
    return Math.max(
      Math.abs(expected.cx - actual.cx),
      Math.abs(expected.cy - actual.cy),
      Math.abs(expected.radius - actual.radius),
    )
  }
  return Number.POSITIVE_INFINITY
}

function constraintResidual(
  constraint: PointConstraint,
  candidate: PointObject,
  objects: Record<string, ConstructionObject>,
) {
  const getPoint = (id: string) => {
    const value = objects[id]
    return value?.kind === 'point' ? value : null
  }
  if (constraint.kind === 'equidistant') {
    const a = getPoint(constraint.a)
    const b = getPoint(constraint.b)
    if (!a || !b) return Number.POSITIVE_INFINITY
    return Math.abs(sq(distance(candidate, a)) - sq(distance(candidate, b)))
  }
  if (constraint.kind === 'on-line') {
    const a = getPoint(constraint.a)
    const b = getPoint(constraint.b)
    if (!a || !b) return Number.POSITIVE_INFINITY
    const line = canonicalLine(a, b)
    return line ? Math.abs(line.a * candidate.x + line.b * candidate.y + line.c) : Number.POSITIVE_INFINITY
  }
  const center = getPoint(constraint.center)
  const through = getPoint(constraint.through)
  if (!center || !through) return Number.POSITIVE_INFINITY
  return Math.abs(sq(distance(candidate, center)) - sq(distance(center, through)))
}

class Builder {
  readonly steps: ConstructionStep[] = []
  readonly objects: Record<string, ConstructionObject> = {}
  private serial = 0

  constructor(readonly goal: ConstructionGoal) {
    for (const [id, point] of Object.entries(goal.givens)) {
      const object: PointObject = { kind: 'point', id, label: id.toUpperCase(), ...point }
      this.objects[id] = object
      this.addStep('given-point', `${object.label} を与える`, '問題の初期条件', [], [object], 0, 0)
    }
  }

  private next(prefix: string) {
    this.serial += 1
    return `${prefix}_${this.serial}`
  }

  private addStep(
    operation: ConstructionOperation,
    label: string,
    reason: string,
    inputs: string[],
    produced: ConstructionObject[],
    depth: number,
    residual: number,
  ) {
    for (const object of produced) this.objects[object.id] = object
    this.steps.push({
      id: `step_${this.steps.length + 1}`,
      operation,
      label,
      reason,
      inputs,
      produced,
      depth,
      residual,
      verification: 'replayed-numeric',
    })
  }

  point(id: string) {
    const value = this.objects[id]
    return value?.kind === 'point' ? value : null
  }

  line(firstId: string, secondId: string, label?: string) {
    const first = this.point(firstId)
    const second = this.point(secondId)
    if (!first || !second) return null
    const equation = canonicalLine(first, second)
    if (!equation) return null
    const existing = Object.values(this.objects).find(object =>
      object.kind === 'line'
      && Math.max(
        Math.abs(object.a - equation.a),
        Math.abs(object.b - equation.b),
        Math.abs(object.c - equation.c),
      ) < EPS)
    if (existing?.kind === 'line') return existing.id
    const id = this.next('line')
    const object: LineObject = {
      kind: 'line', id, label: label ?? `直線 ${first.label}${second.label}`, ...equation,
    }
    const residual = Math.max(
      Math.abs(equation.a * first.x + equation.b * first.y + equation.c),
      Math.abs(equation.a * second.x + equation.b * second.y + equation.c),
    )
    this.addStep(
      'line-through', object.label, '2点を通る直線は一意に定まる',
      [firstId, secondId], [object], this.steps.length, residual,
    )
    return id
  }

  circle(centerId: string, throughId: string, label?: string) {
    const center = this.point(centerId)
    const through = this.point(throughId)
    if (!center || !through) return null
    const radius = distance(center, through)
    if (radius < EPS) return null
    const existing = Object.values(this.objects).find(object =>
      object.kind === 'circle'
      && distance({ x: object.cx, y: object.cy }, center) < EPS
      && Math.abs(object.radius - radius) < EPS)
    if (existing?.kind === 'circle') return existing.id
    const id = this.next('circle')
    const object: CircleObject = {
      kind: 'circle', id, label: label ?? `${center.label} 中心・${through.label} 通過の円`,
      cx: center.x, cy: center.y, radius,
    }
    this.addStep(
      'circle-center-through', object.label, '中心と円周上の1点が円を定める',
      [centerId, throughId], [object], this.steps.length,
      Math.abs(distance(center, through) - radius),
    )
    return id
  }

  intersect(leftId: string, rightId: string, label = '交点') {
    const left = this.objects[leftId]
    const right = this.objects[rightId]
    if (!left || !right || left.kind === 'point' || right.kind === 'point') return []
    let operation: ConstructionOperation
    let values: Vec2[]
    if (left.kind === 'line' && right.kind === 'line') {
      operation = 'intersect-line-line'
      values = lineLine(left, right)
    } else if (left.kind === 'circle' && right.kind === 'circle') {
      operation = 'intersect-circle-circle'
      values = circleCircle(left, right)
    } else {
      operation = 'intersect-line-circle'
      const line = left.kind === 'line' ? left : right as LineObject
      const circle = left.kind === 'circle' ? left : right as CircleObject
      values = lineCircle(line, circle)
    }
    const produced = values.map((value, index): PointObject => ({
      kind: 'point', id: this.next('point'),
      label: values.length > 1 ? `${label}${index + 1}` : label,
      ...value,
    }))
    const residual = produced.reduce((maximum, point) => {
      const forObject = (object: LineObject | CircleObject) => object.kind === 'line'
        ? Math.abs(object.a * point.x + object.b * point.y + object.c)
        : Math.abs(sq(distance(point, { x: object.cx, y: object.cy })) - sq(object.radius))
      return Math.max(maximum, forObject(left), forObject(right))
    }, 0)
    this.addStep(
      operation, label, '2つの軌跡を同時に満たす点を作る',
      [leftId, rightId], produced, this.steps.length, residual,
    )
    return produced.map(point => point.id)
  }

  locus(constraint: PointConstraint, index: number): Locus | null {
    if (constraint.kind === 'on-line') {
      const id = this.line(constraint.a, constraint.b, `制約 ${index + 1}: 直線上`)
      return id ? { kind: 'line', id } : null
    }
    if (constraint.kind === 'on-circle') {
      const id = this.circle(
        constraint.center,
        constraint.through,
        `制約 ${index + 1}: 固定距離の円`,
      )
      return id ? { kind: 'circle', id } : null
    }

    const leftCircle = this.circle(
      constraint.a, constraint.b,
      `等距離軌跡 ${index + 1}: 第1コンパス円`,
    )
    const rightCircle = this.circle(
      constraint.b, constraint.a,
      `等距離軌跡 ${index + 1}: 第2コンパス円`,
    )
    if (!leftCircle || !rightCircle) return null
    const crossing = this.intersect(leftCircle, rightCircle, `等距離補助点 ${index + 1}-`)
    if (crossing.length < 2) return null
    const bisector = this.line(crossing[0], crossing[1], `制約 ${index + 1}: 垂直二等分線`)
    return bisector ? { kind: 'line', id: bisector } : null
  }

  select(witnessIds: string[], constraints: PointConstraint[]) {
    const residual = witnessIds.reduce((maximum, id) => {
      const point = this.point(id)
      if (!point) return Number.POSITIVE_INFINITY
      return Math.max(
        maximum,
        ...constraints.map(constraint => constraintResidual(constraint, point, this.objects)),
      )
    }, 0)
    this.addStep(
      'select-witness', `${this.goal.unknown} を確定`,
      'すべての型付き制約を同時に満たす候補だけを残す',
      witnessIds, [], this.steps.length, residual,
    )
  }
}

function satisfyingWitnesses(
  ids: string[],
  constraints: PointConstraint[],
  builder: Builder,
) {
  return ids.filter(id => {
    const point = builder.point(id)
    if (!point) return false
    return constraints.every(constraint =>
      constraintResidual(constraint, point, builder.objects) <= EPS)
  })
}

function planFrom(builder: Builder, witnessIds: string[]): ConstructionPlan {
  const verificationDraft: ConstructionPlan = {
    id: builder.goal.id,
    label: builder.goal.label,
    unknown: builder.goal.unknown,
    constraints: builder.goal.constraints,
    steps: builder.steps,
    objects: builder.objects,
    witnessIds,
    status: witnessIds.length ? 'verified' : 'unsatisfied',
    verification: 'independent-numeric-replay',
  }
  const verified = verifyConstructionPlan(verificationDraft)
  return {
    ...verificationDraft,
    status: witnessIds.length && verified.passed ? 'verified' : 'unsatisfied',
  }
}

export function solveConstructionGoal(goal: ConstructionGoal): ConstructionPlan {
  const builder = new Builder(goal)
  const loci = goal.constraints
    .map((constraint, index) => builder.locus(constraint, index))
    .filter((value): value is Locus => value !== null)
  const candidates: string[] = []
  for (let left = 0; left < loci.length; left += 1) {
    for (let right = left + 1; right < loci.length; right += 1) {
      candidates.push(...builder.intersect(loci[left].id, loci[right].id, `${goal.unknown} 候補`))
    }
  }
  const witnesses = satisfyingWitnesses(candidates, goal.constraints, builder)
  if (witnesses.length) builder.select(witnesses, goal.constraints)
  return planFrom(builder, witnesses)
}

/** A dense, visually legible construction compiled from three equidistance constraints. */
export function buildCircumcenterConstruction(): ConstructionPlan {
  const goal: ConstructionGoal = {
    id: 'triangle-circumcenter-locus-intersection',
    label: '3本の等距離軌跡から外心と外接円を構成',
    unknown: 'O',
    givens: {
      a: { x: -3.8, y: -1.8 },
      b: { x: 3.7, y: -1.35 },
      c: { x: 0.45, y: 4.15 },
    },
    constraints: [
      { kind: 'equidistant', a: 'a', b: 'b' },
      { kind: 'equidistant', a: 'b', b: 'c' },
      { kind: 'equidistant', a: 'c', b: 'a' },
    ],
  }
  const builder = new Builder(goal)
  builder.line('a', 'b', '三角形の辺 AB')
  builder.line('b', 'c', '三角形の辺 BC')
  builder.line('c', 'a', '三角形の辺 CA')
  const loci = goal.constraints
    .map((constraint, index) => builder.locus(constraint, index))
    .filter((value): value is Locus => value !== null)
  const candidates = loci.length >= 2
    ? builder.intersect(loci[0].id, loci[1].id, '外心 O')
    : []
  const witnesses = satisfyingWitnesses(candidates, goal.constraints, builder)
  if (witnesses.length) {
    const point = builder.point(witnesses[0])
    if (point) point.label = 'O'
    builder.circle(witnesses[0], 'a', 'O を中心とする外接円')
    builder.select([witnesses[0]], goal.constraints)
  }
  return planFrom(builder, witnesses.slice(0, 1))
}

/**
 * Build the two-ring hexagonal orbit (the 19-circle flower) from one centre
 * and one radius point. Every new centre is an intersection of already
 * constructed loci; no final circle centre is placed by a coordinate formula.
 */
export function buildHexagonalCircleOrbitConstruction(radius = 2.15): ConstructionPlan {
  const goal: ConstructionGoal = {
    id: 'hexagonal-circle-orbit-two-rings',
    label: '交点の反復から19円の六方軌道を構成',
    unknown: 'hexagonal-orbit',
    givens: {
      o: { x: 0, y: 0 },
      a: { x: radius, y: 0 },
    },
    constraints: [],
  }
  const builder = new Builder(goal)
  const central = builder.circle('o', 'a', '基準円 C₀')
  if (!central) return planFrom(builder, [])

  const firstRing = ['a']
  let previous = 'a'
  let current = 'a'
  for (let index = 0; index < 5; index += 1) {
    const currentCircle = builder.circle(current, 'o', `第1環コンパス円 ${index + 1}`)
    if (!currentCircle) break
    const candidates = builder.intersect(central, currentCircle, `第1環交点 ${index + 1}-`)
    const previousPoint = builder.point(previous)
    const currentPoint = builder.point(current)
    const candidatePoints = candidates
      .map(id => ({ id, point: builder.point(id) }))
      .filter((value): value is { id: string; point: PointObject } => value.point !== null)
    let next: string | undefined
    if (index === 0 && currentPoint) {
      next = candidatePoints
        .sort((left, right) => {
          const leftCross = currentPoint.x * left.point.y - currentPoint.y * left.point.x
          const rightCross = currentPoint.x * right.point.y - currentPoint.y * right.point.x
          return rightCross - leftCross
        })[0]?.id
    } else if (previousPoint) {
      next = candidatePoints.find(value => distance(value.point, previousPoint) > EPS * 10)?.id
    }
    if (!next) break
    previous = current
    current = next
    firstRing.push(next)
  }

  for (const [index, center] of firstRing.entries()) {
    builder.circle(center, 'o', `第1環 ${index + 1}/6`)
  }

  const secondRing: string[] = []
  for (const [index, center] of firstRing.entries()) {
    const radial = builder.line('o', center, `第2環への半径線 ${index + 1}`)
    const compass = builder.circle(center, 'o', `第2環軸コンパス円 ${index + 1}`)
    if (!radial || !compass) continue
    const candidates = builder.intersect(radial, compass, `第2環軸交点 ${index + 1}-`)
    const outer = candidates
      .map(id => ({ id, point: builder.point(id) }))
      .filter((value): value is { id: string; point: PointObject } => value.point !== null)
      .sort((left, right) => distance(right.point, { x: 0, y: 0 }) - distance(left.point, { x: 0, y: 0 }))[0]
    if (!outer) continue
    secondRing.push(outer.id)
    builder.circle(outer.id, center, `第2環 軸 ${index + 1}/6`)
  }

  for (let index = 0; index < firstRing.length; index += 1) {
    const leftCenter = firstRing[index]
    const rightCenter = firstRing[(index + 1) % firstRing.length]
    const leftCircle = builder.circle(leftCenter, 'o')
    const rightCircle = builder.circle(rightCenter, 'o')
    if (!leftCircle || !rightCircle) continue
    const candidates = builder.intersect(leftCircle, rightCircle, `第2環斜交点 ${index + 1}-`)
    const outer = candidates
      .map(id => ({ id, point: builder.point(id) }))
      .filter((value): value is { id: string; point: PointObject } => value.point !== null)
      .sort((left, right) => distance(right.point, { x: 0, y: 0 }) - distance(left.point, { x: 0, y: 0 }))[0]
    if (!outer) continue
    secondRing.push(outer.id)
    builder.circle(outer.id, leftCenter, `第2環 斜 ${index + 1}/6`)
  }

  const witnesses = [...firstRing, ...secondRing]
  if (witnesses.length === 18) builder.select(witnesses, [])
  return planFrom(builder, witnesses.length === 18 ? witnesses : [])
}

export function verifyConstructionPlan(plan: ConstructionPlan): PlanVerification {
  const replay: Record<string, ConstructionObject> = {}
  const results: PlanVerification['steps'] = []

  const push = (step: ConstructionStep, expected: ConstructionObject[]) => {
    const residual = expected.length === step.produced.length
      ? expected.reduce(
          (maximum, object, index) => Math.max(maximum, objectDifference(object, step.produced[index])),
          0,
        )
      : Number.POSITIVE_INFINITY
    const passed = residual <= EPS && step.residual <= EPS
    if (passed) for (const object of step.produced) replay[object.id] = object
    results.push({ id: step.id, passed, residual: Math.max(residual, step.residual) })
  }

  for (const step of plan.steps) {
    if (step.operation === 'given-point') {
      push(step, step.produced)
      continue
    }
    if (step.operation === 'select-witness') {
      const residual = step.inputs.reduce((maximum, id) => {
        const point = replay[id]
        if (point?.kind !== 'point') return Number.POSITIVE_INFINITY
        return Math.max(
          maximum,
          ...plan.constraints.map(constraint => constraintResidual(constraint, point, replay)),
        )
      }, 0)
      results.push({ id: step.id, passed: residual <= EPS, residual })
      continue
    }
    if (step.operation === 'line-through') {
      const first = replay[step.inputs[0]]
      const second = replay[step.inputs[1]]
      const line = first?.kind === 'point' && second?.kind === 'point'
        ? canonicalLine(first, second) : null
      const source = step.produced[0]
      push(step, line && source?.kind === 'line'
        ? [{ ...source, ...line }]
        : [])
      continue
    }
    if (step.operation === 'circle-center-through') {
      const center = replay[step.inputs[0]]
      const through = replay[step.inputs[1]]
      const source = step.produced[0]
      push(step, center?.kind === 'point' && through?.kind === 'point' && source?.kind === 'circle'
        ? [{
            ...source,
            cx: center.x,
            cy: center.y,
            radius: distance(center, through),
          }]
        : [])
      continue
    }

    const left = replay[step.inputs[0]]
    const right = replay[step.inputs[1]]
    if (!left || !right || left.kind === 'point' || right.kind === 'point') {
      push(step, [])
      continue
    }
    let values: Vec2[] = []
    if (left.kind === 'line' && right.kind === 'line') values = lineLine(left, right)
    else if (left.kind === 'circle' && right.kind === 'circle') values = circleCircle(left, right)
    else values = lineCircle(
      left.kind === 'line' ? left : right as LineObject,
      left.kind === 'circle' ? left : right as CircleObject,
    )
    const expected = values.map((value, index) => {
      const source = step.produced[index]
      return source?.kind === 'point' ? { ...source, ...value } : null
    }).filter((value): value is PointObject => value !== null)
    push(step, expected)
  }

  const maxResidual = results.reduce((maximum, result) => Math.max(maximum, result.residual), 0)
  return {
    passed: results.length > 0 && results.every(result => result.passed),
    maxResidual,
    steps: results,
  }
}

/** Convert a semantic plan to physical pen strokes without inventing geometry. */
export type ConstructionDrawingPath = {
  stepId: string
  objectId: string
  kind: 'point' | 'line' | 'circle'
  label: string
  points: Vec2[]
}

export function constructionDrawingPaths(plan: ConstructionPlan, span = 7.5): ConstructionDrawingPath[] {
  const paths: ConstructionDrawingPath[] = []
  for (const step of plan.steps) {
    for (const object of step.produced) {
      if (object.kind === 'point') {
        paths.push({
      stepId: step.id,
      objectId: object.id,
      kind: 'point',
      label: object.label,
      points: [{ x: object.x, y: object.y }],
        })
        continue
      }
      if (object.kind === 'circle') {
        const points = Array.from({ length: 145 }, (_, index) => {
          const angle = (index / 144) * Math.PI * 2
          return {
            x: object.cx + object.radius * Math.cos(angle),
            y: object.cy + object.radius * Math.sin(angle),
          }
        })
        paths.push({ stepId: step.id, objectId: object.id, kind: 'circle', label: object.label, points })
        continue
      }
      const anchor = { x: -object.a * object.c, y: -object.b * object.c }
      const direction = { x: -object.b, y: object.a }
      paths.push({
        stepId: step.id,
        objectId: object.id,
        kind: 'line',
        label: object.label,
        points: [
          { x: anchor.x - direction.x * span, y: anchor.y - direction.y * span },
          { x: anchor.x + direction.x * span, y: anchor.y + direction.y * span },
        ],
      })
    }
  }
  return paths
}
