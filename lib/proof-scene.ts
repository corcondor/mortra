/**
 * Proof Scene — 証明・図・文章を一つの対象から出す。
 *
 * これまで図と文章は別々に作っていた。だから図が説明から切り離されて見え、
 * 「あとから貼った挿絵」になっていた。ここでは逆にする。
 *
 *   証明の 1 ステップ = 図の 1 ステップ = 文の 1 ステップ
 *
 * 一つの Beat が、主張・根拠・図の操作・書く式を同時に持つ。
 * 描画側は Beat を順に再生するだけで、図と字が同期する。配置を人が決める余地はない。
 *
 * 推論は前向き（forward chaining）。worker/src/typed-fact-closure.ts と同じ骨格だが、
 * 幾何に必要な二つを足している:
 *   - 相異条件（A≠B）。これが無いと perp(a,a,b,c) のような退化事実が量産される。
 *   - 数値検証。形式化が作った座標に対して、導けた事実が実際に成り立つか毎回確かめる。
 *     規則が健全でも、退化した当てはめは独立な座標検査が弾く。
 *
 * LLM も外部 API も使わない。
 */

import {
  inspectSemanticGeometry,
  type CoordinateProvenance,
  type GeometryCandidate,
  type GeometryCandidateCertificate,
} from './mortra/vision/geometry-candidate-loop'

export type Pt = { x: number; y: number }

/** MORTRAの有限幾何述語。証明状態と図の同期に共用する。 */
export type Fact = {
  pred: 'perp' | 'para' | 'coll' | 'cong' | 'midp' | 'eqangle'
  args: string[]
}

export type Derivation = {
  fact: Fact
  /** null なら前提（問題文に書いてあったもの） */
  rule: string | null
  premises: Fact[]
  origin: 'given' | 'deduced' | 'visual-certified'
  certificate?: GeometryCandidateCertificate
}

// ---------------------------------------------------------------------------
// 規則
// ---------------------------------------------------------------------------

export type Rule = {
  id: string
  /** 日本語の言い回し。証明文はここから作る。$1 は束縛された点名に置換 */
  says: (b: Record<string, string>) => string
  premises: { pred: Fact['pred']; args: string[] }[]
  conclusion: { pred: Fact['pred']; args: string[] }
  /** 相異でなければならない変数の組 */
  distinct?: [string, string][]
}

/**
 * 規則は「定理を一本ずつ足す」のではなく、
 * 少数の規則が複数の問題に同時に効くように選ぶ。
 * どの規則がどれだけの問題を開けたかは compileScene の結果から数えられる。
 */
