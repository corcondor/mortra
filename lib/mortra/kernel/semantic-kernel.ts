/**
 * Semantic Kernel — 全機能が参照する唯一の意味核。
 *
 * 監査で分かった分断：
 *
 *   'proved' の定義が 7 箇所にあった
 *     lib/mortra/world/world-types.ts
 *     worker/src/alphageometry2-executor.ts   （proved | unproved | unformalized | unavailable | error）
 *     worker/src/exact-linear-invariant.ts    （proved | underdetermined | inconsistent | blocked）
 *     worker/src/generalization-kernel.ts     （proved | open）
 *     worker/backend/cas_solver.py            （proved | verified_instance | ... ）
 *     worker/src/benchmark-bridge.ts
 *     lib/proof-scene.ts                      （数値検証のみ）
 *
 *   射の型が 2 つ
 *     worker/src/generalization-kernel.ts  MorphismSchema
 *     worker/src/verified-domain-extensions.ts  VerifiedDomainMorphism
 *
 * 同じ言葉が別の意味を持っていたので、「証明済み」を横断して数えられなかった。
 * ここを唯一の定義にし、既存はアダプタで写す。大きな書き換えはしない。
 *
 * 規約（convention）と記号の役割（symbol role）を第一級にする。
 * 今回の scale error（テータの指数の取り違え）と `I` の衝突は、
 * どちらも規約と役割が暗黙だったことが原因だった。
 */

// ---------------------------------------------------------------------------
// 同一性
// ---------------------------------------------------------------------------

export type SemanticId = string & { readonly __brand: 'SemanticId' }
export const sid = (value: string) => value as SemanticId

/** 数学的な種別。分野をまたいで同じ語を使う */
export type MathSort =
  | 'Real' | 'Integer' | 'Rational' | 'Complex'
  | 'Point' | 'Line' | 'Circle' | 'Conic' | 'Triangle' | 'Polygon'
  | 'Vector' | 'Matrix' | 'Lattice' | 'Basis' | 'QuadraticForm'
  | 'Group' | 'GroupElement' | 'Orbit' | 'Stabilizer' | 'Quotient'
  | 'RootSystem' | 'CartanMatrix' | 'ThetaSeries'
  | 'Expression' | 'Equation' | 'Inequality' | 'Function' | 'Sequence'
  | 'Proposition' | 'Proof' | 'Certificate'
  | 'VisualElement' | 'DesignArtifact'
  | 'Opaque'

// ---------------------------------------------------------------------------
// 知識の状態。ここが唯一の定義
// ---------------------------------------------------------------------------

/**
 * 主張の強さ。「具体例で合った」と「一般に証明した」を同じ語で呼ばない。
 *
 * これまで各所で別々の列挙になっていたので、横断して数えられなかった。
 */
export type KnowledgeStatus =
  | 'proved'                 // 記号的に導出し、恒等式として確かめた
  | 'verified_instance'      // 具体値では一致した。一般には未証明
  | 'numerically_supported'  // 数値では合うが記号的な確認が無い
  | 'stable_under_perturbation' // 摂動しても保たれた。まだ予想
  | 'conjectured'            // 観測しただけ
  | 'unverified'             // 出したが確認が取れていない
  | 'disproved'              // 反例が出た
  | 'rejected'               // 確認して成り立たないと分かった
  | 'unformalized'           // 形式化できていない
  | 'unsupported'            // 扱える範囲の外

/** 検証に使った独立な手段。LLM の自己申告は列挙に入れない */
export type VerificationMethod =
  | 'symbolic_identity' | 'exact_substitution' | 'groebner_reduction'
  | 'interval_arithmetic' | 'smt' | 'ddar' | 'forward_chaining'
  | 'numeric_sampling' | 'property_test' | 'group_closure'
  | 'orbit_membership' | 'symmetry_verification'

export type Certificate = {
  id: SemanticId
  method: VerificationMethod
  /** 検証が消費した前提。書かれていない前提を使っていないかを見る */
  consumedPremises: SemanticId[]
  detail?: string
  /** どのコミット・成果物で得たか */
  artifact?: string
}

// ---------------------------------------------------------------------------
// 規約。暗黙にしない
// ---------------------------------------------------------------------------

