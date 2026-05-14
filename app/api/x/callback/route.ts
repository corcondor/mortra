import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { buildOAuthHeader } from '@/lib/x-oauth'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const oauthToken    = searchParams.get('oauth_token')    ?? ''
  const oauthVerifier = searchParams.get('oauth_verifier') ?? ''

  const appUrl = (process.env.NEXT_PUBLIC_APP_URL ?? 'https://sakumon-web.vercel.app').replace(/\/$/, '')

  if (!oauthToken || !oauthVerifier) {
    return NextResponse.redirect(`${appUrl}?x_error=missing_params`)
  }

  // ── 一時保存した oauth_token_secret と user_id を取得 ────────────────
  const { data: stateRow } = await supabaseAdmin
    .from('x_oauth_states')
    .select('user_id, oauth_token_secret, created_at')
    .eq('oauth_token', oauthToken)
    .single()

  if (!stateRow) {
    return NextResponse.redirect(`${appUrl}?x_error=invalid_state`)
  }

  // 10分以上経過していたら拒否
  const age = Date.now() - new Date(stateRow.created_at).getTime()
  if (age > 10 * 60 * 1000) {
    await supabaseAdmin.from('x_oauth_states').delete().eq('oauth_token', oauthToken)
    return NextResponse.redirect(`${appUrl}?x_error=state_expired`)
  }

  const consumerKey    = process.env.X_API_KEY?.trim()    ?? ''
  const consumerSecret = process.env.X_API_SECRET?.trim() ?? ''

  // ── access_token の交換 ───────────────────────────────────────────────
  const url = 'https://api.twitter.com/oauth/access_token'
  const res = await fetch(url, {
    method:  'POST',
    headers: {
      Authorization:  buildOAuthHeader('POST', url, consumerKey, consumerSecret,
        { oauth_token: oauthToken, oauth_verifier: oauthVerifier },
        stateRow.oauth_token_secret,
      ),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })

  if (!res.ok) {
    return NextResponse.redirect(`${appUrl}?x_error=token_exchange_failed`)
  }

  const p = new URLSearchParams(await res.text())
  const accessToken       = p.get('oauth_token')        ?? ''
  const accessTokenSecret = p.get('oauth_token_secret') ?? ''
  const xUserId           = p.get('user_id')            ?? ''
  const xUsername         = p.get('screen_name')        ?? ''

  if (!accessToken || !xUserId) {
    return NextResponse.redirect(`${appUrl}?x_error=invalid_token`)
  }

  // ── user_x_tokens に保存 ─────────────────────────────────────────────
  await supabaseAdmin.from('user_x_tokens').upsert({
    user_id:             stateRow.user_id,
    x_user_id:           xUserId,
    x_username:          xUsername,
    access_token:        accessToken,
    access_token_secret: accessTokenSecret,
    updated_at:          new Date().toISOString(),
  }, { onConflict: 'user_id' })

  // 一時データを削除
  await supabaseAdmin.from('x_oauth_states').delete().eq('oauth_token', oauthToken)

  return NextResponse.redirect(`${appUrl}?x_connected=1`)
}
