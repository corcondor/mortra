import { NextRequest } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import {
  makeAnalysisPrompt, makeSimilarPrompt,
  makeFusionPrompt,   makeExpandPrompt,
  makeVerificationPrompt,
  extractJson,        type ParentProblem,
} from '@/lib/prompts'
import crypto from 'crypto'

export const maxDuration = 300

import { ADMIN_EMAIL, FREE_GENERATIONS_PER_MONTH, currentYearMonth } from '@/lib/billing'

/** 生成回数をインクリメント（存在しなければ作成） */
async function incrementUsage(userId: string) {
  const yearMonth = currentYearMonth()
  // upsert: count +1
  await supabaseAdmin.rpc('increment_usage', { p_user_id: userId, p_year_month: yearMonth })
    .then(({ error }) => {
      if (error) {
        // RPC が存在しない場合は手動でupsert
        return supabaseAdmin
          .from('usage')
          .upsert({ user_id: userId, year_month: yearMonth, generations_count: 1 },
            { onConflict: 'user_id,year_month', ignoreDuplicates: false })
      }
    })
}

const DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
// deepseek-reasoner = R1（推論モデル）、deepseek-chat = V3（高速モデル）
const MODEL            = process.env.DEEPSEEK_MODEL ?? 'deepseek-reasoner'
const FAST_MODEL       = process.env.DEEPSEEK_FAST_MODEL ?? 'deepseek-chat'
// R1は推論トレース(reasoning_content)+JSON本文で合計32k超えることがある。余裕を持って設定
const MAX_TOKENS       = Number(process.env.DEEPSEEK_MAX_TOKENS ?? 32000)
// 分析・検証など軽いタスクはトークン節約
const FAST_MAX_TOKENS  = 6000

type SseType = 'status' | 'log' | 'done' | 'error'

function deepSeekHttpError(status: number, body: string) {
  const detail = body.replace(/\s+/g, ' ').trim().slice(0, 500)
  if (status === 401 || status === 403) {
    return `DeepSeek 認証エラー (${status}): API key が無効、または権限がありません。${detail}`
  }
  if (status === 429) {
    return `DeepSeek rate limit (${status}): 利用量上限または混雑に達しました。時間を置いて再試行してください。${detail}`
  }
  if (status >= 500) {
    return `DeepSeek サーバーエラー (${status}): DeepSeek 側で失敗しました。${detail}`
  }
  return `DeepSeek API error ${status}: ${detail || 'no response body'}`
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return String(error)
}

async function listDeepSeekModels() {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) {
    throw new Error('DEEPSEEK_API_KEY が設定されていません。Vercel/ローカルの環境変数を確認してください。')
  }

  const res = await fetch('https://api.deepseek.com/models', {
    headers: { Authorization: `Bearer ${apiKey}` },
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(deepSeekHttpError(res.status, body))
  }

  const data = await res.json() as { data?: { id?: string }[] }
  return (data.data ?? []).map(model => model.id).filter(Boolean) as string[]
}

type RatingRow = { status?: string | null; x_posted?: boolean | null }
type PurgeCandidate = {
  id: string
  rating?: RatingRow | RatingRow[] | null
}

function shouldPurge(candidate: PurgeCandidate, excludeIds: Set<string>) {
  if (excludeIds.has(candidate.id)) return false
  // 全ユーザーの ratings を確認: いずれかが selected/posted なら保持
  const ratings: RatingRow[] = Array.isArray(candidate.rating)
    ? candidate.rating
    : candidate.rating ? [candidate.rating] : []
  if (ratings.length === 0) return true
  return !ratings.some(r => r.x_posted === true || r.status === 'selected' || r.status === 'posted')
}

async function purgeUnselectedProblems(excludeIds: string[] = []) {
  const excluded = new Set(excludeIds)
  const { data, error } = await supabaseAdmin
    .from('problems')
    .select('id, rating:ratings(status,x_posted)')

  if (error) throw new Error(error.message)

  const candidates = (data ?? []) as PurgeCandidate[]
  const ids = candidates
    .filter(candidate => shouldPurge(candidate, excluded))
    .map(candidate => candidate.id)

  if (ids.length === 0) {
    return { deleted: 0, considered: candidates.length, excluded: excluded.size }
  }

  const { error: rErr } = await supabaseAdmin.from('ratings').delete().in('problem_id', ids)
  if (rErr) throw new Error(rErr.message)

  const { count, error: pErr } = await supabaseAdmin.from('problems').delete({ count: 'exact' }).in('id', ids)
  if (pErr) throw new Error(pErr.message)

  return { deleted: count ?? ids.length, considered: candidates.length, excluded: excluded.size }
}

