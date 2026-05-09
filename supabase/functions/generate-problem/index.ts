// Supabase Edge Function: generate-problem
// Deno runtime - タイムアウトなし（ストリーミング中は無制限）
// DeepSeek R1/V3 両対応

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import {
  makeAnalysisPrompt, makeSimilarPrompt,
  makeFusionPrompt,   makeExpandPrompt,
  makeVerificationPrompt,
  makeR1FusionPrompt, makeR1SimilarPrompt,
  extractJson,
  type ParentProblem,
} from '../_shared/prompts.ts'

// ── 定数 ──────────────────────────────────────────────────────────────────
const DEEPSEEK_API_URL  = 'https://api.deepseek.com/chat/completions'
const MODEL             = Deno.env.get('DEEPSEEK_MODEL')      ?? 'deepseek-chat'
const FAST_MODEL        = Deno.env.get('DEEPSEEK_FAST_MODEL') ?? 'deepseek-chat'
const MAX_TOKENS        = Number(Deno.env.get('DEEPSEEK_MAX_TOKENS') ??
  (MODEL.includes('reasoner') ? '32000' : '8000'))
const FAST_MAX_TOKENS   = 6000
// Edge Function はストリーミング中タイムアウトなしだが、一応上限を設ける
const DEEPSEEK_TIMEOUT_MS = Number(Deno.env.get('DEEPSEEK_TIMEOUT_MS') ?? '180000')
const FREE_GENERATIONS_PER_MONTH = 10
const ADMIN_EMAIL       = Deno.env.get('ADMIN_EMAIL') ?? 'imtceed@gmail.com'

const corsHeaders = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
}

// ── ユーティリティ ─────────────────────────────────────────────────────────
function currentYearMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function randomHex(bytes = 6): string {
  const arr = new Uint8Array(bytes)
  crypto.getRandomValues(arr)
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('')
}

// ── Supabase Admin（SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY は自動注入） ──
function getSupabaseAdmin() {
  return createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )
}

// ── 生成数インクリメント ───────────────────────────────────────────────────
async function incrementUsage(
  supabase: ReturnType<typeof getSupabaseAdmin>,
  userId: string,
) {
  const yearMonth = currentYearMonth()
  const { error } = await supabase.rpc('increment_usage', {
    p_user_id: userId, p_year_month: yearMonth,
  })
  if (error) {
    // RPC 未登録の場合は手動 upsert
    await supabase.from('usage').upsert(
      { user_id: userId, year_month: yearMonth, generations_count: 1 },
      { onConflict: 'user_id,year_month', ignoreDuplicates: false },
    )
  }
}

// ── DeepSeek API 呼び出し ─────────────────────────────────────────────────
function deepSeekHttpError(status: number, body: string): string {
  const d = body.replace(/\s+/g, ' ').trim().slice(0, 400)
  if (status === 401 || status === 403) return `DeepSeek 認証エラー (${status}): ${d}`
  if (status === 429) return `DeepSeek rate limit (${status}): ${d}`
  if (status >= 500)  return `DeepSeek サーバーエラー (${status}): ${d}`
  return `DeepSeek API error ${status}: ${d}`
}

