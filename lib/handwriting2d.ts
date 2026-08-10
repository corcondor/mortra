/**
 * 文字を 2D の筆跡にする。
 *
 * ブラウザのフォントで一文字ずつ出すと「表示された」ようにしか見えない。
 * KanjiVG は 1画 = 1パスの中心線なので、なぞれば「書いた」ように見える。
 * しかも筆順が人間と同じ。
 *
 * 輪郭フォント（TTF/OTF）は字の縁を囲む閉曲線なので、なぞると塗り絵になる。
 * だから使わない。
 */

import glyphs from '../data/strokes/ja.json'

export type Pt = { x: number; y: number }

type Glyph = { view: number; strokes: string[] }
const JA = glyphs as Record<string, Glyph>

// ── SVG パス → 折れ線 ───────────────────────────────────────────────
// KanjiVG が使うのは M/m L/l C/c S/s Z/z のみ。

function bezier(p0: Pt, p1: Pt, p2: Pt, p3: Pt, steps: number): Pt[] {
  const out: Pt[] = []
  for (let i = 1; i <= steps; i++) {
    const t = i / steps, u = 1 - t
    out.push({
      x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
      y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
    })
  }
  return out
}

export function parsePath(d: string, steps = 6): Pt[] {
  const tokens = d.match(/[MmLlCcSsZz]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) ?? []
  const points: Pt[] = []
  let i = 0, command = ''
  let current: Pt = { x: 0, y: 0 }
  let lastControl: Pt | null = null
  const num = () => parseFloat(tokens[i++])

  while (i < tokens.length) {
    if (/[MmLlCcSsZz]/.test(tokens[i])) { command = tokens[i]; i++ }
    switch (command) {
      case 'M': case 'm': {
        const x = num(), y = num()
        current = command === 'M' ? { x, y } : { x: current.x + x, y: current.y + y }
        points.push({ ...current })
        command = command === 'M' ? 'L' : 'l'
        lastControl = null
        break
      }
      case 'L': case 'l': {
        const x = num(), y = num()
        current = command === 'L' ? { x, y } : { x: current.x + x, y: current.y + y }
        points.push({ ...current })
        lastControl = null
        break
      }
      case 'C': case 'c': {
        const rel = command === 'c'
        const c1 = { x: num(), y: num() }, c2 = { x: num(), y: num() }, e = { x: num(), y: num() }
        const a = rel ? { x: current.x + c1.x, y: current.y + c1.y } : c1
        const b = rel ? { x: current.x + c2.x, y: current.y + c2.y } : c2
        const end = rel ? { x: current.x + e.x, y: current.y + e.y } : e
        points.push(...bezier(current, a, b, end, steps))
        lastControl = b; current = end
        break
      }
      case 'S': case 's': {
        const rel = command === 's'
        const c2 = { x: num(), y: num() }, e = { x: num(), y: num() }
        const b = rel ? { x: current.x + c2.x, y: current.y + c2.y } : c2
        const end = rel ? { x: current.x + e.x, y: current.y + e.y } : e
        const a = lastControl
          ? { x: 2 * current.x - lastControl.x, y: 2 * current.y - lastControl.y }
          : current
        points.push(...bezier(current, a, b, end, steps))
        lastControl = b; current = end
        break
      }
      default: i++
    }
  }
  return points
}

// ── ASCII と記号（単線。輪郭データが要らない）────────────────────────
// 0..1 の升目。y は下向き（KanjiVG に合わせる）。

