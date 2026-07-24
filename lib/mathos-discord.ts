import { createHash } from 'node:crypto'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'
import { supabaseAdmin } from '@/lib/supabase-admin'

const SOURCE_FILE = 'mathos_discord_verified'
const EVENT_MODE = 'discord_sakumon'
const CLAIM_MODE = 'discord_sakumon_claim'

type BatchProblem = {
  accepted: boolean
  answer_tex: string
  candidate_id: string
  domain: string
  family_id: string
  statement_tex: string
  solution_tex: string
  lift_certificate: {
    type_checked: boolean
    morphism_chain?: string[]
  }
  novelty: {
    corpus_novel: boolean
    maximum_surface_jaccard?: number
  }
  verification: {
    exact_backend: boolean
    independent_check: boolean
    method: string
  }
}

export type MathOSProblem = {
  problemHash: string
  shortId: string
  candidateId: string
  domain: string
  familyId: string
  statementTex: string
  answerTex: string
  solutionTex: string
  verificationMethod: string
  maximumSurfaceJaccard?: number
  morphismChain: string[]
}

export type DeliveryInput = {
  interactionId: string
  userId: string
  channelId?: string
  guildId?: string
  domain?: string
}

type ProblemRow = {
  id: string
  topic_a: string
  topic_b: string | null
  statement: string
  answer: string | null
  solution: string | null
  meta: string | null
}

type JobResult = {
  problem_hash?: string
  short_id?: string
  problem_id?: string
}

type JobRow = {
  result: JobResult | null
}

const DOMAIN_ALIASES: Record<string, string[]> = {
  algebra: ['algebra', '代数', '方程式', '多項式'],
  geometry: [
    'geometry',
    '幾何',
    '図形',
    'algebraic_geometry',
    'complex_geometry',
    'analytic_geometry',
  ],
  number_theory: [
    'number_theory',
    'linear_algebra_number_theory',
    '整数',
    '数論',
    '素数',
    '合同',
  ],
  probability: ['probability', '確率', '期待値'],
  analysis: [
    'analysis',
    'real_analysis',
    'combinatorics_analysis',
    '解析',
    '微分',
    '積分',
    '極限',
  ],
  linear_algebra: [
    'linear_algebra',
    'linear_algebra_number_theory',
    '線形代数',
    '行列',
  ],
  combinatorics: ['combinatorics', 'combinatorics_analysis', '組合せ', '数え上げ'],
  complex: ['complex', 'complex_geometry', '複素数'],
}

function hashProblem(problem: BatchProblem): string {
  return createHash('sha256')
    .update(
      [
        problem.candidate_id,
        problem.family_id,
        problem.statement_tex,
        problem.answer_tex,
      ].join('\u241f'),
    )
    .digest('hex')
}

function accepted(problem: BatchProblem): boolean {
  return Boolean(
    problem.accepted &&
      problem.verification.exact_backend &&
      problem.verification.independent_check &&
      problem.lift_certificate.type_checked &&
      problem.novelty.corpus_novel,
  )
}

function fromBatch(problem: BatchProblem): MathOSProblem {
  const problemHash = hashProblem(problem)
  return {
    problemHash,
    shortId: problemHash.slice(0, 10),
    candidateId: problem.candidate_id,
    domain: problem.domain,
    familyId: problem.family_id,
    statementTex: problem.statement_tex,
    answerTex: problem.answer_tex,
    solutionTex: problem.solution_tex,
    verificationMethod: problem.verification.method,
    maximumSurfaceJaccard: problem.novelty.maximum_surface_jaccard,
    morphismChain: problem.lift_certificate.morphism_chain ?? [],
  }
}

export const verifiedMathOSProblems = (
  verifiedBatch.problems as BatchProblem[]
)
  .filter(accepted)
  .map(fromBatch)

export function canonicalDomain(input?: string): string | undefined {
  if (!input) return undefined
  const normalized = input.trim().toLowerCase()
  if (!normalized || normalized === 'おまかせ' || normalized === 'any') {
    return undefined
  }

  for (const [canonical, aliases] of Object.entries(DOMAIN_ALIASES)) {
    if (
      canonical === normalized ||
      aliases.some((alias) => alias.toLowerCase() === normalized)
    ) {
      return canonical
    }
  }
  return normalized
}

export function domainMatches(problemDomain: string, requested?: string): boolean {
  const canonical = canonicalDomain(requested)
  if (!canonical) return true
  const aliases = DOMAIN_ALIASES[canonical] ?? [canonical]
  return aliases.some((alias) => alias.toLowerCase() === problemDomain.toLowerCase())
}

