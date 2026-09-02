/**
 * MORTRA autonomous structural-discovery worker.
 *
 * The worker accepts only MathOS/MORTRA-owned typed search jobs.  Problem
 * generation, verification, and repair are performed by deterministic
 * structure synthesis and certified backends; no external language-model
 * runtime is reachable from this process.
 */

import { createClient } from '@supabase/supabase-js'
import {
  runAutonomousSynthesis,
  type AutonomousSearchState,
} from './autonomous-synthesis'
import type { CertifiedLawRecord } from './primitive-law-inducer'
import {
  sealResearchRound,
  verifyResearchEvidenceEnvelope,
  type ResearchEvidenceEnvelope,
} from './research-evidence-envelope'

const SUPABASE_URL = process.env.SUPABASE_URL!
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error('Required environment variables are missing: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

interface ParentProblem {
  id: string
  statement: string
  answer?: string | null
  solution?: string | null
  inspiration?: string | null
  topic_a: string
  topic_b?: string | null
}

interface LogEntry {
  level: string
  message: string
  ts: string
}

type PreviousResult = {
  searchState?: AutonomousSearchState
  researchEvidence?: Pick<ResearchEvidenceEnvelope, 'evidence_sha256'>
} & Record<string, unknown>

function certifiedLawFromMeta(meta: unknown): CertifiedLawRecord | null {
  try {
    const value = typeof meta === 'string' ? JSON.parse(meta) : meta
    if (!value || typeof value !== 'object') return null
    const blueprint = (value as { structureBlueprint?: { synthesizedLaw?: unknown } }).structureBlueprint
    const law = blueprint?.synthesizedLaw
    if (!law || typeof law !== 'object') return null
    const candidate = law as Partial<CertifiedLawRecord>
    if (typeof candidate.name !== 'string' || typeof candidate.expression !== 'string') return null
    if (!Number.isInteger(candidate.arity)) return null
    if (!Array.isArray(candidate.sources) || !Array.isArray(candidate.preserves) || !Array.isArray(candidate.backend)) return null
    return candidate as CertifiedLawRecord
  } catch {
    return null
  }
}

let logBuffer: LogEntry[] = []

function pushLog(message: string, level = 'info') {
  logBuffer.push({ level, message, ts: new Date().toISOString() })
  console.log(`[${level.toUpperCase()}] ${message}`)
}

async function flushLogs(jobId: string) {
  if (!logBuffer.length) return
  const batch = logBuffer.splice(0)
  const { error } = await supabase.rpc('append_job_logs', { p_job_id: jobId, p_logs: batch })
  if (error) console.error('flushLogs:', error.message)
}

async function saveCards(
  cards: ReturnType<typeof runAutonomousSynthesis>['cards'],
  userId: string | null,
  researchEvidence: ResearchEvidenceEnvelope,
) {
  const { data: latest } = await supabase.from('problems')
    .select('generation').order('generation', { ascending: false }).limit(1).single()
  const generation = ((latest?.generation as number | null) ?? 0) + 1

  for (const card of cards) {
    const { error } = await supabase.from('problems').upsert({
      id: card.id,
      topic_a: card.domain,
      topic_b: card.family_id,
      variation: 0,
      statement: card.statement_tex,
      answer: card.answer_tex,
      difficulty: 'B',
      solution: card.solution_tex,
      inspiration: card.morphism_chain.join(' -> '),
      meta: JSON.stringify({
        generatedBy: 'mortra_parent_conditioned_discovery',
        parentContext: {
          parentIds: card.parent_ids,
          fusionDerivation: card.fusion_derivation,
        },
        structureBlueprint: card.structure_blueprint,
        verification: card.verification,
        executionCertificate: card.execution_certificate,
        researchEvidence: {
          envelopeSha256: researchEvidence.evidence_sha256,
          previousEvidenceSha256: researchEvidence.previous_evidence_sha256,
          replay: researchEvidence.card_replays.find(replay => replay.card_id === card.id) ?? null,
        },
      }),
      surprise: 8,
      minimality: 7,
      connection: 9,
      inevitability: 8,
      diff_cal: 8,
      total: 8,
      generation,
      parent_ids: card.parent_ids,
      source_file: 'mortra_parent_conditioned_discovery',
    }, { onConflict: 'id' })
    if (error) throw new Error(`discovered problem save failed: ${error.message}`)

    await supabase.from('ratings').upsert(
      { user_id: userId ?? 'system', problem_id: card.id, status: 'pending', x_posted: false },
      { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
    )
  }
}

export async function processJob(jobId: string) {
  console.log(`Processing MORTRA job: ${jobId}`)
  logBuffer = []
  const startedAt = new Date().toISOString()

  await supabase.from('generation_jobs').update({
    status: 'processing',
    model: 'mortra-autonomous-structural-search',
    updated_at: startedAt,
  }).eq('id', jobId)

  const flushInterval = setInterval(() => void flushLogs(jobId), 3000)

  try {
    const { data: rawJob, error } = await supabase
      .from('generation_jobs').select('*').eq('id', jobId).single()
    if (error || !rawJob) throw new Error(`job not found: ${error?.message ?? jobId}`)

    const mode = String(rawJob.mode ?? '')
    if (mode !== 'mathos_discovery' && mode !== 'mortra_discovery') {
      throw new Error(`unsupported legacy generation mode: ${mode || '(empty)'}`)
    }

    const parents = Array.isArray(rawJob.parents) ? rawJob.parents as ParentProblem[] : []
    if (parents.length < 1 || parents.some(parent => !parent.id || !parent.statement)) {
      throw new Error('structural discovery requires at least one complete parent problem')
    }

    const count = Math.max(1, Math.min(Number(rawJob.count) || 3, 10))
    const userId = rawJob.user_id as string | null
    const previous = (rawJob.result ?? null) as PreviousResult | null

    await supabase.from('generation_jobs').update({
      result: {
        ...(previous ?? {}),
        searchRuntime: {
          phase: 'executing_round',
          message: '親問題を再liftし、型付き項と複合実行プログラムを列挙しています',
          started_at: startedAt,
        },
      },
      updated_at: startedAt,
    }).eq('id', jobId)

    pushLog(`[lift] ${parents.length} input problem${parents.length === 1 ? '' : 's'} -> typed objects, constraints, and observables`)
    const { data: learnedRows } = await supabase.from('problems')
      .select('meta').eq('source_file', 'mortra_parent_conditioned_discovery').limit(1000)
    const legacyRows = await supabase.from('problems')
      .select('meta').eq('source_file', 'mathos_parent_conditioned_discovery').limit(1000)
    const certifiedLaws = [...new Map([...(learnedRows ?? []), ...(legacyRows.data ?? [])]
      .map(row => certifiedLawFromMeta(row.meta))
      .filter((law): law is CertifiedLawRecord => law !== null)
      .map(law => [`${law.arity}:${law.expression}`, law])).values()]
    pushLog(`[atlas] loaded ${certifiedLaws.length} previously certified dynamic morphisms`)
    await flushLogs(jobId)

    const autonomous = runAutonomousSynthesis(
      parents,
      count,
      previous?.searchState,
      undefined,
      new Date(),
      certifiedLaws,
    )
    const { discovery } = autonomous
    const sealed = sealResearchRound({
      parents,
      cards: autonomous.cards,
      requested: count,
      state: autonomous.state,
      previousEvidenceSha256: previous?.researchEvidence?.evidence_sha256 ?? null,
    })
    const { cards, state: searchState, evidence: researchEvidence } = sealed
    const evidenceErrors = verifyResearchEvidenceEnvelope({
      evidence: researchEvidence,
      parents,
      acceptedCards: cards,
      state: searchState,
    })
    if (evidenceErrors.length) {
      throw new Error(`research evidence replay failed: ${evidenceErrors.join('; ')}`)
    }
    pushLog(`[enumeration] round=${searchState.round}, depth=${searchState.depth}, terms=${searchState.terms_enumerated ?? 0}, executable_goals=${searchState.executable_goals ?? 0}`)
    pushLog(`[induction] tested=${searchState.induction_tested ?? 0}, rejected=${searchState.induction_rejected ?? 0}, certified=${searchState.induced_laws ?? 0}`)
    for (const attempt of autonomous.attempts) {
      pushLog(`[backend:${attempt.applicable ? 'apply' : 'skip'}] ${attempt.strategy}@${attempt.version}: ${attempt.reason}`)
    }
    pushLog(`[evidence] ${researchEvidence.status}; accepted=${researchEvidence.output.accepted_card_count}, rejected=${researchEvidence.output.rejected_card_count}, sha256=${researchEvidence.evidence_sha256}`)

    if (cards.length) {
      await saveCards(cards, userId, researchEvidence)
      const continuingAfterDelivery = searchState.continuing
      const result = {
        engine: 'MORTRA executable parent-conditioned synthesis',
        generated: cards.length,
        discovered: discovery.hypotheses.length,
        requested: count,
        cards,
        searchState,
        researchEvidence,
        searchRuntime: {
          phase: continuingAfterDelivery ? 'waiting_next_round' : 'completed',
          message: continuingAfterDelivery
            ? `検証済み問題を先に保存しました。登録済み経路を実行時合成へ置き換える未実装演算${searchState.execution_obligations?.length ?? 0}件を継続します`
            : '検証済みの複合実行プログラムを保存しました',
          started_at: startedAt,
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
        backgroundResearch: continuingAfterDelivery,
      }
      pushLog(`[verified] ${cards.length}/${count} candidates passed backend, counterexample, and parent-ablation checks`)
      if (continuingAfterDelivery) {
        pushLog(`[continue] delivered verified cards; runtime execution obligations=${searchState.execution_obligations?.length ?? 0}`)
      }
      await flushLogs(jobId)
      await supabase.from('generation_jobs').update({
        status: continuingAfterDelivery ? 'processing' : 'done',
        model: continuingAfterDelivery ? 'mortra-autonomous-structural-search' : 'mortra-executable-discovery',
        result,
        error: null,
        updated_at: new Date().toISOString(),
      }).eq('id', jobId)
      return result
    }

    const result = {
      ...discovery,
      searchState,
      researchEvidence,
      searchRuntime: {
        phase: (searchState.stagnant_rounds ?? 0) >= 3 ? 'stalled_waiting' : 'waiting_next_round',
        message: `ラウンド${searchState.round}を完了しました。深さ${searchState.depth}まで${searchState.states_explored ?? 0}状態を検査し、未閉鎖義務${searchState.frontier.length}件から次の探索を再開します`,
        started_at: startedAt,
        finished_at: new Date().toISOString(),
      },
      strategyAttempts: autonomous.attempts,
      generalization: autonomous.generalization,
      typedEnumeration: autonomous.enumeration,
      backgroundResearch: true,
    }
    pushLog(`[continue] no certified program yet; preserved frontier=${searchState.frontier.length}`)
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: 'processing',
      model: 'mortra-autonomous-structural-search',
      result,
      error: null,
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)
    return result
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    pushLog(`[failed] ${message}`, 'error')
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: 'failed',
      model: 'mortra-autonomous-structural-search',
      error: message,
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)
    throw error
  } finally {
    clearInterval(flushInterval)
  }
}

export function startWorker() {
  const pollMs = Number(process.env.POLL_INTERVAL_MS ?? '3000')
  let busy = false

  async function poll() {
    if (busy) return
    busy = true
    try {
      const { data: job } = await supabase.from('generation_jobs')
        .select('id').eq('status', 'pending').eq('mode', 'mathos_discovery')
        .order('created_at', { ascending: true }).limit(1).single()
      if (job) await processJob(String(job.id))
    } catch (error: unknown) {
      if ((error as { code?: string }).code !== 'PGRST116') console.error('[poll]', error)
    } finally {
      busy = false
    }
  }

  console.log(`MORTRA structural-discovery worker started: poll=${pollMs}ms`)
  void poll()
  setInterval(() => void poll(), pollMs)
  process.on('SIGTERM', () => process.exit(0))
  process.on('SIGINT', () => process.exit(0))
}

if (require.main === module) {
  const jobId = process.env.JOB_ID
  if (jobId) {
    processJob(jobId).then(() => process.exit(0)).catch(error => {
      console.error('Fatal:', error)
      process.exit(1)
    })
  } else {
    startWorker()
  }
}
