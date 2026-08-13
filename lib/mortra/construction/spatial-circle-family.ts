/**
 * A 3D surface represented by many certified planar constructions.
 *
 * A torus has two natural circle foliations. Meridian circles are rotations of
 * one profile circle; parallel circles are SO(2) orbits of points on that
 * profile. Their superposition exposes volume without replacing construction
 * primitives with an opaque triangle mesh.
 */

export type Vec3 = { x: number; y: number; z: number }

export type SpatialCircle = {
  id: string
  family: 'meridian' | 'parallel'
  parameter: number
  center: Vec3
  normal: Vec3
  basisU: Vec3
  basisV: Vec3
  radius: number
  sourceSemanticId: 'torus-of-revolution'
  operation: 'rotate-profile-circle' | 'orbit-profile-point'
}

export type SpatialCircleFamily = {
  id: 'torus-two-circle-foliations'
  sourceEquation: '(sqrt(x^2+y^2)-R)^2+z^2=r^2'
  majorRadius: number
  minorRadius: number
  circles: SpatialCircle[]
  construction: {
    seed: 'profile-circle'
    action: 'SO(2)-rotation-about-z-axis'
    charts: ['meridian', 'parallel']
  }
}

export type SpatialFamilyVerification = {
  passed: boolean
  circles: number
  sampledPoints: number
  maxPlaneResidual: number
  maxCircleResidual: number
  maxSurfaceResidual: number
}

const sq = (value: number) => value * value
const add = (a: Vec3, b: Vec3): Vec3 => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z })
const scale = (value: Vec3, amount: number): Vec3 => ({
  x: value.x * amount,
  y: value.y * amount,
  z: value.z * amount,
})
const sub = (a: Vec3, b: Vec3): Vec3 => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
const dot = (a: Vec3, b: Vec3) => a.x * b.x + a.y * b.y + a.z * b.z
const normSquared = (value: Vec3) => dot(value, value)

export function pointOnSpatialCircle(circle: SpatialCircle, angle: number): Vec3 {
  return add(
    circle.center,
    add(
      scale(circle.basisU, circle.radius * Math.cos(angle)),
      scale(circle.basisV, circle.radius * Math.sin(angle)),
    ),
  )
}

export function buildTorusCircleFamily(options: {
  meridians?: number
  parallels?: number
  majorRadius?: number
  minorRadius?: number
} = {}): SpatialCircleFamily {
  const meridians = Math.max(3, Math.floor(options.meridians ?? 48))
  const parallels = Math.max(3, Math.floor(options.parallels ?? 48))
  const majorRadius = options.majorRadius ?? 4.45
  const minorRadius = options.minorRadius ?? 1.62
  if (!(majorRadius > minorRadius && minorRadius > 0)) {
    throw new Error('A ring torus requires R > r > 0')
  }

  const circles: SpatialCircle[] = []
  for (let index = 0; index < meridians; index += 1) {
    const angle = (index / meridians) * Math.PI * 2
    const radial = { x: Math.cos(angle), y: Math.sin(angle), z: 0 }
    circles.push({
      id: `meridian_${index + 1}`,
      family: 'meridian',
      parameter: angle,
      center: scale(radial, majorRadius),
      normal: { x: Math.sin(angle), y: -Math.cos(angle), z: 0 },
      basisU: radial,
      basisV: { x: 0, y: 0, z: 1 },
      radius: minorRadius,
      sourceSemanticId: 'torus-of-revolution',
      operation: 'rotate-profile-circle',
    })
  }

  for (let index = 0; index < parallels; index += 1) {
    const angle = (index / parallels) * Math.PI * 2
    circles.push({
      id: `parallel_${index + 1}`,
      family: 'parallel',
      parameter: angle,
      center: { x: 0, y: 0, z: minorRadius * Math.sin(angle) },
      normal: { x: 0, y: 0, z: 1 },
      basisU: { x: 1, y: 0, z: 0 },
      basisV: { x: 0, y: 1, z: 0 },
      radius: majorRadius + minorRadius * Math.cos(angle),
      sourceSemanticId: 'torus-of-revolution',
      operation: 'orbit-profile-point',
    })
  }

  return {
    id: 'torus-two-circle-foliations',
    sourceEquation: '(sqrt(x^2+y^2)-R)^2+z^2=r^2',
    majorRadius,
    minorRadius,
    circles,
    construction: {
      seed: 'profile-circle',
      action: 'SO(2)-rotation-about-z-axis',
      charts: ['meridian', 'parallel'],
    },
  }
}

export function verifySpatialCircleFamily(
  family: SpatialCircleFamily,
  samplesPerCircle = 48,
): SpatialFamilyVerification {
  let maxPlaneResidual = 0
  let maxCircleResidual = 0
  let maxSurfaceResidual = 0
  let sampledPoints = 0
  for (const circle of family.circles) {
    for (let index = 0; index < samplesPerCircle; index += 1) {
      const point = pointOnSpatialCircle(circle, (index / samplesPerCircle) * Math.PI * 2)
      const relative = sub(point, circle.center)
      const radial = Math.hypot(point.x, point.y)
      maxPlaneResidual = Math.max(maxPlaneResidual, Math.abs(dot(relative, circle.normal)))
      maxCircleResidual = Math.max(maxCircleResidual, Math.abs(normSquared(relative) - sq(circle.radius)))
      maxSurfaceResidual = Math.max(
        maxSurfaceResidual,
        Math.abs(sq(radial - family.majorRadius) + sq(point.z) - sq(family.minorRadius)),
      )
      sampledPoints += 1
    }
  }
  const tolerance = 1e-10
  return {
    passed:
      family.circles.length >= 6
      && maxPlaneResidual <= tolerance
      && maxCircleResidual <= tolerance
      && maxSurfaceResidual <= tolerance,
    circles: family.circles.length,
    sampledPoints,
    maxPlaneResidual,
    maxCircleResidual,
    maxSurfaceResidual,
  }
}

export function spatialCirclePaths(family: SpatialCircleFamily, segments = 128) {
  return family.circles.map(circle => ({
    id: circle.id,
    family: circle.family,
    operation: circle.operation,
    points: Array.from({ length: segments + 1 }, (_, index) =>
      pointOnSpatialCircle(circle, (index / segments) * Math.PI * 2)),
  }))
}
