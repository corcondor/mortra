/**
 * 文字を「アームが書ける線」に変える。
 *
 * 図と解説を同じ板に共存させるための土台。図だけ描いても解説にならない。
 * 予備校の板書は、日本語と数式と図が同じ面に並んでいる。
 *
 * 日本語は KanjiVG の筆順つき中心線を使う（data/strokes/ja.json）。
 * 輪郭フォントは字の縁を囲む閉曲線なので、なぞると字が塗り絵になる。
 * KanjiVG は人が書く線そのものなので、ペン先の軌跡として正しい。
 *
 * ASCII と数学記号は輪郭データが要らないので、ここで単線として定義する。
 */

import type { P3, Stroke3 } from './figures'
import glyphData from '../data/strokes/ja.json'

const BOARD_Y = 55
const BOARD_Z = 46

type Glyph = { view: number; strokes: string[] }
const JA = glyphData as Record<string, Glyph>

// ── SVG パスを折れ線にする ──────────────────────────────────────────
// KanjiVG が使うのは M/m L/l C/c S/s Z/z だけ。それ以外は来ない。

type Pt = { x: number; y: number }

function bezier(p0: Pt, p1: Pt, p2: Pt, p3: Pt, steps: number): Pt[] {
  const out: Pt[] = []
  for (let i = 1; i <= steps; i++) {
    const t = i / steps
    const u = 1 - t
    out.push({
      x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
      y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
    })
  }
  return out
}

/** 1画ぶんの d 属性 → 折れ線。座標は SVG のまま（左上原点・y 下向き） */
export function parsePath(d: string, steps = 8): Pt[] {
  const tokens = d.match(/[MmLlCcSsZz]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) ?? []
  const points: Pt[] = []
  let i = 0
  let current: Pt = { x: 0, y: 0 }
  let command = ''
  let lastControl: Pt | null = null

  const num = () => parseFloat(tokens[i++])

  while (i < tokens.length) {
    const token = tokens[i]
    if (/[MmLlCcSsZz]/.test(token)) { command = token; i++ }

    switch (command) {
      case 'M': case 'm': {
        const x = num(), y = num()
        current = command === 'M' ? { x, y } : { x: current.x + x, y: current.y + y }
        points.push({ ...current })
        command = command === 'M' ? 'L' : 'l'   // 続く数値は暗黙の L
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
        const c1 = { x: num(), y: num() }
        const c2 = { x: num(), y: num() }
        const end = { x: num(), y: num() }
        const a = rel ? { x: current.x + c1.x, y: current.y + c1.y } : c1
        const b = rel ? { x: current.x + c2.x, y: current.y + c2.y } : c2
        const e = rel ? { x: current.x + end.x, y: current.y + end.y } : end
        points.push(...bezier(current, a, b, e, steps))
        lastControl = b
        current = e
        break
      }
      case 'S': case 's': {
        const rel = command === 's'
        const c2 = { x: num(), y: num() }
        const end = { x: num(), y: num() }
        const b = rel ? { x: current.x + c2.x, y: current.y + c2.y } : c2
        const e = rel ? { x: current.x + end.x, y: current.y + end.y } : end
        // 直前の制御点を現在点で鏡映したものが第1制御点になる
        const a = lastControl
          ? { x: 2 * current.x - lastControl.x, y: 2 * current.y - lastControl.y }
          : current
        points.push(...bezier(current, a, b, e, steps))
        lastControl = b
        current = e
        break
      }
      case 'Z': case 'z':
        i++
        break
      default:
        i++
    }
  }
  return points
}

// ── ASCII と数学記号（単線で定義）────────────────────────────────────
// 1文字を 0..1 の升目に置く。y は下向き（KanjiVG に合わせる）。

