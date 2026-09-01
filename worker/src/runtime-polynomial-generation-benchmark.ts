import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import { hasCompleteParentProof } from './autonomous-synthesis'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { synthesizePolynomialRootFusions } from './polynomial-root-fusion'

function hash(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function parentsFor(cohort: number, delta = 0): DiscoveryParent[] {
  const a = 1 + (cohort % 7)
  const b = 2 + ((3 * cohort) % 17) + delta
  const c = 1 + ((2 * cohort) % 11)
  const d = 3 + ((5 * cohort) % 19)
  return [
    { id: `unseen-polynomial-${cohort + 1}-left`, statement: `方程式 $x^2+${a}x-${b}=0$ のすべての根を考える。` },
    { id: `unseen-polynomial-${cohort + 1}-right`, statement: `方程式 $y^2-${c}y-${d}=0$ のすべての根を考える。` },
  ]
}

function main(): void {
  const cohortCount = Number(process.argv[2] ?? 40)
  const outputPath = resolve(process.argv[3] ?? 'artifacts/benchmarks/runtime-polynomial-generation-unseen-20260901.json')
  const failures: Array<Record<string, unknown>> = []
  const records: Array<Record<string, unknown>> = []
  const statementHashes = new Set<string>()
  let generatedCards = 0
  let exactCards = 0
  let completeParentCards = 0
  let registeredRouteCards = 0
  let mutationChanges = 0

  for (let cohort = 0; cohort < cohortCount; cohort++) {
    const parents = parentsFor(cohort)
    const cards = synthesizePolynomialRootFusions(parents, 3, 1 + (cohort % 3))
    let valid = cards.length === 3
    for (const card of cards) {
      generatedCards++
      statementHashes.add(hash(card.statement_tex))
      const exact = card.verification.exact_backend && card.verification.independent_check &&
        card.fusion_derivation.ablationPassed
      if (exact) exactCards++
      else valid = false
      if (hasCompleteParentProof(card, parents)) completeParentCards++
      else valid = false
      if (card.execution_certificate?.registered_composite_used === true) registeredRouteCards++
      if (card.execution_certificate?.capability_origin !== 'synthesized_proof_program') valid = false
      const program = card.execution_certificate?.generated_program as Record<string, unknown>
      if (program?.numeric_root_check !== true || program?.whole_parent_ablation !== true) valid = false
    }

    const changed = synthesizePolynomialRootFusions(parentsFor(cohort, 1), 1, 1 + (cohort % 3))
    const mutationChanged = cards.length > 0 && changed.length === 1 && cards[0].answer_tex !== changed[0].answer_tex
    if (mutationChanged) mutationChanges++
    else valid = false

    const record = {
      cohort: cohort + 1,
      parent_sha256: hash(parents),
      generated: cards.length,
      operations: cards.map(card => card.family_id),
      answer_sha256: cards.map(card => hash(card.answer_tex)),
      coefficient_mutation_changes_answer: mutationChanged,
      valid,
    }
    records.push(record)
    if (!valid) failures.push(record)
  }

  const summary = {
    schema: 'mortra.runtime-polynomial-generation-benchmark.v1',
    generated_at: new Date().toISOString(),
    claim_scope: 'fresh pairs of univariate quadratic root systems',
    methodology: {
      expected_answers_supplied: false,
      registered_completed_routes_allowed: false,
      operations_enumerated: ['root-set sum', 'root-set difference', 'pointwise root product'],
      exact_resultant_required: true,
      independent_numeric_root_check_required: true,
      both_parent_perturbation_required: true,
    },
    cohort_count: cohortCount,
    requested_cards: cohortCount * 3,
    generated_cards: generatedCards,
    distinct_statement_count: statementHashes.size,
    exact_and_independently_checked_cards: exactCards,
    complete_parent_proof_cards: completeParentCards,
    registered_route_cards: registeredRouteCards,
    mutated_cohorts_with_changed_answer: mutationChanges,
    failed_cohorts: failures.length,
    success_rate: cohortCount === 0 ? 0 : (cohortCount - failures.length) / cohortCount,
  }
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, `${JSON.stringify({ summary, failures, records }, null, 2)}\n`, 'utf8')
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`)
  if (failures.length > 0) process.exitCode = 1
}

main()
