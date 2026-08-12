'use client'

/**
 * 証明が進むと、図がその場で伸びる。
 *
 * ここに置いてある時間軸は手で書いていない。lib/proof-scene.ts が
 * 「問題文 → 型付き述語 → 前向き推論 → 証明 DAG」を潰して作った物をそのまま再生している。
 * だから図は説明の挿絵ではなく、証明のその段そのものになる。
 *
 *   ?p=<id>        どの問題か
 *   ?theme=board   黒地（既定は紙＝白地）
 *   ?export=1      1080×1920 で書き出し用に固定し、フレームを刻む
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import corpus from '@/data/formalized-geometry.json'
import visualReasoningDemo from '@/data/visual-reasoning-demo.json'
import { write2d, strokeLength } from '@/lib/handwriting2d'
import {
  compileScene, formulaOf,
  type Beat, type Fact, type Mark, type Pt, type ProofScene,
} from '@/lib/proof-scene'

// ---------------------------------------------------------------------------
// 形式化器の出力 → シーン
// ---------------------------------------------------------------------------

type Raw = {
  id: string; title: string; text: string; status: string
  points: string[]
  predicates: { name: string; args: string[] }[]
  goal: { name: string; args: string[] } | null
  coordinates: Record<string, [number, number]>
}

/**
 * 形式化器は中点を coll + cong の二本で出す。
 * 人はそれを「中点」という一つの事実として読むので、束ねてから証明に入れる。
 * 束ねないと、図に同じ線が二度引かれ、文が二行に割れる。
 */
function toFacts(raw: Raw): { premises: Fact[]; goal: Fact | null } {
  const P = raw.predicates
  const used = new Set<number>()
  const premises: Fact[] = []

  P.forEach((c, i) => {
    if (c.name !== 'cong' || used.has(i)) return
    const [a, m1, m2, b] = c.args
    if (m1 !== m2) return
    const j = P.findIndex((o, k) => !used.has(k) && o.name === 'coll'
      && new Set(o.args).size === 3 && o.args.includes(m1) && o.args.includes(a) && o.args.includes(b))
    if (j < 0) return
    used.add(i); used.add(j)
    premises.push({ pred: 'midp', args: [m1, a, b] })
  })

  P.forEach((c, i) => {
    if (used.has(i)) return
    if (['perp', 'para', 'coll', 'cong', 'eqangle'].includes(c.name)) {
      premises.push({ pred: c.name as Fact['pred'], args: c.args })
    }
  })

  const goal = raw.goal && ['perp', 'para', 'coll', 'cong', 'eqangle'].includes(raw.goal.name)
    ? { pred: raw.goal.name as Fact['pred'], args: raw.goal.args }
    : null
  return { premises, goal }
}

/** 点名は小文字で来る。図には大文字で置く */
const up = (s: string) => s.toUpperCase()

function buildScene(raw: Raw): ProofScene | null {
  const { premises, goal } = toFacts(raw)
  if (!goal) return null
  const points: Record<string, Pt> = {}
  for (const [k, v] of Object.entries(raw.coordinates)) points[k] = { x: v[0], y: v[1] }
  // 問題文に「三角形ABC」と書いてあれば、その三辺を図の骨組みにする
  const triangles = [...raw.text.matchAll(/(?:三角形|△)\s*([A-Z])\s*([A-Z])\s*([A-Z])/g)]
    .map(m => [m[1].toLowerCase(), m[2].toLowerCase(), m[3].toLowerCase()] as [string, string, string])
    .filter(t => t.every(n => points[n]))
  return compileScene({ title: raw.title, statement: raw.text, premises, goal, points, triangles })
}

// ---------------------------------------------------------------------------
// 描画
// ---------------------------------------------------------------------------

type Palette = {
  bg: string; ink: string; faint: string; accent: string; paper: string
}

const PAPER: Palette = { bg: '#ffffff', ink: '#111111', faint: '#c9c9c9', accent: '#111111', paper: '#ffffff' }
const BOARD: Palette = { bg: '#000000', ink: '#ffffff', faint: '#4a4a4a', accent: '#ffffff', paper: '#000000' }