export const RULES: Rule[] = [
  {
    id: 'perp-along-line',
    says: b => `${b.E} は直線 ${b.A}${b.B} 上にあるので、${b.A}${b.E} は ${b.A}${b.B} と同じ直線。よって ${b.A}${b.E} ⊥ ${b.C}${b.D}`,
    premises: [
      { pred: 'perp', args: ['A', 'B', 'C', 'D'] },
      { pred: 'coll', args: ['A', 'B', 'E'] },
    ],
    conclusion: { pred: 'perp', args: ['A', 'E', 'C', 'D'] },
    distinct: [['A', 'E'], ['A', 'B']],
  },
  {
    id: 'perp-bisector',
    says: b => `${b.O}${b.B} = ${b.O}${b.C} で、${b.M} は ${b.B}${b.C} の中点。${b.O} は ${b.B}${b.C} の垂直二等分線上にあるから ${b.O}${b.M} ⊥ ${b.B}${b.C}`,
    premises: [
      { pred: 'cong', args: ['O', 'B', 'O', 'C'] },
      { pred: 'midp', args: ['M', 'B', 'C'] },
    ],
    conclusion: { pred: 'perp', args: ['O', 'M', 'B', 'C'] },
    distinct: [['O', 'M']],
  },
  {
    id: 'midline',
    says: b => `${b.M} は ${b.A}${b.B} の中点、${b.N} は ${b.A}${b.C} の中点。中点連結より ${b.M}${b.N} ∥ ${b.B}${b.C}`,
    premises: [
      { pred: 'midp', args: ['M', 'A', 'B'] },
      { pred: 'midp', args: ['N', 'A', 'C'] },
    ],
    conclusion: { pred: 'para', args: ['M', 'N', 'B', 'C'] },
    distinct: [['B', 'C'], ['M', 'N']],
  },
  {
    id: 'midline-half',
    says: b => `中点連結より ${b.M}${b.N} は ${b.B}${b.C} の半分の長さ。${b.M}${b.N} = ${b.M}${b.N}`,
    premises: [
      { pred: 'midp', args: ['M', 'A', 'B'] },
      { pred: 'midp', args: ['N', 'A', 'C'] },
    ],
    conclusion: { pred: 'cong', args: ['M', 'N', 'M', 'N'] },
    distinct: [['M', 'N']],
  },
  {
    id: 'perp-perp-para',
    says: b => `${b.A}${b.B} と ${b.C}${b.D} はどちらも ${b.E}${b.F} に垂直。よって ${b.A}${b.B} ∥ ${b.C}${b.D}`,
    premises: [
      { pred: 'perp', args: ['A', 'B', 'E', 'F'] },
      { pred: 'perp', args: ['C', 'D', 'E', 'F'] },
    ],
    conclusion: { pred: 'para', args: ['A', 'B', 'C', 'D'] },
    distinct: [['A', 'C'], ['A', 'B'], ['C', 'D']],
  },
  {
    id: 'para-perp',
    says: b => `${b.A}${b.B} ∥ ${b.C}${b.D} で ${b.C}${b.D} ⊥ ${b.E}${b.F}。よって ${b.A}${b.B} ⊥ ${b.E}${b.F}`,
    premises: [
      { pred: 'para', args: ['A', 'B', 'C', 'D'] },
      { pred: 'perp', args: ['C', 'D', 'E', 'F'] },
    ],
    conclusion: { pred: 'perp', args: ['A', 'B', 'E', 'F'] },
    distinct: [['A', 'B']],
  },
  {
    id: 'para-transitive',
    says: b => `${b.A}${b.B} ∥ ${b.C}${b.D}、${b.C}${b.D} ∥ ${b.E}${b.F}。よって ${b.A}${b.B} ∥ ${b.E}${b.F}`,
    premises: [
      { pred: 'para', args: ['A', 'B', 'C', 'D'] },
      { pred: 'para', args: ['C', 'D', 'E', 'F'] },
    ],
    conclusion: { pred: 'para', args: ['A', 'B', 'E', 'F'] },
    distinct: [['A', 'E'], ['A', 'B'], ['E', 'F']],
  },
  {
    id: 'midp-to-coll',
    says: b => `${b.M} は ${b.A}${b.B} の中点なので、${b.A}, ${b.M}, ${b.B} は同一直線上`,
    premises: [{ pred: 'midp', args: ['M', 'A', 'B'] }],
    conclusion: { pred: 'coll', args: ['A', 'M', 'B'] },
  },
  {
    // 正三角形は AB=BC と BC=CA として入る。AB=CA は書かれていない。
    // 推移律が無いと、そこで止まる。
    id: 'cong-transitive',
    says: b => `${b.A}${b.B} = ${b.C}${b.D}、${b.C}${b.D} = ${b.E}${b.F}。よって ${b.A}${b.B} = ${b.E}${b.F}`,
    premises: [
      { pred: 'cong', args: ['A', 'B', 'C', 'D'] },
      { pred: 'cong', args: ['C', 'D', 'E', 'F'] },
    ],
    conclusion: { pred: 'cong', args: ['A', 'B', 'E', 'F'] },
    distinct: [['A', 'E'], ['A', 'B'], ['E', 'F']],
  },
  {
    id: 'isosceles-base-angles',
    says: b => `${b.A}${b.B} = ${b.A}${b.C} なので、△${b.A}${b.B}${b.C} は二等辺三角形。底角は等しい`,
    premises: [{ pred: 'cong', args: ['A', 'B', 'A', 'C'] }],
    conclusion: { pred: 'eqangle', args: ['B', 'A', 'B', 'C', 'C', 'B', 'C', 'A'] },
    distinct: [['B', 'C'], ['A', 'B'], ['A', 'C']],
  },
  {
    id: 'perp-both-to-eq',
    says: b => `${b.A}${b.B} ⊥ ${b.E}${b.F} と ${b.C}${b.D} ⊥ ${b.E}${b.F} から、${b.A}${b.B} と ${b.C}${b.D} は同じ向き`,
    premises: [
      { pred: 'perp', args: ['A', 'B', 'E', 'F'] },
      { pred: 'para', args: ['C', 'D', 'A', 'B'] },
    ],
    conclusion: { pred: 'perp', args: ['C', 'D', 'E', 'F'] },
    distinct: [['C', 'D']],
  },
]

