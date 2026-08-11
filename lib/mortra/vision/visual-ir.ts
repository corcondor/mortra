/**
 * Visual IR — 表示の意味であって、描画ではない（仕様 §11）。
 *
 *   Domain IR  →  Certified Transport  →  Visual IR  →  Timeline  →  Renderer
 *
 * この層は Three.js も SVG も canvas も知らない。座標も色もカメラも持つが、
 * 大事なのは各要素が semantic ID に結び付いていること。
 *
 * それによって、
 *   式をクリックすると対応する図形が光る
 *   図形をクリックするとそれを使った証明の段が出る
 *   表現を切り替えても「同じ物」を追い続ける
 * が、後付けの紐付けではなく構造として出てくる。
 *
 * 分野ごとの中身（格子・力学・テンソル）は domain 側が Visual IR を作る。
 * domain が Three.js を直接触ると、この分離が壊れる。
 */
import type { SemanticId } from '../world/world-types'

export type Vec = [number, number, number]

/** 表示要素。すべて semantic ID を持つ。持たない要素は作れない */
type Bound<T> = T & {
  id: SemanticId
  /** この見た目が表している数学対象 */
  of: SemanticId
  /** 現在の推論で必要かどうか。不要な物は薄くするか出さない（仕様 §15） */
  role?: 'focus' | 'context' | 'faded'
}

export type VisualNode =
  | Bound<{ kind: 'point'; at: Vec; label?: string }>
  | Bound<{ kind: 'segment'; from: Vec; to: Vec }>
  | Bound<{ kind: 'line'; through: Vec; direction: Vec }>
  | Bound<{ kind: 'circle'; center: Vec; radius: number; normal?: Vec }>
  | Bound<{ kind: 'curve'; points: Vec[] }>
  | Bound<{ kind: 'surface'; triangles: [Vec, Vec, Vec][] }>
  | Bound<{ kind: 'pointCloud'; points: Vec[] }>
  | Bound<{ kind: 'segmentSet'; segments: [Vec, Vec][] }>
  | Bound<{ kind: 'planeFamily'; normal: Vec; spacing: number; count: number }>
  | Bound<{ kind: 'arrow'; from: Vec; to: Vec; head?: number }>
  | Bound<{ kind: 'orbitArrow'; center: Vec; from: Vec; to: Vec }>
  | Bound<{ kind: 'rootVector'; at: Vec; simple?: boolean }>
  | Bound<{ kind: 'dynkinNode'; index: number; bonds: number[] }>
  | Bound<{ kind: 'tensorNode'; legs: { name: string; variance: 'up' | 'down' }[] }>
  | Bound<{ kind: 'feynmanEdge'; from: Vec; to: Vec; particle: string }>
  | Bound<{ kind: 'spring'; from: Vec; to: Vec; coils: number }>
  | Bound<{ kind: 'rigidBody'; center: Vec; orientation: [number, number, number, number] }>
  | Bound<{ kind: 'angleMark'; at: Vec; from: Vec; to: Vec; right?: boolean }>
  | Bound<{ kind: 'lengthMark'; from: Vec; to: Vec; ticks: number }>
  | Bound<{ kind: 'parallelMark'; from: Vec; to: Vec; ticks: number }>
  /** 式と文章も表示要素。図と同じ ID 空間に置くから同期できる */
  | Bound<{ kind: 'formulaAnchor'; latex: string; near?: SemanticId }>
  | Bound<{ kind: 'narrationAnchor'; text: string; near?: SemanticId }>
  | Bound<{ kind: 'certificateBadge'; status: string; method: string }>

export type Camera = {
  position: Vec
  target: Vec
  /** 数学的な意味を持つ視点。「逆格子から見る」など */
  meaning?: string
}

// ---------------------------------------------------------------------------
// 時間軸（仕様 §11 Presentation Timeline）
// ---------------------------------------------------------------------------

