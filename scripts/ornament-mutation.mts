/**
 * 検証器が「壊れた模様」を本当に拒否するか。
 *
 * 正しい模様を通す試験（positive）だけでは、常に true を返す検証器も満点になる。
 * 意味を壊す変異を作り、全部が拒否されることを確かめる。
 * 一つでも通ったら、その検証器は何も検証していない。
 *
 *   npx tsx scripts/ornament-mutation.mts
 */
import {
  WALLPAPER, windowOrbit, verifySymmetry, closePointGroup, pointGroupOrder,
  polygon, circle, motifFromVectors, translationBasis, apply,
  type Stroke, type WallpaperGroup, type Pt,
} from '../lib/mortra/vision/ornament.js'

let pass = 0
let fail = 0
const failures: string[] = []
const check = (name: string, ok: boolean, detail = '') => {
  ok ? pass++ : (fail++, failures.push(`${name}  ${detail}`))
  console.log(`${ok ? '  ok  ' : '  NG  '} ${name}${ok || !detail ? '' : '   ' + detail}`)
}

const MOTIF: Stroke[] = [
  polygon({ x: 0.3, y: 0.12 }, 0.15, 3),
  [{ x: 0, y: 0 }, { x: 0.3, y: 0.12 }],
]

// ---------------------------------------------------------------------------
// 変異。どれも意味を壊す
// ---------------------------------------------------------------------------

type Mutation = {
  name: string
  apply: (s: Stroke[], g: WallpaperGroup) => Stroke[]
  /** その群に対して意味のある変異か。効かない変異は検査しない。
   *  鏡映を持たない群から鏡映を落としても何も壊れないので、
   *  「壊れているのに通った」と数えるのは検査側の誤り */
  appliesTo?: (g: WallpaperGroup) => boolean
}

const hasReflection = (g: WallpaperGroup) =>
  closePointGroup(g.pointGroupGenerators)
    .some(m => m[0][0] * m[1][1] - m[0][1] * m[1][0] < 0)

const MUTATIONS: Mutation[] = [
  {
    name: '点を1つ消す',
    apply: s => {
      const out = s.map(x => [...x])
      // 窓の内側にある線を選ぶ。端を消しても検証は内側しか見ないので効かない
      const i = out.findIndex(x => x.every(p => Math.hypot(p.x, p.y) < 0.9))
      if (i >= 0) out.splice(i, 1)
      return out
    },
  },
  {
    name: '1点を微小変位（1e-3）',
    apply: s => {
      const out = s.map(x => x.map(p => ({ ...p })))
      const i = out.findIndex(x => x.every(p => Math.hypot(p.x, p.y) < 0.9))
      if (i >= 0) out[i][0] = { x: out[i][0].x + 1e-3, y: out[i][0].y }
      return out
    },
  },
  {
    name: '1本を不正な角度で回す（7°）',
    apply: s => {
      const out = s.map(x => x.map(p => ({ ...p })))
      const i = out.findIndex(x => x.every(p => Math.hypot(p.x, p.y) < 0.9))
      if (i < 0) return out
      const a = (7 * Math.PI) / 180
      const c = Math.cos(a), sn = Math.sin(a)
      out[i] = out[i].map(p => ({ x: c * p.x - sn * p.y, y: sn * p.x + c * p.y }))
      return out
    },
  },
  {
    name: '格子の周期をずらす（1.07倍）',
    apply: (_, g) => windowOrbit(MOTIF, g, { repeat: 5, scale: 1.07 }).strokes,
  },
  {
    name: '点群の要素を1つ落とす',
    appliesTo: g => closePointGroup(g.pointGroupGenerators).length > 1,
    apply: (_, g) => {
      const full = closePointGroup(g.pointGroupGenerators)
      if (full.length < 2) return []
      const partial = full.slice(0, full.length - 1)
      const [u, v] = translationBasis(g.latticeType, 1)
      const out: Stroke[] = []
      for (const linear of partial) {
        for (let i = -5; i <= 5; i++) {
          for (let j = -5; j <= 5; j++) {
            const t = { linear, translate: { x: u.x * i + v.x * j, y: u.y * i + v.y * j } }
            for (const st of MOTIF) out.push(st.map(p => apply(t, p)))
          }
        }
      }
      return out
    },
  },
  {
    name: '境界だけずらす（外周を平行移動）',
    apply: s => s.map(x =>
      x.every(p => Math.hypot(p.x, p.y) > 1.05)
        ? x.map(p => ({ x: p.x + 0.02, y: p.y }))
        : x),
  },
  {
    name: '母型を非対称に歪める',
    apply: (_, g) => {
      const skew: Stroke[] = MOTIF.map(st => st.map(p => ({ x: p.x + 0.09 * p.y, y: p.y })))
      return windowOrbit(skew, { ...g, pointGroupGenerators: [[[1, 0], [0, 1]]] },
        { repeat: 5 }).strokes
    },
  },
  {
    name: '鏡映だけ落とす（回転は残す）',
    appliesTo: hasReflection,
    apply: (_, g) => {
      const rotations = closePointGroup(g.pointGroupGenerators)
        .filter(m => m[0][0] * m[1][1] - m[0][1] * m[1][0] > 0)
      if (!rotations.length) return []
      const [u, v] = translationBasis(g.latticeType, 1)
      const out: Stroke[] = []
      for (const linear of rotations) {
        for (let i = -5; i <= 5; i++) {
          for (let j = -5; j <= 5; j++) {
            const t = { linear, translate: { x: u.x * i + v.x * j, y: u.y * i + v.y * j } }
            for (const st of MOTIF) out.push(st.map(p => apply(t, p)))
          }
        }
      }
      return out
    },
  },
]

