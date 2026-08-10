/**
 * MathOS の構築ごとの作図。
 *
 * 各構築は「対象を作り、条件を課し、非自明な量を問う」形をしている。
 * その「対象を作る」部分は、点と線と円（と立体）の系列として書き下せる。
 * ここではそれを構築ごとに用意し、アームが辿れる筆跡へ変換する。
 *
 * 立体は板の上ではなく空間に描く。アームは板の前の空間を通るので、
 * ペンの向きも点ごとに変える必要があり、そこで逆運動学の姿勢部分
 * （手首3軸）が本当に効いてくる。
 *
 * 作図の工程数はそのまま難易度の手がかりになる。手数が多い図ほど、
 * 解くのに必要な段数も多い。figure.operations がその数である。
 */

import { write } from './handwriting'

export type P3 = { x: number; y: number; z: number }

export type Stroke3 = {
  points: P3[]
  label: string
  kind: 'edge' | 'aux' | 'mark' | 'curve' | 'line' | 'solid'
  /** ペンの向き。省略時は板の法線 */
  approach?: P3
}

export type Figure = {
  id: string
  title: string
  /** この図から MathOS が切り出している族 */
  families: string[]
  dimension: 2 | 3
  strokes: Stroke3[]
  facts: { label: string; value: string }[]
}

const BOARD_Y = 55
const BOARD_Z = 46

/** 板面座標 (u,v) をワールドへ */
const onBoard = (u: number, v: number): P3 => ({
  x: u, y: BOARD_Y, z: BOARD_Z + v,
})

/** 空間座標。板より手前 (y が小さい) に置く */
const inSpace = (x: number, y: number, z: number): P3 => ({
  x, y: BOARD_Y - 26 + y, z: BOARD_Z + z,
})

const sub3 = (a: P3, b: P3): P3 => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
const add3 = (a: P3, b: P3): P3 => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z })
const scale3 = (a: P3, k: number): P3 => ({ x: a.x * k, y: a.y * k, z: a.z * k })
const mid3 = (a: P3, b: P3): P3 => scale3(add3(a, b), 0.5)
const norm3 = (a: P3) => Math.hypot(a.x, a.y, a.z)
const unit3 = (a: P3): P3 => {
  const n = norm3(a) || 1
  return { x: a.x / n, y: a.y / n, z: a.z / n }
}

/**
 * 点の印。
 *
 * 以前は十字を 1 本の折れ線で描いていた。ペンを上げないので
 * 「横棒 → 中心へ戻る → 縦棒」と繋がり、画面ではジグザグの走り書きに
 * 見えていた。1 筆で閉じる小さなひし形にすると、同じ「点を打った」
 * 意味のまま線が乱れない。
 */
function mark(p: P3, label: string, size = 1.2, approach?: P3): Stroke3 {
  const r = size * 0.9
  return {
    points: [
      { ...p, x: p.x - r },
      { ...p, z: p.z - r },
      { ...p, x: p.x + r },
      { ...p, z: p.z + r },
      { ...p, x: p.x - r },
    ],
    label, kind: 'mark', approach,
  }
}

function polyline(points: P3[], label: string, kind: Stroke3['kind'] = 'edge', approach?: P3): Stroke3 {
  return { points, label, kind, approach }
}

/** 板面上の円 */
function boardCircle(cu: number, cv: number, r: number, label: string): Stroke3 {
  const points: P3[] = []
  for (let i = 0; i <= 90; i++) {
    const t = (i / 90) * Math.PI * 2
    points.push(onBoard(cu + r * Math.cos(t), cv + r * Math.sin(t)))
  }
  return { points, label, kind: 'curve' }
}

