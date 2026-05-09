import { NextRequest, NextResponse } from 'next/server'
import { ImageResponse } from 'next/og'

export const runtime = 'edge'

const WIDTH  = 1200
const HEIGHT = 628

// ── セグメント型 ──────────────────────────────────────────────────────────────
type Seg =
  | { type: 'text';  text: string }
  | { type: 'math';  latex: string; block: boolean }

// ── LaTeX デリミタを解析してセグメント配列に ──────────────────────────────────
function parseSegments(src: string): Seg[] {
  const segs: Seg[] = []
  // $$...$$ / \[...\] → block、 $...$ / \(...\) → inline
  const re = /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\$([^$\n]+?)\$|\\\(([^)]*?)\\\)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) segs.push({ type: 'text', text: src.slice(last, m.index) })
    const latex = (m[1] ?? m[2] ?? m[3] ?? m[4] ?? '').trim()
    if (latex) segs.push({ type: 'math', latex, block: !!(m[1] ?? m[2]) })
    last = m.index + m[0].length
  }
  if (last < src.length) segs.push({ type: 'text', text: src.slice(last) })
  return segs
}

// ── codecogs から PNG を base64 DataURL に変換 ───────────────────────────────
async function mathPng(latex: string): Promise<string | null> {
  try {
    const formula = `\\dpi{150}\\large ${latex}`
    const url = `https://latex.codecogs.com/png.image?${encodeURIComponent(formula)}`

    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 6000)
    let res: Response
    try {
      res = await fetch(url, { signal: controller.signal })
    } finally {
      clearTimeout(tid)
    }

    if (!res.ok) return null
    const buf = await res.arrayBuffer()
    const bytes = new Uint8Array(buf)

    // Uint8Array → base64（チャンク処理で stack overflow 回避）
    const chunks: string[] = []
    for (let i = 0; i < bytes.length; i += 4096) {
      chunks.push(String.fromCharCode(...bytes.subarray(i, Math.min(i + 4096, bytes.length))))
    }
    return `data:image/png;base64,${btoa(chunks.join(''))}`
  } catch {
    return null
  }
}

// ── PNG 取得失敗時の Unicode フォールバック ──────────────────────────────────
function texFallback(latex: string): string {
  return latex
    .replace(/\\alpha/g,      'α').replace(/\\beta/g,      'β')
    .replace(/\\gamma/g,      'γ').replace(/\\delta/g,      'δ')
    .replace(/\\epsilon/g,    'ε').replace(/\\varepsilon/g, 'ε')
    .replace(/\\zeta/g,       'ζ').replace(/\\eta/g,        'η')
    .replace(/\\theta/g,      'θ').replace(/\\vartheta/g,   'θ')
    .replace(/\\lambda/g,     'λ').replace(/\\mu/g,         'μ')
    .replace(/\\nu/g,         'ν').replace(/\\xi/g,         'ξ')
    .replace(/\\pi/g,         'π').replace(/\\rho/g,        'ρ')
    .replace(/\\sigma/g,      'σ').replace(/\\tau/g,        'τ')
    .replace(/\\phi/g,        'φ').replace(/\\varphi/g,     'φ')
    .replace(/\\chi/g,        'χ').replace(/\\psi/g,        'ψ')
    .replace(/\\omega/g,      'ω').replace(/\\Gamma/g,      'Γ')
    .replace(/\\Delta/g,      'Δ').replace(/\\Theta/g,      'Θ')
    .replace(/\\Lambda/g,     'Λ').replace(/\\Pi/g,         'Π')
    .replace(/\\Sigma/g,      'Σ').replace(/\\Phi/g,        'Φ')
    .replace(/\\Psi/g,        'Ψ').replace(/\\Omega/g,      'Ω')
    .replace(/\\infty/g,      '∞').replace(/\\times/g,      '×')
    .replace(/\\cdot/g,       '·').replace(/\\pm/g,         '±')
    .replace(/\\leq?/g,       '≤').replace(/\\geq?/g,       '≥')
    .replace(/\\neq?/g,       '≠').replace(/\\approx/g,     '≈')
    .replace(/\\sqrt\{([^{}]*)\}/g,           '√($1)')
    .replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, '($1)/($2)')
    .replace(/\\[a-zA-Z]+\{([^{}]*)\}/g,      '$1')
    .replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '')
    .trim()
}