/** 図の座標 → 画面座標。余白を大きく取り、縦横比は崩さない */
function framer(points: Record<string, Pt>, box: { x: number; y: number; w: number; h: number }) {
  const vs = Object.values(points)
  const xs = vs.map(p => p.x), ys = vs.map(p => p.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const spanX = Math.max(maxX - minX, 1e-6), spanY = Math.max(maxY - minY, 1e-6)
  const k = Math.min(box.w / spanX, box.h / spanY) * 0.86
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2
  return (p: Pt) => ({
    x: box.x + box.w / 2 + (p.x - cx) * k,
    // 数学の y は上向き、画面の y は下向き
    y: box.y + box.h / 2 - (p.y - cy) * k,
  })
}

type Seg = { a: Pt; b: Pt }

function markToPolylines(m: Mark, X: Record<string, Pt>, to: (p: Pt) => Pt): Pt[][] {
  const g = (n: string) => (X[n] ? to(X[n]) : null)
  switch (m.kind) {
    case 'segment':
    case 'parallel':
    case 'tick':
    case 'line': {
      const a = g(m.from), b = g(m.to)
      if (!a || !b) return []
      if (m.kind === 'line') {
        // 直線は線分より少し伸ばす。図として「直線である」ことが見える
        const d = { x: b.x - a.x, y: b.y - a.y }
        const L = Math.hypot(d.x, d.y) || 1
        const e = 0.14
        return [[
          { x: a.x - d.x * e, y: a.y - d.y * e },
          { x: b.x + d.x * e, y: b.y + d.y * e },
        ]]
      }
      if (m.kind === 'segment') return [[a, b]]
      // 印（合同の斜線 / 平行の矢羽根）は線分の中点に置く
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
      const d = { x: b.x - a.x, y: b.y - a.y }
      const L = Math.hypot(d.x, d.y) || 1
      const u = { x: d.x / L, y: d.y / L }
      const n = { x: -u.y, y: u.x }
      const s = 9
      if (m.kind === 'tick') {
        return [[
          { x: mid.x - n.x * s, y: mid.y - n.y * s },
          { x: mid.x + n.x * s, y: mid.y + n.y * s },
        ]]
      }
      return [[
        { x: mid.x - u.x * s + n.x * s, y: mid.y - u.y * s + n.y * s },
        { x: mid.x + u.x * s, y: mid.y + u.y * s },
        { x: mid.x - u.x * s - n.x * s, y: mid.y - u.y * s - n.y * s },
      ]]
    }
    case 'rightangle': {
      const o = g(m.at), p = g(m.from), q = g(m.to)
      if (!o || !p || !q) return []
      const unit = (t: Pt) => {
        const d = { x: t.x - o.x, y: t.y - o.y }
        const L = Math.hypot(d.x, d.y) || 1
        return { x: d.x / L, y: d.y / L }
      }
      const u = unit(p), v = unit(q), s = 15
      return [[
        { x: o.x + u.x * s, y: o.y + u.y * s },
        { x: o.x + (u.x + v.x) * s, y: o.y + (u.y + v.y) * s },
        { x: o.x + v.x * s, y: o.y + v.y * s },
      ]]
    }
    case 'point': {
      const a = g(m.at)
      if (!a) return []
      const r = 4.2, N = 14
      return [Array.from({ length: N + 1 }, (_, i) => ({
        x: a.x + r * Math.cos((i / N) * Math.PI * 2),
        y: a.y + r * Math.sin((i / N) * Math.PI * 2),
      }))]
    }
  }
}

/** 折れ線を、長さ比 t (0..1) まで引く */
function drawPartial(ctx: CanvasRenderingContext2D, pts: Pt[], t: number) {
  if (pts.length < 2) return
  const total = strokeLength(pts)
  if (total === 0) return
  let want = total * Math.min(1, Math.max(0, t))
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i++) {
    const seg = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y)
    if (want >= seg) {
      ctx.lineTo(pts[i].x, pts[i].y)
      want -= seg
    } else {
      const r = seg === 0 ? 0 : want / seg
      ctx.lineTo(pts[i - 1].x + (pts[i].x - pts[i - 1].x) * r, pts[i - 1].y + (pts[i].y - pts[i - 1].y) * r)
      break
    }
  }
  ctx.stroke()
}

