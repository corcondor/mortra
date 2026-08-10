/**
 * 数論を形式空間に入れて、素のアトラスがどこまで到達するかを測る。
 *
 * 手順:
 *  1. 実在の数論問題7問を root_sorts / query_sorts に手で形式化
 *  2. 素のアトラスで走らせ到達数を測る
 *  3. frontier の missing ソートを集計
 *  4. 一般性のある射を足して再測定
 *  5. 各射がどの問題で実際に使われたかを数え、暗記か語彙かを判定
 */
import { enumerateTypedTerms } from './typed-term-enumerator.ts'
import { executableMorphismAtlas } from './generalization-kernel.ts'
import type { HyperMorphismSchema, SemanticHypergraph } from './generalization-kernel.ts'

function graph(id: string, rootSorts: string[], querySorts: string[]): SemanticHypergraph {
  return {
    parent_id: id,
    nodes: rootSorts.map((sort, i) => ({ id: `${id}:n${i}`, sort, label: sort } as never)),
    edges: [],
    root_sorts: rootSorts,
    query_sorts: querySorts,
    language_analysis: {
      token_count: 0, parse_count: 1, parse_truncated: false, clause_count: 1,
      quantifier_prefix: [], definitions: [], declarations: [],
      constraints: [], unresolved_references: [], diagnostics: ['手で形式化'],
    },
  }
}

/**
 * 追加する射。1問専用は禁止。数論の複数問題に効く一般性で定義する。
 */
const ADDED: HyperMorphismSchema[] = [
  // --- (A) 配管: アトラスに生成源が無いソートの入口 ---
  {
    name: 'IntegerPairFormation',
    sources: ['Integer', 'Integer'], target: 'IntegerPair',
    preserves: ['both-parent-provenance', 'integrality'],
    backend: ['integer-arithmetic'],
  },
  {
    name: 'PrimeRestriction',
    sources: ['Integer'], target: 'PrimeSpectrum',
    preserves: ['primality'],
    backend: ['primality-test', 'modular-arithmetic'],
  },
  {
    name: 'IntegerAsArithmeticObject',
    sources: ['Integer'], target: 'ArithmeticObject',
    preserves: ['value', 'integrality'],
    backend: ['identity'],
  },
  {
    name: 'ScalarAsArithmeticObject',
    sources: ['Scalar'], target: 'ArithmeticObject',
    preserves: ['value'],
    backend: ['identity'],
  },
  {
    name: 'IntegerAsReal',
    sources: ['Integer'], target: 'Real',
    preserves: ['value', 'order'],
    backend: ['identity'],
  },
  {
    name: 'ScalarAsReal',
    sources: ['Scalar'], target: 'Real',
    preserves: ['value', 'order'],
    backend: ['identity'],
  },

  // --- (B) 数論固有の語彙 ---
  {
    name: 'SequenceIndexing',
    sources: ['Sequence'], target: 'FiniteFamily',
    preserves: ['index-set', 'multiplicity'],
    backend: ['recurrence-engine', 'index-truncation'],
  },
  {
    name: 'DivisorLattice',
    sources: ['Integer'], target: 'FiniteSet',
    preserves: ['divisor-lattice', 'prime-valuations'],
    backend: ['prime-valuation', 'integer-factorization'],
  },
  {
    name: 'PrimeValuation',
    sources: ['Integer', 'PrimeSpectrum'], target: 'IntegerInvariant',
    preserves: ['both-parent-provenance', 'prime-valuations'],
    backend: ['prime-valuation', 'legendre-formula'],
  },
  {
    name: 'ModularInversion',
    sources: ['FiniteSet', 'IntegerPair'], target: 'Integer',
    preserves: ['both-parent-provenance', 'unit-group-action', 'bezout-ideal'],
    backend: ['extended-euclidean-algorithm', 'modular-arithmetic'],
  },
  {
    name: 'InvariantAsInteger',
    sources: ['IntegerInvariant'], target: 'Integer',
    preserves: ['value'],
    backend: ['identity'],
  },
  {
    // 数列を法 m で見て周期軌道を取る。位数・周期・巡回性を扱う数論の中核操作。
    name: 'ResidueOrbitOfSequence',
    sources: ['Sequence', 'FiniteSet'], target: 'Orbit',
    preserves: ['both-parent-provenance', 'congruence-class', 'periodicity'],
    backend: ['modular-arithmetic', 'recurrence-engine'],
  },

  // --- (C) 証明への出口。既存の PredicateLift の純算術版 ---
  {
    name: 'ArithmeticPredicateLift',
    sources: ['ArithmeticObject', 'IntegerPredicate'], target: 'Proposition',
    preserves: ['both-parent-provenance', 'integrality'],
    backend: ['integer-arithmetic', 'presburger-arithmetic'],
  },
  {
    name: 'PrimeArithmeticPredicateLift',
    sources: ['ArithmeticObject', 'PrimeSpectrum'], target: 'Proposition',
    preserves: ['both-parent-provenance', 'primality'],
    backend: ['primality-test', 'integer-arithmetic'],
  },
  {
    name: 'CongruencePredicateLift',
    sources: ['FiniteSet', 'IntegerPredicate'], target: 'Proposition',
    preserves: ['both-parent-provenance', 'congruence-class'],
    backend: ['modular-arithmetic', 'presburger-arithmetic'],
  },
  {
    name: 'CoprimalityProposition',
    sources: ['GCDValue', 'IntegerPredicate'], target: 'Proposition',
    preserves: ['both-parent-provenance', 'common-divisor-order'],
    backend: ['extended-euclidean-algorithm', 'presburger-arithmetic'],
  },
  {
    name: 'PropositionCertification',
    sources: ['Proposition'], target: 'Proof',
    preserves: ['truth'],
    backend: ['lean', 'smt', 'symbolic-identity'],
  },
]

