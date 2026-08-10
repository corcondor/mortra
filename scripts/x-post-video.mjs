/**
 * 動画を X に投稿する。
 *
 * app/api/post/route.ts の uploadMedia() は PNG を 1 回の POST で送っているが、
 * 動画はその経路では通らない。INIT / APPEND / FINALIZE に分けて送り、
 * サーバー側の変換が終わるまで STATUS を待つ必要がある。
 *
 *   node scripts/x-post-video.mjs <動画> --text "本文"        アップロードのみ（非公開）
 *   node scripts/x-post-video.mjs <動画> --text "本文" --post  投稿まで実行
 *
 * --post を付けない限り公開されない。media_id を取った時点では
 * まだどのツイートにも紐づいていないので、外からは見えない。
 */
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const UPLOAD = 'https://upload.twitter.com/1.1/media/upload.json'
const TWEETS = 'https://api.twitter.com/2/tweets'
const CHUNK = 4 * 1024 * 1024 // X の 1 チャンク上限は 5MB。余裕を持たせる

// ── 認証情報 ────────────────────────────────────────────────────────
// route.ts と同じ順序で読む。値はどこにも出力しない。

function loadEnvFile(file) {
  if (!fs.existsSync(file)) return
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line)
    if (!m) continue
    const value = m[2].trim().replace(/^["']|["']$/g, '')
    if (value && !process.env[m[1]]) process.env[m[1]] = value
  }
}

function credentials() {
  loadEnvFile(path.join(repoRoot, '.env.local'))

  let config = null
  const configPath = process.env.X_CONFIG_PATH?.trim()
  if (configPath && fs.existsSync(configPath)) {
    try { config = JSON.parse(fs.readFileSync(configPath, 'utf8')) } catch { config = null }
  }

  const creds = {
    apiKey:            process.env.X_API_KEY?.trim()            || config?.consumer_key       || '',
    apiSecret:         process.env.X_API_SECRET?.trim()         || config?.consumer_secret    || '',
    accessToken:       process.env.X_ACCESS_TOKEN?.trim()       || config?.access_token       || '',
    accessTokenSecret: process.env.X_ACCESS_TOKEN_SECRET?.trim()|| config?.access_token_secret|| '',
  }
  const missing = Object.entries(creds).filter(([, v]) => !v).map(([k]) => k)
  if (missing.length) throw new Error(`認証情報が足りない: ${missing.join(', ')}`)
  return creds
}

// ── OAuth 1.0a ──────────────────────────────────────────────────────
// 署名の対象にはクエリ文字列も含める。ヘッダーに入れるのは oauth_* だけ。

