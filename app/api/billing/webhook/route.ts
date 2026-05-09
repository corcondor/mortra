import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { supabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'  // Edge では stripe.webhooks.constructEvent が動かない

function getStripe() {
  if (!process.env.STRIPE_SECRET_KEY) throw new Error('STRIPE_SECRET_KEY not set')
  return new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2026-04-22.dahlia' })
}

export async function POST(req: NextRequest) {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET
  if (!webhookSecret || !process.env.STRIPE_SECRET_KEY) {
    return NextResponse.json({ error: 'Stripe webhook not configured' }, { status: 503 })
  }

  const stripe = getStripe()
  const body   = await req.text()
  const sig    = req.headers.get('stripe-signature') ?? ''

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(body, sig, webhookSecret)
  } catch (err) {
    return NextResponse.json({ error: `Webhook signature invalid: ${err}` }, { status: 400 })
  }

  // サブスクリプション状態の更新
  const updateSub = async (sub: Stripe.Subscription) => {
    const userId = sub.metadata?.supabase_user_id
    if (!userId) return

    await supabaseAdmin.from('subscriptions').upsert({
      user_id:                userId,
      stripe_subscription_id: sub.id,
      stripe_customer_id:     typeof sub.customer === 'string' ? sub.customer : (sub.customer as Stripe.Customer).id,
      status:                 sub.status === 'active' ? 'active' : 'canceled',
      current_period_end:     (sub as Stripe.Subscription & { current_period_end?: number }).current_period_end
        ? new Date(((sub as Stripe.Subscription & { current_period_end: number }).current_period_end) * 1000).toISOString()
        : null,
      updated_at: new Date().toISOString(),
    }, { onConflict: 'user_id' })
  }

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session
      if (session.mode === 'subscription' && session.subscription) {
        const sub = await stripe.subscriptions.retrieve(session.subscription as string)
        await updateSub(sub)
      }
      break
    }
    case 'customer.subscription.updated':
    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription
      await updateSub(sub)
      break
    }
  }

  return NextResponse.json({ received: true })
}
