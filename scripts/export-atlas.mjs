/**
 * 射のアトラスを JSON に書き出す。
 * Python 側（研究室のエージェント）が読むため。TS を二重に持たない。
 */
import fs from 'node:fs'
import path from 'node:path'

const src = fs.readFileSync('worker/src/generalization-kernel.ts', 'utf8')

/** MORPHISM_ATLAS（単源）と HYPER_MORPHISM_ATLAS（多源）を正規表現で拾う */
const single = [...src.matchAll(
  /\{\s*name:\s*'([^']+)',\s*source:\s*'([^']+)',\s*target:\s*'([^']+)',\s*preserves:\s*\[([^\]]*)\],\s*backend:\s*\[([^\]]*)\]/g,
)].map(m => ({
  name: m[1], sources: [m[2]], target: m[3],
  preserves: [...m[4].matchAll(/'([^']+)'/g)].map(x => x[1]),
  backend: [...m[5].matchAll(/'([^']+)'/g)].map(x => x[1]),
}))

/*
 * 多源の射は、フィールドの順序も改行も一定でない
 * （allows_cross_parent_fusion のような追加フィールドが挟まる）。
 * だから固定順の正規表現ではなく、オブジェクト単位で切ってから
 * フィールドごとに拾う。
 */
const multi = []
for (const block of src.matchAll(/\{[^{}]*\bsources:\s*\[[^\]]*\][^{}]*\}/g)) {
  const t = block[0]
  const name = /name:\s*'([^']+)'/.exec(t)?.[1]
  const target = /target:\s*'([^']+)'/.exec(t)?.[1]
  const sources = [...(/sources:\s*\[([^\]]*)\]/.exec(t)?.[1] ?? '').matchAll(/'([^']+)'/g)].map(x => x[1])
  if (!name || !target || !sources.length) continue
  const grab = (key) =>
    [...(new RegExp(key + ":\\s*\\[([^\\]]*)\\]").exec(t)?.[1] ?? '').matchAll(/'([^']+)'/g)].map(x => x[1])
  multi.push({ name, sources, target, preserves: grab('preserves'), backend: grab('backend') })
}

const seen = new Set()
const atlas = [...single, ...multi].filter(m => {
  const k = m.name + '|' + m.sources.join(',')
  if (seen.has(k)) return false
  seen.add(k)
  return true
})

const out = path.join('data', 'atlas.json')
fs.mkdirSync('data', { recursive: true })
fs.writeFileSync(out, JSON.stringify({ morphisms: atlas }, null, 1), 'utf8')

const sorts = new Set(atlas.flatMap(m => [...m.sources, m.target]))
console.log(`射 ${atlas.length} / ソート ${sorts.size} → ${out}`)
