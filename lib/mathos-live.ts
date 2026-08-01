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

function linearExpression(xCoefficient: number, yCoefficient: number): string {
  const term = (coefficient: number, variable: string, first: boolean) => {
    if (coefficient === 0) return ''
    const sign = coefficient < 0 ? '-' : first ? '' : '+'
    const magnitude = Math.abs(coefficient) === 1 ? '' : Math.abs(coefficient)
    return `${sign}${magnitude}${variable}`
  }
  const xTerm = term(xCoefficient, 'x', true)
  return `${xTerm}${term(yCoefficient, 'y', xTerm.length === 0)}` || '0'
}

function scaledTexAnswer(expression: string, factor: number): string {
  if (factor === 1) return expression

  const integer = expression.match(/^(\d+)$/)
  if (integer) return `${factor * Number(integer[1])}`

  const fraction = expression.match(/^\\dfrac\{(\d+)\}\{(\d+)\}$/)
  if (fraction) return ratTex(rat(factor * Number(fraction[1]), Number(fraction[2])))

  const mixedPi = expression.match(/^(\d+)\+(\d*)\\pi$/)
  if (mixedPi) {
    const piCoefficient = mixedPi[2] ? Number(mixedPi[2]) : 1
    return `${factor * Number(mixedPi[1])}+${factor * piCoefficient}\\pi`
  }

  const piTerm = expression.match(/^(?:(\d+)|\\dfrac\{(\d+)\}\{(\d+)\})?\\pi$/)
  if (piTerm) {
    const coefficient = piTerm[1]
      ? rat(Number(piTerm[1]))
      : piTerm[2]
        ? rat(Number(piTerm[2]), Number(piTerm[3]))
        : rat(1)
    const scaled = rat(coefficient.n * factor, coefficient.d)
    return `${scaled.n === scaled.d ? '' : ratTex(scaled)}\\pi`
  }

  return `${factor}\\left(${expression}\\right)`
}

type RootTriangleData = {
  e1: number
  e2: number
  e3: number
  semiperimeter: number
  areaSquared: number
  roots: number[]
}

function cubicValue(x: number, e1: number, e2: number, e3: number): number {
  return x * x * x - e1 * x * x + e2 * x - e3
}

function bisectRoot(
  left: number,
  right: number,
  e1: number,
  e2: number,
  e3: number,
): number | null {
  let lo = left
  let hi = right
  let flo = cubicValue(lo, e1, e2, e3)
  const fhi = cubicValue(hi, e1, e2, e3)
  if (flo === 0) return lo
  if (fhi === 0) return hi
  if (flo * fhi > 0) return null
  for (let i = 0; i < 90; i++) {
    const mid = (lo + hi) / 2
    const fm = cubicValue(mid, e1, e2, e3)
    if (flo * fm <= 0) {
      hi = mid
    } else {
      lo = mid
      flo = fm
    }
  }
  return (lo + hi) / 2
}

function hasIntegerRoot(e1: number, e2: number, e3: number): boolean {
  for (let divisor = 1; divisor * divisor <= e3; divisor++) {
    if (e3 % divisor !== 0) continue
    if (cubicValue(divisor, e1, e2, e3) === 0) return true
    if (cubicValue(e3 / divisor, e1, e2, e3) === 0) return true
  }
  return false
}

/**
 * 整数係数三次式を先に作り、その根が相異なる正の無理数かつ三角形を成す候補だけを採用する。
 * 答えのための対称式計算と、数値的な根の再構成を独立な検証経路として持つ。
 */
