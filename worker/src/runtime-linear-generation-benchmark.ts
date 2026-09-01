import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import {
  executeLinearInvariant,
  verifyLinearInvariantCertificate,
  type LinearInvariantProgram,
} from './exact-linear-invariant'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { synthesizeRuntimeLinearProblems } from './runtime-linear-problem-generation'

type GeneratedProgram = {
  equations: LinearInvariantProgram['equations']
  goal: LinearInvariantProgram['goal']
  exact_value: string
  proof_coefficients: string[]
  ablations: Array<{ parent_id: string; status: string }>
  counterfactuals: Array<{ parent_id: string; value_before: string; value_after: string }>
}

function hash(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function parentFor(cohort: number, parentIndex: number, firstRhsDelta = 0): DiscoveryParent {
  const a = 2 + ((cohort + 2 * parentIndex) % 7)
  const b = 1 + ((2 * cohort + parentIndex) % 5)
  const c = 1 + ((cohort + 3 * parentIndex) % 6)
  let d = 2 + ((3 * cohort + 2 * parentIndex) % 7)
  if (a * d === b * c) d += 1
  const firstRhs = 19 + 5 * cohort + 7 * parentIndex + firstRhsDelta
  const secondRhs = 11 + 3 * cohort + 13 * parentIndex
  return {
    id: `unseen-${cohort + 1}-${parentIndex + 1}`,
    statement: `実数 $x,y$ は $${a}x+${b}y=${firstRhs}$, $${c}x+${d}y=${secondRhs}$ を満たす。$x$ を求めよ。`,
  }
}

function main(): void {
  const cohortCount = Number(process.argv[2] ?? 120)
  const requestedPerCohort = Number(process.argv[3] ?? 8)
  const outputPath = resolve(process.argv[4] ?? 'artifacts/benchmarks/runtime-linear-generation-unseen-20260901.json')
  const records: Array<Record<string, unknown>> = []
  const failures: Array<Record<string, unknown>> = []
  const statementHashes = new Set<string>()
  let exactReplayCards = 0
  let registeredRouteCards = 0
  let allParentAblationsPassed = 0
  let allParentCounterfactualsPassed = 0
  let mutationAnswerChanges = 0
  let totalCards = 0

  for (let cohort = 0; cohort < cohortCount; cohort++) {
    const parentCount = 2 + (cohort % 3)
    const parents = Array.from({ length: parentCount }, (_, parentIndex) => parentFor(cohort, parentIndex))
    const result = synthesizeRuntimeLinearProblems(parents, requestedPerCohort)
    const cohortRecord: Record<string, unknown> = {
      cohort: cohort + 1,
      parent_count: parentCount,
      parent_sha256: hash(parents),
      requested: requestedPerCohort,
      generated: result.cards.length,
      hypotheses_evaluated: result.hypothesesEvaluated,
      reason: result.reason,
      answer_sample: result.cards.slice(0, 3).map(card => card.answer_tex),
    }
    if (result.cards.length !== requestedPerCohort) {
      failures.push({ ...cohortRecord, failure: 'requested cardinality was not generated' })
      records.push(cohortRecord)
      continue
    }

    let cohortValid = true
    for (const card of result.cards) {
      totalCards++
      statementHashes.add(hash(card.statement_tex))
      if (card.execution_certificate?.registered_composite_used === true) registeredRouteCards++
      const generated = card.execution_certificate?.generated_program as GeneratedProgram
      const program: LinearInvariantProgram = {
        coordinate: 'additive',
        equations: generated.equations,
        goal: generated.goal,
      }
      const replay = executeLinearInvariant(program)
      const exact = replay.status === 'proved' && replay.value === generated.exact_value &&
        verifyLinearInvariantCertificate(program, replay)
      if (exact) exactReplayCards++
      else cohortValid = false

      const ablationPassed = generated.ablations.length === parentCount &&
        generated.ablations.every(ablation => ablation.status !== 'proved')
      if (ablationPassed) allParentAblationsPassed++
      else cohortValid = false

      const counterfactualPassed = generated.counterfactuals.length === parentCount &&
        generated.counterfactuals.every(counterfactual =>
          counterfactual.value_before !== counterfactual.value_after)
      if (counterfactualPassed) allParentCounterfactualsPassed++
      else cohortValid = false
    }

    const mutated = [...parents]
    mutated[parentCount - 1] = parentFor(cohort, parentCount - 1, 1)
    const changed = synthesizeRuntimeLinearProblems(mutated, 1)
    const mutationChanged = changed.cards.length === 1 &&
      changed.cards[0].answer_tex !== result.cards[0].answer_tex
    if (mutationChanged) mutationAnswerChanges++
    else cohortValid = false

    cohortRecord.valid = cohortValid
    cohortRecord.mutated_parent_changes_answer = mutationChanged
    cohortRecord.card_sha256 = result.cards.map(card => hash({
      statement: card.statement_tex,
      answer: card.answer_tex,
      certificate: card.execution_certificate?.generated_program_sha256,
    }))
    if (!cohortValid) failures.push({ ...cohortRecord, failure: 'certificate, causality, or mutation replay failed' })
    records.push(cohortRecord)
  }

  const summary = {
    schema: 'mortra.runtime-linear-generation-benchmark.v1',
    generated_at: new Date().toISOString(),
    claim_scope: 'fresh additive affine constraint systems generated after the implementation was fixed',
    methodology: {
      expected_answers_supplied: false,
      registered_completed_routes_allowed: false,
      coefficients_vary_by_cohort: true,
      parent_count_range: [2, 4],
      whole_parent_ablation_required: true,
      structure_preserving_parent_perturbation_required: true,
      independent_exact_replay_required: true,
    },
    cohort_count: cohortCount,
    requested_per_cohort: requestedPerCohort,
    requested_cards: cohortCount * requestedPerCohort,
    generated_cards: totalCards,
    distinct_statement_count: statementHashes.size,
    exact_replay_cards: exactReplayCards,
    registered_route_cards: registeredRouteCards,
    whole_parent_ablation_cards: allParentAblationsPassed,
    parent_counterfactual_cards: allParentCounterfactualsPassed,
    mutated_cohorts_with_changed_answer: mutationAnswerChanges,
    failed_cohorts: failures.length,
    success_rate: cohortCount === 0 ? 0 : (cohortCount - failures.length) / cohortCount,
  }
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, `${JSON.stringify({ summary, failures, records }, null, 2)}\n`, 'utf8')
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`)
  if (failures.length > 0) process.exitCode = 1
}

main()
