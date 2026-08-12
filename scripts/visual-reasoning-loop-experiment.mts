import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  compileScene,
  factKey,
  forwardChain,
  type Fact,
  type Pt,
} from '../lib/proof-scene.js'
import type { CoordinateProvenance } from '../lib/mortra/vision/geometry-candidate-loop.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

type ExperimentCase = {
  id: string
  points: Record<string, Pt>
  premises: Fact[]
  goal: Fact
  expectedIntermediate: Fact
  provenance?: CoordinateProvenance
  shouldProve: boolean
}

const base: Record<string, Pt> = {
  a: { x: 0, y: 0 }, b: { x: 2, y: 0 },
  c: { x: 0, y: 1 }, d: { x: 2, y: 1 },
  e: { x: 3, y: 0 }, f: { x: 3, y: 2 },
}

const positive: ExperimentCase[] = [
  {
    id: 'parallel-plus-hidden-perpendicular',
    points: base,
    premises: [{ pred: 'para', args: ['a', 'b', 'c', 'd'] }],
    goal: { pred: 'perp', args: ['a', 'b', 'e', 'f'] },
    expectedIntermediate: { pred: 'perp', args: ['c', 'd', 'e', 'f'] },
    shouldProve: true,
  },
  {
    id: 'common-hidden-perpendicular',
    points: base,
    premises: [{ pred: 'perp', args: ['a', 'b', 'e', 'f'] }],
    goal: { pred: 'para', args: ['a', 'b', 'c', 'd'] },
    expectedIntermediate: { pred: 'perp', args: ['c', 'd', 'e', 'f'] },
    shouldProve: true,
  },
  {
    id: 'hidden-isosceles',
    points: { a: { x: 0, y: 2 }, b: { x: -1, y: 0 }, c: { x: 1, y: 0 } },
    premises: [],
    goal: { pred: 'eqangle', args: ['b', 'a', 'b', 'c', 'c', 'b', 'c', 'a'] },
    expectedIntermediate: { pred: 'cong', args: ['a', 'b', 'a', 'c'] },
    shouldProve: true,
  },
  {
    id: 'hidden-equidistance',
    points: {
      b: { x: -2, y: 0 }, c: { x: 2, y: 0 },
      m: { x: 0, y: 0 }, o: { x: 0, y: 3 },
    },
    premises: [{ pred: 'midp', args: ['m', 'b', 'c'] }],
    goal: { pred: 'perp', args: ['o', 'm', 'b', 'c'] },
    expectedIntermediate: { pred: 'cong', args: ['o', 'b', 'o', 'c'] },
    shouldProve: true,
  },
  {
    id: 'hidden-parallel-chain',
    points: {
      a: { x: 0, y: 0 }, b: { x: 2, y: 0 },
      c: { x: 0, y: 1 }, d: { x: 2, y: 1 },
      e: { x: 0, y: 2 }, f: { x: 2, y: 2 },
    },
    premises: [{ pred: 'para', args: ['a', 'b', 'c', 'd'] }],
    goal: { pred: 'para', args: ['a', 'b', 'e', 'f'] },
    expectedIntermediate: { pred: 'para', args: ['c', 'd', 'e', 'f'] },
    shouldProve: true,
  },
  {
    id: 'hidden-midpoint',
    points: { a: { x: 0, y: 0 }, m: { x: 2, y: 0 }, b: { x: 4, y: 0 } },
    premises: [],
    goal: { pred: 'coll', args: ['a', 'm', 'b'] },
    expectedIntermediate: { pred: 'midp', args: ['m', 'a', 'b'] },
    shouldProve: true,
  },
]

const negative: ExperimentCase[] = [
  {
    ...positive[0],
    id: 'constructed-witness-is-not-proof',
    provenance: 'constructed_witness',
    shouldProve: false,
  },
  {
    id: 'near-perpendicular-is-not-exact',
    points: { ...base, d: { x: 2, y: 1.02 } },
    premises: [{ pred: 'perp', args: ['a', 'b', 'e', 'f'] }],
    goal: { pred: 'para', args: ['a', 'b', 'c', 'd'] },
    expectedIntermediate: { pred: 'perp', args: ['c', 'd', 'e', 'f'] },
    shouldProve: false,
  },
]