/** 一つの拍。証明の一段・作図の一段・変形の一段が、これ一つに対応する */
export type Beat = {
  id: SemanticId
  /** この拍が対応する主張。無い場合は骨組みや導入 */
  claim?: SemanticId
  /** 注目する対象。ここに無い物は薄くなる */
  focus: SemanticId[]
  enter: VisualNode[]
  update: { id: SemanticId; patch: Partial<VisualNode> }[]
  exit: SemanticId[]
  camera?: Camera
  formula?: { latex: string; of: SemanticId }
  narration?: { text: string; of: SemanticId }
  /** 検証の状態を画面に出す。証明済みでないものを証明済みに見せない */
  certificate?: { status: string; method: string }
  /** 拍の長さ。スクロール駆動なら位置、動画なら秒 */
  timing: { seconds?: number; scrollFraction?: number }
}

export type Timeline = {
  id: SemanticId
  beats: Beat[]
  /** スクロールを戻すと数学の状態も戻る（仕様 §25）。
   *  拍が状態の関数として書かれているなら、これは自動的に成り立つ */
  scrubbable: boolean
}

export type VisualScene = {
  id: SemanticId
  /** 最初から立っている骨組み。証明の段ではない */
  frame: VisualNode[]
  timeline: Timeline
  /** 表現の種類。同じ世界の別の姿を並べられる */
  representation: string
}

// ---------------------------------------------------------------------------
// 検査
// ---------------------------------------------------------------------------

export type VisualViolation = { kind: string; detail: string }

/**
 * Visual IR が意味から切れていないかを見る。
 *
 * 図が説明の挿絵になっていた原因は、表示要素が意味を参照していなかったこと。
 * ここで落とせば、切れた図は最初から作れない。
 */
export function auditScene(scene: VisualScene, knownSemantics: Set<string>): VisualViolation[] {
  const out: VisualViolation[] = []
  const all = [...scene.frame, ...scene.timeline.beats.flatMap(b => b.enter)]

  for (const node of all) {
    if (!node.of) {
      out.push({ kind: 'node_without_meaning', detail: `${node.kind} が意味を指していない` })
      continue
    }
    if (knownSemantics.size && !knownSemantics.has(node.of)) {
      out.push({ kind: 'unknown_meaning', detail: `${node.kind} → ${node.of} は世界に無い` })
    }
  }

  for (const beat of scene.timeline.beats) {
    if (beat.claim && !beat.focus.length) {
      out.push({ kind: 'claim_without_focus',
        detail: `主張のある拍が何も注目していない（${beat.id}）` })
    }
    // 式と図が同じ拍で別の物を指していたら、それは同期していない
    if (beat.formula && beat.claim && beat.formula.of !== beat.claim
      && !beat.focus.includes(beat.formula.of)) {
      out.push({ kind: 'formula_out_of_sync',
        detail: `式が拍の主張とも注目対象とも無関係（${beat.id}）` })
    }
  }
  return out
}

/** 図と証明がどれだけ同期しているか。仕様 §9.3 の proof_diagram_sync_rate */
export function proofDiagramSyncRate(scene: VisualScene): number {
  const withClaim = scene.timeline.beats.filter(b => b.claim)
  if (!withClaim.length) return 0
  const synced = withClaim.filter(b =>
    b.enter.some(n => n.of === b.claim || b.focus.includes(n.of))
    || b.update.some(u => b.focus.includes(u.id)))
  return synced.length / withClaim.length
}

/** 表現をまたいで同じ意味が追えているか。仕様 §9.3 の cross_representation_consistency */
export function crossRepresentationConsistency(scenes: VisualScene[]): number {
  if (scenes.length < 2) return 1
  const sets = scenes.map(s => new Set(
    [...s.frame, ...s.timeline.beats.flatMap(b => b.enter)].map(n => n.of)))
  const shared = [...sets[0]].filter(id => sets.every(s => s.has(id)))
  const union = new Set(sets.flatMap(s => [...s]))
  return union.size ? shared.length / union.size : 0
}
