/**
 * 6軸多関節アーム（球面手首）の運動学。
 *
 * 構成は産業用アームの標準形に合わせた:
 *   J1 基部旋回 / J2 肩 / J3 肘 / J4,J5,J6 手首（3軸が1点で交わる球面手首）
 *
 * 手首が球面であることが Pieper の条件で、これを満たすと逆運動学が
 *   「位置は J1-J3」「姿勢は J4-J6」
 * に分離でき、数値解法ではなく閉形式で解ける（kinematic decoupling）。
 *
 * 変換は Denavit-Hartenberg 記法:
 *   A_i = Rz(theta_i) * Tz(d_i) * Tx(a_i) * Rx(alpha_i)
 *
 * この実装は three.js に依存しない。行列を自前で持つのは、
 * 順運動学と逆運動学が本当に整合しているかを node のテストで確かめるため。
 */

export type Mat4 = number[] // 16要素、行優先
export type Vec3 = [number, number, number]

/** DH パラメータ（1関節ぶん）。theta は関節変数なのでオフセットのみ持つ */
export type DHLink = {
  a: number
  alpha: number
  d: number
  thetaOffset: number
}

/** 標準的な 6R アームの寸法（単位は cm 相当の任意単位） */
export const ARM: DHLink[] = [
  { a: 0, alpha: Math.PI / 2, d: 34, thetaOffset: 0 },   // J1 基部旋回
  { a: 44, alpha: 0, d: 0, thetaOffset: 0 },             // J2 肩
  { a: 0, alpha: Math.PI / 2, d: 0, thetaOffset: 0 },    // J3 肘
  { a: 0, alpha: -Math.PI / 2, d: 43, thetaOffset: 0 },  // J4 手首ロール
  { a: 0, alpha: Math.PI / 2, d: 0, thetaOffset: 0 },    // J5 手首ピッチ
  { a: 0, alpha: 0, d: 12, thetaOffset: 0 },             // J6 手先ロール
]

export const A2 = ARM[1].a   // 肩→肘
export const D4 = ARM[3].d   // 肘→手首中心
export const D1 = ARM[0].d   // 基部高さ
export const D6 = ARM[5].d   // 手首中心→ペン先

export function identity(): Mat4 {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
}

export function multiply(m: Mat4, n: Mat4): Mat4 {
  const out = new Array(16).fill(0) as Mat4
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 4; c++) {
      let sum = 0
      for (let k = 0; k < 4; k++) sum += m[r * 4 + k] * n[k * 4 + c]
      out[r * 4 + c] = sum
    }
  }
  return out
}

/** DH の 1 リンク変換 */
export function dhMatrix(link: DHLink, theta: number): Mat4 {
  const t = theta + link.thetaOffset
  const ct = Math.cos(t)
  const st = Math.sin(t)
  const ca = Math.cos(link.alpha)
  const sa = Math.sin(link.alpha)
  return [
    ct, -st * ca, st * sa, link.a * ct,
    st, ct * ca, -ct * sa, link.a * st,
    0, sa, ca, link.d,
    0, 0, 0, 1,
  ]
}

/** 順運動学。各関節の原点までの変換をすべて返す（描画用） */
export function forwardAll(joints: number[]): Mat4[] {
  const frames: Mat4[] = []
  let acc = identity()
  for (let i = 0; i < ARM.length; i++) {
    acc = multiply(acc, dhMatrix(ARM[i], joints[i] ?? 0))
    frames.push(acc)
  }
  return frames
}

export function forward(joints: number[]): Mat4 {
  const frames = forwardAll(joints)
  return frames[frames.length - 1]
}

export function positionOf(m: Mat4): Vec3 {
  return [m[3], m[7], m[11]]
}

/** 3x3 回転部分を取り出す（行優先の9要素） */
export function rotationOf(m: Mat4): number[] {
  return [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]]
}

function rotMul(a: number[], b: number[]): number[] {
  const out = new Array(9).fill(0)
  for (let r = 0; r < 3; r++)
    for (let c = 0; c < 3; c++) {
      let s = 0
      for (let k = 0; k < 3; k++) s += a[r * 3 + k] * b[k * 3 + c]
      out[r * 3 + c] = s
    }
  return out
}

function rotTranspose(a: number[]): number[] {
  return [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]]
}

/**
 * 逆運動学（閉形式）。
 *
 * target: ペン先の位置、approach: ペンが向く向き（板の法線の逆）、
 * ペンの軸回りは自由なので、板の上向きから残り 1 自由度を決める。
 *
 * 1) 手首中心 p_w = p_e - d6 * approach
 * 2) theta1 = atan2(y_w, x_w)
 * 3) 肩-肘-手首の三角形に余弦定理（肘の上/下は elbowUp で選ぶ）
 * 4) R36 = R03^T * R から ZYZ オイラー角で theta4,5,6
 */
