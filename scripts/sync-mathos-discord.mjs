import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { createClient } from '@supabase/supabase-js'

const source = new URL(
  '../data/mathos/continuous_verified_problem_batch1.json',
  import.meta.url,
)
const batch = JSON.parse(await readFile(source, 'utf8'))
const poolGeneratedAt = batch.generated_at ?? new Date().toISOString()

const accepted = batch.problems.filter(
  (problem) =>
    problem.accepted &&
    problem.verification?.exact_backend &&
    problem.verification?.independent_check &&
    problem.lift_certificate?.type_checked &&
    problem.novelty?.corpus_novel &&
    problem.curriculum_certificate?.scope ===
      'jp_upper_secondary_math_IA_IIB_IIIC' &&
    problem.curriculum_certificate?.type_checked &&
    problem.curriculum_certificate?.uses_only_school_level_primitives,
)

const hashProblem = (problem) =>
  createHash('sha256')
    .update(
      [
        problem.candidate_id,
        problem.family_id,
        problem.statement_tex,
        problem.answer_tex,
      ].join('\u241f'),
    )
    .digest('hex')

const rows = accepted.map((problem) => {
  const problemHash = hashProblem(problem)
  const shortId = problemHash.slice(0, 10)
  return {
    id: `mathos-${shortId}`,
    topic_a: problem.domain,
    topic_b: problem.family_id,
    variation: 0,
    statement: problem.statement_tex,
    answer: problem.answer_tex,
    difficulty: 'C',
    solution: problem.solution_tex,
    surprise: 8,
    minimality: 7,
    connection: 8,
    inevitability: 8,
    diff_cal: 7,
    total: 7.6,
    inspiration: problem.lift_certificate.morphism_chain.join(' → '),
    meta: JSON.stringify({
      problemHash,
      shortId,
      candidateId: problem.candidate_id,
      familyId: problem.family_id,
      structureKey: problem.structure_key,
      curriculumScope: problem.curriculum_certificate.scope,
      loweringChain: problem.curriculum_certificate.lowering_chain,
      verificationMethod: problem.verification.method,
      maximumSurfaceJaccard: problem.novelty.maximum_surface_jaccard,
      morphismChain: problem.lift_certificate.morphism_chain,
      gates: {
        exactBackend: true,
        independentCheck: true,
        typeChecked: true,
        corpusNovel: true,
      },
      activePool: true,
      poolGeneratedAt,
    }),
    generation: 0,
    parent_ids: [],
    source_file: 'mathos_discord_entrance_v2',
  }
})

const url = process.env.NEXT_PUBLIC_SUPABASE_URL
const serviceKey = process.env.SUPABASE_SERVICE_KEY
if (!url || !serviceKey) {
  throw new Error('NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required')
}

const supabase = createClient(url, serviceKey, {
  auth: { persistSession: false, autoRefreshToken: false },
})

// Keep historical votes for research, but do not keep superseded variants in
// the curation UI. Earlier syncs used candidate IDs as row IDs, so the same
// structure could survive under several IDs even after the pool quotient had
// collapsed it to one representative.
const { data: previousRows, error: previousError } = await supabase
  .from('problems')
  .select('id,meta')
  .eq('source_file', 'mathos_discord_entrance_v2')
if (previousError) throw previousError

// Move the previous snapshot out of the active namespace in one operation.
// The following upsert restores exactly the current representatives. Ratings
// remain attached to archived rows and are still available to research tools.
const { error: archiveError } = await supabase
  .from('problems')
  .update({ source_file: 'mathos_discord_archive' })
  .eq('source_file', 'mathos_discord_entrance_v2')
if (archiveError) throw archiveError

const { error } = await supabase.from('problems').upsert(rows, {
  onConflict: 'id',
})
if (error) throw error

console.log(
  `Synced ${rows.length} verified MathOS problems; archived ${(previousRows ?? []).length} previous rows.`,
)
