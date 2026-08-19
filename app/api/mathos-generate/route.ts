import { NextRequest, NextResponse } from 'next/server'
import { getSupabaseAdmin } from '@/lib/supabase-admin'
import { generateLiveProblem, type StructureBlueprint } from '@/lib/mathos-live'
import { buildProblemDiagram } from '@/lib/mortra/problem-artifact'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'
import { generalizeParents, type GeneralizationCertificate } from '../../../worker/src/generalization-kernel'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 300

/**
 * MathOS 作問セッション — LLM を使わない。
 *
 * その場で対象を構築し（ライブ生成）、答えをツールで計算・独立検証し、
 * 既存問題との類似度を実際に計算して問題カードとして保存する。
 * External language-model APIs are not used by this route.
 */

type PoolProblem = {
  statement_tex?: string
  answer_tex?: string
  solution_tex?: string
  family_id?: string
  domain?: string
  difficulty?: { band?: string; score?: number }
  lift_certificate?: { morphism_chain?: string[] }
  verification?: { method?: string }
  novelty?: { maximum_surface_jaccard?: number }
}

const POOL = (verifiedBatch as { problems: PoolProblem[] }).problems ?? []

/** 正規化（SIMILARITY.md の κ）: レイアウト命令を落として空白を除去 */
function canonical(text: string): string {
  return text
    .toLowerCase()
    .replace(/\\(left|right|displaystyle|textstyle)/g, '')
    .replace(/\\[dt]frac/g, '\\frac')
    .replace(/\s+/g, '')
}

/** 文字 3-gram 集合 */
function ngrams(text: string, n = 3): Set<string> {
  const s = canonical(text)
  const out = new Set<string>()
  if (s.length <= n) {
    if (s) out.add(s)
    return out
  }
  for (let i = 0; i + n <= s.length; i++) out.add(s.slice(i, i + n))
  return out
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (!a.size && !b.size) return 1
  let inter = 0
  for (const g of a) if (b.has(g)) inter++
  const union = a.size + b.size - inter
  return union ? inter / union : 0
}

/**
 * 既存問題との重複判定。
 *
 * 実測したところ、同じ族の *別パラメータ* 問題どうしでも表層 3-gram Jaccard は
 * 0.74〜0.97 になる（文型が同じなので当然）。したがって表層類似度だけでは
 * 「同族の別問題」と「本当の重複」を区別できない。そこで:
 *
 *   - 重複 = (族, 正規化した答え) が既出、または問題文が完全一致
 *   - 表層類似度 = 参考値として実測（0 のハードコードはしない）。
 *     *別の族* と表層が近ければ、それは本当に似た問題なので警告に使う。
 */
type NoveltyEntry = {
  id: string
  family: string | null
  answer: string | null
  canonicalStatement: string
  canonicalAnswer: string | null
  grams: Set<string>
}

type NoveltyCorpus = {
  entries: NoveltyEntry[]
  statements: Set<string>
  familyAnswers: Set<string>
}

function noveltyEntry(
  statement: string,
  family: string | null,
  answer: string | null,
  id: string,
): NoveltyEntry {
  return {
    id,
    family,
    answer,
    canonicalStatement: canonical(statement),
    canonicalAnswer: answer ? canonical(answer) : null,
    grams: ngrams(statement),
  }
}

async function loadNoveltyCorpus(): Promise<NoveltyCorpus> {
  const entries: NoveltyEntry[] = []
  for (const p of POOL) {
    if (!p.statement_tex) continue
    entries.push(noveltyEntry(
      p.statement_tex,
      p.family_id ?? null,
      p.answer_tex ?? null,
      p.family_id ?? 'pool',
    ))
  }

  // セッションごとに1回だけ取得する。旧実装は候補ごとに同じ4000問を再取得していた。
  const { data } = await getSupabaseAdmin()
    .from('problems')
    .select('id,statement,answer,topic_b')
    .not('statement', 'is', null)
    .limit(4000)
  for (const row of (data ?? []) as {
    id: string; statement: string; answer: string | null; topic_b: string | null
  }[]) {
    if (!row.statement) continue
    entries.push(noveltyEntry(row.statement, row.topic_b, row.answer, row.id))
  }

  return {
    entries,
    statements: new Set(entries.map(entry => entry.canonicalStatement)),
    familyAnswers: new Set(entries
      .filter(entry => entry.family && entry.canonicalAnswer)
      .map(entry => `${entry.family}\u0000${entry.canonicalAnswer}`)),
  }
}

function addToNoveltyCorpus(
  corpus: NoveltyCorpus,
  statement: string,
  family: string,
  answer: string,
  id: string,
) {
  const entry = noveltyEntry(statement, family, answer, id)
  corpus.entries.push(entry)
  corpus.statements.add(entry.canonicalStatement)
  if (entry.canonicalAnswer) corpus.familyAnswers.add(`${family}\u0000${entry.canonicalAnswer}`)
}

function assessNovelty(
  statement: string,
  familyId: string,
  answer: string,
  corpus: NoveltyCorpus,
): {
  duplicate: boolean
  score: number
  closestId: string | null
  closestFamily: string | null
  crossFamilyMax: number
  comparedAgainst: number
} {
  const target = ngrams(statement)
  const canonStatement = canonical(statement)
  const canonAnswer = canonical(answer)
  const duplicate = corpus.statements.has(canonStatement) ||
    corpus.familyAnswers.has(`${familyId}\u0000${canonAnswer}`)

  if (duplicate) {
    return {
      duplicate: true,
      score: 1,
      closestId: null,
      closestFamily: familyId,
      crossFamilyMax: 0,
      comparedAgainst: corpus.entries.length,
    }
  }

  let best = 0
  let closestId: string | null = null
  let closestFamily: string | null = null
  let crossFamilyMax = 0

  for (const entry of corpus.entries) {
    const similarity = jaccard(target, entry.grams)
    if (similarity > best) {
      best = similarity
      closestId = entry.id
      closestFamily = entry.family
    }
    if (entry.family !== familyId && similarity > crossFamilyMax) crossFamilyMax = similarity
  }

  return {
    duplicate,
    score: Number(best.toFixed(4)),
    closestId,
    closestFamily,
    crossFamilyMax: Number(crossFamilyMax.toFixed(4)),
    comparedAgainst: corpus.entries.length,
  }
}

type ParentInput = {
  id?: string
  topic_a?: string
  topic_b?: string | null
  statement?: string
  answer?: string | null
  solution?: string | null
  inspiration?: string | null
  meta?: string | Record<string, unknown> | null
}

type GenerationProfile = {
  domain?: string
  tags: string[]
  requiredTags: string[]
  queryTags: string[]
  parentIds: string[]
  atlasPath?: string[]
  atlasPaths?: string[][]
  parentAnchors?: string[]
  parentAnchorSets?: Array<{ parentId: string; anchors: string[] }>
  allParentScaffold?: boolean
  recovery?: boolean
  mode: 'similar' | 'fusion' | 'expand' | 'batch'
}

const QUERY_TAGS = new Set([
  'area', 'volume', 'radius_ratio', 'radius_product', 'circumradius',
  'curvature', 'center_distance', 'reciprocal_invariant', 'limit',
  'extremum', 'function_graph',
])