// ---------------------------------------------------------------------------
// 正規化。perp(a,b,c,d) は端点の入れ替えと二直線の入れ替えで不変
// ---------------------------------------------------------------------------

function seg(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

export function factKey(f: Fact): string {
  const a = f.args
  switch (f.pred) {
    case 'perp':
    case 'para': {
      const s = [seg(a[0], a[1]), seg(a[2], a[3])].sort()
      return `${f.pred}(${s.join(',')})`
    }
    case 'cong': {
      const s = [seg(a[0], a[1]), seg(a[2], a[3])].sort()
      return `cong(${s.join(',')})`
    }
    case 'coll':
      return `coll(${[...a].sort().join(',')})`
    case 'midp':
      return `midp(${a[0]};${seg(a[1], a[2])})`
    default:
      return `${f.pred}(${a.join(',')})`
  }
}

// ---------------------------------------------------------------------------
// 数値検証。座標があるので、導けた事実が図の上で本当に成り立つか毎回確かめる
// ---------------------------------------------------------------------------

const EPS = 1e-6

function vec(p: Pt, q: Pt) {
  return { x: q.x - p.x, y: q.y - p.y }
}
function norm(v: { x: number; y: number }) {
  return Math.hypot(v.x, v.y)
}

/** 図の上で成り立つか。成り立たなければ、その当てはめは退化している */
export function holdsNumerically(f: Fact, xy: Record<string, Pt>): boolean {
  const P = (n: string) => xy[n]
  if (f.args.some(n => !P(n))) return false
  const a = f.args
  switch (f.pred) {
    case 'perp': {
      const u = vec(P(a[0]), P(a[1])), v = vec(P(a[2]), P(a[3]))
      const lu = norm(u), lv = norm(v)
      if (lu < EPS || lv < EPS) return false
      return Math.abs((u.x * v.x + u.y * v.y) / (lu * lv)) < 1e-6
    }
    case 'para': {
      const u = vec(P(a[0]), P(a[1])), v = vec(P(a[2]), P(a[3]))
      const lu = norm(u), lv = norm(v)
      if (lu < EPS || lv < EPS) return false
      return Math.abs((u.x * v.y - u.y * v.x) / (lu * lv)) < 1e-6
    }
    case 'coll': {
      const u = vec(P(a[0]), P(a[1])), v = vec(P(a[0]), P(a[2]))
      const lu = norm(u), lv = norm(v)
      if (lu < EPS || lv < EPS) return false
      return Math.abs((u.x * v.y - u.y * v.x) / (lu * lv)) < 1e-6
    }
    case 'cong': {
      const d1 = norm(vec(P(a[0]), P(a[1]))), d2 = norm(vec(P(a[2]), P(a[3])))
      return Math.abs(d1 - d2) < 1e-6 * Math.max(1, d1, d2)
    }
    case 'midp': {
      const m = P(a[0]), p = P(a[1]), q = P(a[2])
      return Math.abs(m.x - (p.x + q.x) / 2) < 1e-6 && Math.abs(m.y - (p.y + q.y) / 2) < 1e-6
    }
    case 'eqangle': {
      // eqangle(a,b,c,d,e,f,g,h) は「直線 ab から cd への角」と
      // 「ef から gh への角」が等しいということ。向きつき角なので π を法にする。
      // 絶対値で測ると、鏡像の当てはめまで通ってしまう。
      const dir = (p: string, q: string) => Math.atan2(P(q).y - P(p).y, P(q).x - P(p).x)
      const len = (p: string, q: string) => Math.hypot(P(q).x - P(p).x, P(q).y - P(p).y)
      for (let i = 0; i < 8; i += 2) if (len(a[i], a[i + 1]) < EPS) return false
      const t1 = dir(a[2], a[3]) - dir(a[0], a[1])
      const t2 = dir(a[6], a[7]) - dir(a[4], a[5])
      return Math.abs(Math.sin(t1 - t2)) < 1e-6
    }
    default:
      return true
  }
}

// ---------------------------------------------------------------------------
// 前向き推論。導出の親を保持するので、証明は DAG として取り出せる
// ---------------------------------------------------------------------------

function matchPattern(
  pat: { pred: Fact['pred']; args: string[] },
  fact: Fact,
  binding: Record<string, string>,
): Record<string, string> | null {
  if (pat.pred !== fact.pred) return null
  // 対称性のある述語は、引数の並べ替えも試す
  const orders: number[][] =
    pat.pred === 'perp' || pat.pred === 'para' || pat.pred === 'cong'
      ? [[0, 1, 2, 3], [1, 0, 2, 3], [0, 1, 3, 2], [1, 0, 3, 2],
         [2, 3, 0, 1], [3, 2, 0, 1], [2, 3, 1, 0], [3, 2, 1, 0]]
      : pat.pred === 'coll'
        ? [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]]
        : pat.pred === 'midp'
          ? [[0, 1, 2], [0, 2, 1]]
          : [fact.args.map((_, i) => i)]

  for (const order of orders) {
    const next = { ...binding }
    let ok = true
    for (let i = 0; i < pat.args.length; i++) {
      const v = pat.args[i]
      const value = fact.args[order[i]]
      if (next[v] === undefined) next[v] = value
      else if (next[v] !== value) { ok = false; break }
    }
    if (ok) return next
  }
  return null
}

