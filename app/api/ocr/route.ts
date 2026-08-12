/**
 * 写真 → LaTeX 書き起こし (TeX64 風)
 * POST /api/ocr  { image: "data:image/png;base64,...", quality?: 'standard'|'high' }
 * → { title, statement, solution, provider }
 *
 * Vision プロバイダ自動検出: ANTHROPIC_API_KEY > GEMINI_API_KEY > OPENAI_API_KEY
 * OCR providers are isolated from MORTRA's mathematical reasoning backend.
 */
import { NextRequest, NextResponse } from 'next/server'

export const maxDuration = 120

const SYSTEM = `あなたは数学の問題を正確に書き起こす専門家です。
画像内の数学問題（手書き・印刷どちらも）を読み取り、KaTeX/LaTeX互換に書き起こしてください。

ルール:
- インライン数式は $...$、別行立ては $$...$$
- 数式は画像に忠実に。曖昧な箇所は数学的に最も自然な解釈を選ぶ
- 問題文と解答が両方写っている場合は分離する
- 次のJSONのみを返す:
{"title": "問題の短いタイトル（10字程度）", "statement": "問題文のLaTeX", "solution": "解答のLaTeX（写っていなければ空文字）"}`

interface OcrResult { title: string; statement: string; solution: string }

function parseDataUrl(image: string): { mime: string; b64: string } {
  const m = image.match(/^data:([^;]+);base64,(.+)$/)
  if (!m) throw new Error('image must be a base64 data URL')
  return { mime: m[1], b64: m[2] }
}

function extractJson(text: string): OcrResult {
  const m = text.match(/\{[\s\S]*\}/)
  if (!m) throw new Error('モデル出力からJSONを抽出できませんでした')
  const obj = JSON.parse(m[0])
  return {
    title: obj.title ?? '無題',
    statement: obj.statement ?? '',
    solution: obj.solution ?? '',
  }
}

async function ocrAnthropic(key: string, mime: string, b64: string, high: boolean): Promise<OcrResult> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': key,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: high ? 'claude-sonnet-4-6' : 'claude-haiku-4-5-20251001',
      max_tokens: 4096,
      system: SYSTEM,
      messages: [{
        role: 'user',
        content: [
          { type: 'image', source: { type: 'base64', media_type: mime, data: b64 } },
          { type: 'text', text: '書き起こしてください。JSONのみ。' },
        ],
      }],
    }),
  })
  if (!res.ok) throw new Error(`Anthropic API ${res.status}: ${(await res.text()).slice(0, 200)}`)
  const data = await res.json()
  return extractJson(data.content?.[0]?.text ?? '')
}

async function ocrGemini(key: string, mime: string, b64: string, high: boolean): Promise<OcrResult> {
  const model = high ? 'gemini-2.5-pro' : 'gemini-2.5-flash'
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM }] },
        contents: [{
          parts: [
            { inlineData: { mimeType: mime, data: b64 } },
            { text: '書き起こしてください。JSONのみ。' },
          ],
        }],
      }),
    },
  )
  if (!res.ok) throw new Error(`Gemini API ${res.status}: ${(await res.text()).slice(0, 200)}`)
  const data = await res.json()
  return extractJson(data.candidates?.[0]?.content?.parts?.[0]?.text ?? '')
}

async function ocrOpenAI(key: string, _mime: string, b64DataUrl: string, high: boolean): Promise<OcrResult> {
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model: high ? 'gpt-4o' : 'gpt-4o-mini',
      max_tokens: 4096,
      messages: [
        { role: 'system', content: SYSTEM },
        {
          role: 'user',
          content: [
            { type: 'image_url', image_url: { url: b64DataUrl } },
            { type: 'text', text: '書き起こしてください。JSONのみ。' },
          ],
        },
      ],
    }),
  })
  if (!res.ok) throw new Error(`OpenAI API ${res.status}: ${(await res.text()).slice(0, 200)}`)
  const data = await res.json()
  return extractJson(data.choices?.[0]?.message?.content ?? '')
}

export async function POST(req: NextRequest) {
  const { image, quality } = await req.json()
  if (!image) return NextResponse.json({ error: 'image required' }, { status: 400 })

  const high = quality === 'high'

  try {
    const { mime, b64 } = parseDataUrl(image)

    const anthropicKey = process.env.ANTHROPIC_API_KEY
    const geminiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY
    const openaiKey = process.env.OPENAI_API_KEY

    let result: OcrResult
    let provider: string

    if (anthropicKey) {
      result = await ocrAnthropic(anthropicKey, mime, b64, high)
      provider = 'anthropic'
    } else if (geminiKey) {
      result = await ocrGemini(geminiKey, mime, b64, high)
      provider = 'gemini'
    } else if (openaiKey) {
      result = await ocrOpenAI(openaiKey, mime, image, high)
      provider = 'openai'
    } else {
      return NextResponse.json({
        error: '画像認識用のAPIキーが未設定です。Vercel の環境変数に ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY のいずれかを追加してください。',
      }, { status: 501 })
    }

    return NextResponse.json({ ...result, provider })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ error: msg }, { status: 502 })
  }
}