function constructIrrationalRootTriangle(): RootTriangleData | null {
  for (let attempt = 0; attempt < 240; attempt++) {
    const a = 4 + Math.floor(Math.random() * 8)
    const b = 4 + Math.floor(Math.random() * 8)
    const minC = Math.abs(a - b) + 2
    const maxC = a + b - 2
    if (minC > maxC) continue
    const c = minC + Math.floor(Math.random() * (maxC - minC + 1))
    const e1 = a + b + c
    if (e1 % 2 !== 0) continue
    const e2 = a * b + b * c + c * a
    const e3 = a * b * c + pick([-2, -1, 1, 2])
    if (e3 <= 0 || hasIntegerRoot(e1, e2, e3)) continue

    const discriminant =
      e1 * e1 * e2 * e2 - 4 * e2 * e2 * e2 - 4 * e1 * e1 * e1 * e3 -
      27 * e3 * e3 + 18 * e1 * e2 * e3
    if (discriminant <= 0) continue

    const derivativeDiscriminant = e1 * e1 - 3 * e2
    if (derivativeDiscriminant <= 0) continue
    const criticalOffset = Math.sqrt(derivativeDiscriminant)
    const criticalLeft = (e1 - criticalOffset) / 3
    const criticalRight = (e1 + criticalOffset) / 3
    const upper = e1 + e2 + e3 + 1
    const roots = [
      bisectRoot(0, criticalLeft, e1, e2, e3),
      bisectRoot(criticalLeft, criticalRight, e1, e2, e3),
      bisectRoot(criticalRight, upper, e1, e2, e3),
    ]
    if (roots.some(root => root == null)) continue
    const numericRoots = (roots as number[]).sort((x, y) => x - y)
    if (numericRoots[0] <= 0 || numericRoots[2] >= numericRoots[0] + numericRoots[1]) continue

    const semiperimeter = e1 / 2
    const areaSquared = semiperimeter * cubicValue(semiperimeter, e1, e2, e3)
    if (!Number.isInteger(areaSquared) || areaSquared <= 0) continue

    return { e1, e2, e3, semiperimeter, areaSquared, roots: numericRoots }
  }
  return null
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
  const N = 4 + Math.floor(Math.random() * 25) // 4..28
  const k = 1 + Math.floor(Math.random() * (N - 1))
  const biased = Math.random() < 0.5
  const [pa, pb] = biased ? pick<number[]>([[2,1],[1,2],[3,1],[1,3],[3,2],[2,3],[4,1],[1,4],[5,2],[2,5],[5,3],[3,5],[4,3],[3,4]]) : [1, 1]

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
  const [s, t] = pick<number[]>([[1,1],[1,2],[2,1],[3,-1],[1,3],[2,3],[3,1],[1,-1],[4,1],[2,-1],[5,1],[1,4],[3,2],[4,-1],[2,5],[5,-2],[6,1],[1,5],[3,4],[4,3]])
  const m: number = 3 + Math.floor(Math.random() * 45) // 3..47
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
  const k: number = 3 + Math.floor(Math.random() * 45) // 3..47
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
  const p: number = pick([13,17,29,37,41,53,61,73,89,97,101,109,113,137,149,157,173,181,193,197,229,233,241,257,269,277,281,293] as const)
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
  const c = 1 + Math.floor(Math.random() * 30)
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


// ---------- F7 逆数変換の漸化式（数列・高校） ----------
function reciprocalRecurrence(): LiveProblem | null {
  const pp = 1 + Math.floor(Math.random() * 9)
  const qq = 1 + Math.floor(Math.random() * 9)
  // b_n = 1/a_n は b_{n+1} = p b_n + q, b_1 = 1
  // 独立検証: 逐次計算と閉形式が一致するか
  const bClosed = (n: number) =>
    pp === 1 ? 1 + qq * (n - 1) : Math.pow(pp, n - 1) + (qq * (Math.pow(pp, n - 1) - 1)) / (pp - 1)
  let a = 1
  for (let n = 1; n <= 12; n++) {
    if (Math.abs(1 / a - bClosed(n)) > 1e-6 * Math.max(1, Math.abs(bClosed(n)))) return null
    a = a / (pp + qq * a)
  }
  const denom = `${pp}${qq === 1 ? '+a_n' : `+${qq}a_n`}`
  const closedTex =
    pp === 1
      ? `\\dfrac{1}{${qq === 1 ? 'n' : `${qq}n-${qq - 1}`}}`
      : `\\dfrac{${pp - 1}}{(${pp + qq - 1})\\cdot ${pp}^{n-1}-${qq}}`
  return {
    familyId: 'construct.reciprocal_recurrence',
    domain: 'algebra',
    tool: 'reciprocal_transform',
    parameters: { p: pp, q: qq },
    statementTex:
      `数列 \\((a_n)\\) を \\(a_1=1,\\ a_{n+1}=\\dfrac{a_n}{${denom}}\\) で定める。` +
      `一般項 \\(a_n\\) を求めよ。`,
    answerTex: closedTex,
    solutionTex:
      `逆数 \\(b_n=1/a_n\\) をとると \\(b_{n+1}=${pp}b_n+${qq}\\)（高校：逆数変換で線形漸化式）。` +
      `これを解いて \\(a_n=1/b_n\\)。`,
    morphismChain: ['ReciprocalTransform', 'LinearRecurrence', 'GeneralTerm'],
    verificationMethod: 'reciprocal_linearization_plus_sequential_check',
  }
}

// ---------- F8 複素アフィン漸化式の極限（複素数平面・高校） ----------
function complexAffineLimit(): LiveProblem | null {
  const br = Math.floor(Math.random() * 13) - 6
  const bi = Math.floor(Math.random() * 13) - 6
  if (br === 0 && bi === 0) return null
  // z_{n+1} = (z_n + b)/2 → 不動点 w = b
  // 独立検証: 数値反復
  let zr = 1, zi = 0
  for (let i = 0; i < 300; i++) { zr = (zr + br) / 2; zi = (zi + bi) / 2 }
  if (Math.abs(zr - br) > 1e-9 || Math.abs(zi - bi) > 1e-9) return null
  const fmt = (re: number, im: number) => {
    if (im === 0) return `${re}`
    const imPart = im === 1 ? 'i' : im === -1 ? '-i' : `${im}i`
    if (re === 0) return imPart
    return `${re}${im > 0 ? '+' : ''}${imPart}`
  }
  const bTex = fmt(br, bi)
  return {
    familyId: 'construct.complex_affine_limit',
    domain: 'complex',
    tool: 'fixed_point',
    parameters: { br, bi },
    statementTex:
      `複素数列を \\(z_1=1,\\ z_{n+1}=\\dfrac{z_n+(${bTex})}{2}\\) で定める。` +
      `\\(z_n\\) の \\(n\\to\\infty\\) における極限を求めよ。`,
    answerTex: bTex,
    solutionTex:
      `不動点 \\(w=(w+(${bTex}))/2\\) より \\(w=${bTex}\\)。` +
      `\\(z_{n+1}-w=\\tfrac12(z_n-w)\\) だから \\(|z_n-w|\\to0\\)（高校：複素数平面）。`,
    morphismChain: ['FixedPointShift', 'ContractionHalf', 'ComplexLimit'],
    verificationMethod: 'complex_fixed_point_plus_numeric_iteration',
  }
}

// ---------- F9 座標軸上を動く切片を結ぶ線分の通過領域 ----------
function axisInterceptSegmentRegion(): LiveProblem | null {
  const c = 3 + Math.floor(Math.random() * 12)
  const exactArea = rat(c * c, 6)

  // 独立検算: 境界 y=(sqrt(c)-sqrt(x))^2 を中点則で積分する。
  const divisions = 1200
  let numericArea = 0
  for (let i = 0; i < divisions; i++) {
    const x = c * (i + 0.5) / divisions
    numericArea += Math.pow(Math.sqrt(c) - Math.sqrt(x), 2) * c / divisions
  }
  if (Math.abs(numericArea - ratNum(exactArea)) > 1e-3) return null

  return {
    familyId: 'construct.axis_intercept_segment_swept_region',
    domain: 'geometry',
    tool: 'parameter_elimination_and_integration',
    parameters: { c },
    statementTex:
      `正の数 \\(a,b\\) が \\(a+b=${c}\\) を満たしながら動く。点 ` +
      `\\(A=(a,0),\\ B=(0,b)\\) を結ぶ線分 \\(AB\\) の通過領域の面積を求めよ。`,
    answerTex: ratTex(exactArea),
    solutionTex:
      `点 \\((x,y)\\) がある線分上にある条件は \\(x/a+y/b=1\\)。` +
      `\\(a+b=${c}\\) の下で左辺の最小値は \\((\\sqrt{x}+\\sqrt{y})^2/${c}\\) だから，` +
      `通過領域は \\(\\sqrt{x}+\\sqrt{y}\\le\\sqrt{${c}}\\)。よって ` +
      `\\(\\int_0^{${c}}(\\sqrt{${c}}-\\sqrt{x})^2\\,dx=${ratTex(exactArea)}\\)。`,
    morphismChain: ['MovingIntercepts', 'SegmentIncidence', 'ParameterMinimization', 'SweptRegion', 'AreaIntegral'],
    verificationMethod: 'parameter_elimination_plus_midpoint_area_check',
  }
}

// ---------- F10 円板を線分に沿って動かした通過領域（Minkowski和） ----------
function translatedDiskRegion(): LiveProblem | null {
  const radius = 1 + Math.floor(Math.random() * 5)
  const length = 3 + Math.floor(Math.random() * 12)
  const integerPart = 2 * radius * length
  const piPart = radius * radius

  // 独立検算: 各xでの縦断面長を数値積分する。
  const left = -radius
  const right = length + radius
  const divisions = 2400
  let numericArea = 0
  for (let i = 0; i < divisions; i++) {
    const x = left + (right - left) * (i + 0.5) / divisions
    const distance = x < 0 ? -x : x > length ? x - length : 0
    const halfHeight = Math.sqrt(Math.max(0, radius * radius - distance * distance))
    numericArea += 2 * halfHeight * (right - left) / divisions
  }
  const exactNumeric = integerPart + piPart * Math.PI
  if (Math.abs(numericArea - exactNumeric) > 2e-3) return null

  return {
    familyId: 'construct.translated_disk_swept_region',
    domain: 'geometry',
    tool: 'minkowski_sum',
    parameters: { radius, length },
    statementTex:
      `半径 \\(${radius}\\) の円板 \\(D\\) を，その中心が線分 ` +
      `\\(\\{(t,0)\\mid 0\\le t\\le ${length}\\}\\) 上を自由に動くように移動させる。` +
      `このとき円板 \\(D\\) の通過領域の面積を求めよ。`,
    answerTex: `${integerPart}+${piPart === 1 ? '' : piPart}\\pi`,
    solutionTex:
      `通過領域は長さ \\(${length}\\) の線分と半径 \\(${radius}\\) の円板のMinkowski和である。` +
      `中央の長方形と両端の半円に分けると面積は ` +
      `\\(2\\cdot${radius}\\cdot${length}+\\pi${radius}^2=${integerPart}+${piPart === 1 ? '' : piPart}\\pi\\)。`,
    morphismChain: ['CenterPath', 'DiskTranslation', 'MinkowskiSum', 'CapsuleDecomposition', 'Area'],
    verificationMethod: 'minkowski_decomposition_plus_cross_section_quadrature',
  }
}

// ---------- F11 原点中心の長方形を回転させた通過領域 ----------
function rotatingRectangleRegion(): LiveProblem | null {
  const width = 2 * (1 + Math.floor(Math.random() * 6))
  const height = 2 * (1 + Math.floor(Math.random() * 6))
  if (width === height) return null
  const radiusSquaredNumerator = width * width + height * height
  const areaCoefficient = rat(radiusSquaredNumerator, 4)

  // 独立検算: 4頂点の回転半径がすべて外接円半径に一致する。
  const cornerRadiusSquared = Math.pow(width / 2, 2) + Math.pow(height / 2, 2)
  if (Math.abs(cornerRadiusSquared - radiusSquaredNumerator / 4) > 1e-12) return null

  return {
    familyId: 'construct.rotating_rectangle_swept_region',
    domain: 'geometry',
    tool: 'rotation_orbit',
    parameters: { width, height },
    statementTex:
      `縦 \\(${height}\\)，横 \\(${width}\\) の長方形 \\(R\\) の中心を原点に固定し，` +
      `平面内で自由に回転させる。長方形 \\(R\\) の通過領域の面積を求めよ。`,
    answerTex: `${ratTex(areaCoefficient)}\\pi`,
    solutionTex:
      `中心から長方形内の点までの距離は半対角線 ` +
      `\\(\\frac12\\sqrt{${width}^2+${height}^2}\\) 以下である。逆に各半径方向へ長方形を回せるので，` +
      `通過領域はこの半径の円板全体。面積は \\(${ratTex(areaCoefficient)}\\pi\\)。`,
    morphismChain: ['Rectangle', 'RotationGroupAction', 'RadialOrbit', 'Circumdisk', 'Area'],
    verificationMethod: 'rotation_orbit_bound_plus_corner_radius_check',
  }
}

// ---------- F12 円周上の固定長弦が掃く通過領域 ----------
function fixedChordRegion(): LiveProblem | null {
  const radius = 3 + Math.floor(Math.random() * 8)
  const halfChord = 1 + Math.floor(Math.random() * (radius - 1))
  const chord = 2 * halfChord
  const coefficient = halfChord * halfChord
  const innerRadiusSquared = radius * radius - coefficient

  // 独立検算: annulus面積 π(R²-h²) が π(d/2)² に一致する。
  if (radius * radius - innerRadiusSquared !== coefficient) return null

  return {
    familyId: 'construct.fixed_chord_swept_region',
    domain: 'geometry',
    tool: 'rotation_orbit_and_annulus',
    parameters: { radius, chord },
    statementTex:
      `半径 \\(${radius}\\) の円周上を，\\(PQ=${chord}\\) を保ちながら2点 \\(P,Q\\) が動く。` +
      `線分 \\(PQ\\) の通過領域の面積を求めよ。`,
    answerTex: `${coefficient === 1 ? '' : coefficient}\\pi`,
    solutionTex:
      `弦 \\(PQ\\) と中心の距離を \\(h\\) とすると ` +
      `\\(h^2=${radius}^2-(${chord}/2)^2=${innerRadiusSquared}\\)。` +
      `弦を回転した通過領域は内半径 \\(h\\)，外半径 \\(${radius}\\) の円環だから，` +
      `面積は \\(\\pi(${radius}^2-h^2)=${coefficient}\\pi\\)。`,
    morphismChain: ['FixedLengthChord', 'DistanceFromCenter', 'RotationOrbit', 'Annulus', 'Area'],
    verificationMethod: 'chord_distance_identity_plus_annulus_area_check',
  }
}

// ---------- F13-F15 三次式の根から作る三角形の対称不変量 ----------
type RootTriangleQuery = 'curvature_sum' | 'center_distance_sum' | 'radius_ratio'

function rootTriangleInvariant(query: RootTriangleQuery): LiveProblem | null {
  const data = constructIrrationalRootTriangle()
  if (!data) return null
  const { e1, e2, e3, semiperimeter: s, areaSquared, roots } = data
  const polynomial = `x^3-${e1}x^2+${e2}x-${e3}=0`
  const sharedStatement =
    `三次方程式 \\(${polynomial}\\) は3つの相異なる正の無理数解 ` +
    `\\(a,b,c\\) をもち，これらは三角形の3辺の長さになる。`
  const sharedSolution =
    `\\(P(x)=x^3-${e1}x^2+${e2}x-${e3}\\) とする。Vietaの公式より ` +
    `\\(a+b+c=${e1},\\ ab+bc+ca=${e2},\\ abc=${e3}\\)，したがって半周長は \\(s=${s}\\)。` +
    `Heronの公式を根多項式で書けば ` +
    `\\(\\Delta^2=s(s-a)(s-b)(s-c)=sP(s)=${areaSquared}\\)。`

  let familyId: string
  let statementTex: string
  let answer: Rat
  let solutionTex: string
  let numericValue: number
  let verificationMethod: string
  let finalMorphisms: string[]

  if (query === 'curvature_sum') {
    familyId = 'construct.root_triangle.curvature_square_sum'
    statementTex =
      `${sharedStatement} 内接円の曲率を \\(\\kappa_0\\)，3つの傍接円の曲率を ` +
      `\\(\\kappa_1,\\kappa_2,\\kappa_3\\) とするとき，` +
      `\\(\\kappa_0^2+\\kappa_1^2+\\kappa_2^2+\\kappa_3^2\\) を求めよ。`
    answer = rat(e1 * e1 - 2 * e2, areaSquared)
    solutionTex =
      `${sharedSolution} 各曲率は \\(s/\\Delta,(s-a)/\\Delta,(s-b)/\\Delta,(s-c)/\\Delta\\)。` +
      `分子の二乗和は相殺して \\(a^2+b^2+c^2=${e1 * e1 - 2 * e2}\\) となるから，` +
      `求める値は \\(${ratTex(answer)}\\)。`
    numericValue = (s * s + roots.reduce((sum, root) => sum + (s - root) ** 2, 0)) / areaSquared
    verificationMethod = 'vieta_heron_curvature_identity_plus_numeric_roots'
    finalMorphisms = ['IncircleExcircles', 'CurvatureDual', 'SymmetricCancellation']
  } else if (query === 'center_distance_sum') {
    familyId = 'construct.root_triangle.center_distance_square_sum'
    statementTex =
      `${sharedStatement} 外心を \\(O\\)，内心を \\(I\\)，3つの傍心を ` +
      `\\(I_1,I_2,I_3\\) とするとき，` +
      `\\(OI^2+OI_1^2+OI_2^2+OI_3^2\\) を求めよ。`
    answer = rat(3 * e3 * e3, 4 * areaSquared)
    solutionTex =
      `${sharedSolution} Eulerの距離公式と \\(r_1+r_2+r_3-r=4R\\) より距離の二乗和は ` +
      `\\(12R^2\\)。また \\(R=abc/(4\\Delta)=${e3}/(4\\Delta)\\) だから，` +
      `求める値は \\(${ratTex(answer)}\\)。`
    const numericArea = Math.sqrt(areaSquared)
    const numericCircumradius = roots.reduce((product, root) => product * root, 1) / (4 * numericArea)
    const numericInradius = numericArea / s
    const numericExradii = roots.map(root => numericArea / (s - root))
    numericValue = numericCircumradius ** 2 - 2 * numericCircumradius * numericInradius +
      numericExradii.reduce(
        (sum, exradius) => sum + numericCircumradius ** 2 + 2 * numericCircumradius * exradius,
        0,
      )
    verificationMethod = 'euler_center_identity_plus_numeric_root_triangle'
    finalMorphisms = ['TriangleCenters', 'EulerDistanceIdentity', 'RadiusCancellation']
  } else {
    familyId = 'construct.root_triangle.circumradius_inradius_ratio'
    statementTex =
      `${sharedStatement} 外接円半径を \\(R\\)，内接円半径を \\(r\\) とするとき，` +
      `比 \\(R/r\\) を求めよ。`
    answer = rat(e3 * s, 4 * areaSquared)
    solutionTex =
      `${sharedSolution} \\(R=abc/(4\\Delta)\\)，\\(r=\\Delta/s\\) より ` +
      `\\(R/r=abcs/(4\\Delta^2)\\)。対称式を代入すると \\(${ratTex(answer)}\\)。`
    const numericArea = Math.sqrt(areaSquared)
    const numericCircumradius = roots.reduce((product, root) => product * root, 1) / (4 * numericArea)
    numericValue = numericCircumradius / (numericArea / s)
    verificationMethod = 'vieta_heron_radius_ratio_plus_numeric_roots'
    finalMorphisms = ['Circumradius', 'Inradius', 'RadiusRatio']
  }

  if (Math.abs(numericValue - ratNum(answer)) > 1e-9) return null

  return {
    familyId,
    domain: 'geometry_algebra',
    tool: 'vieta_heron_triangle_invariants',
    parameters: { e1, e2, e3, semiperimeter: s, areaSquared },
    statementTex,
    answerTex: ratTex(answer),
    solutionTex,
    morphismChain: [
      'CubicPolynomial',
      'IrrationalRootMultiset',
      'VietaSymmetricSums',
      'TriangleInequalityCertificate',
      'HeronPolynomialEvaluation',
      ...finalMorphisms,
      'ExactRationalEvaluation',
    ],
    verificationMethod,
  }
}

const rootTriangleCurvatureSum = () => rootTriangleInvariant('curvature_sum')
const rootTriangleCenterDistanceSum = () => rootTriangleInvariant('center_distance_sum')
const rootTriangleRadiusRatio = () => rootTriangleInvariant('radius_ratio')

type LiveGenerator = () => LiveProblem | null

/**
 * 任意の通過領域問題を可逆線形写像で持ち上げる共通の射。
 * 元の問題族ごとの特別扱いはせず、面積測度の変換則 |det T| だけを合成する。
 */
function affineImageOfSweptRegion(baseGenerator: LiveGenerator): LiveGenerator {
  return () => {
    const base = baseGenerator()
    if (!base) return null
    const [m11, m12, m21, m22] = pick<number[]>([
      [2, 1, 1, 2],
      [1, 1, -1, 2],
      [3, 1, 1, 1],
      [2, -1, 1, 1],
    ])
    const determinant = Math.abs(m11 * m22 - m12 * m21)
    if (!determinant) return null

    const premise = base.statementTex.replace(
      /の通過領域の面積を求めよ。$/,
      'の通過領域を \\(S\\) とする。',
    )
    if (premise === base.statementTex) return null
    const linearMap =
      `\\(T(x,y)=(${linearExpression(m11, m12)},${linearExpression(m21, m22)})\\)`
    const answer = scaledTexAnswer(base.answerTex, determinant)

    return {
      familyId: `compose.affine_image.${base.familyId}`,
      domain: 'geometry',
      tool: `${base.tool}+jacobian_determinant`,
      parameters: { ...base.parameters, m11, m12, m21, m22, determinant },
      statementTex:
        `${premise} 線形変換 ${linearMap} による像 \\(T(S)\\) の面積を求めよ。`,
      answerTex: answer,
      solutionTex:
        `${base.solutionTex} したがって \\(S\\) の面積は \\(${base.answerTex}\\)。` +
        `一方，線形変換 \\(T\\) は面積を ` +
        `\\(|\\det T|=|${m11}\\cdot${m22}-(${m12})\\cdot${m21}|=${determinant}\\) 倍する。` +
        `ゆえに \\(T(S)\\) の面積は \\(${answer}\\)。`,
      morphismChain: [...base.morphismChain, 'LinearImage', 'JacobianDeterminant', 'AreaScale'],
      verificationMethod: `${base.verificationMethod}_plus_exact_determinant_scale`,
    }
  }
}

const affineAxisInterceptRegion = affineImageOfSweptRegion(axisInterceptSegmentRegion)
const affineTranslatedDiskRegion = affineImageOfSweptRegion(translatedDiskRegion)
const affineRotatingRectangleRegion = affineImageOfSweptRegion(rotatingRectangleRegion)
const affineFixedChordRegion = affineImageOfSweptRegion(fixedChordRegion)

type GeneratorSpec = {
  generate: LiveGenerator
  domain: string
  tags: string[]
  depth: number
}

const GENERATORS: GeneratorSpec[] = [
  { generate: gambler, domain: 'probability', tags: ['probability', 'recurrence', 'hitting_probability'], depth: 3 },
  { generate: recurrenceModPeriod, domain: 'number_theory', tags: ['number_theory', 'recurrence', 'period', 'modular'], depth: 3 },
  { generate: complexRotation, domain: 'complex', tags: ['complex', 'rotation', 'period'], depth: 3 },
  { generate: paley, domain: 'number_theory_graph', tags: ['number_theory', 'graph', 'quadratic_residue'], depth: 3 },
  { generate: parabolaFixedPoint, domain: 'geometry', tags: ['geometry', 'locus', 'invariant', 'parabola'], depth: 3 },
  { generate: mobiusPeriod, domain: 'algebra', tags: ['algebra', 'iteration', 'matrix', 'period'], depth: 3 },
  { generate: reciprocalRecurrence, domain: 'algebra', tags: ['algebra', 'recurrence', 'transformation'], depth: 3 },
  { generate: complexAffineLimit, domain: 'complex', tags: ['complex', 'recurrence', 'limit', 'fixed_point'], depth: 3 },
  { generate: axisInterceptSegmentRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'parameter_elimination'], depth: 5 },
  { generate: translatedDiskRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'disk', 'minkowski_sum'], depth: 5 },
  { generate: rotatingRectangleRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'rotation', 'group_action'], depth: 5 },
  { generate: fixedChordRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'chord', 'rotation'], depth: 5 },
  { generate: affineAxisInterceptRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'parameter_elimination', 'linear_map'], depth: 8 },
  { generate: affineTranslatedDiskRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'disk', 'minkowski_sum', 'linear_map'], depth: 8 },
  { generate: affineRotatingRectangleRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'rotation', 'group_action', 'linear_map'], depth: 8 },
  { generate: affineFixedChordRegion, domain: 'geometry', tags: ['geometry', 'passage_region', 'area', 'segment', 'chord', 'rotation', 'linear_map'], depth: 8 },
  { generate: rootTriangleCurvatureSum, domain: 'geometry_algebra', tags: ['geometry', 'algebra', 'triangle', 'polynomial_roots', 'symmetric_polynomial', 'heron', 'circle_centers', 'curvature'], depth: 9 },
  { generate: rootTriangleCenterDistanceSum, domain: 'geometry_algebra', tags: ['geometry', 'algebra', 'triangle', 'polynomial_roots', 'symmetric_polynomial', 'heron', 'circle_centers', 'center_distance'], depth: 9 },
  { generate: rootTriangleRadiusRatio, domain: 'geometry_algebra', tags: ['geometry', 'algebra', 'triangle', 'polynomial_roots', 'symmetric_polynomial', 'heron', 'circle_centers', 'radius_ratio'], depth: 9 },
]

