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
      .select('id, status, mode, count, parents, logs, result, error, updated_at')
      .eq('id', jobId)
      .single()

    if (error || !data) {
      return NextResponse.json({ error: 'not found' }, { status: 404 })
    }
    const state = (data.result as {
      searchState?: { continuing?: boolean; next_attempt_at?: string | null }
    } | null)?.searchState
    const updatedAt = Date.parse(data.updated_at ?? '')
    const due = data.status === 'processing' && state?.continuing === true &&
      (!state.next_attempt_at || Date.parse(state.next_attempt_at) <= Date.now())
    const stale = !Number.isFinite(updatedAt) || Date.now() - updatedAt >= 90_000
    let resumeRequested = false
    let replacementJobId: string | null = null
    if (due && stale) {
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
        }
      }
    }
    const { parents: _parents, mode: _mode, count: _count, ...publicData } = data
    return NextResponse.json({
      ...publicData,
      resume_requested: resumeRequested,
      replacement_job_id: replacementJobId,
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
