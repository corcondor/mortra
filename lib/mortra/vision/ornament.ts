/**
 * 対称群から模様を作る。
 *
 * これまで格子核を「数学の可視化」としてしか見ていなかったのが誤りだった。
 * 幾何学は数学の中だけの物ではない。美しいから、模様・ロゴ・装飾・UI に使える。
 *
 * Rikyū が幾何学からロゴを作って 96 万再生を取ったのは、
 * デザインの問題を幾何の問題として解いたから。
 * MORTRA は既にその幾何を厳密に持っている。
 *
 *   Aut(Λ) 位数 48        →  対称性の生成元
 *   A₃ ルート系 12本       →  12方向の反復
 *   Miller 面             →  面群と縞
 *   最密充填 π/(3√2)      →  円の詰め方
 *   テータ級数の殻         →  同心の環
 *
 * ここは「数学を絵にする」層ではない。
 * **対称性から、意味を持った模様を生成する層**である。
 * 出てくる模様の対称群は宣言でき、検証できる。
 *
 * 17 種類の壁紙群（平面結晶群）は、平面の周期模様の完全な分類。
 * 装飾の歴史がこの 17 種類に尽きることは Fedorov が示している。
 * つまり「模様を作る」は、有限の語彙で書ける問題である。
 */

export type Pt = { x: number; y: number }

/** 平面の合同変換。模様はこの群の作用でできる */
export type Isometry = {
  /** [[a,b],[c,d]] の線型部分。回転・鏡映 */
  linear: [[number, number], [number, number]]
  translate: Pt
}

const compose = (f: Isometry, g: Isometry): Isometry => {
  const [[a, b], [c, d]] = f.linear
  const [[p, q], [r, s]] = g.linear
  return {
    linear: [[a * p + b * r, a * q + b * s], [c * p + d * r, c * q + d * s]],
    translate: {
      x: a * g.translate.x + b * g.translate.y + f.translate.x,
      y: c * g.translate.x + d * g.translate.y + f.translate.y,
    },
  }
}

export const apply = (t: Isometry, p: Pt): Pt => ({
  x: t.linear[0][0] * p.x + t.linear[0][1] * p.y + t.translate.x,
  y: t.linear[1][0] * p.x + t.linear[1][1] * p.y + t.translate.y,
})

const rotation = (turns: number): Isometry['linear'] => {
  const a = turns * 2 * Math.PI
  const c = Math.cos(a), s = Math.sin(a)
  return [[c, -s], [s, c]]
}
const mirrorX: Isometry['linear'] = [[1, 0], [0, -1]]
const identity: Isometry['linear'] = [[1, 0], [0, 1]]

// ---------------------------------------------------------------------------
// 壁紙群。平面の周期模様はこの 17 種類しかない（Fedorov 1891）
// ---------------------------------------------------------------------------

export type WallpaperGroup = {
  name: string
  /** 格子の型。模様の周期構造を決める */
  lattice: 'oblique' | 'rectangular' | 'rhombic' | 'square' | 'hexagonal'
  /** 最小の生成元。ここから群を閉包で作る。
   *  手で全要素を並べると閉じていない集合を「群」と呼んでしまう。実際そうなった。 */
  generators: Isometry['linear'][]
  /** 図形的な特徴。デザインの意図で選べるように言葉で持つ */
  character: string
}

const matKey = (m: Isometry['linear']) =>
  m.flat().map(x => (Math.abs(x) < 1e-9 ? 0 : x).toFixed(6)).join(',')