const CASES = [
  {
    id: 'P1包除カウント',
    problem: '1〜100の整数で3の倍数でも5の倍数でもないものの個数（頻出入試）',
    roots: ['Integer', 'IntegerPair'], goals: ['Integer', 'FiniteSet'],
  },
  {
    id: 'P2床関数の和',
    problem: 'Σ_{n=1}^{2024} ⌊√n⌋ を求めよ（京大・一橋系の頻出）',
    roots: ['Sequence', 'Real'], goals: ['Scalar', 'Integer'],
  },
  {
    id: 'P3互いに素',
    problem: 'gcd(21n+4, 14n+3)=1 を示せ（IMO 1959 P1）',
    roots: ['IntegerPair', 'Sequence'], goals: ['Proposition', 'Proof'],
  },
  {
    id: 'P4Wilson',
    problem: 'p が素数のとき (p-1)! ≡ -1 (mod p) を示せ（Wilson・東工大類題）',
    roots: ['PrimeSpectrum', 'FiniteFamily'], goals: ['Proposition', 'Proof'],
  },
  {
    id: 'P5Legendre',
    problem: 'n! を割り切る素数 p の最大指数を求めよ（Legendre・京大類題）',
    roots: ['Integer', 'PrimeSpectrum'], goals: ['Integer', 'IntegerInvariant'],
  },
  {
    id: 'P6位数',
    problem: '2^n − 1 が 7 で割り切れる自然数 n をすべて求めよ（IMO 1964 P1）',
    roots: ['Sequence', 'Integer'], goals: ['FiniteSet', 'IntegerPredicate'],
  },
  {
    id: 'P7mod逆元',
    problem: 'gcd(a,p)=1 のとき ax ≡ 1 (mod p) の解 x を求めよ（一橋類題）',
    roots: ['IntegerPair', 'PrimeSpectrum'], goals: ['Integer', 'FiniteSet'],
  },
]

/**
 * ホールドアウト。射を設計したあとで選んだ問題。
 * ここで到達が増えれば「足した理由と違う問題にも効いた」＝語彙。
 */
const HOLDOUT = [
  {
    id: 'H1三乗差6倍数',
    problem: 'n^3 − n が 6 の倍数であることを示せ（東大類題）',
    roots: ['Sequence', 'Integer'], goals: ['Proposition', 'Proof'],
  },
  {
    id: 'H2素数p^q+q^p',
    problem: 'p, q が素数で p^q + q^p も素数となる組を求めよ（京大2014）',
    roots: ['PrimeSpectrum', 'IntegerPair'], goals: ['FiniteSet', 'Proposition'],
  },
  {
    id: 'H3約数個数奇数',
    problem: '約数の個数 d(n) が奇数となる n を特徴づけよ（一橋類題）',
    roots: ['Integer', 'FiniteSet'], goals: ['IntegerPredicate', 'Proposition'],
  },
  {
    id: 'H4IMO1988P6',
    problem: '(a²+b²)/(ab+1) が整数ならそれは平方数（IMO 1988 P6）',
    roots: ['IntegerPair', 'IntegerPredicate'], goals: ['Proposition', 'Proof'],
  },
  {
    id: 'H5フェルマー小',
    problem: 'gcd(a,p)=1, p 素数のとき a^{p-1} ≡ 1 (mod p)（フェルマーの小定理）',
    roots: ['PrimeSpectrum', 'Sequence'], goals: ['Proposition', 'FiniteSet'],
  },
]

