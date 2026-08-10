/**
 * 手書きに要る字のストロークを集めてくる。
 *
 * 日本語は KanjiVG（筆順つきの中心線）。1画 = 1 パスで入っている。
 * 輪郭フォントと違い、ペン先がなぞる線そのものなので変換が要らない。
 *
 *   node scripts/fetch-strokes.mjs "余弦定理より"
 *
 * 取ったものは data/strokes/ja.json に貯める。同じ字は二度取りに行かない。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const outFile = path.join(root, 'data', 'strokes', 'ja.json')
const BASE = 'https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/'

/** KanjiVG は 109×109 の座標系。0..1 に正規化して保存する */
const VIEW = 109

const cache = fs.existsSync(outFile)
  ? JSON.parse(fs.readFileSync(outFile, 'utf8'))
  : {}

const wanted = [...new Set((process.argv.slice(2).join('') || '').split(''))]
  .filter(ch => ch.trim() && !cache[ch])

if (!wanted.length) {
  console.log(`追加なし（保有 ${Object.keys(cache).length} 字）`)
  process.exit(0)
}

let got = 0
for (const ch of wanted) {
  const hex = ch.codePointAt(0).toString(16).padStart(5, '0')
  try {
    const res = await fetch(BASE + hex + '.svg')
    if (!res.ok) { console.log(`  ${ch} → ${res.status} 取得できず`); continue }
    const svg = await res.text()
    // <path d="..."> を出現順に取る。この順序がそのまま筆順になっている。
    const paths = [...svg.matchAll(/<path[^>]*\sd="([^"]+)"/g)].map(m => m[1])
    if (!paths.length) { console.log(`  ${ch} → パスなし`); continue }
    cache[ch] = { view: VIEW, strokes: paths }
    got++
    console.log(`  ${ch}  ${paths.length}画`)
  } catch (error) {
    console.log(`  ${ch} → ${error.message}`)
  }
}

fs.mkdirSync(path.dirname(outFile), { recursive: true })
fs.writeFileSync(outFile, JSON.stringify(cache), 'utf8')
console.log(`${got} 字を追加。合計 ${Object.keys(cache).length} 字 → ${path.relative(root, outFile)}`)
