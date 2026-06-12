/**
 * Level 2-3: TikZ 自動生成
 * POST /api/tikz  { problem_id?, statement?, type? }
 * type: 'auto' | 'passage_region' | 'solid' | 'graph'
 *
 * → Claude で TikZ コードを生成 → Supabase に保存 → TikZ ソースを返す
 */
import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { supabaseAdmin } from '@/lib/supabase-admin'

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY! })

// ── TikZ 生成プロンプト ────────────────────────────────────────────────────

function buildPrompt(statement: string, type: string): string {
  const BASE = `あなたは数学問題の図を TikZ で描く専門家です。
問題文を読み、その本質的な幾何的状況を表す TikZ コードのみを出力してください。

ルール:
- \\begin{tikzpicture} ... \\end{tikzpicture} のみ出力（preamble不要）
- scale は適切に設定（大きすぎず小さすぎず）
- 軸、ラベル、グリッド線を適切に追加
- 日本語ラベルは使わない（英字・数式のみ）
- 説明文は不要。コードのみ返す`

  if (type === 'passage_region') {
    return `${BASE}

特に「通過領域」問題では:
- 動く図形を薄い色で数枚描く（例: fill opacity=0.1）
- 通過領域の境界を太線で強調
- 境界がリマソン曲線の場合は \\draw[domain=...] plot ({...},{...}) で描く

問題文:
${statement}`
  }

  if (type === 'solid') {
    return `${BASE}

特に「立体・断面」問題では:
- 3D っぽく見えるよう斜め射影（x方向に 0.4*cos(210°) 等）を使う
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

// ── メインハンドラ ────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { problem_id, statement: rawStatement, type: rawType } = body

  let statement = rawStatement ?? ''

  // problem_id が指定された場合は DB から取得
  if (problem_id && !statement) {
    const { data } = await supabaseAdmin
      .from('problems')
      .select('statement, meta')
      .eq('id', problem_id)
      .single()
    if (!data) return NextResponse.json({ error: 'Problem not found' }, { status: 404 })
    statement = data.statement
  }

  if (!statement) return NextResponse.json({ error: 'statement required' }, { status: 400 })

  const type = rawType ?? detectType(statement)
  const prompt = buildPrompt(statement, type)

  // Claude で TikZ 生成
  const msg = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 2048,
    messages: [{ role: 'user', content: prompt }],
  })

  const raw = msg.content[0].type === 'text' ? msg.content[0].text : ''

  // \\begin{tikzpicture}...\\end{tikzpicture} を抽出
  const match = raw.match(/\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\}/)
  const tikz = match ? match[0] : raw

  // DB に保存（meta フィールドを更新）
  if (problem_id) {
    const { data: cur } = await supabaseAdmin
      .from('problems').select('meta').eq('id', problem_id).single()
    const meta = cur?.meta ? JSON.parse(cur.meta) : {}
    meta.tikz = tikz
    meta.tikz_type = type
    meta.tikz_at = new Date().toISOString()
    await supabaseAdmin
      .from('problems')
      .update({ meta: JSON.stringify(meta) })
      .eq('id', problem_id)
  }

  return NextResponse.json({ tikz, type, problem_id })
}

/** GET /api/tikz?problem_id=xxx → キャッシュ済み TikZ を返す */
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('problem_id')
  if (!id) return NextResponse.json({ error: 'problem_id required' }, { status: 400 })

  const { data } = await supabaseAdmin
    .from('problems').select('meta').eq('id', id).single()
  const meta = data?.meta ? JSON.parse(data.meta) : {}

  if (!meta.tikz) return NextResponse.json({ error: 'No TikZ cached' }, { status: 404 })
  return NextResponse.json({ tikz: meta.tikz, type: meta.tikz_type })
}
