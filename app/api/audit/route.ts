import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/** 問題プールの純度監査（削除はしない・集計のみ） */
export async function GET() {
  const { data, error } = await supabaseAdmin
    .from('problems')
    .select('id,statement,answer,solution,total,source_file,meta')
    .limit(6000)
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  const rows = (data ?? []) as {
    id: string
    statement: string | null
    answer: string | null
    solution: string | null
    total: number | null
    source_file: string | null
    meta: string | null
  }[]

  const bySource: Record<string, number> = {}
  let verified = 0
  let noAnswer = 0
  let noStatement = 0
  let tooShort = 0
  let dupStatement = 0
  const seen = new Set<string>()

  for (const r of rows) {
    const src = r.source_file ?? '(none)'
    bySource[src] = (bySource[src] ?? 0) + 1

    let isVerified = false
    try {
      const m = r.meta ? JSON.parse(r.meta) : null
      isVerified = Boolean(
        m?.verificationMethod || m?.gates || m?.generatedBy === 'mathos_live',
      )
    } catch {
      /* meta が壊れている */
    }
    if (isVerified) verified++

    if (!r.statement || !r.statement.trim()) {
      noStatement++
    } else {
      const key = r.statement.replace(/\s+/g, '').toLowerCase()
      if (seen.has(key)) dupStatement++
      else seen.add(key)
      if (r.statement.replace(/\s+/g, '').length < 30) tooShort++
    }
    if (!r.answer || !r.answer.trim()) noAnswer++
  }

  return NextResponse.json({
    total: rows.length,
    verified_by_mathos: verified,
    unverified: rows.length - verified,
    problems: { noStatement, noAnswer, tooShort, duplicateStatement: dupStatement },
    bySource,
    note: 'これは集計のみ。削除は行っていない。',
  })
}
