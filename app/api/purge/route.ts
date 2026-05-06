import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

/**
 * selected / posted 以外を Supabase から直接削除
 * Python 不要 → Vercel でも動作する
 */
export async function POST() {
  // 1. 削除対象の problem_id を取得（ratings で selected/posted でないもの）
  const { data: targets, error: fetchErr } = await supabaseAdmin
    .from('ratings')
    .select('problem_id')
    .not('status', 'in', '("selected","posted")')

  if (fetchErr)
    return NextResponse.json({ ok: false, error: fetchErr.message }, { status: 500 })

  const ids = (targets ?? []).map((r: { problem_id: string }) => r.problem_id)

  if (ids.length === 0)
    return NextResponse.json({ ok: true, deleted: 0 })

  // 2. ratings を削除
  const { error: rErr } = await supabaseAdmin
    .from('ratings')
    .delete()
    .in('problem_id', ids)

  if (rErr)
    return NextResponse.json({ ok: false, error: rErr.message }, { status: 500 })

  // 3. problems を削除
  const { error: pErr } = await supabaseAdmin
    .from('problems')
    .delete()
    .in('id', ids)

  if (pErr)
    return NextResponse.json({ ok: false, error: pErr.message }, { status: 500 })

  return NextResponse.json({ ok: true, deleted: ids.length })
}
