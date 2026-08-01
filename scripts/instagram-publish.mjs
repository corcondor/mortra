/**
 * Instagram へリール／画像を自動投稿する。
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
 *   node scripts/instagram-publish.mjs ... --dry   … 実際には投稿せず検査だけ
 */
import { config } from 'dotenv'

config({ path: '.env.local' })

const GRAPH = 'https://graph.facebook.com/v21.0'

const args = process.argv.slice(2)
const flag = (name) => {
  const index = args.indexOf(`--${name}`)
  return index >= 0 ? args[index + 1] : undefined
}
const has = (name) => args.includes(`--${name}`)

const token = process.env.IG_ACCESS_TOKEN
const igUserId = process.env.IG_USER_ID
const videoUrl = flag('video')
const imageUrl = flag('image')
const caption = flag('caption') ?? ''
const dryRun = has('dry')

function fail(message) {
  console.error(`✗ ${message}`)
  process.exit(1)
}

if (!videoUrl && !imageUrl) fail('--video か --image のどちらかが要る')

// 公開 URL が本当に取れるかを先に確かめる。ここで落ちるのが一番多い。
const target = videoUrl ?? imageUrl
const head = await fetch(target, { method: 'GET', headers: { Range: 'bytes=0-1' } })
  .catch(() => null)
if (!head || !head.ok) {
  fail(`メディアの URL が外部から取れない (${head?.status ?? 'ネットワークエラー'}): ${target}`)
}
const contentType = head.headers.get('content-type') ?? ''
console.log(`メディア確認: ${head.status} ${contentType}`)
if (videoUrl && !contentType.includes('mp4') && !contentType.includes('video')) {
  fail(`動画の Content-Type が mp4 でない: ${contentType}`)
}

if (!token || !igUserId) {
  console.log()
  console.log('IG_ACCESS_TOKEN と IG_USER_ID が .env.local に無いので、ここで止める。')
  console.log('メディアの URL は投稿できる状態。取得手順は README-instagram.md を見る。')
  console.log()
  console.log('入ったら実行されるリクエスト:')
  console.log(`  POST ${GRAPH}/${igUserId ?? '<IG_USER_ID>'}/media`)
  console.log(`       ${videoUrl ? `media_type=REELS&video_url=${target}` : `image_url=${target}`}`)
  console.log(`       caption=${JSON.stringify(caption).slice(0, 60)}...`)
  console.log(`  GET  ${GRAPH}/<container-id>?fields=status_code   （FINISHED まで待つ）`)
  console.log(`  POST ${GRAPH}/${igUserId ?? '<IG_USER_ID>'}/media_publish`)
  process.exit(0)
}

if (dryRun) {
  console.log('--dry なのでここまで。認証情報は揃っている。')
  process.exit(0)
}

// 1. コンテナ
const createParams = new URLSearchParams({ caption, access_token: token })
if (videoUrl) {
  createParams.set('media_type', 'REELS')
  createParams.set('video_url', videoUrl)
} else {
  createParams.set('image_url', imageUrl)
}
const created = await fetch(`${GRAPH}/${igUserId}/media`, {
  method: 'POST', body: createParams,
}).then((r) => r.json())
if (created.error) fail(`コンテナ作成に失敗: ${JSON.stringify(created.error)}`)
const containerId = created.id
console.log(`コンテナ作成: ${containerId}`)

// 2. 処理待ち。動画は 30 秒〜数分かかる。
if (videoUrl) {
  const deadline = Date.now() + 10 * 60 * 1000
  for (;;) {
    if (Date.now() > deadline) fail('動画の処理が10分で終わらなかった')
    const status = await fetch(
      `${GRAPH}/${containerId}?fields=status_code,status&access_token=${token}`,
    ).then((r) => r.json())
    if (status.status_code === 'FINISHED') { console.log('処理完了'); break }
    if (status.status_code === 'ERROR') {
      fail(`動画の処理でエラー: ${status.status ?? '詳細なし'}`)
    }
    console.log(`  待機中… ${status.status_code ?? '?'}`)
    await new Promise((resolve) => setTimeout(resolve, 6000))
  }
}

// 3. 公開
const published = await fetch(`${GRAPH}/${igUserId}/media_publish`, {
  method: 'POST',
  body: new URLSearchParams({ creation_id: containerId, access_token: token }),
}).then((r) => r.json())
if (published.error) fail(`公開に失敗: ${JSON.stringify(published.error)}`)
console.log(`✓ 投稿完了: ${published.id}`)
