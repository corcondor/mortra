import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  buildCircumcenterConstruction,
  buildHexagonalCircleOrbitConstruction,
  solveConstructionGoal,
  verifyConstructionPlan,
  type ConstructionGoal,
  type PointConstraint,
  type Vec2,
} from '../lib/mortra/construction/euclidean-construction.js'
import {
  buildTorusCircleFamily,
  verifySpatialCircleFamily,
} from '../lib/mortra/construction/spatial-circle-family.js'
import {
  buildDynkinA,
  buildTorusCellulation,
  verifyCellComplex,
} from '../lib/mortra/construction/diagrammatic-complex.js'
import { evaluateDiagramSemantics } from '../lib/mortra/construction/diagram-semantic-evaluation.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sq = (value: number) => value * value
const d2 = (a: Vec2, b: Vec2) => sq(a.x - b.x) + sq(a.y - b.y)

function visibleWitness(goal: ConstructionGoal) {
  const residual = (point: Vec2, constraint: PointConstraint) => {
    if (constraint.kind === 'equidistant') {
      return Math.abs(d2(point, goal.givens[constraint.a]) - d2(point, goal.givens[constraint.b]))
    }
    if (constraint.kind === 'on-circle') {
      return Math.abs(
        d2(point, goal.givens[constraint.center])
        - d2(goal.givens[constraint.center], goal.givens[constraint.through]),
      )
    }
    const a = goal.givens[constraint.a]
    const b = goal.givens[constraint.b]
    return Math.abs((b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x))
  }
  return Object.values(goal.givens).some(point =>
    goal.constraints.every(constraint => residual(point, constraint) < 1e-7))
}

const circumcenter = (id: string, givens: Record<string, Vec2>): ConstructionGoal => ({
  id, label: 'circumcenter', unknown: 'O', givens,
  constraints: [
    { kind: 'equidistant', a: 'a', b: 'b' },
    { kind: 'equidistant', a: 'a', b: 'c' },
  ],
})

const midpoint = (id: string, a: Vec2, b: Vec2): ConstructionGoal => ({
  id, label: 'midpoint', unknown: 'M', givens: { a, b },
  constraints: [
    { kind: 'on-line', a: 'a', b: 'b' },
    { kind: 'equidistant', a: 'a', b: 'b' },
  ],
})

const equilateral = (id: string, a: Vec2, b: Vec2): ConstructionGoal => ({
  id, label: 'equilateral apex', unknown: 'P', givens: { a, b },
  constraints: [
    { kind: 'on-circle', center: 'a', through: 'b' },
    { kind: 'on-circle', center: 'b', through: 'a' },
  ],
})

const positive: ConstructionGoal[] = [
  circumcenter('circumcenter-acute', {
    a: { x: 0, y: 0 }, b: { x: 4, y: 0 }, c: { x: 1, y: 3 },
  }),
  circumcenter('circumcenter-rotated', {
    a: { x: 2, y: -3 }, b: { x: 2, y: 3.8 }, c: { x: -3.1, y: -1.3 },
  }),
  circumcenter('circumcenter-scaled', {
    a: { x: -5, y: 1 }, b: { x: 3, y: -2 }, c: { x: 4, y: 5 },
  }),
  circumcenter('circumcenter-obtuse', {
    a: { x: -4, y: 0 }, b: { x: 5, y: 0 }, c: { x: -2.5, y: 2 },
  }),
  midpoint('midpoint-horizontal', { x: -5, y: 1 }, { x: 3, y: 1 }),
  midpoint('midpoint-slanted', { x: -3, y: -4 }, { x: 5, y: 2 }),
  midpoint('midpoint-vertical', { x: 2, y: -6 }, { x: 2, y: 4 }),
  equilateral('equilateral-horizontal', { x: -3, y: 0 }, { x: 3, y: 0 }),
  equilateral('equilateral-slanted', { x: -2, y: -1 }, { x: 3, y: 4 }),
  equilateral('equilateral-short', { x: 1, y: 1 }, { x: 3, y: 0 }),
  {
    id: 'line-circle', label: 'line circle intersection', unknown: 'X',
    givens: {
      a: { x: -5, y: 0 }, b: { x: 5, y: 0 },
      c: { x: 0, y: 0 }, d: { x: 3, y: 0 },
    },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'on-circle', center: 'c', through: 'd' },
    ],
  },
  {
    id: 'line-line', label: 'line intersection', unknown: 'X',
    givens: {
      a: { x: -4, y: -2 }, b: { x: 4, y: 3 },
      c: { x: -3, y: 4 }, d: { x: 5, y: -3 },
    },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'on-line', a: 'c', b: 'd' },
    ],
  },
]

