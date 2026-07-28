/**
 * 最小ジャーク軌道。
 *
 * ジャーク（加加速度）は加速度の時間微分で、これが大きいと実機では
 * 振動が出て、見た目にもカクつく。ヒトの到達運動が
 *   J = ∫ |d^3 q / dt^3|^2 dt
 * を最小にする軌道に一致することが知られており（Flash & Hogan 1985）、
 * 2点間なら 5 次多項式 10τ^3 - 15τ^4 + 6τ^5 が厳密解になる。
 *
 * ここで必要なのは 2 点間ではなく、作図の経由点を何百個も通る軌道である。
 * 経由点を固定したうえで J を最小にする軌道は「各区間が 5 次多項式で、
 * 節点で 4 階微分まで連続」な spline になる。これを厳密に構成する:
 *
 *   * 区間 i の 5 次多項式は両端の (位置, 速度, 加速度) で一意に決まる
 *   * 位置は与件、両端の速度・加速度は 0（静止して始まり静止して終わる）
 *   * 内部節点で「ジャークの連続」「スナップ(4階)の連続」を課すと、
 *     未知数 (v_i, a_i) と方程式の数がちょうど一致する
 *
 * 結果として係数行列は 2x2 ブロックの三重対角になるので、
 * ブロック Thomas 法で O(n) で解ける。近似ではなく厳密解である。
 */

export type QuinticSegment = {
  /** c0..c5、区間内の経過時間 s∈[0,h] に対して p(s)=Σ c_k s^k */
  c: number[]
  h: number
}

/** 3x3 の連立一次方程式を解く（部分ピボット付き） */
function solve3(a: number[][], b: number[]): number[] {
  const m = a.map((row, i) => [...row, b[i]])
  for (let col = 0; col < 3; col++) {
    let pivot = col
    for (let r = col + 1; r < 3; r++) {
      if (Math.abs(m[r][col]) > Math.abs(m[pivot][col])) pivot = r
    }
    ;[m[col], m[pivot]] = [m[pivot], m[col]]
    const d = m[col][col]
    for (let c = col; c < 4; c++) m[col][c] /= d
    for (let r = 0; r < 3; r++) {
      if (r === col) continue
      const f = m[r][col]
      for (let c = col; c < 4; c++) m[r][c] -= f * m[col][c]
    }
  }
  return [m[0][3], m[1][3], m[2][3]]
}

/**
 * 両端の (p, v, a) を満たす 5 次多項式の係数。
 * c0..c2 は始点で決まり、c3..c5 は終点条件の 3 元連立で決まる。
 */
export function quinticCoefficients(
  p0: number, v0: number, a0: number,
  p1: number, v1: number, a1: number,
  h: number,
): number[] {
  const c0 = p0
  const c1 = v0
  const c2 = a0 / 2
  const h2 = h * h
  const h3 = h2 * h
  const h4 = h3 * h
  const h5 = h4 * h
  const rhs = [
    p1 - (c0 + c1 * h + c2 * h2),
    v1 - (c1 + 2 * c2 * h),
    a1 - 2 * c2,
  ]
  const matrix = [
    [h3, h4, h5],
    [3 * h2, 4 * h3, 5 * h4],
    [6 * h, 12 * h2, 20 * h3],
  ]
  const [c3, c4, c5] = solve3(matrix, rhs)
  return [c0, c1, c2, c3, c4, c5]
}

/**
 * 係数が両端データ (p0,v0,a0,p1,v1,a1) にどう線形依存するかを返す。
 * 3x6 行列。これを使って連続条件を組み立てる。
 */
function coefficientBasis(h: number): number[][] {
  const basis: number[][] = [[], [], []]
  for (let k = 0; k < 6; k++) {
    const unit = [0, 0, 0, 0, 0, 0]
    unit[k] = 1
    const c = quinticCoefficients(unit[0], unit[1], unit[2], unit[3], unit[4], unit[5], h)
    basis[0][k] = c[3]
    basis[1][k] = c[4]
    basis[2][k] = c[5]
  }
  return basis
}

/** 2x2 行列演算 */
type M2 = [number, number, number, number] // 行優先
const m2mul = (a: M2, b: M2): M2 => [
  a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
  a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
]
const m2vec = (a: M2, v: [number, number]): [number, number] => [
  a[0] * v[0] + a[1] * v[1],
  a[2] * v[0] + a[3] * v[1],
]
const m2inv = (a: M2): M2 => {
  const det = a[0] * a[3] - a[1] * a[2]
  if (Math.abs(det) < 1e-14) return [1, 0, 0, 1]
  return [a[3] / det, -a[1] / det, -a[2] / det, a[0] / det]
}
const m2sub = (a: M2, b: M2): M2 => [a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3]]

/**
 * 経由点列を通る最小ジャーク軌道を構成する。
 *
 * points: 通過すべき位置（1 次元）
 * durations: 各区間の所要時間（長さ points.length - 1）
 *
 * 返り値は各区間の 5 次多項式。始点と終点では速度・加速度が 0 になる。
 */
