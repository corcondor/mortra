/**
 * MortraWorld — 一つの意味状態から、複数の成果物が派生する（仕様 §19, §20）。
 *
 * これまで成果物は別々に生成していた。図を作る関数、記事を書く関数、
 * 動画を書き出す関数がそれぞれ独立していたので、
 * 「証明を座標から幾何に変えて」と言われたときに全部を作り直すしかなかった。
 *
 * ここでは逆にする。世界は一つで、成果物はその射影にする。
 *
 *   世界（意味・証明・証明書）
 *     → 表現経路
 *       → 成果物（解答・証明・図・3D・記事・動画・投稿）
 *
 * 「高校生向けに」「3Dで」「15秒で」「逆格子から」は、
 * 別々の生成ではなく同じ世界の描画方針の変更として扱う。
 *
 * 大きな書き換えはしない。既存の /solve /robot ScrollSolid article video を
 * adapter で包んで、この型に合わせる。
 */

/** 意味対象の同一性。すべての成果物はこの ID を参照する。
 *  文字列の一致ではなく ID の一致で「同じ物」を判断する。 */
export type SemanticId = string & { readonly __brand: 'SemanticId' }

export const semanticId = (value: string) => value as SemanticId

// ---------------------------------------------------------------------------
// 意味の側
// ---------------------------------------------------------------------------

/** 型付きの数学的対象。格子・三角形・多項式・不等式など */
export type SemanticObject = {
  id: SemanticId
  sort: string
  /** その対象を作った経緯。どの前提から来たか */
  origin: { kind: 'given' | 'constructed' | 'derived'; from: SemanticId[] }
  /** 表示に使う短い名前。A, BC, Λ, Θ など */
  label?: string
  payload?: unknown
}

/** 主張。証明されたかどうかは certificate 側で決まる */
export type Claim = {
  id: SemanticId
  statement: string
  about: SemanticId[]
  status: ClaimStatus
}

/**
 * 主張の強さ。仕様 §8 の taxonomy に合わせる。
 * 「具体例で合った」と「一般に証明した」を同じ言葉で呼ばない。
 */
export type ClaimStatus =
  | 'proved'                 // 記号的に導出し、恒等式として確かめた
  | 'verified_instance'      // 具体値では一致した。一般には未証明
  | 'numerically_supported'  // 数値では合うが記号的な確認が無い
  | 'conjectured'            // 観測しただけ
  | 'unverified'             // 出したが確認が取れていない
  | 'rejected'               // 確認して、成り立たないと分かった
  | 'unformalized'           // 形式化できていない
  | 'unsupported'            // 扱える範囲の外

/** 証明書。どの手段でどこまで確かめたか */
export type Certificate = {
  id: SemanticId
  claim: SemanticId
  /** 検証に使った独立な手段。LLM の自己申告は認めない（仕様 §6.6） */
  method:
    | 'symbolic_identity' | 'exact_substitution' | 'groebner_reduction'
    | 'interval_arithmetic' | 'forward_chaining'
    | 'numeric_sampling' | 'property_test'
  /** 検証が消費した前提。書かれていない前提を使っていないかを見る */
  consumedPremises: SemanticId[]
  detail?: string
}

/** 証明の有向グラフ。別経路を保つので「別の証明」が出せる（仕様 §16） */
export type ProofGraph = {
  nodes: Claim[]
  edges: { from: SemanticId[]; to: SemanticId; rule: string }[]
  /** 目標へ至る経路。複数あってよい */
  routes: { id: SemanticId; goal: SemanticId; steps: SemanticId[]; cost: number }[]
}

// ---------------------------------------------------------------------------
// 表現の側
// ---------------------------------------------------------------------------

/** 表現のあいだを移す射。裸の値を渡すだけの橋は射と呼ばない（仕様 §3） */
export type RepresentationRoute = {
  id: SemanticId
  source: string
  target: string
  preconditions: string[]
  /** 運ばれる意味。何が移動したのか */
  transports: SemanticId[]
  /** 保たれる不変量。ここが空なら、それは射ではない */
  preservedInvariants: string[]
  proofObligations: SemanticId[]
  certificate?: SemanticId
  failureState?: string
}

/** 成果物。すべて semantic ID を参照し、独立には作らない（仕様 §18） */
export type ArtifactKind =
  | 'solution' | 'proof' | 'alternative_proof'
  | 'diagram' | 'interactive_diagram' | 'scene3d' | 'simulation'
  | 'liveproof' | 'article' | 'research_note'
  | 'social_card' | 'reel' | 'video' | 'worksheet' | 'pdf' | 'slide'
  | 'robot_trajectory'

