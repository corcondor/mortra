'use client'

/**
 * 解いている過程を見せる。
 *
 * ロボットは映さない。カメラは紙の上にある。
 * 図が線ずつ描かれ、その脇に導出が現れる。図と字が交互に進む。
 *
 * 厳密な散文は書かない。人が板書するときと同じで、
 * 図式・記号・短い断片だけを書く。
 *
 * 2D。真っ白な紙に黒。ロボットの CG は要らない。
 * ?export=1 で 1080×1920 の PNG を書き出す。
 */

import { useEffect, useRef, useState } from 'react'
import { write2d, strokeLength } from '@/lib/handwriting2d'

const W = 1080
const H = 1920
const FPS = 30

type Pt = { x: number; y: number }

/** 描く手順。図の一筆か、脇に書く一行 */
type Step =
  | { kind: 'stroke'; points: Pt[]; width?: number; dim?: boolean; seconds: number }
  | { kind: 'mark'; at: Pt; label?: string; seconds: number }
  | { kind: 'text'; at: Pt; text: string; size?: number; seconds: number }
  | { kind: 'pause'; seconds: number }

// ── 問題: 三角形の9つの点が1つの円に乗る ──────────────────────────
// 13-14-15 のヘロン三角形。座標が有理数で出るので図が正確に描ける。

const S = 34                       // 1 単位あたりの画素
const OX = 150, OY = 1180          // 原点
const P = (x: number, y: number): Pt => ({ x: OX + x * S, y: OY - y * S })

const A = P(0, 0), B = P(14, 0), C = P(5, 12)

const mid = (p: Pt, q: Pt): Pt => ({ x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 })

/** p から直線 ab へ下ろした垂線の足 */
function foot(p: Pt, a: Pt, b: Pt): Pt {
  const dx = b.x - a.x, dy = b.y - a.y
  const t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)
  return { x: a.x + dx * t, y: a.y + dy * t }
}

function circumcentre(a: Pt, b: Pt, c: Pt): Pt {
  const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
  const s = (p: Pt) => p.x * p.x + p.y * p.y
  return {
    x: (s(a) * (b.y - c.y) + s(b) * (c.y - a.y) + s(c) * (a.y - b.y)) / d,
    y: (s(a) * (c.x - b.x) + s(b) * (a.x - c.x) + s(c) * (b.x - a.x)) / d,
  }
}

const O = circumcentre(A, B, C)
const H_ = { x: A.x + B.x + C.x - 2 * O.x, y: A.y + B.y + C.y - 2 * O.y }
const N = mid(O, H_)
const R = Math.hypot(A.x - O.x, A.y - O.y)

const Fa = foot(A, B, C), Fb = foot(B, C, A), Fc = foot(C, A, B)
const Ma = mid(B, C), Mb = mid(C, A), Mc = mid(A, B)
const Pa = mid(A, H_), Pb = mid(B, H_), Pc = mid(C, H_)

const circle = (c: Pt, r: number): Pt[] => {
  const out: Pt[] = []
  for (let i = 0; i <= 96; i++) {
    const t = (i / 96) * Math.PI * 2
    out.push({ x: c.x + r * Math.cos(t), y: c.y + r * Math.sin(t) })
  }
  return out
}

/** 脇に書く行の位置。上から順に降りてくる */
let line = 0
const TX = 640
const say = (text: string, seconds = 0.9, size = 30): Step => ({
  kind: 'text', at: { x: TX, y: 300 + line++ * 46 }, text, size, seconds,
})
const gap = () => { line += 0.5 }

