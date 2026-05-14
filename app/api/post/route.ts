import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { buildOAuthHeader, percent } from '@/lib/x-oauth'

export const maxDuration = 120

type XCredentials = {
  apiKey: string
  apiSecret: string
  accessToken: string
  accessTokenSecret: string
}

type TweetResult = {
  ok: boolean
  tweet_id?: string
  url?: string
  error?: string
  renderWarning?: string
}

function firstEnv(...names: string[]) {
  for (const name of names) {
    const value = process.env[name]?.trim()
    if (value) return value
  }
  return ''
}

function readJsonConfig() {
  const configPath = process.env.X_CONFIG_PATH?.trim()
  if (!configPath) return null

  try {
    const raw = fs.readFileSync(configPath, 'utf8')
    const data = JSON.parse(raw) as { x_api?: Record<string, string> }
    return data.x_api ?? null
  } catch {
    return null
  }
}

function getXCredentials(): XCredentials {
  const config = readJsonConfig()
  const credentials = {
    apiKey: firstEnv('X_API_KEY', 'TWITTER_API_KEY', 'X_CONSUMER_KEY', 'TWITTER_CONSUMER_KEY') || config?.consumer_key || '',
    apiSecret: firstEnv('X_API_SECRET', 'TWITTER_API_SECRET', 'X_CONSUMER_SECRET', 'TWITTER_CONSUMER_SECRET') || config?.consumer_secret || '',
    accessToken: firstEnv('X_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN') || config?.access_token || '',
    accessTokenSecret: firstEnv('X_ACCESS_TOKEN_SECRET', 'TWITTER_ACCESS_TOKEN_SECRET') || config?.access_token_secret || '',
  }

  const missing = [
    ['X_API_KEY', credentials.apiKey],
    ['X_API_SECRET', credentials.apiSecret],
    ['X_ACCESS_TOKEN', credentials.accessToken],
    ['X_ACCESS_TOKEN_SECRET', credentials.accessTokenSecret],
  ].filter(([, value]) => !value).map(([name]) => name)

  if (missing.length > 0) {
    throw new Error(`X API credentials missing: ${missing.join(', ')}`)
  }

  return credentials
}

function oauthHeader(method: 'POST', url: string, credentials: XCredentials) {
  return buildOAuthHeader(method, url, credentials.apiKey, credentials.apiSecret,
    { oauth_token: credentials.accessToken }, credentials.accessTokenSecret)
}

function summarizeOutput(value: string, limit = 1200) {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

function stripLatexDollars(text: string) {
  return text
    .replace(/\$\$([\s\S]*?)\$\$/g, '$1')
    .replace(/\$((?:[^$\\]|\\.)*?)\$/g, '$1')
    .replace(/\\\[([\s\S]*?)\\\]/g, '$1')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$1')
    .trim()
}

function tweetText(statement: string) {
  const text = stripLatexDollars(statement).replace(/\s+/g, ' ').trim()
  return text.length > 270 ? `${text.slice(0, 267)}...` : text
}

function imageTweetText(topic?: string) {
  const label = topic?.trim() || '数学'
  return `Sakumon Station\n${label}の問題です。問題文と解答は画像に添付しています。`
}

async function renderImage(req: NextRequest, body: Record<string, unknown>) {
  const renderUrl = new URL('/api/render', req.url)
  const res = await fetch(renderUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const data = await res.json().catch(() => null) as { error?: string; stderr?: string; code?: string } | null
    const detail = data?.stderr || data?.error || `HTTP ${res.status}`
    return { image: null, warning: `画像レンダリングに失敗したため、テキストのみで投稿します: ${detail}` }
  }

  return { image: await res.arrayBuffer(), warning: undefined }
}

async function uploadMedia(image: ArrayBuffer, credentials: XCredentials) {
  const url = 'https://upload.twitter.com/1.1/media/upload.json'
  const form = new FormData()
  form.append('media', new Blob([image], { type: 'image/png' }), 'sakumon.png')

  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: oauthHeader('POST', url, credentials) },
    body: form,
  })

  const data = await res.json().catch(() => null) as { media_id_string?: string; errors?: unknown; error?: string } | null
  if (!res.ok || !data?.media_id_string) {
    throw new Error(`X media upload failed (${res.status}): ${summarizeOutput(JSON.stringify(data ?? {}))}`)
  }

  return data.media_id_string
}