// ── ブロック数式の高さ判定 ──────────────────────────────────────────────────
function mathImgHeight(latex: string, block: boolean, fontSize: number): number {
  if (block) return fontSize * 2.4
  if (/\\frac|\\sum|\\int|\\prod|\\binom|\\lim/.test(latex)) return fontSize * 1.9
  return fontSize * 1.2
}

// ── フォントサイズ（テキスト全体の長さ依存） ─────────────────────────────────
function stmtFontSize(len: number): number {
  if (len <= 120) return 34
  if (len <= 250) return 30
  if (len <= 400) return 26
  if (len <= 600) return 22
  return 19
}

function ansFontSize(len: number): number {
  if (len <= 80)  return 28
  if (len <= 180) return 24
  return 20
}

// ── API ──────────────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({})) as Record<string, unknown>
  const statement = typeof body.statement === 'string' ? body.statement.trim() : ''
  const answer    = typeof body.answer    === 'string' ? body.answer.trim()    : ''
  const topic     = typeof body.topic     === 'string' ? body.topic.trim()     : '数学'
  const score     = Number(body.score)

  if (!statement) {
    return NextResponse.json(
      { ok: false, error: 'statement required', code: 'STATEMENT_REQUIRED' },
      { status: 400 },
    )
  }

  const stSegs = parseSegments(statement)
  const anSegs = answer ? parseSegments(answer) : []

  // 全数式を重複排除して並列フェッチ
  const mathSet = new Set<string>()
  ;[...stSegs, ...anSegs].forEach(s => { if (s.type === 'math') mathSet.add(s.latex) })
  const mathList = [...mathSet]
  const fetched  = await Promise.allSettled(mathList.map(mathPng))

  const pngMap = new Map<string, string | null>()
  mathList.forEach((latex, i) => {
    const r = fetched[i]
    pngMap.set(latex, r.status === 'fulfilled' ? r.value : null)
  })

  const topicLabel = topic || '数学'
  const scoreLabel = Number.isFinite(score) ? score.toFixed(1) : '0.0'
  const sFontSize  = stmtFontSize(statement.length)
  const aFontSize  = ansFontSize(answer.length)

  // セグメント → JSX
  function renderSegs(segs: Seg[], fontSize: number, color: string) {
    return segs.map((seg, i) => {
      if (seg.type === 'text') {
        return (
          <span key={i} style={{ fontSize, color, lineHeight: 1.75, fontFamily: 'sans-serif' }}>
            {seg.text}
          </span>
        )
      }
      const png = pngMap.get(seg.latex)
      const h   = mathImgHeight(seg.latex, seg.block, fontSize)
      if (png) {
        return (
          <img
            key={i}
            src={png}
            style={{
              height: h,
              alignSelf: 'center',
              margin: seg.block ? '8px 0' : '0 2px',
            }}
          />
        )
      }
      // PNG 失敗 → Unicode フォールバック
      return (
        <span key={i} style={{ fontSize: fontSize * 0.88, color, fontFamily: 'serif', letterSpacing: 0.5 }}>
          {texFallback(seg.latex)}
        </span>
      )
    })
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: '#f8fafc',
          padding: 48,
          fontFamily: 'sans-serif',
          color: '#1e293b',
        }}
      >
        {/* ヘッダー */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 20,
            fontSize: 26,
            fontWeight: 700,
          }}
        >
          <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <span style={{ color: '#0a84ff' }}>Sakumon Station</span>
            <span style={{ color: '#94a3b8', fontWeight: 400 }}>{topicLabel}</span>
          </div>
          <span style={{ color: '#94a3b8', fontWeight: 400 }}>score {scoreLabel}</span>
        </div>

        {/* 問題カード */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            background: '#ffffff',
            borderRadius: 20,
            padding: '36px 52px',
            border: '1px solid #e2e8f0',
            boxShadow: '0 8px 28px rgba(15,23,42,0.09)',
            overflow: 'hidden',
          }}
        >
          {/* 問題文 */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              fontWeight: 600,
              gap: 3,
            }}
          >
            {renderSegs(stSegs, sFontSize, '#1e293b')}
          </div>

          {/* 解答（あれば） */}
          {anSegs.length > 0 && (
            <div
              style={{
                marginTop: 24,
                paddingTop: 20,
                borderTop: '2px solid #d1fae5',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: 3,
              }}
            >
              {renderSegs(anSegs, aFontSize, '#047857')}
            </div>
          )}
        </div>
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      headers: { 'Cache-Control': 'no-store' },
    },
  )
}
