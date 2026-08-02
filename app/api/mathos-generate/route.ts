import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { generateLiveProblem, type StructureBlueprint } from '@/lib/mathos-live'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 300

/**
 * MathOS 作問セッション — LLM を使わない。
 *
 * その場で対象を構築し（ライブ生成）、答えをツールで計算・独立検証し、
 * 既存問題との類似度を実際に計算して問題カードとして保存する。
 * DeepSeek 等の外部 LLM API は一切使わないので残高切れで止まらない。
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
  const { data } = await supabaseAdmin
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
  mode: 'similar' | 'fusion' | 'expand' | 'batch'
}

const QUERY_TAGS = new Set([
  'area', 'volume', 'radius_ratio', 'radius_product', 'circumradius',
  'curvature', 'center_distance', 'reciprocal_invariant', 'limit',
])

// 直接一致しないときも、Atlas上で意味のある隣接射だけを許す。遠距離ジャンプはしない。
const EXECUTABLE_TAG_BRIDGES: Record<string, string[]> = {
  centroid: ['triangle', 'circle_centers'],
  circle_centers: ['triangle'],
  heron: ['triangle', 'symmetric_polynomial'],
  tangent: ['parabola', 'locus'],
  intersection: ['polynomial_roots', 'algebra'],
  envelope: ['locus', 'passage_region', 'parabola'],
  locus: ['passage_region', 'parabola'],
  minkowski_sum: ['passage_region', 'disk'],
  polynomial_roots: ['symmetric_polynomial', 'algebra'],
  dynamical_system: ['iteration', 'recurrence'],
  iteration: ['recurrence', 'matrix'],
  ellipse: ['locus', 'tangent'],
}

function expandedFocusTags(tags: string[]): string[] {
  return [...new Set(tags.flatMap(tag => [tag, ...(EXECUTABLE_TAG_BRIDGES[tag] ?? [])]))]
}

function preservedByAtlas(tag: string, candidateTags: string[]): boolean {
  return candidateTags.includes(tag) ||
    (EXECUTABLE_TAG_BRIDGES[tag] ?? []).some(neighbor => candidateTags.includes(neighbor))
}

const TAG_PATTERNS: Array<[string, RegExp]> = [
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
  ['polynomial_roots', /方程式[^。\n]{0,140}(?:解|根)|(?:解|根)[^。\n]{0,100}(?:方程式|多項式)|polynomial[_\s-]?roots?|root[_\s-]?polynomial/i],
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
    mode,
  }
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
  const { data } = await supabaseAdmin
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
  emit: ProgressEmitter = () => undefined,
): Promise<GenerationResult> {
  const cards: Record<string, unknown>[] = []
  const errors: string[] = []
  const structures: RegisteredStructure[] = []
  const sessionLogs: Array<{ phase: string; message: string; ts: string }> = []
  const seenFamilies = new Set<string>()
  const seenCandidates = new Set<string>()
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
  const isBatch = profiles.length > 1
  const attemptsPerProfile = isBatch ? 12 : searchDepth === 'deep' ? 180 : 50
  const maxAttempts = isBatch
    ? Math.min(720, Math.max(180, profiles.length * attemptsPerProfile))
    : attemptsPerProfile
  const deadline = Date.now() + (searchDepth === 'deep' ? 240_000 : 45_000)
  const firstProfile = profiles[0] ?? buildGenerationProfile([])
  const focusLabel = profiles.length > 1
    ? `${profiles.length} 個の親構造を個別探索`
    : firstProfile.tags.slice(0, 5).join(' / ') || firstProfile.domain || 'all'
  const requiredLabel = profiles.length === 1 && firstProfile.requiredTags.length
    ? ` / 継承: ${firstProfile.requiredTags.join(' + ')}`
    : ''

  const { error: jobError } = await supabaseAdmin.from('generation_jobs').insert({
    id: jobId,
    status: 'processing',
    parents: profiles.map(profile => ({
      parentIds: profile.parentIds,
      tags: profile.tags,
      requiredTags: profile.requiredTags,
      queryTags: profile.queryTags,
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
    message: `MathOS が${searchDepth === 'deep' ? '深層' : '標準'}探索を開始: ${focusLabel}${requiredLabel}`,
    current: 0,
    total: count,
  })

  for (let i = 0; i < count; i++) {
    const current = i + 1
    let profileIndex = i % profiles.length
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
    for (let attempt = 0; attempt < maxAttempts && Date.now() < deadline; attempt++) {
      if (isBatch && attempt > 0 && attempt % attemptsPerProfile === 0) {
        profileIndex = (profileIndex + 1) % profiles.length
        profile = profiles[profileIndex] ?? firstProfile
      }
      if (attempt > 0 && attempt % 30 === 0) {
        report({
          phase: 'searching',
          message: `問題 ${current}/${count}: ${attempt} 候補を検査。構造条件を保ったまま探索を継続`,
          current,
          total: count,
        })
      }
      const candidate = generateLiveProblem({
        domain: profile.domain,
        focusTags: expandedFocusTags(profile.tags),
        avoidQueryTags: profile.queryTags,
        excludedFamilies: attempt < Math.floor(maxAttempts * 0.6) ? [...seenFamilies] : [],
        preferDepth: searchDepth === 'deep',
      })
      if (!candidate) continue
      const candidateKey = `${candidate.familyId}\u0000${canonical(candidate.statementTex)}`
      if (seenCandidates.has(candidateKey)) continue
      seenCandidates.add(candidateKey)

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
      const profileAttempt = isBatch ? attempt % attemptsPerProfile : attempt
      const requiredCount = profileAttempt < Math.floor(attemptsPerProfile * 0.55)
        ? profile.requiredTags.length
        : profileAttempt < Math.floor(attemptsPerProfile * 0.8)
          ? Math.min(profile.requiredTags.length, 2)
          : Math.min(profile.requiredTags.length, 1)
      const attemptRequiredTags = profile.requiredTags.slice(0, requiredCount)
      const candidateQueryTags = candidateTags.filter(tag => QUERY_TAGS.has(tag))
      const changesQuery = profile.queryTags.length === 0 ||
        candidateQueryTags.every(tag => !profile.queryTags.includes(tag))
      const requireQueryChange = profile.queryTags.length > 0 &&
        profileAttempt < Math.floor(attemptsPerProfile * 0.85)
      const preservesRequiredStructure = profile.mode === 'similar' || profile.mode === 'expand' || profile.mode === 'fusion'
        ? attemptRequiredTags.every(tag => preservedByAtlas(tag, candidateTags))
        : attemptRequiredTags.some(tag => preservedByAtlas(tag, candidateTags))
      if ((attemptRequiredTags.length && !preservesRequiredStructure) || (requireQueryChange && !changesQuery)) {
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
          const { error } = await supabaseAdmin.from('generation_jobs').update({
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
        live = candidate
        sim = s
        inheritedTags = attemptRequiredTags.filter(tag => candidateTags.includes(tag))
        bridgedTags = attemptRequiredTags.filter(tag =>
          !candidateTags.includes(tag) && preservedByAtlas(tag, candidateTags),
        )
        seenFamilies.add(candidate.familyId)
        report({
          phase: 'novelty',
          message: `既存 ${s.comparedAgainst} 問と照合。最大表層類似度 ${(s.score * 100).toFixed(0)}%`,
          current,
          total: count,
          draft: candidate.statementTex,
          familyId: candidate.familyId,
          morphisms: candidate.morphismChain,
          similarity: s.score,
        })
        break
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
      const message = `実行射が不足する構造 ${pendingId} をAtlas保留キューへ登録し、次候補の探索へ進みました`
      errors.push(message)
      report({ phase: 'registering', message, current, total: count, structureId: pendingId, structureStatus: 'pending' })
      continue
    }

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
    const meta = {
      shortId,
      familyId: live.familyId,
      tool: live.tool,
      parameters: live.parameters,
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
      },
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

    const { error } = await supabaseAdmin.from('problems').upsert(
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
  }
  if (jobWritable) {
    await supabaseAdmin.from('generation_jobs').update({
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
  let mode: GenerationProfile['mode'] = 'batch'
  try {
    const body = await request.json()
    count = Math.min(Math.max(Number(body?.count ?? 1), 1), 10)
    domain = body?.domain || undefined
    stream = body?.stream === true
    parents = Array.isArray(body?.parents) ? body.parents.slice(0, 250) : []
    searchDepth = body?.searchDepth === 'standard' ? 'standard' : 'deep'
    mode = ['similar', 'fusion', 'expand'].includes(body?.mode) ? body.mode : 'batch'
  } catch {
    // 既定値で続行
  }

  const shuffledParents = [...parents]
  for (let i = shuffledParents.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffledParents[i], shuffledParents[j]] = [shuffledParents[j], shuffledParents[i]]
  }
  const profiles = mode === 'batch' && shuffledParents.length > 0
    ? shuffledParents.map(parent => {
        return buildGenerationProfile([parent], parent.topic_a || domain, 'similar')
      })
    : [buildGenerationProfile(parents, domain, mode)]

  if (!stream) return NextResponse.json(await generateCards(count, profiles, searchDepth))

  const encoder = new TextEncoder()
  const responseStream = new ReadableStream({
    async start(controller) {
      const send = (event: ProgressEvent | { phase: 'done'; result: GenerationResult }) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      try {
        const result = await generateCards(count, profiles, searchDepth, send)
        send({ phase: 'done', result })
      } catch (error) {
        send({
          phase: 'error',
          message: error instanceof Error ? error.message : String(error),
          current: 0,
          total: count,
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
    usage: 'POST { count?: 1-10, domain?: string, parents?: Parent[], mode?: similar|fusion|expand|batch, searchDepth?: standard|deep, stream?: boolean }',
  })
}
