/**
 * World-scoped identity と ForbiddenIdentification。
 *
 * IUT 研究プロンプト §2 §3 §5 から取った一般概念。IUT 専用にしない。
 *
 * 動機は理論からではなく、実際に踏んだバグから来ている。
 *
 *   a_k   数列の第k項なのに、添字を名前へ畳んだので一個の記号に見えた
 *         sympy は k に依らない定数として和を取り、Σa_k = a_k·n を返した
 *   I     問題側の関数なのに、sympy の虚数単位と同一視された
 *   α     前提 a₁ = α を α について解いて a₁ を返し、答えとして数えた
 *   log r  目標が log r なのに r の解領域を返し、答えとして数えた
 *
 * どれも「記号が同じ」「値が同じ」「見た目が同じ」を理由に、
 * 別の world の対象を同一視した結果。
 *
 * ここで型として禁じる。
 */
import type { SemanticId, MathSort } from './semantic-kernel'

export type WorldId = string & { readonly __brand: 'WorldId' }
export const wid = (s: string) => s as WorldId

/**
 * 意味の世界。理論・利用できる構造・規約・仮定で決まる。
 *
 * X@WorldA と X@WorldB は原則として別対象。同じ記号を持つことは同一性を意味しない。
 */
export type SemanticWorld = {
  id: WorldId
  theory: string
  availableStructures: MathSort[]
  conventions: string[]
  assumptions: string[]
  objectRegistry: SemanticId[]
}

/** world 付きの参照。global name だけで対象を指さない */
export type WorldScopedRef = { world: WorldId; object: SemanticId }

export const scopedKey = (r: WorldScopedRef) => `${r.object}@${r.world}`

// ---------------------------------------------------------------------------
// 同一性の種類を分ける
// ---------------------------------------------------------------------------

/**
 * 「同じ」の強さ。混ぜると偽の証明が出る。
 *
 * 記号が同じ / 値が同じ / 同型 / 同値 / 同一 を一つの語で扱っていたのが、
 * 今回の false positive の共通原因だった。
 */
export type IdentityKind =
  | 'definitional_equality'   // 定義により等しい
  | 'equality'                // 同じ world 内で値が等しい
  | 'canonical_isomorphism'   // 標準的な同型がある
  | 'isomorphism'             // 同型だが標準的とは限らない
  | 'equivalence'             // 同値
  | 'correspondence'          // 対応がある
  | 'representation_of'       // 一方が他方の表現
  | 'reconstruction_of'       // 一方から他方を復元した
  | 'analogy'                 // 類似。証明には使えない

/** 証明に使ってよい同一性。analogy と correspondence は使えない */
const PROVABLE: IdentityKind[] = [
  'definitional_equality', 'equality', 'canonical_isomorphism',
]

export type IdentityClaim = {
  kind: IdentityKind
  left: WorldScopedRef
  right: WorldScopedRef
  justification: string
  certificate?: SemanticId
}

export const usableInProof = (c: IdentityClaim) => PROVABLE.includes(c.kind)

// ---------------------------------------------------------------------------
// 同一視の禁止
// ---------------------------------------------------------------------------

export type ForbiddenReason =
  | 'different_binding_scope'    // 束縛変数と自由変数。a_k の k
  | 'different_symbol_role'      // 関数と定数。I
  | 'different_branch'           // √ や arg の枝
  | 'different_coordinate_chart'
  | 'quotient_vs_representative'
  | 'dual_vs_original'           // Fourier の双対変数
  | 'gauge_choice'
  | 'local_vs_global'
  | 'isomorphic_not_identical'
  | 'premise_vs_conclusion'      // 前提の言い換えを答えと呼ばない
  | 'different_world_convention'

export type ForbiddenIdentification = {
  left: WorldScopedRef
  right: WorldScopedRef
  reason: ForbiddenReason
  detail: string
  scope: [WorldId, WorldId]
}

export type IdentityRegistry = {
  worlds: Map<WorldId, SemanticWorld>
  claims: IdentityClaim[]
  forbidden: ForbiddenIdentification[]
}

export function createRegistry(): IdentityRegistry {
  return { worlds: new Map(), claims: [], forbidden: [] }
}

export function forbid(
  reg: IdentityRegistry, left: WorldScopedRef, right: WorldScopedRef,
  reason: ForbiddenReason, detail: string,
): void {
  reg.forbidden.push({ left, right, reason, detail, scope: [left.world, right.world] })
}

/** その同一視が禁じられているか。向きは問わない */
export function isForbidden(
  reg: IdentityRegistry, left: WorldScopedRef, right: WorldScopedRef,
): ForbiddenIdentification | null {
  const a = scopedKey(left), b = scopedKey(right)
  return reg.forbidden.find(f =>
    (scopedKey(f.left) === a && scopedKey(f.right) === b)
    || (scopedKey(f.left) === b && scopedKey(f.right) === a)) ?? null
}

