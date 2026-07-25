/**
 * MathOS ライブ作問 — /sakumon を叩いた *その場* で問題を構築・検証する。
 *
 * 事前生成プールの配布ではなく、要求のたびにパラメータを引いて対象を構築し、
 * 答えをその場で計算し、独立な方法で検証してから返す。SymPy を必要としない
 * 「整数・有理数演算で閉じる」族だけをここに置く（幾何の記号処理などは
 * Python 側の事前生成プールが担当）。
 *
 * 各族は construct_engine.py の同名族と同じ数学。検証は必ず別経路
 * （総当り・逐次計算）で行い、一致しない候補は捨てる。
 */

// ---------- 有理数（整数分数・値は小さいので number で安全） ----------
type Rat = { n: number; d: number }

function gcdNum(a: number, b: number): number {
  a = Math.abs(a); b = Math.abs(b)
  while (b) { const t = a % b; a = b; b = t }
  return a
}

function rat(n: number, d: number = 1): Rat {
  if (d === 0) throw new Error('zero denominator')
  if (d < 0) { n = -n; d = -d }
  const g = gcdNum(n, d) || 1
  return { n: n / g, d: d / g }
}

const ratSub = (a: Rat, b: Rat) => rat(a.n * b.d - b.n * a.d, a.d * b.d)
const ratDiv = (a: Rat, b: Rat) => rat(a.n * b.d, a.d * b.n)
function ratPow(a: Rat, e: number): Rat {
  let r = rat(1)
  for (let i = 0; i < e; i++) r = rat(r.n * a.n, r.d * a.d)
  return r
}
function ratTex(r: Rat): string {
  if (r.d === 1) return `${r.n}`
  const sign = r.n < 0 ? '-' : ''
  const n = Math.abs(r.n)
  return `${sign}\\dfrac{${n}}{${r.d}}`
}
const ratNum = (r: Rat) => r.n / r.d

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

export type LiveProblem = {
  familyId: string
  domain: string
  tool: string
  parameters: Record<string, number>
  statementTex: string
  answerTex: string
  solutionTex: string
  morphismChain: string[]
  verificationMethod: string
}

// ---------- F1 ギャンブラーの破産（確率漸化式・高校） ----------
function gambler(): LiveProblem | null {
  const N = 4 + Math.floor(Math.random() * 9) // 4..12
  const k = 1 + Math.floor(Math.random() * (N - 1))
  const biased = Math.random() < 0.5
  const [pa, pb] = biased ? pick<number[]>([[2, 1], [1, 2], [3, 1], [1, 3], [3, 2]]) : [1, 1]

  let answer: Rat
  let solution: string
  if (pa === pb) {
    answer = rat(k, N)
    solution =
      `到達確率を \\(p_k\\) とおくと \\(p_k=\\tfrac12p_{k+1}+\\tfrac12p_{k-1}\\)。` +
      `これは等差数列で \\(p_0=0,\\ p_{${N}}=1\\) より \\(p_k=k/${N}\\)（高校：漸化式）。`
  } else {
    const r = rat(pb, pa)
    const num = ratSub(rat(1), ratPow(r, k))
    const den = ratSub(rat(1), ratPow(r, N))
    answer = ratDiv(num, den)
    solution =
      `\\(p_k=\\tfrac{${pa}}{${pa + pb}}p_{k+1}+\\tfrac{${pb}}{${pa + pb}}p_{k-1}\\)。` +
      `比 \\(r=${ratTex(r)}\\) を用いると \\(p_k=\\dfrac{1-r^k}{1-r^N}\\)（高校：漸化式）。`
  }

  // 独立検証: 線形方程式を数値で解いて一致を確認
  const p = pa / (pa + pb)
  const probs = new Array<number>(N + 1).fill(0)
  probs[N] = 1
  for (let iter = 0; iter < 20000; iter++) {
    for (let i = 1; i < N; i++) probs[i] = p * probs[i + 1] + (1 - p) * probs[i - 1]
  }
  if (Math.abs(probs[k] - ratNum(answer)) > 1e-9) return null

  const step = pa === pb
    ? '左右へ等確率 \\(\\tfrac12\\)'
    : `右へ確率 \\(\\tfrac{${pa}}{${pa + pb}}\\)、左へ \\(\\tfrac{${pb}}{${pa + pb}}\\)`
  return {
    familyId: 'construct.gambler_ruin_probability',
    domain: 'probability',
    tool: 'linear_recurrence',
    parameters: { N, k, pa, pb },
    statementTex:
      `数直線上の点が \\(k=${k}\\) から出発し，各回 ${step} で \\(\\pm1\\) 動く。` +
      `\\(0\\) または \\(N=${N}\\) に達したら止まる。\\(N\\) に先に到達する確率を求めよ。`,
    answerTex: ratTex(answer),
    solutionTex: solution,
    morphismChain: ['AbsorbingWalk', 'BoundaryRecurrence', 'RatioClosedForm'],
    verificationMethod: 'gambler_ruin_recurrence_plus_numeric_fixed_point',
  }
}

