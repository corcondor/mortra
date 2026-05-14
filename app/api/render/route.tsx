import { NextRequest, NextResponse } from 'next/server'
import { ImageResponse } from 'next/og'

export const runtime = 'edge'

const WIDTH   = 1200
const HEIGHT  = 628
// カード内コンテンツの最大幅（外padding 48×2 + 内padding 52×2 = 200）
const CONTENT_W = WIDTH - 48 * 2 - 52 * 2   // 1000px

// ── セグメント型 ──────────────────────────────────────────────────────────────
type Seg =
  | { type: 'text'; text: string }
  | { type: 'math'; latex: string; block: boolean }

// ── LaTeX デリミタを解析してセグメント配列に ──────────────────────────────────
function parseSegments(src: string): Seg[] {
  const segs: Seg[] = []
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
// DPI は表示フォントサイズに合わせて調整する
// codecogs の \normalsize (10pt) の高さ ≈ DPI/72*10 px
// → targetPx と合わせるには DPI = targetPx * 7.2 だが上限を設ける
async function mathPng(latex: string, targetFontPx: number): Promise<string | null> {
  try {
    // normalsize で targetFontPx の高さになるよう DPI を計算（80〜160 にクランプ）
    const dpi     = Math.min(160, Math.max(80, Math.round(targetFontPx * 6.5)))
    const sizeCmd = targetFontPx >= 30 ? '\\normalsize' : '\\small'
    const formula = `\\dpi{${dpi}}\\color{1e293b}${sizeCmd} ${latex}`
    const url     = `https://latex.codecogs.com/png.image?${encodeURIComponent(formula)}`

    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 6000)
    let res: Response
    try {
      res = await fetch(url, { signal: controller.signal })
    } finally {
      clearTimeout(tid)
    }

    if (!res.ok) return null
    const buf   = await res.arrayBuffer()
    const bytes = new Uint8Array(buf)
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
    .replace(/\\gamma/g,      'γ').replace(/\\delta/g,     'δ')
    .replace(/\\epsilon/g,    'ε').replace(/\\varepsilon/g,'ε')
    .replace(/\\zeta/g,       'ζ').replace(/\\eta/g,       'η')
    .replace(/\\theta/g,      'θ').replace(/\\vartheta/g,  'θ')
    .replace(/\\lambda/g,     'λ').replace(/\\mu/g,        'μ')
    .replace(/\\nu/g,         'ν').replace(/\\xi/g,        'ξ')
    .replace(/\\pi/g,         'π').replace(/\\rho/g,       'ρ')
    .replace(/\\sigma/g,      'σ').replace(/\\tau/g,       'τ')
    .replace(/\\phi/g,        'φ').replace(/\\varphi/g,    'φ')
    .replace(/\\chi/g,        'χ').replace(/\\psi/g,       'ψ')
    .replace(/\\omega/g,      'ω').replace(/\\Gamma/g,     'Γ')
    .replace(/\\Delta/g,      'Δ').replace(/\\Theta/g,     'Θ')
    .replace(/\\Lambda/g,     'Λ').replace(/\\Pi/g,        'Π')
    .replace(/\\Sigma/g,      'Σ').replace(/\\Phi/g,       'Φ')
    .replace(/\\Psi/g,        'Ψ').replace(/\\Omega/g,     'Ω')
    .replace(/\\infty/g,      '∞').replace(/\\times/g,     '×')
    .replace(/\\cdot/g,       '·').replace(/\\pm/g,        '±')
    .replace(/\\leq?/g,       '≤').replace(/\\geq?/g,      '≥')
    .replace(/\\neq?/g,       '≠').replace(/\\approx/g,    '≈')
    .replace(/\\sqrt\{([^{}]*)\}/g,            '√($1)')
    .replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g,'($1)/($2)')
    .replace(/\\[a-zA-Z]+\{([^{}]*)\}/g,       '$1')
    .replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '')
    .trim()
}

