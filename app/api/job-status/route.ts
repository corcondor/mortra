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
      .select('id, status, logs, result, error, updated_at')
      .eq('id', jobId)
      .single()

    if (error || !data) {
      return NextResponse.json({ error: 'not found' }, { status: 404 })
    }
    return NextResponse.json(data)
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