const percent = (v) => encodeURIComponent(v)
  .replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`)

function authHeader(method, url, params, creds) {
  const oauth = {
    oauth_consumer_key:     creds.apiKey,
    oauth_nonce:            crypto.randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp:        Math.floor(Date.now() / 1000).toString(),
    oauth_token:            creds.accessToken,
    oauth_version:          '1.0',
  }
  const normalized = Object.entries({ ...oauth, ...params })
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${percent(k)}=${percent(v)}`)
    .join('&')
  const base = [method, url, normalized].map(percent).join('&')
  const key = `${percent(creds.apiSecret)}&${percent(creds.accessTokenSecret)}`
  const signature = crypto.createHmac('sha1', key).update(base).digest('base64')

  return 'OAuth ' + Object.entries({ ...oauth, oauth_signature: signature })
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${percent(k)}="${percent(v)}"`)
    .join(', ')
}

async function signedFetch(method, baseUrl, query, body, creds) {
  const qs = Object.entries(query).map(([k, v]) => `${percent(k)}=${percent(v)}`).join('&')
  const res = await fetch(qs ? `${baseUrl}?${qs}` : baseUrl, {
    method,
    headers: { Authorization: authHeader(method, baseUrl, query, creds) },
    body,
  })
  const text = await res.text()
  let json = null
  try { json = text ? JSON.parse(text) : null } catch { /* HTML のエラーページ等 */ }
  if (!res.ok) {
    throw new Error(`${method} ${baseUrl} → ${res.status}: ${text.slice(0, 400)}`)
  }
  return json
}

// ── 分割アップロード ─────────────────────────────────────────────────

async function uploadVideo(file, creds) {
  const bytes = fs.readFileSync(file)
  console.log(`  ファイル ${path.basename(file)}  ${(bytes.length / 1048576).toFixed(2)} MB`)

  const init = await signedFetch('POST', UPLOAD, {
    command: 'INIT',
    total_bytes: String(bytes.length),
    media_type: 'video/mp4',
    media_category: 'tweet_video',
  }, undefined, creds)

  const mediaId = init.media_id_string
  if (!mediaId) throw new Error(`INIT が media_id を返さない: ${JSON.stringify(init)}`)
  console.log(`  INIT      media_id 取得`)

  const total = Math.ceil(bytes.length / CHUNK)
  for (let i = 0; i < total; i++) {
    const slice = bytes.subarray(i * CHUNK, Math.min((i + 1) * CHUNK, bytes.length))
    const form = new FormData()
    form.append('media', new Blob([slice]), 'chunk')
    await signedFetch('POST', UPLOAD, {
      command: 'APPEND',
      media_id: mediaId,
      segment_index: String(i),
    }, form, creds)
    console.log(`  APPEND    ${i + 1}/${total}  (${(slice.length / 1048576).toFixed(2)} MB)`)
  }

  let state = await signedFetch('POST', UPLOAD,
    { command: 'FINALIZE', media_id: mediaId }, undefined, creds)
  console.log(`  FINALIZE  送信完了`)

  // X 側で H.264 の再エンコードが走る。終わるまで投稿できない。
  let info = state.processing_info
  while (info && (info.state === 'pending' || info.state === 'in_progress')) {
    const wait = (info.check_after_secs ?? 3) * 1000
    console.log(`  STATUS    ${info.state}  ${info.progress_percent ?? 0}%  → ${wait / 1000}秒待つ`)
    await new Promise((r) => setTimeout(r, wait))
    state = await signedFetch('GET', UPLOAD,
      { command: 'STATUS', media_id: mediaId }, undefined, creds)
    info = state.processing_info
  }
  if (info?.state === 'failed') {
    throw new Error(`X 側の変換が失敗: ${JSON.stringify(info.error ?? info)}`)
  }
  console.log(`  STATUS    ${info?.state ?? 'succeeded'}`)
  return mediaId
}

async function createTweet(text, mediaId, creds) {
  const res = await fetch(TWEETS, {
    method: 'POST',
    headers: {
      Authorization: authHeader('POST', TWEETS, {}, creds),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text, media: { media_ids: [mediaId] } }),
  })
  const json = await res.json().catch(() => null)
  if (!res.ok) throw new Error(`ツイート作成に失敗 (${res.status}): ${JSON.stringify(json)}`)
  return json.data
}

// ── 実行 ────────────────────────────────────────────────────────────

const argv = process.argv.slice(2)
const file = argv.find((a) => !a.startsWith('--'))
const textArg = argv.indexOf('--text')
const text = textArg >= 0 ? argv[textArg + 1] : ''
const doPost = argv.includes('--post')

if (!file) {
  console.error('使い方: node scripts/x-post-video.mjs <動画> --text "本文" [--post]')
  process.exit(1)
}
const target = path.isAbsolute(file) ? file : path.join(repoRoot, file)
if (!fs.existsSync(target)) {
  console.error(`ファイルがない: ${target}`)
  process.exit(1)
}
if (doPost && !text.trim()) {
  console.error('--post には --text が要る')
  process.exit(1)
}

const creds = credentials()
console.log(doPost ? '動画をアップロードして投稿する' : '動画をアップロードするのみ（投稿しない）')
const mediaId = await uploadVideo(target, creds)

if (!doPost) {
  console.log('')
  console.log('アップロード成功。まだ公開されていない。')
  console.log('投稿するには同じコマンドに --post を付ける。')
  process.exit(0)
}

const tweet = await createTweet(text, mediaId, creds)
console.log('')
console.log(`投稿した: https://x.com/i/status/${tweet.id}`)