// ---------------------------------------------------------------------------
// 平面figure: 九点円とオイラー線（13-14-15 のヘロン三角形）
// ---------------------------------------------------------------------------
function ninePointFigure(): Figure {
  const k = 2.9
  const shift = { u: -20, v: -13 }
  const T = (x: number, y: number) => onBoard(x * k + shift.u, y * k + shift.v)
  const A = T(0, 0), B = T(14, 0), C = T(5, 12)

  const foot = (p: P3, a: P3, b: P3): P3 => {
    const ab = sub3(b, a)
    const t = ((p.x - a.x) * ab.x + (p.z - a.z) * ab.z) / (ab.x ** 2 + ab.z ** 2)
    return add3(a, scale3(ab, t))
  }
  const circum = (a: P3, b: P3, c: P3): P3 => {
    const d = 2 * (a.x * (b.z - c.z) + b.x * (c.z - a.z) + c.x * (a.z - b.z))
    const s = (p: P3) => p.x * p.x + p.z * p.z
    return {
      x: (s(a) * (b.z - c.z) + s(b) * (c.z - a.z) + s(c) * (a.z - b.z)) / d,
      y: BOARD_Y,
      z: (s(a) * (c.x - b.x) + s(b) * (a.x - c.x) + s(c) * (b.x - a.x)) / d,
    }
  }
  const O = circum(A, B, C)
  const G = scale3(add3(add3(A, B), C), 1 / 3)
  const H = sub3(add3(add3(A, B), C), scale3(O, 2))
  const N = mid3(O, H)
  const R = Math.hypot(A.x - O.x, A.z - O.z)
  const Fa = foot(A, B, C), Fb = foot(B, C, A), Fc = foot(C, A, B)
  const Ma = mid3(B, C), Mb = mid3(C, A), Mc = mid3(A, B)
  const Pa = mid3(A, H), Pb = mid3(B, H), Pc = mid3(C, H)

  const perp = (m: P3, a: P3, b: P3, reach: number): Stroke3 => {
    const d = unit3({ x: -(b.z - a.z), y: 0, z: b.x - a.x })
    return polyline(
      [add3(m, scale3(d, -reach)), add3(m, scale3(d, reach))],
      '垂直二等分線', 'aux',
    )
  }

  return {
    id: 'nine_point',
    title: '九点円とオイラー線',
    families: [
      'traceback.triangle_centers.nine_point_radius_sq',
      'traceback.triangle_centers.euler_line_slope',
      'traceback.triangle_centers.OH_dist_sq',
    ],
    dimension: 2,
    strokes: [
      polyline([A, B], '三角形 ABC の辺 AB'),
      polyline([B, C], '辺 BC'),
      polyline([C, A], '辺 CA'),
      polyline([A, Fa], 'A から BC へ垂線', 'aux'), mark(Fa, '垂線の足 Fa'),
      polyline([B, Fb], 'B から CA へ垂線', 'aux'), mark(Fb, '垂線の足 Fb'),
      polyline([C, Fc], 'C から AB へ垂線', 'aux'), mark(Fc, '垂線の足 Fc'),
      mark(H, '3垂線の交点 = 垂心 H', 1.7),
      mark(Ma, '辺 BC の中点 Ma'), mark(Mb, '辺 CA の中点 Mb'),
      mark(Mc, '辺 AB の中点 Mc'),
      mark(Pa, 'AH の中点 Pa'), mark(Pb, 'BH の中点 Pb'), mark(Pc, 'CH の中点 Pc'),
      perp(Mc, A, B, 13), perp(Ma, B, C, 13),
      mark(O, '外心 O', 1.7), mark(G, '重心 G', 1.4), mark(N, 'OH の中点 N', 1.7),
      boardCircle(N.x, N.z - BOARD_Z, R / 2, '半径 R/2 の円が9点すべてを通る'),
      polyline(
        [add3(O, scale3(unit3(sub3(H, O)), -14)), add3(H, scale3(unit3(sub3(H, O)), 14))],
        'O, G, N, H は同一直線上（オイラー線）', 'line',
      ),
    ],
    facts: [
      { label: '外接円の半径 R', value: '65/8' },
      { label: '九点円の半径の平方', value: '4225/256' },
      { label: 'OH^2', value: '265/64' },
      { label: 'オイラー線の傾き', value: '3/16' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 平面figure: 双曲線と漸近線
// ---------------------------------------------------------------------------
function hyperbolaFigure(): Figure {
  const a = 8, b = 6
  const curve = (sign: number): P3[] => {
    const points: P3[] = []
    for (let i = -22; i <= 22; i++) {
      const t = i * 0.09
      points.push(onBoard(sign * a * Math.cosh(t), b * Math.sinh(t)))
    }
    return points
  }
  const t0 = 0.72
  const px = a * Math.cosh(t0), py = b * Math.sinh(t0)
  const P = onBoard(px, py)
  // 接線 x*px/a^2 - y*py/b^2 = 1 と漸近線 y = ±(b/a)x の交点
  const inter = (s: number): P3 => {
    const x = 1 / (px / (a * a) - (s * b / a) * (py / (b * b)))
    return onBoard(x, (s * b / a) * x)
  }
  const T1 = inter(1), T2 = inter(-1)
  const asym = (s: number): Stroke3 =>
    polyline([onBoard(-20, (s * b / a) * -20), onBoard(20, (s * b / a) * 20)],
      `漸近線 y = ${s > 0 ? '' : '-'}(b/a)x`, 'line')

  return {
    id: 'hyperbola',
    title: '双曲線・接線・漸近線',
    families: [
      'traceback.hyperbola_asymptote.asymptote_triangle_area',
      'traceback.hyperbola_asymptote.asymptote_distance_product',
      'traceback.hyperbola_asymptote.director_circle_radius_sq',
    ],
    dimension: 2,
    strokes: [
      polyline(curve(1), '双曲線の右枝', 'curve'),
      polyline(curve(-1), '双曲線の左枝', 'curve'),
      asym(1), asym(-1),
      mark(P, '双曲線上に点 P を取る', 1.4),
      polyline([T1, T2], 'P における接線', 'aux'),
      mark(T1, '接線と漸近線の交点 T1'),
      mark(T2, '接線と漸近線の交点 T2'),
      polyline([onBoard(0, 0), T1], 'O から T1 へ', 'aux'),
      polyline([onBoard(0, 0), T2], 'O から T2 へ', 'aux'),
      boardCircle(0, 0, Math.sqrt(Math.abs(a * a - b * b)), '2接線が直交する点の軌跡'),
    ],
    facts: [
      { label: '接線と2漸近線が囲む三角形の面積', value: 'ab（接点によらない）' },
      { label: '2漸近線までの距離の積', value: 'a^2b^2/(a^2+b^2)' },
      { label: '直交接線の軌跡の半径の平方', value: 'a^2-b^2' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 平面figure: 放物線の焦点弦
// ---------------------------------------------------------------------------
function parabolaFigure(): Figure {
  const p = 2.2
  const curve: P3[] = []
  for (let i = -26; i <= 26; i++) {
    const t = i * 0.12
    curve.push(onBoard(p * t * t - 10, 2 * p * t))
  }
  const t1 = 1.35, t2 = -1 / t1
  const A = onBoard(p * t1 * t1 - 10, 2 * p * t1)
  const B = onBoard(p * t2 * t2 - 10, 2 * p * t2)
  const F = onBoard(p - 10, 0)
  const tangentAt = (t: number): Stroke3 => {
    // ty = x + p t^2  →  x = t y - p t^2
    const ys = [-16, 16]
    return polyline(
      ys.map((y) => onBoard(t * y - p * t * t - 10, y)),
      `t=${t.toFixed(2)} における接線`, 'aux',
    )
  }
  const directrixX = -p - 10
  const T = onBoard(p * t1 * t2 - 10, p * (t1 + t2))

  return {
    id: 'parabola_focal',
    title: '放物線の焦点弦',
    families: [
      'traceback.parabola_focal_chord.reciprocal_focal_radii_sum',
      'traceback.parabola_focal_chord.tangent_intersection_x',
      'traceback.parabola_focal_chord.tangent_slope_product',
    ],
    dimension: 2,
    strokes: [
      polyline(curve, '放物線', 'curve'),
      polyline([onBoard(directrixX, -18), onBoard(directrixX, 18)], '準線', 'line'),
      mark(F, '焦点 F', 1.5),
      mark(A, '放物線上の点 A'),
      polyline([A, B], '焦点を通る弦 AB'),
      mark(B, 'もう一方の交点 B'),
      polyline([A, onBoard(directrixX, A.z - BOARD_Z)], 'A から準線へ垂線', 'aux'),
      polyline([B, onBoard(directrixX, B.z - BOARD_Z)], 'B から準線へ垂線', 'aux'),
      tangentAt(t1), tangentAt(t2),
      mark(T, '2接線の交点は準線上にある', 1.6),
      boardCircle(
        (A.x + B.x) / 2, (A.z + B.z) / 2 - BOARD_Z,
        Math.hypot(A.x - B.x, A.z - B.z) / 2,
        'AB を直径とする円は準線に接する',
      ),
    ],
    facts: [
      { label: '1/AF + 1/BF', value: '1/p（弦によらない）' },
      { label: '2接線の交点の x 座標', value: '-p（準線上）' },
      { label: '2接線の傾きの積', value: '-1（常に直交）' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 立体figure: 立方体の断面（正六角形）
// ---------------------------------------------------------------------------
function cubeSectionFigure(): Figure {
  const s = 11
  const V = (x: number, y: number, z: number) => inSpace(x * s, y * s, z * s)
  const c = [
    V(-1, -1, -1), V(1, -1, -1), V(1, 1, -1), V(-1, 1, -1),
    V(-1, -1, 1), V(1, -1, 1), V(1, 1, 1), V(-1, 1, 1),
  ]
  const edges: [number, number][] = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ]
  // 対角線 (-1,-1,-1)-(1,1,1) に垂直で中心を通る平面 → 正六角形の断面
  const hexagon = [
    mid3(c[0], c[1]), mid3(c[1], c[2]), mid3(c[2], c[6]),
    mid3(c[6], c[7]), mid3(c[7], c[4]), mid3(c[4], c[0]),
  ]
  const centre = inSpace(0, 0, 0)
  // ペンの向きは板向き（+y）を主にして、位置に応じて少しだけ傾ける。
  // 純粋な外向きにすると向きが球面全体に散らばり、辺から辺へ移るときに
  // 手首が 180 度反転する。実測で関節が 179.7 度跳んでいた。
  // 空間の線を引くのにペンが外を向いている必要はない。
  const outward = (p: P3): P3 =>
    unit3(add3(unit3(sub3(p, centre)), { x: 0, y: 3.4, z: 0 }))

  const strokes: Stroke3[] = edges.map(([i, j], index) =>
    polyline([c[i], c[j]], `立方体の辺 ${index + 1}/12`, 'solid', outward(mid3(c[i], c[j]))),
  )
  strokes.push(
    polyline([c[0], c[6]], '対角線 AG を引く', 'aux', outward(centre)),
    mark(centre, '対角線の中点 = 立方体の中心', 1.4, outward(centre)),
  )
  hexagon.forEach((p, i) => {
    strokes.push(mark(p, `辺の中点 ${i + 1}/6`, 1.0, outward(p)))
  })
  for (let i = 0; i < hexagon.length; i++) {
    const a = hexagon[i]
    const b = hexagon[(i + 1) % hexagon.length]
    strokes.push(polyline([a, b], `断面の辺 ${i + 1}/6（正六角形になる）`, 'edge', outward(mid3(a, b))))
  }

  return {
    id: 'cube_section',
    title: '立方体の対角線に垂直な断面',
    families: ['solid.cube_diagonal_section'],
    dimension: 3,
    strokes,
    facts: [
      { label: '断面の形', value: '正六角形' },
      { label: '一辺の長さ（立方体の一辺 a）', value: 'a/√2' },
      { label: '断面積', value: '3√3 a^2 / 4' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 立体figure: 正四面体と外接球
// ---------------------------------------------------------------------------
function tetrahedronFigure(): Figure {
  const s = 13
  const v = [
    inSpace(s, s, s), inSpace(s, -s, -s), inSpace(-s, s, -s), inSpace(-s, -s, s),
  ]
  const centre = inSpace(0, 0, 0)
  // 立方体と同じ理由で、板向きを主にした緩やかな傾きにする
  const outward = (p: P3): P3 =>
    unit3(add3(unit3(sub3(p, centre)), { x: 0, y: 3.4, z: 0 }))
  const edges: [number, number][] = [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]
  const strokes: Stroke3[] = edges.map(([i, j], index) =>
    polyline([v[i], v[j]], `正四面体の辺 ${index + 1}/6`, 'solid', outward(mid3(v[i], v[j]))),
  )
  strokes.push(mark(centre, '外接球の中心 = 重心', 1.5, outward(centre)))
  // 各面の重心へ下ろす（内接球の接点）
  const faces: [number, number, number][] = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]
  faces.forEach((face, index) => {
    const g = scale3(add3(add3(v[face[0]], v[face[1]]), v[face[2]]), 1 / 3)
    strokes.push(polyline([centre, g], `中心から面 ${index + 1} の重心へ`, 'aux', outward(g)))
    strokes.push(mark(g, `内接球の接点 ${index + 1}/4`, 1.0, outward(g)))
  })
  // 外接球を3つの大円で示す
  for (const axis of [0, 1, 2]) {
    const points: P3[] = []
    const R = norm3(sub3(v[0], centre))
    for (let i = 0; i <= 72; i++) {
      const t = (i / 72) * Math.PI * 2
      const cos = R * Math.cos(t)
      const sin = R * Math.sin(t)
      const p = axis === 0
        ? { x: centre.x + cos, y: centre.y + sin, z: centre.z }
        : axis === 1
          ? { x: centre.x + cos, y: centre.y, z: centre.z + sin }
          : { x: centre.x, y: centre.y + cos, z: centre.z + sin }
      points.push(p)
    }
    strokes.push(polyline(points, `外接球の大円 ${axis + 1}/3`, 'curve', { x: 0, y: 1, z: 0 }))
  }

  return {
    id: 'tetrahedron',
    title: '正四面体と外接球・内接球',
    families: ['solid.regular_tetrahedron_spheres'],
    dimension: 3,
    strokes,
    facts: [
      { label: '外接球の半径 R（一辺 a）', value: '√6 a / 4' },
      { label: '内接球の半径 r', value: '√6 a / 12' },
      { label: 'R : r', value: '3 : 1' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 平面figure: 円に内接する四角形（トレミー）
// ---------------------------------------------------------------------------
function cyclicQuadFigure(): Figure {
  const R = 15
  const angles = [-0.35, 1.15, 2.6, 4.35]
  const P = angles.map((t) => onBoard(R * Math.cos(t), R * Math.sin(t)))
  return {
    id: 'cyclic_quad',
    title: '円に内接する四角形（トレミー）',
    families: [
      'traceback.cyclic_quadrilateral.diagonal_product',
      'traceback.cyclic_quadrilateral.area',
      'traceback.cyclic_quadrilateral.circumradius_sq',
    ],
    dimension: 2,
    strokes: [
      boardCircle(0, 0, R, '円を描く'),
      mark(P[0], '円周上に A'), mark(P[1], 'B'), mark(P[2], 'C'), mark(P[3], 'D'),
      polyline([P[0], P[1]], '辺 AB'), polyline([P[1], P[2]], '辺 BC'),
      polyline([P[2], P[3]], '辺 CD'), polyline([P[3], P[0]], '辺 DA'),
      polyline([P[0], P[2]], '対角線 AC', 'aux'),
      polyline([P[1], P[3]], '対角線 BD', 'aux'),
      mark(onBoard(0, 0), '中心 O', 1.5),
      polyline([onBoard(0, 0), P[0]], '半径 OA', 'aux'),
    ],
    facts: [
      { label: 'トレミー', value: 'AC·BD = AB·CD + BC·DA' },
      { label: '面積（ブラーマグプタ）', value: '√((s-a)(s-b)(s-c)(s-d))' },
      { label: '外接円の半径', value: '√((ab+cd)(ac+bd)(ad+bc)) / (4S)' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 平面figure: 単位円に内接する正 n 角形
// ---------------------------------------------------------------------------
function regularPolygonFigure(n = 9): Figure {
  const R = 15
  const V = Array.from({ length: n }, (_, i) =>
    onBoard(R * Math.cos((2 * Math.PI * i) / n), R * Math.sin((2 * Math.PI * i) / n)))
  const strokes: Stroke3[] = [boardCircle(0, 0, R, '単位円を描く')]
  V.forEach((p, i) => strokes.push(mark(p, `頂点 z_${i}`, 0.9)))
  for (let i = 0; i < n; i++) {
    strokes.push(polyline([V[i], V[(i + 1) % n]], `正${n}角形の辺 ${i + 1}/${n}`))
  }
  for (let i = 1; i < n; i++) {
    strokes.push(polyline([V[0], V[i]], `z_0 から z_${i} への距離`, 'aux'))
  }
  return {
    id: 'regular_polygon',
    title: `単位円に内接する正 ${n} 角形`,
    families: [
      'traceback.regular_polygon.vertex_distance_product',
      'traceback.regular_polygon.sum_sq_pairwise',
      'traceback.regular_polygon.centroid_zero_subsets',
    ],
    dimension: 2,
    strokes,
    facts: [
      { label: 'z_0 から他の全頂点までの距離の積', value: 'n' },
      { label: '全頂点対の距離の平方和', value: 'n^2' },
      { label: '頂点ベクトルの総和', value: '0' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 平面figure: パラメータ曲線族の通過領域と包絡線
// ---------------------------------------------------------------------------
function passageRegionFigure(): Figure {
  const xLow = -1
  const xHigh = 2
  const tx = (value: number) => 18 * value - 9
  const ty = (value: number) => 7 * value
  const valueAt = (x: number, t: number) => x + 2 * x * t - t * t
  const lowerAt = (x: number) => (x <= 0.5 ? 3 * x - 1 : x)
  const upperAt = (x: number) => {
    if (x <= 0) return x
    if (x <= 1) return x + x * x
    return 3 * x - 1
  }
  const curve = (fn: (x: number) => number, samples = 90): P3[] =>
    Array.from({ length: samples + 1 }, (_, index) => {
      const x = xLow + ((xHigh - xLow) * index) / samples
      return onBoard(tx(x), ty(fn(x)))
    })

  const strokes: Stroke3[] = []
  for (const parameter of [0, 0.25, 0.5, 0.75, 1]) {
    strokes.push(polyline(
      curve((x) => valueAt(x, parameter)),
      `曲線族 t=${parameter.toFixed(2)}`,
      'curve',
    ))
  }
  strokes.push(
    polyline(curve(lowerAt), '各 x における最小値の境界', 'line'),
    polyline(curve(upperAt), '各 x における最大値の境界（包絡線を含む）', 'line'),
  )
  for (const x of [-0.75, -0.25, 0.25, 0.75, 1.25, 1.75]) {
    strokes.push(polyline(
      [
        onBoard(tx(x), ty(lowerAt(x))),
        onBoard(tx(x), ty(upperAt(x))),
      ],
      `x=${x.toFixed(2)} の縦断面`,
      'aux',
    ))
  }
  strokes.push(
    mark(onBoard(tx(0), ty(0)), '停留点が区間へ入る点 x=0'),
    mark(onBoard(tx(0.5), ty(0.5)), '下端が切り替わる点 x=1/2'),
    mark(onBoard(tx(1), ty(2)), '停留点が区間を出る点 x=1'),
  )

  return {
    id: 'passage_region',
    title: '曲線族の通過領域・包絡線',
    families: [
      'passage_region.quadratic_interval_image',
      'passage_region.quadratic_interval_area',
      'passage_region.quadratic_envelope_boundary',
    ],
    dimension: 2,
    strokes,
    facts: [
      { label: '曲線族', value: 'y=x+2xt-t², 0≤t≤1' },
      { label: '上側境界（0≤x≤1）', value: 'y=x+x²' },
      { label: '0≤x≤1 における通過領域の面積', value: '7/12' },
    ],
  }
}

/**
 * 図だけでなく解説を書く。予備校の板書と同じ構成にする。
 *
 *   見出し → 図 → 「余弦定理より」→ 式 → 答
 *
 * 図と文章が同じ面に並び、文章が図を指す。LLM が書けないのはここ。
 */
function cosineSolutionFigure(): Figure {
  const strokes: Stroke3[] = []

  // 見出し
  strokes.push(...write('問題', { u: -46, v: 30, size: 6.5 }))

  // 三角形 AB=7, BC=5, CA=3 を実際の比で置く
  const A = onBoard(-40, 2)
  const B = onBoard(-12, 2)
  // AB=7 を 28 単位に取る。CA=3→12, BC=5→20
  const scale = 4
  const cosA = (49 + 9 - 25) / (2 * 7 * 3)      // 11/14
  const sinA = Math.sqrt(1 - cosA * cosA)
  const C = onBoard(-40 + 3 * scale * cosA, 2 + 3 * scale * sinA)

  strokes.push({ points: [A, B], label: '辺 AB', kind: 'edge' })
  strokes.push({ points: [B, C], label: '辺 BC', kind: 'edge' })
  strokes.push({ points: [C, A], label: '辺 CA', kind: 'edge' })

  // 頂点の名前と辺の長さ
  strokes.push(...write('A', { u: A.x - 3.4, v: A.z - BOARD_Z - 3.6, size: 3 }))
  strokes.push(...write('B', { u: B.x + 1.2, v: B.z - BOARD_Z - 3.6, size: 3 }))
  strokes.push(...write('C', { u: C.x - 1.0, v: C.z - BOARD_Z + 1.4, size: 3 }))
  strokes.push(...write('7', { u: (A.x + B.x) / 2 - 1, v: -3.2, size: 2.8 }))
  strokes.push(...write('3', { u: (A.x + C.x) / 2 - 4.2, v: (A.z + C.z) / 2 - BOARD_Z, size: 2.8 }))
  strokes.push(...write('5', { u: (B.x + C.x) / 2 + 1.4, v: (B.z + C.z) / 2 - BOARD_Z, size: 2.8 }))

  // 解説。右側に縦に流す
  strokes.push(...write('解答', { u: 4, v: 30, size: 6.5 }))
  strokes.push(...write('余弦定理より', { u: 4, v: 19, size: 5.2 }))
  strokes.push(...write('cosA=(49+9-25)/(2·7·3)', { u: 4, v: 9, size: 4.4 }))
  strokes.push(...write('=11/14', { u: 12, v: -1, size: 4.4 }))

  return {
    id: 'solution_cosine',
    title: '解説板書：余弦定理',
    families: ['traceback.triangle_centers'],
    dimension: 2,
    strokes,
    facts: [
      { label: '答', value: '11/14' },
      { label: '書いた画数', value: String(strokes.length) },
    ],
  }
}

export const FIGURES: Figure[] = [
  cosineSolutionFigure(),
  ninePointFigure(),
  hyperbolaFigure(),
  parabolaFigure(),
  cyclicQuadFigure(),
  regularPolygonFigure(9),
  passageRegionFigure(),
  cubeSectionFigure(),
  tetrahedronFigure(),
]

/** 作図の工程数と経由点数。工程が多いほど手数の多い問題である */
export function figureComplexity(figure: Figure) {
  const operations = figure.strokes.length
  const points = figure.strokes.reduce(
    (sum, stroke) => sum + resample3(stroke.points).length, 0,
  )
  const marks = figure.strokes.filter((s) => s.kind === 'mark').length
  const auxiliary = figure.strokes.filter((s) => s.kind === 'aux').length
  return { operations, points, marks, auxiliary }
}

/** ストロークを一定間隔で刻む */
export function resample3(points: P3[], step = 1.3): P3[] {
  if (points.length < 2) return points
  const out: P3[] = [points[0]]
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    const length = norm3(sub3(b, a))
    const n = Math.max(1, Math.ceil(length / step))
    for (let j = 1; j <= n; j++) {
      out.push({
        x: a.x + ((b.x - a.x) * j) / n,
        y: a.y + ((b.y - a.y) * j) / n,
        z: a.z + ((b.z - a.z) * j) / n,
      })
    }
  }
  return out
}
