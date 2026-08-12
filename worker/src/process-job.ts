/**
 * MORTRA structural discovery worker.
 *
 * This worker intentionally supports only the owner-approved, external-LLM-free
 * `mathos_discovery` mode. Legacy external-LLM generation modes were removed.
 */

import { createClient } from '@supabase/supabase-js'
import {
  runAutonomousSynthesis,
  type AutonomousSearchState,
} from './autonomous-synthesis'
import type { CertifiedLawRecord } from './primitive-law-inducer'
import type { DiscoveryParent } from './parent-conditioned-discovery'

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required')
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

type LogEntry = {
  level: string
  message: string
  ts: string
}

type DiscoveryJobResult = {
  searchState?: AutonomousSearchState
  [key: string]: unknown
}

let logBuffer: LogEntry[] = []

function pushLog(message: string, level = 'info'): void {
  logBuffer.push({ level, message, ts: new Date().toISOString() })
  console.log(`[${level.toUpperCase()}] ${message}`)
}

async function flushLogs(jobId: string): Promise<void> {
  if (!logBuffer.length) return
  const batch = logBuffer.splice(0)
  const { error } = await supabase.rpc('append_job_logs', {
    p_job_id: jobId,
    p_logs: batch,
  })
  if (error) console.error('flushLogs:', error.message)
}

function certifiedLawFromMeta(meta: unknown): CertifiedLawRecord | null {
  try {
    const value = typeof meta === 'string' ? JSON.parse(meta) : meta
    if (!value || typeof value !== 'object') return null
    const blueprint = (value as { structureBlueprint?: { synthesizedLaw?: unknown } }).structureBlueprint
    const law = blueprint?.synthesizedLaw
    if (!law || typeof law !== 'object') return null

    const candidate = law as Partial<CertifiedLawRecord>
    if (
      typeof candidate.name !== 'string' ||
      typeof candidate.expression !== 'string' ||
      !Number.isInteger(candidate.arity) ||
      !Array.isArray(candidate.sources) ||
      !Array.isArray(candidate.preserves) ||
      !Array.isArray(candidate.backend)
    ) {
      return null
    }
    return candidate as CertifiedLawRecord
  } catch {
    return null
  }
}

async function markFailed(jobId: string, error: unknown): Promise<void> {
  const message = error instanceof Error ? error.message : String(error)
  pushLog(`❌ [致命的エラー] ${message}`, 'error')
  await flushLogs(jobId)
  await supabase
    .from('generation_jobs')
    .update({
      status: 'failed',
      error: message,
      updated_at: new Date().toISOString(),
    })
    .eq('id', jobId)
}