export type ConventionKind =
  | 'reciprocal_lattice'   // 2π を付けるか（数学 / 結晶学）
  | 'root_normalization'   // 最小ノルム² を 2 にするか
  | 'theta_exponent'       // |x|² か |x|²/2 か
  | 'coordinate_frame'
  | 'unit'
  | 'orientation'
  | 'branch_selection'     // √ や arg の枝
  | 'symbol_role'          // I が虚数単位か関数か

export type Convention = {
  kind: ConventionKind
  value: string
  /** なぜその規約を選んだか。移すときに突き合わせる */
  rationale?: string
}

/** 規約が食い違ったまま値を渡すと、静かに間違う。移す前に必ず突き合わせる */
export function conventionsAgree(a: Convention[], b: Convention[]): {
  agree: boolean
  conflicts: { kind: ConventionKind; from: string; to: string }[]
} {
  const conflicts: { kind: ConventionKind; from: string; to: string }[] = []
  for (const x of a) {
    const y = b.find(c => c.kind === x.kind)
    if (y && y.value !== x.value) conflicts.push({ kind: x.kind, from: x.value, to: y.value })
  }
  return { agree: conflicts.length === 0, conflicts }
}

// ---------------------------------------------------------------------------
// 記号の役割。MathML の I 衝突はここが暗黙だったせい
// ---------------------------------------------------------------------------

export type SymbolRole = 'variable' | 'function' | 'constant' | 'operator' | 'set' | 'index'

export type SymbolBinding = {
  name: string
  role: SymbolRole
  sort?: MathSort
  /** どこから決まったか。優先順位はこの順 */
  source:
    | 'explicit_declaration'    // 1
    | 'content_mathml'          // 2
    | 'presentation_structure'  // 3  &af; / &it; / 括弧の隣接
    | 'text_context'            // 4
    | 'standard_dictionary'     // 5
    | 'inferred'                // 6
  confidence: number
}

const SOURCE_RANK: Record<SymbolBinding['source'], number> = {
  explicit_declaration: 1,
  content_mathml: 2,
  presentation_structure: 3,
  text_context: 4,
  standard_dictionary: 5,
  inferred: 6,
}

/** 同じ名前に複数の役割が来たら、出所の強い方を採る。同順位で食い違えば棄権 */
export function resolveBinding(candidates: SymbolBinding[]): SymbolBinding | null {
  if (!candidates.length) return null
  const sorted = [...candidates].sort((a, b) => SOURCE_RANK[a.source] - SOURCE_RANK[b.source])
  const best = sorted[0]
  const rivals = sorted.filter(
    c => SOURCE_RANK[c.source] === SOURCE_RANK[best.source] && c.role !== best.role)
  return rivals.length ? null : best
}

// ---------------------------------------------------------------------------
// 対象・関係・射
// ---------------------------------------------------------------------------

export type Provenance = {
  /** 何から来たか */
  source: string
  /** どの射を通ってきたか */
  path: SemanticId[]
  /** 消費した前提 */
  consumed: SemanticId[]
  method?: VerificationMethod
  artifact?: string
}

export type SemanticObject = {
  id: SemanticId
  sort: MathSort
  /** 人が読む名前。A, BC, Λ, Θ */
  label?: string
  definition?: string
  assumptions: SemanticId[]
  conventions: Convention[]
  provenance: Provenance
  /** 分野核が持つ実体。lattice の Basis、group の生成元など */
  payload?: unknown
}

export type TypedRelation = {
  id: SemanticId
  predicate: string
  arguments: SemanticId[]
  status: KnowledgeStatus
  certificate?: SemanticId
  provenance: Provenance
}

/**
 * 射。裸の値を渡すだけの橋は射と呼ばない。
 *
 * 何を保つのかを宣言しない移動は、意味を運んでいない。
 */
export type Morphism = {
  id: SemanticId
  name: string
  source: SemanticId[]
  target: SemanticId[]
  sourceSorts: MathSort[]
  targetSorts: MathSort[]
  preconditions: string[]
  /** 運ばれる意味 */
  transported: SemanticId[]
  /** 保たれる不変量。空なら射ではない */
  preserved: string[]
  proofObligations: SemanticId[]
  certificate?: SemanticId
  /** 規約が変わる射なら、その対応を書く */
  conventionMap?: { from: Convention; to: Convention }[]
  failureState?: string
}