export type ClosureResult = {
  derivations: Map<string, Derivation>
  proved: boolean
  goalKey: string
}

export function forwardChain(
  premises: Fact[],
  goal: Fact,
  xy: Record<string, Pt>,
  opts: {
    maxRounds?: number
    certifiedSeeds?: { fact: Fact; certificate: GeometryCandidateCertificate }[]
  } = {},
): ClosureResult {
  const derivations = new Map<string, Derivation>()
  for (const f of premises) {
    derivations.set(factKey(f), { fact: f, rule: null, premises: [], origin: 'given' })
  }
  for (const seed of opts.certifiedSeeds ?? []) {
    if (seed.certificate.status !== 'certified') continue
    const key = factKey(seed.fact)
    if (!derivations.has(key)) {
      derivations.set(key, {
        fact: seed.fact,
        rule: 'visual-exact-coordinate',
        premises: [],
        origin: 'visual-certified',
        certificate: seed.certificate,
      })
    }
  }
  const goalKey = factKey(goal)
  const maxRounds = opts.maxRounds ?? 12

  for (let round = 0; round < maxRounds; round++) {
    if (derivations.has(goalKey)) break
    const snapshot = [...derivations.values()].map(d => d.fact)
    let added = false

    for (const rule of RULES) {
      const search = (i: number, binding: Record<string, string>, used: Fact[]) => {
        if (i === rule.premises.length) {
          for (const [u, v] of rule.distinct ?? []) {
            if (binding[u] !== undefined && binding[u] === binding[v]) return
          }
          const concl: Fact = {
            pred: rule.conclusion.pred,
            args: rule.conclusion.args.map(v => binding[v]),
          }
          if (concl.args.some(a => a === undefined)) return
          // 結論自身が退化していないか
          if (new Set(concl.args).size < (concl.pred === 'cong' ? 2 : concl.args.length === 4 ? 3 : 2)) return
          const key = factKey(concl)
          if (derivations.has(key)) return
          // 図の上で成り立たないなら、当てはめが退化している。捨てる
          if (!holdsNumerically(concl, xy)) return
          derivations.set(key, {
            fact: concl,
            rule: rule.id,
            premises: used.slice(),
            origin: 'deduced',
          })
          added = true
          return
        }
        for (const fact of snapshot) {
          const next = matchPattern(rule.premises[i], fact, binding)
          if (next) search(i + 1, next, [...used, fact])
        }
      }
      search(0, {}, [])
    }
    if (!added) break
  }

  return { derivations, proved: derivations.has(goalKey), goalKey }
}