export type Artifact = {
  id: SemanticId
  kind: ArtifactKind
  /** この成果物が参照している意味。ここが空の成果物は作らせない */
  references: SemanticId[]
  /** どの描画方針で作られたか。方針を変えると作り直す対象が決まる */
  policy: RenderPolicy
  /** 出力の実体。ファイルパス・URL・シリアライズ済み IR */
  output?: { path?: string; url?: string; inline?: unknown }
  builtFrom?: SemanticId
}

/**
 * 描画方針。「高校生向け」「3Dで」「15秒で」はここを変えるだけ。
 * 成果物を別々に作り直すのではなく、同じ世界を別の方針で描く。
 */
export type RenderPolicy = {
  audience?: 'highschool' | 'undergraduate' | 'researcher' | 'general'
  representation?: 'euclidean' | 'coordinate' | 'complex' | 'matrix' | 'lattice' | 'reciprocal'
  dimension?: '2d' | '3d'
  durationSeconds?: number
  formulaDensity?: 'minimal' | 'normal' | 'detailed'
  language?: 'ja' | 'en'
}

/** 変更の履歴。何を変えたら何が作り直されたかを残す */
export type Revision = {
  id: SemanticId
  at: string
  request: string
  /** 方針の差分。意味は変えず描き方だけ変えた場合はこちらだけ動く */
  policyDelta?: Partial<RenderPolicy>
  /** 意味の差分。証明経路を変えた場合はこちら */
  routeChange?: { goal: SemanticId; from: SemanticId; to: SemanticId }
  invalidated: SemanticId[]
  rebuilt: SemanticId[]
}

// ---------------------------------------------------------------------------

export type MortraWorld = {
  id: SemanticId
  /** 何をしたいか。自然文のまま持つ */
  brief: { text: string; constraints?: string[] }

  objects: SemanticObject[]
  claims: Claim[]
  certificates: Certificate[]
  proofGraph?: ProofGraph

  routes: RepresentationRoute[]
  artifacts: Artifact[]
  revisions: Revision[]
}

// ---------------------------------------------------------------------------
// 整合の検査。これを通らない世界は成果物を出さない
// ---------------------------------------------------------------------------

export type WorldViolation = { kind: string; id: SemanticId; detail: string }

/**
 * 世界が矛盾していないかを見る。
 *
 * 成果物が存在しない意味を参照していないか、
 * proved と名乗る主張に証明書があるか、
 * 射が不変量を宣言しているか。
 */
export function auditWorld(world: MortraWorld): WorldViolation[] {
  const out: WorldViolation[] = []
  const known = new Set<string>([
    ...world.objects.map(o => o.id),
    ...world.claims.map(c => c.id),
  ])
  const certified = new Set(world.certificates.map(c => c.claim))

  for (const artifact of world.artifacts) {
    if (!artifact.references.length) {
      out.push({ kind: 'artifact_without_meaning', id: artifact.id,
        detail: '意味を参照していない成果物は、独立生成になっている' })
    }
    for (const ref of artifact.references) {
      if (!known.has(ref)) {
        out.push({ kind: 'dangling_reference', id: artifact.id, detail: `未知の意味 ${ref}` })
      }
    }
  }

  for (const claim of world.claims) {
    if (claim.status === 'proved' && !certified.has(claim.id)) {
      out.push({ kind: 'proved_without_certificate', id: claim.id,
        detail: 'proved と名乗るなら独立な検証の証明書が要る' })
    }
  }

  for (const route of world.routes) {
    if (!route.preservedInvariants.length) {
      out.push({ kind: 'route_without_invariant', id: route.id,
        detail: '保つ不変量を宣言しない移動は、射ではなく単なる橋' })
    }
  }

  return out
}

/** 方針を変えたときに作り直す必要がある成果物を返す */
export function affectedByPolicy(
  world: MortraWorld,
  delta: Partial<RenderPolicy>,
): Artifact[] {
  const keys = Object.keys(delta) as (keyof RenderPolicy)[]
  return world.artifacts.filter(a =>
    keys.some(k => a.policy[k] !== undefined && a.policy[k] !== delta[k]))
}

/** 証明経路を変えたときに作り直す必要がある成果物を返す */
export function affectedByRoute(world: MortraWorld, changedClaims: SemanticId[]): Artifact[] {
  const changed = new Set(changedClaims)
  return world.artifacts.filter(a => a.references.some(r => changed.has(r)))
}