// ---------------------------------------------------------------------------
// 登録簿
// ---------------------------------------------------------------------------

export type SemanticKernel = {
  objects: Map<SemanticId, SemanticObject>
  relations: Map<SemanticId, TypedRelation>
  morphisms: Map<SemanticId, Morphism>
  certificates: Map<SemanticId, Certificate>
  symbols: Map<string, SymbolBinding>
}

export function createKernel(): SemanticKernel {
  return {
    objects: new Map(), relations: new Map(),
    morphisms: new Map(), certificates: new Map(), symbols: new Map(),
  }
}

export function addObject(k: SemanticKernel, o: SemanticObject): SemanticObject {
  k.objects.set(o.id, o)
  return o
}

export function addRelation(k: SemanticKernel, r: TypedRelation): TypedRelation {
  k.relations.set(r.id, r)
  return r
}

export function addMorphism(k: SemanticKernel, m: Morphism): Morphism {
  k.morphisms.set(m.id, m)
  return m
}

export function addCertificate(k: SemanticKernel, c: Certificate): Certificate {
  k.certificates.set(c.id, c)
  return c
}

// ---------------------------------------------------------------------------
// 監査。核が矛盾していたら成果物を出さない
// ---------------------------------------------------------------------------

export type KernelViolation = { kind: string; id: SemanticId; detail: string }

export function auditKernel(k: SemanticKernel): KernelViolation[] {
  const out: KernelViolation[] = []

  for (const r of k.relations.values()) {
    if (r.status === 'proved' && !r.certificate) {
      out.push({ kind: 'proved_without_certificate', id: r.id,
        detail: 'proved と名乗るなら独立な検証の証明書が要る' })
    }
    if (r.certificate && !k.certificates.has(r.certificate)) {
      out.push({ kind: 'dangling_certificate', id: r.id, detail: String(r.certificate) })
    }
    for (const a of r.arguments) {
      if (!k.objects.has(a)) {
        out.push({ kind: 'dangling_argument', id: r.id, detail: `未知の対象 ${a}` })
      }
    }
  }

  for (const m of k.morphisms.values()) {
    if (!m.preserved.length) {
      out.push({ kind: 'morphism_without_invariant', id: m.id,
        detail: '保つ不変量を宣言しない移動は射ではない' })
    }
    if (m.sourceSorts.length !== m.source.length || m.targetSorts.length !== m.target.length) {
      out.push({ kind: 'sort_arity_mismatch', id: m.id, detail: '型の個数が対象の個数と合わない' })
    }
    // 規約が変わるのに対応を書いていない射
    const srcConv = m.source.flatMap(s => k.objects.get(s)?.conventions ?? [])
    const tgtConv = m.target.flatMap(t => k.objects.get(t)?.conventions ?? [])
    const { agree, conflicts } = conventionsAgree(srcConv, tgtConv)
    if (!agree && !m.conventionMap?.length) {
      out.push({ kind: 'silent_convention_change', id: m.id,
        detail: `規約が変わる: ${conflicts.map(c => `${c.kind} ${c.from}→${c.to}`).join(', ')}` })
    }
  }

  for (const o of k.objects.values()) {
    if (!o.provenance || !o.provenance.source) {
      out.push({ kind: 'object_without_provenance', id: o.id, detail: '出所が無い' })
    }
  }
  return out
}

/** 対象がどの射を通ってきたか。provenance を辿る */
export function transportPath(k: SemanticKernel, id: SemanticId): Morphism[] {
  const o = k.objects.get(id)
  if (!o) return []
  return o.provenance.path
    .map(p => k.morphisms.get(p))
    .filter((m): m is Morphism => m !== undefined)
}

/** 状態の集計。分野をまたいで同じ語で数えられる */
export function statusCounts(k: SemanticKernel): Record<string, number> {
  const out: Record<string, number> = {}
  for (const r of k.relations.values()) out[r.status] = (out[r.status] ?? 0) + 1
  return out
}