// ---------------------------------------------------------------------------
// Beat — 証明・図・文章が同じ一つの物になる場所
// ---------------------------------------------------------------------------

export type Mark =
  | { kind: 'point'; at: string }
  | { kind: 'segment'; from: string; to: string }
  | { kind: 'line'; from: string; to: string }
  | { kind: 'rightangle'; at: string; from: string; to: string }
  | { kind: 'tick'; from: string; to: string; count: number }
  | { kind: 'parallel'; from: string; to: string; count: number }

export type Beat = {
  /** この段で主張すること */
  claim: Fact
  /** 使った規則。null なら前提 */
  rule: string | null
  /** 人が読む一行 */
  says: string
  /** 数式としての一行 */
  formula: string
  /** この段で図に足すもの */
  draw: Mark[]
  /** この段で光らせるもの（根拠として使った既出の対象） */
  highlight: Mark[]
  /** 前提か、導出か、結論か */
  role: 'given' | 'step' | 'goal'
  origin: Derivation['origin']
  certificate?: GeometryCandidateCertificate
}

export type VisualReasoningAudit = {
  coordinateProvenance: CoordinateProvenance
  baselineProved: boolean
  augmentedProved: boolean
  consideredPoints: number
  consideredSegments: number
  candidates: GeometryCandidate[]
  certified: number
  proofOpening: number
  selectedCandidateIds: string[]
  rejected: number
  conjectureOnly: number
  unverifiable: number
}

export type ProofScene = {
  title: string
  statement: string
  points: Record<string, Pt>
  /** 最初に引いておく骨組み（三角形の三辺など）。証明の段ではない */
  frame: Mark[]
  beats: Beat[]
  proved: boolean
  /** 使った規則の一覧。「定理を暗記していない」ことの根拠になる */
  rulesUsed: string[]
  /** 図からReasonerへ戻した候補と、その独立検証結果。 */
  visualReasoning?: VisualReasoningAudit
}

const SYM: Record<Fact['pred'], (a: string[]) => string> = {
  perp: a => `${a[0]}${a[1]} ⊥ ${a[2]}${a[3]}`,
  para: a => `${a[0]}${a[1]} ∥ ${a[2]}${a[3]}`,
  cong: a => `${a[0]}${a[1]} = ${a[2]}${a[3]}`,
  coll: a => `${a[0]}, ${a[1]}, ${a[2]} は同一直線上`,
  midp: a => `${a[0]} は ${a[1]}${a[2]} の中点`,
  eqangle: a => `∠${a[0]}${a[1]}${a[2]} = ∠${a[3]}${a[4]}${a[5]}`,
}

/**
 * 点名は形式化器から小文字で来るが、図でも式でも大文字が普通。
 * 片方だけ大文字にすると、図の A と式の a が別物に見える。
 */
export function label(name: string): string {
  return name.length === 1 ? name.toUpperCase() : name.toUpperCase().replace(/_/g, '')
}

export function formulaOf(f: Fact): string {
  return SYM[f.pred](f.args.map(label))
}