export function inverse(
  target: Vec3,
  approach: Vec3,
  boardUp: Vec3,
  elbowUp = true,
  baseFlip = false,
  wristFlip = false,
  seedTheta4 = 0,
): number[] | null {
  const [ax, ay, az] = normalize(approach)
  // 1) 手首中心
  const wx = target[0] - D6 * ax
  const wy = target[1] - D6 * ay
  const wz = target[2] - D6 * az

  // 2) 基部旋回。反対向きに振って裏から届く解も同じ点に到達する
  const theta1 = Math.atan2(wy, wx) + (baseFlip ? Math.PI : 0)

  // 3) 肩・肘。この DH 表では手首中心が
  //      R = a2*cos(t2) + d4*sin(t2+t3)
  //      Z = a2*sin(t2) - d4*cos(t2+t3)
  //    となる。(sin(t2+t3), -cos(t2+t3)) = (cos w, sin w), w = t2+t3-pi/2 と
  //    置くと、長さ a2 と d4 の平面 2 リンクそのものになる。
  //    よって余弦定理の値は cos(w - t2) = sin(t3) に等しい。
  const r = (baseFlip ? -1 : 1) * Math.hypot(wx, wy)
  const s = wz - D1
  const distSq = r * r + s * s
  const sin3 = (distSq - A2 * A2 - D4 * D4) / (2 * A2 * D4)
  if (!Number.isFinite(sin3) || Math.abs(sin3) > 1) return null // 到達不能
  const cos3 = (elbowUp ? 1 : -1) * Math.sqrt(Math.max(0, 1 - sin3 * sin3))
  const theta3 = Math.atan2(sin3, cos3)
  const theta2 =
    Math.atan2(s, r) - Math.atan2(-D4 * cos3, A2 + D4 * sin3)

  // 4) 姿勢。ペンの z 軸を approach に、x 軸を板の上方向から作る
  const zAxis: Vec3 = [ax, ay, az]
  let xAxis = normalize(cross(boardUp, zAxis))
  if (!Number.isFinite(xAxis[0])) xAxis = [1, 0, 0]
  const yAxis = cross(zAxis, xAxis)
  // 列ベクトルとして並べる（行優先で格納）
  const R06 = [
    xAxis[0], yAxis[0], zAxis[0],
    xAxis[1], yAxis[1], zAxis[1],
    xAxis[2], yAxis[2], zAxis[2],
  ]

  const first3 = [theta1, theta2, theta3]
  let acc = identity()
  for (let i = 0; i < 3; i++) acc = multiply(acc, dhMatrix(ARM[i], first3[i]))
  const R03 = rotationOf(acc)
  const R36 = rotMul(rotTranspose(R03), R06)

  // ZYZ オイラー角。theta5 の符号で 2 通りの解がある
  const sign = wristFlip ? -1 : 1
  const theta5 = Math.atan2(
    sign * Math.hypot(R36[2], R36[5]), // sqrt(r13^2 + r23^2)
    R36[8],                            // r33
  )
  let theta4: number
  let theta6: number
  if (Math.abs(Math.sin(theta5)) < 1e-6) {
    // 手首特異点: theta4 と theta6 は和（または差）しか決まらない。
    // 0 に固定すると通過のたびに 180 度飛ぶので、直前の値を保って
    // 残りを theta6 に寄せる。こうすると特異点を跨いでも連続になる。
    theta4 = seedTheta4
    const total = Math.atan2(-R36[1], R36[0])
    theta6 = R36[8] > 0 ? total - theta4 : total + theta4
  } else {
    theta4 = Math.atan2(sign * R36[5], sign * R36[2])
    theta6 = Math.atan2(sign * R36[7], -sign * R36[6])
  }
  return [theta1, theta2, theta3, theta4, theta5, theta6]
}

export function normalize(v: Vec3): Vec3 {
  const n = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / n, v[1] / n, v[2] / n]
}

export function cross(a: Vec3, b: Vec3): Vec3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ]
}

/** 角度を base から ±π 以内へ巻き戻す */
export function unwrapNear(angle: number, base: number): number {
  let value = angle
  while (value - base > Math.PI) value -= 2 * Math.PI
  while (value - base < -Math.PI) value += 2 * Math.PI
  return value
}