// 直接一致しないときも、Atlas上で意味のある隣接射だけを許す。遠距離ジャンプはしない。
const EXECUTABLE_TAG_BRIDGES: Record<string, string[]> = {
  centroid: ['triangle', 'circle_centers'],
  circle_centers: ['triangle', 'pythagorean', 'heron'],
  heron: ['triangle', 'symmetric_polynomial', 'circle_centers'],
  tangent: ['parabola', 'locus'],
  intersection: ['polynomial_roots', 'algebra'],
  envelope: ['locus', 'passage_region', 'parabola'],
  locus: ['passage_region', 'parabola'],
  minkowski_sum: ['passage_region', 'disk'],
  polynomial_roots: ['symmetric_polynomial', 'algebra'],
  symmetric_polynomial: ['polynomial_roots', 'heron', 'algebra'],
  recurrence: ['iteration', 'matrix', 'characteristic_polynomial'],
  matrix: ['recurrence', 'iteration', 'characteristic_polynomial'],
  characteristic_polynomial: ['matrix', 'recurrence', 'polynomial_roots'],
  polynomial_system: ['algebra', 'polynomial_roots', 'dynamical_system'],
  triangle: ['heron', 'circle_centers', 'pythagorean'],
  pythagorean: ['triangle', 'number_theory', 'circle_centers', 'gcd'],
  number_theory: ['pythagorean', 'gcd', 'modular', 'parity'],
  gcd: ['number_theory', 'pythagorean', 'modular'],
  modular: ['number_theory', 'gcd', 'parity'],
  parity: ['number_theory', 'modular'],
  dynamical_system: ['iteration', 'recurrence'],
  iteration: ['recurrence', 'matrix'],
  ellipse: ['locus', 'tangent'],
  mobius: ['iteration', 'matrix', 'cross_ratio', 'roots_of_unity'],
  cross_ratio: ['mobius', 'projective_geometry'],
  roots_of_unity: ['complex', 'polynomial_roots', 'mobius'],
  projective_geometry: ['cross_ratio', 'mobius'],
  power_sum: ['symmetric_polynomial', 'polynomial_roots'],
  calculus: ['derivative', 'variation', 'function_graph', 'extremum'],
  derivative: ['calculus', 'variation', 'extremum'],
  variation: ['derivative', 'function_graph', 'extremum'],
  function_graph: ['variation', 'extremum'],
  extremum: ['derivative', 'variation', 'function_graph'],
}

function expandedFocusTags(tags: string[]): string[] {
  return [...new Set(tags.flatMap(tag => [tag, ...(EXECUTABLE_TAG_BRIDGES[tag] ?? [])]))]
}

function atlasNeighbors(tag: string): string[] {
  const direct = EXECUTABLE_TAG_BRIDGES[tag] ?? []
  const reverse = Object.entries(EXECUTABLE_TAG_BRIDGES)
    .filter(([, neighbors]) => neighbors.includes(tag))
    .map(([source]) => source)
  return [...new Set([...direct, ...reverse])]
}

function shortestAtlasPath(from: string, to: string, maxEdges = 4): string[] | null {
  if (from === to) return [from]
  const queue: string[][] = [[from]]
  const visited = new Set([from])
  while (queue.length) {
    const path = queue.shift()!
    if (path.length - 1 >= maxEdges) continue
    for (const neighbor of atlasNeighbors(path.at(-1)!)) {
      if (visited.has(neighbor)) continue
      const next = [...path, neighbor]
      if (neighbor === to) return next
      visited.add(neighbor)
      queue.push(next)
    }
  }
  return null
}

function preservedByAtlas(tag: string, candidateTags: string[]): boolean {
  return candidateTags.includes(tag) || candidateTags.some(candidateTag =>
    shortestAtlasPath(tag, candidateTag, 1) !== null,
  )
}