async function callDeepSeek(
  prompt: string,
  onChunk?: (s: string, kind: 'content' | 'reasoning') => void,
  maxTokens = MAX_TOKENS,
  model = MODEL,
): Promise<string> {
  const apiKey = Deno.env.get('DEEPSEEK_API_KEY')
  if (!apiKey) throw new Error('DEEPSEEK_API_KEY が設定されていません')

  const isReasoner = model.includes('reasoner')
  const controller = new AbortController()
  const timeoutId  = setTimeout(() => controller.abort(), DEEPSEEK_TIMEOUT_MS)

  let res: Response
  try {
    res = await fetch(DEEPSEEK_API_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model,
        messages:   [{ role: 'user', content: prompt }],
        stream:     !!onChunk,
        max_tokens: maxTokens,
        ...(isReasoner ? { temperature: 1 } : {}),
      }),
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timeoutId)
    if ((err as Error)?.name === 'AbortError')
      throw new Error(`DeepSeek タイムアウト (${DEEPSEEK_TIMEOUT_MS / 1000}s)`)
    throw new Error(`DeepSeek 接続エラー: ${err}`)
  }

  if (!res.ok) {
    clearTimeout(timeoutId)
    throw new Error(deepSeekHttpError(res.status, await res.text()))
  }

  // 非ストリーミング
  if (!onChunk) {
    // deno-lint-ignore no-explicit-any
    const json: any = await res.json()
    clearTimeout(timeoutId)
    const choice = json.choices?.[0]
    if (choice?.finish_reason === 'length' || choice?.message?.finish_reason === 'length')
      throw new Error(`トークン上限(${maxTokens})に達しました`)
    return choice?.message?.content ?? ''
  }

  // ストリーミング
  if (!res.body) throw new Error('streaming body が空です')
  const reader = res.body.getReader()
  const dec    = new TextDecoder()
  let full = '', reasoning = '', streamDone = false, finishReason = ''

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
        if (fr) finishReason = fr
        if (delta?.reasoning_content) { reasoning += delta.reasoning_content; onChunk(delta.reasoning_content, 'reasoning') }
        if (delta?.content)           { full      += delta.content;           onChunk(delta.content, 'content') }
      } catch { /* skip */ }
    }
  }

  clearTimeout(timeoutId)

  if (!streamDone) {
    if (finishReason === 'length') throw new Error(`トークン上限(${maxTokens})に達して途切れました`)
    if (!full && !reasoning) throw new Error('DeepSeek から応答なしでストリームが終了しました')
    if (!full && reasoning)  throw new Error(`推論が途中で切断されました (${reasoning.length} chars)。再試行します。`)
  }
  if (!full && reasoning) full = reasoning
  return full
}

// ── 未選択問題の淘汰 ──────────────────────────────────────────────────────
async function purgeUnselectedProblems(
  supabase: ReturnType<typeof getSupabaseAdmin>,
  excludeIds: string[],
) {
  const excluded = new Set(excludeIds)
  type RatingRow = { status?: string | null; x_posted?: boolean | null }
  type Candidate = { id: string; rating?: RatingRow | RatingRow[] | null }

  const { data, error } = await supabase
    .from('problems')
    .select('id, rating:ratings(status,x_posted)')
  if (error) throw new Error(error.message)

  const candidates = (data ?? []) as Candidate[]
  const ids = candidates
    .filter(c => {
      if (excluded.has(c.id)) return false
      const ratings: RatingRow[] = Array.isArray(c.rating)
        ? c.rating : c.rating ? [c.rating] : []
      if (ratings.length === 0) return true
      return !ratings.some(r => r.x_posted === true || r.status === 'selected' || r.status === 'posted')
    })
    .map(c => c.id)

  if (ids.length === 0)
    return { deleted: 0, considered: candidates.length, excluded: excluded.size }

  await supabase.from('ratings').delete().in('problem_id', ids)
  const { count } = await supabase.from('problems').delete({ count: 'exact' }).in('id', ids)
  return { deleted: count ?? ids.length, considered: candidates.length, excluded: excluded.size }
}

