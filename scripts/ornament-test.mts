import { WALLPAPER, tile, verifySymmetry, polygon, motifFromVectors, toPath, groupOrder, closeGroup } from '../lib/mortra/vision/ornament.js'
import { LATTICES, minimalVectors } from '../lib/vision/lattice.js'

let pass = 0, fail = 0
const check = (n: string, ok: boolean, d = '') => {
  ok ? pass++ : fail++
  console.log(`${ok ? '  ok  ' : '  NG  '} ${n}${ok || !d ? '' : '   ' + d}`)
}

console.log('\n■ 17種の壁紙群のうち実装した9種で、模様が宣言どおりの対称性を持つか')
const motif = [
  ...polygon({ x: 0.28, y: 0.1 }, 0.12, 3).map(p => [p]).flat().length ? [polygon({ x: 0.28, y: 0.1 }, 0.12, 3)] : [],
  [{ x: 0.05, y: 0.05 }, { x: 0.34, y: 0.18 }],
]
for (const [key, g] of Object.entries(WALLPAPER)) {
  const strokes = tile(motif, g, { repeat: 4, scale: 1 })
  const v = verifySymmetry(strokes, g)
  check(`${key.padEnd(4)} 位数${String(groupOrder(g)).padStart(2)}  ${g.character}`, v.holds,
    v.holds ? '' : `生成元 ${v.failed.join(',')} で重ならない`)
}

console.log('\n■ 格子の実データが意匠になるか')
{
  // FCC の最小ベクトル12本（= A₃ ルート系）を平面へ射影して母型にする
  const min = minimalVectors(LATTICES.fcc.basis)
  const projected = min.vectors.map(v => ({ x: v[0], y: v[1] }))
  const m = motifFromVectors(projected)
  check('A₃ の12本から母型ができる', m.length === 12, `${m.length} 本`)
  const strokes = tile(m, WALLPAPER.p6, { repeat: 2, scale: 1.2 })
  check('p6 で展開できる', strokes.length === 12 * groupOrder(WALLPAPER.p6) * 25, `${strokes.length} 本`)
  const path = toPath(strokes.slice(0, 3))
  check('SVG パスになる', path.startsWith('M ') && path.includes('L '), path.slice(0, 46))
}

console.log('\n■ 偽の主張を拒む')
{
  // 対称でない母型を p1（並進のみ）で展開し、p6 を名乗れないことを確認
  const skew = [[{ x: 0.11, y: 0.03 }, { x: 0.37, y: 0.09 }]]
  const strokes = tile(skew, WALLPAPER.p1, { repeat: 4, scale: 1 })
  const v = verifySymmetry(strokes, WALLPAPER.p6)
  check('並進だけの模様は p6 を名乗れない', !v.holds, `失敗した生成元 ${v.failed.length} 個`)
}

console.log(`\n${'─'.repeat(60)}`)
console.log(`意匠生成 ${pass}/${pass + fail}`)
process.exit(fail ? 1 : 0)