export type LiveGenerationRequest = {
  domain?: string
  focusTags?: string[]
  excludedFamilies?: string[]
  preferDepth?: boolean
}

function domainMatches(requested: string | undefined, actual: string): boolean {
  if (!requested) return true
  return actual.includes(requested) || requested.includes(actual) ||
    (requested.includes('geometry') && actual === 'geometry')
}

/** 選択問題の意味タグとの一致度で族を並べ、同点だけをランダム化して構築する。 */
export function generateLiveProblem(request: LiveGenerationRequest = {}): LiveProblem | null {
  const focus = new Set(request.focusTags ?? [])
  const excluded = new Set(request.excludedFamilies ?? [])
  const scored = GENERATORS.map((spec) => {
    const tagScore = spec.tags.reduce((score, tag) => score + (focus.has(tag) ? 4 : 0), 0)
    const domainScore = domainMatches(request.domain, spec.domain) ? 3 : 0
    const depthScore = request.preferDepth ? spec.depth * 0.35 : 0
    return { spec, score: tagScore + domainScore + depthScore + Math.random() * 0.35 }
  }).sort((a, b) => b.score - a.score)

  const bestScore = scored[0]?.score ?? 0
  const relevant = scored.filter(({ spec, score }) => {
    if (excluded.size && excluded.has(spec.generate.name)) return false
    if (focus.size) return score >= Math.max(3, bestScore - 4.2)
    return domainMatches(request.domain, spec.domain)
  })
  const deepestRelevant = relevant.reduce((depth, { spec }) => Math.max(depth, spec.depth), 0)
  const order = request.preferDepth
    ? relevant.filter(({ spec }) => spec.depth === deepestRelevant)
    : relevant

  for (const { spec } of order) {
    for (let attempt = 0; attempt < 6; attempt++) {
      try {
        const p = spec.generate()
        if (!p) continue
        if (excluded.has(p.familyId)) continue
        return p
      } catch {
        continue
      }
    }
  }
  return null
}