// ── 直列キュー（同時に1生成のみ） ─────────────────────────────────────
let _queue: (() => void)[] = []
let _busy = false
function enqueue(): Promise<void> {
  return new Promise(resolve => {
    _queue.push(resolve)
    if (!_busy) _drain()
  })
}
function _drain() {
  if (_queue.length === 0) { _busy = false; return }
  _busy = true
  _queue.shift()!()
}
function dequeue() { _drain() }

// ── DeepSeek API 呼び出し ──────────────────────────────────────────────
async function callDeepSeek(
  prompt: string,
  onChunk?: (s: string, kind: 'content' | 'reasoning') => void,
  maxTokens = MAX_TOKENS,
  model = MODEL,
): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) {
    throw new Error('DEEPSEEK_API_KEY が設定されていません。Vercel/ローカルの環境変数を確認してください。')
  }

  // R1（deepseek-reasoner）は temperature=1 推奨。V3はデフォルト(1.0)のまま
  const isReasoner = model.includes('reasoner')

  let res: Response
  try {
    res = await fetch(DEEPSEEK_API_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        stream:   !!onChunk,
        max_tokens: maxTokens,
        ...(isReasoner ? { temperature: 1 } : {}),
      }),
    })
  } catch (error) {
    throw new Error(`DeepSeek 接続エラー: ${errorMessage(error)}`)
  }

  if (!res.ok) {
    const err = await res.text()
    throw new Error(deepSeekHttpError(res.status, err))
  }

  if (!onChunk) {
    const json = await res.json() as { choices?: { message?: { content?: string; finish_reason?: string } }[] }
    const choice = json.choices?.[0]
    if (choice?.message?.finish_reason === 'length') {
      throw new Error(`トークン上限(${maxTokens})に達して応答が途切れました。DEEPSEEK_MAX_TOKENS を増やしてください。`)
    }
    return choice?.message?.content ?? ''
  }

  // SSE ストリーミング
  if (!res.body) throw new Error('DeepSeek streaming response body が空です')

  const reader = res.body.getReader()
  const dec    = new TextDecoder()
  let full = ''
  let reasoning = ''
  let streamDone = false
  let finishReason = ''

  outer: while (!streamDone) {
    const { done, value } = await reader.read()
    if (done) break
    for (const line of dec.decode(value).split('\n')) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') { streamDone = true; break outer }
      try {
        const parsed = JSON.parse(data)
        const delta  = parsed.choices?.[0]?.delta
        const fr     = parsed.choices?.[0]?.finish_reason
        if (fr)  finishReason = fr
        const rc = delta?.reasoning_content
        const cc = delta?.content
        if (rc) { reasoning += rc; onChunk(rc, 'reasoning') }
        if (cc) { full += cc; onChunk(cc, 'content') }
      } catch { /* skip */ }
    }
  }

  if (!streamDone) {
    // [DONE] を受け取らずにストリームが終了
    if (finishReason === 'length') {
      throw new Error(`トークン上限(${maxTokens})に達して応答が途切れました。DEEPSEEK_MAX_TOKENS を増やしてください（現在: ${maxTokens}）。`)
    }
    // finish_reason が不明な場合も警告（内容が取れていれば続行）
    if (!full && !reasoning) {
      throw new Error('DeepSeek から応答なしでストリームが終了しました。')
    }
    // 部分的でも内容があれば続行（onChunk で通知は不要なのでそのまま）
  }

  // reasoning-only モデル（DeepSeek-R1等）: content が空なら reasoning から JSON を抽出
  if (!full && reasoning) full = reasoning
  return full
}