const matMul = (a: Isometry['linear'], b: Isometry['linear']): Isometry['linear'] => [
  [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
  [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
]

/**
 * 生成元から点群を作る。位数は宣言ではなく、この閉包の大きさで決まる。
 *
 * 手で 8 個並べて「位数 8」と書いたら閉じていなかった。
 * 閉包を取れば、位数は数えるものになる。
 */
export function closeGroup(generators: Isometry['linear'][], limit = 64): Isometry['linear'][] {
  const seen = new Map<string, Isometry['linear']>()
  seen.set(matKey(identity), identity)
  let frontier = [identity, ...generators]
  for (const g of generators) seen.set(matKey(g), g)
  while (frontier.length && seen.size <= limit) {
    const next: Isometry['linear'][] = []
    for (const a of frontier) {
      for (const g of generators) {
        const m = matMul(a, g)
        const k = matKey(m)
        if (!seen.has(k)) { seen.set(k, m); next.push(m) }
      }
    }
    frontier = next
  }
  return [...seen.values()]
}

/** 群の位数。数えて出す */
export const groupOrder = (group: WallpaperGroup) => closeGroup(group.generators).length

const G = (linear: Isometry['linear'][]): Isometry['linear'][] => linear

export const WALLPAPER: Record<string, WallpaperGroup> = {
  p1:  { name: 'p1',  lattice: 'oblique',     generators: G([identity]),
         character: '並進だけ。斜めに流れる' },
  p2:  { name: 'p2',  lattice: 'oblique',     generators: G([rotation(0.5)]),
         character: '180°の回転。点対称' },
  pm:  { name: 'pm',  lattice: 'rectangular', generators: G([mirrorX]),
         character: '鏡映。左右対称の帯' },
  pmm: { name: 'pmm', lattice: 'rectangular', generators: G([mirrorX, [[-1, 0], [0, 1]]]),
         character: '直交する二つの鏡。格子縞' },
  p4:  { name: 'p4',  lattice: 'square',      generators: G([rotation(0.25)]),
         character: '4回回転。風車' },
  p4m: { name: 'p4m', lattice: 'square',      generators: G([rotation(0.25), mirrorX]),
         character: '正方形の完全な対称性。市松と八方' },
  p3:  { name: 'p3',  lattice: 'hexagonal',   generators: G([rotation(1 / 3)]),
         character: '3回回転。三つ巴' },
  p6:  { name: 'p6',  lattice: 'hexagonal',   generators: G([rotation(1 / 6)]),
         character: '6回回転。雪の結晶・蜂の巣' },
  p6m: { name: 'p6m', lattice: 'hexagonal',   generators: G([rotation(1 / 6), mirrorX]),
         character: '六方の完全な対称性。麻の葉・籠目' },
}

/** 格子の型から並進ベクトルを作る */
export function latticeVectors(kind: WallpaperGroup['lattice'], scale = 1): [Pt, Pt] {
  switch (kind) {
    case 'square': return [{ x: scale, y: 0 }, { x: 0, y: scale }]
    case 'hexagonal': return [{ x: scale, y: 0 }, { x: scale / 2, y: scale * Math.sqrt(3) / 2 }]
    case 'rectangular': return [{ x: scale, y: 0 }, { x: 0, y: scale * 1.618 }]
    case 'rhombic': return [{ x: scale, y: scale * 0.5 }, { x: scale, y: -scale * 0.5 }]
    default: return [{ x: scale, y: 0 }, { x: scale * 0.42, y: scale * 0.91 }]
  }
}

// ---------------------------------------------------------------------------
// 母型（motif）。これを群で写して模様にする
// ---------------------------------------------------------------------------

export type Stroke = Pt[]

/**
 * 母型を群の全要素で写し、格子で並べる。
 *
 * 模様を「それらしく描く」のではなく、群の作用として作る。
 * だから出てきた模様の対称群を宣言でき、後から検証できる。
 */
export function tile(
  motif: Stroke[],
  group: WallpaperGroup,
  options: { repeat?: number; scale?: number } = {},
): Stroke[] {
  const repeat = options.repeat ?? 3
  const scale = options.scale ?? 1
  const [u, v] = latticeVectors(group.lattice, scale)
  const out: Stroke[] = []

  for (const linear of closeGroup(group.generators)) {
    for (let i = -repeat; i <= repeat; i++) {
      for (let j = -repeat; j <= repeat; j++) {
        const t: Isometry = {
          linear,
          translate: { x: u.x * i + v.x * j, y: u.y * i + v.y * j },
        }
        for (const stroke of motif) out.push(stroke.map(p => apply(t, p)))
      }
    }
  }
  return out
}

// ---------------------------------------------------------------------------
// 検証。出てきた模様が本当にその対称性を持つか
// ---------------------------------------------------------------------------

/**
 * 模様が宣言どおりの対称性を持つか確かめる。
 *
 * 「対称に見える」で済ませない。各生成元で写して、点集合が自分に重なるかを見る。
 * 重ならないなら、その群だと名乗ってはいけない。
 */
export function verifySymmetry(
  strokes: Stroke[],
  group: WallpaperGroup,
  tolerance = 1e-6,
): { holds: boolean; failed: number[] } {
  const points = strokes.flat()
  const grid = new Map<string, Pt[]>()
  const cell = Math.max(tolerance * 100, 1e-3)
  const key = (p: Pt) => `${Math.round(p.x / cell)}:${Math.round(p.y / cell)}`
  for (const p of points) {
    const k = key(p)
    if (!grid.has(k)) grid.set(k, [])
    grid.get(k)!.push(p)
  }
  const has = (p: Pt) => {
    const [gx, gy] = [Math.round(p.x / cell), Math.round(p.y / cell)]
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (const q of grid.get(`${gx + dx}:${gy + dy}`) ?? []) {
          if (Math.hypot(q.x - p.x, q.y - p.y) < tolerance) return true
        }
      }
    }
    return false
  }

  const failed: number[] = []
  closeGroup(group.generators).forEach((linear, index) => {
    // 端で切れているので、中心付近の点だけで判定する
    const inner = points.filter(p => Math.hypot(p.x, p.y) < 1.2)
    const ok = inner.every(p => has(apply({ linear, translate: { x: 0, y: 0 } }, p)))
    if (!ok) failed.push(index)
  })
  return { holds: failed.length === 0, failed }
}

// ---------------------------------------------------------------------------
// 格子から母型を作る。数学の対象がそのまま意匠になる
// ---------------------------------------------------------------------------

/** ルート系の各ルートを線分にする。A₃ なら 12 本の放射 */
export function motifFromVectors(vectors: { x: number; y: number }[]): Stroke[] {
  return vectors.map(v => [{ x: 0, y: 0 }, { x: v.x, y: v.y }])
}

/** 円をなぞる。最密充填の球、テータ級数の殻 */
export function circle(center: Pt, radius: number, segments = 48): Stroke {
  return Array.from({ length: segments + 1 }, (_, i) => {
    const a = (i / segments) * Math.PI * 2
    return { x: center.x + radius * Math.cos(a), y: center.y + radius * Math.sin(a) }
  })
}

/** 正多角形。単位胞の骨格 */
export function polygon(center: Pt, radius: number, sides: number, phase = 0): Stroke {
  return Array.from({ length: sides + 1 }, (_, i) => {
    const a = phase + (i / sides) * Math.PI * 2
    return { x: center.x + radius * Math.cos(a), y: center.y + radius * Math.sin(a) }
  })
}

/** 折れ線を SVG のパスにする。描画層はここから先 */
export function toPath(strokes: Stroke[], decimals = 3): string {
  const n = (v: number) => v.toFixed(decimals)
  return strokes
    .filter(s => s.length > 1)
    .map(s => `M ${n(s[0].x)} ${n(s[0].y)} ` + s.slice(1).map(p => `L ${n(p.x)} ${n(p.y)}`).join(' '))
    .join(' ')
}