// ---------------------------------------------------------------------------

console.log('\n■ positive — 正しく生成した模様は通る')
const good: Record<string, Stroke[]> = {}
for (const [key, group] of Object.entries(WALLPAPER)) {
  const orbit = windowOrbit(MOTIF, group, { repeat: 5, scale: 1 })
  good[key] = orbit.strokes
  const v = verifySymmetry(orbit.strokes, group, { scale: 1 })
  check(`${key.padEnd(4)} 点群 G/T の位数 ${String(pointGroupOrder(group)).padStart(2)}`, v.holds,
    v.holds ? '' : `点群 ${v.failedPointGroupElements.length} / 並進 ${v.failedTranslations.length} で不一致`)
}

console.log('\n■ negative — 壊した模様は全部拒否されなければならない')
let leaked = 0
for (const [key, group] of Object.entries(WALLPAPER)) {
  // 対称性が自明な p1 は、多くの変異が「まだ p1 として正しい」ので除く
  if (key === 'p1') continue
  for (const mutation of MUTATIONS) {
    if (mutation.appliesTo && !mutation.appliesTo(group)) continue
    const broken = mutation.apply(good[key], group)
    if (!broken.length) continue
    const v = verifySymmetry(broken, group, { scale: 1 })
    const rejected = !v.holds
    if (!rejected) leaked++
    check(`${key.padEnd(4)} ${mutation.name}`, rejected,
      rejected ? '' : '← 壊れているのに通った')
  }
}

console.log('\n■ 検証器が常に true を返していないことの確認')
{
  // 全部拒否する検証器も無意味なので、positive が通っていることを併せて確認
  const anyPositive = Object.entries(WALLPAPER)
    .some(([, g]) => verifySymmetry(windowOrbit(MOTIF, g, { repeat: 5 }).strokes, g, { scale: 1 }).holds)
  check('正しい模様は通る（全部拒否ではない）', anyPositive)
  check('壊れた模様が漏れていない', leaked === 0, `漏れ ${leaked} 件`)
}

console.log(`\n${'─'.repeat(64)}`)
console.log(`変異テスト ${pass}/${pass + fail}${fail ? `   失敗 ${fail}` : ''}`)
if (failures.length) {
  console.log('\n失敗:')
  failures.forEach(f => console.log(`  ${f}`))
}
process.exit(fail ? 1 : 0)