const negative: ConstructionGoal[] = [
  {
    id: 'parallel-lines', label: 'parallel lines', unknown: 'X',
    givens: {
      a: { x: 0, y: 0 }, b: { x: 3, y: 0 },
      c: { x: 0, y: 2 }, d: { x: 3, y: 2 },
    },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'on-line', a: 'c', b: 'd' },
    ],
  },
  {
    id: 'disjoint-circles', label: 'disjoint circles', unknown: 'X',
    givens: {
      a: { x: -5, y: 0 }, b: { x: -4, y: 0 },
      c: { x: 5, y: 0 }, d: { x: 6, y: 0 },
    },
    constraints: [
      { kind: 'on-circle', center: 'a', through: 'b' },
      { kind: 'on-circle', center: 'c', through: 'd' },
    ],
  },
  {
    id: 'concentric-circles', label: 'concentric circles', unknown: 'X',
    givens: {
      o: { x: 0, y: 0 }, a: { x: 2, y: 0 }, b: { x: 4, y: 0 },
    },
    constraints: [
      { kind: 'on-circle', center: 'o', through: 'a' },
      { kind: 'on-circle', center: 'o', through: 'b' },
    ],
  },
  {
    id: 'line-misses-circle', label: 'line misses circle', unknown: 'X',
    givens: {
      a: { x: -4, y: 5 }, b: { x: 4, y: 5 },
      c: { x: 0, y: 0 }, d: { x: 2, y: 0 },
    },
    constraints: [
      { kind: 'on-line', a: 'a', b: 'b' },
      { kind: 'on-circle', center: 'c', through: 'd' },
    ],
  },
]

const rows = [...positive, ...negative].map((goal, index) => {
  const plan = solveConstructionGoal(goal)
  const verification = verifyConstructionPlan(plan)
  return {
    id: goal.id,
    expected: index < positive.length,
    baseline_visible_witness: visibleWitness(goal),
    construction_status: plan.status,
    replay_verified: verification.passed,
    witnesses: plan.witnessIds.length,
    steps: plan.steps.length,
    operations: [...new Set(plan.steps.map(step => step.operation))],
    max_residual: verification.maxResidual,
  }
})

const positiveRows = rows.slice(0, positive.length)
const negativeRows = rows.slice(positive.length)
const summary = {
  cases: positiveRows.length,
  negative_cases: negativeRows.length,
  baseline_without_auxiliary_construction: positiveRows.filter(row => row.baseline_visible_witness).length,
  construction_search_solved: positiveRows.filter(row => row.construction_status === 'verified').length,
  independently_replayed: positiveRows.filter(row => row.replay_verified).length,
  false_acceptance: negativeRows.filter(row => row.construction_status === 'verified').length,
  mean_steps: positiveRows.reduce((sum, row) => sum + row.steps, 0) / positiveRows.length,
  operation_vocabulary: [...new Set(rows.flatMap(row => row.operations))].sort(),
}

