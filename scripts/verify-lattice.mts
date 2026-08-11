/**
 * Lattice Core の検算。
 *
 * 主張は全部、独立に知られている値と突き合わせる。
 * 一致しなければ落とす。「それらしい絵が出た」は結果ではない。
 *
 *   npx tsx scripts/verify-lattice.mts
 */
import {
  LATTICES, dual, gram, determinant, kissingNumber, packingFraction,
  thetaSeries, automorphisms, rootSystem, millerPlane, minimalVectors,
  type Basis, type Vec3,
} from '../lib/vision/lattice.js'

let pass = 0
let fail = 0

function check(name: string, got: unknown, want: unknown, tol = 0) {
  const ok = typeof got === 'number' && typeof want === 'number'
    ? Math.abs(got - want) <= tol
    : JSON.stringify(got) === JSON.stringify(want)
  console.log(`${ok ? '  ok  ' : '  NG  '} ${name.padEnd(46)} ${JSON.stringify(got)}${ok ? '' : `  期待 ${JSON.stringify(want)}`}`)
  ok ? pass++ : fail++
}

const near = (B: Basis, C: Basis) =>
  B.every((v, i) => v.every((x, j) => Math.abs(x - C[i][j]) < 1e-9))

/** 双対の基底は取り方が違いうるので、Gram 行列で比べる */
const sameLattice = (B: Basis, C: Basis) => {
  const g1 = gram(B), g2 = gram(C)
  const s1 = JSON.stringify(g1.flat().map(x => +x.toFixed(9)).sort((a, b) => a - b))
  const s2 = JSON.stringify(g2.flat().map(x => +x.toFixed(9)).sort((a, b) => a - b))
  return s1 === s2
}

console.log('\n■ 配位数（接吻数）— 結晶学で確立した値')
check('SC  の配位数', kissingNumber(LATTICES.sc.basis), 6)
check('FCC の配位数', kissingNumber(LATTICES.fcc.basis), 12)
check('BCC の配位数', kissingNumber(LATTICES.bcc.basis), 8)

console.log('\n■ 充填率 — 閉じた式と一致するか')
check('SC  の充填率 π/6', packingFraction(LATTICES.sc.basis), Math.PI / 6, 1e-12)
check('FCC の充填率 π/(3√2)', packingFraction(LATTICES.fcc.basis), Math.PI / (3 * Math.SQRT2), 1e-12)
check('BCC の充填率 π√3/8', packingFraction(LATTICES.bcc.basis), (Math.PI * Math.sqrt(3)) / 8, 1e-12)

console.log('\n■ 双対（逆格子）— FCC ↔ BCC が入れ替わるか')
const fccDual = dual(LATTICES.fcc.basis)
const bccDual = dual(LATTICES.bcc.basis)
check('FCC の双対は BCC 型', sameLattice(fccDual, LATTICES.bcc.basis.map(v => v.map(x => x * 2) as Vec3) as Basis), true)
check('BCC の双対は FCC 型', sameLattice(bccDual, LATTICES.fcc.basis.map(v => v.map(x => x * 2) as Vec3) as Basis), true)
check('SC は自己双対', near(dual(LATTICES.sc.basis), LATTICES.sc.basis), true)
check('det(FCC)', determinant(LATTICES.fcc.basis), 0.25, 1e-12)

console.log('\n■ Miller 面 — 立方晶の面間隔 d = a/√(h²+k²+l²)')
{
  const cube = LATTICES.sc.basis
  for (const hkl of [[1, 0, 0], [1, 1, 0], [1, 1, 1], [2, 1, 0]] as [number, number, number][]) {
    const d = millerPlane(cube, hkl).spacing
    const want = 1 / Math.hypot(...hkl)
    check(`SC (${hkl.join('')}) の面間隔`, +d.toFixed(9), +want.toFixed(9), 1e-9)
  }
}

console.log('\n■ Aut(Λ) — 立方格子の点群の位数は 48 (O_h)')
check('SC  の Aut の位数', automorphisms(LATTICES.sc.basis).length, 48)
check('FCC の Aut の位数', automorphisms(LATTICES.fcc.basis).length, 48)
check('BCC の Aut の位数', automorphisms(LATTICES.bcc.basis).length, 48)

console.log('\n■ ルート系 — FCC の最近接 12 本は A₃')
{
  const rs = rootSystem(LATTICES.fcc.basis)
  check('FCC のルートの本数', rs.roots.length, 12)
  check('FCC の単純ルートの本数', rs.simple.length, 3)
  check('FCC のルート系の型', rs.type, 'A3')
  check('Cartan 対角成分が 2', rs.cartan.every((r, i) => r[i] === 2), true)
  const off = rs.cartan.flatMap((r, i) => r.filter((_, j) => i !== j))
  check('Cartan 非対角が 0 か -1', off.every(x => x === 0 || x === -1), true)
  console.log('       Cartan =', JSON.stringify(rs.cartan))
}

console.log('\n■ テータ級数 — D₃(=FCC) の殻の個数')
{
  // FCC の基底ベクトルはノルム² = 1/2。D₃ の標準形は最小ノルム² = 2 なので 2 倍する
  const d3: Basis = LATTICES.fcc.basis.map(v => v.map(x => x * 2) as Vec3) as Basis
  const th = thetaSeries(d3, 20).map(t => ({ n: Math.round(t.norm2), c: t.count }))
  console.log('       Θ =', th.map(t => `${t.c}q^${t.n}`).join(' + '))
  // D₃ の既知の殻の個数（ノルム² = 2,4,6,… の順に）
  const want = [[0, 1], [2, 12], [4, 6], [6, 24], [8, 12], [10, 24],
                [12, 8], [14, 48], [16, 6], [18, 36], [20, 24]]
  check('D₃ のテータ級数の係数', th.map(t => [t.n, t.c]), want)
}

console.log('\n■ 同一性の追跡 — 最小ベクトルが逆格子でどこへ行くか')
{
  // FCC の最小ベクトルは 12 本。その双対（BCC）の最小ベクトルは 8 本。
  // 本数が変わることが「別の姿になった」ことの一番素朴な証拠
  const a = minimalVectors(LATTICES.fcc.basis)
  const b = minimalVectors(dual(LATTICES.fcc.basis) as Basis)
  check('FCC の最小ベクトル数', a.coeffs.length, 12)
  check('その逆格子の最小ベクトル数', b.coeffs.length, 8)
}

console.log(`\n${'─'.repeat(64)}`)
console.log(`検算 ${pass}/${pass + fail}${fail ? `   失敗 ${fail}` : ''}`)
process.exit(fail ? 1 : 0)
