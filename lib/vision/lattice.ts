/**
 * MORTRA Vision — Lattice Core
 *
 * 格子は描画の対象ではなく、意味の中心にする。
 * 一つの格子 Λ = BZⁿ から、結晶・対称群・ルート系・整数論が同じ対象の別の姿として開く。
 *
 *   Λ ─┬─ Λ*, Miller面, 回折      結晶
 *      ├─ Aut(Λ)                  対称群
 *      ├─ 最小ベクトル → ルート系  Lie
 *      └─ Θ_Λ(q)                  整数論
 *
 * ここには Three.js も SVG も出てこない。描画は別の層の仕事で、
 * この層は「同じベクトルがどこへ運ばれたか」だけを保証する。
 * それが semantic transport であり、MORTRA という名前の中身。
 *
 * 全部整数と有理数の演算で、外部サービスも LLM も使わない。
 */

export type Vec3 = [number, number, number]
/** 基底。列ベクトルが基本並進ベクトル。B[i] が i 番目の基底ベクトル */
export type Basis = [Vec3, Vec3, Vec3]

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k]
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]

/** 整数係数から実際の格子点へ */
export function lift(B: Basis, n: [number, number, number]): Vec3 {
  return add(add(scale(B[0], n[0]), scale(B[1], n[1])), scale(B[2], n[2]))
}

export function determinant(B: Basis): number {
  return dot(B[0], cross(B[1], B[2]))
}

/** Gram 行列 G = BᵀB。格子の計量はここに全部入っている */
export function gram(B: Basis): number[][] {
  return [0, 1, 2].map(i => [0, 1, 2].map(j => dot(B[i], B[j])))
}

/**
 * 双対格子（結晶では逆格子）。
 *   Λ* = { y : ⟨x, y⟩ ∈ ℤ  ∀x ∈ Λ }
 * 数学の規約（2π を付けない）。結晶学の 2π 倍が要るときは呼び出し側で掛ける。
 */
export function dual(B: Basis): Basis {
  const V = determinant(B)
  if (Math.abs(V) < 1e-12) throw new Error('degenerate basis')
  return [
    scale(cross(B[1], B[2]), 1 / V),
    scale(cross(B[2], B[0]), 1 / V),
    scale(cross(B[0], B[1]), 1 / V),
  ]
}

/**
 * Miller 指数 (hkl) → 逆格子ベクトル G_hkl と面間隔 d。
 *   G_hkl = h b₁ + k b₂ + l b₃      (b は逆格子基底)
 *   d_hkl = 1 / |G_hkl|
 * 面の法線が逆格子ベクトルそのものである、というのが結晶学の要。
 */
export function millerPlane(B: Basis, hkl: [number, number, number]) {
  const R = dual(B)
  const G = lift(R, hkl)
  const len = Math.hypot(...G)
  return {
    hkl,
    /** 面の法線 = 逆格子ベクトル。同じベクトルが実空間の面と逆空間の点の両方を指す */
    normal: G,
    spacing: len > 0 ? 1 / len : Infinity,
    /** 面 ⟨x, G⟩ = m 上に乗る格子点だけを取る */
    onPlane: (n: [number, number, number], m = 0) => hkl[0] * n[0] + hkl[1] * n[1] + hkl[2] * n[2] === m,
  }
}

// ---------------------------------------------------------------------------
// 殻（shell）— ノルムごとの格子点。ここから配位数もテータ級数も出る
// ---------------------------------------------------------------------------

export type Shell = {
  /** ノルムの二乗。整数格子なら整数になる */
  norm2: number
  /** その殻に乗る格子点（整数座標） */
  coeffs: [number, number, number][]
  vectors: Vec3[]
}

/**
 * ノルム二乗が maxNorm2 以下の格子点を、殻ごとに集める。
 * 探索範囲は Gram 行列の最小固有値から決める。基底が歪んでいても取りこぼさない。
 */
