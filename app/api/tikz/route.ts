/**
 * Level 2-3: TikZ 自動生成（コンパイル検証付き）
 * POST /api/tikz  { problem_id?, statement?, type? }
 * type: 'auto' | 'passage_region' | 'solid' | 'graph'
 *
 * DeepSeek で TikZ 生成 → texlive.net で実コンパイル検証 →
 * 失敗時はエラーログを渡して1回リトライ → 成功したものだけキャッシュ
 */
import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { buildTikzStandalone, compileTex } from '@/lib/latex'

export const maxDuration = 120

const DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
const MODEL = process.env.DEEPSEEK_MODEL ?? 'deepseek-chat'

// ── TikZ 生成プロンプト ────────────────────────────────────────────────────

function buildPrompt(statement: string, type: string): string {
  const BASE = `あなたは数学問題の図を TikZ で描く専門家です。
問題文を読み、その本質的な幾何的状況を表す TikZ コードのみを出力してください。

ルール:
- \\begin{tikzpicture} ... \\end{tikzpicture} のみ出力（preamble不要）
- 使用可能な TikZ ライブラリは calc, arrows.meta, intersections, patterns, decorations.markings のみ
- pgfplots や外部パッケージは使用禁止
- 図中に日本語文字を使わない（英字・数式のみ。数式は $...$ で）
- scale は適切に設定（大きすぎず小さすぎず）
- 軸、ラベルを適切に追加
- 説明文は不要。コードのみ返す`

  if (type === 'passage_region') {
    return `${BASE}

特に「通過領域」問題では:
- 動く図形を薄い色で数枚描く（例: fill opacity=0.1）
- 通過領域の境界を太線で強調
- 境界が媒介変数曲線の場合は \\draw[domain=...] plot ({...},{...}) で描く

問題文:
${statement}`
  }

  if (type === 'solid') {
    return `${BASE}

特に「立体・断面」問題では:
- 3D っぽく見えるよう斜め射影（x方向に 0.4*cos(210) 等）を使う
- 断面は fill=gray!30 で表示
- 不可視辺は dashed

問題文:
${statement}`
  }

  return `${BASE}

問題の種類を自動判定して最適な図を描いてください。

問題文:
${statement}`
}

// ── 問題タイプの自動判定 ──────────────────────────────────────────────────

function detectType(statement: string): string {
  if (/通過領域|軌跡|動く/.test(statement)) return 'passage_region'
  if (/立体|断面|球|四面体|正六面体/.test(statement)) return 'solid'
  if (/グラフ|関数|曲線|放物線/.test(statement)) return 'graph'
  return 'auto'
}

// ── DeepSeek 呼び出し ─────────────────────────────────────────────────────

async function callDeepSeek(messages: { role: string; content: string }[]): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) throw new Error('DEEPSEEK_API_KEY not set')

  const res = await fetch(DEEPSEEK_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model: MODEL, max_tokens: 2048, messages }),
  })

  if (res.status === 402) {
    throw new Error('DeepSeek APIの残高が不足しています。platform.deepseek.com でチャージしてください。')
  }
  if (!res.ok) {
    throw new Error(`DeepSeek error ${res.status}: ${(await res.text()).slice(0, 200)}`)
  }

  const data = await res.json()
  return data.choices?.[0]?.message?.content ?? ''
}

function extractTikz(raw: string): string | null {
  const match = raw.match(/\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\}/)
  return match ? match[0] : null
}

// ── メインハンドラ ────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { problem_id, statement: rawStatement, type: rawType } = body

  let statement = rawStatement ?? ''

  if (problem_id && !statement) {
    const { data } = await supabaseAdmin
      .from('problems')
      .select('statement')
      .eq('id', problem_id)
      .single()
    if (!data) return NextResponse.json({ error: 'Problem not found' }, { status: 404 })
    statement = data.statement
  }

  if (!statement) return NextResponse.json({ error: 'statement required' }, { status: 400 })

  const type = rawType ?? detectType(statement)
  const prompt = buildPrompt(statement, type)

  try {
    const messages = [{ role: 'user', content: prompt }]
    let raw = await callDeepSeek(messages)
    let tikz = extractTikz(raw)
    if (!tikz) {
      return NextResponse.json({ error: 'TikZコードを抽出できませんでした' }, { status: 502 })
    }

    // ── コンパイル検証（失敗時はログを渡して1回リトライ） ──
    let verified = false
    let compileLog = ''
    for (let attempt = 0; attempt < 2; attempt++) {
      const result = await compileTex(buildTikzStandalone(tikz), 'pdflatex')
      if (result.ok) { verified = true; break }
      compileLog = result.log ?? ''
      if (attempt === 0) {
        messages.push({ role: 'assistant', content: tikz })
        messages.push({
          role: 'user',
          content: `このTikZコードはコンパイルに失敗しました。エラー:\n${compileLog}\n\n修正した完全なtikzpicture環境のみを返してください。`,
        })
        raw = await callDeepSeek(messages)
        const fixed = extractTikz(raw)
        if (fixed) tikz = fixed
      }
    }

    if (!verified) {
      return NextResponse.json(
        { error: 'TikZのコンパイルに失敗しました（2回試行）', log: compileLog.slice(0, 800) },
        { status: 422 },
      )
    }

    // DB にキャッシュ（検証済みのみ）
    if (problem_id) {
      const { data: cur } = await supabaseAdmin
        .from('problems').select('meta').eq('id', problem_id).single()
      let meta: Record<string, unknown> = {}
      try { meta = cur?.meta ? JSON.parse(cur.meta) : {} } catch { /* 旧形式 */ }
      meta.tikz = tikz
      meta.tikz_type = type
      meta.tikz_verified = true
      meta.tikz_at = new Date().toISOString()
      await supabaseAdmin
        .from('problems')
        .update({ meta: JSON.stringify(meta) })
        .eq('id', problem_id)
    }

    return NextResponse.json({ tikz, type, problem_id, verified: true })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    const status = msg.includes('残高') ? 402 : 502
    return NextResponse.json({ error: msg }, { status })
  }
}

/** GET /api/tikz?problem_id=xxx → キャッシュ済み TikZ を返す */
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('problem_id')
  if (!id) return NextResponse.json({ error: 'problem_id required' }, { status: 400 })

  const { data } = await supabaseAdmin
    .from('problems').select('meta').eq('id', id).single()
  let meta: Record<string, unknown> = {}
  try { meta = data?.meta ? JSON.parse(data.meta) : {} } catch { /* 旧形式 */ }

  if (!meta.tikz) return NextResponse.json({ error: 'No TikZ cached' }, { status: 404 })
  return NextResponse.json({ tikz: meta.tikz, type: meta.tikz_type, verified: !!meta.tikz_verified })
}