function execute(item: ExperimentCase) {
  const baseline = forwardChain(item.premises, item.goal, item.points)
  const scene = compileScene({
    title: item.id,
    statement: item.id,
    premises: item.premises,
    goal: item.goal,
    points: item.points,
    visualReasoning: {
      coordinateProvenance: item.provenance ?? 'given_exact',
      allowDirectGoal: false,
      maxCandidates: 256,
    },
  })
  const expectedKey = factKey(item.expectedIntermediate)
  const expected = scene.visualReasoning?.candidates.find(candidate => factKey(candidate.fact) === expectedKey)
  return {
    id: item.id,
    expected: item.shouldProve,
    baseline_proved: baseline.proved,
    visual_loop_proved: scene.proved,
    expected_intermediate: expectedKey,
    intermediate_status: expected?.certificate.status ?? 'not_proposed',
    proposed: scene.visualReasoning?.candidates.length ?? 0,
    certified: scene.visualReasoning?.certified ?? 0,
    proof_opening: scene.visualReasoning?.proofOpening ?? 0,
    selected: scene.visualReasoning?.selectedCandidateIds.length ?? 0,
    rejected: scene.visualReasoning?.rejected ?? 0,
    conjecture_only: scene.visualReasoning?.conjectureOnly ?? 0,
    proof_steps: scene.beats.filter(beat => beat.origin !== 'given').length,
    rules_used: scene.rulesUsed,
  }
}

const rows = [...positive, ...negative].map(execute)
const positiveRows = rows.slice(0, positive.length)
const negativeRows = rows.slice(positive.length)
const proposed = rows.reduce((sum, row) => sum + row.proposed, 0)
const certified = rows.reduce((sum, row) => sum + row.certified, 0)
const rejected = rows.reduce((sum, row) => sum + row.rejected, 0)
const proofOpening = rows.reduce((sum, row) => sum + row.proof_opening, 0)
const selected = rows.reduce((sum, row) => sum + row.selected, 0)
const summary = {
  positive_cases: positiveRows.length,
  negative_cases: negativeRows.length,
  baseline_proof_rate: positiveRows.filter(row => row.baseline_proved).length / positiveRows.length,
  visual_loop_proof_rate: positiveRows.filter(row => row.visual_loop_proved).length / positiveRows.length,
  auxiliary_candidate_recall: positiveRows.filter(row => row.intermediate_status === 'certified').length / positiveRows.length,
  proposal_precision_after_exact_verification: certified / Math.max(1, certified + rejected),
  proof_opening_candidates: proofOpening,
  selected_reasoning_seeds: selected,
  selected_seed_precision: positiveRows.filter(row => row.visual_loop_proved).length / Math.max(1, selected),
  verifier_false_acceptance_rate: negativeRows.filter(row => row.visual_loop_proved).length / negativeRows.length,
  mean_augmented_proof_steps: positiveRows.reduce((sum, row) => sum + row.proof_steps, 0) / positiveRows.length,
  candidates_proposed: proposed,
  candidates_certified: certified,
  candidates_rejected: rejected,
}

const artifact = {
  experiment: 'semantic-geometry-visual-candidate-verifier-loop-v1',
  recorded_on: '2026-08-13',
  semantics: {
    candidate_source: 'bounded spatial inspection over salient typed points and segments',
    acceptance: 'safe exact-rational polynomial identities only',
    witness_policy: 'constructed witnesses may propose conjectures but cannot certify facts',
    direct_goal_policy: 'disabled to measure whether an intermediate proposition opens a proof',
  },
  summary,
  rows,
}

const demo = compileScene({
  title: 'Visual feedback loop',
  statement: '厳密座標で定義された点から中間命題を観測し、検証後に証明へ戻す。',
  premises: positive[0].premises,
  goal: positive[0].goal,
  points: positive[0].points,
  visualReasoning: {
    coordinateProvenance: 'given_exact',
    allowDirectGoal: false,
    maxCandidates: 256,
  },
})
if (demo.visualReasoning) {
  const selected = new Set(demo.visualReasoning.selectedCandidateIds)
  demo.visualReasoning.candidates = demo.visualReasoning.candidates.filter(candidate => selected.has(candidate.id))
}

await mkdir(path.join(ROOT, 'data'), { recursive: true })
await writeFile(
  path.join(ROOT, 'data', 'visual-reasoning-loop-experiment.json'),
  `${JSON.stringify(artifact, null, 2)}\n`,
  'utf8',
)
await writeFile(
  path.join(ROOT, 'data', 'visual-reasoning-demo.json'),
  `${JSON.stringify(demo, null, 2)}\n`,
  'utf8',
)

console.log(JSON.stringify(summary, null, 2))
if (summary.visual_loop_proof_rate !== 1 || summary.verifier_false_acceptance_rate !== 0) process.exit(1)
