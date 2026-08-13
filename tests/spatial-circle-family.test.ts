import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildTorusCircleFamily,
  spatialCirclePaths,
  verifySpatialCircleFamily,
} from '../lib/mortra/construction/spatial-circle-family.js'

test('96 planar circles form two verified foliations of one torus', () => {
  const family = buildTorusCircleFamily()
  const verification = verifySpatialCircleFamily(family)
  assert.equal(family.circles.filter(circle => circle.family === 'meridian').length, 48)
  assert.equal(family.circles.filter(circle => circle.family === 'parallel').length, 48)
  assert.equal(verification.circles, 96)
  assert.equal(verification.sampledPoints, 4608)
  assert.equal(verification.passed, true)
  assert.ok(verification.maxSurfaceResidual < 1e-10)
})

test('increasing sampling density preserves the same semantic construction', () => {
  const family = buildTorusCircleFamily({ meridians: 64, parallels: 64 })
  assert.equal(family.circles.length, 128)
  assert.equal(verifySpatialCircleFamily(family, 64).passed, true)
  assert.equal(spatialCirclePaths(family, 192).every(path => path.points.length === 193), true)
})

test('a tampered circle is rejected by the surface invariant', () => {
  const family = structuredClone(buildTorusCircleFamily())
  family.circles[17].center.z += 0.4
  assert.equal(verifySpatialCircleFamily(family).passed, false)
})