// ---------------------------------------------------------------------------

const OUT_W = 1080
const OUT_H = 1920
/** 1 beat あたりのフレーム数。書く → 少し止まる */
const DRAW_FRAMES = 26
const HOLD_FRAMES = 16
const BEAT_FRAMES = DRAW_FRAMES + HOLD_FRAMES

export default function ProofPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [params, setParams] = useState<URLSearchParams | null>(null)
  const [frame, setFrame] = useState(0)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 })

  useEffect(() => { setParams(new URLSearchParams(location.search)) }, [])

  const id = params?.get('p') ?? 'midline'
  const theme = params?.get('theme') === 'board' ? BOARD : PAPER
  const exporting = params?.get('export') === '1'

  const scene = useMemo(() => {
    if (id === 'visual-loop') return visualReasoningDemo as unknown as ProofScene
    const raw = (corpus as unknown as Raw[]).find(r => r.id === id) ?? (corpus as unknown as Raw[])[0]
    if (!raw || raw.status !== 'formalized') return null
    try { return buildScene(raw) } catch { return null }
  }, [id])

  const totalFrames = scene ? scene.beats.length * BEAT_FRAMES + 50 : 0

  // Background tabs can pause requestAnimationFrame. Measure independently so a
  // responsive resize still causes one deterministic draw.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || exporting) return
    const measure = () => {
      const rect = canvas.getBoundingClientRect()
      const next = {
        width: Math.max(1, Math.round(rect.width)),
        height: Math.max(1, Math.round(rect.height)),
      }
      setCanvasSize(current =>
        current.width === next.width && current.height === next.height ? current : next,
      )
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(canvas)
    window.addEventListener('resize', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [exporting])

  // 再生
  useEffect(() => {
    if (!scene || exporting) return
    let raf = 0
    let f = 0
    const tick = () => {
      f = (f + 1) % totalFrames
      setFrame(f)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [scene, exporting, totalFrames])

  // 書き出し。1 フレームずつ描いて API へ送る。
  // ブラウザのスクリーンショットに頼らないので、画面が出ていなくても 1080×1920 で出る。
  useEffect(() => {
    if (!exporting) return
    const w = window as unknown as {
      __proofFrames?: number
      __proofExport?: (dir: string) => Promise<string>
      __proofShot?: (dir: string, n: number) => Promise<string>
      __proofProgress?: number
    }
    w.__proofFrames = totalFrames

    // requestAnimationFrame には乗せない。
    // 画面が表示されていないタブでは rAF が止まるので、待つと永久に返ってこない。
    // 描画は純関数なので、その場で呼んでその場で読み出す。
    const shoot = async (dir: string, n: number, name: string) => {
      const canvas = canvasRef.current
      if (!canvas || !scene) return 'no canvas'
      const ctx = canvas.getContext('2d')
      if (!ctx) return 'no context'
      canvas.width = OUT_W
      canvas.height = OUT_H
      renderFrame(ctx, scene, n, { W: OUT_W, H: OUT_H, dpr: 1, theme })
      const res = await fetch('/api/frame', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ dir, name, dataUrl: canvas.toDataURL('image/png') }),
      })
      return (await res.json()).path ?? 'failed'
    }

    // 全部流す前に絵を確かめるための一枚撮り
    w.__proofShot = (dir, n) => shoot(dir, n, `shot-${String(n).padStart(4, '0')}.png`)
    w.__proofExport = async (dir: string) => {
      for (let n = 0; n < totalFrames; n++) {
        await shoot(dir, n, `${String(n).padStart(4, '0')}.png`)
        w.__proofProgress = n + 1
      }
      return `${totalFrames} frames -> export/frames/${dir}`
    }
  }, [exporting, totalFrames, scene, theme])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !scene) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = exporting ? OUT_W : canvasSize.width || canvas.clientWidth
    const H = exporting ? OUT_H : canvasSize.height || canvas.clientHeight
    if (W <= 0 || H <= 0) return
    const dpr = exporting ? 1 : Math.min(2, window.devicePixelRatio || 1)
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) {
      canvas.width = W * dpr
      canvas.height = H * dpr
    }
    renderFrame(ctx, scene, frame, { W, H, dpr, theme })
  }, [scene, frame, theme, exporting, canvasSize])

  if (!scene) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-white text-zinc-500">
        形式化できた問題がありません（data/formalized-geometry.json）
      </main>
    )
  }

  return (
    <main
      className="flex min-h-[100dvh] flex-col items-center justify-center"
      style={{ background: theme.bg }}
    >
      <canvas
        ref={canvasRef}
        style={
          exporting
            ? { width: OUT_W, height: OUT_H }
            : { width: 'min(92vw, 54vh)', height: 'min(163vw, 96vh)' }
        }
      />
    </main>
  )
}