// ── フォントサイズ（文字数依存） ─────────────────────────────────────────────
function stmtFontSize(len: number): number {
  if (len <= 100) return 34
  if (len <= 220) return 30
  if (len <= 380) return 26
  if (len <= 550) return 22
  return 19
}


// ── 日本語フォント読み込み（Satori の文字化け防止） ──────────────────────────
async function loadJapaneseFont(): Promise<ArrayBuffer | null> {
  try {
    // Step1: CSS から woff2 URL を取得（3 s タイムアウト）
    const ac1 = new AbortController()
    const t1  = setTimeout(() => ac1.abort(), 3000)
    let css: string
    try {
      css = await fetch(
        'https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400',
        {
          headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
          signal: ac1.signal,
        }
      ).then(r => r.text())
    } finally {
      clearTimeout(t1)
    }

    // latin サブセットの URL を探す（CJK は容量大のため除外）
    const latinMatch = css.match(/\/\* latin \*\/[\s\S]*?url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.woff2)\)/)
    const anyMatch   = css.match(/url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.woff2)\)/)
    const woff2Url   = (latinMatch?.[1] ?? anyMatch?.[1]) ?? null
    if (!woff2Url) return null

    // Step2: woff2 バイナリを取得（4 s タイムアウト・別 AbortController）
    const ac2 = new AbortController()
    const t2  = setTimeout(() => ac2.abort(), 4000)
    try {
      return await fetch(woff2Url, { signal: ac2.signal }).then(r => r.arrayBuffer())
    } finally {
      clearTimeout(t2)
    }
  } catch {
    return null
  }
}

