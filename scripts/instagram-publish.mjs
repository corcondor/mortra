/**
 * Instagram へリール、画像、画像カルーセルを投稿する。
 *
 * Content Publishing API は 3 段階:
 *   1. POST /{ig-user-id}/media          … コンテナを作る（動画の URL を渡す）
 *   2. GET  /{container-id}?fields=status_code … FINISHED になるまで待つ
 *   3. POST /{ig-user-id}/media_publish  … creation_id を渡して公開
 *
 * 前提（ここは本人の操作が要る。README-instagram.md に手順あり）:
 *   * Instagram が「プロアカウント（ビジネス or クリエイター）」であること
 *   * Facebook ページと連携していること
 *   * Meta の App を作り instagram_basic + instagram_content_publish を付けること
 *   * 長期アクセストークンと IG ユーザー ID を .env.local に入れること
 *
 * 動画の制約（守らないと error code 24 で黙って失敗する）:
 *   9:16 / 5〜90秒 / H.264 の MP4 / 音声は AAC / 公開 URL であること
 *
 * 1 アカウントあたり 24 時間で 25 投稿まで。
 *
 * 使い方:
 *   node scripts/instagram-publish.mjs --video <公開URL> --caption "本文"
 *   node scripts/instagram-publish.mjs --image <公開URL> --caption "本文"
 *   node scripts/instagram-publish.mjs --image <問題URL> --image <解答URL> --caption "本文"
 *   node scripts/instagram-publish.mjs ... --dry   … 実際には投稿せず検査だけ
 */
import { existsSync, readFileSync } from 'node:fs'

function loadEnvFile(path) {
  if (!existsSync(path)) return
  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const value = line.trim()
    if (!value || value.startsWith('#')) continue
    const separator = value.indexOf('=')
    if (separator < 1) continue
    const key = value.slice(0, separator).trim()
    const content = value.slice(separator + 1).trim().replace(/^["']|["']$/g, '')
    if (key && !(key in process.env)) process.env[key] = content
  }
}

loadEnvFile('.env.local')

const GRAPH = 'https://graph.facebook.com/v21.0'

const args = process.argv.slice(2)
const flags = (name) => {
  const values = []
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === `--${name}` && args[index + 1]) values.push(args[index + 1])
  }
  return values
}
const flag = (name) => flags(name).at(-1)
const has = (name) => args.includes(`--${name}`)

const token = process.env.IG_ACCESS_TOKEN
const igUserId = process.env.IG_USER_ID
const videoUrl = flag('video')
const imageUrls = flags('image')
const caption = flag('caption') ?? ''
const dryRun = has('dry')
const expectedAccount = (flag('expected-account') ?? process.env.IG_EXPECTED_USERNAME ?? 'mortra_ai').replace(/^@/, '')

function fail(message) {
  console.error(`✗ ${message}`)
  process.exit(1)
}

if (!videoUrl && !imageUrls.length) fail('--video か --image のどちらかが要る')
if (videoUrl && imageUrls.length) fail('--video と --image は同時に指定できない')
if (imageUrls.length > 10) fail('Instagram のカルーセル画像は10枚までです')

// 公開 URL が本当に取れるかを先に確かめる。ここで落ちるのが一番多い。
const targets = videoUrl ? [videoUrl] : imageUrls
for (const target of targets) {
  const head = await fetch(target, { method: 'GET', headers: { Range: 'bytes=0-1' } })
    .catch(() => null)
  if (!head || !head.ok) {
    fail(`メディアの URL が外部から取れない (${head?.status ?? 'ネットワークエラー'}): ${target}`)
  }
  const contentType = head.headers.get('content-type') ?? ''
  console.log(`メディア確認: ${head.status} ${contentType} ${target}`)
  if (videoUrl && !contentType.includes('mp4') && !contentType.includes('video')) {
    fail(`動画の Content-Type が mp4 でない: ${contentType}`)
  }
  if (!videoUrl && !contentType.includes('image')) {
    fail(`画像の Content-Type ではない: ${contentType}`)
  }
}

