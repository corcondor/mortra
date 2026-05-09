import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { FREE_GENERATIONS_PER_MONTH, currentYearMonth } from '@/lib/billing'

/** ユーザーの今月の生成数と課金状態を返す */
export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('Authorization')
  const token = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null
  if (!token) return NextResponse.json({ error: 'unauthorized' }, { status: 401 })

  const { data: userData } = await supabaseAdmin.auth.getUser(token)
  const user = userData?.user
  if (!user) return NextResponse.json({ error: 'invalid token' }, { status: 401 })

  const adminEmail = process.env.ADMIN_EMAIL ?? 'imtceed@gmail.com'
  const isAdmin    = user.email === adminEmail
  const yearMonth = currentYearMonth()

  // 今月の生成数を取得
  const { data: usageData } = await supabaseAdmin
    .from('usage')
    .select('generations_count')
    .eq('user_id', user.id)
    .eq('year_month', yearMonth)
    .single()

  const generationsUsed = (usageData?.generations_count as number) ?? 0

  // サブスクリプション状態
  const { data: subData } = await supabaseAdmin
    .from('subscriptions')
    .select('status, current_period_end')
    .eq('user_id', user.id)
    .single()

  const isPaid    = subData?.status === 'active'
  const canGenerate = isAdmin || isPaid || generationsUsed < FREE_GENERATIONS_PER_MONTH

  return NextResponse.json({
    ok: true,
    isAdmin,
    isPaid,
    generationsUsed,
    freeLimit: FREE_GENERATIONS_PER_MONTH,
    canGenerate,
    yearMonth,
    subscriptionStatus: subData?.status ?? 'free',
    currentPeriodEnd:   subData?.current_period_end ?? null,
  })
}