// ---------------------------------------------------------------------------
// 1 フレームを描く。副作用も React も要らない純関数にしてある。
// 画面が表示されていなくても、書き出し側からそのまま呼べる。
// ---------------------------------------------------------------------------

function renderFrame(
  ctx: CanvasRenderingContext2D,
  scene: ProofScene,
  frame: number,
  o: { W: number; H: number; dpr: number; theme: Palette },
) {
  {
    const { W, H, dpr, theme } = o
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    ctx.fillStyle = theme.bg
    ctx.fillRect(0, 0, W, H)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    const pad = W * 0.09
    // 図が主役。上 55% を図に、下を導出に渡す
    const figBox = { x: pad, y: H * 0.155, w: W - pad * 2, h: H * 0.40 }
    const to = framer(scene.points, figBox)

    // ── 問題文 ─────────────────────────────────────────────
    ctx.fillStyle = theme.ink
    ctx.font = `${Math.round(W * 0.028)}px "Hiragino Mincho ProN", "Yu Mincho", serif`
    ctx.textBaseline = 'top'
    wrapText(ctx, scene.statement, pad, H * 0.075, W - pad * 2, W * 0.045)

    const beatIndex = Math.min(scene.beats.length - 1, Math.floor(frame / BEAT_FRAMES))
    const local = frame - beatIndex * BEAT_FRAMES
    const progress = Math.min(1, local / DRAW_FRAMES)

    // ── 図 ─────────────────────────────────────────────────
    // まず骨組み。三角形は証明の一段ではないので、最初から立っている
    ctx.strokeStyle = theme.ink
    ctx.lineWidth = W * 0.0026
    for (const m of scene.frame) {
      for (const poly of markToPolylines(m, scene.points, to)) drawPartial(ctx, poly, 1)
    }

    // 済んだ段は実線で残す。進行中の段だけ伸びる
    for (let i = 0; i <= beatIndex; i++) {
      const b = scene.beats[i]
      const t = i < beatIndex ? 1 : ease(progress)
      const isCurrent = i === beatIndex
      ctx.strokeStyle = theme.ink
      ctx.lineWidth = b.role === 'goal' ? W * 0.0052 : W * 0.0032
      if (isCurrent && b.role === 'goal') ctx.lineWidth = W * 0.0052
      for (const m of b.draw) {
        for (const poly of markToPolylines(m, scene.points, to)) drawPartial(ctx, poly, t)
      }
    }

    // 点の名前。図が出そろってから置く
    ctx.fillStyle = theme.ink
    ctx.font = `${Math.round(W * 0.030)}px "Times New Roman", serif`
    ctx.textBaseline = 'middle'
    const shown = new Set<string>()
    scene.frame.forEach(m => {
      if ('at' in m) shown.add(m.at)
      else if ('from' in m) { shown.add(m.from); shown.add(m.to) }
    })
    for (let i = 0; i <= beatIndex; i++) {
      for (const m of scene.beats[i].draw) {
        const names = 'at' in m ? [m.at] : 'from' in m ? [m.from, m.to] : []
        names.forEach(n => shown.add(n))
      }
      scene.beats[i].claim.args.forEach(n => shown.add(n))
    }
    for (const name of shown) {
      const p = scene.points[name]
      if (!p) continue
      const s = to(p)
      const off = labelOffset(name, scene.points, to, s)
      ctx.fillText(up(name), s.x + off.x, s.y + off.y)
    }

    // ── 導出 ───────────────────────────────────────────────
    // 図の下に、その段で言えたことを一行ずつ書く。図と字は同じ beat から出ている
    const lineH = H * 0.052
    const baseY = H * 0.585
    const maxLines = Math.floor((H * 0.94 - baseY) / lineH)
    const from = Math.max(0, beatIndex - maxLines + 1)

    for (let i = from; i <= beatIndex; i++) {
      const b = scene.beats[i]
      const y = baseY + (i - from) * lineH
      const t = i < beatIndex ? 1 : ease(progress)

      // 段の種類を左の記号で示す。前提・導出・結論
      ctx.fillStyle = b.role === 'goal' ? theme.ink : theme.faint
      ctx.font = `${Math.round(W * 0.019)}px "Times New Roman", serif`
      ctx.textBaseline = 'middle'
      ctx.fillText(b.role === 'given' ? '与' : b.role === 'goal' ? '∴' : '⇒', pad, y + lineH * 0.34)

      // 式は手で書く。書き順のまま出る
      ctx.strokeStyle = theme.ink
      ctx.lineWidth = b.role === 'goal' ? W * 0.0034 : W * 0.0024
      const written = write2d(b.formula, pad + W * 0.055, y, W * 0.036)
      const n = written.strokes.length
      const upto = t * n
      written.strokes.forEach((stroke, k) => {
        const st = Math.min(1, Math.max(0, upto - k))
        if (st > 0) drawPartial(ctx, stroke, st)
      })

      // 根拠の一行。読める大きさで、式のすぐ下に置く
      if (t > 0.7) {
        ctx.fillStyle = theme.faint
        ctx.font = `${Math.round(W * 0.0182)}px "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif`
        ctx.textBaseline = 'top'
        const line = b.says.length > 44 ? b.says.slice(0, 43) + '…' : b.says
        ctx.fillText(line, pad + W * 0.055, y + lineH * 0.56)
      }
    }

    // ── 証明終わり ─────────────────────────────────────────
    if (beatIndex === scene.beats.length - 1 && progress >= 1 && scene.proved) {
      ctx.fillStyle = theme.ink
      ctx.font = `${Math.round(W * 0.022)}px "Times New Roman", serif`
      ctx.textBaseline = 'alphabetic'
      ctx.fillText('□', W - pad - W * 0.03, H * 0.955)
    }

    // 条件の明示。実際にその条件で走った時だけ出す
    ctx.fillStyle = theme.faint
    ctx.font = `${Math.round(W * 0.0155)}px "SF Mono", ui-monospace, monospace`
    ctx.textBaseline = 'alphabetic'
    ctx.fillText('no LLM   no external API   forward chaining + numeric check', pad, H * 0.955)
  }
}

// ---------------------------------------------------------------------------

function ease(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, w: number, lh: number) {
  let line = ''
  let cursor = y
  for (const ch of text) {
    const test = line + ch
    if (ctx.measureText(test).width > w && line) {
      ctx.fillText(line, x, cursor)
      cursor += lh
      line = ch
    } else {
      line = test
    }
  }
  if (line) ctx.fillText(line, x, cursor)
}

/**
 * ラベルを図の外側へ置く。
 * 重心から離れる向きに逃がすだけだが、これだけで線とラベルの衝突はほぼ消える。
 */
function labelOffset(
  name: string,
  points: Record<string, Pt>,
  to: (p: Pt) => Pt,
  at: Pt,
): Pt {
  const screen = Object.values(points).map(to)
  const cx = screen.reduce((s, p) => s + p.x, 0) / screen.length
  const cy = screen.reduce((s, p) => s + p.y, 0) / screen.length
  const d = { x: at.x - cx, y: at.y - cy }
  const L = Math.hypot(d.x, d.y)
  const r = 21
  if (L < 1e-3) return { x: r, y: -r }
  return { x: (d.x / L) * r, y: (d.y / L) * r }
}