/** 事実を「図に何を描くか」へ落とす。ここが図と証明を繋いでいる一点 */
function marksFor(f: Fact): Mark[] {
  const a = f.args
  switch (f.pred) {
    case 'perp':
      return [
        { kind: 'segment', from: a[0], to: a[1] },
        { kind: 'segment', from: a[2], to: a[3] },
      ]
    case 'para':
      return [
        { kind: 'parallel', from: a[0], to: a[1], count: 1 },
        { kind: 'parallel', from: a[2], to: a[3], count: 1 },
      ]
    case 'cong':
      return [
        { kind: 'tick', from: a[0], to: a[1], count: 1 },
        { kind: 'tick', from: a[2], to: a[3], count: 1 },
      ]
    case 'coll':
      return [{ kind: 'line', from: a[0], to: a[2] }, { kind: 'point', at: a[1] }]
    case 'midp':
      return [
        { kind: 'point', at: a[0] },
        { kind: 'tick', from: a[1], to: a[0], count: 1 },
        { kind: 'tick', from: a[0], to: a[2], count: 1 },
      ]
    default:
      return []
  }
}

/** 直角の位置を出す。二本の垂直な線分の交点に印を置く */
function rightAngleMark(f: Fact, xy: Record<string, Pt>): Mark | null {
  if (f.pred !== 'perp') return null
  const [p, q, r, s] = f.args
  const shared = [p, q].find(n => n === r || n === s)
  if (!shared) return null
  const other1 = p === shared ? q : p
  const other2 = r === shared ? s : r
  if (!xy[shared] || !xy[other1] || !xy[other2]) return null
  return { kind: 'rightangle', at: shared, from: other1, to: other2 }
}

export type VisualReasoningOptions = {
  coordinateProvenance: CoordinateProvenance
  visualTolerance?: number
  maxCandidates?: number
  maxReasoningSeeds?: number
  /** 実験で「中間命題が証明を開くか」を分離して測るための設定。 */
  allowDirectGoal?: boolean
}

export function closeWithVisualReasoning(input: {
  premises: Fact[]
  goal: Fact
  points: Record<string, Pt>
  options: VisualReasoningOptions
}): { closure: ClosureResult; audit: VisualReasoningAudit } {
  const baseline = forwardChain(input.premises, input.goal, input.points)
  const inspection = inspectSemanticGeometry({
    points: input.points,
    facts: [...input.premises, input.goal],
    coordinateProvenance: input.options.coordinateProvenance,
    visualTolerance: input.options.visualTolerance,
    maxCandidates: input.options.maxCandidates,
  })
  const known = new Set(baseline.derivations.keys())
  const goalKey = factKey(input.goal)
  const candidates = inspection.candidates.filter(candidate =>
    !known.has(factKey(candidate.fact))
    && (input.options.allowDirectGoal !== false || factKey(candidate.fact) !== goalKey),
  )
  const certifiedCandidates = candidates
    .filter(candidate => candidate.certificate.status === 'certified')
  // A visual fact is useful only if it changes the proof state. Test each fact
  // independently, then inject the smallest ranked set instead of flooding the
  // closure with every relation visible in the coordinate model.
  const proofOpening = baseline.proved ? [] : certifiedCandidates.filter(candidate =>
    forwardChain(input.premises, input.goal, input.points, {
      certifiedSeeds: [{ fact: candidate.fact, certificate: candidate.certificate }],
    }).proved,
  )
  const selected = proofOpening
    .sort((a, b) => b.score - a.score || factKey(a.fact).localeCompare(factKey(b.fact)))
    .slice(0, input.options.maxReasoningSeeds ?? 1)
  const certifiedSeeds = selected.map(candidate => ({
    fact: candidate.fact,
    certificate: candidate.certificate,
  }))
  const closure = forwardChain(input.premises, input.goal, input.points, { certifiedSeeds })
  const count = (status: GeometryCandidateCertificate['status']) =>
    candidates.filter(candidate => candidate.certificate.status === status).length

  return {
    closure,
    audit: {
      coordinateProvenance: input.options.coordinateProvenance,
      baselineProved: baseline.proved,
      augmentedProved: closure.proved,
      consideredPoints: inspection.consideredPoints,
      consideredSegments: inspection.consideredSegments,
      candidates,
      certified: count('certified'),
      proofOpening: proofOpening.length,
      selectedCandidateIds: selected.map(candidate => candidate.id),
      rejected: count('rejected'),
      conjectureOnly: count('conjecture_only'),
      unverifiable: count('unverifiable'),
    },
  }
}

