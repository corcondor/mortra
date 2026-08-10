/**
 * 解析・数列の問題を形式空間に入れて、どこまで到達するかを測る。
 *
 * 対象: 極限・積分漸化式・非線形漸化式・関数列。
 * ソートは MORPHISM_ATLAS / HYPER_MORPHISM_ATLAS に出るものだけを根に使う。
 *
 * 規律:
 *   - 1問専用の射は入れない
 *   - 「極限を取る」を Sequence -> Real の1本にすると答えを配ってしまうので、
 *     極限は「閉じた形が出た」か「収束の証拠がある」ときにのみ取れるようにする
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

type Case = { id: string; problem: string; roots: string[]; goals: string[] }

const CASES: Case[] = [
  {
    id: 'Wallis積分',
    problem: 'I_n=∫_0^{π/2} sin^n x dx の漸化式を導き lim √n·I_n を求めよ',
    roots: ['Function', 'Sequence'],
    goals: ['Real'],
  },
  {
    id: 'Newton漸化式',
    problem: 'a_1=2, a_{n+1}=(a_n+2/a_n)/2 の lim a_n と |a_n-√2| の評価',
    roots: ['Sequence', 'Function'],
    goals: ['Real'],
  },
  {
    id: 'IMO2014P1',
    problem: '整数列 a_0<a_1<… に対し a_n<(a_0+…+a_n)/n≤a_{n+1} なる n がちょうど一つ',
    roots: ['Sequence', 'ArithmeticObject'],
    goals: ['Proof', 'Proposition'],
  },
  {
    id: '区分求積',
    problem: 'lim (1/n)Σ f(k/n) を定積分に直し Σ 1/(n+k) の極限を求めよ',
    roots: ['FiniteFamily', 'Function'],
    goals: ['Real'],
  },
  {
    id: '関数列',
    problem: 'f_1(x)=x, f_{n+1}(x)=∫_0^x f_n dt の f_n と Σf_n(x) を閉じた形で',
    roots: ['DifferentiableFunction', 'Sequence'],
    goals: ['Function', 'Real'],
  },
  {
    id: '二乗漸化式',
    problem: 'a_1=3, a_{n+1}=a_n^2-2 の一般項を閉じた形で求めよ',
    roots: ['Sequence', 'Polynomial'],
    goals: ['FiniteFamily', 'Real'],
  },
  {
    id: '積分不等式',
    problem: 'J_n=∫_0^1 x^n/(1+x)dx に対し J_n+J_{n+1}=1/(n+1) を示し lim n·J_n を求めよ',
    roots: ['Function', 'Sequence'],
    goals: ['Real', 'Proof'],
  },
]

/** 追加する射。すべて「解析・数列に共通する操作」であって、特定の1問の解法ではない。 */
const ADDED: HyperMorphismSchema[] = [
  // (0) ソート設計の是正。Scalar と Real は同じ対象なのに分断されていた
  { name: 'ScalarAsReal', sources: ['Scalar'], target: 'Real', preserves: ['value'], backend: ['identity'] },
  { name: 'RealAsScalar', sources: ['Real'], target: 'Scalar', preserves: ['value'], backend: ['identity'] },

  // (1) 数列の出入口。素の Sequence は Matrix2 への1本しか出口が無く、そこは行き止まり
  { name: 'SequenceTermFamily', sources: ['Sequence'], target: 'FiniteFamily', preserves: ['index-set', 'order'], backend: ['recurrence-engine'] },
  { name: 'IndexedIntegralSequence', sources: ['Function'], target: 'Sequence', preserves: ['index-set', 'linearity'], backend: ['symbolic-integration', 'recurrence-engine'] },

  // (2) 漸化式そのものをソートに昇格させる。抽出 -> 解く -> 一般項
  { name: 'RecurrenceExtraction', sources: ['Sequence'], target: 'RecurrenceRelation', preserves: ['index-shift', 'initial-state'], backend: ['recurrence-engine', 'symbolic-identity'] },
  { name: 'RecurrenceSolution', sources: ['RecurrenceRelation'], target: 'ClosedFormSequence', preserves: ['index-shift', 'initial-state'], backend: ['sympy.rsolve', 'generating-function'] },
  { name: 'ClosedFormRealization', sources: ['ClosedFormSequence'], target: 'Sequence', preserves: ['index-set', 'value'], backend: ['identity'] },
  { name: 'ClosedFormTermFamily', sources: ['ClosedFormSequence'], target: 'FiniteFamily', preserves: ['index-set', 'multiplicity'], backend: ['recurrence-engine'] },

  // (3) 極限。無料では取らせない。閉じた形か収束証拠を経由させる
  { name: 'LimitOfClosedForm', sources: ['ClosedFormSequence'], target: 'Real', preserves: ['limit'], backend: ['sympy.limit'] },
  { name: 'MonotoneBoundedCertificate', sources: ['Sequence', 'Proposition'], target: 'ConvergenceCertificate', preserves: ['both-parent-provenance', 'order', 'boundedness'], backend: ['induction-engine', 'cvc5'] },
  { name: 'SqueezeCertificate', sources: ['Sequence', 'ClosedFormSequence'], target: 'ConvergenceCertificate', preserves: ['both-parent-provenance', 'order', 'limit'], backend: ['interval-arithmetic', 'sympy.limit'] },
  { name: 'CertifiedLimit', sources: ['Sequence', 'ConvergenceCertificate'], target: 'Real', preserves: ['both-parent-provenance', 'limit'], backend: ['limit-engine'] },

  // (4) 和 -> 積分。区分求積・級数に共通
  { name: 'RiemannSumLimit', sources: ['FiniteFamily', 'Function'], target: 'Real', preserves: ['both-parent-provenance', 'measure-class', 'limit'], backend: ['symbolic-integration', 'limit-engine'] },
  { name: 'FunctionSeriesLimit', sources: ['Sequence', 'Function'], target: 'Function', preserves: ['both-parent-provenance', 'uniform-limit'], backend: ['series-engine'] },

  // (5) 主張と証明。解析側から Proposition / Proof に入る道が1本も無かった
  { name: 'OrderComparison', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['both-parent-provenance', 'order'], backend: ['cvc5', 'interval-arithmetic'] },
  { name: 'InductionSchema', sources: ['Sequence', 'Proposition'], target: 'Proposition', preserves: ['both-parent-provenance', 'index-shift', 'truth'], backend: ['induction-engine', 'smt'] },
  { name: 'ProofObligation', sources: ['Proposition'], target: 'Proof', preserves: ['truth'], backend: ['lean', 'smt'] },
]