function parseProblemRow(row: ProblemRow): MathOSProblem | null {
  try {
    const meta = JSON.parse(row.meta ?? '{}') as Partial<MathOSProblem>
    if (!meta.problemHash || !meta.shortId || !meta.candidateId) return null
    return {
      problemHash: meta.problemHash,
      shortId: meta.shortId,
      candidateId: meta.candidateId,
      domain: row.topic_a,
      familyId: row.topic_b ?? meta.familyId ?? 'unknown',
      statementTex: row.statement,
      answerTex: row.answer ?? '',
      solutionTex: row.solution ?? '',
      verificationMethod: meta.verificationMethod ?? 'unknown',
      maximumSurfaceJaccard: meta.maximumSurfaceJaccard,
      morphismChain: meta.morphismChain ?? [],
    }
  } catch {
    return null
  }
}

async function loadPool(): Promise<MathOSProblem[]> {
  const { data, error } = await supabaseAdmin
    .from('problems')
    .select('id,topic_a,topic_b,statement,answer,solution,meta')
    .eq('source_file', SOURCE_FILE)

  if (error) throw new Error(`MathOS DB pool: ${error.message}`)
  const parsed = ((data ?? []) as ProblemRow[])
    .map(parseProblemRow)
    .filter((problem): problem is MathOSProblem => problem !== null)
  return parsed.length > 0 ? parsed : verifiedMathOSProblems
}

async function replayedDelivery(
  interactionId: string,
): Promise<MathOSProblem | null> {
  const { data, error } = await supabaseAdmin
    .from('generation_jobs')
    .select('result')
    .eq('id', `discord-event:${interactionId}`)
    .maybeSingle()

  if (error) throw new Error(`MathOS replay lookup: ${error.message}`)
  const result = (data as JobRow | null)?.result
  if (!result?.problem_hash) return null
  const pool = await loadPool()
  return pool.find((problem) => problem.problemHash === result.problem_hash) ?? null
}

async function claimCandidate(
  problem: MathOSProblem,
  input: DeliveryInput,
): Promise<boolean> {
  const now = new Date().toISOString()
  const { error } = await supabaseAdmin.from('generation_jobs').insert({
    id: `discord-claim:${problem.problemHash}`,
    status: 'done',
    user_id: input.userId,
    parents: {
      source: 'discord_interactions',
      event_id: input.interactionId,
      channel_id: input.channelId ?? null,
      guild_id: input.guildId ?? null,
    },
    mode: CLAIM_MODE,
    count: 1,
    result: {
      problem_hash: problem.problemHash,
      short_id: problem.shortId,
      problem_id: `mathos-${problem.shortId}`,
    },
    model: 'MathOS verified pool',
    updated_at: now,
  })

  if (!error) return true
  return error.code !== '23505'
    ? Promise.reject(new Error(`MathOS candidate claim: ${error.message}`))
    : false
}

async function recordEvent(
  problem: MathOSProblem,
  input: DeliveryInput,
): Promise<void> {
  const now = new Date().toISOString()
  const { error } = await supabaseAdmin.from('generation_jobs').insert({
    id: `discord-event:${input.interactionId}`,
    status: 'done',
    user_id: input.userId,
    parents: {
      source: 'discord_interactions',
      domain: canonicalDomain(input.domain) ?? null,
      channel_id: input.channelId ?? null,
      guild_id: input.guildId ?? null,
    },
    mode: EVENT_MODE,
    count: 1,
    result: {
      problem_hash: problem.problemHash,
      short_id: problem.shortId,
      problem_id: `mathos-${problem.shortId}`,
    },
    model: 'MathOS verified pool',
    updated_at: now,
  })

  if (error && error.code !== '23505') {
    await supabaseAdmin
      .from('generation_jobs')
      .delete()
      .eq('id', `discord-claim:${problem.problemHash}`)
    throw new Error(`MathOS event record: ${error.message}`)
  }
}

function rotateForInteraction(
  problems: MathOSProblem[],
  interactionId: string,
): MathOSProblem[] {
  if (problems.length < 2) return problems
  const offset =
    Number.parseInt(
      createHash('sha256').update(interactionId).digest('hex').slice(0, 8),
      16,
    ) % problems.length
  return [...problems.slice(offset), ...problems.slice(0, offset)]
}

export async function deliverMathOSProblem(
  input: DeliveryInput,
): Promise<MathOSProblem> {
  try {
    const replay = await replayedDelivery(input.interactionId)
    if (replay) return replay

    const candidates = rotateForInteraction(
      (await loadPool()).filter((problem) =>
        domainMatches(problem.domain, input.domain),
      ),
      input.interactionId,
    )

    for (const candidate of candidates) {
      if (!(await claimCandidate(candidate, input))) continue
      await recordEvent(candidate, input)
      return candidate
    }

    throw new Error('この条件の検証済み未配信問題がありません。')
  } catch (error) {
    const fallback = rotateForInteraction(
      verifiedMathOSProblems.filter((problem) =>
        domainMatches(problem.domain, input.domain),
      ),
      `${input.userId}:${input.interactionId}`,
    )[0]
    if (fallback) return fallback
    throw error
  }
}