/**
 * 証明 DAG を、目標から遡って一本の時間軸へ潰す。
 * 出てくる順が、図に描かれる順であり、文が書かれる順でもある。
 */
export function compileScene(input: {
  title: string
  statement: string
  premises: Fact[]
  goal: Fact
  points: Record<string, Pt>
  /** 骨組みにする三角形（問題文から取れた物）。無ければ図は証明の線だけになる */
  triangles?: [string, string, string][]
  /** 指定時だけ、semantic geometryから検証済み候補をReasonerへ戻す。 */
  visualReasoning?: VisualReasoningOptions
}): ProofScene {
  const visual = input.visualReasoning
    ? closeWithVisualReasoning({
        premises: input.premises,
        goal: input.goal,
        points: input.points,
        options: input.visualReasoning,
      })
    : null
  const { derivations, proved, goalKey } = visual?.closure
    ?? forwardChain(input.premises, input.goal, input.points)

  // 目標に本当に効いた事実だけを残す。使わなかった前提は図に描かない
  const needed: string[] = []
  const seen = new Set<string>()
  const visit = (key: string) => {
    if (seen.has(key)) return
    seen.add(key)
    const d = derivations.get(key)
    if (!d) return
    d.premises.forEach(p => visit(factKey(p)))
    needed.push(key)
  }
  if (proved) visit(goalKey)
  else [...derivations.keys()].forEach(visit)

  // 三角形の三辺は証明の一段ではない。図の骨組みとして先に引いておく。
  // これが無いと「線がぽつぽつ現れる」だけの絵になり、何の図か分からない。
  const frame: Mark[] = (input.triangles ?? []).flatMap(([a, b, c]) =>
    [[a, b], [b, c], [c, a]].map(([p, q]) => ({ kind: 'segment', from: p, to: q } as Mark)),
  )

  const drawn = new Set<string>(frame.map(m => JSON.stringify(m)))
  const beats: Beat[] = []

  for (const key of needed) {
    const d = derivations.get(key)!
    const role: Beat['role'] = key === goalKey ? 'goal' : d.origin === 'given' ? 'given' : 'step'

    const marks = marksFor(d.fact)
    const ra = rightAngleMark(d.fact, input.points)
    if (ra) marks.push(ra)

    // 既に描いた物は描き直さない。図は積み上がる
    const fresh = marks.filter(m => {
      const id = JSON.stringify(m)
      if (drawn.has(id)) return false
      drawn.add(id)
      return true
    })

    const rule = d.rule ? RULES.find(r => r.id === d.rule) : null
    let says: string
    if (d.origin === 'visual-certified' && d.certificate) {
      says = `${formulaOf(d.fact)}（入力された厳密座標から ${d.certificate.identities.join(', ')} を検証）`
    } else if (rule) {
      // 規則の変数を、実際に束縛された点名へ戻す
      const binding: Record<string, string> = {}
      rule.conclusion.args.forEach((v, i) => { binding[v] = label(d.fact.args[i]) })
      rule.premises.forEach((p, pi) => {
        const src = d.premises[pi]
        if (src) p.args.forEach((v, i) => { if (!binding[v]) binding[v] = label(src.args[i]) })
      })
      says = Object.values(binding).every(Boolean)
        ? rule.says(binding)
        : formulaOf(d.fact)
    } else {
      says = `${formulaOf(d.fact)}（問題文より）`
    }

    beats.push({
      claim: d.fact,
      rule: d.rule,
      says,
      formula: formulaOf(d.fact),
      draw: fresh,
      highlight: d.premises.flatMap(marksFor),
      role,
      origin: d.origin,
      certificate: d.certificate,
    })
  }

  return {
    title: input.title,
    statement: input.statement,
    points: input.points,
    frame,
    beats,
    proved,
    rulesUsed: [...new Set(beats.map(b => b.rule).filter((r): r is string => !!r))],
    visualReasoning: visual?.audit,
  }
}