const OPTS = { maxDepth: 10, maxStates: 200_000 }

function run(rules: readonly HyperMorphismSchema[]) {
  return CASES.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], { ...OPTS, goalSorts: c.goals, rules })
    const perSort = new Map<string, number>()
    for (const g of r.goals) if (!perSort.has(g.sort)) perSort.set(g.sort, g.depth)
    const missing = new Map<string, number>()
    for (const f of r.frontier) for (const m of f.missing) missing.set(m, (missing.get(m) ?? 0) + 1)
    const sorts = [...new Set(r.terms.map(t => t.sort))].sort()
    return { id: c.id, goals: r.goals.length, terms: r.terms.length, perSort, missing, sorts, all: r.goals }
  })
}

const base = executableMorphismAtlas()
console.log(`素のアトラス: ${base.length}本 / 追加後: ${base.length + ADDED.length}本 (追加 ${ADDED.length}本)\n`)

const before = run(base)
const after = run([...base, ...ADDED])

console.log('=== 到達数 ===')
console.log('問題            素:到達/項      追加後:到達/項    追加後の到達ソート(最短深さ)')
for (let i = 0; i < CASES.length; i++) {
  const b = before[i], a = after[i]
  const reached = [...a.perSort.entries()].map(([s, d]) => `${s}@d${d}`).join(' ') || '(なし)'
  console.log(
    `${b.id.padEnd(14)} ${String(b.goals).padStart(4)} /${String(b.terms).padStart(5)}    `
    + `${String(a.goals).padStart(5)} /${String(a.terms).padStart(5)}     ${reached}`,
  )
}

console.log('\n=== 素の状態: 各問題から到達できたソートの全体 ===')
for (const b of before) console.log(`${b.id.padEnd(14)} ${b.sorts.join(', ')}`)

console.log('\n=== 素の状態の frontier 不足ソート（頻度） ===')
const missTotal = new Map<string, number>()
for (const b of before) {
  const top = [...b.missing.entries()].sort((x, y) => y[1] - x[1])
  console.log(`${b.id.padEnd(14)} ${top.map(([s, n]) => `${s}(${n})`).join(' ') || '(frontier空=領域ごと切断)'}`)
  for (const [s, n] of b.missing) missTotal.set(s, (missTotal.get(s) ?? 0) + n)
}
console.log('合計:', [...missTotal.entries()].sort((x, y) => y[1] - x[1]).map(([s, n]) => `${s}(${n})`).join(' '))

