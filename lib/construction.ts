/**
 * 作図の手順を、板面上の筆跡（ストローク）に落とす。
 *
 * 描くのは九点円とオイラー線。三角形の
 *   3辺の中点 / 3つの垂線の足 / 各頂点と垂心の中点
 * という 9 点が 1 つの円上に乗り、さらに外心・重心・九点円の中心・垂心が
 * 1 直線に並ぶ。工程が長く、途中で現れる点が問題文には出てこない。
 *
 * これは MathOS の traceback.triangle_centers 構築そのもので、
 * そこから切り出されるノード（九点円の半径の平方・オイラー線の傾き・OH^2）
 * が問題になっている。図は問題のために後から描いた挿絵ではない。
 */

export type P2 = { x: number; y: number }

export type Stroke = {
  /** 板面上の点列（この順に描く） */
  points: P2[]
  /** 板書の脇に出す説明 */
  label: string
  /** 線の種類 */
  kind: 'edge' | 'aux' | 'mark' | 'circle' | 'line'
}

const sub = (a: P2, b: P2): P2 => ({ x: a.x - b.x, y: a.y - b.y })
const add = (a: P2, b: P2): P2 => ({ x: a.x + b.x, y: a.y + b.y })
const scale = (a: P2, k: number): P2 => ({ x: a.x * k, y: a.y * k })
const mid = (a: P2, b: P2): P2 => scale(add(a, b), 0.5)
const dot = (a: P2, b: P2) => a.x * b.x + a.y * b.y

/** 点 p から直線 ab への垂線の足 */
function foot(p: P2, a: P2, b: P2): P2 {
  const ab = sub(b, a)
  const t = dot(sub(p, a), ab) / dot(ab, ab)
  return add(a, scale(ab, t))
}