/**
 * 同一性の主張を登録する。禁じられていれば拒否する。
 *
 * 「記号が同じだから同じ」を型で止める。
 */
export function claimIdentity(
  reg: IdentityRegistry, claim: IdentityClaim,
): { accepted: boolean; blockedBy?: ForbiddenIdentification } {
  const blocked = isForbidden(reg, claim.left, claim.right)
  if (blocked) return { accepted: false, blockedBy: blocked }
  reg.claims.push(claim)
  return { accepted: true }
}

// ---------------------------------------------------------------------------
// 実際に踏んだバグを、禁止として登録する
// ---------------------------------------------------------------------------

export const MATH_WORLD = wid('math:default')
export const PROBLEM_WORLD = wid('problem:statement')
export const SYMPY_WORLD = wid('cas:sympy')

/**
 * 既知の禁止。これまで実際に間違えた組み合わせを型として持つ。
 *
 * 「同じ記号だから同じ対象」を、名前と理由付きで止める。
 */
export function registerKnownForbidden(reg: IdentityRegistry): void {
  const problem = (id: string) => ({ world: PROBLEM_WORLD, object: id as SemanticId })
  const sympy = (id: string) => ({ world: SYMPY_WORLD, object: id as SemanticId })

  forbid(reg, problem('I'), sympy('ImaginaryUnit'), 'different_symbol_role',
    '問題文で I(a,n) と関数として使われている。sympy の虚数単位と同一視しない')
  forbid(reg, problem('e'), sympy('E'), 'different_symbol_role',
    '問題文で e が変数として使われることがある。自然対数の底と同一視しない')
  forbid(reg, problem('C'), sympy('C'), 'different_symbol_role',
    '問題文の C(n,k) は二項係数、曲線 C、定数 C のいずれでもありうる')

  forbid(reg, problem('a_k:bound'), problem('a_k:free'), 'different_binding_scope',
    'Σ の中の a_k は数列の第k項。束縛変数を含むので、外の a_k と同一視しない')

  forbid(reg, problem('premise'), problem('conclusion'), 'premise_vs_conclusion',
    '前提 a₁ = α を α について解いて a₁ を返すのは、前提の言い換えであって答えではない')

  forbid(reg, problem('goal'), problem('other_unknown'), 'different_symbol_role',
    '目標が log r のとき、r の解領域を答えとして返さない')
}

// ---------------------------------------------------------------------------
// 監査
// ---------------------------------------------------------------------------

export type IdentityViolation = { kind: string; detail: string }

export function auditIdentity(reg: IdentityRegistry): IdentityViolation[] {
  const out: IdentityViolation[] = []
  for (const c of reg.claims) {
    const blocked = isForbidden(reg, c.left, c.right)
    if (blocked) {
      out.push({ kind: 'forbidden_identification_claimed',
        detail: `${scopedKey(c.left)} ≡ ${scopedKey(c.right)}: ${blocked.detail}` })
    }
    if (c.kind === 'analogy' && c.certificate) {
      out.push({ kind: 'analogy_with_certificate',
        detail: '類似に証明書は付かない。証明に使えるのは定義・等式・標準同型だけ' })
    }
    if (PROVABLE.includes(c.kind) && c.left.world !== c.right.world && !c.certificate) {
      out.push({ kind: 'cross_world_equality_without_certificate',
        detail: `${scopedKey(c.left)} と ${scopedKey(c.right)} は別の world。`
          + '等式を名乗るなら、規約の対応と証明書が要る' })
    }
  }
  return out
}

/**
 * 経路が可換とは限らない（§13）。
 * A → B → D と A → C → D が同じ結果になると自動で仮定しない。
 */
export type CommutativityStatus =
  | 'commutes' | 'commutes_up_to_isomorphism' | 'commutes_under_conditions'
  | 'does_not_commute' | 'unknown'

export type RouteSquare = {
  corner: [SemanticId, SemanticId, SemanticId, SemanticId]
  routeA: SemanticId[]
  routeB: SemanticId[]
  status: CommutativityStatus
  conditions?: string[]
  certificate?: SemanticId
}

/** 未検査の四角形を可換と仮定していないか */
export function auditCommutativity(squares: RouteSquare[]): IdentityViolation[] {
  return squares
    .filter(s => s.status === 'commutes' && !s.certificate)
    .map(s => ({ kind: 'assumed_commutative',
      detail: `${s.routeA.join('→')} と ${s.routeB.join('→')} を証明書なしで可換としている` }))
}
