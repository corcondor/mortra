import { createHash } from 'node:crypto'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'
import { supabaseAdmin } from '@/lib/supabase-admin'
import {
  canonicalDomain,
  domainMatches,
  orderForInteraction,
  structureKeyFromRecord,
} from '@/lib/mathos-selection'

export { canonicalDomain } from '@/lib/mathos-selection'

const EVENT_MODE = 'discord_sakumon'
const CLAIM_MODE = 'discord_sakumon_structure_claim_v2'

type BatchProblem = {
  accepted: boolean
  answer_tex: string
  candidate_id: string
  domain: string
  family_id: string
  structure_key?: string
  statement_tex: string
  solution_tex: string
  lift_certificate: {
    type_checked: boolean
    morphism_chain?: string[]
    constraint_skeleton?: unknown
    query_signature?: unknown
  }
  curriculum_certificate: {
    scope: string
    type_checked: boolean
    lowering_chain: string[]
    uses_only_school_level_primitives: boolean
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
  structureKey: string
  curriculumScope: string
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

type JobResult = {
  problem_hash?: string
  short_id?: string
  problem_id?: string
}

type JobRow = {
  result: JobResult | null
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
      problem.novelty.corpus_novel &&
      problem.curriculum_certificate?.scope ===
        'jp_upper_secondary_math_IA_IIB_IIIC' &&
      problem.curriculum_certificate.type_checked &&
      problem.curriculum_certificate.uses_only_school_level_primitives &&
      problem.curriculum_certificate.lowering_chain.length > 0,
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
    structureKey: structureKeyFromRecord(problem),
    curriculumScope: problem.curriculum_certificate.scope,
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

async function loadPool(): Promise<MathOSProblem[]> {
  // The certified bundle is the delivery authority. Reading the large problems
  // table here made every slash command depend on a slow full-table filter.
  return verifiedMathOSProblems
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
  const claimId = structureClaimId(input.userId, problem.structureKey)
  const { error } = await supabaseAdmin.from('generation_jobs').insert({
    id: claimId,
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
      structure_key: problem.structureKey,
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

function structureClaimId(userId: string, structureKey: string): string {
  const digest = createHash('sha256')
    .update(`${userId}:${structureKey}`)
    .digest('hex')
  return `discord-structure-claim:${digest}`
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
      structure_key: problem.structureKey,
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
      .eq('id', structureClaimId(input.userId, problem.structureKey))
    throw new Error(`MathOS event record: ${error.message}`)
  }
}

export async function deliverMathOSProblem(
  input: DeliveryInput,
): Promise<MathOSProblem> {
  const replay = await replayedDelivery(input.interactionId)
  if (replay) return replay

  const candidates = orderForInteraction(
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

  throw new Error(
    'この条件には、まだ配信していない別構造の問題がありません。',
  )
}

export async function findMathOSSolution(
  shortId: string,
): Promise<MathOSProblem | null> {
  const normalized = shortId.trim().toLowerCase()
  if (!/^[0-9a-f]{10}$/.test(normalized)) return null
  const pool = await loadPool().catch(() => verifiedMathOSProblems)
  return pool.find((problem) => problem.shortId === normalized) ?? null
}

export async function mathOSDiscordStats(userId: string) {
  try {
    const [pool, { count: claims, error: claimError }] = await Promise.all([
      loadPool(),
      supabaseAdmin
        .from('generation_jobs')
        .select('*', { count: 'exact', head: true })
        .eq('mode', CLAIM_MODE)
        .eq('user_id', userId),
    ])

    if (claimError) throw new Error(`MathOS delivery stats: ${claimError.message}`)
    // 配信数ではなく、構造署名で商を取った受験数学プールを数える。
    const verifiedPool = pool.length
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
      { name: '範囲', value: '大学受験数学', inline: true },
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
      {
        name: '評価してください',
        value:
          '**難**n = 難易度(1易→5難)、**新**n = 新規性/既視感(1見たことある→5新規)。' +
          '両方タップで作問器の改良に使います。',
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

// Discord のメッセージコンポーネント: 2軸(難易度・新規性) の 1〜5 評価 + 解答。
// 難易度=解くのが難しいか、新規性=見たことがあるか(既視感)。人間の評価を集める。
export function mathosProblemComponents(shortId: string) {
  return [
    {
      type: 1,
      components: [1, 2, 3, 4, 5].map((n) => ({
        type: 2,
        style: n <= 2 ? 4 : n === 3 ? 2 : 3,
        label: `難${n}`,
        custom_id: `mathos_rate:${shortId}:diff:${n}`,
      })),
    },
    {
      type: 1,
      components: [1, 2, 3, 4, 5].map((n) => ({
        type: 2,
        style: n <= 2 ? 4 : n === 3 ? 2 : 3,
        label: `新${n}`,
        custom_id: `mathos_rate:${shortId}:nov:${n}`,
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

const RATING_DIMENSIONS: Record<string, string> = {
  diff: 'difficulty',
  nov: 'novelty',
}

export async function recordDiscordRating(
  shortId: string,
  dimension: string,
  rating: number,
  userId: string,
): Promise<void> {
  const dim = RATING_DIMENSIONS[dimension]
  if (!dim) throw new Error('評価軸が不正です。')
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    throw new Error('評価は1〜5で指定してください。')
  }
  const now = new Date().toISOString()
  // (user, problem, 軸) ごとに1件。付け直しは上書き。
  const { error } = await supabaseAdmin.from('generation_jobs').upsert(
    {
      id: `discord-rating:${shortId}:${dim}:${userId}`,
      status: 'done',
      user_id: userId,
      parents: {
        source: 'discord_rating',
        short_id: shortId,
        dimension: dim,
        rating,
      },
      mode: 'discord_rating',
      count: 1,
      result: { short_id: shortId, dimension: dim, rating, rated_at: now },
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

export function helpEmbed() {
  return {
    title: 'CorcondorAI / MathOS コマンド',
    description:
      'DMとCorcondorAI導入済みサーバーの両方で使えます。' +
      'スラッシュコマンドはBotのオンライン表示に依存しません。',
    color: 0x7c3aed,
    fields: [
      {
        name: '/sakumon [domain]',
        value:
          '大学受験範囲の検証済み問題を、構造単位でランダムに1問表示します。' +
          '同じ構造の数値違いは繰り返しません。分野は省略可能です。\n' +
          '例: `/sakumon domain:整数・数論`',
        inline: false,
      },
      {
        name: '/mathos_answer problem_id',
        value:
          '問題に表示された10文字IDから解答と射の合成を表示します。' +
          '問題下の「解答を見る」ボタンでも開けます。',
        inline: false,
      },
      {
        name: '/mathos_status',
        value:
          'あなた向けの検証済み構造、配信済み構造、未配信構造の件数を表示します。',
        inline: false,
      },
      {
        name: '/help',
        value: 'このコマンド一覧を表示します。',
        inline: false,
      },
    ],
    footer: {
      text:
        '自由文のDM・メンション返信にはGateway版CorcondorAIの稼働が必要です。',
    },
  }
}