function circumcenter(a: P2, b: P2, c: P2): P2 {
  const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
  const a2 = a.x * a.x + a.y * a.y
  const b2 = b.x * b.x + b.y * b.y
  const c2 = c.x * c.x + c.y * c.y
  return {
    x: (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d,
    y: (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d,
  }
}

/** 点を打つ印（小さな十字） */
function markStroke(p: P2, label: string, size = 1.1): Stroke {
  return {
    points: [
      { x: p.x - size, y: p.y },
      { x: p.x + size, y: p.y },
      { x: p.x, y: p.y },
      { x: p.x, y: p.y - size },
      { x: p.x, y: p.y + size },
    ],
    label,
    kind: 'mark',
  }
}

function circleStroke(center: P2, radius: number, label: string): Stroke {
  const points: P2[] = []
  const segments = 96
  for (let i = 0; i <= segments; i++) {
    const t = (i / segments) * Math.PI * 2
    points.push({
      x: center.x + radius * Math.cos(t),
      y: center.y + radius * Math.sin(t),
    })
  }
  return { points, label, kind: 'circle' }
}

/** 直線 ab を両側へ伸ばした線分 */
function extendedLine(a: P2, b: P2, reach: number, label: string): Stroke {
  const dir = sub(b, a)
  const n = Math.hypot(dir.x, dir.y) || 1
  const u = scale(dir, 1 / n)
  return {
    points: [add(a, scale(u, -reach)), add(b, scale(u, reach))],
    label,
    kind: 'line',
  }
}

/**
 * 13-14-15 のヘロン三角形から、九点円とオイラー線を作図する。
 * 板面に収まるよう平行移動と拡大縮小をかける。
 */
export function ninePointConstruction(): {
  strokes: Stroke[]
  facts: { label: string; value: string }[]
} {
  // 元の三角形（面積 84, r = 4, R = 65/8）
  const raw: [P2, P2, P2] = [
    { x: 0, y: 0 },
    { x: 14, y: 0 },
    { x: 5, y: 12 },
  ]
  // 板面へ写す
  const k = 3.1
  const shift = { x: -21, y: -14 }
  const T = (p: P2): P2 => ({ x: p.x * k + shift.x, y: p.y * k + shift.y })
  const [A, B, C] = raw.map(T) as [P2, P2, P2]

  const O = circumcenter(A, B, C)
  const G = scale(add(add(A, B), C), 1 / 3)
  const H = sub(add(add(A, B), C), scale(O, 2)) // オイラーの関係 H = A+B+C-2O
  const N = mid(O, H)
  const R = Math.hypot(A.x - O.x, A.y - O.y)

  const Fa = foot(A, B, C)
  const Fb = foot(B, C, A)
  const Fc = foot(C, A, B)
  const Ma = mid(B, C)
  const Mb = mid(C, A)
  const Mc = mid(A, B)
  const Pa = mid(A, H)
  const Pb = mid(B, H)
  const Pc = mid(C, H)

  const strokes: Stroke[] = [
    { points: [A, B], label: '三角形 ABC を取る（辺 AB）', kind: 'edge' },
    { points: [B, C], label: '辺 BC', kind: 'edge' },
    { points: [C, A], label: '辺 CA', kind: 'edge' },

    { points: [A, Fa], label: 'A から BC へ垂線を下ろす', kind: 'aux' },
    markStroke(Fa, '垂線の足 Fa'),
    { points: [B, Fb], label: 'B から CA へ垂線を下ろす', kind: 'aux' },
    markStroke(Fb, '垂線の足 Fb'),
    { points: [C, Fc], label: 'C から AB へ垂線を下ろす', kind: 'aux' },
    markStroke(Fc, '垂線の足 Fc'),
    markStroke(H, '3垂線は1点で交わる → 垂心 H', 1.6),

    markStroke(Ma, '辺 BC の中点 Ma'),
    markStroke(Mb, '辺 CA の中点 Mb'),
    markStroke(Mc, '辺 AB の中点 Mc'),

    markStroke(Pa, 'AH の中点 Pa'),
    markStroke(Pb, 'BH の中点 Pb'),
    markStroke(Pc, 'CH の中点 Pc'),

    {
      points: [
        add(Mc, scale({ x: -(B.y - A.y), y: B.x - A.x }, -0.5)),
        add(Mc, scale({ x: -(B.y - A.y), y: B.x - A.x }, 0.5)),
      ],
      label: 'AB の垂直二等分線',
      kind: 'aux',
    },
    {
      points: [
        add(Ma, scale({ x: -(C.y - B.y), y: C.x - B.x }, -0.5)),
        add(Ma, scale({ x: -(C.y - B.y), y: C.x - B.x }, 0.5)),
      ],
      label: 'BC の垂直二等分線',
      kind: 'aux',
    },
    markStroke(O, '2本の交点 → 外心 O', 1.6),
    markStroke(G, '重心 G', 1.4),
    markStroke(N, 'OH の中点 N', 1.6),

    circleStroke(N, R / 2, 'N を中心に半径 R/2 の円 → 9点すべてを通る'),
    extendedLine(O, H, 10, 'O, G, N, H は同一直線上（オイラー線）'),
  ]

  const facts = [
    { label: '外接円の半径 R', value: '65/8' },
    { label: '九点円の半径', value: 'R/2 = 65/16' },
    { label: '九点円の半径の平方', value: '4225/256' },
    { label: 'OH^2 = 9R^2 - (a^2+b^2+c^2)', value: '265/64' },
    { label: 'オイラー線の傾き', value: '3/16' },
  ]
  return { strokes, facts }
}

/** ストロークを一定間隔で細かく刻む（アームの経由点にする） */
export function resample(points: P2[], step = 1.1): P2[] {
  if (points.length < 2) return points
  const out: P2[] = [points[0]]
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    const length = Math.hypot(b.x - a.x, b.y - a.y)
    const n = Math.max(1, Math.ceil(length / step))
    for (let j = 1; j <= n; j++) {
      out.push({
        x: a.x + ((b.x - a.x) * j) / n,
        y: a.y + ((b.y - a.y) * j) / n,
      })
    }
  }
  return out
}