async function createTweet(text: string, mediaId: string | null, credentials: XCredentials): Promise<TweetResult> {
  const url = 'https://api.twitter.com/2/tweets'
  const body = mediaId ? { text, media: { media_ids: [mediaId] } } : { text }
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: oauthHeader('POST', url, credentials),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  const data = await res.json().catch(() => null) as { data?: { id?: string }; detail?: string; title?: string; errors?: unknown } | null
  const tweetId = data?.data?.id
  if (!res.ok || !tweetId) {
    throw new Error(`X post failed (${res.status}): ${summarizeOutput(JSON.stringify(data ?? {}))}`)
  }

  return { ok: true, tweet_id: tweetId, url: `https://x.com/i/web/status/${tweetId}` }
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { problem_id, statement, answer, topic, score, dry_run } = body as {
    problem_id: string
    statement:  string
    answer?:    string
    topic?:     string
    score?:     number
    dry_run?:   boolean
  }

  if (!problem_id || !statement) {
    return NextResponse.json(
      { ok: false, error: 'problem_id and statement required' },
      { status: 400 },
    )
  }

  const render = await renderImage(req, {
    statement,
    answer: answer ?? '',
    topic: topic ?? '数学',
    score: score ?? 0,
  })

  if (dry_run) {
    return NextResponse.json({
      ok: true,
      dryRun: true,
      wouldAttachImage: !!render.image,
      text: render.image ? imageTweetText(topic) : tweetText(statement),
      renderWarning: render.warning,
    })
  }

  // ── ユーザー自身のX認証トークンを優先して使う ────────────────────────
  let credentials: XCredentials
  const authToken = req.headers.get('Authorization')?.replace('Bearer ', '') ?? ''
  const baseApiKey    = process.env.X_API_KEY?.trim()    ?? ''
  const baseApiSecret = process.env.X_API_SECRET?.trim() ?? ''

  if (authToken && baseApiKey && baseApiSecret) {
    const { data: { user } } = await supabaseAdmin.auth.getUser(authToken)
    if (user) {
      const { data: xToken } = await supabaseAdmin
        .from('user_x_tokens')
        .select('access_token, access_token_secret')
        .eq('user_id', user.id)
        .single()

      if (xToken?.access_token) {
        credentials = {
          apiKey:            baseApiKey,
          apiSecret:         baseApiSecret,
          accessToken:       xToken.access_token,
          accessTokenSecret: xToken.access_token_secret,
        }
      } else {
        return NextResponse.json({
          ok: false,
          code: 'X_NOT_CONNECTED',
          error: 'Xアカウントが接続されていません。設定からXアカウントを接続してください。',
        }, { status: 403 })
      }
    } else {
      // ユーザー認証なし → env vars フォールバック（管理者用）
      try { credentials = getXCredentials() }
      catch (e) {
        return NextResponse.json({ ok: false, code: 'X_CREDENTIALS_MISSING',
          error: e instanceof Error ? e.message : String(e) }, { status: 503 })
      }
    }
  } else {
    try { credentials = getXCredentials() }
    catch (error) {
      return NextResponse.json({
        ok: false,
        code: 'X_CREDENTIALS_MISSING',
        error: error instanceof Error ? error.message : String(error),
      }, { status: 503 })
    }
  }

  try {
    const mediaId = render.image ? await uploadMedia(render.image, credentials) : null
    const result = await createTweet(mediaId ? imageTweetText(topic) : tweetText(statement), mediaId, credentials)

    await supabaseAdmin.from('ratings').upsert({
      problem_id,
      status:   'posted',
      x_posted: true,
    }, { onConflict: 'problem_id' })

    return NextResponse.json({ ...result, renderWarning: render.warning })
  } catch (error) {
    return NextResponse.json({
      ok: false,
      code: 'X_POST_FAILED',
      error: error instanceof Error ? error.message : String(error),
      renderWarning: render.warning,
    }, { status: 502 })
  }
}