export async function processJob(jobId: string): Promise<void> {
  console.log(`Processing MORTRA discovery job: ${jobId}`)
  logBuffer = []

  const { data: job, error: loadError } = await supabase
    .from('generation_jobs')
    .select('*')
    .eq('id', jobId)
    .single()

  if (loadError || !job) {
    throw new Error(`ジョブが見つかりません: ${loadError?.message ?? jobId}`)
  }

  const mode = String(job.mode ?? '')
  if (mode !== 'mathos_discovery') {
    const message = `Unsupported legacy job mode: ${mode || '(empty)'}. Use /api/mathos-generate.`
    await supabase
      .from('generation_jobs')
      .update({
        status: 'failed',
        model: 'mortra-structural-discovery-no-external-llm',
        error: message,
        updated_at: new Date().toISOString(),
      })
      .eq('id', jobId)
    throw new Error(message)
  }

  const parents = Array.isArray(job.parents) ? (job.parents as DiscoveryParent[]) : []
  if (!parents.length) {
    const message = 'mathos_discovery requires at least one parent problem'
    await supabase
      .from('generation_jobs')
      .update({ status: 'failed', error: message, updated_at: new Date().toISOString() })
      .eq('id', jobId)
    throw new Error(message)
  }

  const count = Math.max(1, Math.min(Number(job.count) || 1, 10))
  const userId = (job.user_id as string | null) ?? null
  const previousResult = (job.result as DiscoveryJobResult | null) ?? null
  const runtimeStartedAt = new Date().toISOString()

  await supabase
    .from('generation_jobs')
    .update({
      status: 'processing',
      model: 'mortra-structural-discovery-no-external-llm',
      error: null,
      result: {
        ...(previousResult ?? {}),
        searchRuntime: {
          phase: 'executing_round',
          message: '親問題を型付き構造へliftし、複合実行プログラムを列挙しています',
          started_at: runtimeStartedAt,
        },
      },
      updated_at: runtimeStartedAt,
    })
    .eq('id', jobId)

  const flushInterval = setInterval(() => {
    void flushLogs(jobId)
  }, 3000)

  try {
    pushLog(`🔎 [未知構造探索] ${parents.length} 個の親問題を演算子・対象・制約へlift`)

    const { data: learnedRows, error: learnedError } = await supabase
      .from('problems')
      .select('meta')
      .eq('source_file', 'mathos_parent_conditioned_discovery')
      .limit(1000)
    if (learnedError) throw new Error(`認証Atlasの読込に失敗: ${learnedError.message}`)

    const learnedMetaRows = (learnedRows ?? []) as Array<{ meta: unknown }>
    const certifiedLaws = [
      ...new Map(
        learnedMetaRows
          .map(row => certifiedLawFromMeta(row.meta))
          .filter((law): law is CertifiedLawRecord => law !== null)
          .map(law => [`${law.arity}:${law.expression}`, law]),
      ).values(),
    ]
    pushLog(`📚 [認証Atlas] 認証済み動的射 ${certifiedLaws.length} 件を読込`)

    const autonomous = runAutonomousSynthesis(
      parents,
      count,
      previousResult?.searchState,
      undefined,
      new Date(),
      certifiedLaws,
    )
    const { discovery, cards, state: searchState } = autonomous

    pushLog(`🧭 [中間命題] ${discovery.hypotheses.length} 個の普遍構成候補を比較`)
    pushLog(
      `⚙️ [型付き項列挙] round=${searchState.round}, depth=${searchState.depth}, ` +
      `terms=${searchState.terms_enumerated ?? 0}, full-goals=${searchState.executable_goals ?? 0}`,
    )
    pushLog(
      `🧪 [原始法則帰納] enumerated=${searchState.induction_enumerated ?? 0}, ` +
      `tested=${searchState.induction_tested ?? 0}, rejected=${searchState.induction_rejected ?? 0}, ` +
      `certified=${searchState.induced_laws ?? 0}`,
    )
    pushLog(
      `🧰 [実行基盤] synthesis=${searchState.induction_engine ?? 'unavailable'}, ` +
      `cvc5=${searchState.cvc5_available ? 'active' : 'fallback'}, ` +
      `egglog=${searchState.egglog_available ? 'active' : 'fallback'}`,
    )

    for (const attempt of autonomous.attempts) {
      pushLog(`${attempt.applicable ? '🔧' : '↪'} [${attempt.strategy}@${attempt.version}] ${attempt.reason}`)
    }

    if (cards.length) {
      const { data: latest, error: generationError } = await supabase
        .from('problems')
        .select('generation')
        .order('generation', { ascending: false })
        .limit(1)
        .single()
      if (generationError && generationError.code !== 'PGRST116') {
        throw new Error(`世代番号の取得に失敗: ${generationError.message}`)
      }
      const generation = ((latest?.generation as number | null) ?? 0) + 1

      for (const card of cards) {
        const { error: saveError } = await supabase
          .from('problems')
          .upsert({
            id: card.id,
            topic_a: card.domain,
            topic_b: card.family_id,
            variation: 0,
            statement: card.statement_tex,
            answer: card.answer_tex,
            difficulty: 'B',
            solution: card.solution_tex,
            inspiration: card.morphism_chain.join(' → '),
            meta: JSON.stringify({
              generatedBy: 'mathos_parent_conditioned_discovery',
              parentContext: {
                parentIds: card.parent_ids,
                fusionDerivation: card.fusion_derivation,
              },
              structureBlueprint: card.structure_blueprint,
              verification: card.verification,
            }),
            surprise: 8,
            minimality: 7,
            connection: 9,
            inevitability: 8,
            diff_cal: 8,
            total: 8,
            generation,
            parent_ids: card.parent_ids,
            source_file: 'mathos_parent_conditioned_discovery',
          }, { onConflict: 'id' })
        if (saveError) throw new Error(`問題保存に失敗: ${saveError.message}`)

        const { error: ratingError } = await supabase
          .from('ratings')
          .upsert(
            {
              user_id: userId ?? 'system',
              problem_id: card.id,
              status: 'pending',
              x_posted: false,
            },
            { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
          )
        if (ratingError) throw new Error(`評価行の保存に失敗: ${ratingError.message}`)
      }

      const result = {
        engine: 'MORTRA executable parent-conditioned synthesis (no external LLM)',
        generated: cards.length,
        discovered: discovery.hypotheses.length,
        requested: count,
        cards,
        searchState,
        searchRuntime: {
          phase: 'completed',
          message: '検証済みの複合実行プログラムを保存しました',
          started_at: runtimeStartedAt,
          finished_at: new Date().toISOString(),
        },
        strategyAttempts: autonomous.attempts,
        generalization: autonomous.generalization,
        typedEnumeration: autonomous.enumeration,
        structures: cards.map(card => ({
          blueprint: card.structure_blueprint,
          status: 'new',
          parentIds: card.parent_ids,
          registeredAt: new Date().toISOString(),
        })),
        errors: [],
        rejectionCounts: {},
      }

      pushLog(`✅ [厳密検証] ${cards.length} 問が実行backend・独立検査・親アブレーションを通過`)
      pushLog(`💾 [保存] ${cards.length} 問を問題DBへ追加`)
      await flushLogs(jobId)
      await supabase
        .from('generation_jobs')
        .update({
          status: 'done',
          model: 'mortra-executable-discovery-no-external-llm',
          result,
          error: null,
          updated_at: new Date().toISOString(),
        })
        .eq('id', jobId)
      return
    }

    if ((searchState.stagnant_rounds ?? 0) > 0) {
      pushLog(
        `⚠ [停滞検出] frontierが${searchState.stagnant_rounds}回連続で不変です。` +
        '未登録の射を捏造せず、型付き列挙とbackend接続だけで探索を継続します。',
        'warn',
      )
    }

    const result = {
      ...discovery,
      searchState,
      searchRuntime: {
        phase: (searchState.stagnant_rounds ?? 0) >= 3
          ? 'stalled_waiting'
          : 'waiting_next_round',
        message: (searchState.stagnant_rounds ?? 0) >= 3
          ? '同じfrontierで停滞中。次ラウンドでは探索深さと状態予算を増やします'
          : '現在のfrontierを保存し、次の探索ラウンドを待っています',
        started_at: runtimeStartedAt,
        finished_at: new Date().toISOString(),
      },
      strategyAttempts: autonomous.attempts,
      generalization: autonomous.generalization,
      typedEnumeration: autonomous.enumeration,
      backgroundResearch: true,
    }

    pushLog(
      `⏳ [探索継続] 実行証明は未完成。frontier=${searchState.frontier.length} を保存し、` +
      `${searchState.next_attempt_at ?? '次回実行時'} に再開`,
    )
    await flushLogs(jobId)
    await supabase
      .from('generation_jobs')
      .update({
        status: 'processing',
        model: 'mortra-autonomous-structural-search-no-external-llm',
        result,
        error: null,
        updated_at: new Date().toISOString(),
      })
      .eq('id', jobId)
  } catch (error) {
    await markFailed(jobId, error)
    throw error
  } finally {
    clearInterval(flushInterval)
    await flushLogs(jobId)
  }
}

export function startWorker(): void {
  const pollMs = Number(process.env.POLL_INTERVAL_MS ?? '3000')
  let busy = false

  async function poll(): Promise<void> {
    if (busy) return
    busy = true
    try {
      const { data: job, error } = await supabase
        .from('generation_jobs')
        .select('id')
        .eq('status', 'pending')
        .eq('mode', 'mathos_discovery')
        .order('created_at', { ascending: true })
        .limit(1)
        .single()
      if (error && error.code !== 'PGRST116') throw error
      if (job) await processJob(String(job.id))
    } catch (error) {
      console.error('[poll]', error)
    } finally {
      busy = false
    }
  }

  console.log(`MORTRA discovery worker started (poll=${pollMs}ms, external LLM disabled)`)
  void poll()
  setInterval(() => void poll(), pollMs)
  process.on('SIGTERM', () => process.exit(0))
  process.on('SIGINT', () => process.exit(0))
}

if (require.main === module) {
  const targetJobId = process.env.JOB_ID
  if (targetJobId) {
    processJob(targetJobId)
      .then(() => {
        console.log('Done.')
        process.exit(0)
      })
      .catch(error => {
        console.error('Fatal:', error)
        process.exit(1)
      })
  } else {
    startWorker()
  }
}
