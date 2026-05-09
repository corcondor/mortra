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

  const { problem_id, status } = await req.json()
  if (!problem_id || !status) {
    return NextResponse.json({ error: 'missing fields' }, { status: 400 })
  }

  if (!userId) {
    // フォールバック: 認証なしでも動作（後方互換）
    const { error } = await supabaseAdmin
      .from('ratings')
      .upsert(
        { problem_id, status, updated_at: new Date().toISOString() },
        { onConflict: 'problem_id' },
      )
    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ ok: true })
  }

  // user_id ありの場合は per-user ratings に upsert
  const { error } = await supabaseAdmin
    .from('ratings')
    .upsert(
      { user_id: userId, problem_id, status, updated_at: new Date().toISOString() },
      { onConflict: 'user_id,problem_id' },
    )
  if (error) {
    // onConflict カラムが存在しない場合は旧方式にフォールバック
    const { error: fallbackError } = await supabaseAdmin
      .from('ratings')
      .upsert(
        { problem_id, status, updated_at: new Date().toISOString() },
        { onConflict: 'problem_id' },
      )
    if (fallbackError) return NextResponse.json({ error: fallbackError.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