export async function findMathOSSolution(
  shortId: string,
): Promise<MathOSProblem | null> {
  const normalized = shortId.trim().toLowerCase()
  if (!/^[0-9a-f]{10}$/.test(normalized)) return null
  const pool = await loadPool().catch(() => verifiedMathOSProblems)
  return pool.find((problem) => problem.shortId === normalized) ?? null
}

export async function mathOSDiscordStats() {
  try {
    const [
      { count: poolCount, error: poolError },
      { count: claims, error: claimError },
    ] = await Promise.all([
      supabaseAdmin
        .from('problems')
        .select('*', { count: 'exact', head: true })
        .eq('source_file', SOURCE_FILE),
      supabaseAdmin
        .from('generation_jobs')
        .select('*', { count: 'exact', head: true })
        .eq('mode', CLAIM_MODE),
    ])

    if (poolError) throw new Error(`MathOS pool stats: ${poolError.message}`)
    if (claimError) throw new Error(`MathOS delivery stats: ${claimError.message}`)
    const verifiedPool = poolCount ?? verifiedMathOSProblems.length
    const delivered = claims ?? 0
    return {
      verifiedPool,
      delivered,
      remaining: Math.max(verifiedPool - delivered, 0),
      persistent: true,
    }
  } catch {
    return {
      verifiedPool: verifiedMathOSProblems.length,
      delivered: 0,
      remaining: verifiedMathOSProblems.length,
      persistent: false,
    }
  }
}

export function problemEmbed(problem: MathOSProblem) {
  const similarity =
    problem.maximumSurfaceJaccard === undefined
      ? '記録なし'
      : problem.maximumSurfaceJaccard.toFixed(4)
  return {
    title: `MathOS 新作問題 #${problem.shortId}`,
    description: problem.statementTex.slice(0, 4096),
    color: 0x2563eb,
    fields: [
      { name: '分野', value: problem.domain.slice(0, 1024), inline: true },
      {
        name: '構造族',
        value: `\`${problem.familyId.slice(0, 900)}\``,
        inline: false,
      },
      {
        name: '検証',
        value: `\`${problem.verificationMethod}\`\n既存集合との最大表層類似度: \`${similarity}\``,
        inline: false,
      },
    ],
    footer: { text: '型検査・厳密計算・独立検証・新規性検査を通過' },
  }
}

export function solutionEmbed(problem: MathOSProblem) {
  return {
    title: `MathOS 解答 #${problem.shortId}`,
    description: `**答**\n${problem.answerTex}`.slice(0, 4096),
    color: 0x059669,
    fields: [
      {
        name: '解法概略',
        value: (problem.solutionTex || '解法記録なし').slice(0, 1024),
        inline: false,
      },
      {
        name: '射の合成',
        value: (problem.morphismChain.join(' → ') || '記録なし').slice(0, 1024),
        inline: false,
      },
    ],
    footer: { text: `構造族: ${problem.familyId}` },
  }
}

// Discord のメッセージコンポーネント: 1〜5 の評価ボタン + 解答ボタン。
// 人間が問題を直接見た評価を集め、作問器の改良フィードバックにする。
export function mathosProblemComponents(shortId: string) {
  return [
    {
      type: 1,
      components: [1, 2, 3, 4, 5].map((n) => ({
        type: 2,
        style: n <= 2 ? 4 : n === 3 ? 2 : 3,
        label: `${n}`,
        custom_id: `mathos_rate:${shortId}:${n}`,
      })),
    },
    {
      type: 1,
      components: [
        {
          type: 2,
          style: 2,
          label: '解答を見る',
          custom_id: `mathos_answer:${shortId}`,
        },
      ],
    },
  ]
}

export async function recordDiscordRating(
  shortId: string,
  rating: number,
  userId: string,
): Promise<void> {
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    throw new Error('評価は1〜5で指定してください。')
  }
  const now = new Date().toISOString()
  // (user, problem) ごとに1件。付け直しは上書き。
  const { error } = await supabaseAdmin.from('generation_jobs').upsert(
    {
      id: `discord-rating:${shortId}:${userId}`,
      status: 'done',
      user_id: userId,
      mode: 'discord_rating',
      count: 1,
      result: { short_id: shortId, rating, rated_at: now },
      model: 'human_feedback',
      updated_at: now,
    },
    { onConflict: 'id' },
  )
  if (error) throw new Error(`MathOS rating: ${error.message}`)
}

export async function mathOSRatingSummary(shortId: string) {
  const { data, error } = await supabaseAdmin
    .from('generation_jobs')
    .select('result')
    .eq('mode', 'discord_rating')
    .like('id', `discord-rating:${shortId}:%`)
  if (error) throw new Error(`MathOS rating summary: ${error.message}`)
  const ratings = ((data ?? []) as { result: { rating?: number } | null }[])
    .map((row) => Number(row.result?.rating))
    .filter((value) => Number.isFinite(value))
  const count = ratings.length
  const average = count > 0 ? ratings.reduce((a, b) => a + b, 0) / count : null
  return { count, average }
}
