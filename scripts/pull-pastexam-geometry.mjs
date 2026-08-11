/**
 * 過去問DB から平面幾何の証明問題を抜き出す。
 *
 * 形式化器の未見データにするので、こちらの都合で問題文を書き換えない。
 * 書き換えた瞬間に「解けた」は意味を失う。
 *
 *   node scripts/pull-pastexam-geometry.mjs
 */
import { createClient } from '@supabase/supabase-js'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// .env.local を読む。値は絶対に出力しない
const env = Object.fromEntries(
  (await readFile(path.join(ROOT, '.env.local'), 'utf8'))
    .split('\n')
    .filter(l => l.includes('=') && !l.trim().startsWith('#'))
    .map(l => {
      const i = l.indexOf('=')
      return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^["']|["']$/g, '')]
    }),
)

const url = env.NEXT_PUBLIC_SUPABASE_URL
const key = env.SUPABASE_SERVICE_ROLE_KEY || env.NEXT_PUBLIC_SUPABASE_ANON_KEY
if (!url || !key) {
  console.error('Supabase の接続情報が .env.local に見つかりません')
  process.exit(1)
}
const db = createClient(url, key)

// 過去問は source_file が数字で始まる（01_tokyo/... など）
let all = []
for (let page = 0; page < 40; page++) {
  const { data, error } = await db
    .from('problems')
    .select('id, statement, answer, solution, difficulty, source_file, topic_a, topic_b')
    .like('source_file', '0%')
    .range(page * 1000, page * 1000 + 999)
  if (error) { console.error(error.message); process.exit(1) }
  if (!data?.length) break
  all = all.concat(data)
  if (data.length < 1000) break
}
console.error(`過去問 ${all.length} 件`)

// 出所の内訳
const bySource = {}
for (const p of all) {
  const k = String(p.source_file ?? '').split('/')[0]
  bySource[k] = (bySource[k] ?? 0) + 1
}
console.error('\n出所:')
for (const [k, n] of Object.entries(bySource).sort((a, b) => b[1] - a[1])) {
  console.error(`  ${k.padEnd(28)} ${n}`)
}

// 平面幾何の証明問題らしさ。三角形/円があり、示せ・証明せよ で終わる
const GEO = /三角形|△|外接円|内接円|垂心|外心|内心|重心|中点|垂線|接線|平行四辺形|正方形|ひし形|菱形|二等辺/
const PROVE = /示せ|証明せよ|証明しなさい/
// 座標・ベクトル・空間は今の語彙の外。混ぜると測定の意味が濁る
const OUT_OF_SCOPE = /空間|四面体|体積|ベクトル|座標平面|xy平面|積分|微分|数列|確率|複素数平面/

const candidates = all.filter(p => {
  const s = String(p.statement ?? '')
  return GEO.test(s) && PROVE.test(s) && !OUT_OF_SCOPE.test(s)
})
const geoOnly = all.filter(p => GEO.test(String(p.statement ?? '')))

console.error(`\n幾何語を含む            ${geoOnly.length}`)
console.error(`うち証明問題で範囲内      ${candidates.length}`)

await mkdir(path.join(ROOT, 'data'), { recursive: true })
const out = path.join(ROOT, 'data', 'pastexam-geometry.json')
await writeFile(out, JSON.stringify(
  candidates.map(p => ({
    id: p.id,
    source: p.source_file,
    topic: [p.topic_a, p.topic_b].filter(Boolean).join(' × '),
    difficulty: p.difficulty,
    statement: p.statement,
    answer: p.answer,
  })), null, 2), 'utf8')
console.error(`\n→ ${path.relative(ROOT, out)}`)

console.error('\n--- 先頭10件 ---')
for (const p of candidates.slice(0, 10)) {
  console.error(`\n[${p.source_file}] ${String(p.statement).replace(/\s+/g, ' ').slice(0, 150)}`)
}
