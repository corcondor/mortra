import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { supabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/**
 * 診断: ブラウザと同じ anon キーで見た場合と、service キーで見た場合の差を出す。
 * 差があれば RLS（行レベルセキュリティ）が原因で一覧が空になっている。
 */
export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? ''
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''

  const result: Record<string, unknown> = {
    env: {
      hasUrl: Boolean(url),
      hasAnonKey: Boolean(anonKey),
      hasServiceKey: Boolean(process.env.SUPABASE_SERVICE_KEY),
    },
  }

  // service role（RLS バイパス）
  try {
    const { count, error } = await supabaseAdmin
      .from('problems')
      .select('*', { count: 'exact', head: true })
    result.serviceRole = { count: count ?? 0, error: error?.message ?? null }
  } catch (e) {
    result.serviceRole = { error: e instanceof Error ? e.message : String(e) }
  }

  // anon key（ブラウザと同じ条件 = RLS が効く）
  try {
    const anon = createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    })
    const { count, error } = await anon
      .from('problems')
      .select('*', { count: 'exact', head: true })
    result.anonKey = { count: count ?? 0, error: error?.message ?? null }
  } catch (e) {
    result.anonKey = { error: e instanceof Error ? e.message : String(e) }
  }

  // ページと同じクエリ（ratings を JOIN・全列・件数制限なし）を再現
  try {
    const anon2 = createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    })
    const started = Date.now()
    const { data, error } = await anon2
      .from('problems')
      .select('*, rating:ratings(*)')
      .order('total', { ascending: false })
    result.pageQuery = {
      rows: data?.length ?? 0,
      ms: Date.now() - started,
      approxBytes: data ? JSON.stringify(data).length : 0,
      error: error?.message ?? null,
    }
  } catch (e) {
    result.pageQuery = { error: e instanceof Error ? e.message : String(e) }
  }

  const svc = (result.serviceRole as { count?: number })?.count ?? 0
  const anon = (result.anonKey as { count?: number })?.count ?? 0
  result.diagnosis =
    svc > 0 && anon === 0
      ? 'RLS が匿名/ログインユーザーの読み取りを止めています（一覧が空になる原因）。problems と ratings に SELECT ポリシーが必要。'
      : svc > 0 && anon > 0
        ? '読み取りは通っています。一覧が空ならフロント側の問題。'
        : 'service role でも 0 件。DB が空か接続不良。'

  return NextResponse.json(result)
}
