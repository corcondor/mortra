import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { runAutonomousSynthesis } from './autonomous-synthesis'

const cases = [
  { id: 'seventh-roots', map: 'T(z)=\\frac{2z+1}{z+1}', orbit: '方程式 \\(z^7-1=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'cubic-radical', map: 'T(z)=\\frac{3z-2}{2z+1}', orbit: '方程式 \\(z^3-2=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'quartic-orbit', map: 'T(z)=\\frac{z+1}{2z-3}', orbit: '方程式 \\(z^4+z+1=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'quintic-orbit', map: 'T(z)=\\frac{-2z+5}{z-2}', orbit: '方程式 \\(z^5-z+1=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'sextic-orbit', map: 'T(z)=\\frac{5z+1}{3z+2}', orbit: '方程式 \\(z^6+z+1=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'asymmetric-cubic', map: 'T(z)=\\frac{z-4}{z+3}', orbit: '方程式 \\(z^3+z^2-1=0\\) の根全体を考える。', traceKinds: ['rational-map-orbit', 'root-invariant'], expectedGenerated: true },
  { id: 'symbolic-unit-orbit', map: 'T(z)=\\frac{3z+2}{z+2}', orbit: '\\(z_1,\\ldots,z_n\\) を \\(z^n=1\\) の全ての解とする。', traceKinds: ['symbolic-power-orbit', 'power-orbit-summation'], expectedGenerated: true },
  { id: 'symbolic-renamed-orbit', map: 'S(w)=\\frac{5w-1}{2w+3}', orbit: '\\(w_1,\\ldots,w_m\\) を \\(w^m=2\\) の全ての解とする。', traceKinds: ['symbolic-power-orbit', 'power-orbit-summation'], expectedGenerated: true },
  { id: 'symbolic-negative-level', map: 'F(x)=\\frac{-2x+7}{3x-4}', orbit: '\\(x_1,\\ldots,x_k\\) を \\(x^k=-2\\) の全ての解とする。', traceKinds: ['symbolic-power-orbit', 'power-orbit-summation'], expectedGenerated: true },
  { id: 'symbolic-affine-negative-control', map: 'A(y)=\\frac{4y+3}{5}', orbit: '\\(y_1,\\ldots,y_r\\) を \\(y^r=3\\) の全ての解とする。', traceKinds: [], expectedGenerated: false },
] as const

function sha256(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

const startedAt = Date.now()
const rows = cases.map(({ id, map, orbit, traceKinds: requiredTraceKinds, expectedGenerated }) => {
  const parents = [
    {
      id: `${id}:map`,
      statement: `一次分数変換 \\(${map}\\) を考える。`,
    },
    {
      id: `${id}:orbit`,
      statement: orbit,
    },
  ]
  const result = runAutonomousSynthesis(parents, 1)
  const card = result.cards[0]
  const generated = card?.execution_certificate?.generated_program as {
    parent_ablation_outputs?: Record<string, string>
    exact_trace?: Array<{ kind?: string }>
  } | undefined
  const ablatedParents = Object.keys(generated?.parent_ablation_outputs ?? {}).sort()
  const expectedParents = parents.map(parent => parent.id).sort()
  const traceKinds = generated?.exact_trace?.map(step => step.kind) ?? []
  const noRegisteredRoute = result.attempts.every(attempt =>
    attempt.strategy !== 'registered-composite-program-instantiation')
  const passed = expectedGenerated
    ? Boolean(card) &&
      card.execution_certificate?.capability_origin === 'synthesized_proof_program' &&
      card.execution_certificate?.registered_composite_used === false &&
      card.verification.exact_backend &&
      card.verification.independent_check &&
      card.morphism_chain.includes('MapOrbitEvaluation') &&
      card.morphism_chain.includes('FiniteSummation') &&
      requiredTraceKinds.every(kind => traceKinds.includes(kind)) &&
      noRegisteredRoute &&
      JSON.stringify(ablatedParents) === JSON.stringify(expectedParents)
    : !card && result.state.continuing && noRegisteredRoute
  return {
    id,
    input_sha256: sha256(parents),
    answer: card?.answer_tex ?? null,
    generated_program_sha256: card?.execution_certificate?.generated_program_sha256 ?? null,
    capability_origin: card?.execution_certificate?.capability_origin ?? null,
    registered_composite_used: card?.execution_certificate?.registered_composite_used ?? null,
    morphism_chain: card?.morphism_chain ?? [],
    trace_kinds: traceKinds,
    parent_ablation_outputs: generated?.parent_ablation_outputs ?? {},
    attempted_strategies: result.attempts.map(attempt => ({
      strategy: attempt.strategy,
      applicable: attempt.applicable,
      generated: attempt.generated,
    })),
    required_trace_kinds: requiredTraceKinds,
    expected_generated: expectedGenerated,
    passed,
  }
})

const artifact = {
  schema: 'mortra.cold-runtime-map-orbit-benchmark.v2',
  created_at: new Date().toISOString(),
  protocol: {
    expected_answers_supplied: false,
    solutions_supplied: false,
    registered_composite_cache: 'not consulted for generation eligibility',
    required_programs: [
      ['MobiusMap', 'RootConfiguration', 'MapOrbitEvaluation', 'FiniteSummation'],
      ['MobiusMap', 'RootsOfUnity', 'MapOrbitEvaluation', 'FiniteSummation'],
    ],
    required_checks: [
      'exact resultant over QQ',
      'fractional-linear determinant nonzero',
      'pole exclusion on the algebraic orbit',
      'independent numerical root comparison',
      'whole-program one-parent ablation',
      'default strategy list contains no registered completed-route fallback',
    ],
  },
  cases: rows,
  aggregate: {
    cases: rows.length,
    passed_cases: rows.filter(row => row.passed).length,
    runtime_synthesized_cards: rows.filter(row => row.capability_origin === 'synthesized_proof_program').length,
    registered_composites_used: rows.filter(row => row.registered_composite_used === true).length,
    distinct_answers: new Set(rows.flatMap(row => row.answer === null ? [] : [row.answer])).size,
    distinct_generated_programs: new Set(rows.flatMap(row => row.generated_program_sha256 === null ? [] : [row.generated_program_sha256])).size,
    parent_ablation_rejections: rows.filter(row => !row.expected_generated && row.passed).length,
    registered_route_attempts: rows.reduce((sum, row) => sum + row.attempted_strategies.filter(attempt =>
      attempt.strategy === 'registered-composite-program-instantiation').length, 0),
    elapsed_ms: Date.now() - startedAt,
  },
}

const outputPath = path.resolve(
  __dirname,
  '..',
  '..',
  'artifacts',
  'benchmarks',
  'cold-runtime-map-orbit-20260901.json',
)
mkdirSync(path.dirname(outputPath), { recursive: true })
writeFileSync(outputPath, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({ outputPath, aggregate: artifact.aggregate }, null, 2)}\n`)

if (artifact.aggregate.passed_cases !== artifact.aggregate.cases) process.exitCode = 1
