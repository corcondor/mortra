/**
 * 平面結晶群から模様を作る。
 *
 * 幾何学は数学の中だけの物ではない。美しいから、模様・ロゴ・装飾・UI に使える。
 * ここは「数学を絵にする」層ではなく、**対称性から意味を持った模様を生成する層**。
 *
 * ── 用語について（前の実装は間違えていた）─────────────────────────
 *
 * 壁紙群 G は**無限群**である。並進部分群 T ≅ ℤ² を含むので、要素は無限個ある。
 * 「p4m は位数 8」と書いていたのは誤り。8 は点群 G/T の位数。
 *
 *   G          壁紙群。無限。並進を含む
 *   T ⊴ G      並進部分群。ℤ² と同型
 *   G/T        点群。有限。ここが 8 や 12 になる
 *   window     有限の窓に落ちた軌道。描画に使うのはこれ
 *
 * 型名も変数名も表示も、この三つを区別する。混ぜると「無限群の位数」を
 * 数えたことになって嘘になる。
 *
 * 17 種類の壁紙群は平面の周期模様の完全な分類（Fedorov 1891）。
 * つまり「模様を作る」は有限の語彙で書ける問題である。
 *
 * ── 主張の強さ ────────────────────────────────────────────────
 *
 * 群作用から出た模様は certified（数学的に検証できる）。
 * 「充填率 0.74 だから余白を 26% にする」は design_heuristic（解釈であって定理ではない）。
 * 二つを同じ status で扱わない。
 */

export type Pt = { x: number; y: number }

/** 制御文字が入力に混ざっていないか。正規表現に \b を書いて 0x08 を埋めた事故が3回あった */
export function assertNoControlChars(value: string, where: string): void {
  const bad = [...value].findIndex(ch => ch.charCodeAt(0) < 32 && !'\n\r\t'.includes(ch))
  if (bad >= 0) {
    throw new Error(
      `${where}: 制御文字 0x${value.charCodeAt(bad).toString(16)} が位置 ${bad} にある`)
  }
}

/** 平面の合同変換。線型部分と並進 */
export type Isometry = {
  linear: [[number, number], [number, number]]
  translate: Pt
}

/** 点群の要素。並進を持たない線型部分だけ */
export type PointGroupElement = Isometry['linear']

export const apply = (t: Isometry, p: Pt): Pt => ({
  x: t.linear[0][0] * p.x + t.linear[0][1] * p.y + t.translate.x,
  y: t.linear[1][0] * p.x + t.linear[1][1] * p.y + t.translate.y,
})

const rotation = (turns: number): PointGroupElement => {
  const a = turns * 2 * Math.PI
  const c = Math.cos(a), s = Math.sin(a)
  return [[c, -s], [s, c]]
}
const mirrorX: PointGroupElement = [[1, 0], [0, -1]]
const identity: PointGroupElement = [[1, 0], [0, 1]]

const matKey = (m: PointGroupElement) =>
  m.flat().map(x => (Math.abs(x) < 1e-9 ? 0 : x).toFixed(6)).join(',')