// ── API ──────────────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  const body      = await req.json().catch(() => ({})) as Record<string, unknown>
  const statement = typeof body.statement === 'string' ? body.statement.trim() : ''
  // answer は投稿画像には含めない（X投稿では問題文のみ表示）
  const topic     = typeof body.topic     === 'string' ? body.topic.trim()     : '数学'
  const score     = Number(body.score)

  if (!statement) {
    return NextResponse.json(
      { ok: false, error: 'statement required', code: 'STATEMENT_REQUIRED' },
      { status: 400 },
    )
  }

  const sFontSize = stmtFontSize(statement.length)

  const stSegs = parseSegments(statement)

  // 数式を (latex, targetFontPx) のペアで重複排除してフェッチ
  type MathKey = string  // `${latex}__${targetPx}`
  const mathMap = new Map<MathKey, { latex: string; targetPx: number }>()
  stSegs.forEach(s => { if (s.type === 'math') { const k = `${s.latex}__${sFontSize}`; mathMap.set(k, { latex: s.latex, targetPx: sFontSize }) } })

  const mathEntries  = [...mathMap.entries()]

  // 数式 PNG フェッチとフォント読み込みを並列実行（edge timeout 節約）
  const [fetchResults, fontData] = await Promise.all([
    Promise.allSettled(
      mathEntries.map(([, { latex, targetPx }]) => mathPng(latex, targetPx))
    ),
    loadJapaneseFont(),
  ])

  const pngMap = new Map<MathKey, string | null>()
  mathEntries.forEach(([key], i) => {
    const r = fetchResults[i]
    pngMap.set(key, r.status === 'fulfilled' ? r.value : null)
  })

  const topicLabel = topic || '数学'
  const scoreLabel = Number.isFinite(score) ? score.toFixed(1) : '0.0'

  // ── セグメント → JSX ─────────────────────────────────────────────────────
  // block 数式はフレックスラインを占有するよう flexBasis:'100%' で折り返させる
  function renderSegs(segs: Seg[], fontSize: number, color: string) {
    return segs.map((seg, i) => {
      if (seg.type === 'text') {
        return (
          <span key={i} style={{ fontSize, color, lineHeight: 1.75, fontFamily: "'Noto Sans JP', sans-serif", flexShrink: 1 }}>
            {seg.text}
          </span>
        )
      }

      const pngKey = `${seg.latex}__${fontSize}`
      const png    = pngMap.get(pngKey)

      if (seg.block) {
        // ── ブロック数式：1行占有・中央揃え ──────────────────────────────
        // maxWidth で幅を抑え、height: auto でアスペクト比を維持
        const maxH = fontSize * 2.8
        if (png) {
          return (
            <div key={i} style={{
              display:       'flex',
              justifyContent:'center',
              alignItems:    'center',
              flexBasis:     '100%',
              margin:        '10px 0',
            }}>
              <img
                src={png}
                style={{
                  maxWidth:  CONTENT_W,
                  maxHeight: maxH,
                  width:     'auto',
                  height:    'auto',
                }}
              />
            </div>
          )
        }
        return (
          <span key={i} style={{
            fontSize:   fontSize * 0.9,
            color,
            fontFamily: 'serif',
            flexBasis:  '100%',
            textAlign:  'center',
            margin:     '6px 0',
          }}>
            {texFallback(seg.latex)}
          </span>
        )
      }

      // ── インライン数式：高さをテキストに揃え・幅は最大 50% まで ─────────
      const maxInlineH = fontSize * 1.6
      const maxInlineW = Math.round(CONTENT_W * 0.55)
      if (png) {
        return (
          <img
            key={i}
            src={png}
            style={{
              maxHeight:   maxInlineH,
              maxWidth:    maxInlineW,
              width:       'auto',
              height:      'auto',
              alignSelf:   'center',
              margin:      '0 3px',
              flexShrink:  0,
            }}
          />
        )
      }
      return (
        <span key={i} style={{ fontSize: fontSize * 0.88, color, fontFamily: 'serif' }}>
          {texFallback(seg.latex)}
        </span>
      )
    })
  }

  try {
  return new ImageResponse(
    (
      <div
        style={{
          width:       '100%',
          height:      '100%',
          display:     'flex',
          flexDirection:'column',
          background:  '#f8fafc',
          padding:     48,
          fontFamily:  'sans-serif',
          color:       '#1e293b',
        }}
      >
        {/* ヘッダー */}
        <div style={{
          display:        'flex',
          alignItems:     'center',
          justifyContent: 'space-between',
          marginBottom:   20,
          fontSize:       24,
          fontWeight:     700,
        }}>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <span style={{ color: '#0a84ff' }}>Sakumon Station</span>
            <span style={{ color: '#94a3b8', fontWeight: 400 }}>{topicLabel}</span>
          </div>
          <span style={{ color: '#94a3b8', fontWeight: 400 }}>score {scoreLabel}</span>
        </div>

        {/* 問題カード */}
        <div style={{
          flex:          1,
          display:       'flex',
          flexDirection: 'column',
          justifyContent:'center',
          background:    '#ffffff',
          borderRadius:  20,
          padding:       '36px 52px',
          border:        '1px solid #e2e8f0',
          boxShadow:     '0 8px 28px rgba(15,23,42,0.09)',
          overflow:      'hidden',
        }}>
          {/* 問題文のみ（解答は含めない） */}
          <div style={{
            display:    'flex',
            flexWrap:   'wrap',
            alignItems: 'center',
            fontWeight: 600,
            gap:        4,
            maxWidth:   CONTENT_W,
          }}>
            {renderSegs(stSegs, sFontSize, '#1e293b')}
          </div>
        </div>
      </div>
    ),
    {
      width:   WIDTH,
      height:  HEIGHT,
      headers: { 'Cache-Control': 'no-store' },
      ...(fontData ? {
        fonts: [{
          name:   'Noto Sans JP',
          data:   fontData,
          weight: 400 as const,
          style:  'normal' as const,
        }],
      } : {}),
    },
  )
  } catch (err) {
    console.error('[render] ImageResponse error:', err)
    return NextResponse.json(
      { ok: false, error: String(err) },
      { status: 500 },
    )
  }
}
