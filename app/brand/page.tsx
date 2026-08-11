'use client'

/**
 * MORTRA の印。
 *
 * 装飾から作らない。名前の意味から作る。
 *   MORTRA = morphism + transport
 *   主張   = 同じ構造が、別の姿になる
 *
 * 圏論でこれを表す図はもう決まっている。可換図式である。
 * 二つの経路が同じ終点に着く、という図がそのまま会社の主張になる。
 * だから印は「作った形」ではなく「既にある図」を切り出したものにする。
 *
 *   ?v=<n>       候補を一つだけ大きく
 *   ?export=1    書き出し（/api/frame へ PNG を送る）
 */
import { useEffect, useRef, useState } from 'react'

type Ctx = CanvasRenderingContext2D

/** 印はすべて 100×100 の升目で描く。使うときは好きな大きさに拡げる */
const G = 100

type Mark = {
  id: string
  name: string
  idea: string
  draw: (c: Ctx, ink: string, w: number) => void
}

const dot = (c: Ctx, x: number, y: number, r: number, ink: string) => {
  c.fillStyle = ink
  c.beginPath()
  c.arc(x, y, r, 0, Math.PI * 2)
  c.fill()
}

/** 矢先。線の向きが見えないと「射」にならない */
function arrow(c: Ctx, x1: number, y1: number, x2: number, y2: number, w: number, ink: string, head = 9) {
  const a = Math.atan2(y2 - y1, x2 - x1)
  c.strokeStyle = ink
  c.lineWidth = w
  c.lineCap = 'round'
  c.lineJoin = 'round'
  c.beginPath()
  c.moveTo(x1, y1)
  c.lineTo(x2, y2)
  c.stroke()
  c.beginPath()
  c.moveTo(x2 - head * Math.cos(a - 0.42), y2 - head * Math.sin(a - 0.42))
  c.lineTo(x2, y2)
  c.lineTo(x2 - head * Math.cos(a + 0.42), y2 - head * Math.sin(a + 0.42))
  c.stroke()
}

/**
 * 一巡目で分かったこと。
 *   ・矢印を 4 本描くと、印ではなく図解になる。16px で完全に潰れた。
 *   ・M を図式で作ろうとすると M に見えない。字は字、印は印。
 * だから射は 2 本に減らし、始点と終点だけを実体（点）にする。
 * 「一つの出発点から、二つの道で、同じ終点へ」だけが残るように削る。
 */
const MARKS: Mark[] = [
  {
    id: 'square',
    name: '可換正方形',
    idea: '一つの出発点から二つの道。同じ終点に着く',
    draw: (c, ink, w) => {
      const m = 22
      const S: [number, number] = [m, G - m]        // 出発点
      const T: [number, number] = [G - m, m]        // 終点
      const U: [number, number] = [m, m]            // 経由（上）
      const V: [number, number] = [G - m, G - m]    // 経由（下）
      c.strokeStyle = ink
      c.lineWidth = w
      c.lineCap = 'round'
      c.lineJoin = 'round'
      c.beginPath(); c.moveTo(S[0], S[1] - 6); c.lineTo(U[0], U[1]); c.lineTo(T[0] - 11, T[1]); c.stroke()
      c.beginPath(); c.moveTo(S[0] + 6, S[1]); c.lineTo(V[0], V[1]); c.lineTo(T[0], T[1] + 11); c.stroke()
      arrow(c, T[0] - 14, T[1], T[0] - 1, T[1], w, ink, 8)
      arrow(c, T[0], T[1] + 14, T[0], T[1] + 1, w, ink, 8)
      dot(c, S[0], S[1], w * 1.0, ink)
    },
  },
  {
    id: 'square-solid',
    name: '可換正方形（終点を実体に）',
    idea: '終点だけを塗る。「同じものに着いた」が一目で出る',
    draw: (c, ink, w) => {
      const m = 22
      const S: [number, number] = [m, G - m]
      const T: [number, number] = [G - m, m]
      c.strokeStyle = ink
      c.lineWidth = w
      c.lineCap = 'round'
      c.lineJoin = 'round'
      c.beginPath(); c.moveTo(S[0], S[1] - 8); c.lineTo(m, m); c.lineTo(T[0] - 8, T[1]); c.stroke()
      c.beginPath(); c.moveTo(S[0] + 8, S[1]); c.lineTo(G - m, G - m); c.lineTo(T[0], T[1] + 8); c.stroke()
      dot(c, S[0], S[1], w * 1.05, ink)
      dot(c, T[0], T[1], w * 1.75, ink)
    },
  },
  {
    id: 'arc',
    name: '二つの道',
    idea: '正方形をやめ、直線と弧にする。始点と終点だけが実体',
    draw: (c, ink, w) => {
      const S: [number, number] = [24, 50]
      const T: [number, number] = [76, 50]
      c.strokeStyle = ink
      c.lineWidth = w
      c.lineCap = 'round'
      c.beginPath(); c.moveTo(S[0] + 8, S[1]); c.lineTo(T[0] - 8, T[1]); c.stroke()
      c.beginPath()
      c.moveTo(S[0] + 6, S[1] - 5)
      c.quadraticCurveTo(50, 12, T[0] - 6, T[1] - 5)
      c.stroke()
      dot(c, S[0], S[1], w * 1.05, ink)
      dot(c, T[0], T[1], w * 1.7, ink)
    },
  },
  {
    id: 'triangle-diagram',
    name: '三角図式',
    idea: '二つの射とその合成。圏論で最初に描く図',
    draw: (c, ink, w) => {
      const A: [number, number] = [22, 76]
      const B: [number, number] = [50, 24]
      const C: [number, number] = [78, 76]
      c.strokeStyle = ink
      c.lineWidth = w
      c.lineCap = 'round'
      c.lineJoin = 'round'
      c.beginPath(); c.moveTo(A[0] + 5, A[1] - 9); c.lineTo(B[0] - 5, B[1] + 9); c.stroke()
      c.beginPath(); c.moveTo(B[0] + 5, B[1] + 9); c.lineTo(C[0] - 5, C[1] - 9); c.stroke()
      c.beginPath(); c.moveTo(A[0] + 11, A[1]); c.lineTo(C[0] - 11, C[1]); c.stroke()
        ;[A, B, C].forEach(([x, y]) => dot(c, x, y, w * 1.05, ink))
    },
  },
]

