'use client'

/**
 * 背景の作図。スクロール量が証明168手のどこにいるかに直結する。
 *
 * 1段スクロール = 1段証明 = 1段作図。MORTRA の主張そのものを、
 * サイトの操作にしている。
 *
 * 座標も手順も data/proof-scene-2011ARMOg11p8.json の実測値。
 * 架空の配置は使っていない。
 *
 * 発光は二重描画で作る。広く薄いにじみを加算合成で置き、その上に細い芯を引く。
 * 単層で shadowBlur を掛けても、芯が太いままでは光って見えない。
 */
import { useEffect, useRef } from 'react'

import { MORPHISM_COLOR } from './RibbonMark'

/** 2011ARMOg11p8 の実座標。14点 */
const PT: Record<string, [number, number]> = {
  a: [0.4126714639, 0.5303261703], b: [0.9201678148, 0.6639432475],
  c: [0.5467821565, 1.2822640458], d: [0.3710636508, 0.7317113102],
  e: [0.6456157328, 0.6978272789], f: [0.1669735881, 0.7568992237],
  g: [0.3294558377, 0.9330964501], h: [0.6830509386, 1.1020016734],
  i: [0.7931885351, 0.4638417210], m: [0.4797268102, 0.9062951081],
  n: [0.9820761073, 0.8166993923], o: [0.5902098693, 0.8865900765],
  i1: [0.5751537135, 0.7065233968], i2: [0.6053793635, 0.9663167897],
}
const GOAL = ['b', 'i1', 'i2', 'n']
const SUPPORT: [string, string][] = [
  ['a', 'd'], ['d', 'g'], ['a', 'c'], ['a', 'm'], ['c', 'm'], ['g', 'm'], ['m', 'n'],
  ['d', 'f'], ['f', 'm'], ['a', 'o'], ['b', 'o'], ['c', 'o'], ['n', 'o'], ['d', 'm'],
]
const THEOREM_EDGES: [string, string][] = [
  ['a', 'n'], ['n', 'o'], ['a', 'o'], ['c', 'n'], ['c', 'o'],
  ['g', 'n'], ['g', 'i1'], ['c', 'i2'], ['n', 'i2'],
]