const TAG_PATTERNS: Array<[string, RegExp]> = [
  ['calculus', /微分|導関数|増減|極大|極小|calculus|derivative/i],
  ['derivative', /導関数|微分(?:する|せよ|して)|f\s*'|\\frac\{d\}\{d[a-z]\}|derivative/i],
  ['variation', /増減表|増加区間|減少区間|単調(?:増加|減少)|variation|monotonic/i],
  ['function_graph', /グラフ(?:の)?概形|概形を(?:か|描)|関数のグラフ|function[_\s-]?graph|sketch/i],
  ['extremum', /極大(?:値)?|極小(?:値)?|最大値|最小値|extrem(?:um|a)|maximum|minimum/i],
  ['integral', /\\int|積分|integral|\\mathrm\{Ei\}|\bEi\s*\(/i],
  ['inequality', /不等式|大小を比較|評価せよ|比較せよ|\\le|\\ge|[<>]|inequal/i],
  ['exponential', /指数関数|指数積分|e\^|\\exp|exponential/i],
  ['logarithm', /対数|\\ln|\\log|logarithm/i],
  ['special_function', /指数積分|ガウス積分|特殊関数|\\mathrm\{Ei\}|special[_\s-]?function/i],
  ['asymptotic', /漸近|asymptotic|同値|オーダー/i],
  ['cross_ratio', /交比|cross[-_\s]?ratio/i],
  ['mobius', /m[oö]bius|メビウス|一次分数変換|分数線形変換/i],
  ['roots_of_unity', /1の\s*[nNＮ]乗根|1の冪根|z\^\{?n\}?\s*=\s*1|roots? of unity|単位根/i],
  ['projective_geometry', /射影|projective/i],
  ['power_sum', /べき和|冪和|power[_\s-]?sum/i],
  ['passage_region', /通過領域|掃過領域|swept[_\s-]?region|passage[_\s-]?region/i],
  ['envelope', /包絡線|envelope/i],
  ['locus', /軌跡|locus/i],
  ['area', /面積|area/i],
  ['volume', /体積|volume/i],
  ['minkowski_sum', /ミンコフスキー|minkowski/i],
  ['geometry', /幾何|図形|平面|空間|円|三角形|四角形|直線|曲線|geometry/i],
  ['segment', /線分|弦|segment|chord/i],
  ['circle', /円周|円板|円(?!分)|circle|disk/i],
  ['parabola', /放物線|parabola/i],
  ['ellipse', /楕円|ellipse/i],
  ['centroid', /重心|centroid/i],
  ['tangent', /接線|tangent/i],
  ['intersection', /交点|intersection/i],
  ['triangle', /三角形|triangle/i],
  ['pythagorean', /ピタゴラス|直角三角形|pythagorean/i],
  ['gcd', /互いに素|最大公約数|gcd|coprime/i],
  ['parity', /偶奇|奇数|偶数|parity/i],
  ['modular', /合同|剰余|modulo|mod\b/i],
  ['inradius', /内接円半径|内接円の半径|inradius/i],
  ['polynomial_roots', /方程式[^。\n]{0,140}(?:解|根)|(?:解|根)[^。\n]{0,100}(?:方程式|多項式)|polynomial[_\s-]?roots?|root[_\s-]?polynomial/i],
  ['polynomial_system', /連立|x\^\d+[^。\n]{0,100}y\^\d+|polynomial[_\s-]?system/i],
  ['symmetric_polynomial', /解と係数|対称式|vieta|symmetric[_\s-]?polynomial/i],
  ['heron', /ヘロン|heron/i],
  ['circle_centers', /外心|内心|傍心|外接円|内接円|傍接円|circumcenter|incenter|excenter/i],
  ['curvature', /曲率|curvature/i],
  ['center_distance', /中心間距離|center[_\s-]?distance|OI\^?2/i],
  ['radius_ratio', /半径[^。\n]{0,40}比|R\s*\/\s*r|radius[_\s-]?ratio/i],
  ['radius_product', /半径[^。\n]{0,40}積|radius[_\s-]?product/i],
  ['circumradius', /外接円半径|circumradius/i],
  ['reciprocal_invariant', /逆数[^。\n]{0,30}(?:和|不変)|reciprocal[_\s-]?invariant/i],
  ['dynamical_system', /反復|周期[^。\n]{0,40}軌道|力学系|dynamical[_\s-]?system|orbit/i],
  ['rotation', /回転|rotation/i],
  ['probability', /確率|期待値|probability|expectation/i],
  ['number_theory', /整数|素数|合同|剰余|number[_\s-]?theory|modular/i],
  ['recurrence', /数列|漸化式|recurrence|sequence/i],
  ['matrix', /行列|固有値|matrix|eigenvalue/i],
  ['characteristic_polynomial', /特性方程式|特性多項式|characteristic[_\s-]?polynomial/i],
  ['iteration', /反復|合成|iteration|iterate|mobius/i],
  ['complex', /複素|complex/i],
  ['limit', /極限|limit/i],
  ['algebra', /代数|方程式|多項式|algebra|polynomial/i],
]

function inferTags(text: string): string[] {
  return TAG_PATTERNS.filter(([, pattern]) => pattern.test(text)).map(([tag]) => tag)
}

function buildGenerationProfile(
  parents: ParentInput[],
  fallbackDomain?: string,
  mode: GenerationProfile['mode'] = 'batch',
): GenerationProfile {
  const tagCounts = new Map<string, number>()
  const evidenceCounts = new Map<string, number>()
  const parentTagSets: Set<string>[] = []
  const addTags = (text: string, weight: number) => {
    for (const tag of new Set(inferTags(text))) {
      tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + weight)
    }
  }
  const addEvidenceTags = (text: string, weight: number) => {
    addTags(text, weight)
    for (const tag of new Set(inferTags(text))) {
      evidenceCounts.set(tag, (evidenceCounts.get(tag) ?? 0) + weight)
    }
  }
  for (const parent of parents) {
    // 類題の核は分類ラベルではなく問題本文。topic/meta は補助証拠としてだけ使う。
    addEvidenceTags(parent.statement ?? '', 4)
    addTags([parent.topic_a, parent.topic_b].filter(Boolean).join(' '), 1)
    addEvidenceTags([parent.answer, parent.solution, parent.inspiration, typeof parent.meta === 'string'
      ? parent.meta
      : JSON.stringify(parent.meta ?? {})].filter(Boolean).join(' '), 1)
    parentTagSets.push(new Set(inferTags([
      parent.statement,
      parent.answer,
      parent.solution,
      parent.inspiration,
      typeof parent.meta === 'string' ? parent.meta : JSON.stringify(parent.meta ?? {}),
    ].filter(Boolean).join(' '))))
  }
  const tags = [...tagCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag)

  const semanticTags = tags.filter(tag =>
    evidenceCounts.has(tag) && !['geometry', 'algebra', 'circle'].includes(tag),
  )
  const structuralTags = [
    ...semanticTags.filter(tag => !QUERY_TAGS.has(tag)),
    ...semanticTags.filter(tag => QUERY_TAGS.has(tag)),
  ]
  const commonStructuralTags = structuralTags.filter(tag =>
    parentTagSets.length > 0 && parentTagSets.every(parentTags => parentTags.has(tag)),
  )
  const fusionStructuralTags = commonStructuralTags.filter(tag => tag !== 'area')
  const requiredTags = mode === 'similar' || mode === 'expand'
    ? structuralTags.slice(0, 3)
    : mode === 'fusion'
      ? (fusionStructuralTags.length ? fusionStructuralTags : structuralTags.slice(0, 1)).slice(0, 3)
      : []

  let domain = fallbackDomain
  if (tags.some(tag => ['passage_region', 'envelope', 'locus', 'area', 'volume', 'geometry'].includes(tag))) {
    domain = 'geometry'
  } else if (tags.includes('probability')) {
    domain = 'probability'
  } else if (tags.includes('number_theory')) {
    domain = 'number_theory'
  } else if (tags.includes('complex')) {
    domain = 'complex'
  } else if (tags.includes('algebra')) {
    domain = 'algebra'
  }

  return {
    domain,
    tags,
    requiredTags,
    queryTags: semanticTags.filter(tag => QUERY_TAGS.has(tag)),
    parentIds: parents.flatMap(parent => parent.id ? [parent.id] : []),
    parentAnchorSets: parents.map((parent, index) => ({
      parentId: parent.id ?? `parent-${index + 1}`,
      anchors: parentAnchorTags(parent),
    })),
    mode,
  }
}

const FUSION_GENERIC_TAGS = new Set([
  'geometry', 'algebra', 'circle', 'area', 'volume', 'probability', 'complex', 'number_theory',
])

const SOLUTION_CORE_TAGS = new Set([
  'cross_ratio', 'mobius', 'roots_of_unity', 'projective_geometry', 'power_sum',
  'passage_region', 'envelope', 'locus', 'minkowski_sum', 'centroid', 'tangent',
  'intersection', 'triangle', 'polynomial_roots', 'symmetric_polynomial', 'heron',
  'polynomial_system',
  'circle_centers', 'dynamical_system', 'recurrence', 'iteration', 'matrix',
  'characteristic_polynomial', 'pythagorean', 'gcd', 'modular',
  'integral', 'inequality', 'exponential', 'logarithm', 'special_function', 'asymptotic', 'limit',
  'calculus', 'derivative', 'variation', 'function_graph', 'extremum',
])

type ParentCoverage = {
  parentId: string
  anchors: string[]
  exact: string[]
  bridged: string[]
  passed: boolean
}

type FusionDerivation = {
  passed: boolean
  reason: string
  assignments: Array<{
    parentId: string
    portId: string
    role: string
    matchedAnchors: string[]
    witnessSteps: string[]
  }>
  bridges: Array<{ id: string; witnessStep: string; consumes: string[]; produces: string }>
  ablationPassed: boolean
}

function evaluateParentCoverage(profile: GenerationProfile, candidateTags: string[]): ParentCoverage[] {
  return (profile.parentAnchorSets ?? []).map(({ parentId, anchors }) => {
    // 先頭は本文・解答から得た最も固有な構造。一般タグを多数一致させても代替できない。
    const primary = anchors.slice(0, 3)
    const exact = primary.filter(tag => candidateTags.includes(tag))
    const bridged = primary.filter(tag =>
      !candidateTags.includes(tag) && preservedByAtlas(tag, candidateTags),
    )
    // 親本文を意味署名へ持ち上げられなかった場合、任意の既存族へフォールバックしない。
    const passed = primary.length > 0 && (primary.length === 1
      ? exact.length + bridged.length === 1
      : exact.length >= Math.min(2, primary.length))
    return { parentId, anchors: primary, exact, bridged, passed }
  })
}

function evaluateFusionDerivation(
  profile: GenerationProfile,
  candidate: NonNullable<ReturnType<typeof generateLiveProblem>>,
): FusionDerivation {
  const parentSets = profile.parentAnchorSets ?? []
  if (profile.mode !== 'fusion' || parentSets.length < 2) {
    return { passed: true, reason: 'single-parent generation', assignments: [], bridges: [], ablationPassed: true }
  }

  const contract = candidate.structureBlueprint?.fusionContract
  if (!contract) {
    return { passed: false, reason: 'candidate has no fusion contract', assignments: [], bridges: [], ablationPassed: false }
  }
  const chain = new Set(candidate.morphismChain)
  const requiredPortIds = [...new Set(contract.bridges.flatMap(bridge => bridge.consumes))]
  const requiredPorts = requiredPortIds.map(id => contract.ports.find(port => port.id === id)).filter(Boolean)
  if (requiredPorts.length !== requiredPortIds.length || requiredPorts.length !== parentSets.length) {
    return { passed: false, reason: 'fusion arity does not equal selected parent count', assignments: [], bridges: [], ablationPassed: false }
  }
  if (contract.bridges.some(bridge => !chain.has(bridge.witnessStep))) {
    return { passed: false, reason: 'bridge witness is absent from proof chain', assignments: [], bridges: [], ablationPassed: false }
  }
  if (requiredPorts.some(port => !port!.witnessSteps.every(step => chain.has(step)))) {
    return { passed: false, reason: 'input-port witness is absent from proof chain', assignments: [], bridges: [], ablationPassed: false }
  }

  const options = parentSets.map(parent => requiredPorts.map((port, portIndex) => ({
    portIndex,
    matchedAnchors: parent.anchors.filter(anchor => port!.accepts.includes(anchor)),
  })).filter(option => option.matchedAnchors.length > 0))
  if (options.some(parentOptions => parentOptions.length === 0)) {
    return { passed: false, reason: 'a selected parent cannot fill any proof input port', assignments: [], bridges: [], ablationPassed: false }
  }

  let best: Array<{ parentIndex: number; portIndex: number; matchedAnchors: string[] }> | null = null
  let bestScore = -1
  const search = (
    parentIndex: number,
    usedPorts: Set<number>,
    current: Array<{ parentIndex: number; portIndex: number; matchedAnchors: string[] }>,
  ) => {
    if (parentIndex === parentSets.length) {
      const score = current.reduce((sum, item) => sum + item.matchedAnchors.length, 0)
      if (score > bestScore) {
        bestScore = score
        best = [...current]
      }
      return
    }
    for (const option of options[parentIndex]) {
      if (usedPorts.has(option.portIndex)) continue
      usedPorts.add(option.portIndex)
      current.push({ parentIndex, ...option })
      search(parentIndex + 1, usedPorts, current)
      current.pop()
      usedPorts.delete(option.portIndex)
    }
  }
  search(0, new Set(), [])
  if (!best) {
    return { passed: false, reason: 'parents cannot be assigned to distinct proof ports', assignments: [], bridges: [], ablationPassed: false }
  }

  const assignments = (best as Array<{ parentIndex: number; portIndex: number; matchedAnchors: string[] }>).map(item => {
    const port = requiredPorts[item.portIndex]!
    return {
      parentId: parentSets[item.parentIndex].parentId,
      portId: port.id,
      role: port.role,
      matchedAnchors: item.matchedAnchors,
      witnessSteps: port.witnessSteps,
    }
  })
  const roles = new Set(assignments.map(assignment => assignment.role))
  const allPortsConsumed = assignments.every(assignment =>
    contract.bridges.some(bridge => bridge.consumes.includes(assignment.portId)),
  )
  const ablationPassed = allPortsConsumed && assignments.length === requiredPortIds.length
  const passed = roles.size >= 2 && ablationPassed
  return {
    passed,
    reason: passed ? 'all parents occupy distinct indispensable proof ports' : 'parent contributions are not structurally distinct',
    assignments,
    bridges: contract.bridges,
    ablationPassed,
  }
}

function parentAnchorTags(parent: ParentInput): string[] {
  const statementTags = inferTags(parent.statement ?? '')
  const solutionTags = inferTags([
    parent.solution,
    parent.inspiration,
    typeof parent.meta === 'string' ? parent.meta : JSON.stringify(parent.meta ?? {}),
  ].filter(Boolean).join(' ')).filter(tag => SOLUTION_CORE_TAGS.has(tag))
  const candidates = [...new Set([...statementTags, ...solutionTags])]
    .filter(tag => !QUERY_TAGS.has(tag))
  const specific = candidates.filter(tag => !FUSION_GENERIC_TAGS.has(tag))
  return specific.length ? specific : candidates
}

/**
 * 融合は全親のタグをAND結合しない。各親をチャートとして持ち上げ、Atlas上で
 * 最短経路が存在する親ペアだけを候補にする。接続不能な親は後段の単独修復へ回す。
 */
function buildFusionProfiles(parents: ParentInput[], fallbackDomain?: string): GenerationProfile[] {
  const singles = parents.map(parent => buildGenerationProfile(
    [parent],
    parent.topic_a || fallbackDomain,
    'similar',
  ))
  const anchorSets = parents.map((parentInput, index) => {
    const anchors = parentAnchorTags(parentInput)
    if (anchors.length) return anchors
    const fallback = singles[index].tags.filter(tag => !QUERY_TAGS.has(tag))
    const specific = fallback.filter(tag => !FUSION_GENERIC_TAGS.has(tag))
    return (specific.length ? specific : fallback).slice(0, 1)
  })
  const pairProfiles: Array<GenerationProfile & { pathLength: number; leftIndex: number; rightIndex: number }> = []

  for (let leftIndex = 0; leftIndex < singles.length; leftIndex++) {
    for (let rightIndex = leftIndex + 1; rightIndex < singles.length; rightIndex++) {
      const left = singles[leftIndex]
      const right = singles[rightIndex]
      const leftTags = anchorSets[leftIndex]
      const rightTags = anchorSets[rightIndex]
      let bestPath: string[] | null = null
      for (const leftTag of leftTags) {
        for (const rightTag of rightTags) {
          const path = shortestAtlasPath(leftTag, rightTag, 4)
          if (path && (!bestPath || path.length < bestPath.length)) bestPath = path
        }
      }
      if (!bestPath) continue

      const pairParents = [parents[leftIndex], parents[rightIndex]]
      const base = buildGenerationProfile(pairParents, fallbackDomain, 'fusion')
      pairProfiles.push({
        ...base,
        tags: [...new Set([...left.tags, ...right.tags, ...bestPath])],
        requiredTags: [...new Set([bestPath[0], bestPath.at(-1)!])],
        queryTags: [...new Set([...left.queryTags, ...right.queryTags])],
        parentIds: [...new Set([...left.parentIds, ...right.parentIds])],
        atlasPath: bestPath,
        pathLength: bestPath.length - 1,
        leftIndex,
        rightIndex,
      })
    }
  }

  pairProfiles.sort((a, b) => a.pathLength - b.pathLength || b.tags.length - a.tags.length)

  // Kruskal法で、選択された全親を結ぶ最小Atlas中継網を作る。
  const parent = singles.map((_, index) => index)
  const find = (index: number): number => {
    let cursor = index
    while (parent[cursor] !== cursor) cursor = parent[cursor]
    while (parent[index] !== index) {
      const next = parent[index]
      parent[index] = cursor
      index = next
    }
    return cursor
  }
  const treeEdges: typeof pairProfiles = []
  for (const edge of pairProfiles) {
    const leftRoot = find(edge.leftIndex)
    const rightRoot = find(edge.rightIndex)
    if (leftRoot === rightRoot) continue
    parent[leftRoot] = rightRoot
    treeEdges.push(edge)
    if (treeEdges.length === singles.length - 1) break
  }

  const scaffold: GenerationProfile[] = []
  if (singles.length > 1) {
    const base = buildGenerationProfile(parents, fallbackDomain, 'fusion')
    const atlasPaths = treeEdges.map(edge => edge.atlasPath!).filter(Boolean)
    const fullyConnected = treeEdges.length === singles.length - 1
    const parentAnchors = fullyConnected
      ? [...new Set(atlasPaths.flatMap(path => [path[0], path.at(-1)!]))]
      : []
    scaffold.push({
      ...base,
      tags: [...new Set([...singles.flatMap(profile => profile.tags), ...atlasPaths.flat()])],
      requiredTags: parentAnchors,
      queryTags: [...new Set(singles.flatMap(profile => profile.queryTags))],
      parentIds: [...new Set(singles.flatMap(profile => profile.parentIds))],
      atlasPaths,
      parentAnchors,
      parentAnchorSets: parents.map((parentInput, index) => ({
        parentId: parentInput.id ?? `parent-${index + 1}`,
        anchors: anchorSets[index],
      })),
      allParentScaffold: true,
    })
  }
  return scaffold
}

/** 構築・条件の数から難易度帯を見積もる（world_novelty_check.py と同じ考え方） */
function gradeDifficulty(statement: string, solution: string) {
  const construct = (statement.match(/定める|定義|とする|とおく|次のように|与えられ/g) ?? []).length
  const condition = (statement.match(/かつ|満たす|ならば|に対して|任意の|存在|相異なる/g) ?? []).length
  const len = canonical(statement).length
  const depth = (solution.match(/より|したがって|よって|定理|公式|変換|置換/g) ?? []).length
  const score = 2.5 * construct + 2.0 * condition + Math.min(len / 50, 8) + depth
  const band =
    construct === 0 && condition <= 1 && len < 120 ? 'D_textbook'
    : score >= 14 ? 'A_olympiad'
    : score >= 8 ? 'B_hard_university'
    : score >= 4.5 ? 'C_standard_university'
    : 'D_textbook'
  return { band, score: Number(score.toFixed(2)), construct, condition }
}

type GenerationResult = {
  generated: number
  requested: number
  engine: string
  cards: Record<string, unknown>[]
  errors: string[]
  rejectionCounts?: Record<string, number>
  discoveryQueued?: boolean
  discoveryJobId?: string
  generalization?: GeneralizationCertificate
}

async function enqueueParentConditionedDiscovery(
  result: GenerationResult,
  parents: ParentInput[],
  count: number,
  mode: GenerationProfile['mode'],
): Promise<GenerationResult> {
  if (mode !== 'fusion' || result.generated > 0 || parents.length < 2) return result
  const { data, error } = await getSupabaseAdmin().functions.invoke('enqueue-generation', {
    body: {
      parents,
      mode: 'mathos_discovery',
      count: Math.max(1, Math.min(count, 10)),
    },
  })
  if (!error && data?.job_id) {
    return {
      ...result,
      discoveryQueued: true,
      discoveryJobId: String(data.job_id),
      errors: result.errors.filter(message => !message.startsWith('全親を不可欠な証明入力')),
    }
  }

  // The scheduled no-LLM research worker can start directly from this row.
  // This keeps generation alive even when the optional Edge dispatcher is unavailable.
  const fallbackJobId = crypto.randomUUID()
  const now = new Date().toISOString()
  const { error: fallbackError } = await getSupabaseAdmin().from('generation_jobs').insert({
    id: fallbackJobId,
    status: 'processing',
    parents,
    mode: 'mathos_discovery',
    count: Math.max(1, Math.min(count, 10)),
    logs: [{
      level: 'info',
      message: 'Edge dispatcherを迂回し、MathOS定期研究キューへ直接登録しました。',
      ts: now,
    }],
    result: {
      engine: 'MathOS scheduled structural discovery (no LLM)',
      generated: 0,
      requested: count,
      cards: [],
      errors: [],
      backgroundResearch: true,
      searchState: { continuing: true, next_attempt_at: null },
    },
    error: null,
    model: 'mathos-autonomous-structural-search-no-llm',
    updated_at: now,
  })
  if (fallbackError) {
    return {
      ...result,
      errors: [
        ...result.errors,
        `未知構造探索ジョブを保存できませんでした: ${fallbackError.message}`,
      ],
    }
  }
  return {
    ...result,
    discoveryQueued: true,
    discoveryJobId: fallbackJobId,
    errors: result.errors.filter(message => !message.startsWith('全親を不可欠な証明入力')),
  }
}

type ProgressEvent = {
  phase: 'start' | 'searching' | 'inducing' | 'registering' | 'structuring' | 'novelty' | 'verifying' | 'saving' | 'complete' | 'error'
  message: string
  current: number
  total: number
  draft?: string
  familyId?: string
  morphisms?: string[]
  similarity?: number
  structureId?: string
  structureStatus?: 'new' | 'reused' | 'pending'
}

type ProgressEmitter = (event: ProgressEvent) => void

type RegisteredStructure = {
  blueprint: StructureBlueprint | {
    id: string
    version: 1
    kernel: 'unresolved_parent_structure'
    observable: string
    operators: string[]
    domain: string
    tags: string[]
    morphismChain: string[]
    executable: false
  }
  status: 'new' | 'reused' | 'pending'
  parentIds: string[]
  registeredAt: string
}

function stableStructureId(profile: GenerationProfile): string {
  const source = [...profile.requiredTags, ...profile.queryTags, profile.domain ?? 'unknown'].sort().join('|')
  let hash = 2166136261
  for (let index = 0; index < source.length; index++) {
    hash ^= source.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `pending.${(hash >>> 0).toString(36)}`
}

async function loadRegisteredStructureIds(): Promise<Set<string>> {
  const { data } = await getSupabaseAdmin()
    .from('generation_jobs')
    .select('result')
    .eq('status', 'done')
    .not('result', 'is', null)
    .order('created_at', { ascending: false })
    .limit(100)
  const ids = new Set<string>()
  for (const row of (data ?? []) as Array<{ result?: { structures?: RegisteredStructure[] } | null }>) {
    for (const structure of row.result?.structures ?? []) {
      if (structure.status !== 'pending') ids.add(structure.blueprint.id)
    }
  }
  return ids
}

async function generateCards(
  count: number,
  profiles: GenerationProfile[],
  searchDepth: 'standard' | 'deep',
  searchBudgetSeconds: number,
  emit: ProgressEmitter = () => undefined,
): Promise<GenerationResult> {
  const cards: Record<string, unknown>[] = []
  const errors: string[] = []
  const structures: RegisteredStructure[] = []
  const rejectionCounts: Record<string, number> = {}
  const reject = (reason: string) => {
    rejectionCounts[reason] = (rejectionCounts[reason] ?? 0) + 1
  }
  const sessionLogs: Array<{ phase: string; message: string; ts: string }> = []
  const seenFamilies = new Set<string>()
  const seenObservables = new Set<string>()
  const selectedCandidateKeys = new Set<string>()
  const seenStructureIds = new Set<string>()
  const jobId = crypto.randomUUID()
  let jobWritable = true
  const report: ProgressEmitter = event => {
    sessionLogs.push({ phase: event.phase, message: event.message, ts: new Date().toISOString() })
    emit(event)
  }
  const [corpus, registeredStructureIds] = await Promise.all([
    loadNoveltyCorpus(),
    loadRegisteredStructureIds(),
  ])
  const hasAllParentScaffold = profiles[0]?.allParentScaffold === true
  // 全親を結ぶ scaffold がある融合では、pair/single fallback へ切り替えない。
  // それを許すと、選択していない構造族の問題を「融合結果」として返してしまう。
  const isBatch = profiles.length > 1 && !hasAllParentScaffold
  const attemptsPerProfile = isBatch ? 2_000 : searchDepth === 'deep' ? 2_000_000 : 500_000
  const maxAttempts = isBatch
    ? Math.min(20_000, Math.max(1_000, profiles.length * attemptsPerProfile))
    : attemptsPerProfile
  const deadline = Date.now() + searchBudgetSeconds * 1000
  const firstProfile = profiles[0] ?? buildGenerationProfile([])
  const focusLabel = hasAllParentScaffold
    ? `${firstProfile.parentIds.length} 個の選択問題を結ぶAtlas中継網`
    : profiles.length > 1
      ? `${profiles.length} 個の親構造を個別探索`
    : firstProfile.tags.slice(0, 5).join(' / ') || firstProfile.domain || 'all'
  const requiredLabel = profiles.length === 1 && firstProfile.requiredTags.length
    ? ` / 継承: ${firstProfile.requiredTags.join(' + ')}`
    : ''

  const { error: jobError } = await getSupabaseAdmin().from('generation_jobs').insert({
    id: jobId,
    status: 'processing',
    parents: profiles.map(profile => ({
      parentIds: profile.parentIds,
      tags: profile.tags,
      requiredTags: profile.requiredTags,
      queryTags: profile.queryTags,
      atlasPath: profile.atlasPath,
      atlasPaths: profile.atlasPaths,
      parentAnchors: profile.parentAnchors,
      parentAnchorSets: profile.parentAnchorSets,
      allParentScaffold: profile.allParentScaffold ?? false,
      recovery: profile.recovery ?? false,
    })),
    mode: firstProfile.mode,
    count,
    logs: [],
    result: { phase: 'started', structures: [] },
    model: 'mathos-typed-structure-dsl-v1',
    updated_at: new Date().toISOString(),
  })
  if (jobError) jobWritable = false

  report({
    phase: 'start',
    message: `MathOS が${searchDepth === 'deep' ? '深層' : '標準'}探索を開始（最大${searchBudgetSeconds}秒）: ${focusLabel}${requiredLabel}`,
    current: 0,
    total: count,
  })

  for (let i = 0; i < count; i++) {
    const current = i + 1
    let profileIndex = hasAllParentScaffold ? 0 : i % profiles.length
    let profile = profiles[profileIndex] ?? firstProfile
    report({
      phase: 'searching',
      message: `問題 ${current}/${count}: Task Atlas から構成可能な経路を探索`,
      current,
      total: count,
    })

    // 前半は未使用の構造族だけを探索し、数字替えより構造多様性を優先する。
    // 後半だけ同族の別パラメータを許し、要求数を満たせる可能性を残す。
    let live: ReturnType<typeof generateLiveProblem> = null
    let sim: ReturnType<typeof assessNovelty> | null = null
    let inheritedTags: string[] = []
    let bridgedTags: string[] = []
    let selectedParentCoverage: ParentCoverage[] = []
    let selectedFusionDerivation: FusionDerivation | null = null
    let hypothesesEvaluated = 0
    let validHypotheses = 0
    let bestCandidateScore = Number.NEGATIVE_INFINITY
    const cardSeenCandidates = new Set<string>()
    const cardSearchStartedAt = Date.now()
    const targetCardMillis = searchBudgetSeconds * 1000 / Math.max(1, count)
    const minimumSearchEnd = searchDepth === 'deep'
      ? Math.min(deadline, cardSearchStartedAt + Math.max(8_000, targetCardMillis * 0.67))
      : cardSearchStartedAt
    const minimumHypotheses = searchDepth === 'deep' ? 300 : 60
    for (let attempt = 0; attempt < maxAttempts && Date.now() < deadline; attempt++) {
      if (Date.now() >= minimumSearchEnd && hypothesesEvaluated >= minimumHypotheses && live) break
      if (isBatch && attempt > 0 && attempt % attemptsPerProfile === 0) {
        profileIndex = (profileIndex + 1) % profiles.length
        profile = profiles[profileIndex] ?? firstProfile
        report({
          phase: 'searching',
          message: profile.recovery
            ? `問題 ${current}/${count}: 接続不能な全親融合をやめ、単独親チャートから再lift`
            : `問題 ${current}/${count}: Atlas中継網 ${profile.atlasPaths?.map(path => path.join(' → ')).join(' / ') || profile.atlasPath?.join(' → ') || '直接同型'} へ探索を切替`,
          current,
          total: count,
        })
      }
      if (attempt > 0 && attempt % 25_000 === 0) {
        report({
          phase: 'searching',
          message: `問題 ${current}/${count}: ${hypothesesEvaluated} 個の中間仮説を検査。全親の構造署名を保ったまま探索を継続`,
          current,
          total: count,
        })
      }
      const candidate = generateLiveProblem({
        domain: profile.domain,
        focusTags: expandedFocusTags(profile.tags),
        avoidQueryTags: profile.queryTags,
        excludedFamilies: attempt < Math.floor(maxAttempts * 0.6) ? [...seenFamilies] : [],
        excludedObservables: attempt < Math.floor(maxAttempts * 0.85) ? [...seenObservables] : [],
        preferDepth: searchDepth === 'deep',
      })
      if (!candidate) {
        reject('no_executable_candidate')
        continue
      }
      hypothesesEvaluated++
      const candidateKey = `${candidate.familyId}\u0000${canonical(candidate.statementTex)}`
      if (selectedCandidateKeys.has(candidateKey) || cardSeenCandidates.has(candidateKey)) {
        reject('duplicate_candidate')
        continue
      }
      cardSeenCandidates.add(candidateKey)

      const candidateTags = inferTags([
        candidate.familyId,
        candidate.domain,
        candidate.statementTex,
        candidate.solutionTex,
        candidate.tool,
        candidate.verificationMethod,
        candidate.morphismChain.join(' '),
        candidate.structureBlueprint?.tags.join(' '),
      ].join(' '))
      for (const tag of candidate.structureBlueprint?.tags ?? []) {
        if (!candidateTags.includes(tag)) candidateTags.push(tag)
      }
      const profileAttempt = isBatch ? attempt % attemptsPerProfile : attempt
      const requiredCount = ['similar', 'expand', 'fusion'].includes(profile.mode)
        ? profile.requiredTags.length
        : profileAttempt < Math.floor(attemptsPerProfile * 0.55)
        ? profile.requiredTags.length
        : profileAttempt < Math.floor(attemptsPerProfile * 0.8)
          ? Math.min(profile.requiredTags.length, 2)
          : Math.min(profile.requiredTags.length, 1)
      const attemptRequiredTags = profile.requiredTags.slice(0, requiredCount)
      const candidateObservable = candidate.structureBlueprint?.observable ?? ''
      const changesQuery = profile.queryTags.length === 0 || profile.queryTags.every(tag =>
        !candidateObservable.includes(tag) && !tag.includes(candidateObservable),
      )
      const requireQueryChange = profile.queryTags.length > 0 &&
        profileAttempt < Math.floor(attemptsPerProfile * 0.85)
      const preservesRequiredStructure = profile.mode === 'similar' || profile.mode === 'expand' || profile.mode === 'fusion'
        ? attemptRequiredTags.every(tag => preservedByAtlas(tag, candidateTags))
        : attemptRequiredTags.some(tag => preservedByAtlas(tag, candidateTags))
      if ((attemptRequiredTags.length && !preservesRequiredStructure) || (requireQueryChange && !changesQuery)) {
        reject(!preservesRequiredStructure ? 'required_structure_mismatch' : 'query_not_transformed')
        continue
      }
      const parentCoverage = evaluateParentCoverage(profile, candidateTags)
      if (parentCoverage.some(coverage => !coverage.passed)) {
        reject('parent_signature_mismatch')
        continue
      }
      const fusionDerivation = evaluateFusionDerivation(profile, candidate)
      if (!fusionDerivation.passed) {
        reject(`fusion:${fusionDerivation.reason}`)
        continue
      }

      const blueprint = candidate.structureBlueprint
      if (blueprint && !seenStructureIds.has(blueprint.id)) {
        seenStructureIds.add(blueprint.id)
        const status = registeredStructureIds.has(blueprint.id) ? 'reused' : 'new'
        const structure: RegisteredStructure = {
          blueprint,
          status,
          parentIds: profile.parentIds,
          registeredAt: new Date().toISOString(),
        }
        structures.push(structure)
        report({
          phase: 'inducing',
          message: `${blueprint.kernel} から観測 ${blueprint.observable} への型付き射列を合成`,
          current,
          total: count,
          draft: candidate.statementTex,
          familyId: candidate.familyId,
          morphisms: candidate.morphismChain,
          structureId: blueprint.id,
          structureStatus: status,
        })
        report({
          phase: 'registering',
          message: status === 'new'
            ? `新しい実行可能構造 ${blueprint.id} をDBへ登録`
            : `登録済み構造 ${blueprint.id} をDBから再利用`,
          current,
          total: count,
          draft: candidate.statementTex,
          familyId: candidate.familyId,
          morphisms: candidate.morphismChain,
          structureId: blueprint.id,
          structureStatus: status,
        })
        if (jobWritable) {
          const { error } = await getSupabaseAdmin().from('generation_jobs').update({
            logs: sessionLogs,
            result: { phase: 'registering', structures },
            updated_at: new Date().toISOString(),
          }).eq('id', jobId)
          if (error) jobWritable = false
        }
      }

      report({
        phase: 'structuring',
        message: `${candidate.familyId}: 選択問題の ${attemptRequiredTags.join(' / ') || profile.domain || '構造'} を保ち、${candidate.morphismChain.length} 本の射を構成`,
        current,
        total: count,
        draft: candidate.statementTex,
        familyId: candidate.familyId,
        morphisms: candidate.morphismChain,
      })

      const s = assessNovelty(
        candidate.statementTex,
        candidate.familyId,
        candidate.answerTex,
        corpus,
      )
      if (!s.duplicate) {
        validHypotheses++
        const exactCoverage = parentCoverage.reduce((sum, coverage) => sum + coverage.exact.length, 0)
        const bridgedCoverage = parentCoverage.reduce((sum, coverage) => sum + coverage.bridged.length, 0)
        const candidateScore = exactCoverage * 12 + bridgedCoverage * 2 +
          Math.min(candidate.morphismChain.length, 30) * 0.2 + (1 - s.score) * 4
        if (candidateScore > bestCandidateScore) {
          bestCandidateScore = candidateScore
          live = candidate
          sim = s
          selectedParentCoverage = parentCoverage
          selectedFusionDerivation = fusionDerivation
          inheritedTags = attemptRequiredTags.filter(tag => candidateTags.includes(tag))
          bridgedTags = attemptRequiredTags.filter(tag =>
            !candidateTags.includes(tag) && preservedByAtlas(tag, candidateTags),
          )
          report({
            phase: 'novelty',
            message: `中間仮説 ${hypothesesEvaluated}: 全親を別々の証明入力へ割当。既存 ${s.comparedAgainst} 問との最大表層類似度 ${(s.score * 100).toFixed(0)}%`,
            current,
            total: count,
            draft: candidate.statementTex,
            familyId: candidate.familyId,
            morphisms: candidate.morphismChain,
            similarity: s.score,
          })
        }
      }
    }
    if (!live || !sim) {
      const pendingId = stableStructureId(profile)
      if (!seenStructureIds.has(pendingId)) {
        seenStructureIds.add(pendingId)
        structures.push({
          blueprint: {
            id: pendingId,
            version: 1,
            kernel: 'unresolved_parent_structure',
            observable: profile.queryTags[0] ?? 'unknown',
            operators: [],
            domain: profile.domain ?? 'unknown',
            tags: profile.requiredTags,
            morphismChain: [],
            executable: false,
          },
          status: 'pending',
          parentIds: profile.parentIds,
          registeredAt: new Date().toISOString(),
        })
      }
      const topReasons = Object.entries(rejectionCounts)
        .sort((left, right) => right[1] - left[1])
        .slice(0, 3)
        .map(([reason, occurrences]) => `${reason}=${occurrences}`)
        .join(', ')
      const message = `全親を不可欠な証明入力にできる候補がありません。${pendingId} を検証キューへ隔離しました${topReasons ? `（${topReasons}）` : ''}`
      errors.push(message)
      report({ phase: 'registering', message, current, total: count, structureId: pendingId, structureStatus: 'pending' })
      continue
    }

    seenFamilies.add(live.familyId)
    if (live.structureBlueprint) seenObservables.add(live.structureBlueprint.observable)
    selectedCandidateKeys.add(`${live.familyId}\u0000${canonical(live.statementTex)}`)
    const elapsedSearchMs = Date.now() - cardSearchStartedAt

    report({
      phase: 'verifying',
      message: `${live.verificationMethod}: 厳密解と独立検算の証明書を確認`,
      current,
      total: count,
      draft: live.statementTex,
      familyId: live.familyId,
      morphisms: live.morphismChain,
    })

    const diff = gradeDifficulty(live.statementTex, live.solutionTex)

    // 問題カードとして保存（LLM 不使用・検証済み・類似度は実測）
    const shortId = Math.random().toString(36).slice(2, 12)
    const id = `mathos-live-${shortId}`
    const diagram = buildProblemDiagram({
      familyId: live.familyId,
      domain: live.domain,
      parameters: live.parameters,
      morphismChain: live.morphismChain,
      calculusAnalysis: live.calculusAnalysis,
    })
    const meta = {
      shortId,
      familyId: live.familyId,
      tool: live.tool,
      parameters: live.parameters,
      diagram,
      calculusAnalysis: live.calculusAnalysis,
      morphismChain: live.morphismChain,
      verificationMethod: live.verificationMethod,
      difficulty: diff,
      similarity: sim,
      generatedBy: 'mathos_live',
      searchDepth,
      parentContext: {
        parentIds: profile.parentIds,
        focusTags: profile.tags,
        requestedTags: profile.requiredTags,
        inheritedTags,
        bridgedTags,
        unmappedTags: profile.requiredTags.filter(tag =>
          !inheritedTags.includes(tag) && !bridgedTags.includes(tag),
        ),
        parentCoverage: selectedParentCoverage,
        fusionDerivation: selectedFusionDerivation,
      },
      searchEvidence: { hypothesesEvaluated, validHypotheses, elapsedSearchMs, bestCandidateScore },
      structureBlueprint: live.structureBlueprint,
      atlasExpansion: bridgedTags.length > 0 || inheritedTags.length < profile.requiredTags.length,
    }

    report({
      phase: 'saving',
      message: `検証済み問題をライブラリへ保存`,
      current,
      total: count,
      draft: live.statementTex,
      familyId: live.familyId,
      morphisms: live.morphismChain,
    })

    const { error } = await getSupabaseAdmin().from('problems').upsert(
      {
        id,
        topic_a: live.domain,
        topic_b: live.familyId,
        variation: 0,
        statement: live.statementTex,
        answer: live.answerTex,
        difficulty: diff.band.startsWith('A') ? 'A' : diff.band.startsWith('B') ? 'B' : 'C',
        solution: live.solutionTex,
        surprise: 8, minimality: 7, connection: 8, inevitability: 8, diff_cal: 7,
        total: Math.min(10, 6 + diff.score / 5),
        inspiration: live.morphismChain.join(' → '),
        meta: JSON.stringify(meta),
        generation: 0,
        parent_ids: profile.parentIds,
        source_file: 'mathos_live_session',
      },
      { onConflict: 'id' },
    )
    if (error) {
      const message = `保存失敗: ${error.message}`
      errors.push(message)
      report({ phase: 'error', message, current, total: count })
      continue
    }

    const card = {
      id,
      statement_tex: live.statementTex,
      answer_tex: live.answerTex,
      solution_tex: live.solutionTex,
      parameters: live.parameters,
      diagram,
      calculus_analysis: live.calculusAnalysis,
      domain: live.domain,
      family_id: live.familyId,
      tool: live.tool,
      morphism_chain: live.morphismChain,
      verification: { method: live.verificationMethod, exact_backend: true, independent_check: true },
      difficulty: diff,
      similarity: sim,
      inherited_tags: inheritedTags,
      bridged_tags: bridgedTags,
      unmapped_tags: profile.requiredTags.filter(tag =>
        !inheritedTags.includes(tag) && !bridgedTags.includes(tag),
      ),
      atlas_expansion: bridgedTags.length > 0 || inheritedTags.length < profile.requiredTags.length,
      structure_blueprint: live.structureBlueprint,
      parent_ids: profile.parentIds,
      parent_coverage: selectedParentCoverage,
      fusion_derivation: selectedFusionDerivation,
      search_evidence: { hypotheses_evaluated: hypothesesEvaluated, valid_hypotheses: validHypotheses, elapsed_ms: elapsedSearchMs },
    }
    cards.push(card)
    addToNoveltyCorpus(corpus, live.statementTex, live.familyId, live.answerTex, id)
    report({
      phase: 'complete',
      message: `問題 ${current}/${count} を生成・検証・保存しました`,
      current,
      total: count,
      draft: live.statementTex,
      familyId: live.familyId,
      morphisms: live.morphismChain,
    })
  }

  const result = {
    generated: cards.length,
    requested: count,
    engine: `MathOS structural live (${searchDepth}, no LLM)`,
    cards,
    errors,
    rejectionCounts,
  }
  if (jobWritable) {
    await getSupabaseAdmin().from('generation_jobs').update({
      status: cards.length > 0 ? 'done' : 'failed',
      logs: sessionLogs,
      result: { ...result, structures },
      error: cards.length > 0 ? null : errors.join(' / '),
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)
  }
  return result
}

export async function POST(request: NextRequest) {
  let count = 1
  let domain: string | undefined
  let stream = false
  let parents: ParentInput[] = []
  let searchDepth: 'standard' | 'deep' = 'deep'
  let searchBudgetSeconds = 90
  let mode: GenerationProfile['mode'] = 'batch'
  try {
    const body = await request.json()
    count = Math.min(Math.max(Number(body?.count ?? 1), 1), 10)
    domain = body?.domain || undefined
    stream = body?.stream === true
    parents = Array.isArray(body?.parents)
      ? body.parents.filter((parent: unknown): parent is ParentInput => Boolean(parent) && typeof parent === 'object').slice(0, 250)
      : []
    searchDepth = body?.searchDepth === 'standard' ? 'standard' : 'deep'
    searchBudgetSeconds = Math.min(Math.max(Number(body?.searchBudgetSeconds ?? (searchDepth === 'deep' ? 90 : 30)), 20), 180)
    mode = ['similar', 'fusion', 'expand'].includes(body?.mode) ? body.mode : 'batch'
  } catch {
    // 既定値で続行
  }

  if (mode === 'fusion' && parents.length < 2) {
    return NextResponse.json(
      { generated: 0, requested: count, cards: [], errors: ['融合生成には2問以上の親問題が必要です'] },
      { status: 400 },
    )
  }
  if (mode === 'fusion') {
    const parentIds = parents.map(parent => parent.id?.trim()).filter(Boolean) as string[]
    if (parentIds.length !== parents.length || new Set(parentIds).size !== parents.length) {
      return NextResponse.json(
        { generated: 0, requested: count, cards: [], errors: ['融合対象の親IDが欠落または重複しています'] },
        { status: 400 },
      )
    }
    if (parents.some(parent => !parent.statement?.trim())) {
      return NextResponse.json(
        { generated: 0, requested: count, cards: [], errors: ['融合対象の問題本文が取得できていません'] },
        { status: 400 },
      )
    }
  }

  const shuffledParents = [...parents]
  // 融合時はUIで選択した順序を監査ログまで保つ。ランダム化は一括類題だけに限る。
  if (mode !== 'fusion') {
    for (let i = shuffledParents.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[shuffledParents[i], shuffledParents[j]] = [shuffledParents[j], shuffledParents[i]]
    }
  }
  const profiles = mode === 'batch' && shuffledParents.length > 0
    ? shuffledParents.map(parent => {
        return buildGenerationProfile([parent], parent.topic_a || domain, 'similar')
      })
    : mode === 'fusion' && shuffledParents.length > 1
      ? buildFusionProfiles(shuffledParents, domain)
      : [buildGenerationProfile(parents, domain, mode)]
  const generalization = parents.length
    ? generalizeParents(
        parents,
        searchDepth === 'deep' ? 8 : 4,
        Math.max(10_000, searchBudgetSeconds * 1_000),
      ).certificate
    : undefined
  // A fusion request first receives the same bounded executable search as the
  // other modes. Only an actually unsolved endpoint pair is handed to the
  // persistent discovery worker; known executable kernels must not be skipped.
  const needsStructuralDiscovery = profiles.length === 0

  const attachGeneralization = (result: GenerationResult): GenerationResult => ({
    ...result,
    generalization,
  })

  if (!stream) {
    const generated = needsStructuralDiscovery
      ? {
          generated: 0,
          requested: count,
          engine: 'MathOS parent-conditioned structural search',
          cards: [],
          errors: [generalization?.target_sort
            ? '共同型経路を初期frontierとして、選択端点から実行プログラムを合成します'
            : '既存の共同射ではなく、選択端点から中間構造を自己拡張探索します'],
        }
      : await generateCards(count, profiles, searchDepth, searchBudgetSeconds)
    const result = await enqueueParentConditionedDiscovery(
      attachGeneralization(generated),
      parents,
      count,
      mode,
    )
    return NextResponse.json(result)
  }

  const encoder = new TextEncoder()
  const responseStream = new ReadableStream({
    async start(controller) {
      const send = (event: ProgressEvent | { phase: 'done'; result: GenerationResult }) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      try {
        const generated = needsStructuralDiscovery
          ? (() => {
              send({
                phase: 'inducing',
                message: generalization?.target_sort
                  ? '選択した全親を固定端点とし、長時間workerで中間射と実行プログラムを合成します'
                  : '固定端点の間に既知の共同射がないため、中間構造の自己拡張探索へ移行します',
                current: 0,
                total: count,
              })
              return {
                generated: 0,
                requested: count,
                engine: 'MathOS parent-conditioned structural search',
                cards: [],
                errors: ['選択端点から中間構造と実行プログラムを自己拡張探索中'],
              }
            })()
          : await generateCards(count, profiles, searchDepth, searchBudgetSeconds, send)
        const result = await enqueueParentConditionedDiscovery(
          attachGeneralization(generated),
          parents,
          count,
          mode,
        )
        send({ phase: 'done', result })
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        send({
          phase: 'error',
          message,
          current: 0,
          total: count,
        })
        send({
          phase: 'done',
          result: attachGeneralization({
            generated: 0,
            requested: count,
            engine: 'MathOS structural live (no LLM)',
            cards: [],
            errors: [message],
          }),
        })
      } finally {
        controller.close()
      }
    },
  })

  return new Response(responseStream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}

export async function GET() {
  return NextResponse.json({
    engine: 'MathOS live (no LLM)',
    pool_bundled: POOL.length,
    usage: 'POST { count?: 1-10, domain?: string, parents?: Parent[], mode?: similar|fusion|expand|batch, searchDepth?: standard|deep, searchBudgetSeconds?: 20-180, stream?: boolean }',
  })
}
