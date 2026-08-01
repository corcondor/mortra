import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function POST(req: NextRequest) {
  // ── ユーザー認証 ──────────────────────────────────────────────────────
  const authHeader = req.headers.get('Authorization')
  const token = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null

  let userId: string | null = null
  if (token) {
    const { data } = await supabaseAdmin.auth.getUser(token)
    userId = data.user?.id ?? null
  }

  const { problem_id, status, feedback_reasons } = await req.json()
  if (!problem_id || !status) {
    return NextResponse.json({ error: 'missing fields' }, { status: 400 })
  }

  const feedbackReasons = Array.isArray(feedback_reasons)
    ? feedback_reasons.filter((reason: unknown): reason is string => typeof reason === 'string').slice(0, 8)
    : null

  const buildPayload = async (ratingUserId: string | null) => {
    let note: string | undefined
    if (feedbackReasons) {
      const existingQuery = supabaseAdmin
        .from('ratings')
        .select('note')
        .eq('problem_id', problem_id)
      const { data: existing } = ratingUserId
        ? await existingQuery.eq('user_id', ratingUserId).maybeSingle()
        : await existingQuery.is('user_id', null).maybeSingle()
      let parsed: Record<string, unknown> = {}
      try {
        parsed = existing?.note ? JSON.parse(existing.note) as Record<string, unknown> : {}
      } catch {
        if (existing?.note) parsed = { legacy_note: existing.note }
      }
      note = JSON.stringify({
        ...parsed,
        curation_feedback: {
          reasons: feedbackReasons,
          repairable: true,
          updated_at: new Date().toISOString(),
        },
      })
    }
    return {
      ...(ratingUserId ? { user_id: ratingUserId } : {}),
      problem_id,
      status,
      updated_at: new Date().toISOString(),
      ...(note !== undefined ? { note } : {}),
    }
  }

  if (!userId) {
    // フォールバック: 認証なしでも動作（後方互換）
    const { error } = await supabaseAdmin
      .from('ratings')
      .upsert(
        await buildPayload(null),
        { onConflict: 'problem_id' },
      )
    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ ok: true })
  }

  // user_id ありの場合は per-user ratings に upsert
  const { error } = await supabaseAdmin
    .from('ratings')
    .upsert(
      await buildPayload(userId),
      { onConflict: 'user_id,problem_id' },
    )
  if (error) {
    // onConflict カラムが存在しない場合は旧方式にフォールバック
    const { error: fallbackError } = await supabaseAdmin
      .from('ratings')
      .upsert(
        await buildPayload(null),
        { onConflict: 'problem_id' },
      )
    if (fallbackError) return NextResponse.json({ error: fallbackError.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