export function ProofScrollScene({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let V: { x: (v: number) => number; y: (v: number) => number } | null = null
    let circle = { cx: 0, cy: 0, r: 0 }
    let dpr = 1

    const P = (k: string): [number, number] => [V!.x(PT[k][0]), V!.y(PT[k][1])]
    const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t)
    const ease = (t: number) => { const u = clamp01(t); return u * u * (3 - 2 * u) }
    const seg = (t: number, a: number, b: number) => ease((t - a) / (b - a))

    const layout = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      cv.width = Math.floor(window.innerWidth * dpr)
      cv.height = Math.floor(window.innerHeight * dpr)

      const xs = Object.values(PT).map(p => p[0])
      const ys = Object.values(PT).map(p => p[1])
      const minX = Math.min(...xs), maxX = Math.max(...xs)
      const minY = Math.min(...ys), maxY = Math.max(...ys)
      const narrow = window.innerWidth < 860
      const pad = narrow ? 0.16 : 0.10
      const s = Math.min(
        (cv.width * (narrow ? 0.72 : 0.46)) / (maxX - minX),
        (cv.height * (1 - 2 * pad)) / (maxY - minY),
      )
      const cx = narrow ? cv.width * 0.5 : cv.width * 0.68
      V = {
        x: (v: number) => cx + (v - (minX + maxX) / 2) * s,
        // y は上向きに直す
        y: (v: number) => cv.height / 2 - (v - (minY + maxY) / 2) * s,
      }
      const [A, B, C] = [P('b'), P('i1'), P('n')]
      const dd = 2 * (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1]) + C[0] * (A[1] - B[1]))
      const ux = ((A[0] ** 2 + A[1] ** 2) * (B[1] - C[1]) + (B[0] ** 2 + B[1] ** 2) * (C[1] - A[1])
        + (C[0] ** 2 + C[1] ** 2) * (A[1] - B[1])) / dd
      const uy = ((A[0] ** 2 + A[1] ** 2) * (C[0] - B[0]) + (B[0] ** 2 + B[1] ** 2) * (A[0] - C[0])
        + (C[0] ** 2 + C[1] ** 2) * (B[0] - A[0])) / dd
      circle = { cx: ux, cy: uy, r: Math.hypot(A[0] - ux, A[1] - uy) }
    }

    /** にじみ → 芯 の二重描画 */
    const line = (p: string, q: string, color: string, alpha: number, w: number, glow: number) => {
      if (alpha <= 0.004) return
      const A = P(p), B = P(q)
      const stroke = () => {
        ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke()
      }
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      ctx.globalAlpha = alpha * 0.34
      ctx.strokeStyle = color
      ctx.lineWidth = w * 4.5
      ctx.lineCap = 'round'
      ctx.shadowColor = color
      ctx.shadowBlur = glow * 1.6
      stroke()
      ctx.restore()

      ctx.save()
      ctx.globalAlpha = alpha
      ctx.strokeStyle = color
      ctx.lineWidth = w
      ctx.lineCap = 'round'
      stroke()
      ctx.restore()
    }

    const dot = (k: string, color: string, alpha: number, r: number, label: boolean) => {
      if (alpha <= 0.004) return
      const [x, y] = P(k)
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      ctx.globalAlpha = alpha * 0.4
      ctx.fillStyle = color
      ctx.shadowColor = color
      ctx.shadowBlur = 16
      ctx.beginPath(); ctx.arc(x, y, r * 2.2, 0, Math.PI * 2); ctx.fill()
      ctx.restore()

      ctx.save()
      ctx.globalAlpha = alpha
      ctx.fillStyle = color
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill()
      if (label) {
        ctx.globalAlpha = alpha * 0.85
        ctx.font = `400 ${Math.round(r * 4.2)}px "IBM Plex Mono", ui-monospace, monospace`
        ctx.fillText(k, x + r + 9, y - r - 6)
      }
      ctx.restore()
    }

    const draw = (t: number) => {
      ctx.fillStyle = '#06080a'
      ctx.fillRect(0, 0, cv.width, cv.height)
      const u = dpr

      // 作図。オレンジ
      const sup = seg(t, 0.05, 0.26) * 0.62
      SUPPORT.forEach(([p, q]) => line(p, q, MORPHISM_COLOR.construct, sup, 0.6 * u, 7))

      // 名前のある定理。ローズが順に引かれる
      const th = seg(t, 0.24, 0.46)
      THEOREM_EDGES.forEach(([p, q], idx) => {
        const local = clamp01(th * THEOREM_EDGES.length - idx)
        line(p, q, MORPHISM_COLOR.theorem, local * 0.95, 0.85 * u, 9)
      })

      // 代数の消去。白が i1 と i2 へ一斉に集まる
      const ar = seg(t, 0.44, 0.64)
      if (ar > 0) {
        const fade = 1 - clamp01((t - 0.66) / 0.14)
        Object.keys(PT).forEach((k, idx) => {
          const local = clamp01(ar * 2.4 - idx * 0.05)
          line(k, 'i1', MORPHISM_COLOR.algebra, local * 0.34 * fade, 0.45 * u, 5)
          line(k, 'i2', MORPHISM_COLOR.algebra, local * 0.34 * fade, 0.45 * u, 5)
        })
      }

      // 2つの等しい角
      const ang = seg(t, 0.64, 0.80)
      const pairs: [string, string][] = [['b', 'i1'], ['b', 'i2'], ['n', 'i1'], ['n', 'i2']]
      pairs.forEach(([p, q]) => line(p, q, MORPHISM_COLOR.theorem, ang, 1.15 * u, 14))

      // 円が閉じる
      const cl = seg(t, 0.80, 0.96)
      if (cl > 0) {
        const arc = () => {
          ctx.beginPath()
          ctx.arc(circle.cx, circle.cy, circle.r, -Math.PI / 2, -Math.PI / 2 + cl * Math.PI * 2)
          ctx.stroke()
        }
        ctx.save()
        ctx.strokeStyle = MORPHISM_COLOR.close
        ctx.shadowColor = MORPHISM_COLOR.close
        ctx.shadowBlur = 22
        ctx.lineCap = 'round'
        ctx.globalCompositeOperation = 'lighter'
        ctx.globalAlpha = 0.32; ctx.lineWidth = 5.2 * u; arc()
        ctx.globalCompositeOperation = 'source-over'
        ctx.globalAlpha = 1; ctx.lineWidth = 1.15 * u; ctx.shadowBlur = 0; arc()
        ctx.restore()
      }

      // 点
      const app = seg(t, 0.02, 0.16)
      Object.keys(PT).forEach(k => {
        if (GOAL.includes(k)) {
          const glow = seg(t, 0.80, 0.94)
          dot(k, glow > 0 ? MORPHISM_COLOR.close : '#ffffff', app, 2.6 * u, true)
        } else {
          dot(k, MORPHISM_COLOR.construct, app * 0.85, 1.5 * u, false)
        }
      })
    }

    let current = 0, raf = 0, lastY = -1, lastMax = -1

    // scroll イベントに頼らない。埋め込みや独自スクロール容器では
    // window の scroll が届かないことがある（実際に届かなかった）。
    // 毎フレーム位置を読み、変化したときだけ描き直す。
    const scrollProgress = () => {
      const doc = document.documentElement
      const y = window.scrollY || doc.scrollTop || document.body.scrollTop || 0
      const max = Math.max(doc.scrollHeight, document.body.scrollHeight) - window.innerHeight
      return { y, max, t: max > 0 ? clamp01(y / max) : 0 }
    }

    const loop = () => {
      raf = requestAnimationFrame(loop)
      const { y, max, t } = scrollProgress()
      const moved = y !== lastY || max !== lastMax
      lastY = y; lastMax = max
      // 追従を少し遅らせる。生のスクロール値をそのまま使うと動きが硬い
      const next = current + (t - current) * (reduced ? 1 : 0.12)
      if (!moved && Math.abs(next - current) < 0.0004) return
      current = Math.abs(next - t) < 0.0004 ? t : next
      draw(current)
    }

    // リサイズ時はスクロール位置も読み直す。
    // 位置を据え置くと、幅が変わったときに図が前のコマのまま残る
    const onResize = () => { layout(); current = scrollProgress().t; draw(current) }

    // 隠れたタブでは rAF が止まる。戻ったら測り直して再開する
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      cancelAnimationFrame(raf)
      layout()
      current = scrollProgress().t
      draw(current)
      raf = requestAnimationFrame(loop)
    }

    // 初回の layout() が innerWidth 0 の時点で走ることがある。
    // 要素が実サイズを得た瞬間に測り直す。
    const ro = new ResizeObserver(() => { layout(); draw(current) })
    ro.observe(cv)

    layout()
    current = scrollProgress().t
    draw(current)
    raf = requestAnimationFrame(loop)
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