export function minimumJerkSpline(
  points: number[],
  durations: number[],
): QuinticSegment[] {
  const n = points.length - 1 // 区間数
  if (n <= 0) return []
  if (n === 1) {
    return [{
      c: quinticCoefficients(points[0], 0, 0, points[1], 0, 0, durations[0]),
      h: durations[0],
    }]
  }

  const basis = durations.map((h) => coefficientBasis(h))

  // 未知数 x_i = (v_i, a_i), i = 1..n-1
  // 節点 i でのジャーク連続 / スナップ連続:
  //   6c3^{i-1} + 24c4^{i-1} h + 60c5^{i-1} h^2 = 6c3^{i}
  //   24c4^{i-1} + 120c5^{i-1} h                = 24c4^{i}
  // c は (p,v,a) に線形なので、これは x_{i-1}, x_i, x_{i+1} の三重対角になる。
  const size = n - 1
  const A: M2[] = new Array(size)
  const B: M2[] = new Array(size)
  const C: M2[] = new Array(size)
  const d: [number, number][] = new Array(size)

  for (let i = 1; i <= size; i++) {
    const left = basis[i - 1]
    const right = basis[i]
    const hL = durations[i - 1]

    // 左区間の終端でのジャーク/スナップ係数（(p0,v0,a0,p1,v1,a1) に対する行）
    const jerkLeft = left[0].map((_, k) =>
      6 * left[0][k] + 24 * left[1][k] * hL + 60 * left[2][k] * hL * hL)
    const snapLeft = left[0].map((_, k) =>
      24 * left[1][k] + 120 * left[2][k] * hL)
    // 右区間の始端でのジャーク/スナップ
    const jerkRight = right[0].map((_, k) => 6 * right[0][k])
    const snapRight = right[0].map((_, k) => 24 * right[1][k])

    // 左区間の両端は (p_{i-1}, v_{i-1}, a_{i-1}, p_i, v_i, a_i)
    // 右区間の両端は (p_i, v_i, a_i, p_{i+1}, v_{i+1}, a_{i+1})
    // 未知は v,a のみ。p は既知なので右辺へ移す。
    const aBlock: M2 = [jerkLeft[1], jerkLeft[2], snapLeft[1], snapLeft[2]]
    const bBlock: M2 = m2sub(
      [jerkLeft[4], jerkLeft[5], snapLeft[4], snapLeft[5]],
      [jerkRight[1], jerkRight[2], snapRight[1], snapRight[2]],
    )
    const cBlock: M2 = [-jerkRight[4], -jerkRight[5], -snapRight[4], -snapRight[5]]

    // 既知項（位置）を右辺へ
    const known =
      -(jerkLeft[0] * points[i - 1] + jerkLeft[3] * points[i]
        - jerkRight[0] * points[i] - jerkRight[3] * points[i + 1])
    const knownSnap =
      -(snapLeft[0] * points[i - 1] + snapLeft[3] * points[i]
        - snapRight[0] * points[i] - snapRight[3] * points[i + 1])

    A[i - 1] = aBlock
    B[i - 1] = bBlock
    C[i - 1] = cBlock
    d[i - 1] = [known, knownSnap]
  }

  // 両端は静止（v=a=0）なので、最初の A と最後の C は寄与しない
  A[0] = [0, 0, 0, 0]
  C[size - 1] = [0, 0, 0, 0]

  // ブロック Thomas 法
  const cPrime: M2[] = new Array(size)
  const dPrime: [number, number][] = new Array(size)
  let inv = m2inv(B[0])
  cPrime[0] = m2mul(inv, C[0])
  dPrime[0] = m2vec(inv, d[0])
  for (let i = 1; i < size; i++) {
    const denominator = m2sub(B[i], m2mul(A[i], cPrime[i - 1]))
    inv = m2inv(denominator)
    cPrime[i] = m2mul(inv, C[i])
    const rhs: [number, number] = [
      d[i][0] - (A[i][0] * dPrime[i - 1][0] + A[i][1] * dPrime[i - 1][1]),
      d[i][1] - (A[i][2] * dPrime[i - 1][0] + A[i][3] * dPrime[i - 1][1]),
    ]
    dPrime[i] = m2vec(inv, rhs)
  }
  const x: [number, number][] = new Array(size)
  x[size - 1] = dPrime[size - 1]
  for (let i = size - 2; i >= 0; i--) {
    x[i] = [
      dPrime[i][0] - (cPrime[i][0] * x[i + 1][0] + cPrime[i][1] * x[i + 1][1]),
      dPrime[i][1] - (cPrime[i][2] * x[i + 1][0] + cPrime[i][3] * x[i + 1][1]),
    ]
  }

  // 節点の速度・加速度がそろったので各区間を組み立てる
  const velocity = [0, ...x.map((v) => v[0]), 0]
  const acceleration = [0, ...x.map((v) => v[1]), 0]
  const segments: QuinticSegment[] = []
  for (let i = 0; i < n; i++) {
    segments.push({
      c: quinticCoefficients(
        points[i], velocity[i], acceleration[i],
        points[i + 1], velocity[i + 1], acceleration[i + 1],
        durations[i],
      ),
      h: durations[i],
    })
  }
  return segments
}

