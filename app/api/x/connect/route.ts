import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { buildOAuthHeader } from '@/lib/x-oauth'

export async function GET(req: NextRequest) {
  // ── ユーザー認証 ──────────────────────────────────────────────────────
  const token = req.headers.get('Authorization')?.replace('Bearer ', '') ?? ''
  const { data: { user } } = await supabaseAdmin.auth.getUser(token)
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const consumerKey    = process.env.X_API_KEY?.trim() ?? ''
  const consumerSecret = process.env.X_API_SECRET?.trim() ?? ''
  if (!consumerKey || !consumerSecret) {
    return NextResponse.json({ error: 'X API credentials not configured' }, { status: 503 })
  }

  const appUrl      = (process.env.NEXT_PUBLIC_APP_URL ?? 'https://sakumon-web.vercel.app').replace(/\/$/, '')
  const callbackUrl = `${appUrl}/api/x/callback`

  // ── X に request_token をリクエスト ──────────────────────────────────
  const url = 'https://api.twitter.com/oauth/request_token'
  const res = await fetch(url, {
    method:  'POST',
    headers: { Authorization: buildOAuthHeader('POST', url, consumerKey, consumerSecret, { oauth_callback: callbackUrl }) },
  })

  if (!res.ok) {
    const detail = await res.text()
    return NextResponse.json({ error: `X request_token failed (${res.status}): ${detail}` }, { status: 502 })
  }

  const params           = new URLSearchParams(await res.text())
  const oauthToken       = params.get('oauth_token') ?? ''
  const oauthTokenSecret = params.get('oauth_token_secret') ?? ''

  if (!oauthToken) {
    return NextResponse.json({ error: 'X returned no oauth_token' }, { status: 502 })
  }

  // ── oauth_token → user_id のマッピングを一時保存（10分で期限切れ） ──
  await supabaseAdmin.from('x_oauth_states').upsert({
    oauth_token:        oauthToken,
    user_id:            user.id,
    oauth_token_secret: oauthTokenSecret,
    created_at:         new Date().toISOString(),
  })

  return NextResponse.json({
    redirectUrl: `https://api.twitter.com/oauth/authorize?oauth_token=${oauthToken}`,
  })
}
