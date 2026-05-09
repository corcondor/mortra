import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { supabaseAdmin } from '@/lib/supabase-admin'

function getStripe() {
  if (!process.env.STRIPE_SECRET_KEY) throw new Error('STRIPE_SECRET_KEY not set')
  return new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2026-04-22.dahlia' })
}

const PRICE_ID = process.env.STRIPE_PRICE_ID ?? ''  // Stripe ダッシュボードで作成した月額プランの Price ID

export async function POST(req: NextRequest) {
  if (!process.env.STRIPE_SECRET_KEY || !PRICE_ID) {
    return NextResponse.json(
      { error: 'Stripe が設定されていません。STRIPE_SECRET_KEY と STRIPE_PRICE_ID を環境変数に追加してください。' },
      { status: 503 },
    )
  }

  const stripe = getStripe()
  const authHeader = req.headers.get('Authorization')
  const token = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null
  if (!token) return NextResponse.json({ error: 'unauthorized' }, { status: 401 })

  const { data: userData } = await supabaseAdmin.auth.getUser(token)
  const user = userData?.user
  if (!user) return NextResponse.json({ error: 'invalid token' }, { status: 401 })

  const origin = req.headers.get('origin') ?? process.env.NEXT_PUBLIC_SITE_URL ?? 'https://sakumon-web.vercel.app'

  // 既存の Stripe Customer ID を確認
  const { data: subData } = await supabaseAdmin
    .from('subscriptions')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .single()

  let customerId = subData?.stripe_customer_id as string | undefined

  // Customer がなければ作成
  if (!customerId) {
    const customer = await stripe.customers.create({
      email: user.email,
      metadata: { supabase_user_id: user.id },
    })
    customerId = customer.id

    // Supabase に保存
    await supabaseAdmin.from('subscriptions').upsert({
      user_id: user.id,
      stripe_customer_id: customerId,
      status: 'free',
    }, { onConflict: 'user_id' })
  }

  // Stripe Checkout セッションを作成
  const session = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: 'subscription',
    payment_method_types: ['card'],
    line_items: [{ price: PRICE_ID, quantity: 1 }],
    success_url: `${origin}/?payment=success`,
    cancel_url:  `${origin}/?payment=canceled`,
    metadata: { supabase_user_id: user.id },
    subscription_data: {
      metadata: { supabase_user_id: user.id },
    },
  })

  return NextResponse.json({ ok: true, url: session.url })
}