export default function BrandPage() {
  const ref = useRef<HTMLCanvasElement>(null)
  const [q, setQ] = useState<URLSearchParams | null>(null)
  useEffect(() => { setQ(new URLSearchParams(location.search)) }, [])
  const exporting = q?.get('export') === '1'

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const c = canvas.getContext('2d')
    if (!c) return
    const W = 1200, H = 1500
    canvas.width = W; canvas.height = H
    c.setTransform(1, 0, 0, 1, 0, 0)
    c.fillStyle = '#ffffff'
    c.fillRect(0, 0, W, H)

    c.fillStyle = '#111111'
    c.font = '500 20px "SF Mono", ui-monospace, monospace'
    c.textBaseline = 'top'
    c.fillText('MORTRA — MARK CANDIDATES', 80, 70)

    MARKS.forEach((mark, i) => {
      const y = 150 + i * 330
      // 大（96px 相当）
      c.save()
      c.translate(90, y)
      c.scale(1.7, 1.7)
      mark.draw(c, '#111111', 5)
      c.restore()

      // 小（16px 相当。ここで潰れる印は使えない）
      c.save()
      c.translate(300, y + 100)
      c.scale(0.42, 0.42)
      mark.draw(c, '#111111', 8)
      c.restore()

      // 反転
      c.fillStyle = '#111111'
      c.fillRect(360, y, 200, 200)
      c.save()
      c.translate(385, y + 25)
      c.scale(1.5, 1.5)
      mark.draw(c, '#ffffff', 5)
      c.restore()

      // 文字と組んだところ
      c.save()
      c.translate(620, y + 46)
      c.scale(0.85, 0.85)
      mark.draw(c, '#111111', 6)
      c.restore()
      c.fillStyle = '#111111'
      c.font = '600 44px "Helvetica Neue", Arial, sans-serif'
      c.textBaseline = 'middle'
      c.save()
      // 研究所らしさは字間で出る。詰めない
      let x = 730
      for (const ch of 'MORTRA') { c.fillText(ch, x, y + 88); x += c.measureText(ch).width + 9 }
      c.restore()

      c.fillStyle = '#8a8a8a'
      c.font = '15px "Hiragino Kaku Gothic ProN", sans-serif'
      c.textBaseline = 'top'
      c.fillText(`${i + 1}. ${mark.name}`, 90, y + 232)
      c.fillText(mark.idea, 90, y + 256)
    })
  }, [])

  useEffect(() => {
    if (!exporting) return
    const w = window as unknown as { __brandShot?: () => Promise<string> }
    w.__brandShot = async () => {
      const canvas = ref.current
      if (!canvas) return 'no canvas'
      const res = await fetch('/api/frame', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ dir: 'brand', name: 'marks.png', dataUrl: canvas.toDataURL('image/png') }),
      })
      return (await res.json()).path ?? 'failed'
    }
  }, [exporting])

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-white p-8">
      <canvas ref={ref} style={{ width: 'min(92vw, 720px)', height: 'auto' }} />
    </main>
  )
}