if (!token || !igUserId) {
  console.log()
  console.log('IG_ACCESS_TOKEN と IG_USER_ID が .env.local に無いので、ここで止める。')
  console.log('メディアの URL は投稿できる状態。取得手順は README-instagram.md を見る。')
  console.log()
  console.log('入ったら実行されるリクエスト:')
  console.log(`  POST ${GRAPH}/${igUserId ?? '<IG_USER_ID>'}/media`)
  console.log(`       ${videoUrl ? `media_type=REELS&video_url=${videoUrl}` : `image_url=${imageUrls[0]}`}`)
  console.log(`       caption=${JSON.stringify(caption).slice(0, 60)}...`)
  console.log(`  GET  ${GRAPH}/<container-id>?fields=status_code   （FINISHED まで待つ）`)
  console.log(`  POST ${GRAPH}/${igUserId ?? '<IG_USER_ID>'}/media_publish`)
  process.exit(1)
}

const account = await fetch(
  `${GRAPH}/${igUserId}?fields=id,username&access_token=${token}`,
).then(response => response.json()).catch(() => null)
if (!account || account.error) fail(`Instagram アカウントを確認できない: ${JSON.stringify(account?.error ?? null)}`)
if (String(account.username ?? '').toLowerCase() !== expectedAccount.toLowerCase()) {
  fail(`投稿先が @${expectedAccount} ではなく @${account.username ?? 'unknown'} です`)
}

if (dryRun) {
  console.log(JSON.stringify({
    dryRun: true,
    account: { id: account.id, username: account.username },
    mediaType: videoUrl ? 'REELS' : imageUrls.length > 1 ? 'CAROUSEL' : 'IMAGE',
    mediaCount: targets.length,
    captionLength: caption.length,
  }, null, 2))
  process.exit(0)
}

async function createContainer(params) {
  params.set('access_token', token)
  const created = await fetch(`${GRAPH}/${igUserId}/media`, {
    method: 'POST', body: params,
  }).then(response => response.json())
  if (created.error) fail(`コンテナ作成に失敗: ${JSON.stringify(created.error)}`)
  console.log(`コンテナ作成: ${created.id}`)
  return created.id
}

async function waitUntilFinished(containerId) {
  const deadline = Date.now() + 10 * 60 * 1000
  for (;;) {
    if (Date.now() > deadline) fail(`メディアの処理が10分で終わらなかった: ${containerId}`)
    const status = await fetch(
      `${GRAPH}/${containerId}?fields=status_code,status&access_token=${token}`,
    ).then(response => response.json())
    if (status.status_code === 'FINISHED') { console.log('処理完了'); break }
    if (status.status_code === 'ERROR') {
      fail(`メディアの処理でエラー: ${status.status ?? '詳細なし'}`)
    }
    console.log(`  待機中… ${status.status_code ?? '?'}`)
    await new Promise((resolve) => setTimeout(resolve, 6000))
  }
}

let containerId
if (videoUrl) {
  containerId = await createContainer(new URLSearchParams({
    caption,
    media_type: 'REELS',
    video_url: videoUrl,
  }))
  await waitUntilFinished(containerId)
} else if (imageUrls.length === 1) {
  containerId = await createContainer(new URLSearchParams({ caption, image_url: imageUrls[0] }))
  await waitUntilFinished(containerId)
} else {
  const children = []
  for (const imageUrl of imageUrls) {
    const childId = await createContainer(new URLSearchParams({
      image_url: imageUrl,
      is_carousel_item: 'true',
    }))
    await waitUntilFinished(childId)
    children.push(childId)
  }
  containerId = await createContainer(new URLSearchParams({
    caption,
    media_type: 'CAROUSEL',
    children: children.join(','),
  }))
  await waitUntilFinished(containerId)
}

// 3. 公開
const published = await fetch(`${GRAPH}/${igUserId}/media_publish`, {
  method: 'POST',
  body: new URLSearchParams({ creation_id: containerId, access_token: token }),
}).then((r) => r.json())
if (published.error) fail(`公開に失敗: ${JSON.stringify(published.error)}`)
console.log(`✓ 投稿完了: ${published.id}`)
