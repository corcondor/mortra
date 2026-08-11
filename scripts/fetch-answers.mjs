/**
 * 収集した解答リンクから、実際の解答本文を取ってくる。
 *
 * 採点にはこれが要る。自分の答えと突き合わせないと正答率が出ない。
 *
 * 相手のサーバに負荷をかけない。
 *   ・PDF は 1 本で複数問を覆うので、実体単位で 1 回だけ取る
 *   ・逐次・待ち時間つき・取得済みは飛ばす
 *   ・robots.txt を見て、拒否しているホストには行かない
 *
 *   node scripts/fetch-answers.mjs --limit 200
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { glob } from 'node:fs/promises'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'data', 'mathexamtest')
const OUT = path.join(ROOT, 'data', 'answers')
const DELAY_MS = 1200

const args = process.argv.slice(2)
const limit = args.includes('--limit') ? Number(args[args.indexOf('--limit') + 1]) : 100

const sleep = ms => new Promise(r => setTimeout(r, ms))
const key = url => createHash('sha1').update(url).digest('hex').slice(0, 16)

// ── robots.txt を見る ───────────────────────────────────────
const robotsCache = new Map()
async function allowed(url) {
  const u = new URL(url)
  const origin = u.origin
  if (!robotsCache.has(origin)) {
    let rules = []
    try {
      const res = await fetch(`${origin}/robots.txt`, {
        headers: { 'user-agent': 'MORTRA research crawler' },
      })
      if (res.ok) {
        const text = await res.text()
        let applies = false
        for (const line of text.split(/\r?\n/)) {
          const m = line.match(/^\s*(user-agent|disallow)\s*:\s*(.*)$/i)
          if (!m) continue
          if (m[1].toLowerCase() === 'user-agent') applies = m[2].trim() === '*'
          else if (applies && m[2].trim()) rules.push(m[2].trim())
        }
      }
    } catch { rules = [] }
    robotsCache.set(origin, rules)
    await sleep(400)
  }
  const disallow = robotsCache.get(origin)
  return !disallow.some(rule => u.pathname.startsWith(rule))
}

// ── 収集済みの解答リンクを、実体単位でまとめる ──────────────
const targets = new Map()   // url(アンカー無し) → [{problemId, anchor, site}]
for await (const file of glob(`${SRC}/*.json`)) {
  const data = JSON.parse(await readFile(file, 'utf8'))
  for (const p of data.problems ?? []) {
    for (const a of p.answers ?? []) {
      const [base, anchor] = a.url.split('#')
      if (!targets.has(base)) targets.set(base, [])
      targets.get(base).push({ problemId: p.id, anchor: anchor ?? null, site: a.site })
    }
  }
}
// 1本で多く覆うものから取る。少ない回数で多くの問題に答えが付く
const ordered = [...targets.entries()].sort((a, b) => b[1].length - a[1].length)
console.error(`解答の実体 ${ordered.length} 本。上位 ${limit} 本を取る\n`)

await mkdir(OUT, { recursive: true })
let fetched = 0
let skipped = 0
const index = []

for (const [url, uses] of ordered) {
  if (fetched >= limit) break
  const id = key(url)
  const isPdf = /\.pdf$/i.test(url)
  const file = path.join(OUT, `${id}.${isPdf ? 'pdf' : 'html'}`)

  if (existsSync(file)) {
    index.push({ id, url, isPdf, covers: uses })
    skipped++
    continue
  }
  if (!(await allowed(url))) {
    console.error(`  robots で拒否 ${url.slice(0, 70)}`)
    continue
  }
  try {
    const res = await fetch(url, {
      headers: { 'user-agent': 'MORTRA research crawler (contact: yuta_shibahara@icloud.com)' },
    })
    if (!res.ok) throw new Error(String(res.status))
    const buf = Buffer.from(await res.arrayBuffer())
    await writeFile(file, buf)
    index.push({ id, url, isPdf, covers: uses, bytes: buf.length })
    fetched++
    process.stderr.write(`\r取得 ${fetched}  覆う問題 ${index.reduce((s, x) => s + x.covers.length, 0)}`)
  } catch (error) {
    console.error(`\n  失敗 ${String(error.message).slice(0, 20)} ${url.slice(0, 60)}`)
  }
  await sleep(DELAY_MS)
}
process.stderr.write('\r')

await writeFile(path.join(OUT, 'index.json'), JSON.stringify(index, null, 2), 'utf8')
const covered = new Set(index.flatMap(x => x.covers.map(c => c.problemId)))
console.error(`\n新規取得 ${fetched} / 既存 ${skipped}`)
console.error(`解答が手元にある問題: ${covered.size}`)
console.error(`→ data/answers/`)
