import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

type PurgeCandidate = {
  id: string
  rating?: { status?: string | null; x_posted?: boolean | null } | { status?: string | null; x_posted?: boolean | null }[] | null
}

function shouldPurge(candidate: PurgeCandidate) {
  const rating = Array.isArray(candidate.rating) ? candidate.rating[0] : candidate.rating
  if (!rating) return true
  if (rating.x_posted === true) return false
  return rating.status !== 'selected' && rating.status !== 'posted'
}

/**
 * selected / posted 以外を Supabase から直接削除
 * Python 不要 → Vercel でも動作する
 */
export async function POST() {
  // 1. 削除対象を problems 起点で取得（ratings が無い problem も対象にする）
  const { data: candidates, error: fetchErr } = await supabaseAdmin
    .from('problems')
    .select('id, rating:ratings(status,x_posted)')

  if (fetchErr)
    return NextResponse.json({ ok: false, error: fetchErr.message }, { status: 500 })

  const checked = ((candidates ?? []) as PurgeCandidate[])
  const ids = checked.filter(shouldPurge).map(p => p.id)

  if (ids.length === 0)
    return NextResponse.json({ ok: true, deleted: 0, checked: checked.length })

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

  return NextResponse.json({ ok: true, deleted: ids.length, checked: checked.length })
}