/** 問題の与件を全部使って goal に届いたか（片方の根だけを使う項は問題を解いていない） */
const DEPTH = Number(process.env.DEPTH ?? 6)
function usesAllRoots(expression: string, roots: string[]): boolean {
  return roots.every(sort => expression.includes(`,"${sort}")`))
}

function run(rules: readonly HyperMorphismSchema[], cases: typeof CASES = CASES) {
  return cases.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: DEPTH, maxStates: 200_000, goalSorts: c.goals, rules,
    })
    const strict = r.goals.filter(g => usesAllRoots(g.expression, c.roots))
    // 到達可能ソート（未生成ソートの診断用）
    const produced = new Set(r.terms.map(t => t.sort))
    return {
      id: c.id, roots: c.roots, goals: r.goals.length, strict: strict.length,
      terms: r.terms.length, best: r.goals[0], bestStrict: strict[0],
      frontier: r.frontier, all: r.goals, produced,
      unreachedGoalSorts: c.goals.filter(g => !produced.has(g)),
    }
  })
}

const base = executableMorphismAtlas()
console.log(`素のアトラス: 射 ${base.length}本 / 追加 ${ADDED.length}本\n`)

const before = run(base)
const after = run([...base, ...ADDED])

console.log('=== 到達数 ===')
console.log('  緩い到達 = goal ソートに届いた項（片方の根だけでもよい）')
console.log('  厳密到達 = 問題の与件（root_sorts）を全部使って goal に届いた項\n')
console.log('                素のアトラス            射追加後')
console.log('                緩い / 厳密 / 探索項    緩い / 厳密 / 探索項')
for (let i = 0; i < CASES.length; i++) {
  const b = before[i], a = after[i]
  const changed = a.strict > b.strict ? '  ← 厳密到達が増加'
    : (b.strict === 0 && a.strict === 0 ? '  ← 厳密未到達のまま' : '')
  console.log(
    `${b.id.padEnd(14)}  ${String(b.goals).padStart(4)} /${String(b.strict).padStart(4)} / ${String(b.terms).padStart(5)}    `
    + `${String(a.goals).padStart(4)} /${String(a.strict).padStart(4)} / ${String(a.terms).padStart(5)}${changed}`,
  )
}
const sum = (xs: typeof before, k: 'goals' | 'strict') => xs.reduce((s, x) => s + x[k], 0)
console.log(`\n素:     緩い合計 ${sum(before, 'goals')} / 厳密合計 ${sum(before, 'strict')} / 緩い到達 ${before.filter(x => x.goals > 0).length}問 / 厳密到達 ${before.filter(x => x.strict > 0).length}問（全${CASES.length}問）`)
console.log(`追加後: 緩い合計 ${sum(after, 'goals')} / 厳密合計 ${sum(after, 'strict')} / 緩い到達 ${after.filter(x => x.goals > 0).length}問 / 厳密到達 ${after.filter(x => x.strict > 0).length}問`)

console.log('\n=== 素のアトラスでの経路 ===')
for (const b of before) {
  const lax = b.best ? `${b.best.sort} 深さ${b.best.depth} [${b.best.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}]` : '到達せず'
  const st = b.bestStrict ? `${b.bestStrict.sort} 深さ${b.bestStrict.depth} [${b.bestStrict.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}]` : '到達せず'
  console.log(`${b.id}`)
  console.log(`  緩い: ${lax}`)
  console.log(`  厳密: ${st}`)
  if (b.unreachedGoalSorts.length) console.log(`  一度も生成されなかった goal ソート: ${b.unreachedGoalSorts.join(', ')}`)
}

// 生成源が一本も無いソート（frontier より強い診断）
console.log('\n=== 素のアトラスで「生成源ゼロ」のソート（入次数0） ===')
const targets = new Set(base.map(m => m.target))
const sources = new Set(base.flatMap(m => m.sources))
const orphanInputs = [...sources].filter(s => !targets.has(s)).sort()
console.log(`  ${orphanInputs.join(', ')}`)
console.log('  → これらは root に置かない限り絶対に作れない')

console.log('\n=== 未達/不足ソートの問題別集計（素のアトラス） ===')
const missCount = new Map<string, Set<string>>()
for (const b of before) {
  const need = new Set<string>()
  // goal に届かなかったソート
  for (const g of b.unreachedGoalSorts) need.add(`GOAL:${g}`)
  // frontier が報告した不足
  for (const f of b.frontier) for (const m of f.missing) need.add(m)
  // 厳密到達に失敗している場合、根を結合する射が無い＝結合点の不在
  if (b.strict === 0) need.add('（2根を結合する射そのもの）')
  for (const m of need) {
    const s = missCount.get(m) ?? new Set<string>(); s.add(b.id); missCount.set(m, s)
  }
}
for (const [sort, s] of [...missCount.entries()].sort((a, b) => b[1].size - a[1].size)) {
  console.log(`  ${sort.padEnd(30)} ${s.size}問  [${[...s].join(', ')}]`)
}

