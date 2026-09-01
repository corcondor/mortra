import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { runAutonomousSynthesis } from './autonomous-synthesis'

const cases = [
  ['quadratic-2-3', 'x^2-2', 'y^2-3'],
  ['quadratic-5-7', 'x^2-5', 'y^2-7'],
  ['golden-conjugates', 'x^2+x-1', 'y^2-y-1'],
  ['cubic-quadratic', 'x^3-x-1', 'y^2+y-1'],
  ['two-cubics', 'x^3+2x-5', 'y^3-y+1'],
  ['quartic-quadratic', 'x^4-x-1', 'y^2-y-1'],
] as const
const requestedPerCase = 5

function sha256(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

const startedAt = Date.now()
const rows = cases.map(([id, left, right]) => {
  const parents = [
    { id: `${id}:left`, statement: `方程式 $${left}=0$ の根を考える。` },
    { id: `${id}:right`, statement: `方程式 $${right}=0$ の根を考える。` },
  ]
  const result = runAutonomousSynthesis(parents, requestedPerCase)
  const cards = result.cards
  const runtimeCards = cards.filter(card =>
    card.execution_certificate?.capability_origin === 'synthesized_proof_program' &&
    card.execution_certificate?.registered_composite_used === false,
  )
  const answers = cards.map(card => card.answer_tex)
  const programHashes = cards.map(card => card.execution_certificate?.generated_program_sha256)
  const passed = cards.length === requestedPerCase &&
    runtimeCards.length === cards.length &&
    new Set(programHashes).size === cards.length &&
    new Set(answers).size >= 2 &&
    cards.every(card => card.verification.exact_backend && card.verification.independent_check)
  return {
    id,
    input_sha256: sha256(parents),
    generated: cards.length,
    runtime_synthesized: runtimeCards.length,
    registered_composites_used: cards.filter(card =>
      card.execution_certificate?.registered_composite_used === true).length,
    distinct_answers: new Set(answers).size,
    distinct_programs: new Set(programHashes).size,
    answers,
    generated_program_sha256: programHashes,
    attempted_strategies: result.attempts.map(attempt => ({
      strategy: attempt.strategy,
      applicable: attempt.applicable,
      generated: attempt.generated,
    })),
    passed,
  }
})

const artifact = {
  schema: 'mortra.cold-runtime-synthesis-benchmark.v1',
  created_at: new Date().toISOString(),
  protocol: {
    expected_answers_supplied: false,
    registered_composite_cache: 'empty',
    requested_per_case: requestedPerCase,
    required_origins: ['synthesized_proof_program'],
    required_checks: ['exact_backend', 'independent_check', 'whole-program one-parent ablation'],
  },
  cases: rows,
  aggregate: {
    cases: rows.length,
    passed_cases: rows.filter(row => row.passed).length,
    requested_cards: rows.length * requestedPerCase,
    generated_cards: rows.reduce((sum, row) => sum + row.generated, 0),
    runtime_synthesized_cards: rows.reduce((sum, row) => sum + row.runtime_synthesized, 0),
    registered_composites_used: rows.reduce((sum, row) => sum + row.registered_composites_used, 0),
    elapsed_ms: Date.now() - startedAt,
  },
}

const outputPath = path.resolve(__dirname, '..', '..', 'artifacts', 'benchmarks', 'cold-runtime-typed-program-20260901.json')
mkdirSync(path.dirname(outputPath), { recursive: true })
writeFileSync(outputPath, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({ outputPath, aggregate: artifact.aggregate }, null, 2)}\n`)

if (artifact.aggregate.passed_cases !== artifact.aggregate.cases) process.exitCode = 1