// ── Supabase に保存 ────────────────────────────────────────────────────
async function saveToSupabase(data: Record<string, unknown>, parents: ParentProblem[], mode: string, nextGen: number, userId?: string | null) {
  const fp  = (data.final_problem ?? {}) as Record<string, unknown>
  const ba  = (data.beauty_analysis ?? {}) as Record<string, unknown>

  const id = (data.id as string | undefined) ?? crypto.randomBytes(6).toString('hex')
  const problem = {
    id,
    topic_a:    parents[0]?.topic_a ?? 'unknown',
    topic_b:    mode === 'fusion' ? (parents[parents.length - 1]?.topic_a ?? null) : (parents[0]?.topic_b ?? null),
    variation:  0,
    statement:  fp.statement as string ?? '',
    answer:     fp.answer    as string ?? null,
    difficulty: fp.difficulty as string ?? null,
    solution:   fp.solution_outline as string ?? null,
    inspiration: data.inspiration as string ?? null,
    meta:       data.meta as string ?? null,
    surprise:   Number(ba.surprise)              || 0,
    minimality: Number(ba.minimality)            || 0,
    connection: Number(ba.connection_strength)   || 0,
    inevitability: Number(ba.inevitability)      || 0,
    diff_cal:   Number(ba.difficulty_calibration)|| 0,
    total:      Number(ba.total)                 || 0,
    generation: nextGen,
    parent_ids: parents.map(p => p.id),
    source_file: null,
  }

  const { error: pErr } = await supabaseAdmin.from('problems').upsert(problem)
  if (pErr) throw new Error(pErr.message)

  const { error: rErr } = await supabaseAdmin.from('ratings').upsert(
    { user_id: userId ?? 'system', problem_id: id, status: 'pending', x_posted: false },
    { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
  )
  if (rErr) throw new Error(rErr.message)

  return problem
}

// ── GET: キュー状態確認 / DeepSeek 接続確認 ───────────────────────────
export async function GET(req: NextRequest) {
  const url = new URL(req.url)
  if (url.searchParams.get('deepseek') === '1') {
    try {
      const models = await listDeepSeekModels()
      return Response.json({
        ok: models.includes(MODEL),
        generationModel: MODEL,
        fastModel: FAST_MODEL,
        availableModels: models,
        message: models.includes(MODEL)
          ? 'DeepSeek API key is valid and generation model is available.'
          : `DeepSeek API key is valid, but ${MODEL} is not in available models.`,
      })
    } catch (error) {
      return Response.json({
        ok: false,
        generationModel: MODEL,
        fastModel: FAST_MODEL,
        error: errorMessage(error),
      }, { status: 503 })
    }
  }

  return Response.json({ queueLength: _queue.length, busy: _busy })
}

// ── POST: 生成 ─────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  // ── 認証 & 利用制限チェック ──────────────────────────────────────────
  const authHeader = req.headers.get('Authorization')
  const token = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null
  let userId: string | null = null
  let userEmail: string | null = null
  let isAdmin = false

  if (token) {
    const { data } = await supabaseAdmin.auth.getUser(token)
    userId    = data.user?.id ?? null
    userEmail = data.user?.email ?? null
    isAdmin   = userEmail === ADMIN_EMAIL
  }

  // 非管理者は月間生成数をチェック
  if (userId && !isAdmin) {
    const yearMonth = currentYearMonth()
    const { data: usageData } = await supabaseAdmin
      .from('usage')
      .select('generations_count')
      .eq('user_id', userId)
      .eq('year_month', yearMonth)
      .single()

    const used = (usageData?.generations_count as number) ?? 0

    // サブスクリプション確認
    const { data: subData } = await supabaseAdmin
      .from('subscriptions')
      .select('status')
      .eq('user_id', userId)
      .single()

    const isPaid = subData?.status === 'active'

    if (!isPaid && used >= FREE_GENERATIONS_PER_MONTH) {
      return Response.json({
        error: `無料枠（月${FREE_GENERATIONS_PER_MONTH}回）を使い切りました。プレミアムプランにアップグレードしてください。`,
        code:  'USAGE_LIMIT_EXCEEDED',
        used,
        limit: FREE_GENERATIONS_PER_MONTH,
      }, { status: 402 })
    }
  }

  const { parents, mode = 'auto', count = 3, dry_run = false } = await req.json() as {
    parents: ParentProblem[]
    mode?:   string
    count?:  number
    dry_run?: boolean
  }

  if (!parents || parents.length === 0)
    return Response.json({ error: 'parents required' }, { status: 400 })

  if (!process.env.DEEPSEEK_API_KEY)
    return Response.json({ error: 'DEEPSEEK_API_KEY が設定されていません。Vercel の環境変数に追加してください。' }, { status: 503 })

  const resolvedMode = mode === 'auto' ? (parents.length >= 2 ? 'fusion' : 'similar') : mode
  const totalCount = Math.max(1, Math.min(Number(count) || 1, 10))

  // 現世代を取得
  const { data: genData } = await supabaseAdmin
    .from('problems')
    .select('generation')
    .order('generation', { ascending: false })
    .limit(1)
    .single()
  const nextGen = ((genData?.generation as number | null) ?? 0) + 1

  const encoder = new TextEncoder()
  const stream  = new ReadableStream({
    async start(controller) {
      let lockAcquired = false
      const send = (type: SseType, payload: Record<string, unknown>) => {
        const message = payload.message ?? payload.msg
        try {
          controller.enqueue(encoder.encode(
            `data: ${JSON.stringify({ type, ...payload, message })}\n\n`
          ))
        } catch { /* closed */ }
      }

      send('status', { step: 'queued', message: '生成キューに登録しました' })
      await enqueue()
      lockAcquired = true
      send('status', { step: 'start', message: `DeepSeek (${MODEL}) で ${resolvedMode} 生成開始（${totalCount}問）` })

      const generated: { id: string; statement: string }[] = []

      try {
        // 分析フェーズ（similar/expand かつ1問の場合）
        let analysis: Record<string, string> | undefined
        if (resolvedMode !== 'fusion' && parents.length === 1) {
          send('status', { step: 'analyzing', message: '問題を深く分析中...' })
          const raw = await callDeepSeek(makeAnalysisPrompt(parents[0]), undefined, FAST_MAX_TOKENS, FAST_MODEL)
          const a   = extractJson(raw)
          if (a) analysis = a as Record<string, string>
          send('log', { message: `分析完了: ${analysis?.core_structure?.slice(0, 60) ?? 'OK'}` })
        }

        for (let i = 0; i < totalCount; i++) {
          send('status', { step: 'generating', message: `生成中... (${i + 1}/${totalCount})` })

          let prompt: string
          if (resolvedMode === 'fusion') {
            prompt = makeFusionPrompt(parents)
          } else if (resolvedMode === 'expand') {
            prompt = makeExpandPrompt(parents[i % parents.length])
          } else {
            prompt = makeSimilarPrompt(parents[i % parents.length], analysis)
          }

          let data: Record<string, unknown> | null = null
          let lastFailure = ''
          for (let attempt = 1; attempt <= 3; attempt++) {
            send('log', { message: `DeepSeek (${MODEL}) 呼び出し中... (試行 ${attempt}/3)` })
            try {
              let received = 0
              let lastProgress = Date.now()
              const raw = await callDeepSeek(prompt, (chunk, kind) => {
                received += chunk.length
                const now = Date.now()
                if (now - lastProgress < 3500) return
                lastProgress = now
                send('log', {
                  message: kind === 'reasoning'
                    ? `推論中... (${received} chars)`
                    : `応答受信中... (${received} chars)`,
                })
              })
              data = extractJson(raw)
              if (data) break
              lastFailure = `JSON 抽出失敗: 応答先頭=${raw.replace(/\s+/g, ' ').slice(0, 180)}`
              send('log', { level: 'warn', message: `${lastFailure}。リトライします。` })
            } catch (e) {
              lastFailure = errorMessage(e)
              send('log', { level: 'error', message: `DeepSeek エラー: ${lastFailure}` })
            }
          }

          if (data) {
            data.id = crypto.randomBytes(6).toString('hex')
            const fp = (data.final_problem ?? {}) as Record<string, unknown>
            const statement = String(fp.statement ?? '')
            const answer    = String(fp.answer    ?? '')
            const solution  = String(fp.solution_outline ?? (data.verification as Record<string,unknown>)?.computation ?? '')
            const score = (data.beauty_analysis as Record<string, unknown>)?.total ?? '?'

            // ── 数学的妥当性の検証 ────────────────────────────────────
            // モデルが既に verification フィールドを埋めているか確認
            const embeddedVerif = (data.verification ?? {}) as Record<string, unknown>
            const embeddedWellPosed = embeddedVerif.problem_well_posed
            const embeddedIssues   = embeddedVerif.issues_found

            let verificationPassed = true
            if (embeddedWellPosed === false) {
              // モデル自身が問題ありと判定
              send('log', {
                level: 'warn',
                message: `⚠ モデルが問題不成立を報告: ${String(embeddedIssues ?? '詳細不明')}。この問題はスキップします。`,
              })
              verificationPassed = false
            } else {
              // 外部検証（FAST_MODEL でダブルチェック）
              send('status', { step: 'verifying', message: `数学的妥当性を検証中... (${i + 1}/${totalCount})` })
              try {
                const verifyRaw = await callDeepSeek(
                  makeVerificationPrompt(statement, answer, solution),
                  undefined,
                  FAST_MAX_TOKENS,
                  FAST_MODEL,
                )
                const verifyResult = extractJson(verifyRaw) as Record<string, unknown> | null
                if (verifyResult) {
                  const verdict    = String(verifyResult.verdict ?? 'UNKNOWN').toUpperCase()
                  const confidence = Number(verifyResult.confidence ?? 5)
                  const issues     = verifyResult.issues
                  const matches    = verifyResult.answer_matches
                  const wellPosed  = verifyResult.problem_well_posed

                  if (verdict === 'FAIL' || !wellPosed || confidence < 5 || matches === false) {
                    send('log', {
                      level: 'warn',
                      message: `⚠ 検証失敗 (verdict=${verdict}, confidence=${confidence}): ${String(issues ?? '詳細なし')}。この問題はスキップします。`,
                    })
                    verificationPassed = false
                  } else {
                    send('log', {
                      message: `✓ 検証OK (verdict=${verdict}, confidence=${confidence})`,
                    })
                    // 検証で得られた答えで上書き（より正確）
                    if (verifyResult.derived_answer && matches === true) {
                      fp.answer = verifyResult.derived_answer
                    }
                  }
                } else {
                  // 検証JSON取得失敗 → 警告のみ、保存は続行
                  send('log', { level: 'warn', message: '検証レスポンスのJSON解析に失敗。問題はそのまま保存します。' })
                }
              } catch (verifyErr) {
                send('log', { level: 'warn', message: `検証エラー（保存は続行）: ${errorMessage(verifyErr)}` })
              }
            }

            if (!verificationPassed) {
              // 検証失敗 → 生成カウントに含めない、保存しない
              continue
            }

            if (dry_run) {
              send('log', { message: `dry run: 保存スキップ score=${score} -> ${statement.slice(0, 50)}...` })
              generated.push({ id: data.id as string, statement })
            } else {
              send('status', { step: 'saving', message: 'Supabase に保存中...' })
              try {
                const saved = await saveToSupabase(data, parents, resolvedMode, nextGen, userId)
                send('log',    { message: `保存完了 score=${score} -> ${saved.statement.slice(0, 50)}...` })
                generated.push(saved)
                // 生成数をインクリメント（管理者は除く）
                if (userId && !isAdmin) {
                  await incrementUsage(userId).catch(() => { /* 失敗しても続行 */ })
                }
              } catch (e) {
                send('log', { level: 'error', message: `保存エラー: ${errorMessage(e)}` })
              }
            }
          } else {
            send('log', { level: 'error', message: `生成失敗 (${i + 1}問目): ${lastFailure || 'JSON を取得できませんでした'}` })
          }
        }

        // ── 自動淘汰: selected/posted 以外を削除 ─────────────────────
        if (dry_run) {
          send('log', { message: 'dry run: 未選択問題の自動淘汰をスキップ' })
        } else {
          send('status', { step: 'purging', message: '未選択問題を自動淘汰中...' })
        }
        let purgeDeleted = 0
        if (!dry_run) {
          try {
            const purge = await purgeUnselectedProblems(generated.map(problem => problem.id))
            purgeDeleted = purge.deleted
            if (purge.deleted > 0) {
              send('log', {
                message:
                  `淘汰完了: ${purge.deleted} 問削除 ` +
                  `(${purge.considered} 問確認、ratings 未作成の問題も対象、新規生成 ${purge.excluded} 問は保持)`,
              })
            } else {
              send('log', { message: `淘汰対象なし (${purge.considered} 問確認、新規生成 ${purge.excluded} 問は保持)` })
            }
          } catch (purgeErr) {
            send('log', { level: 'error', message: `淘汰エラー（生成結果は保持）: ${errorMessage(purgeErr)}` })
          }
        }

        const ok = generated.length === totalCount
        send('done', {
          ok,
          generated: generated.length,
          total:     totalCount,
          purgeDeleted,
          message:   ok
            ? `完了: ${generated.length}/${totalCount} 問生成`
            : `一部失敗: ${generated.length}/${totalCount} 問生成。ログを確認してください。`,
        })
      } catch (e) {
        send('error', { step: 'error', message: errorMessage(e), ok: false })
      } finally {
        if (lockAcquired) dequeue()
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection':    'keep-alive',
    },
  })
}