type Line = Array<[number, number]>
const A: Record<string, Line[]> = {
  '0': [[[.2,.16],[.78,.16],[.78,.86],[.2,.86],[.2,.16]]],
  '1': [[[.32,.3],[.5,.12],[.5,.88]]],
  '2': [[[.18,.26],[.5,.12],[.8,.32],[.18,.88],[.82,.88]]],
  '3': [[[.18,.16],[.78,.16],[.44,.5],[.8,.66],[.5,.88],[.18,.78]]],
  '4': [[[.68,.88],[.68,.12],[.18,.66],[.86,.66]]],
  '5': [[[.8,.12],[.24,.12],[.2,.46],[.58,.44],[.8,.66],[.5,.88],[.18,.8]]],
  '6': [[[.76,.16],[.38,.16],[.2,.6],[.5,.88],[.8,.7],[.58,.5],[.24,.55]]],
  '7': [[[.18,.14],[.82,.14],[.42,.88]]],
  '8': [[[.5,.12],[.24,.3],[.5,.48],[.76,.3],[.5,.12]],[[.5,.48],[.22,.68],[.5,.88],[.78,.68],[.5,.48]]],
  '9': [[[.76,.46],[.42,.5],[.24,.3],[.5,.12],[.78,.34],[.72,.74],[.38,.88]]],
  '=': [[[.16,.4],[.84,.4]],[[.16,.62],[.84,.62]]],
  '+': [[[.5,.24],[.5,.76]],[[.22,.5],[.78,.5]]],
  '-': [[[.18,.5],[.82,.5]]],
  '/': [[[.22,.88],[.78,.14]]],
  '→': [[[.1,.5],[.86,.5]],[[.68,.36],[.88,.5],[.68,.64]]],
  '△': [[[.5,.12],[.88,.86],[.12,.86],[.5,.12]]],
  'A': [[[.14,.88],[.5,.12],[.86,.88]],[[.27,.6],[.73,.6]]],
  'B': [[[.2,.88],[.2,.12],[.68,.17],[.68,.46],[.2,.5]],[[.2,.5],[.74,.55],[.74,.84],[.2,.88]]],
  'C': [[[.8,.22],[.5,.12],[.2,.36],[.2,.68],[.5,.88],[.8,.8]]],
  'H': [[[.22,.12],[.22,.88]],[[.78,.12],[.78,.88]],[[.22,.5],[.78,.5]]],
  'N': [[[.22,.88],[.22,.12],[.78,.88],[.78,.12]]],
  'O': [[[.5,.12],[.2,.34],[.2,.66],[.5,.88],[.8,.66],[.8,.34],[.5,.12]]],
  'R': [[[.22,.88],[.22,.12],[.7,.18],[.7,.44],[.22,.48]],[[.42,.48],[.76,.88]]],
  'P': [[[.22,.88],[.22,.12],[.72,.19],[.72,.47],[.22,.52]]],
  'M': [[[.16,.88],[.16,.12],[.5,.56],[.84,.12],[.84,.88]]],
  'a': [[[.74,.42],[.42,.36],[.26,.56],[.36,.86],[.72,.8]],[[.74,.36],[.74,.88]]],
  'b': [[[.26,.1],[.26,.88]],[[.26,.5],[.5,.38],[.74,.55],[.66,.84],[.3,.86]]],
  'c': [[[.76,.46],[.5,.36],[.26,.56],[.36,.86],[.76,.82]]],
  ' ': [],
  '、': [[[.44,.72],[.36,.9]]],
}

// ── 文字列 → 筆跡 ───────────────────────────────────────────────────

export type Written = {
  /** 1画 = 1本の折れ線。書き順のまま並ぶ */
  strokes: Pt[][]
  width: number
}

/**
 * 文字列を、指定した位置と大きさで書く。
 * 返る strokes は書き順に並んでいるので、順に引けば「書いている」ように見える。
 */
export function write2d(text: string, x: number, y: number, size: number, tracking = 1.06): Written {
  const strokes: Pt[][] = []
  let cursor = x

  for (const ch of text) {
    const half = /[\x20-\x7E]/.test(ch)
    const w = half ? size * 0.56 : size
    const place = (u: number, v: number): Pt => ({ x: cursor + u * w * (half ? 1.5 : 1), y: y + v * size })

    const ja = JA[ch]
    if (ja) {
      for (const d of ja.strokes) {
        strokes.push(parsePath(d).map(p => place(p.x / ja.view, p.y / ja.view)))
      }
    } else if (A[ch]) {
      for (const line of A[ch]) strokes.push(line.map(([u, v]) => place(u, v)))
    }
    cursor += w * tracking
  }
  return { strokes, width: cursor - x }
}

/** 折れ線の総長。描く速さを長さに比例させるため */
export function strokeLength(points: Pt[]): number {
  let total = 0
  for (let i = 1; i < points.length; i++) {
    total += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y)
  }
  return total
}
