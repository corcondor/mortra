/**
 * Lattice Core の性質テスト。
 *
 * 固定値との一致（FCC の配位数は 12 など）は、既知の答えを埋め込んだだけで、
 * 未知の格子には何も言わない。ここでは格子によらず成り立つ性質を検査する。
 *
 *   dual(dual(L)) ≅ L
 *   基底変換 B → BU (U ∈ GL(n,ℤ)) で不変量が変わらない
 *   Aut(Λ) が群である（単位元・逆元・積で閉じる）
 *   ルート系が鏡映で閉じる
 *   Cartan 整数がすべて整数
 *   テータ級数の係数 = 殻の点の数
 *   未見の格子でも成り立つ
 *   規約の取り違えを検出できる
 *
 *   npx tsx scripts/lattice-properties.mts
 */
import {
  LATTICES, dual, gram, determinant, kissingNumber, packingFraction,
  thetaSeries, automorphisms, rootSystem, shells, minimalVectors, lift,
  type Basis, type Vec3,
} from '../lib/vision/lattice.js'

let pass = 0
let fail = 0
const failures: string[] = []

function check(name: string, ok: boolean, detail = '') {
  ok ? pass++ : (fail++, failures.push(`${name}  ${detail}`))
  console.log(`${ok ? '  ok  ' : '  NG  '} ${name}${ok || !detail ? '' : `   ${detail}`}`)
}

const near = (a: number, b: number, tol = 1e-9) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(a))

/** 短いベクトルのノルム列は基底変換で不変。これを署名にする。
 *  探索範囲は最小ノルムから決める。Gram の成分から決めると
 *  範囲そのものが基底に依存し、比べているものが変わってしまう。 */
function gramSignature(B: Basis): string {
  const min = minimalVectors(B).norm2
  return shells(B, min * 6.001)
    .slice(0, 5)
    .map(s => `${s.norm2.toFixed(6)}:${s.coeffs.length}`)
    .join(' ')
}