const STEPS: Step[] = [
  say('△ABC', 0.7, 38),
  { kind: 'stroke', points: [A, B], seconds: 0.5 },
  { kind: 'stroke', points: [B, C], seconds: 0.5 },
  { kind: 'stroke', points: [C, A], seconds: 0.5 },
  { kind: 'mark', at: A, label: 'A', seconds: 0.2 },
  { kind: 'mark', at: B, label: 'B', seconds: 0.2 },
  { kind: 'mark', at: C, label: 'C', seconds: 0.2 },
  { kind: 'pause', seconds: 0.5 },

  say('3辺の中点', 0.6),
  { kind: 'mark', at: Ma, label: 'Ma', seconds: 0.25 },
  { kind: 'mark', at: Mb, label: 'Mb', seconds: 0.25 },
  { kind: 'mark', at: Mc, label: 'Mc', seconds: 0.25 },
  { kind: 'pause', seconds: 0.4 },

  say('各頂点から対辺へ垂線', 0.6),
  { kind: 'stroke', points: [A, Fa], dim: true, seconds: 0.45 },
  { kind: 'stroke', points: [B, Fb], dim: true, seconds: 0.45 },
  { kind: 'stroke', points: [C, Fc], dim: true, seconds: 0.45 },
  say('  → 垂線の足', 0.5),
  { kind: 'mark', at: Fa, label: 'Fa', seconds: 0.25 },
  { kind: 'mark', at: Fb, label: 'Fb', seconds: 0.25 },
  { kind: 'mark', at: Fc, label: 'Fc', seconds: 0.25 },
  say('  → 3本は1点で交わる', 0.7),
  { kind: 'mark', at: H_, label: 'H', seconds: 0.5 },
  gap() as unknown as Step,
].filter(Boolean) as Step[]

STEPS.push(
  say('垂心 H と各頂点の中点', 0.7),
  { kind: 'mark', at: Pa, label: 'Pa', seconds: 0.25 },
  { kind: 'mark', at: Pb, label: 'Pb', seconds: 0.25 },
  { kind: 'mark', at: Pc, label: 'Pc', seconds: 0.25 },
  { kind: 'pause', seconds: 0.6 },

  say('これで 3 + 3 + 3 = 9 点', 1.0, 34),
  say('互いに無関係に見える', 0.9),
  { kind: 'pause', seconds: 0.8 },

  say('外心 O をとり', 0.6),
  { kind: 'mark', at: O, label: 'O', seconds: 0.35 },
  say('OH の中点を N とすると', 0.8),
  { kind: 'stroke', points: [O, H_], dim: true, seconds: 0.5 },
  { kind: 'mark', at: N, label: 'N', seconds: 0.4 },
  { kind: 'pause', seconds: 0.7 },

  say('N を中心、半径 R/2 の円', 1.0, 34),
  { kind: 'stroke', points: circle(N, R / 2), width: 3.4, seconds: 2.2 },
  { kind: 'pause', seconds: 1.4 },
  say('9 点すべてがこの円上', 1.2, 36),
)

const TOTAL = STEPS.reduce((a, s) => a + s.seconds, 0)

// ── 描画 ────────────────────────────────────────────────────────────

type C2 = CanvasRenderingContext2D

function drawMark(c: C2, p: Pt, label: string | undefined, k: number) {
  const r = 7 * Math.min(1, k * 1.6)
  c.beginPath()
  c.arc(p.x, p.y, r, 0, Math.PI * 2)
  c.fillStyle = '#111'
  c.fill()
  if (label && k > 0.45) {
    c.globalAlpha = Math.min(1, (k - 0.45) * 3)
    c.fillStyle = '#111'
    c.font = '500 25px "Helvetica Neue",Arial,sans-serif'
    c.fillText(label, p.x + 13, p.y - 11)
    c.globalAlpha = 1
  }
}

/** 折れ線を長さ比 k まで描く。ペン先が進むように見せる */
function drawPartial(c: C2, pts: Pt[], k: number, width: number, dim: boolean) {
  if (pts.length < 2) return
  const seg: number[] = []
  let total = 0
  for (let i = 1; i < pts.length; i++) {
    const d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y)
    seg.push(d); total += d
  }
  const want = total * Math.min(1, Math.max(0, k))
  c.beginPath()
  c.moveTo(pts[0].x, pts[0].y)
  let run = 0
  for (let i = 1; i < pts.length; i++) {
    if (run + seg[i - 1] <= want) { c.lineTo(pts[i].x, pts[i].y); run += seg[i - 1] }
    else {
      const t = (want - run) / seg[i - 1]
      c.lineTo(pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t,
        pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t)
      break
    }
  }
  c.strokeStyle = dim ? 'rgba(17,17,17,0.34)' : '#111'
  c.lineWidth = width
  c.lineCap = 'round'
  c.lineJoin = 'round'
  c.stroke()
}

/*
 * 文字を「書く」。
 *
 * フォントで一文字ずつ出すと、表示されたようにしか見えない。
 * KanjiVG の画を書き順のまま、1画ずつペン先を進めて引く。
 * 総長に比例して時間を配るので、画数の多い字ほど長くかかる。人と同じ。
 */
const writtenCache = new Map<string, ReturnType<typeof write2d>>()

