import { NextRequest } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import {
  makeAnalysisPrompt, makeSimilarPrompt,
  makeFusionPrompt,   makeExpandPrompt,
  extractJson,        type ParentProblem,
} from '@/lib/prompts'
import crypto from 'crypto'

const DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
const MODEL            = 'deepseek-reasoner'   // DeepSeek-R1

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

type PurgeCandidate = {
  id: string
  rating?: { status?: string | null; x_posted?: boolean | null } | { status?: string | null; x_posted?: boolean | null }[] | null
}

function shouldPurge(candidate: PurgeCandidate, excludeIds: Set<string>) {
  if (excludeIds.has(candidate.id)) return false
  const rating = Array.isArray(candidate.rating) ? candidate.rating[0] : candidate.rating
  if (!rating) return true
  if (rating.x_posted === true) return false
  return rating.status !== 'selected' && rating.status !== 'posted'
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
async function callDeepSeek(prompt: string, onChunk?: (s: string) => void): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) {
    throw new Error('DEEPSEEK_API_KEY が設定されていません。Vercel/ローカルの環境変数を確認してください。')
  }

  let res: Response
  try {
    res = await fetch(DEEPSEEK_API_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model:    MODEL,
        messages: [{ role: 'user', content: prompt }],
        stream:   !!onChunk,
        max_tokens: 8000,
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
    const json = await res.json()
    return json.choices?.[0]?.message?.content ?? ''
  }

  // SSE ストリーミング
  if (!res.body) throw new Error('DeepSeek streaming response body が空です')

  const reader = res.body.getReader()
  const dec    = new TextDecoder()
  let full = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    for (const line of dec.decode(value).split('\n')) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') break
      try {
        const delta = JSON.parse(data).choices?.[0]?.delta?.content
        if (delta) { full += delta; onChunk(delta) }
      } catch { /* skip */ }
    }
  }
  return full
}

// ── Supabase に保存 ────────────────────────────────────────────────────
async function saveToSupabase(data: Record<string, unknown>, parents: ParentProblem[], mode: string, nextGen: number) {
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

  const { error: rErr } = await supabaseAdmin.from('ratings').upsert({
    problem_id: id, status: 'pending', x_posted: false,
  }, { onConflict: 'problem_id', ignoreDuplicates: true })
  if (rErr) throw new Error(rErr.message)

  return problem
}

// ── GET: キュー状態確認 ────────────────────────────────────────────────
export function GET() {
  return Response.json({ queueLength: _queue.length, busy: _busy })
}

// ── POST: 生成 ─────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  const { parents, mode = 'auto', count = 3 } = await req.json() as {
    parents: ParentProblem[]
    mode?:   string
    count?:  number
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
      send('status', { step: 'start', message: `DeepSeek-R1 で ${resolvedMode} 生成開始（${totalCount}問）` })

      const generated: Awaited<ReturnType<typeof saveToSupabase>>[] = []

      try {
        // 分析フェーズ（similar/expand かつ1問の場合）
        let analysis: Record<string, string> | undefined
        if (resolvedMode !== 'fusion' && parents.length === 1) {
          send('status', { step: 'analyzing', message: '問題を深く分析中...' })
          const raw = await callDeepSeek(makeAnalysisPrompt(parents[0]))
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
            send('log', { message: `DeepSeek API 呼び出し中... (試行 ${attempt}/3)` })
            try {
              const raw = await callDeepSeek(prompt)
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
            send('status', { step: 'saving', message: 'Supabase に保存中...' })
            try {
              const saved = await saveToSupabase(data, parents, resolvedMode, nextGen)
              const score = (data.beauty_analysis as Record<string, unknown>)?.total ?? '?'
              send('log',    { message: `保存完了 score=${score} -> ${saved.statement.slice(0, 50)}...` })
              generated.push(saved)
            } catch (e) {
              send('log', { level: 'error', message: `保存エラー: ${errorMessage(e)}` })
            }
          } else {
            send('log', { level: 'error', message: `生成失敗 (${i + 1}問目): ${lastFailure || 'JSON を取得できませんでした'}` })
          }
        }

        // ── 自動淘汰: selected/posted 以外を削除 ─────────────────────
        send('status', { step: 'purging', message: '未選択問題を自動淘汰中...' })
        let purgeDeleted = 0
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
