import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { generateLiveProblem } from '@/lib/mathos-live'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 60

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
async function assessNovelty(
  statement: string,
  familyId: string,
  answer: string,
): Promise<{
  duplicate: boolean
  score: number
  closestId: string | null
  closestFamily: string | null
  crossFamilyMax: number
  comparedAgainst: number
}> {
  const target = ngrams(statement)
  const canonStatement = canonical(statement)
  const canonAnswer = canonical(answer)
  let best = 0
  let closestId: string | null = null
  let closestFamily: string | null = null
  let crossFamilyMax = 0
  let duplicate = false
  let compared = 0

  const consider = (
    otherStatement: string,
    otherFamily: string | null,
    otherAnswer: string | null,
    id: string,
  ) => {
    compared++
    if (canonical(otherStatement) === canonStatement) duplicate = true
    if (otherFamily === familyId && otherAnswer && canonical(otherAnswer) === canonAnswer) {
      duplicate = true
    }
    const s = jaccard(target, ngrams(otherStatement))
    if (s > best) { best = s; closestId = id; closestFamily = otherFamily }
    if (otherFamily !== familyId && s > crossFamilyMax) crossFamilyMax = s
  }

  // 1) 同梱プール
  for (const p of POOL) {
    if (!p.statement_tex) continue
    consider(p.statement_tex, p.family_id ?? null, p.answer_tex ?? null, p.family_id ?? 'pool')
  }

  // 2) Supabase の既存問題（作問ステーションの蓄積）
  const { data } = await supabaseAdmin
    .from('problems')
    .select('id,statement,answer,topic_b')
    .not('statement', 'is', null)
    .limit(4000)
  for (const row of (data ?? []) as {
    id: string; statement: string; answer: string | null; topic_b: string | null
  }[]) {
    if (!row.statement) continue
    consider(row.statement, row.topic_b, row.answer, row.id)
  }

  return {
    duplicate,
    score: Number(best.toFixed(4)),
    closestId,
    closestFamily,
    crossFamilyMax: Number(crossFamilyMax.toFixed(4)),
    comparedAgainst: compared,
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

export async function POST(request: NextRequest) {
  let count = 1
  let domain: string | undefined
  try {
    const body = await request.json()
    count = Math.min(Math.max(Number(body?.count ?? 1), 1), 10)
    domain = body?.domain || undefined
  } catch {
    // 既定値で続行
  }

  const cards: Record<string, unknown>[] = []
  const errors: string[] = []

  const seenThisRun = new Set<string>()
  for (let i = 0; i < count; i++) {
    // 既出でない問題が出るまで引き直す（重複判定は (族, 答え) と完全一致）
    let live: ReturnType<typeof generateLiveProblem> = null
    let sim: Awaited<ReturnType<typeof assessNovelty>> | null = null
    for (let attempt = 0; attempt < 30; attempt++) {
      const candidate = generateLiveProblem(domain)
      if (!candidate) continue
      const runKey = `${candidate.familyId}::${canonical(candidate.answerTex)}`
      if (seenThisRun.has(runKey)) continue
      const s = await assessNovelty(
        candidate.statementTex,
        candidate.familyId,
        candidate.answerTex,
      )
      if (!s.duplicate) {
        live = candidate
        sim = s
        seenThisRun.add(runKey)
        break
      }
    }
    if (!live || !sim) {
      errors.push('新規な問題を引けず（この族は既に出尽くしている可能性）')
      continue
    }

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
    }

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
        parent_ids: [],
        source_file: 'mathos_live_session',
      },
      { onConflict: 'id' },
    )
    if (error) { errors.push(`保存失敗: ${error.message}`); continue }

    cards.push({
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
    })
  }

  return NextResponse.json({
    generated: cards.length,
    requested: count,
    engine: 'MathOS live (no LLM)',
    cards,
    errors,
  })
}

export async function GET() {
  return NextResponse.json({
    engine: 'MathOS live (no LLM)',
    pool_bundled: POOL.length,
    usage: 'POST { count?: 1-10, domain?: string }',
  })
}
