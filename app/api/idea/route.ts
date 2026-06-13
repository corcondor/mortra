/**
 * 作問アイデアツリーの AI 支援 (DeepSeek)
 * POST /api/idea
 *   { mode: 'brushup',    outline }  → { outline }  アイデアの深掘り・整理
 *   { mode: 'problemize', outline }  → { title, statement, solution }  実問題化
 */
import { NextRequest, NextResponse } from 'next/server'

export const maxDuration = 120

const DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
const MODEL = process.env.DEEPSEEK_MODEL ?? 'deepseek-chat'

async function callDeepSeek(prompt: string, json: boolean): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY
  if (!apiKey) throw new Error('DEEPSEEK_API_KEY not set')

  const res = await fetch(DEEPSEEK_API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 4096,
      ...(json ? { response_format: { type: 'json_object' } } : {}),
      messages: [{ role: 'user', content: prompt }],
    }),
  })
  if (res.status === 402) {
    throw new Error('DeepSeek APIの残高が不足しています。platform.deepseek.com でチャージしてください。')
  }
  if (!res.ok) throw new Error(`DeepSeek error ${res.status}`)
  const data = await res.json()
  return data.choices?.[0]?.message?.content ?? ''
}

const BRUSHUP_PROMPT = (outline: string) => `あなたは難関大学入試数学の作問アドバイザーです。
以下は作問アイデアのアウトライン（インデント付き箇条書き）です。
構造を保ったまま、各アイデアを深掘り・具体化してください。

ルール:
- 同じインデント形式（先頭「- 」、子は2スペース下げ）で返す
- 既存の行は残しつつ、有望な枝に [素材] [方針] [類題] の子ノードを追加
- 数式は $...$ で書く
- 全体で40行以内
- アウトラインのみ返す。説明文不要

アウトライン:
${outline}`

const PROBLEMIZE_PROMPT = (outline: string) => `あなたは難関大学入試数学の作問者です。
以下の作問アイデアツリーから、最も有望な1問を完成させてください。

要件:
- 大学入試として完結した問題文（KaTeX互換LaTeX、インライン $...$、別行 $$...$$）
- 厳密な模範解答も作成
- 東大・京大レベルの品質。誘導小問 (1)(2) を付けてもよい

アイデアツリー:
${outline}

次のJSONのみを返せ:
{"title": "短いタイトル", "statement": "問題文LaTeX", "solution": "模範解答LaTeX"}`

export async function POST(req: NextRequest) {
  const { mode, outline } = await req.json()
  if (!outline?.trim()) return NextResponse.json({ error: 'outline required' }, { status: 400 })

  try {
    if (mode === 'brushup') {
      const text = await callDeepSeek(BRUSHUP_PROMPT(outline), false)
      // コードフェンス除去
      const cleaned = text.replace(/^```[a-z]*\n?/m, '').replace(/```\s*$/m, '').trim()
      return NextResponse.json({ outline: cleaned })
    }

    if (mode === 'problemize') {
      const text = await callDeepSeek(PROBLEMIZE_PROMPT(outline), true)
      const obj = JSON.parse(text)
      return NextResponse.json({
        title: obj.title ?? '無題',
        statement: obj.statement ?? '',
        solution: obj.solution ?? '',
      })
    }

    return NextResponse.json({ error: 'mode must be brushup | problemize' }, { status: 400 })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    const status = msg.includes('残高') ? 402 : 502
    return NextResponse.json({ error: msg }, { status })
  }
}