const matMul = (a: PointGroupElement, b: PointGroupElement): PointGroupElement => [
  [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
  [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
]

// ---------------------------------------------------------------------------
// 壁紙群 G = T ⋊ (G/T)
// ---------------------------------------------------------------------------

export type WallpaperGroup = {
  /** 国際記号 */
  name: string
  /** 並進部分群 T の型。周期構造を決める */
  latticeType: 'oblique' | 'rectangular' | 'rhombic' | 'square' | 'hexagonal'
  /** 点群 G/T の生成元。ここから閉包で点群を作る。
   *  手で全要素を並べると閉じていない集合を「群」と呼んでしまう。実際そうなった */
  pointGroupGenerators: PointGroupElement[]
  /** 図形的な特徴。デザインの意図で選べるように言葉で持つ */
  character: string
}

/**
 * 点群 G/T を生成元から閉包で作る。
 *
 * 返るのは**有限**の集合。壁紙群 G 自体は無限なので、これを G の位数とは呼べない。
 */
export function closePointGroup(
  generators: PointGroupElement[],
  limit = 64,
): PointGroupElement[] {
  const seen = new Map<string, PointGroupElement>()
  seen.set(matKey(identity), identity)
  for (const g of generators) seen.set(matKey(g), g)
  let frontier = [identity, ...generators]
  while (frontier.length && seen.size <= limit) {
    const next: PointGroupElement[] = []
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

/** 点群 G/T の位数。壁紙群 G の位数ではない（G は無限） */
export const pointGroupOrder = (group: WallpaperGroup) =>
  closePointGroup(group.pointGroupGenerators).length

export const WALLPAPER: Record<string, WallpaperGroup> = {
  p1:  { name: 'p1',  latticeType: 'oblique',     pointGroupGenerators: [identity],
         character: '並進だけ。斜めに流れる' },
  p2:  { name: 'p2',  latticeType: 'oblique',     pointGroupGenerators: [rotation(0.5)],
         character: '180°の回転。点対称' },
  pm:  { name: 'pm',  latticeType: 'rectangular', pointGroupGenerators: [mirrorX],
         character: '鏡映。左右対称の帯' },
  pmm: { name: 'pmm', latticeType: 'rectangular', pointGroupGenerators: [mirrorX, [[-1, 0], [0, 1]]],
         character: '直交する二つの鏡。格子縞' },
  p4:  { name: 'p4',  latticeType: 'square',      pointGroupGenerators: [rotation(0.25)],
         character: '4回回転。風車' },
  p4m: { name: 'p4m', latticeType: 'square',      pointGroupGenerators: [rotation(0.25), mirrorX],
         character: '正方形の完全な対称性。市松と八方' },
  p3:  { name: 'p3',  latticeType: 'hexagonal',   pointGroupGenerators: [rotation(1 / 3)],
         character: '3回回転。三つ巴' },
  p6:  { name: 'p6',  latticeType: 'hexagonal',   pointGroupGenerators: [rotation(1 / 6)],
         character: '6回回転。雪の結晶・蜂の巣' },
  p6m: { name: 'p6m', latticeType: 'hexagonal',   pointGroupGenerators: [rotation(1 / 6), mirrorX],
         character: '六方の完全な対称性。麻の葉・籠目' },
}

/** 並進部分群 T の基底 */
export function translationBasis(
  kind: WallpaperGroup['latticeType'],
  scale = 1,
): [Pt, Pt] {
  switch (kind) {
    case 'square': return [{ x: scale, y: 0 }, { x: 0, y: scale }]
    case 'hexagonal': return [{ x: scale, y: 0 }, { x: scale / 2, y: scale * Math.sqrt(3) / 2 }]
    case 'rectangular': return [{ x: scale, y: 0 }, { x: 0, y: scale * 1.618 }]
    case 'rhombic': return [{ x: scale, y: scale * 0.5 }, { x: scale, y: -scale * 0.5 }]
    default: return [{ x: scale, y: 0 }, { x: scale * 0.42, y: scale * 0.91 }]
  }
}

// ---------------------------------------------------------------------------
// 有限の窓に落とした軌道
// ---------------------------------------------------------------------------

export type Stroke = Pt[]

/** 描画に使うのは、無限群の軌道を有限の窓で切ったもの。名前でそう言う */
export type WindowOrbit = {
  strokes: Stroke[]
  /** 使った点群の要素数 */
  pointGroupSize: number
  /** 使った並進の個数。窓の大きさで決まる */
  translationCount: number
  group: WallpaperGroup
}

/**
 * 母型に G を作用させ、有限の窓に落とす。
 *
 * G は無限なので全軌道は書けない。窓を決めて、その中の像だけを取る。
 */
export function windowOrbit(
  motif: Stroke[],
  group: WallpaperGroup,
  options: { repeat?: number; scale?: number } = {},
): WindowOrbit {
  const repeat = options.repeat ?? 3
  const scale = options.scale ?? 1
  const [u, v] = translationBasis(group.latticeType, scale)
  const pointGroup = closePointGroup(group.pointGroupGenerators)
  const strokes: Stroke[] = []

  for (const linear of pointGroup) {
    for (let i = -repeat; i <= repeat; i++) {
      for (let j = -repeat; j <= repeat; j++) {
        const t: Isometry = { linear, translate: { x: u.x * i + v.x * j, y: u.y * i + v.y * j } }
        for (const stroke of motif) strokes.push(stroke.map(p => apply(t, p)))
      }
    }
  }
  return {
    strokes,
    pointGroupSize: pointGroup.length,
    translationCount: (2 * repeat + 1) ** 2,
    group,
  }
}

// ---------------------------------------------------------------------------
// 検証
// ---------------------------------------------------------------------------

export type SymmetryVerdict = {
  holds: boolean
  /** 点群のどの要素で重ならなかったか */
  failedPointGroupElements: number[]
  /** 並進で重ならなかったか */
  failedTranslations: number[]
  checkedPoints: number
}

/**
 * 模様が宣言どおりの対称性を持つか確かめる。
 *
 * 点群の各要素と、並進の基底の両方で写して、点集合が自分に重なるかを見る。
 * 端で切れているので、窓の内側の点だけで判定する。
 */
export function verifySymmetry(
  strokes: Stroke[],
  group: WallpaperGroup,
  options: { tolerance?: number; innerRadius?: number; scale?: number } = {},
): SymmetryVerdict {
  const tolerance = options.tolerance ?? 1e-6
  const innerRadius = options.innerRadius ?? 1.2
  const scale = options.scale ?? 1
  const points = strokes.flat()
  const cell = Math.max(tolerance * 100, 1e-3)
  const grid = new Map<string, Pt[]>()
  for (const p of points) {
    const k = `${Math.round(p.x / cell)}:${Math.round(p.y / cell)}`
    if (!grid.has(k)) grid.set(k, [])
    grid.get(k)!.push(p)
  }
  const has = (p: Pt) => {
    const gx = Math.round(p.x / cell), gy = Math.round(p.y / cell)
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (const q of grid.get(`${gx + dx}:${gy + dy}`) ?? []) {
          if (Math.hypot(q.x - p.x, q.y - p.y) < tolerance) return true
        }
      }
    }
    return false
  }

  const inner = points.filter(p => Math.hypot(p.x, p.y) < innerRadius)
  const failedPointGroupElements: number[] = []
  closePointGroup(group.pointGroupGenerators).forEach((linear, index) => {
    if (!inner.every(p => has(apply({ linear, translate: { x: 0, y: 0 } }, p)))) {
      failedPointGroupElements.push(index)
    }
  })

  // 並進でも重なるか。点群だけ見ていると周期性を確かめていない
  const [u, v] = translationBasis(group.latticeType, scale)
  const failedTranslations: number[] = []
  ;[u, v].forEach((t, index) => {
    const shifted = points.filter(p => Math.hypot(p.x + t.x, p.y + t.y) < innerRadius)
    if (!shifted.every(p => has({ x: p.x + t.x, y: p.y + t.y }))) failedTranslations.push(index)
  })

  return {
    holds: failedPointGroupElements.length === 0 && failedTranslations.length === 0,
    failedPointGroupElements,
    failedTranslations,
    checkedPoints: inner.length,
  }
}

// ---------------------------------------------------------------------------
// 主張の強さ。数学的に検証したものと、デザイン上の解釈を分ける
// ---------------------------------------------------------------------------

export type DesignClaimStatus =
  /** 数学的に検証した。群作用・不変量・閉包など */
  | 'certified'
  /** デザイン上の解釈。定理ではない。充填率から余白を決める等 */
  | 'design_heuristic'
  /** 検証に落ちた */
  | 'rejected'

export type DesignClaim = {
  status: DesignClaimStatus
  statement: string
  /** certified のときだけ、何で確かめたかを書く */
  evidence?: string
  /** design_heuristic のときだけ、どの数学量から来た解釈かを書く */
  derivedFrom?: string
}

// ---------------------------------------------------------------------------
// 母型
// ---------------------------------------------------------------------------

export function motifFromVectors(vectors: Pt[]): Stroke[] {
  return vectors.map(v => [{ x: 0, y: 0 }, { x: v.x, y: v.y }])
}

export function circle(center: Pt, radius: number, segments = 48): Stroke {
  return Array.from({ length: segments + 1 }, (_, i) => {
    const a = (i / segments) * Math.PI * 2
    return { x: center.x + radius * Math.cos(a), y: center.y + radius * Math.sin(a) }
  })
}

export function polygon(center: Pt, radius: number, sides: number, phase = 0): Stroke {
  return Array.from({ length: sides + 1 }, (_, i) => {
    const a = phase + (i / sides) * Math.PI * 2
    return { x: center.x + radius * Math.cos(a), y: center.y + radius * Math.sin(a) }
  })
}

export function toPath(strokes: Stroke[], decimals = 3): string {
  const n = (v: number) => v.toFixed(decimals)
  const path = strokes
    .filter(s => s.length > 1)
    .map(s => `M ${n(s[0].x)} ${n(s[0].y)} ` + s.slice(1).map(p => `L ${n(p.x)} ${n(p.y)}`).join(' '))
    .join(' ')
  assertNoControlChars(path, 'toPath')
  return path
}