/** 区間内の位置・速度・加速度・ジャークを評価する */
export function evaluate(segment: QuinticSegment, s: number) {
  const [c0, c1, c2, c3, c4, c5] = segment.c
  const s2 = s * s
  const s3 = s2 * s
  const s4 = s3 * s
  const s5 = s4 * s
  return {
    position: c0 + c1 * s + c2 * s2 + c3 * s3 + c4 * s4 + c5 * s5,
    velocity: c1 + 2 * c2 * s + 3 * c3 * s2 + 4 * c4 * s3 + 5 * c5 * s4,
    acceleration: 2 * c2 + 6 * c3 * s + 12 * c4 * s2 + 20 * c5 * s3,
    jerk: 6 * c3 + 24 * c4 * s + 60 * c5 * s2,
  }
}

/** 軌道全体のジャーク二乗積分 ∫ jerk^2 dt（厳密に多項式積分で出す） */
export function jerkCost(segments: QuinticSegment[]): number {
  let total = 0
  for (const segment of segments) {
    const [, , , c3, c4, c5] = segment.c
    const h = segment.h
    // jerk(s) = 6c3 + 24c4 s + 60c5 s^2
    const A = 6 * c3
    const B = 24 * c4
    const C = 60 * c5
    // ∫0^h (A + Bs + Cs^2)^2 ds
    total +=
      A * A * h +
      A * B * h ** 2 +
      ((B * B + 2 * A * C) * h ** 3) / 3 +
      ((B * C) * h ** 4) / 2 +
      (C * C * h ** 5) / 5
  }
  return total
}

/** 多関節ぶんまとめて解く。関節ごとに独立に最小ジャークで結ぶ */
export function planJointTrajectory(
  waypoints: number[][],
  durations: number[],
): QuinticSegment[][] {
  const dof = waypoints[0]?.length ?? 0
  const perJoint: QuinticSegment[][] = []
  for (let j = 0; j < dof; j++) {
    perJoint.push(
      minimumJerkSpline(waypoints.map((w) => w[j]), durations),
    )
  }
  return perJoint
}

/** 時刻 t（軌道全体の経過時間）での関節角を返す */
export function sampleAt(
  perJoint: QuinticSegment[][],
  durations: number[],
  t: number,
): { joints: number[]; jerk: number[]; segment: number } {
  let index = 0
  let rest = t
  while (index < durations.length - 1 && rest > durations[index]) {
    rest -= durations[index]
    index++
  }
  rest = Math.max(0, Math.min(durations[index] ?? 0, rest))
  const joints: number[] = []
  const jerk: number[] = []
  for (const segments of perJoint) {
    const segment = segments[index]
    if (!segment) { joints.push(0); jerk.push(0); continue }
    const value = evaluate(segment, rest)
    joints.push(value.position)
    jerk.push(value.jerk)
  }
  return { joints, jerk, segment: index }
}

/**
 * 経由点間の所要時間を、関節の移動量から決める。
 * 大きく動く区間ほど時間を与えると、関節速度の上限を守りやすい。
 */
export function timeParameterize(
  waypoints: number[][],
  maxJointSpeed = 2.4, // rad/s。産業用6軸の関節速度は概ね 2-3 rad/s
  minStep = 0.03,
): number[] {
  const durations: number[] = []
  for (let i = 1; i < waypoints.length; i++) {
    let peak = 0
    for (let j = 0; j < waypoints[i].length; j++) {
      peak = Math.max(peak, Math.abs(waypoints[i][j] - waypoints[i - 1][j]))
    }
    // 5次多項式は平均速度の 1.875 倍が最大速度になるので、その分を見込む
    durations.push(Math.max(minStep, (peak / maxJointSpeed) * 1.875))
  }
  return durations
}

/** 軌道全体での関節速度・加速度・ジャークのピーク（実機の制約と比べるため） */
export function peakDerivatives(
  perJoint: QuinticSegment[][],
  samplesPerSegment = 12,
): { speed: number; acceleration: number; jerk: number } {
  let speed = 0
  let acceleration = 0
  let jerk = 0
  for (const segments of perJoint) {
    for (const segment of segments) {
      for (let i = 0; i <= samplesPerSegment; i++) {
        const value = evaluate(segment, (i / samplesPerSegment) * segment.h)
        speed = Math.max(speed, Math.abs(value.velocity))
        acceleration = Math.max(acceleration, Math.abs(value.acceleration))
        jerk = Math.max(jerk, Math.abs(value.jerk))
      }
    }
  }
  return { speed, acceleration, jerk }
}