export function shells(B: Basis, maxNorm2: number, tol = 1e-9): Shell[] {
  const G = gram(B)
  // ⟨Bn, Bn⟩ = nᵀGn ≥ λ_min |n|² なので、|n| ≤ sqrt(maxNorm2 / λ_min)
  const lambdaMin = smallestEigenvalue3(G)
  if (lambdaMin <= tol) throw new Error('degenerate basis')
  const R = Math.floor(Math.sqrt(maxNorm2 / lambdaMin)) + 1

  const buckets = new Map<number, { coeffs: [number, number, number][]; vectors: Vec3[] }>()
  for (let i = -R; i <= R; i++) {
    for (let j = -R; j <= R; j++) {
      for (let k = -R; k <= R; k++) {
        if (i === 0 && j === 0 && k === 0) continue
        const v = lift(B, [i, j, k])
        const n2 = dot(v, v)
        if (n2 > maxNorm2 + tol) continue
        // 数値誤差で殻が割れないよう、整数に十分近ければ丸める
        const key = Math.abs(n2 - Math.round(n2)) < 1e-7 ? Math.round(n2) : Number(n2.toFixed(6))
        if (!buckets.has(key)) buckets.set(key, { coeffs: [], vectors: [] })
        const b = buckets.get(key)!
        b.coeffs.push([i, j, k])
        b.vectors.push(v)
      }
    }
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([norm2, b]) => ({ norm2, ...b }))
}

/** 最小ベクトル。個数がそのまま配位数（接吻数） */
export function minimalVectors(B: Basis): Shell {
  const G = gram(B)
  const bound = Math.max(G[0][0], G[1][1], G[2][2]) * 1.001
  const s = shells(B, bound)
  if (!s.length) throw new Error('no lattice points found')
  return s[0]
}

export const kissingNumber = (B: Basis) => minimalVectors(B).coeffs.length

/**
 * 充填率。球の半径は最小距離の半分（それ以上だと球が重なる）。
 *   f = (4/3)πr³ / |det B|
 */
export function packingFraction(B: Basis): number {
  const r = Math.sqrt(minimalVectors(B).norm2) / 2
  return (4 / 3) * Math.PI * r ** 3 / Math.abs(determinant(B))
}

/**
 * テータ級数 Θ_Λ(q) = Σ_{x∈Λ} q^{|x|²} の係数。
 * 係数 a_m は「ノルム二乗が m の格子点の個数」。
 * 3D で半径を伸ばすと殻が順に光る、その個数がそのまま整数論の対象になる。
 */
export function thetaSeries(B: Basis, maxNorm2: number): { norm2: number; count: number }[] {
  return [
    { norm2: 0, count: 1 },
    ...shells(B, maxNorm2).map(s => ({ norm2: s.norm2, count: s.coeffs.length })),
  ]
}

// ---------------------------------------------------------------------------
// 対称性 — Aut(Λ) = { A ∈ GL(3,ℤ) : AᵀGA = G }
// ---------------------------------------------------------------------------

/**
 * 格子の自己同型群。
 * 基底ベクトルは同じノルムの格子ベクトルにしか行けないので、
 * その候補の中から内積を全部保つ組だけを残す。有限の探索で厳密に決まる。
 */
export function automorphisms(B: Basis): number[][][] {
  const G = gram(B)
  const maxDiag = Math.max(G[0][0], G[1][1], G[2][2])
  const pool = shells(B, maxDiag * 1.001)

  // 各基底ベクトルの行き先候補は、同じノルムを持つ格子ベクトル
  const candidates = [0, 1, 2].map(i =>
    pool.filter(s => Math.abs(s.norm2 - G[i][i]) < 1e-7).flatMap(s => s.coeffs),
  )

  const out: number[][][] = []
  const images: [number, number, number][] = []
  const search = (i: number) => {
    if (i === 3) {
      // 列が基底の像。整数行列として det = ±1 でなければ格子を保たない
      const A = [0, 1, 2].map(r => [images[0][r], images[1][r], images[2][r]])
      const det = det3(A)
      if (Math.abs(Math.abs(det) - 1) < 1e-9) out.push(A)
      return
    }
    for (const c of candidates[i]) {
      // 既に決めた像との内積が元と一致するか
      let ok = true
      for (let j = 0; j < i; j++) {
        const inner = dot(lift(B, c), lift(B, images[j]))
        if (Math.abs(inner - G[i][j]) > 1e-7) { ok = false; break }
      }
      if (!ok) continue
      images[i] = c
      search(i + 1)
    }
  }
  search(0)
  return out
}

/**
 * 対称 3×3 の最小固有値。探索半径を決めるためだけに使う。
 * 特性多項式を解く（3次なので閉じた式で出る）。
 */
