/**
 * World-scoped identity と ForbiddenIdentification の検査。
 *
 * 実際に踏んだ false positive が、型として止まるかを確かめる。
 *
 *   npx tsx scripts/identity-test.mts
 */
import {
  createRegistry, registerKnownForbidden, claimIdentity, isForbidden,
  auditIdentity, auditCommutativity, usableInProof, wid,
  PROBLEM_WORLD, SYMPY_WORLD, MATH_WORLD,
  type IdentityClaim, type RouteSquare,
} from '../lib/mortra/kernel/world-identity.js'
import type { SemanticId } from '../lib/mortra/kernel/semantic-kernel.js'

let pass = 0, fail = 0
const check = (n: string, ok: boolean, d = '') => {
  ok ? pass++ : fail++
  console.log(`${ok ? '  ok  ' : '  NG  '} ${n}${ok || !d ? '' : '   ' + d}`)
}
const s = (x: string) => x as SemanticId

const reg = createRegistry()
registerKnownForbidden(reg)

console.log('\n■ 実際に踏んだ false positive が型で止まる')
{
  const cases: [string, string, string][] = [
    ['I を虚数単位と同一視', 'I', 'ImaginaryUnit'],
    ['e を自然対数の底と同一視', 'e', 'E'],
    ['C を sympy の C と同一視', 'C', 'C'],
  ]
  for (const [name, left, right] of cases) {
    const blocked = isForbidden(reg,
      { world: PROBLEM_WORLD, object: s(left) },
      { world: SYMPY_WORLD, object: s(right) })
    check(name, !!blocked, blocked?.reason)
  }
  const bound = isForbidden(reg,
    { world: PROBLEM_WORLD, object: s('a_k:bound') },
    { world: PROBLEM_WORLD, object: s('a_k:free') })
  check('Σ の中の a_k と外の a_k', !!bound, bound?.reason)

  const premise = isForbidden(reg,
    { world: PROBLEM_WORLD, object: s('premise') },
    { world: PROBLEM_WORLD, object: s('conclusion') })
  check('前提の言い換えを答えと呼ぶ', !!premise, premise?.reason)
}

console.log('\n■ 禁じられた同一視は登録できない')
{
  const attempt: IdentityClaim = {
    kind: 'equality',
    left: { world: PROBLEM_WORLD, object: s('I') },
    right: { world: SYMPY_WORLD, object: s('ImaginaryUnit') },
    justification: '記号が同じ',
  }
  const r = claimIdentity(reg, attempt)
  check('「記号が同じ」では通らない', !r.accepted, r.blockedBy?.detail?.slice(0, 40))
}

console.log('\n■ 同一性の種類が分かれている')
{
  check('定義による等式は証明に使える', usableInProof({
    kind: 'definitional_equality', left: { world: MATH_WORLD, object: s('a') },
    right: { world: MATH_WORLD, object: s('b') }, justification: '定義' }))
  check('類似は証明に使えない', !usableInProof({
    kind: 'analogy', left: { world: MATH_WORLD, object: s('a') },
    right: { world: wid('other'), object: s('b') }, justification: '似ている' }))
  check('同型は等式ではない', !usableInProof({
    kind: 'isomorphism', left: { world: MATH_WORLD, object: s('a') },
    right: { world: MATH_WORLD, object: s('b') }, justification: '同型' }))
}

console.log('\n■ world をまたぐ等式は証明書が要る')
{
  const r2 = createRegistry()
  claimIdentity(r2, {
    kind: 'equality',
    left: { world: MATH_WORLD, object: s('x') },
    right: { world: wid('other'), object: s('x') },
    justification: '同じ名前',
  })
  const v = auditIdentity(r2)
  check('証明書なしの跨ぎ等式を落とす',
    v.some(x => x.kind === 'cross_world_equality_without_certificate'),
    v[0]?.detail?.slice(0, 50))
}

console.log('\n■ 経路の可換性を自動で仮定しない')
{
  const squares: RouteSquare[] = [
    { corner: [s('A'), s('B'), s('C'), s('D')],
      routeA: [s('f'), s('g')], routeB: [s('h'), s('k')],
      status: 'commutes' },
  ]
  const v = auditCommutativity(squares)
  check('証明書なしで可換と言っているのを落とす', v.length === 1, v[0]?.detail?.slice(0, 46))

  const withCert: RouteSquare[] = [{ ...squares[0], certificate: s('cert:1') }]
  check('証明書があれば通る', auditCommutativity(withCert).length === 0)
}

console.log(`\n${'─'.repeat(60)}`)
console.log(`identity テスト ${pass}/${pass + fail}`)
process.exit(fail ? 1 : 0)
