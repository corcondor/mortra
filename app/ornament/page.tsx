'use client'

/**
 * 対称群から模様を作る画面。
 *
 * 幾何学は数学の中だけの物ではない。美しいから、模様・ロゴ・装飾に使える。
 * ここに出る模様は「それらしく描いた」ものではなく、
 * 群の作用として生成し、対称性を検証したもの。
 * 検証に落ちた模様はその群を名乗らない。
 *
 *   ?g=p6m      群
 *   ?m=root     母型（root = A₃ の12方向 / poly / circle / line）
 *   ?export=1   1080×1350 で書き出す
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  WALLPAPER, windowOrbit, verifySymmetry, pointGroupOrder,
  polygon, circle, motifFromVectors,
  type Stroke, type WallpaperGroup,
} from '@/lib/mortra/vision/ornament'

/** A₃ ルート系（FCC の最近接12方向）を平面へ落とした母型 */
const A3_PLANE = Array.from({ length: 12 }, (_, i) => {
  const a = (i / 12) * Math.PI * 2
  return { x: Math.cos(a) * 0.34, y: Math.sin(a) * 0.34 }
})

function motifOf(kind: string): Stroke[] {
  switch (kind) {
    case 'root':
      return motifFromVectors(A3_PLANE)
    case 'circle':
      return [circle({ x: 0.26, y: 0.15 }, 0.17), circle({ x: 0, y: 0 }, 0.09)]
    case 'line':
      return [[{ x: 0.04, y: 0.04 }, { x: 0.4, y: 0.2 }],
              [{ x: 0.4, y: 0.2 }, { x: 0.22, y: 0.42 }]]
    default:
      return [polygon({ x: 0.3, y: 0.12 }, 0.15, 3),
              [{ x: 0, y: 0 }, { x: 0.3, y: 0.12 }]]
  }
}

const OUT_W = 1080
const OUT_H = 1350

export default function OrnamentPage() {
  const ref = useRef<HTMLCanvasElement>(null)
  const [q, setQ] = useState<URLSearchParams | null>(null)
  useEffect(() => { setQ(new URLSearchParams(location.search)) }, [])

  const groupKey = q?.get('g') ?? 'p6m'
  const motifKind = q?.get('m') ?? 'poly'
  const exporting = q?.get('export') === '1'

  const built = useMemo(() => {
    const group: WallpaperGroup = WALLPAPER[groupKey] ?? WALLPAPER.p6m
    const motif = motifOf(motifKind)
    const orbit = windowOrbit(motif, group, { repeat: 5, scale: 1 })
    // 名乗る前に確かめる。落ちたら群名を出さない
    const verdict = verifySymmetry(orbit.strokes, group, { scale: 1 })
    return { group, strokes: orbit.strokes, verdict, order: pointGroupOrder(group) }
  }, [groupKey, motifKind])

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const c = canvas.getContext('2d')
    if (!c) return
    const W = exporting ? OUT_W : Math.min(900, canvas.clientWidth || 900)
    const H = exporting ? OUT_H : Math.round(W * 1.25)
    canvas.width = W
    canvas.height = H
    c.setTransform(1, 0, 0, 1, 0, 0)
    c.fillStyle = '#ffffff'
    c.fillRect(0, 0, W, H)

    const { group, strokes, verdict, order } = built
    // 模様を紙面に収める。中心を原点に、正方形の領域へ
    const pad = W * 0.08
    const side = Math.min(W - pad * 2, H * 0.72)
    const k = side / 4.2
    const cx = W / 2
    const cy = pad + side / 2

    c.save()
    c.beginPath()
    c.rect(pad, pad, W - pad * 2, side)
    c.clip()
    c.strokeStyle = '#111111'
    c.lineWidth = Math.max(1, W * 0.0016)
    c.lineCap = 'round'
    c.lineJoin = 'round'
    for (const s of strokes) {
      if (s.length < 2) continue
      c.beginPath()
      c.moveTo(cx + s[0].x * k, cy - s[0].y * k)
      for (let i = 1; i < s.length; i++) c.lineTo(cx + s[i].x * k, cy - s[i].y * k)
      c.stroke()
    }
    c.restore()

    // 何から出た模様かを書く。装飾ではなく生成物なので、由来が言える
    const textY = pad + side + W * 0.075
    c.fillStyle = '#111111'
    c.font = `600 ${Math.round(W * 0.052)}px "Helvetica Neue", Arial, sans-serif`
    c.textBaseline = 'alphabetic'
    c.fillText(group.name, pad, textY)

    c.fillStyle = '#6a6a6a'
    c.font = `${Math.round(W * 0.021)}px "Hiragino Kaku Gothic ProN", sans-serif`
    c.fillText(group.character, pad, textY + W * 0.036)
    c.fillText(`点群 G/T の位数 ${order}（生成元 ${group.pointGroupGenerators.length} 本の閉包を数えた。壁紙群 G 自体は無限）`,
      pad, textY + W * 0.066)
    c.fillText(`並進部分群 T ${group.latticeType} ／ 窓の中の線 ${strokes.length} 本`, pad, textY + W * 0.096)

    c.fillStyle = verdict.holds ? '#111111' : '#b00020'
    c.font = `${Math.round(W * 0.019)}px "SF Mono", ui-monospace, monospace`
    c.fillText(
      verdict.holds
        ? `symmetry verified  point group ${order}/${order} + 2 translations`
        : `NOT VERIFIED  point group ${verdict.failedPointGroupElements.length}`
          + ` / translations ${verdict.failedTranslations.length}`,
      pad, textY + W * 0.128)
    c.fillStyle = '#9a9a9a'
    c.fillText('generated from a symmetry group  ·  no LLM', pad, H - pad * 0.6)
  }, [built, exporting])

  useEffect(() => {
    if (!exporting) return
    const w = window as unknown as { __ornamentShot?: (name: string) => Promise<string> }
    w.__ornamentShot = async (name: string) => {
      const canvas = ref.current
      if (!canvas) return 'no canvas'
      const res = await fetch('/api/frame', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ dir: 'ornament', name, dataUrl: canvas.toDataURL('image/png') }),
      })
      return (await res.json()).path ?? 'failed'
    }
  }, [exporting])

  return (
    <main className="flex min-h-[100dvh] flex-col items-center gap-6 bg-white p-8">
      <canvas ref={ref} style={{ width: 'min(92vw, 720px)', height: 'auto' }} />
      <div className="flex flex-wrap justify-center gap-2 text-[12px]">
        {Object.keys(WALLPAPER).map(k => (
          <a key={k} href={`?g=${k}&m=${motifKind}`}
            className={`rounded-sm border px-3 py-1 ${k === groupKey
              ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-300 text-zinc-600'}`}>
            {k}
          </a>
        ))}
        <span className="mx-2 text-zinc-300">|</span>
        {['poly', 'root', 'circle', 'line'].map(m => (
          <a key={m} href={`?g=${groupKey}&m=${m}`}
            className={`rounded-sm border px-3 py-1 ${m === motifKind
              ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-300 text-zinc-600'}`}>
            {m}
          </a>
        ))}
      </div>
    </main>
  )
}