console.log('\n=== 射追加後の経路（厳密到達の最短経路） ===')
for (const a of after) {
  const st = a.bestStrict
  if (st) {
    console.log(`${a.id}: ${st.sort} 深さ${st.depth}`)
    console.log(`  ${st.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}`)
  } else {
    console.log(`${a.id}: 厳密到達せず`)
  }
}

// leave-one-out アブレーション。厳密到達がどの問題で落ちるかで語彙/暗記を判定する。
console.log('\n=== leave-one-out アブレーション（暗記か語彙かの判定） ===')
console.log('  射を1本抜いて厳密到達がゼロに落ちる問題を数える。')
console.log('  1問だけ落ちる = その1問専用（暗記の疑い）。複数問で落ちる = 語彙。\n')
const fullStrict = new Map(after.map(a => [a.id, a.strict]))
for (const m of ADDED) {
  const rules = [...base, ...ADDED.filter(x => x.name !== m.name)]
  const r = run(rules)
  const lost = r.filter(x => x.strict === 0 && (fullStrict.get(x.id) ?? 0) > 0).map(x => x.id)
  const dropped = r.filter(x => x.strict < (fullStrict.get(x.id) ?? 0)).map(x => x.id)
  const verdict = lost.length === 0
    ? (dropped.length >= 2 ? `必須ではないが${dropped.length}問で経路数を増やす → 語彙（冗長）` : dropped.length === 1 ? '1問で経路数のみ増やす → 冗長' : '効果なし')
    : lost.length === 1 ? `${lost.length}問が到達不能に → 暗記の疑い`
    : `${lost.length}問が到達不能に → 語彙`
  console.log(`  ${m.name.padEnd(30)} ${verdict}`)
  if (lost.length) console.log(`      到達不能化: [${lost.join(', ')}]`)
}

// ---- ホールドアウト：射を設計したあとで選んだ問題に効くか ----
console.log('\n\n########## ホールドアウト（射の設計に使っていない5問） ##########')
const hBefore = run(base, HOLDOUT)
const hAfter = run([...base, ...ADDED], HOLDOUT)
console.log('\n                素のアトラス            射追加後')
console.log('                緩い / 厳密 / 探索項    緩い / 厳密 / 探索項')
for (let i = 0; i < HOLDOUT.length; i++) {
  const b = hBefore[i], a = hAfter[i]
  const changed = a.strict > b.strict ? '  ← 厳密到達が増加' : (a.strict === 0 ? '  ← 厳密未到達のまま' : '')
  console.log(
    `${b.id.padEnd(14)}  ${String(b.goals).padStart(4)} /${String(b.strict).padStart(4)} / ${String(b.terms).padStart(5)}    `
    + `${String(a.goals).padStart(4)} /${String(a.strict).padStart(4)} / ${String(a.terms).padStart(5)}${changed}`,
  )
}
console.log(`\n素:     厳密到達 ${hBefore.filter(x => x.strict > 0).length}/${HOLDOUT.length}問（厳密合計 ${hBefore.reduce((s, x) => s + x.strict, 0)}）`)
console.log(`追加後: 厳密到達 ${hAfter.filter(x => x.strict > 0).length}/${HOLDOUT.length}問（厳密合計 ${hAfter.reduce((s, x) => s + x.strict, 0)}）`)

console.log('\n=== ホールドアウトの厳密到達経路 ===')
for (const a of hAfter) {
  const st = a.bestStrict
  console.log(st
    ? `${a.id}: ${st.sort} 深さ${st.depth}\n  ${st.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}`
    : `${a.id}: 厳密到達せず`)
}

console.log('\n=== ホールドアウトでの leave-one-out（設計理由と違う問題に効いたか） ===')
const hFull = new Map(hAfter.map(a => [a.id, a.strict]))
for (const m of ADDED) {
  const rules = [...base, ...ADDED.filter(x => x.name !== m.name)]
  const r = run(rules, HOLDOUT)
  const lost = r.filter(x => x.strict === 0 && (hFull.get(x.id) ?? 0) > 0).map(x => x.id)
  const dropped = r.filter(x => x.strict < (hFull.get(x.id) ?? 0)).map(x => x.id)
  console.log(`  ${m.name.padEnd(30)} 到達不能化 ${lost.length}問 [${lost.join(', ')}] / 経路減 ${dropped.length}問`)
}