function smallestEigenvalue3(G: number[][]): number {
  const p1 = G[0][1] ** 2 + G[0][2] ** 2 + G[1][2] ** 2
  const tr = G[0][0] + G[1][1] + G[2][2]
  if (p1 === 0) return Math.min(G[0][0], G[1][1], G[2][2])
  const q = tr / 3
  const p2 = (G[0][0] - q) ** 2 + (G[1][1] - q) ** 2 + (G[2][2] - q) ** 2 + 2 * p1
  const p = Math.sqrt(p2 / 6)
  const Bm = G.map((row, i) => row.map((x, j) => (x - (i === j ? q : 0)) / p))
  const r = Math.max(-1, Math.min(1, det3(Bm) / 2))
  const phi = Math.acos(r) / 3
  // eig1 ≥ eig2 ≥ eig3
  const eig1 = q + 2 * p * Math.cos(phi)
  const eig3 = q + 2 * p * Math.cos(phi + (2 * Math.PI) / 3)
  return Math.min(eig3, eig1)
}

function det3(A: number[][]): number {
  return (
    A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1])
    - A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
    + A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0])
  )
}

// ---------------------------------------------------------------------------
// ルート系 — 結晶が Lie 理論に変わるところ
// ---------------------------------------------------------------------------

export type RootSystem = {
  roots: Vec3[]
  /** 単純ルート。Dynkin 図はここから出る */
  simple: Vec3[]
  /** Cartan 行列 a_ij = 2⟨αᵢ,αⱼ⟩/⟨αⱼ,αⱼ⟩ */
  cartan: number[][]
  /** A3, D3, … 判定できたときだけ */
  type: string | null
}

/**
 * 最小ベクトルをルート系として読む。
 *
 * FCC の 12 本の最近接方向は、そのまま A₃ ルート系である。
 * 物質の結晶が Lie 代数のルート系になる、というのはここが根拠。
 * 判定は Cartan 整数（すべて整数になるか）と Dynkin 図の形で行う。
 */
export function rootSystem(B: Basis): RootSystem {
  const min = minimalVectors(B)
  const roots = min.vectors

  // Cartan 整数がすべて整数でなければルート系ではない
  const cartanInt = (a: Vec3, b: Vec3) => 2 * dot(a, b) / dot(b, b)
  for (const a of roots) {
    for (const b of roots) {
      const c = cartanInt(a, b)
      if (Math.abs(c - Math.round(c)) > 1e-7) {
        return { roots, simple: [], cartan: [], type: null }
      }
    }
  }

  // 単純ルート：ある一般の方向について正のルートを取り、
  // 他の正ルートの和で書けないものを残す
  const generic: Vec3 = [Math.SQRT2, Math.PI / 3, Math.E / 5]
  const positive = roots.filter(r => dot(r, generic) > 1e-9)
  const key = (v: Vec3) => v.map(x => x.toFixed(6)).join(',')
  const posSet = new Set(positive.map(key))
  const simple = positive.filter(r =>
    !positive.some(a =>
      posSet.has(key(a))
      && key(a) !== key(r)
      && posSet.has(key([r[0] - a[0], r[1] - a[1], r[2] - a[2]] as Vec3)),
    ),
  )

  const cartan = simple.map(a => simple.map(b => Math.round(cartanInt(a, b))))
  return { roots, simple, cartan, type: classifyCartan(cartan) }
}

/**
 * Cartan 行列から型を読む。3 次元で出るものだけを見る。
 * A₃ ≅ D₃ なので、鎖なら A₃ と呼ぶ。
 */
function classifyCartan(C: number[][]): string | null {
  const n = C.length
  if (n === 0) return null
  if (!C.every((row, i) => row[i] === 2)) return null
  // 単純連結図：辺の本数（a_ij ≠ 0, i≠j）
  const edges: [number, number][] = []
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (C[i][j] !== 0) {
        if (C[i][j] !== C[j][i]) return `non-simply-laced(${n})`
        edges.push([i, j])
      }
    }
  }
  const degree = new Array(n).fill(0)
  edges.forEach(([i, j]) => { degree[i]++; degree[j]++ })
  if (edges.length === n - 1 && degree.every(d => d <= 2)) return `A${n}`
  if (edges.length === n - 1 && degree.some(d => d === 3)) return `D${n}`
  return `rank${n}`
}

// ---------------------------------------------------------------------------
// 既知の格子。基底は最短ベクトルで取る（可視化でも扱いやすい）
// ---------------------------------------------------------------------------

export const LATTICES: Record<string, { name: string; basis: Basis; note: string }> = {
  sc: {
    name: '単純立方 (SC)',
    basis: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    note: '自己双対。双対を取っても同じ格子に戻る',
  },
  fcc: {
    name: '面心立方 (FCC)',
    basis: [[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]],
    note: '最近接 12 本がそのまま A₃ ルート系。双対は BCC',
  },
  bcc: {
    name: '体心立方 (BCC)',
    basis: [[-0.5, 0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5]],
    note: 'A₃ のウェイト格子。双対は FCC',
  },
}