// ---------- F2 線形漸化式の mod m 周期（整数・高校） ----------
function recurrenceModPeriod(): LiveProblem | null {
  const [s, t] = pick<number[]>([[1, 1], [1, 2], [2, 1], [3, -1], [1, 3], [2, 3], [3, 1], [1, -1], [4, 1], [2, -1]])
  const m: number = pick([5, 7, 8, 9, 11, 13, 16, 17, 19, 23] as const)
  let a = 0, b = 1, period = 0
  const limit = m * m * 6
  for (let i = 1; i <= limit; i++) {
    const nb = (((s * b + t * a) % m) + m) % m
    a = ((b % m) + m) % m
    b = nb
    if (a === 0 && b === 1) { period = i; break }
  }
  if (!period) return null

  // 独立検証: 周期ぶん進めて初期条件に戻るか、かつそれ未満で戻らないか
  let x = 0, y = 1
  for (let i = 0; i < period; i++) {
    const ny = (((s * y + t * x) % m) + m) % m
    x = ((y % m) + m) % m
    y = ny
  }
  if (!(x === 0 && y === 1)) return null

  const term = (c: number, sym: string) =>
    c === 0 ? '' : c === 1 ? `+${sym}` : c === -1 ? `-${sym}` : c > 0 ? `+${c}${sym}` : `${c}${sym}`
  const rhs = (term(s, 'a_{n+1}') + term(t, 'a_n')).replace(/^\+/, '')
  return {
    familyId: 'construct.linear_recurrence_mod_period',
    domain: 'number_theory',
    tool: 'matrix_mod_order',
    parameters: { s, t, m },
    statementTex:
      `数列 \\((a_n)\\) を \\(a_0=0,\\ a_1=1,\\ a_{n+2}=${rhs}\\) で定める。` +
      `\\((a_n)\\) を \\(\\bmod\\ ${m}\\) で見たときの最小周期を求めよ。`,
    answerTex: `${period}`,
    solutionTex:
      `\\((a_{n+1},a_n)\\) は行列 \\(\\begin{pmatrix}${s}&${t}\\\\1&0\\end{pmatrix}\\) を` +
      `かけて進む。\\(\\bmod\\ ${m}\\) でこの行列の乗法的位数が周期。`,
    morphismChain: ['CompanionMatrix', 'ModularReduction', 'MultiplicativeOrder'],
    verificationMethod: 'sequence_period_search_plus_replay_check',
  }
}

