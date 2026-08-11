/**
 * 対称群から模様を作り、SVG で書き出す。
 *
 * 意匠として使うなら SVG が正しい形式。ロゴにも壁紙にも UI にも持っていける。
 * 出す前に対称性を検証し、落ちたものは書き出さない。
 *
 *   npx tsx scripts/render-ornament.mts
 */
import { writeFile, mkdir } from 'node:fs/promises'
import {
  WALLPAPER, windowOrbit, verifySymmetry, pointGroupOrder,
  polygon, circle, motifFromVectors, toPath, type Stroke,
} from '../lib/mortra/vision/ornament.js'
import { LATTICES, minimalVectors } from '../lib/vision/lattice.js'

const OUT = 'export/ornament'
await mkdir(OUT, { recursive: true })

/** FCC の最小ベクトル12本（= A₃ ルート系）を平面へ落とす。数学の実データが母型になる */
const a3 = minimalVectors(LATTICES.fcc.basis).vectors
  .map(v => ({ x: v[0] * 0.62, y: v[1] * 0.62 }))

const MOTIFS: Record<string, Stroke[]> = {
  root: motifFromVectors(a3),
  poly: [polygon({ x: 0.3, y: 0.12 }, 0.15, 3), [{ x: 0, y: 0 }, { x: 0.3, y: 0.12 }]],
  circle: [circle({ x: 0.26, y: 0.15 }, 0.17), circle({ x: 0, y: 0 }, 0.09)],
  line: [[{ x: 0.04, y: 0.04 }, { x: 0.4, y: 0.2 }], [{ x: 0.4, y: 0.2 }, { x: 0.22, y: 0.42 }]],
}

const SIZE = 800
const K = SIZE / 4.4

let made = 0
let refused = 0
const rows: string[] = []

for (const [gk, group] of Object.entries(WALLPAPER)) {
  for (const [mk, motif] of Object.entries(MOTIFS)) {
    const strokes = windowOrbit(motif, group, { repeat: 5, scale: 1 }).strokes
    const verdict = verifySymmetry(strokes, group, { scale: 1 })
    if (!verdict.holds) {
      refused++
      rows.push(`  拒否  ${gk}/${mk}  点群 ${verdict.failedPointGroupElements.length} / 並進 ${verdict.failedTranslations.length} で重ならない`)
      continue
    }
    const placed = strokes.map(s =>
      s.map(p => ({ x: SIZE / 2 + p.x * K, y: SIZE / 2 - p.y * K })))
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${SIZE} ${SIZE}" width="${SIZE}" height="${SIZE}">
<title>${group.name} — ${group.character}</title>
<desc>点群 G/T の位数 ${pointGroupOrder(group)}。壁紙群 G は無限。生成元 ${group.pointGroupGenerators.length} 本の閉包。対称性を検証済み。</desc>
<rect width="${SIZE}" height="${SIZE}" fill="#ffffff"/>
<g fill="none" stroke="#111111" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"
   clip-path="url(#c)">
<clipPath id="c"><rect width="${SIZE}" height="${SIZE}"/></clipPath>
<path d="${toPath(placed)}"/>
</g>
</svg>`
    await writeFile(`${OUT}/${gk}-${mk}.svg`, svg, 'utf8')
    made++
    rows.push(`  ok    ${gk.padEnd(4)}/${mk.padEnd(7)} |G/T|=${String(pointGroupOrder(group)).padStart(2)}  線 ${String(strokes.length).padStart(5)} 本  ${group.character}`)
  }
}

console.log('\n対称群から模様を生成（対称性を検証してから書き出す）\n')
rows.forEach(r => console.log(r))
console.log(`\n書き出し ${made} 枚 / 拒否 ${refused} 枚 → ${OUT}/`)
