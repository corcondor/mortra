import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { generateLiveProblem } from '@/lib/mathos-live'
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
  inspiration?: string | null
  meta?: string | Record<string, unknown> | null
}

type GenerationProfile = {
  domain?: string
  tags: string[]
  requiredTags: string[]
  parentIds: string[]
  mode: 'similar' | 'fusion' | 'expand' | 'batch'
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
  const addTags = (text: string, weight: number) => {
    for (const tag of new Set(inferTags(text))) {
      tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + weight)
    }
  }
  for (const parent of parents) {
    // 類題の核は分類ラベルではなく問題本文。topic/meta は補助証拠としてだけ使う。
    addTags(parent.statement ?? '', 4)
    addTags([parent.topic_a, parent.topic_b].filter(Boolean).join(' '), 1)
    addTags([parent.answer, parent.inspiration, typeof parent.meta === 'string'
      ? parent.meta
      : JSON.stringify(parent.meta ?? {})].filter(Boolean).join(' '), 1)
  }
  const tags = [...tagCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag)

  const specificPriority = [
    'passage_region', 'envelope', 'volume', 'minkowski_sum', 'probability',
    'number_theory', 'complex', 'recurrence', 'iteration', 'limit', 'locus', 'area',
  ]
  const strongestSpecific = specificPriority.find(tag => tagCounts.has(tag))
  const structuralTags = tags.filter(tag => !['geometry', 'algebra'].includes(tag))
  const requiredTags = mode === 'similar' || mode === 'expand'
    ? structuralTags.slice(0, 3)
    : strongestSpecific ? [strongestSpecific] : []

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
  phase: 'start' | 'searching' | 'structuring' | 'novelty' | 'verifying' | 'saving' | 'complete' | 'error'
  message: string
  current: number
  total: number
  draft?: string
  familyId?: string
  morphisms?: string[]
  similarity?: number
}

type ProgressEmitter = (event: ProgressEvent) => void

async function generateCards(
  count: number,
  profile: GenerationProfile,
  searchDepth: 'standard' | 'deep',
  emit: ProgressEmitter = () => undefined,
): Promise<GenerationResult> {
  const cards: Record<string, unknown>[] = []
  const errors: string[] = []
  const seenFamilies = new Set<string>()
  const seenCandidates = new Set<string>()
  const corpus = await loadNoveltyCorpus()
  const maxAttempts = searchDepth === 'deep' ? 180 : 50
  const deadline = Date.now() + (searchDepth === 'deep' ? 240_000 : 45_000)
  const focusLabel = profile.tags.slice(0, 5).join(' / ') || profile.domain || 'all'

  emit({
    phase: 'start',
    message: `MathOS が${searchDepth === 'deep' ? '深層' : '標準'}探索を開始: ${focusLabel}`,
    current: 0,
    total: count,
  })

  for (let i = 0; i < count; i++) {
    const current = i + 1
    emit({
      phase: 'searching',
      message: `問題 ${current}/${count}: Task Atlas から構成可能な経路を探索`,
      current,
      total: count,
    })

    // 前半は未使用の構造族だけを探索し、数字替えより構造多様性を優先する。
    // 後半だけ同族の別パラメータを許し、要求数を満たせる可能性を残す。
    let live: ReturnType<typeof generateLiveProblem> = null
    let sim: ReturnType<typeof assessNovelty> | null = null
    for (let attempt = 0; attempt < maxAttempts && Date.now() < deadline; attempt++) {
      if (attempt > 0 && attempt % 30 === 0) {
        emit({
          phase: 'searching',
          message: `問題 ${current}/${count}: ${attempt} 候補を検査。構造条件を保ったまま探索を継続`,
          current,
          total: count,
        })
      }
      const candidate = generateLiveProblem({
        domain: profile.domain,
        focusTags: profile.tags,
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
        candidate.morphismChain.join(' '),
      ].join(' '))
      const preservesRequiredStructure = profile.mode === 'similar' || profile.mode === 'expand'
        ? profile.requiredTags.every(tag => candidateTags.includes(tag))
        : profile.requiredTags.some(tag => candidateTags.includes(tag))
      if (profile.requiredTags.length && !preservesRequiredStructure) {
        continue
      }

      emit({
        phase: 'structuring',
        message: `${candidate.familyId}: 選択問題の ${profile.requiredTags.join(' / ') || profile.domain || '構造'} を保ち、${candidate.morphismChain.length} 本の射を構成`,
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
        seenFamilies.add(candidate.familyId)
        emit({
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
      const message = '新規な問題を引けませんでした（この構造族は出尽くしている可能性があります）'
      errors.push(message)
      emit({ phase: 'error', message, current, total: count })
      continue
    }

    emit({
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
        requiredTags: profile.requiredTags,
      },
    }

    emit({
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
      emit({ phase: 'error', message, current, total: count })
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
      inherited_tags: profile.requiredTags,
      parent_ids: profile.parentIds,
    }
    cards.push(card)
    addToNoveltyCorpus(corpus, live.statementTex, live.familyId, live.answerTex, id)
    emit({
      phase: 'complete',
      message: `問題 ${current}/${count} を生成・検証・保存しました`,
      current,
      total: count,
      draft: live.statementTex,
      familyId: live.familyId,
      morphisms: live.morphismChain,
    })
  }

  return {
    generated: cards.length,
    requested: count,
    engine: `MathOS structural live (${searchDepth}, no LLM)`,
    cards,
    errors,
  }
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
    parents = Array.isArray(body?.parents) ? body.parents.slice(0, 20) : []
    searchDepth = body?.searchDepth === 'standard' ? 'standard' : 'deep'
    mode = ['similar', 'fusion', 'expand'].includes(body?.mode) ? body.mode : 'batch'
  } catch {
    // 既定値で続行
  }

  const profile = buildGenerationProfile(parents, domain, mode)

  if (!stream) return NextResponse.json(await generateCards(count, profile, searchDepth))

  const encoder = new TextEncoder()
  const responseStream = new ReadableStream({
    async start(controller) {
      const send = (event: ProgressEvent | { phase: 'done'; result: GenerationResult }) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      try {
        const result = await generateCards(count, profile, searchDepth, send)
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
    usage: 'POST { count?: 1-10, domain?: string, parents?: Parent[], mode?: similar|fusion|expand, searchDepth?: standard|deep, stream?: boolean }',
  })
}