/**
 * 直前の姿勢に最も近い解を選ぶ逆運動学。
 *
 * atan2 が返す角は ±π で折り返すので、素直に使うと 2 度動かしたいところで
 * 358 度回る解が出る。軌道を張るとその大回転をそのまま補間してしまい、
 * 腕が暴れる。実測すると立体の作図で 358.9 度の跳びが出ていた。
 *
 * さらに球面手首には (t4, t5, t6) と (t4+pi, -t5, t6+pi) という
 * 同じ姿勢を与える 2 通りがあるので、直前に近い方を選ぶ。
 */
export function inverseAll(
  target: Vec3,
  approach: Vec3,
  boardUp: Vec3,
  seedTheta4 = 0,
): number[][] {
  const solutions: number[][] = []
  for (const baseFlip of [false, true]) {
    for (const elbowUp of [true, false]) {
      for (const wristFlip of [false, true]) {
        const solution = inverse(
          target, approach, boardUp, elbowUp, baseFlip, wristFlip, seedTheta4,
        )
        if (solution) solutions.push(solution)
      }
    }
  }
  return solutions
}

/** approach 軸のまわりに boardUp を phi だけ回す（ロドリゲスの公式） */
function rollAbout(axis: Vec3, vector: Vec3, phi: number): Vec3 {
  const k = normalize(axis)
  const cos = Math.cos(phi)
  const sin = Math.sin(phi)
  const kv = cross(k, vector)
  const kd = k[0] * vector[0] + k[1] * vector[1] + k[2] * vector[2]
  return [
    vector[0] * cos + kv[0] * sin + k[0] * kd * (1 - cos),
    vector[1] * cos + kv[1] * sin + k[1] * kd * (1 - cos),
    vector[2] * cos + kv[2] * sin + k[2] * kd * (1 - cos),
  ]
}

/** 手首特異点に近いほど大きい罰則。|sin(theta5)| が 0 に近いと theta4 が定まらない */
const SINGULARITY_FLOOR = 0.22

export function inverseNear(
  target: Vec3,
  approach: Vec3,
  boardUp: Vec3,
  previous: number[] | null,
  elbowUp = true,
  tiltSteps = 6,
  maxTilt = 0.22, // 約 12.6 度
): number[] | null {
  if (!previous) {
    return inverse(target, approach, boardUp, elbowUp)
  }
  // 選択肢は 2 種類ある。
  //  * 解の枝: 6R は 1 姿勢に最大 8 解（基部の表裏 × 肘の上下 × 手首の裏返し）
  //  * ペンの傾き: ペン先の位置は指定どおりでも、軸の傾きは少し変えてよい
  //
  // ペンの「軸まわりの回転」は使えない。それは theta6 に丸ごと吸収されるので、
  // theta5（手首特異点までの距離）を動かせないためである。効くのは傾きの方。
  // 特異点の近くではわずかな移動で theta4 が数十度動き、腕が跳ねて見える。
  const tilts: Vec3[] = [normalize(approach)]
  const side = normalize(cross(boardUp, approach))
  const other = cross(normalize(approach), side)
  for (let s = 1; s <= tiltSteps; s++) {
    const phi = (s / tiltSteps) * Math.PI * 2
    const amount = maxTilt
    tilts.push(normalize([
      approach[0] + amount * (side[0] * Math.cos(phi) + other[0] * Math.sin(phi)),
      approach[1] + amount * (side[1] * Math.cos(phi) + other[1] * Math.sin(phi)),
      approach[2] + amount * (side[2] * Math.cos(phi) + other[2] * Math.sin(phi)),
    ]))
  }

  let best: number[] | null = null
  let bestCost = Infinity
  for (const tilted of tilts) {
    for (const candidate of inverseAll(target, tilted, boardUp, previous[3] ?? 0)) {
      const wrapped = candidate.map((angle, index) =>
        unwrapNear(angle, previous[index] ?? 0),
      )
      let cost = 0
      for (let i = 0; i < wrapped.length; i++) {
        // 手首側は多少回っても手先は暴れないので重みを下げる
        const weight = i < 3 ? 1 : 0.7
        cost = Math.max(cost, weight * Math.abs(wrapped[i] - (previous[i] ?? 0)))
      }
      const away = Math.abs(Math.sin(wrapped[4]))
      if (away < SINGULARITY_FLOOR) {
        cost += (SINGULARITY_FLOOR - away) * 6
      }
      if (cost < bestCost) { bestCost = cost; best = wrapped }
    }
  }
  return best
}

/** 関節角を滑らかに補間する（最短回りを選ぶ） */
export function lerpJoints(from: number[], to: number[], t: number): number[] {
  return from.map((value, index) => {
    let delta = (to[index] ?? 0) - value
    while (delta > Math.PI) delta -= 2 * Math.PI
    while (delta < -Math.PI) delta += 2 * Math.PI
    return value + delta * t
  })
}