const designPlan = buildHexagonalCircleOrbitConstruction()
const designVerification = verifyConstructionPlan(designPlan)
const designCircles = Object.values(designPlan.objects).filter(object => object.kind === 'circle')
const designBenchmark = {
  target: 'two-ring hexagonal orbit generated from one centre and one radius point',
  circles: designCircles.length,
  derived_centres: designPlan.witnessIds.length,
  construction_steps: designPlan.steps.length,
  intersection_steps: designPlan.steps.filter(step => step.operation.startsWith('intersect-')).length,
  independent_replay: designVerification.passed,
  max_residual: designVerification.maxResidual,
}
const spatialFamily = buildTorusCircleFamily()
const spatialVerification = verifySpatialCircleFamily(spatialFamily)
const spatialBenchmark = {
  target: 'torus represented by two planar circle foliations',
  planar_circles: spatialFamily.circles.length,
  meridians: spatialFamily.circles.filter(circle => circle.family === 'meridian').length,
  parallels: spatialFamily.circles.filter(circle => circle.family === 'parallel').length,
  sampled_points: spatialVerification.sampledPoints,
  invariant_verified: spatialVerification.passed,
  max_surface_residual: spatialVerification.maxSurfaceResidual,
}
const dynkinComplex = buildDynkinA(8)
const torusComplex = buildTorusCellulation(40, 30)
const dynkinVerification = verifyCellComplex(dynkinComplex)
const torusComplexVerification = verifyCellComplex(torusComplex)
const semanticReference = buildTorusCellulation(12, 9)
const semanticIdMap = new Map(
  semanticReference.cells.map((cell, index) => [cell.id, `candidate_${index}`]),
)
const semanticIsomorph = {
  ...semanticReference,
  cells: semanticReference.cells.map(cell => ({
    ...cell,
    id: semanticIdMap.get(cell.id)!,
    boundary: cell.boundary.map(term => ({
      ...term,
      cellId: semanticIdMap.get(term.cellId)!,
    })),
  })),
}
const semanticBroken = structuredClone(semanticReference)
const brokenFace = semanticBroken.cells.find(cell => cell.dimension === 2)!
brokenFace.boundary[0] = brokenFace.boundary[1]
const isomorphScore = evaluateDiagramSemantics(semanticReference, semanticIsomorph)
const brokenScore = evaluateDiagramSemantics(semanticReference, semanticBroken)
const diagrammaticBenchmark = {
  target: 'sparse typed cell complexes independent of geometric embedding',
  dynkin_A8_verified: dynkinVerification.passed,
  torus_cellulation_verified: torusComplexVerification.passed,
  torus_cells: torusComplex.cells.length,
  torus_counts: torusComplexVerification.counts,
  torus_euler_characteristic: torusComplexVerification.eulerCharacteristic,
  torus_betti_numbers: torusComplexVerification.bettiNumbers,
  boundary_squared_residuals: torusComplexVerification.boundarySquaredResiduals,
  semantic_id_invariance: isomorphScore.strictPass,
  topology_error_rejected: !brokenScore.strictPass,
  topology_error_primitive_f1: brokenScore.cellTypeF1,
}

const artifact = {
  experiment: 'typed-locus-to-dynamic-euclidean-construction-v1',
  recorded_on: '2026-08-13',
  scope: 'typed point constraints with straightedge-and-compass locus compilation',
  claim_boundary: [
    'This is a bounded auxiliary-construction benchmark, not the frozen 522-problem benchmark.',
    'Certificates are deterministic independent numeric replay, not Lean proofs.',
    'Natural-language parsing is held outside this experiment.',
  ],
  summary,
  design_benchmark: designBenchmark,
  spatial_benchmark: spatialBenchmark,
  diagrammatic_benchmark: diagrammaticBenchmark,
  rows,
}

await mkdir(path.join(ROOT, 'data'), { recursive: true })
await writeFile(
  path.join(ROOT, 'data', 'euclidean-construction-experiment.json'),
  `${JSON.stringify(artifact, null, 2)}\n`,
  'utf8',
)
await writeFile(
  path.join(ROOT, 'data', 'euclidean-construction-demo.json'),
  `${JSON.stringify(designPlan, null, 2)}\n`,
  'utf8',
)

console.log(JSON.stringify(summary, null, 2))
if (
  summary.construction_search_solved !== positive.length
  || summary.independently_replayed !== positive.length
  || summary.false_acceptance !== 0
  || !spatialVerification.passed
  || !dynkinVerification.passed
  || !torusComplexVerification.passed
  || !isomorphScore.strictPass
  || brokenScore.strictPass
) process.exit(1)