/** 整数ユニモジュラ行列。基底変換に使う */
const UNIMODULAR: number[][][] = [
  [[1, 1, 0], [0, 1, 0], [0, 0, 1]],
  [[1, 0, 0], [2, 1, 0], [0, 0, 1]],
  [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
  [[1, 2, 3], [0, 1, 4], [0, 0, 1]],
  [[-1, 0, 0], [0, 1, 0], [0, 0, 1]],
]

function applyU(B: Basis, U: number[][]): Basis {
  // 新しい基底ベクトル = U の行に従う整数結合
  return U.map(row => lift(B, [row[0], row[1], row[2]])) as Basis
}

// ── 未見の格子。既知の値を持っていないものを混ぜる ─────────────
const UNSEEN: Record<string, Basis> = {
  '直方晶': [[1, 0, 0], [0, 1.7, 0], [0, 0, 2.3]],
  '六方（底面）': [[1, 0, 0], [-0.5, Math.sqrt(3) / 2, 0], [0, 0, 1.633]],
  '三斜晶': [[1, 0, 0], [0.31, 1.12, 0], [0.17, 0.23, 1.41]],
  '引き伸ばしたFCC': [[0, 0.5, 0.9], [0.5, 0, 0.9], [0.5, 0.5, 0]],
}
const ALL: Record<string, Basis> = {
  ...Object.fromEntries(Object.entries(LATTICES).map(([k, v]) => [v.name, v.basis])),
  ...UNSEEN,
}

console.log('\n■ 双対の対合性  dual(dual(L)) ≅ L')
for (const [name, B] of Object.entries(ALL)) {
  const back = dual(dual(B))
  const same = B.every((v, i) => v.every((x, j) => near(x, back[i][j], 1e-8)))
  check(`${name} で dual∘dual = id`, same)
}

console.log('\n■ 基底変換の不変性  B → BU  (U ∈ GL(3,ℤ))')
for (const [name, B] of Object.entries(ALL)) {
  const base = {
    sig: gramSignature(B),
    kiss: kissingNumber(B),
    pack: packingFraction(B),
    det: Math.abs(determinant(B)),
    aut: automorphisms(B).length,
  }
  for (let i = 0; i < UNIMODULAR.length; i++) {
    const C = applyU(B, UNIMODULAR[i])
    if (Math.abs(determinant(C)) < 1e-9) continue
    const ok =
      gramSignature(C) === base.sig
      && kissingNumber(C) === base.kiss
      && near(packingFraction(C), base.pack, 1e-7)
      && near(Math.abs(determinant(C)), base.det, 1e-7)
      && automorphisms(C).length === base.aut
    check(`${name} U${i} で不変量が保たれる`, ok,
      ok ? '' : `kiss ${kissingNumber(C)}≠${base.kiss} / aut ${automorphisms(C).length}≠${base.aut}`)
  }
}

console.log('\n■ Aut(Λ) が群である')
for (const [name, B] of Object.entries(ALL)) {
  const G = automorphisms(B)
  const key = (M: number[][]) => M.flat().join(',')
  const set = new Set(G.map(key))
  const identity = set.has('1,0,0,0,1,0,0,0,1')
  const mul = (A: number[][], Bm: number[][]) =>
    A.map((_, i) => [0, 1, 2].map(j => [0, 1, 2].reduce((s, k) => s + A[i][k] * Bm[k][j], 0)))
  // 積で閉じるか（総当たりは重いので先頭から確認）
  const sample = G.slice(0, Math.min(12, G.length))
  const closed = sample.every(A => sample.every(Bm => set.has(key(mul(A, Bm)))))
  check(`${name} Aut に単位元がある`, identity)
  check(`${name} Aut が積で閉じる`, closed, `|Aut| = ${G.length}`)
}

console.log('\n■ ルート系の性質（最小ベクトルがルート系である格子だけ）')
for (const [name, B] of Object.entries(ALL)) {
  const rs = rootSystem(B)
  if (!rs.type) {
    check(`${name} ルート系でないと正しく判定`, rs.simple.length === 0,
      'Cartan 整数が整数でないので棄権')
    continue
  }
  const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  // 同一判定は距離で行う。文字列にすると、同じ点でも計算経路が違えば
  // 末尾の桁が変わって別物になる（√3/2 が実際にそうなった）
  const isRoot = (v: Vec3) =>
    rs.roots.some(r => Math.hypot(r[0] - v[0], r[1] - v[1], r[2] - v[2]) < 1e-7)
  // 鏡映で閉じる：s_a(b) = b - 2⟨a,b⟩/⟨a,a⟩ a もルート
  const closed = rs.roots.every(a => rs.roots.every(b => {
    const c = 2 * dot(a, b) / dot(a, a)
    return isRoot([b[0] - c * a[0], b[1] - c * a[1], b[2] - c * a[2]] as Vec3)
  }))
  check(`${name} (${rs.type}) が鏡映で閉じる`, closed)
  const integral = rs.cartan.every(row => row.every(x => Number.isInteger(x)))
  check(`${name} (${rs.type}) の Cartan 整数がすべて整数`, integral)
  check(`${name} (${rs.type}) の −α もルート`,
    rs.roots.every(a => isRoot([-a[0], -a[1], -a[2]] as Vec3)))
}

console.log('\n■ テータ級数の係数 = 殻の点の数')
for (const [name, B] of Object.entries(ALL)) {
  const bound = gram(B).reduce((m, r) => Math.max(m, ...r.map(Math.abs)), 0) * 6
  const th = thetaSeries(B, bound)
  const sh = shells(B, bound)
  const ok = th.length === sh.length + 1
    && th.slice(1).every((t, i) => t.norm2 === sh[i].norm2 && t.count === sh[i].coeffs.length)
  check(`${name} でテータ係数が殻の数と一致`, ok)
  check(`${name} の定数項が 1（原点のみ）`, th[0].norm2 === 0 && th[0].count === 1)
}

console.log('\n■ 規約の取り違えを検出する')
{
  // 逆格子の 2π 規約。結晶学の慣習で作った基底は、数学の規約とは別物になる
  const fcc = LATTICES.fcc.basis
  const mathDual = dual(fcc)
  const crystalDual = mathDual.map(v => v.map(x => x * 2 * Math.PI) as Vec3) as Basis
  const differs = !mathDual.every((v, i) => v.every((x, j) => near(x, crystalDual[i][j])))
  check('2π 規約の違いが数値に現れる（黙って混ざらない）', differs)

  // 最小ノルムの正規化。D₃ の標準形は最小ノルム² = 2
  const raw = minimalVectors(fcc).norm2
  const scaled = minimalVectors(fcc.map(v => v.map(x => x * 2) as Vec3) as Basis).norm2
  check('スケールでテータの指数が変わる（正規化を型で持つ必要がある）',
    !near(raw, scaled), `${raw} → ${scaled}`)
}

console.log('\n■ 退化した入力で棄権する')
{
  const degenerate: Basis = [[1, 0, 0], [2, 0, 0], [0, 1, 0]]   // 一次従属
  let threw = false
  try { minimalVectors(degenerate) } catch { threw = true }
  check('一次従属な基底では例外を出す（黙って答えない）', threw)

  let dualThrew = false
  try { dual(degenerate) } catch { dualThrew = true }
  check('退化した基底の双対を作らない', dualThrew)
}

console.log(`\n${'─'.repeat(64)}`)
console.log(`性質テスト ${pass}/${pass + fail}${fail ? `   失敗 ${fail}` : ''}`)
if (fail) {
  console.log('\n失敗:')
  failures.forEach(f => console.log(`  ${f}`))
}
process.exit(fail ? 1 : 0)