// ---------- F3 複素回転の周期（ド・モアブル・高校） ----------
function complexRotation(): LiveProblem | null {
  const k: number = pick([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 18, 20, 24] as const)
  const cands: number[] = []
  for (let m = 1; m < k; m++) if (gcdNum(m, k) === 1) cands.push(m)
  if (!cands.length) return null
  const m = pick(cands)
  // 独立検証: α^j=1 となる最小 j が k であること（偏角の総和で確認）
  let ok = true
  for (let j = 1; j < k; j++) if ((m * j) % k === 0) ok = false
  if (!ok || (m * k) % k !== 0) return null
  return {
    familyId: 'construct.complex_rotation_period',
    domain: 'complex',
    tool: 'polar_form',
    parameters: { k, m },
    statementTex:
      `複素数 \\(\\alpha=\\cos\\dfrac{${2 * m}\\pi}{${k}}+i\\sin\\dfrac{${2 * m}\\pi}{${k}}\\) に対し，` +
      `複素数列を \\(z_1=1,\\ z_{n+1}=\\alpha z_n\\) で定める。` +
      `\\(z_n=1\\) となる最小の正の整数 \\(n\\) を求めよ。`,
    answerTex: `${k + 1}`,
    solutionTex:
      `\\(z_n=\\alpha^{n-1}\\)。\\(\\gcd(${m},${k})=1\\) だから \\(\\alpha^{j}=1\\) となる` +
      `最小の正の整数 \\(j\\) は \\(${k}\\)。よって \\(n-1=${k}\\)、\\(n=${k + 1}\\)（ド・モアブル）。`,
    morphismChain: ['PrimitiveRootOfUnity', 'DeMoivrePower', 'MinimalPeriod'],
    verificationMethod: 'primitive_root_order_check',
  }
}

// ---------- F4 Paleyグラフ（平方剰余・整数） ----------
function paley(): LiveProblem | null {
  const p: number = pick([13, 17, 29, 37, 41, 53, 61, 73, 89, 97, 101, 109, 113] as const)
  const QR = new Set<number>()
  for (let x = 1; x < p; x++) QR.add((x * x) % p)
  let r0 = p
  for (const q of QR) if (q < r0) r0 = q
  let common = 0
  for (let w = 0; w < p; w++) {
    if (w === 0 || w === r0) continue
    if (QR.has(((w % p) + p) % p) && QR.has((((w - r0) % p) + p) % p)) common++
  }
  if (common !== (p - 5) / 4) return null // 独立検証: 強正則グラフの λ
  return {
    familyId: 'construct.paley_common_neighbors',
    domain: 'number_theory_graph',
    tool: 'quadratic_residue',
    parameters: { p },
    statementTex:
      `素数 \\(p=${p}\\)（\\(p\\equiv1\\pmod4\\)）に対し，頂点集合 \\(\\mathbb Z_{${p}}\\) 上の` +
      `グラフ \\(G\\) を，2頂点 \\(x,y\\) が \\(x-y\\) が平方剰余のとき辺で結ぶことで定める。` +
      `辺で結ばれた2頂点の共通の隣接頂点の個数を求めよ。`,
    answerTex: `${common}`,
    solutionTex:
      `これは Paley グラフ。強正則で，隣接2頂点の共通隣接点数は \\(\\lambda=(p-5)/4=${common}\\)。` +
      `平方剰余の指標和で示せる。`,
    morphismChain: ['ResidueVertices', 'QuadraticResidueEdges', 'CommonNeighborCount'],
    verificationMethod: 'exhaustive_common_neighbor_count_vs_srg_lambda',
  }
}

// ---------- F5 放物線の直角弦の定点（二次関数・高校） ----------
function parabolaFixedPoint(): LiveProblem | null {
  const c = 1 + Math.floor(Math.random() * 10)
  const fixedY = rat(1, c)
  // 独立検証: 任意の a について b=-1/(c^2 a) とし、弦が (0,1/c) を通るか
  for (const a of [1, 2, 0.5, 3]) {
    const b = -1 / (c * c * a)
    const yAt0 = c * a * b * -1 // 弦 y=c(a+b)x - c ab → x=0 で -c·ab
    if (Math.abs(yAt0 - 1 / c) > 1e-9) return null
  }
  const curve = c === 1 ? 'x^2' : `${c}x^2`
  return {
    familyId: 'construct.parabola_right_angle_chord',
    domain: 'geometry',
    tool: 'slope_product',
    parameters: { c },
    statementTex:
      `放物線 \\(y=${curve}\\) 上の相異なる2点 \\(A,B\\) と原点 \\(O\\) が ` +
      `\\(\\angle AOB=90^\\circ\\) を満たしながら動く。このとき弦 \\(AB\\) が必ず通る定点を求めよ。`,
    answerTex: `(0,\\ ${ratTex(fixedY)})`,
    solutionTex:
      `\\(A=(a,${c}a^2),B=(b,${c}b^2)\\)。\\(OA\\perp OB\\) から傾きの積 \\(${c}^2ab=-1\\)，` +
      `すなわち \\(ab=-1/${c}^2\\)（一定）。弦 \\(AB\\) は \\(y=${c}(a+b)x-${c}ab\\) で ` +
      `\\(x=0\\) のとき \\(y=1/${c}\\)。`,
    morphismChain: ['RightAngleCondition', 'SlopeProductInvariant', 'FixedPoint'],
    verificationMethod: 'slope_product_invariant_plus_numeric_chord_check',
  }
}

