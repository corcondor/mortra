import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type ResearchParent = {
  id: string
  statement: string
  answer?: string | null
  solution?: string | null
}

function getAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) throw new Error('Supabase env not set')
  return createClient(url, key)
}

function validParents(value: unknown): ResearchParent[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((candidate, index) => {
    if (!candidate || typeof candidate !== 'object') return []
    const record = candidate as Record<string, unknown>
    const statement = typeof record.statement === 'string' ? record.statement.trim() : ''
    if (!statement) return []
    return [{
      id: typeof record.id === 'string' && record.id.trim()
        ? record.id.trim()
        : `research-parent-${index + 1}`,
      statement,
      answer: typeof record.answer === 'string' ? record.answer : null,
      solution: typeof record.solution === 'string' ? record.solution : null,
    }]
  }).slice(0, 250)
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null) as {
    parents?: unknown
    count?: number
  } | null
  const parents = validParents(body?.parents)
  if (!parents.length) {
    return NextResponse.json({ error: '探索対象の問題文が必要です' }, { status: 400 })
  }
  const count = Math.max(1, Math.min(Number(body?.count) || 1, 10))
  const admin = getAdmin()

  const { data, error } = await admin.functions.invoke('enqueue-generation', {
    body: { parents, mode: 'mathos_discovery', count },
  })
  if (!error && data?.job_id) {
    return NextResponse.json({
      generated: 0,
      requested: count,
      cards: [],
      errors: [],
      discoveryQueued: true,
      discoveryJobId: String(data.job_id),
      engine: 'MORTRA persistent typed research (no LLM)',
      trace: [
        '即時の厳密解答器で閉じなかった義務を保存',
        '型付き項・中間補題・実行可能制約の探索を開始',
        '検証済み解答が得られるまで同じジョブを再開',
      ],
    }, { status: 202 })
  }

  const jobId = crypto.randomUUID()
  const now = new Date().toISOString()
  const { error: insertError } = await admin.from('generation_jobs').insert({
    id: jobId,
    status: 'pending',
    parents,
    mode: 'mathos_discovery',
    count,
    logs: [{
      level: 'info',
      message: '未解決義務を永続研究キューへ保存しました。',
      ts: now,
    }],
    result: {
      engine: 'MORTRA persistent typed research (no LLM)',
      generated: 0,
      requested: count,
      cards: [],
      errors: [],
      backgroundResearch: true,
      searchState: { continuing: true, next_attempt_at: null, frontier: [] },
    },
    error: null,
    model: 'mortra-autonomous-structural-search',
    updated_at: now,
  })
  if (insertError) {
    return NextResponse.json({
      error: `未解決義務を保存できませんでした: ${insertError.message}`,
    }, { status: 503 })
  }
  return NextResponse.json({
    generated: 0,
    requested: count,
    cards: [],
    errors: [],
    discoveryQueued: true,
    discoveryJobId: jobId,
    engine: 'MORTRA scheduled typed research (no LLM)',
    trace: [
      '即時の厳密解答器で閉じなかった義務を保存',
      '定期研究ワーカーが型付き探索を再開',
      '完成した問題文・解答・証明書を同じジョブへ返却',
    ],
  }, { status: 202 })
}