console.log('\n=== 追加後: 各ゴールソートへの最短経路 ===')
for (const a of after) {
  if (!a.goals) { console.log(`${a.id}: 到達せず`); continue }
  const shown = new Set<string>()
  for (const g of a.all) {
    if (shown.has(g.sort)) continue
    shown.add(g.sort)
    console.log(`${a.id} → ${g.sort} (深さ${g.depth}): ${g.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}`)
  }
}

// ---- 意図した経路が存在するか（型が通るだけの偽陽性と区別する） ----
// 型が通る = 数学が合っている ではない。問題ごとに「この射が経路に居なければ
// その問題を解いたことにならない」ものを指定して、そんな経路が実在するか調べる。
const INTENDED: Record<string, string[]> = {
  'Wallis積分': ['IndexedIntegralSequence', 'RecurrenceExtraction', 'RecurrenceSolution'],
  'Newton漸化式': ['RecurrenceExtraction', 'CertifiedLimit'],
  'IMO2014P1': ['SequenceTermFamily', 'OrderComparison', 'ProofObligation'],
  '区分求積': ['RiemannSumLimit'],
  '関数列': ['RecurrenceExtraction', 'FunctionSeriesLimit'],
  '二乗漸化式': ['RecurrenceExtraction', 'RecurrenceSolution', 'ClosedFormTermFamily'],
  '積分不等式': ['IndexedIntegralSequence', 'RecurrenceExtraction', 'OrderComparison'],
}
console.log('\n=== 意図した経路が実在するか ===')
for (const a of after) {
  const need = INTENDED[a.id]
  const hit = a.all.find(g => {
    const names = new Set((g.steps as Array<{ morphism: string }>).map(s => s.morphism))
    return need.every(n => names.has(n))
  })
  console.log(
    `${a.id.padEnd(14)} 要求[${need.join(',')}] → ${hit ? `有り (${hit.sort} 深さ${hit.depth})` : '無し ※型は通るが数学が通っていない'}`,
  )
  if (hit) console.log(`               ${(hit.steps as Array<{ morphism: string }>).map(s => s.morphism).join(' → ')}`)
}

// ---- leave-one-out: どの追加射が実際に効いているか ----
// 判定は「到達したゴールソートの集合」で行う。項数は探索の副産物でノイズが多い。
console.log('\n=== leave-one-out（その射を抜くとゴールソートを失う問題） ===')
const fullSorts = after.map(a => new Set(a.perSort.keys()))
for (const m of ADDED) {
  const rules = [...base, ...ADDED.filter(x => x.name !== m.name)]
  const r = run(rules)
  const lost: string[] = []
  const zeroed: string[] = []
  for (let i = 0; i < CASES.length; i++) {
    const now = new Set(r[i].perSort.keys())
    const missing = [...fullSorts[i]].filter(s => !now.has(s))
    if (missing.length) lost.push(`${CASES[i].id}(${missing.join('/')})`)
    if (now.size === 0 && fullSorts[i].size > 0) zeroed.push(CASES[i].id)
  }
  console.log(
    `${m.name.padEnd(28)} ${String(lost.length)}問: ${lost.join(' ') || '(到達ソートは変わらず)'}`
    + `${zeroed.length ? `  【全滅: ${zeroed.join(',')}】` : ''}`,
  )
}

// ---- 各射が「何問の到達経路に現れるか」（一般性の粗い指標） ----
console.log('\n=== 追加射が到達経路に現れた問題数 ===')
const appear = new Map<string, Set<string>>()
for (const a of after) {
  const shown = new Set<string>()
  for (const g of a.all) {
    if (shown.has(g.sort)) continue
    shown.add(g.sort)
    for (const s of g.steps as Array<{ morphism: string }>) {
      if (!ADDED.some(x => x.name === s.morphism)) continue
      appear.set(s.morphism, (appear.get(s.morphism) ?? new Set()).add(a.id))
    }
  }
}
for (const m of ADDED) {
  const rows = [...(appear.get(m.name) ?? [])]
  console.log(`${m.name.padEnd(28)} ${rows.length}問: ${rows.join(', ') || '(最短経路には未出現)'}`)
}
