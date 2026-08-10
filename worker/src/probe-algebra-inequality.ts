/**
 * 代数・不等式（対称式 / 相加相乗 / 解と係数）を形式空間に入れて到達を測る。
 *
 * 手順: 素のアトラスで走らせる → frontier の不足ソートを集計 → 射を足して再測定。
 * 射は「その分野の複数問題に効く」ものだけ。1問専用は暗記なので入れない。
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

// ---------------------------------------------------------------------------
// 実在の問題。ソートは MORPHISM_ATLAS に登場するものだけから手で選ぶ。
// ---------------------------------------------------------------------------
const CASES = [
  {
    id: 'IMO1995-P2',
    text: 'a,b,c>0, abc=1 のとき 1/(a^3(b+c))+1/(b^3(c+a))+1/(c^3(a+b)) >= 3/2',
    roots: ['FiniteFamily', 'PolynomialSystem'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: 'IMO2001-P2',
    text: 'a,b,c>0 のとき a/sqrt(a^2+8bc)+b/sqrt(b^2+8ca)+c/sqrt(c^2+8ab) >= 1',
    roots: ['FiniteFamily'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: 'IMO1964-P2',
    text: '三角形の3辺 a,b,c に対し a^2(b+c-a)+b^2(c+a-b)+c^2(a+b-c) <= 3abc',
    roots: ['Triangle', 'FiniteFamily'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: 'IMO1983-P6',
    text: '三角形の3辺 a,b,c に対し a^2 b(a-b)+b^2 c(b-c)+c^2 a(c-a) >= 0',
    roots: ['Triangle', 'FiniteFamily'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: 'IMO1984-P1',
    text: 'x+y+z=1, x,y,z>=0 のとき 0 <= xy+yz+zx-2xyz <= 7/27（最大値問題）',
    roots: ['FiniteFamily', 'PolynomialSystem'],
    goals: ['Real', 'Scalar', 'Proposition'],
  },
  {
    id: 'IMO2005-P3',
    text: 'x,y,z>0, xyz>=1 のとき (x^5-x^2)/(x^5+y^2+z^2)+... >= 0',
    roots: ['FiniteFamily', 'PolynomialSystem'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: 'Putnam2003-A2',
    text: '(a1..an)^(1/n)+(b1..bn)^(1/n) <= ((a1+b1)..(an+bn))^(1/n)（相加相乗の超加法性）',
    roots: ['FiniteFamily', 'Sequence'],
    goals: ['Proposition', 'Proof'],
  },
  {
    id: '例:xy+1/xy',
    text: 'x+y=4 のとき xy+1/(xy) >= 2',
    roots: ['FiniteFamily', 'PolynomialSystem'],
    goals: ['Proposition', 'Real'],
  },
  {
    id: '例:根の凸包面積',
    text: '単位円板に根をもつ n 次多項式について、根の凸包の面積の最大値',
    roots: ['Polynomial', 'SemialgebraicSet'],
    goals: ['Scalar', 'Real'],
  },
]

// ---------------------------------------------------------------------------
// 追加する射。すべて「代数・不等式の複数問題に効く」水準で定義する。
// ---------------------------------------------------------------------------
const ADDED: HyperMorphismSchema[] = [
  // 対称式の共通座標。変数族も多項式も同じ場所に落ちる（ここが一般化の要）
  { name: 'ElementarySymmetricChart', sources: ['FiniteFamily'], target: 'SymmetricCoordinates', preserves: ['symmetric-action', 'multiplicity'], backend: ['sympy.symmetrize'] },
  { name: 'VietaChart', sources: ['Polynomial'], target: 'SymmetricCoordinates', preserves: ['symmetric-action', 'root-coefficient-duality'], backend: ['vieta'] },

  // 対称座標から実代数的な領域へ
  { name: 'SymmetricConstraintSlice', sources: ['SymmetricCoordinates', 'PolynomialSystem'], target: 'SemialgebraicSet', preserves: ['both-parent-provenance', 'symmetric-action', 'feasible-set'], backend: ['groebner-basis', 'quantifier-elimination'] },
  { name: 'RealRootRealizabilityCone', sources: ['SymmetricCoordinates'], target: 'SemialgebraicSet', preserves: ['symmetric-action', 'realizability'], backend: ['newton-maclaurin', 'discriminant'] },

  // 平均の階層（相加相乗・冪平均・Cauchy を1本で覆う）
  { name: 'PowerMeanFiltration', sources: ['FiniteFamily'], target: 'MeanTower', preserves: ['symmetric-action', 'order'], backend: ['power-mean'] },
  { name: 'MeanTowerOrdering', sources: ['MeanTower'], target: 'Proposition', preserves: ['order'], backend: ['power-mean-inequality'] },

  // 数値層の分断の是正（Scalar と Real は同じ対象）
  { name: 'ScalarAsReal', sources: ['Scalar'], target: 'Real', preserves: ['value'], backend: ['identity'] },

  // 不等式そのものを作る射。これが無いと「>=」が書けない
  { name: 'OrderAssertion', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['both-parent-provenance', 'order'], backend: ['cvc5'] },

  // 証明の出口
  { name: 'PositivstellensatzCertificate', sources: ['SemialgebraicSet'], target: 'Proof', preserves: ['truth', 'feasible-set'], backend: ['sos', 'cvc5'] },
  { name: 'PropositionDischarge', sources: ['Proposition'], target: 'Proof', preserves: ['truth'], backend: ['lean', 'smt'] },

  // 三角形の辺 → 制約なしの正数族（Ravi 置換）
  { name: 'RaviSubstitution', sources: ['TriangleMetricData'], target: 'FiniteFamily', preserves: ['triangle-inequality', 'positivity'], backend: ['linear-substitution'] },

  // 根を平面配置として見る（根の幾何すべて）
  { name: 'RootPlaneRealization', sources: ['FiniteAlgebraicOrbit'], target: 'GeometricConfiguration', preserves: ['multiplicity', 'incidence'], backend: ['complex-plane-embedding'] },
]

function run(rules: readonly HyperMorphismSchema[]) {
  return CASES.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 8, maxStates: 60_000, goalSorts: c.goals, rules,
    })
    return { id: c.id, goals: r.goals.length, terms: r.terms.length, best: r.goals[0], frontier: r.frontier }
  })
}

const base = executableMorphismAtlas()
console.log(`素のアトラス: 射 ${base.length}本 / 追加 ${ADDED.length}本\n`)

const before = run(base)
const after = run([...base, ...ADDED])

console.log('=== 到達数 ===')
console.log('問題                 素: 到達/探索      追加後: 到達/探索')
for (let i = 0; i < CASES.length; i++) {
  const b = before[i], a = after[i]
  const mark = a.goals > b.goals ? '  ← 増' : (b.goals === 0 && a.goals === 0 ? '  ← 依然0' : '')
  console.log(
    `${b.id.padEnd(18)} ${String(b.goals).padStart(4)} / ${String(b.terms).padStart(5)}   `
    + `${String(a.goals).padStart(6)} / ${String(a.terms).padStart(5)}${mark}`,
  )
}

console.log('\n=== 素の状態の frontier 不足ソート（頻度） ===')
const tally = new Map<string, number>()
const perCase = new Map<string, Set<string>>()
for (const b of before) {
  const s = new Set<string>()
  for (const f of b.frontier) for (const m of f.missing) s.add(m)
  perCase.set(b.id, s)
  for (const m of s) tally.set(m, (tally.get(m) ?? 0) + 1)
}
for (const [sort, n] of [...tally.entries()].sort((x, y) => y[1] - x[1])) {
  console.log(`  ${String(n).padStart(2)}問  ${sort}`)
}
if (!tally.size) console.log('  （なし）')

// frontier は「そのソートの項が1つも無い」時しか出ないので診断が弱い。
// 本当の不足は「到達できなかったゴールソート」と「素のアトラスで生成源が無いソート」。
console.log('\n=== 到達できなかったゴールソート（素の状態・頻度） ===')
const goalMiss = new Map<string, number>()
for (const b of before) {
  const c = CASES.find(x => x.id === b.id)!
  const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
    maxDepth: 8, maxStates: 60_000, goalSorts: c.goals, rules: base,
  })
  const have = new Set(r.terms.map(t => t.sort))
  for (const g of c.goals) if (!have.has(g)) goalMiss.set(g, (goalMiss.get(g) ?? 0) + 1)
}
for (const [sort, n] of [...goalMiss.entries()].sort((x, y) => y[1] - x[1])) {
  console.log(`  ${String(n).padStart(2)}問  ${sort}`)
}

console.log('\n=== 素のアトラスで生成源(入次数)0 のソート ===')
const produced = new Set(base.map(r => r.target))
const consumed = new Set(base.flatMap(r => r.sources))
const orphan = [...consumed].filter(s => !produced.has(s)).sort()
console.log(`  ${orphan.join(', ')}`)

console.log('\n=== 素の状態で到達0だった問題 ===')
for (const b of before) {
  if (b.goals > 0) continue
  console.log(`${b.id}: 到達0  項数${b.terms}  frontier不足: ${[...(perCase.get(b.id) ?? [])].join(', ') || '(なし)'}`)
}

console.log('\n=== 追加後に到達した経路 ===')
for (const a of after) {
  if (a.best) {
    console.log(`${a.id}: ${a.best.sort} 深さ${a.best.depth}  到達${a.goals}件`)
    console.log(`  ${a.best.steps.map((s: { morphism: string }) => s.morphism).join(' → ')}`)
  } else {
    console.log(`${a.id}: 到達せず`)
  }
}

// 暗記か語彙かの判定: leave-one-out。1本抜いて到達が落ちる問題数を数える。
// 1問しか落ちない射は暗記の疑い。複数問で落ちる射は語彙。
console.log('\n=== leave-one-out（射を1本抜いたときに到達が減る問題） ===')
const full = [...base, ...ADDED]
const afterCounts = new Map(after.map(a => [a.id, a.goals]))
for (const m of ADDED) {
  const rules = full.filter(r => r.name !== m.name)
  const res = run(rules)
  const drops = res
    .filter(r => r.goals < (afterCounts.get(r.id) ?? 0))
    .map(r => `${r.id}(${afterCounts.get(r.id)}→${r.goals})`)
  const verdict = drops.length >= 3 ? '語彙' : drops.length >= 1 ? '限定的' : '寄与なし'
  console.log(`  ${m.name.padEnd(30)} ${String(drops.length).padStart(2)}問 [${verdict}] ${drops.join(' ')}`)
}

// 全到達項のうち、各追加射を使うものの割合（最短経路だけでなく全体を見る）
console.log('\n=== 追加射が現れた到達項の分布（全ゴール項ベース） ===')
for (const m of ADDED) {
  const cases: string[] = []
  for (const c of CASES) {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 8, maxStates: 60_000, goalSorts: c.goals, rules: full,
    })
    const n = r.goals.filter(g => g.steps.some((s: { morphism: string }) => s.morphism === m.name)).length
    if (n > 0) cases.push(`${c.id}:${n}`)
  }
  console.log(`  ${m.name.padEnd(30)} ${String(cases.length).padStart(2)}問  ${cases.join(' ') || '(未出現)'}`)
}