// ── Supabase に保存 ───────────────────────────────────────────────────────
async function saveToSupabase(
  supabase: ReturnType<typeof getSupabaseAdmin>,
  data: Record<string, unknown>,
  parents: ParentProblem[],
  mode: string,
  nextGen: number,
  userId?: string | null,
) {
  const fp = (data.final_problem ?? {}) as Record<string, unknown>
  const ba = (data.beauty_analysis ?? {}) as Record<string, unknown>
  const id = (data.id as string | undefined) ?? randomHex(6)

  const problem = {
    id,
    topic_a:      parents[0]?.topic_a ?? 'unknown',
    topic_b:      mode === 'fusion'
      ? (parents[parents.length - 1]?.topic_a ?? null)
      : (parents[0]?.topic_b ?? null),
    variation:    0,
    statement:    fp.statement as string ?? '',
    answer:       fp.answer    as string ?? null,
    difficulty:   fp.difficulty as string ?? null,
    solution:     fp.solution_outline as string ?? null,
    inspiration:  data.inspiration as string ?? null,
    meta:         data.meta as string ?? null,
    surprise:     Number(ba.surprise)               || 0,
    minimality:   Number(ba.minimality)             || 0,
    connection:   Number(ba.connection_strength)    || 0,
    inevitability:Number(ba.inevitability)          || 0,
    diff_cal:     Number(ba.difficulty_calibration) || 0,
    total:        Number(ba.total)                  || 0,
    generation:   nextGen,
    parent_ids:   parents.map(p => p.id),
    source_file:  null,
  }

  const { error: pErr } = await supabase.from('problems').upsert(problem)
  if (pErr) throw new Error(pErr.message)

  const { error: rErr } = await supabase.from('ratings').upsert(
    { user_id: userId ?? 'system', problem_id: id, status: 'pending', x_posted: false },
    { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
  )
  if (rErr) throw new Error(rErr.message)

  return problem
}

// ── メインハンドラ ────────────────────────────────────────────────────────
Deno.serve(async (req: Request) => {
  // CORS preflight
  if (req.method === 'OPTIONS')
    return new Response('ok', { headers: corsHeaders })

  // ヘルスチェック
  if (req.method === 'GET')
    return new Response(JSON.stringify({ ok: true, model: MODEL, runtime: 'supabase-edge' }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })

  const supabase = getSupabaseAdmin()

  // ── 認証 ──────────────────────────────────────────────────────────────
  const token = req.headers.get('Authorization')?.replace(/^Bearer /, '') ?? null
  let userId: string | null = null, userEmail: string | null = null, isAdmin = false

  if (token) {
    const { data } = await supabase.auth.getUser(token)
    userId    = data.user?.id    ?? null
    userEmail = data.user?.email ?? null
    isAdmin   = userEmail === ADMIN_EMAIL
  }

  // ── 利用制限チェック ────────────────────────────────────────────────
  if (userId && !isAdmin) {
    const ym = currentYearMonth()
    const { data: usageData } = await supabase.from('usage')
      .select('generations_count').eq('user_id', userId).eq('year_month', ym).single()
    const used = (usageData?.generations_count as number) ?? 0

    const { data: subData } = await supabase.from('subscriptions')
      .select('status').eq('user_id', userId).single()
    const isPaid = subData?.status === 'active'

    if (!isPaid && used >= FREE_GENERATIONS_PER_MONTH) {
      return new Response(JSON.stringify({
        error: `無料枠（月${FREE_GENERATIONS_PER_MONTH}回）を使い切りました。`,
        code: 'USAGE_LIMIT_EXCEEDED', used, limit: FREE_GENERATIONS_PER_MONTH,
      }), { status: 402, headers: { ...corsHeaders, 'Content-Type': 'application/json' } })
    }
  }

  // ── リクエスト解析 ─────────────────────────────────────────────────
  let body: { parents: ParentProblem[]; mode?: string; count?: number; dry_run?: boolean }
  try { body = await req.json() }
  catch { return new Response(JSON.stringify({ error: 'invalid json' }),
    { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }) }

  const { parents, mode = 'auto', count = 3, dry_run = false } = body

  if (!parents?.length)
    return new Response(JSON.stringify({ error: 'parents required' }),
      { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } })

  if (!Deno.env.get('DEEPSEEK_API_KEY'))
    return new Response(JSON.stringify({ error: 'DEEPSEEK_API_KEY が設定されていません' }),
      { status: 503, headers: { ...corsHeaders, 'Content-Type': 'application/json' } })

  const resolvedMode  = mode === 'auto' ? (parents.length >= 2 ? 'fusion' : 'similar') : mode
  const totalCount    = Math.max(1, Math.min(Number(count) || 1, 10))
  const isR1          = MODEL.includes('reasoner')
  const useStreaming   = !isR1  // R1は非ストリーミング（タイムアウト回避）

  const { data: genData } = await supabase.from('problems')
    .select('generation').order('generation', { ascending: false }).limit(1).single()
  const nextGen = ((genData?.generation as number | null) ?? 0) + 1

  // ── SSE ストリーム ─────────────────────────────────────────────────
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      const send = (type: string, payload: Record<string, unknown>) => {
        try {
          controller.enqueue(encoder.encode(
            `data: ${JSON.stringify({ type, ...payload, message: payload.message ?? payload.msg })}\n\n`
          ))
        } catch { /* closed */ }
      }

      send('status', { step: 'start',
        message: `[Edge Function] DeepSeek (${MODEL}) で ${resolvedMode} 生成開始（${totalCount}問）` })

      const generated: { id: string; statement: string }[] = []

      try {
        // 分析フェーズ
        let analysis: Record<string, string> | undefined
        if (resolvedMode !== 'fusion' && parents.length === 1) {
          send('status', { step: 'analyzing', message: '問題を分析中...' })
          const raw = await callDeepSeek(makeAnalysisPrompt(parents[0]), undefined, FAST_MAX_TOKENS, FAST_MODEL)
          const a = extractJson(raw)
          if (a) analysis = a as Record<string, string>
          send('log', { message: `分析完了: ${analysis?.core_structure?.slice(0, 60) ?? 'OK'}` })
        }

        for (let i = 0; i < totalCount; i++) {
          send('status', { step: 'generating', message: `生成中... (${i + 1}/${totalCount})` })

          // R1は短いプロンプト専用（長いとAPIが17秒でタイムアウト）
          const prompt = isR1
            ? (resolvedMode === 'fusion'
                ? makeR1FusionPrompt(parents)
                : makeR1SimilarPrompt(parents[i % parents.length]))
            : resolvedMode === 'fusion'  ? makeFusionPrompt(parents)
            : resolvedMode === 'expand'  ? makeExpandPrompt(parents[i % parents.length])
            : makeSimilarPrompt(parents[i % parents.length], analysis)

          let data: Record<string, unknown> | null = null
          let lastFailure = ''

          for (let attempt = 1; attempt <= 3; attempt++) {
            send('log', { message: `DeepSeek (${MODEL}) 呼び出し中... (試行 ${attempt}/3)` })

            // R1 用 keepAlive タイマー（SSE 接続をブラウザが切らないよう）
            let keepAliveTimer: number | null = null
            let waitSec = 0
            if (!useStreaming) {
              keepAliveTimer = setInterval(() => {
                waitSec += 5
                send('log', { message: `R1 推論中... (${waitSec}s 経過)` })
              }, 5000) as unknown as number
            }

            try {
              let received = 0, lastProgress = Date.now()
              const onChunk = useStreaming
                ? (chunk: string, kind: 'content' | 'reasoning') => {
                    received += chunk.length
                    if (Date.now() - lastProgress < 3500) return
                    lastProgress = Date.now()
                    send('log', { message: kind === 'reasoning'
                      ? `推論中... (${received} chars)`
                      : `応答受信中... (${received} chars)` })
                  }
                : undefined

              const raw = await callDeepSeek(prompt, onChunk)
              data = extractJson(raw)
              if (data) break
              lastFailure = `JSON 抽出失敗: ${raw.replace(/\s+/g, ' ').slice(0, 180)}`
              send('log', { level: 'warn', message: `${lastFailure}。リトライします。` })
            } catch (e) {
              lastFailure = String(e)
              send('log', { level: 'error', message: `DeepSeek エラー: ${lastFailure}` })
              if (attempt < 3) {
                send('log', { message: '5秒後にリトライします...' })
                await new Promise(r => setTimeout(r, 5000))
              }
            } finally {
              if (keepAliveTimer !== null) clearInterval(keepAliveTimer)
            }
          }

          if (!data) {
            send('log', { level: 'error', message: `生成失敗 (${i + 1}問目): ${lastFailure}` })
            continue
          }

          data.id = randomHex(6)

          // R1はフラット構造 { statement, answer, solution_outline, difficulty, verification }
          // V3は { final_problem: { statement, answer, ... }, beauty_analysis: { total, ... } }
          // → 両方を final_problem フィールドに正規化
          if (isR1 && !data.final_problem) {
            data.final_problem = {
              statement:        data.statement,
              answer:           data.answer,
              solution_outline: data.solution_outline,
              difficulty:       data.difficulty ?? 'B',
            }
            data.beauty_analysis = {
              surprise: 7, minimality: 8, connection_strength: 8,
              inevitability: 8, difficulty_calibration: 7, total: 7.6,
              comment: 'R1生成',
            }
          }

          const fp        = (data.final_problem ?? {}) as Record<string, unknown>
          const statement = String(fp.statement ?? '')
          const answer    = String(fp.answer    ?? '')
          const solution  = String(fp.solution_outline
            ?? (data.verification as Record<string, unknown>)?.computation ?? '')
          const score     = (data.beauty_analysis as Record<string, unknown>)?.total ?? '?'

          // ── 検証 ────────────────────────────────────────────────
          const embedded = (data.verification ?? {}) as Record<string, unknown>
          let verificationPassed = true

          if (embedded.problem_well_posed === false) {
            send('log', { level: 'warn',
              message: `⚠ モデルが問題不成立を報告: ${embedded.issues_found ?? '詳細不明'}。スキップします。` })
            verificationPassed = false
          } else {
            send('status', { step: 'verifying', message: `数学的妥当性を検証中... (${i + 1}/${totalCount})` })
            try {
              const vRaw    = await callDeepSeek(
                makeVerificationPrompt(statement, answer, solution),
                undefined, FAST_MAX_TOKENS, FAST_MODEL,
              )
              const vResult = extractJson(vRaw) as Record<string, unknown> | null
              if (vResult) {
                const verdict     = String(vResult.verdict ?? 'UNKNOWN').toUpperCase()
                const confidence  = Number(vResult.confidence ?? 5)
                const wellPosed   = vResult.problem_well_posed
                const matches     = vResult.answer_matches

                if (verdict === 'FAIL' || wellPosed === false || confidence < 5 || matches === false) {
                  send('log', { level: 'warn',
                    message: `⚠ 検証失敗 (verdict=${verdict}, confidence=${confidence}): ${vResult.issues ?? ''}。スキップします。` })
                  verificationPassed = false
                } else {
                  send('log', { message: `✓ 検証OK (verdict=${verdict}, confidence=${confidence})` })
                  if (vResult.derived_answer && matches === true) fp.answer = vResult.derived_answer
                }
              }
            } catch (e) {
              send('log', { level: 'warn', message: `検証エラー（保存は続行）: ${e}` })
            }
          }

          if (!verificationPassed) continue

          if (dry_run) {
            send('log', { message: `dry run: スキップ score=${score} -> ${statement.slice(0, 50)}...` })
            generated.push({ id: data.id as string, statement })
          } else {
            send('status', { step: 'saving', message: 'Supabase に保存中...' })
            try {
              const saved = await saveToSupabase(supabase, data, parents, resolvedMode, nextGen, userId)
              send('log', { message: `保存完了 score=${score} -> ${saved.statement.slice(0, 50)}...` })
              generated.push(saved)
              if (userId && !isAdmin)
                await incrementUsage(supabase, userId).catch(() => {})
            } catch (e) {
              send('log', { level: 'error', message: `保存エラー: ${e}` })
            }
          }
        }

        // ── 淘汰 ──────────────────────────────────────────────────
        if (!dry_run) {
          send('status', { step: 'purging', message: '未選択問題を自動淘汰中...' })
          try {
            const purge = await purgeUnselectedProblems(supabase, generated.map(p => p.id))
            send('log', { message: purge.deleted > 0
              ? `淘汰完了: ${purge.deleted} 問削除 (${purge.considered} 問確認)`
              : `淘汰対象なし (${purge.considered} 問確認)` })
          } catch (e) {
            send('log', { level: 'error', message: `淘汰エラー: ${e}` })
          }
        }

        const ok = generated.length > 0
        send('done', {
          ok,
          generated: generated.length,
          total:     totalCount,
          message:   ok
            ? `完了: ${generated.length}/${totalCount} 問生成`
            : `失敗: 0/${totalCount} 問生成。ログを確認してください。`,
        })
      } catch (e) {
        send('error', { step: 'error', message: String(e), ok: false })
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      ...corsHeaders,
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection':    'keep-alive',
    },
  })
})