function drawWritten(c: C2, s: { at: Pt; text: string; size?: number }, k: number) {
  const size = s.size ?? 30
  const key = `${s.text}|${s.at.x}|${s.at.y}|${size}`
  let w = writtenCache.get(key)
  if (!w) {
    // KanjiVG の原点は字の左上。baseline 合わせのため少し持ち上げる
    w = write2d(s.text, s.at.x, s.at.y - size * 0.82, size)
    writtenCache.set(key, w)
  }
  const lengths = w.strokes.map(strokeLength)
  const total = lengths.reduce((a, b) => a + b, 0) || 1
  let want = total * Math.min(1, Math.max(0, k))

  c.strokeStyle = '#111'
  c.lineWidth = Math.max(1.6, size * 0.062)
  c.lineCap = 'round'
  c.lineJoin = 'round'

  for (let i = 0; i < w.strokes.length && want > 0; i++) {
    const pts = w.strokes[i]
    if (pts.length < 2) continue
    const ratio = Math.min(1, want / (lengths[i] || 1))
    want -= lengths[i]
    c.beginPath()
    c.moveTo(pts[0].x, pts[0].y)
    let run = 0
    const need = (lengths[i] || 0) * ratio
    for (let j = 1; j < pts.length; j++) {
      const d = Math.hypot(pts[j].x - pts[j - 1].x, pts[j].y - pts[j - 1].y)
      if (run + d <= need) { c.lineTo(pts[j].x, pts[j].y); run += d }
      else {
        const t2 = d ? (need - run) / d : 0
        c.lineTo(pts[j - 1].x + (pts[j].x - pts[j - 1].x) * t2,
          pts[j - 1].y + (pts[j].y - pts[j - 1].y) * t2)
        break
      }
    }
    c.stroke()
  }
}

function draw(c: C2, t: number) {
  c.fillStyle = '#fff'
  c.fillRect(0, 0, W, H)

  c.fillStyle = '#111'
  c.font = '600 30px "Hiragino Sans","Noto Sans JP",sans-serif'
  c.fillText('三角形の9つの点', 150, 200)
  c.fillStyle = 'rgba(17,17,17,0.4)'
  c.font = '400 22px "Hiragino Sans","Noto Sans JP",sans-serif'
  c.fillText('MORTRA', 150, 240)

  let acc = 0
  for (const s of STEPS) {
    const k = Math.min(1, Math.max(0, (t - acc) / s.seconds))
    acc += s.seconds
    if (k <= 0) break
    if (s.kind === 'stroke') drawPartial(c, s.points, k, s.width ?? 2.6, !!s.dim)
    else if (s.kind === 'mark') drawMark(c, s.at, s.label, k)
    else if (s.kind === 'text') drawWritten(c, s, k)
  }
}

export default function SolvePage() {
  const ref = useRef<HTMLCanvasElement | null>(null)
  const [status, setStatus] = useState('')

  useEffect(() => {
    const canvas = ref.current
    const c = canvas?.getContext('2d')
    if (!canvas || !c) return
    const exporting = new URLSearchParams(window.location.search).get('export') === '1'

    if (!exporting) {
      let raf = 0
      const start = performance.now()
      const loop = () => {
        draw(c, ((performance.now() - start) / 1000) % (TOTAL + 2))
        raf = requestAnimationFrame(loop)
      }
      loop()
      return () => cancelAnimationFrame(raf)
    }

    let cancelled = false
    ;(async () => {
      const frames = Math.ceil((TOTAL + 2) * FPS)
      for (let i = 0; i < frames && !cancelled; i++) {
        draw(c, i / FPS)
        await fetch('/api/frames', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ index: i, dataUrl: canvas.toDataURL('image/png'), session: 'solve' }),
        })
        if (i % 30 === 0) setStatus(`${i} / ${frames}`)
      }
      setStatus(cancelled ? '中断' : `完了 ${frames} 枚`)
    })()
    return () => { cancelled = true }
  }, [])

  return (
    <main style={{ minHeight: '100vh', background: '#111', display: 'flex',
      flexDirection: 'column', alignItems: 'center', gap: 10, padding: 14 }}>
      <canvas ref={ref} width={W} height={H}
        style={{ height: '90vh', width: 'auto', background: '#fff' }} />
      {status && <p style={{ color: '#9fe0b0', font: '13px monospace' }}>{status}</p>}
    </main>
  )
}
