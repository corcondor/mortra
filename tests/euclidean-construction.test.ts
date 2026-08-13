import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildCircumcenterConstruction,
  buildHexagonalCircleOrbitConstruction,
  constructionDrawingPaths,
  solveConstructionGoal,
  verifyConstructionPlan,
  type ConstructionGoal,
  type ConstructionPlan,
} from '../lib/mortra/construction/euclidean-construction.js'

test('circumcenter is synthesized from three equidistance loci', () => {
  const plan = buildCircumcenterConstruction()
  assert.equal(plan.status, 'verified')
  assert.equal(plan.witnessIds.length, 1)
  assert.equal(verifyConstructionPlan(plan).passed, true)
  assert.ok(plan.steps.filter(step => step.operation === 'circle-center-through').length >= 7)
  assert.ok(plan.steps.filter(step => step.operation === 'intersect-circle-circle').length >= 3)
  assert.ok(constructionDrawingPaths(plan).length >= 18)
})

test('a 19-circle orbit is constructed only through reusable intersections', () => {
  const plan = buildHexagonalCircleOrbitConstruction()
  const circles = Object.values(plan.objects).filter(object => object.kind === 'circle')
  assert.equal(plan.status, 'verified')
  assert.equal(circles.length, 19)
  assert.equal(plan.witnessIds.length, 18)
  assert.equal(verifyConstructionPlan(plan).passed, true)
  assert.ok(plan.steps.filter(step => step.operation.startsWith('intersect-')).length >= 17)
})

test('the 19-circle construction is scale invariant', () => {
  const small = buildHexagonalCircleOrbitConstruction(1.25)
  const large = buildHexagonalCircleOrbitConstruction(4.75)
  assert.equal(small.status, 'verified')
  assert.equal(large.status, 'verified')
  assert.deepEqual(
    small.steps.map(step => step.operation),
    large.steps.map(step => step.operation),
  )
})

test('the same locus compiler constructs a midpoint', () => {
  const plan = solveConstructionGoal({
    id: 'midpoint', label: 'midpoint', unknown: 'M',
    givens: { a: { x: -4, y: 1 }, b: { x: 2, y: 3 } },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'equidistant', a: 'a', b: 'b' },
    ],
  })
  assert.equal(plan.status, 'verified')
  const midpoint = plan.objects[plan.witnessIds[0]]
  assert.equal(midpoint.kind, 'point')
  if (midpoint.kind === 'point') {
    assert.ok(Math.abs(midpoint.x + 1) < 1e-7)
    assert.ok(Math.abs(midpoint.y - 2) < 1e-7)
  }
})

test('the same locus compiler returns both equilateral apexes', () => {
  const plan = solveConstructionGoal({
    id: 'equilateral', label: 'equilateral apex', unknown: 'P',
    givens: { a: { x: -2, y: 0 }, b: { x: 2, y: 0 } },
    constraints: [
      { kind: 'on-circle', center: 'a', through: 'b' },
      { kind: 'on-circle', center: 'b', through: 'a' },
    ],
  })
  assert.equal(plan.status, 'verified')
  assert.equal(plan.witnessIds.length, 2)
  assert.equal(verifyConstructionPlan(plan).passed, true)
})

test('inconsistent typed loci abstain instead of fabricating a point', () => {
  const goal: ConstructionGoal = {
    id: 'parallel-lines', label: 'no intersection', unknown: 'X',
    givens: {
      a: { x: 0, y: 0 }, b: { x: 3, y: 0 },
      c: { x: 0, y: 2 }, d: { x: 3, y: 2 },
    },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'on-line', a: 'c', b: 'd' },
    ],
  }
  const plan = solveConstructionGoal(goal)
  assert.equal(plan.status, 'unsatisfied')
  assert.deepEqual(plan.witnessIds, [])
})

test('independent replay rejects a tampered derived intersection', () => {
  const source = buildCircumcenterConstruction()
  const tampered = structuredClone(source) as ConstructionPlan
  const step = tampered.steps.find(item => item.operation === 'intersect-circle-circle')
  assert.ok(step?.produced[0]?.kind === 'point')
  if (step?.produced[0]?.kind === 'point') step.produced[0].x += 0.25
  assert.equal(verifyConstructionPlan(tampered).passed, false)
})

test('similarity transforms preserve construction success and operation vocabulary', () => {
  const base: ConstructionGoal = {
    id: 'circumcenter-base', label: 'circumcenter', unknown: 'O',
    givens: { a: { x: 0, y: 0 }, b: { x: 4, y: 0 }, c: { x: 1, y: 3 } },
    constraints: [
      { kind: 'equidistant', a: 'a', b: 'b' },
      { kind: 'equidistant', a: 'a', b: 'c' },
    ],
  }
  const transformed: ConstructionGoal = {
    ...base,
    id: 'circumcenter-transformed',
    givens: Object.fromEntries(Object.entries(base.givens).map(([id, point]) => [id, {
      x: 2 - 1.7 * point.y,
      y: -3 + 1.7 * point.x,
    }])),
  }
  const first = solveConstructionGoal(base)
  const second = solveConstructionGoal(transformed)
  assert.equal(first.status, 'verified')
  assert.equal(second.status, 'verified')
  assert.deepEqual(
    first.steps.map(step => step.operation),
    second.steps.map(step => step.operation),
  )
})
