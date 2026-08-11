/**
 * mathexamtest.jp から問題と、問題ごとの解答リンクを集める。
 *
 * これまで持っていた 5,369 問は 8 大学ぶんの .tex で、解答が付いていなかった。
 * この索引は問題ごとに解答サイトへの直リンクを持っているので、
 * 「問題 → 想定解」の対応が作れる。自動採点の分母になる。
 *
 * 相手のサーバに負荷をかけない。逐次・待ち時間つき・取得済みは飛ばす。
 *
 *   node scripts/harvest-mathexamtest.mjs --univ 10261 10541      東大・京大だけ
 *   node scripts/harvest-mathexamtest.mjs --all --limit 400        全大学から400ページ
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const OUT = path.join(ROOT, 'data', 'mathexamtest')
const BASE = 'https://mathexamtest.jp'
/** 相手のサーバへの間隔。詰めない */
const DELAY_MS = 900

const args = process.argv.slice(2)
const wantAll = args.includes('--all')
const limit = args.includes('--limit') ? Number(args[args.indexOf('--limit') + 1]) : Infinity
const univFilter = args.includes('--univ')
  ? args.slice(args.indexOf('--univ') + 1).filter(a => /^\d+$/.test(a))
  : []

const sleep = ms => new Promise(r => setTimeout(r, ms))

async function fetchText(url) {
  const res = await fetch(url, {
    headers: { 'user-agent': 'MORTRA research crawler (contact: yuta_shibahara@icloud.com)' },
  })
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  await sleep(DELAY_MS)
  return res.text()
}

/** 属性の取り出しは素朴に。DOM は要らない */
const links = html => [...html.matchAll(/<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi)]
  .map(m => ({ href: m[1], text: m[2].replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim() }))

const abs = (href, from) => new URL(href, from).toString()

// ── 1. 大学一覧 ─────────────────────────────────────────────
console.error('大学一覧を取得')
const indexHtml = await fetchText(`${BASE}/daigakubetumj/index.html`)
const universities = links(indexHtml)
  .filter(l => /\/daigakubetumj\/\d+index\.html$/.test(abs(l.href, `${BASE}/daigakubetumj/`)))
  .map(l => ({
    code: abs(l.href, `${BASE}/daigakubetumj/`).match(/(\d+)index\.html$/)[1],
    name: l.text,
    url: abs(l.href, `${BASE}/daigakubetumj/`),
  }))
const uniq = [...new Map(universities.map(u => [u.code, u])).values()]
console.error(`  ${uniq.length} 大学`)

const targets = univFilter.length
  ? uniq.filter(u => univFilter.includes(u.code))
  : wantAll ? uniq : uniq.slice(0, 3)
console.error(`  対象 ${targets.length} 大学\n`)

// ── 2. 各大学の試験ページ ───────────────────────────────────
await mkdir(OUT, { recursive: true })
let pageCount = 0
const summary = []

for (const u of targets) {
  const file = path.join(OUT, `${u.code}.json`)
  if (existsSync(file)) {
    const prev = JSON.parse(await readFile(file, 'utf8'))
    console.error(`${u.name} … 取得済み ${prev.problems.length} 問`)
    summary.push({ code: u.code, name: u.name, problems: prev.problems.length })
    continue
  }
  let examPages = []
  try {
    const html = await fetchText(u.url)
    examPages = [...new Set(
      links(html)
        .map(l => abs(l.href, u.url))
        .filter(h => /\/\d{4}\/\d+\/\d+mj\.html$/.test(h)),
    )]
  } catch (error) {
    console.error(`${u.name} … 一覧が取れない ${error.message}`)
    continue
  }

  const problems = []
  for (const page of examPages) {
    if (pageCount >= limit) break
    pageCount++
    let html
    try { html = await fetchText(page) } catch { continue }

    // 一枚のページに複数の問題。問題IDで切る
    const parts = html.split(/(?=<[^>]*>\s*\d{4}-\d+-\d+)/)
    for (const part of parts) {
      const idm = part.match(/(\d{4})-(\d+)-(\d+)/)
      if (!idm) continue
      const answers = links(part)
        .filter(l => /解答/.test(l.text) && /^https?:/.test(l.href))
        .map(l => ({ site: l.text, url: l.href }))
      if (!answers.length) continue
      // MathML をそのまま残す。タグを剥くと不等号も積分区間も消える。
      // 意味を運んでいるのはタグの方だった。
      const mathml = [...part.matchAll(/<math\b[\s\S]*?<\/math>/g)].map(m => m[0])
      const body = part
        .replace(/<script[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<math\b[\s\S]*?<\/math>/g, ' ⟦式⟧ ')
        .replace(/<[^>]*>/g, ' ')
        .replace(/&[a-z]+;/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim()
      problems.push({ id: idm[0], year: idm[1], univ: idm[2], no: idm[3], page, answers, body, mathml })
    }
    process.stderr.write(`\r${u.name} … ${problems.length} 問 / ${pageCount} ページ`)
  }
  await writeFile(file, JSON.stringify({ ...u, problems }, null, 2), 'utf8')
  console.error(`\r${u.name} … ${problems.length} 問 保存                `)
  summary.push({ code: u.code, name: u.name, problems: problems.length })
  if (pageCount >= limit) break
}

const total = summary.reduce((s, x) => s + x.problems, 0)
console.error(`\n合計 ${total} 問 / ${summary.length} 大学 → data/mathexamtest/`)
for (const s of summary) console.error(`  ${s.name.padEnd(14)} ${s.problems}`)