type Line = Array<[number, number]>
const A: Record<string, Line[]> = {
  '0': [[[.15,.15],[.85,.15],[.85,.85],[.15,.85],[.15,.15]]],
  '1': [[[.3,.3],[.5,.1],[.5,.9]], [[.25,.9],[.75,.9]]],
  '2': [[[.15,.25],[.5,.1],[.85,.3],[.15,.9],[.85,.9]]],
  '3': [[[.15,.15],[.85,.15],[.4,.5],[.85,.65],[.5,.9],[.15,.8]]],
  '4': [[[.7,.9],[.7,.1],[.15,.65],[.9,.65]]],
  '5': [[[.85,.1],[.2,.1],[.15,.45],[.6,.42],[.85,.65],[.5,.9],[.15,.82]]],
  '6': [[[.8,.15],[.35,.15],[.15,.6],[.5,.9],[.85,.7],[.6,.5],[.2,.55]]],
  '7': [[[.15,.12],[.85,.12],[.4,.9]]],
  '8': [[[.5,.1],[.2,.28],[.5,.48],[.8,.28],[.5,.1]], [[.5,.48],[.18,.7],[.5,.9],[.82,.7],[.5,.48]]],
  '9': [[[.8,.45],[.4,.5],[.2,.28],[.5,.1],[.82,.32],[.75,.75],[.35,.9]]],
  '=': [[[.15,.4],[.85,.4]], [[.15,.62],[.85,.62]]],
  '+': [[[.5,.22],[.5,.78]], [[.2,.5],[.8,.5]]],
  '-': [[[.18,.5],[.82,.5]]],
  '/': [[[.2,.9],[.8,.12]]],
  '(': [[[.65,.1],[.35,.3],[.35,.7],[.65,.9]]],
  ')': [[[.35,.1],[.65,.3],[.65,.7],[.35,.9]]],
  '.': [[[.45,.85],[.55,.85]]],
  ',': [[[.5,.8],[.4,.95]]],
  '·': [[[.45,.5],[.55,.5]]],
  'A': [[[.15,.9],[.5,.1],[.85,.9]], [[.28,.6],[.72,.6]]],
  'B': [[[.2,.9],[.2,.1],[.7,.15],[.7,.45],[.2,.5]], [[.2,.5],[.75,.55],[.75,.85],[.2,.9]]],
  'C': [[[.82,.2],[.5,.1],[.2,.35],[.2,.68],[.5,.9],[.82,.8]]],
  'a': [[[.75,.4],[.4,.35],[.25,.55],[.35,.85],[.7,.8]], [[.75,.35],[.75,.9]]],
  'c': [[[.78,.45],[.5,.35],[.25,.55],[.35,.85],[.78,.82]]],
  'o': [[[.5,.35],[.25,.55],[.4,.85],[.72,.75],[.68,.45],[.5,.35]]],
  's': [[[.78,.42],[.4,.35],[.3,.52],[.7,.62],[.62,.85],[.25,.8]]],
  '√': [[[.1,.55],[.28,.62],[.45,.92],[.72,.08],[.95,.08]]],
  ' ': [],
}

// ── 文字列 → 板の上のストローク ──────────────────────────────────────

export type WriteOptions = {
  /** 板の座標。u は左右（−が左）、v は上下（+が上） */
  u: number
  v: number
  /** 1文字の高さ（板の単位） */
  size: number
  /** 字間の倍率 */
  tracking?: number
  label?: string
}

/** 1文字ぶんの画を、板の座標に置く */
function glyphStrokes(ch: string, originU: number, v: number, size: number): P3[][] {
  const place = (x: number, y: number): P3 => ({
    // KanjiVG は y 下向き。板は v 上向きなので反転する
    x: originU + x * size,
    y: BOARD_Y,
    z: BOARD_Z + v - y * size,
  })

  const ja = JA[ch]
  if (ja) {
    return ja.strokes.map(d =>
      parsePath(d).map(p => place(p.x / ja.view, p.y / ja.view)),
    )
  }
  const ascii = A[ch]
  if (ascii) return ascii.map(line => line.map(([x, y]) => place(x, y)))
  return []
}

/**
 * 文字列を板に書く。返るのは figures.ts と同じ Stroke3 なので、
 * 逆運動学も最小ジャーク軌道もそのまま通る。
 */
export function write(text: string, options: WriteOptions): Stroke3[] {
  const { u, v, size, tracking = 1.08, label = text } = options
  const out: Stroke3[] = []
  let cursor = u
  let index = 0

  for (const ch of text) {
    // 半角は幅を詰める。全角と同じ幅だと隙間だらけになる
    const width = /[\x20-\x7E]/.test(ch) ? size * 0.58 : size
    for (const points of glyphStrokes(ch, cursor, v, size)) {
      if (points.length >= 2) {
        out.push({ points, label: `${label} ${++index}`, kind: 'line' })
      }
    }
    cursor += width * tracking
  }
  return out
}

/** 書いたときの右端。次の行や図の位置を決めるのに使う */
export function measure(text: string, size: number, tracking = 1.08): number {
  let width = 0
  for (const ch of text) {
    width += (/[\x20-\x7E]/.test(ch) ? size * 0.58 : size) * tracking
  }
  return width
}

/** 板の座標 (u, v) を空間の点にする。図と文字を同じ面に置くため */
export function boardPoint(u: number, v: number): P3 {
  return { x: u, y: BOARD_Y, z: BOARD_Z + v }
}