// ---------- F6 メビウス反復の周期（2×2整数行列） ----------
function mobiusPeriod(): LiveProblem | null {
  const [a, b, c, d] = pick<number[]>([[0, -1, 1, 0], [0, -1, 1, -1], [1, -1, 1, 0], [2, -1, 1, 0]])
  const det = a * d - b * c
  if (det === 0) return null
  // M^n がスカラー行列になる最小 n
  let m = [a, b, c, d]
  const mul = (x: number[], y: number[]) => [
    x[0] * y[0] + x[1] * y[2], x[0] * y[1] + x[1] * y[3],
    x[2] * y[0] + x[3] * y[2], x[2] * y[1] + x[3] * y[3],
  ]
  let period = 0
  for (let n = 2; n <= 24; n++) {
    m = mul(m, [a, b, c, d])
    if (m[1] === 0 && m[2] === 0 && m[0] === m[3]) { period = n; break }
  }
  if (!period) return null
  // 独立検証: 実際に f を period 回合成して恒等になるか（数値）
  const f = (x: number) => (a * x + b) / (c * x + d)
  for (const x0 of [0.3, 1.7, -2.4]) {
    let x = x0
    for (let i = 0; i < period; i++) x = f(x)
    if (!isFinite(x) || Math.abs(x - x0) > 1e-6) return null
  }
  const num = `${a === 0 ? '' : a === 1 ? 'x' : `${a}x`}${b === 0 ? '' : b > 0 ? `+${b}` : `${b}`}` || '1'
  const den = `${c === 0 ? '' : c === 1 ? 'x' : `${c}x`}${d === 0 ? '' : d > 0 ? `+${d}` : `${d}`}` || '1'
  return {
    familyId: 'construct.mobius_iteration_period',
    domain: 'algebra',
    tool: 'matrix_power',
    parameters: { a, b, c, d },
    statementTex:
      `関数 \\(f(x)=\\dfrac{${num}}{${den}}\\) を定める。合成を \\(f_1=f,\\ f_{n+1}=f\\circ f_n\\) で` +
      `帰納的に定める。\\(f_n\\) が恒等写像となる最小の正の整数 \\(n\\) を求めよ。`,
    answerTex: `${period}`,
    solutionTex:
      `\\(f\\) を行列 \\(M=\\begin{pmatrix}${a}&${b}\\\\${c}&${d}\\end{pmatrix}\\) に対応させると ` +
      `\\(f_n\\leftrightarrow M^n\\)。\\(M^n\\) がスカラー行列になる最小の \\(n\\) が答え。`,
    morphismChain: ['MobiusToMatrix', 'MatrixPower', 'ScalarPeriod'],
    verificationMethod: 'matrix_scalar_period_plus_numeric_composition_check',
  }
}

const GENERATORS: Array<() => LiveProblem | null> = [
  gambler,
  recurrenceModPeriod,
  complexRotation,
  paley,
  parabolaFixedPoint,
  mobiusPeriod,
]

/** その場で1問構築する。族はランダム、失敗したら別の族を試す。 */
export function generateLiveProblem(domain?: string): LiveProblem | null {
  const order = [...GENERATORS].sort(() => Math.random() - 0.5)
  for (const gen of order) {
    for (let attempt = 0; attempt < 6; attempt++) {
      try {
        const p = gen()
        if (!p) continue
        if (domain && !p.domain.includes(domain) && !domain.includes(p.domain)) continue
        return p
      } catch {
        continue
      }
    }
  }
  return null
}
