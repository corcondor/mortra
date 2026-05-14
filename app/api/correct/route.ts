import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('Authorization')
  const token      = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null

  let userId: string | null = null
  if (token) {
    const { data } = await supabaseAdmin.auth.getUser(token)
    userId = data.user?.id ?? null
  }

  const { problem_id, is_incorrect, corrected_answer } = await req.json() as {
    problem_id:        string
    is_incorrect:      boolean
    corrected_answer?: string | null
  }

  if (!problem_id) {
    return NextResponse.json({ error: 'problem_id required' }, { status: 400 })
  }

  const patch: Record<string, unknown> = {
    problem_id,
    is_incorrect,
    updated_at: new Date().toISOString(),
  }
  if (corrected_answer !== undefined) patch.corrected_answer = corrected_answer
  if (userId) patch.user_id = userId

  const { error } = await supabaseAdmin
    .from('ratings')
    .upsert(patch, { onConflict: userId ? 'user_id,problem_id' : 'problem_id' })

  if (error) {
    // user_id カラムがない場合は旧方式にフォールバック
    delete patch.user_id
    const { error: e2 } = await supabaseAdmin
      .from('ratings')
      .upsert(patch, { onConflict: 'problem_id' })
    if (e2) return NextResponse.json({ error: e2.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
