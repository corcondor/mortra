import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import {
  auditCompositionComplexity,
  compositionGenomeFingerprint,
  compositionGenomeMetrics,
} from '../lib/mortra/composition-genome'
import { hasCompleteParentProof } from '../worker/src/autonomous-synthesis'
import { auditEntranceExamPublication } from '../worker/src/entrance-exam-publication-audit'
import { capabilityOrigin } from '../worker/src/execution-certificate'
import { runPublicRuntimeGeneration } from '../worker/src/public-runtime-generation'
import { discoverMirrorForbiddenWordCoordinateGrammars } from '../worker/src/runtime-branching-moment-generation'

const repositoryRoot = resolve(import.meta.dirname, '..')
const outputPath = resolve(
  repositoryRoot,
  process.argv[2] ?? 'artifacts/benchmarks/certified-runtime-forbidden-grammar-generation-20260904.json',
)
const parents = [{
  id: 'unseen-dual-shear-grammar-benchmark',
  statement: String.raw`整数の組に対する写像 \(L(a,b)=(a+b,b)\), \(R(a,b)=(a,a+b)\) を考える。`,
}]
const splitParents = [
  {
    id: 'unseen-left-shear-parent',
    statement: String.raw`整数の組に対する写像 \(L(x,y)=(x+y,y)\) を考える。`,
  },
  {
    id: 'unseen-right-shear-parent',
    statement: String.raw`整数の組に対する写像 \(R(u,v)=(u,u+v)\) を考える。`,
  },
]

function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex')
}

