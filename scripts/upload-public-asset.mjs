/**
 * 動画・画像を Supabase Storage の公開バケットへ上げて、公開 URL を返す。
 *
 * Instagram の Content Publishing API は video_url に
 * **外部から取得できる URL** を要求する（ローカルファイルは渡せない）。
 * X の動画アップロードもチャンク方式で公開 URL があると楽なので、
 * まず置き場所を用意する。
 *
 * 使い方:
 *   node scripts/upload-public-asset.mjs export/video/robot_ninepoint_reel.mp4
 */
import { readFile } from 'node:fs/promises'
import { basename } from 'node:path'
import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'

config({ path: '.env.local' })

const BUCKET = 'public-assets'

const url = process.env.NEXT_PUBLIC_SUPABASE_URL
const key = process.env.SUPABASE_SERVICE_KEY
if (!url || !key) {
  console.error('NEXT_PUBLIC_SUPABASE_URL と SUPABASE_SERVICE_KEY が要る')
  process.exit(1)
}

const filePath = process.argv[2]
if (!filePath) {
  console.error('使い方: node scripts/upload-public-asset.mjs <ファイル>')
  process.exit(1)
}

const supabase = createClient(url, key, {
  auth: { persistSession: false, autoRefreshToken: false },
})

// バケットが無ければ作る（公開読み取り）
const { data: buckets } = await supabase.storage.listBuckets()
if (!buckets?.some((b) => b.name === BUCKET)) {
  const { error } = await supabase.storage.createBucket(BUCKET, {
    public: true,
    // プランの上限を超えるとバケット自体が作れない。無料枠は 50MB。
    fileSizeLimit: 52428800,
  })
  if (error) { console.error('バケット作成に失敗:', error.message); process.exit(1) }
  console.log(`バケット ${BUCKET} を作成した（公開）`)
}

const body = await readFile(filePath)
const name = basename(filePath)
const contentType = name.endsWith('.mp4') ? 'video/mp4'
  : name.endsWith('.png') ? 'image/png'
  : 'application/octet-stream'

const { error } = await supabase.storage.from(BUCKET).upload(name, body, {
  contentType, upsert: true,
})
if (error) { console.error('アップロード失敗:', error.message); process.exit(1) }

const { data } = supabase.storage.from(BUCKET).getPublicUrl(name)
console.log(`アップロード完了: ${name} (${(body.length / 1024 / 1024).toFixed(1)}MB)`)
console.log(`公開URL: ${data.publicUrl}`)
