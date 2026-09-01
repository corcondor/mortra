/**
 * GET /api/job-status?job_id=xxx
 * Realtimeが届かない場合のポーリング用フォールバック。
 * サービスロールキーで generation_jobs を読み取る。
 */
import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

function getAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) throw new Error('Supabase env not set')
  return createClient(url, key)
}

export async function GET(req: NextRequest) {
  const jobId = req.nextUrl.searchParams.get('job_id')
  if (!jobId) {
    return NextResponse.json({ error: 'job_id required' }, { status: 400 })
  }

  try {
    const supabase = getAdmin()
    const { data, error } = await supabase
      .from('generation_jobs')
      .select('id, status, mode, count, parents, logs, result, error, created_at, updated_at')
      .eq('id', jobId)
      .single()

    if (error || !data) {
      return NextResponse.json({ error: 'not found' }, { status: 404 })
    }
    const resultEnvelope = data.result as ({
      searchState?: {
        continuing?: boolean
        next_attempt_at?: string | null
        round?: number
        depth?: number
        terms_enumerated?: number
        executable_goals?: number
        local_expansions?: number
        states_explored?: number
        progress_delta?: number
        induction_enumerated?: number
        induction_tested?: number
        induction_rejected?: number
        induced_laws?: number
        induction_engine?: string
        synthesis_terms_examined?: number
        equivalence_classes?: number
        cvc5_checked?: number
        cvc5_available?: boolean
        egglog_available?: boolean
        frontier?: unknown[]
        stagnant_rounds?: number
        last_progress_at?: string
        synthesized_programs?: unknown[]
        reused_parameterized_morphisms?: number
        primitive_executions?: number
        execution_obligations?: string[]
      }
      searchRuntime?: {
        phase?: string
        message?: string
        started_at?: string
      }
      superseded_by?: string
    } | null)
    let state = resultEnvelope?.searchState
    const runtime = resultEnvelope?.searchRuntime
    let replacementJobId: string | null = resultEnvelope?.superseded_by ?? null
    if (replacementJobId) {
      const { data: replacement } = await supabase
        .from('generation_jobs')
        .select('id')
        .eq('id', replacementJobId)
        .maybeSingle()
      if (!replacement) {
        const rawResult = data.result && typeof data.result === 'object'
          ? data.result as Record<string, unknown>
          : {}
        const repairedState = {
          ...(state ?? {}),
          continuing: true,
          next_attempt_at: null,
        }
        const { superseded_by: _missingSuccessor, ...repairableResult } = rawResult
        data.result = { ...repairableResult, searchState: repairedState }
        state = repairedState
        replacementJobId = null
        await supabase.from('generation_jobs').update({ result: data.result }).eq('id', jobId)
      }
    }
    const now = Date.now()
    const updatedAt = Date.parse(data.updated_at ?? '')
    const createdAt = Date.parse(data.created_at ?? '')
    const nextAttemptAt = state?.next_attempt_at ? Date.parse(state.next_attempt_at) : Number.NaN
    const due = data.status === 'processing' && state?.continuing === true &&
      (!Number.isFinite(nextAttemptAt) || nextAttemptAt <= now)
    const waitingForNextRound = data.status === 'processing' && state?.continuing === true &&
      Number.isFinite(nextAttemptAt) && nextAttemptAt > now
    const secondsSinceUpdate = Number.isFinite(updatedAt) ? Math.max(0, Math.floor((now - updatedAt) / 1000)) : null
    const secondsUntilNextRound = waitingForNextRound ? Math.max(0, Math.ceil((nextAttemptAt - now) / 1000)) : 0
    const stale = secondsSinceUpdate === null || secondsSinceUpdate >= 90
    let resumeRequested = false
    if (due && stale && !replacementJobId) {
      const { data: resumeData, error: resumeError } = await supabase.functions.invoke('enqueue-generation', {
        body: { resume_job_id: jobId },
      })
      resumeRequested = !resumeError && resumeData?.resumed === true
      // Backward-compatible path until the resume-aware Edge Function is deployed:
      // create a dispatched successor, then transplant the exact search state.
      if (!resumeRequested) {
        await supabase.from('generation_jobs').update({ updated_at: new Date().toISOString() }).eq('id', jobId)
        const { data: successor, error: successorError } = await supabase.functions.invoke('enqueue-generation', {
          body: {
            parents: data.parents,
            mode: 'mathos_discovery',
            count: data.count,
          },
        })
        if (!successorError && successor?.job_id) {
          replacementJobId = String(successor.job_id)
          await supabase.from('generation_jobs').update({
            result: data.result,
            updated_at: new Date().toISOString(),
          }).eq('id', replacementJobId)
          const oldResult = (data.result && typeof data.result === 'object')
            ? data.result as Record<string, unknown>
            : {}
          const oldState = (oldResult.searchState && typeof oldResult.searchState === 'object')
            ? oldResult.searchState as Record<string, unknown>
            : {}
          await supabase.from('generation_jobs').update({
            result: {
              ...oldResult,
              superseded_by: replacementJobId,
              searchState: { ...oldState, continuing: false, next_attempt_at: null },
            },
            updated_at: new Date().toISOString(),
          }).eq('id', jobId)
          const { data: visibleSuccessor } = await supabase
            .from('generation_jobs')
            .select('id')
            .eq('id', replacementJobId)
            .maybeSingle()
          // The Edge Function may return before the inserted row is visible to this
          // request. Keep polling the current job until the successor can be read.
          if (!visibleSuccessor) replacementJobId = null
        }
      }
    }
    const compactSearchState = state ? {
      continuing: state.continuing,
      next_attempt_at: state.next_attempt_at,
      round: state.round,
      depth: state.depth,
      terms_enumerated: state.terms_enumerated,
      executable_goals: state.executable_goals,
      states_explored: state.states_explored,
      progress_delta: state.progress_delta,
      frontier: state.frontier?.slice(0, 12),
      stagnant_rounds: state.stagnant_rounds,
      last_progress_at: state.last_progress_at,
    } : undefined
    const rawPublicResult = data.result && typeof data.result === 'object'
      ? data.result as Record<string, unknown>
      : null
    const publicResult = rawPublicResult ? (() => {
      const {
        searchState: _fullSearchState,
        hypotheses: _fullHypotheses,
        typedEnumeration: _fullTypedEnumeration,
        ...summary
      } = rawPublicResult
      const typedEnumeration = _fullTypedEnumeration && typeof _fullTypedEnumeration === 'object'
        ? _fullTypedEnumeration as {
            goals?: unknown[]
            terms?: unknown[]
            frontier?: unknown[]
            exhausted?: boolean
            statesExplored?: number
          }
        : null
      return {
        ...summary,
        searchState: compactSearchState,
        hypothesis_count: Array.isArray(_fullHypotheses) ? _fullHypotheses.length : 0,
        typedEnumeration: typedEnumeration ? {
          goals: typedEnumeration.goals?.slice(0, 12) ?? [],
          term_count: typedEnumeration.terms?.length ?? 0,
          frontier: typedEnumeration.frontier?.slice(0, 12) ?? [],
          frontier_count: typedEnumeration.frontier?.length ?? 0,
          exhausted: typedEnumeration.exhausted ?? false,
          statesExplored: typedEnumeration.statesExplored ?? 0,
        } : undefined,
      }
    })() : null
    const { parents: _parents, mode: _mode, count: _count, result: _result, ...publicData } = data
    return NextResponse.json({
      ...publicData,
      result: publicResult,
      telemetry: {
        server_time: new Date(now).toISOString(),
        elapsed_seconds: Number.isFinite(createdAt) ? Math.max(0, Math.floor((now - createdAt) / 1000)) : null,
        seconds_since_update: secondsSinceUpdate,
        seconds_until_next_round: secondsUntilNextRound,
        worker_active: data.status === 'processing' && !waitingForNextRound && !stale,
        waiting_for_next_round: waitingForNextRound,
        due_for_resume: due,
        stalled: (state?.stagnant_rounds ?? 0) >= 3 && (state?.executable_goals ?? 0) === 0,
        runtime_phase: runtime?.phase ?? null,
        runtime_message: runtime?.message ?? null,
        runtime_started_at: runtime?.started_at ?? null,
        round: state?.round ?? 0,
        depth: state?.depth ?? 0,
        terms_enumerated: state?.terms_enumerated ?? 0,
        executable_goals: state?.executable_goals ?? 0,
        local_expansions: state?.local_expansions ?? 0,
        states_explored: state?.states_explored ?? 0,
        progress_delta: state?.progress_delta ?? 0,
        induction_enumerated: state?.induction_enumerated ?? 0,
        induction_tested: state?.induction_tested ?? 0,
        induction_rejected: state?.induction_rejected ?? 0,
        induced_laws: state?.induced_laws ?? 0,
        induction_engine: state?.induction_engine ?? 'unavailable',
        synthesis_terms_examined: state?.synthesis_terms_examined ?? 0,
        equivalence_classes: state?.equivalence_classes ?? 0,
        cvc5_checked: state?.cvc5_checked ?? 0,
        cvc5_available: state?.cvc5_available ?? false,
        egglog_available: state?.egglog_available ?? false,
        frontier_count: state?.frontier?.length ?? 0,
        stagnant_rounds: state?.stagnant_rounds ?? 0,
        last_progress_at: state?.last_progress_at ?? null,
        synthesized_programs: state?.synthesized_programs?.length ?? 0,
        reused_parameterized_morphisms: state?.reused_parameterized_morphisms ?? 0,
        primitive_executions: state?.primitive_executions ?? 0,
        execution_obligations: state?.execution_obligations?.length ?? 0,
      },
      resume_requested: resumeRequested,
      replacement_job_id: replacementJobId,
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