const discovery = discoverMirrorForbiddenWordCoordinateGrammars(3)
const publicResult = runPublicRuntimeGeneration(parents, 4)
const splitPublicResult = runPublicRuntimeGeneration(splitParents, 4)
const generatedCards = publicResult.cards.slice(2)
const rows = generatedCards.map(card => {
  const program = card.execution_certificate?.generated_program as Record<string, unknown> | undefined
  const forbiddenWords = (program?.forbidden_words ?? []) as string[]
  const analysis = discovery.analyses.find(candidate =>
    candidate.forbiddenWords.join(',') === forbiddenWords.join(','))
  const publication = auditEntranceExamPublication(card)
  const genome = card.structure_blueprint.compositionGenome!
  const complexity = auditCompositionComplexity(genome)
  const visual = card.visual_explanation as {
    steps?: Array<{
      morphism?: { label_ja?: string }
      source_state?: { id?: string }
      target_state?: { id?: string }
      diagram?: { version?: number; kind?: string }
    }>
  }
  const visualKinds = new Set(['plane', 'morphism', 'state', 'variation', 'calculus'])
  const renderableVisualSteps = Boolean(visual.steps?.length)
    && visual.steps!.every(step =>
      Boolean(step.morphism?.label_ja)
      && Boolean(step.source_state?.id)
      && Boolean(step.target_state?.id)
      && step.diagram?.version === 1
      && visualKinds.has(step.diagram?.kind ?? ''))
  const checks = {
    analysis_found: Boolean(analysis),
    independent_enumeration_matches: Boolean(analysis)
      && analysis!.samples.every((value, index) => value === analysis!.independentlyEnumeratedSamples[index]),
    card_samples_match_analysis: Boolean(analysis)
      && card.verification.samples.every((value, index) => BigInt(value) === analysis!.samples[index]),
    parent_proof_complete: hasCompleteParentProof(card, parents),
    synthesized_at_runtime: capabilityOrigin(card.execution_certificate) === 'synthesized_proof_program',
    registered_composite_unused: card.execution_certificate?.registered_composite_used === false,
    publication_audit_passed: publication.passed,
    exact_answer_has_no_decimal: !/\d+\.\d+/.test(card.answer_tex),
    cube_root_tex_is_well_formed: /\\sqrt\[3\]/.test(card.answer_tex)
      && !/(^|[^\\])sqrt/.test(card.answer_tex),
    every_proof_stage_has_a_renderable_diagram: renderableVisualSteps
      && visual.steps?.length === card.solution_tex.split(/\n\s*\n/).length,
    deep_composition_audit_passed: complexity.passed,
  }
  return {
    id: card.id,
    family_id: card.family_id,
    forbidden_words: forbiddenWords,
    answer_tex: card.answer_tex,
    statement_sha256: sha256(card.statement_tex),
    solution_sha256: sha256(card.solution_tex),
    generated_program_sha256: card.execution_certificate?.generated_program_sha256,
    composition_fingerprint: compositionGenomeFingerprint(genome),
    composition_metrics: compositionGenomeMetrics(genome),
    first_exact_terms: analysis?.samples.slice(0, 8).map(String) ?? [],
    characteristic_polynomial: analysis?.recurrencePolynomial.map(String) ?? [],
    dominant_factor: analysis?.dominantFactor.map(String) ?? [],
    safe_block_code: analysis?.safeBlockCode ?? null,
    publication_errors: publication.errors,
    checks,
    passed: Object.values(checks).every(Boolean),
  }
})
const fingerprints = rows.map(row => row.composition_fingerprint)
const splitParentRows = splitPublicResult.cards.map(card => ({
  id: card.id,
  family_id: card.family_id,
  parent_ids: card.parent_ids,
  assigned_parent_ids: card.fusion_derivation.assignments.map(item => item.parentId),
  synthesized_law_arity: card.structure_blueprint.synthesizedLaw?.arity ?? null,
  proof_complete: hasCompleteParentProof(card, splitParents),
  capability_origin: capabilityOrigin(card.execution_certificate),
  unresolved: card.unresolved,
  proof_sha256: card.proof_sha256,
}))
const summaryChecks = {
  all_four_length_three_mirror_pairs_evaluated: discovery.hypothesesEvaluated === 4,
  exactly_two_grammars_closed: discovery.analyses.length === 2,
  exactly_two_grammars_rejected_with_reasons: discovery.rejected.length === 2
    && discovery.rejected.every(item => item.reason.length > 0),
  public_gateway_returned_four_cards: publicResult.cards.length === 4,
  two_generated_grammar_cards_published: rows.length === 2,
  generated_grammars_are_structurally_distinct: new Set(fingerprints).size === rows.length,
  every_generated_card_passed: rows.every(row => row.passed),
  public_search_finished: publicResult.state.continuing === false,
  split_parents_returned_four_cards: splitParentRows.length === 4,
  split_parents_are_both_used: splitParentRows.every(row =>
    row.parent_ids.join(',') === splitParents.map(parent => parent.id).join(',')
    && row.assigned_parent_ids.join(',') === splitParents.map(parent => parent.id).join(',')),
  split_parent_bridge_is_binary: splitParentRows.every(row => row.synthesized_law_arity === 2),
  split_parent_proofs_are_complete: splitParentRows.every(row => row.proof_complete),
  split_parent_cards_are_runtime_synthesized: splitParentRows.every(row =>
    row.capability_origin === 'synthesized_proof_program' && row.unresolved === false),
  split_parent_search_finished: splitPublicResult.state.continuing === false,
}
const sourceFiles = [
  'lib/mortra/finite-word-grammar.ts',
  'worker/src/runtime-branching-moment-generation.ts',
  'worker/src/public-runtime-generation.ts',
]
const artifact = {
  schema: 'mortra.runtime-forbidden-grammar-generation.v1',
  generated_at: new Date().toISOString(),
  benchmark_scope: {
    parent_maps: ['L(a,b)=(a+b,b)', 'R(a,b)=(a,a+b)'],
    grammar_search: 'all L/R-exchange-symmetric pairs of forbidden words of length three',
    requested_public_cards: 4,
    split_parent_public_cards: 4,
    completed_problem_templates_consulted: false,
  },
  discovery: {
    hypotheses_evaluated: discovery.hypothesesEvaluated,
    accepted_forbidden_word_sets: discovery.analyses.map(analysis => analysis.forbiddenWords),
    rejected: discovery.rejected,
  },
  generated_cards: rows,
  multi_parent_public_gateway: {
    parents: splitParents,
    cards: splitParentRows,
    continuing: splitPublicResult.state.continuing,
  },
  summary_checks: summaryChecks,
  passed: Object.values(summaryChecks).every(Boolean),
  source_sha256: Object.fromEntries(sourceFiles.map(file => [
    file,
    sha256(readFileSync(resolve(repositoryRoot, file))),
  ])),
}

mkdirSync(dirname(outputPath), { recursive: true })
writeFileSync(outputPath, JSON.stringify(artifact, null, 2) + '\n', 'utf8')
console.log(JSON.stringify({
  output: outputPath,
  passed: artifact.passed,
  hypotheses_evaluated: discovery.hypothesesEvaluated,
  generated_cards: rows.length,
  rejected_grammars: discovery.rejected.length,
}, null, 2))
if (!artifact.passed) process.exitCode = 1
