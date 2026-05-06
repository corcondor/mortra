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
  if (!apiKey) throw new Error('DEEPSEEK_API_KEY が設定されていません')

  const res = await fetch(DEEPSEEK_API_URL, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model:    MODEL,
      messages: [{ role: 'user', content: prompt }],
      stream:   !!onChunk,
      max_tokens: 8000,
    }),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`DeepSeek API error ${res.status}: ${err}`)
  }

  if (!onChunk) {
    const json = await res.json()
    return json.choices?.[0]?.message?.content ?? ''
  }

  // SSE ストリーミング
  const reader = res.body!.getReader()
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
      const send = (type: string, payload: Record<string, unknown>) => {
        try {
          controller.enqueue(encoder.encode(
            `data: ${JSON.stringify({ type, ...payload })}\n\n`
          ))
        } catch { /* closed */ }
      }

      await enqueue()
      send('status', { step: 'start', msg: `DeepSeek-R1 で ${resolvedMode} 生成開始（${count}問）` })

      const generated: Record<string, unknown>[] = []

      try {
        // 分析フェーズ（similar/expand かつ1問の場合）
        let analysis: Record<string, string> | undefined
        if (resolvedMode !== 'fusion' && parents.length === 1) {
          send('status', { step: 'analyzing', msg: '問題を深く分析中…' })
          const raw = await callDeepSeek(makeAnalysisPrompt(parents[0]))
          const a   = extractJson(raw)
          if (a) analysis = a as Record<string, string>
          send('log', { msg: `分析完了: ${analysis?.core_structure?.slice(0, 60) ?? 'OK'}` })
        }

        for (let i = 0; i < count; i++) {
          send('status', { step: 'generating', msg: `生成中… (${i + 1}/${count})` })

          let prompt: string
          if (resolvedMode === 'fusion') {
            prompt = makeFusionPrompt(parents)
          } else if (resolvedMode === 'expand') {
            prompt = makeExpandPrompt(parents[i % parents.length])
          } else {
            prompt = makeSimilarPrompt(parents[i % parents.length], analysis)
          }

          let data: Record<string, unknown> | null = null
          for (let attempt = 1; attempt <= 3; attempt++) {
            send('log', { msg: `API 呼び出し中… (試行 ${attempt}/3)` })
            try {
              const raw = await callDeepSeek(prompt)
              data = extractJson(raw)
              if (data) break
              send('log', { msg: `JSON 抽出失敗、リトライ…` })
            } catch (e) {
              send('log', { msg: `エラー: ${String(e)}` })
            }
          }

          if (data) {
            data.id = crypto.randomBytes(6).toString('hex')
            send('status', { step: 'saving', msg: '保存中…' })
            try {
              const saved = await saveToSupabase(data, parents, resolvedMode, nextGen)
              const score = (data.beauty_analysis as Record<string, unknown>)?.total ?? '?'
              send('log',    { msg: `✅ 保存完了 score=${score} → ${saved.statement.slice(0, 50)}…` })
              generated.push(data)
            } catch (e) {
              send('log', { msg: `保存エラー: ${String(e)}` })
            }
          } else {
            send('log', { msg: `❌ 生成失敗 (${i + 1}問目)` })
          }
        }

        send('done', {
          generated: generated.length,
          total:     count,
          msg:       `完了: ${generated.length}/${count} 問生成`,
        })
      } catch (e) {
        send('status', { step: 'error', msg: String(e) })
      } finally {
        dequeue()
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
