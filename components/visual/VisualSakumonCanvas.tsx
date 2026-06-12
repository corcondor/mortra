'use client'

import { PointerEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Background } from '@/components/Background'

type ToolId = 'select' | 'point' | 'segment' | 'circle' | 'polygon' | 'rotate' | 'trace' | 'measure'
type Mode = '2d' | 'passage' | 'verifier'
type Point = { x: number; y: number }

const VIEW_W = 960
const VIEW_H = 620
const SAMPLE_COUNT = 84

const tools: { id: ToolId; label: string; shortcut: string; icon: string }[] = [
  { id: 'select', label: '選択', shortcut: 'V', icon: 'M5 4l10 8-5 1.2 3.2 5.8-2.4 1.3-3.1-5.8L4 18z' },
  { id: 'point', label: '点', shortcut: 'P', icon: 'M12 8a4 4 0 100 8 4 4 0 000-8z' },
  { id: 'segment', label: '線分', shortcut: 'L', icon: 'M5 18L19 6M5 18h4M19 6v4' },
  { id: 'circle', label: '円', shortcut: 'C', icon: 'M12 5a7 7 0 100 14 7 7 0 000-14z' },
  { id: 'polygon', label: '多角形', shortcut: 'G', icon: 'M12 4l7 5v8l-7 4-7-4V9z' },
  { id: 'rotate', label: '回転', shortcut: 'R', icon: 'M17 8a6 6 0 11-2.2-2.2M17 4v4h-4' },
  { id: 'trace', label: '通過領域', shortcut: 'T', icon: 'M5 15c4-7 10-7 14 0M5 18c4-4 10-4 14 0' },
  { id: 'measure', label: '測定', shortcut: 'M', icon: 'M4 17L17 4l3 3L7 20zM8 17l-2-2M11 14l-2-2M14 11l-2-2' },
]

function degToRad(value: number) {
  return value * Math.PI / 180
}

function triangleVertices(center: Point, radius: number, angleDeg: number) {
  const base = degToRad(angleDeg - 90)
  return [0, 1, 2].map((i) => {
    const a = base + i * Math.PI * 2 / 3
    return {
      x: center.x + Math.cos(a) * radius,
      y: center.y + Math.sin(a) * radius,
    }
  })
}

function polygonArea(points: Point[]) {
  if (points.length < 3) return 0
  let sum = 0
  for (let i = 0; i < points.length; i++) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    sum += a.x * b.y - b.x * a.y
  }
  return Math.abs(sum) / 2
}

function convexHull(points: Point[]) {
  const sorted = [...points].sort((a, b) => a.x === b.x ? a.y - b.y : a.x - b.x)
  if (sorted.length <= 1) return sorted

  const cross = (o: Point, a: Point, b: Point) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
  const lower: Point[] = []
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop()
    lower.push(p)
  }

  const upper: Point[] = []
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop()
    upper.push(p)
  }

  upper.pop()
  lower.pop()
  return lower.concat(upper)
}

function pointString(points: Point[]) {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
}

function pathFrom(points: Point[]) {
  if (points.length === 0) return ''
  return `M ${points.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L ')}`
}

function insideSquare(p: Point, square: { x: number; y: number; size: number }) {
  return p.x >= square.x && p.x <= square.x + square.size && p.y >= square.y && p.y <= square.y + square.size
}

function useAnimationFrame(enabled: boolean, onFrame: () => void) {
  useEffect(() => {
    if (!enabled) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      if (now - last > 36) {
        last = now
        onFrame()
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [enabled, onFrame])
}

function ToolIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function VisualSakumonCanvas() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [tool, setTool] = useState<ToolId>('trace')
  const [mode, setMode] = useState<Mode>('passage')
  const [isPlaying, setIsPlaying] = useState(true)
  const [frame, setFrame] = useState(43)
  const [center, setCenter] = useState<Point>({ x: 498, y: 330 })
  const [radius, setRadius] = useState(118)
  const [startAngle, setStartAngle] = useState(-38)
  const [endAngle, setEndAngle] = useState(84)
  const [dragging, setDragging] = useState(false)
  const [toast, setToast] = useState('Autosaved locally')

  const square = useMemo(() => ({ x: 288, y: 142, size: 334 }), [])
  const currentAngle = startAngle + (endAngle - startAngle) * frame / 100
  const vertices = useMemo(
    () => triangleVertices(center, radius, currentAngle),
    [center, currentAngle, radius],
  )

  const traces = useMemo(() => {
    const output: Point[][] = [[], [], []]
    const all: Point[] = []
    for (let i = 0; i <= SAMPLE_COUNT; i++) {
      const a = startAngle + (endAngle - startAngle) * i / SAMPLE_COUNT
      const tri = triangleVertices(center, radius, a)
      tri.forEach((p, idx) => {
        output[idx].push(p)
        all.push(p)
      })
    }
    return { byVertex: output, hull: convexHull(all), all }
  }, [center, endAngle, radius, startAngle])

  const verifier = useMemo(() => {
    const area = polygonArea(traces.hull)
    const samplesInSquare = traces.all.filter((p) => insideSquare(p, square)).length
    const currentInside = vertices.filter((p) => insideSquare(p, square)).length
    const side = Math.sqrt(3) * radius
    return {
      area,
      side,
      samplesInSquare,
      currentInside,
      enoughSweep: Math.abs(endAngle - startAngle) >= 60,
      centerInside: insideSquare(center, square),
    }
  }, [center, endAngle, radius, square, startAngle, traces.all, traces.hull, vertices])

  const sceneGraph = useMemo(() => ({
    objects: [
      { id: 'S', type: 'square', size: Math.round(square.size), position: [square.x, square.y] },
      { id: 'P', type: 'rotation_center', position: [Math.round(center.x), Math.round(center.y)] },
      { id: 'ABC', type: 'equilateral_triangle', side: Math.round(verifier.side) },
      { id: 'R', type: 'passage_region', area: Math.round(verifier.area) },
    ],
    relations: [
      { type: 'rotates_about', subject: 'ABC', object: 'P' },
      { type: 'sweeps', subject: 'ABC', object: 'R', range: [startAngle, endAngle] },
      { type: 'intersects', subject: 'R', object: 'S', samples: verifier.samplesInSquare },
    ],
  }), [center, endAngle, square, startAngle, verifier.area, verifier.samplesInSquare, verifier.side])

  const operationHistory = useMemo(() => [
    `正方形 S を配置 size=${square.size}`,
    `点 P=(${Math.round(center.x)}, ${Math.round(center.y)}) を回転中心に設定`,
    `正三角形 ABC の外接半径 r=${Math.round(radius)}`,
    `角度範囲 ${startAngle}° → ${endAngle}° を掃引`,
    `通過領域 R を ${traces.hull.length} 頂点の近似境界で抽出`,
  ], [center, endAngle, radius, square.size, startAngle, traces.hull.length])

  const generatedProblem = useMemo(() => {
    const side = Math.round(verifier.side)
    return `正方形 S の近くに点 P を取り、一辺 ${side} の正三角形 ABC を点 P のまわりに ${Math.abs(endAngle - startAngle)}° 回転させる。三角形 ABC が通過する領域の境界を図示し、その面積を求めよ。`
  }, [endAngle, startAngle, verifier.side])

  const advanceFrame = useCallback(() => {
    setFrame((value) => value >= 100 ? 0 : value + 1)
  }, [])

  useAnimationFrame(isPlaying, advanceFrame)

  useEffect(() => {
    const payload = JSON.stringify({ center, radius, startAngle, endAngle })
    localStorage.setItem('visual-sakumon-canvas:v0', payload)
  }, [center, endAngle, radius, startAngle])

  const toSvgPoint = (event: PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return center
    const rect = svg.getBoundingClientRect()
    return {
      x: (event.clientX - rect.left) * VIEW_W / rect.width,
      y: (event.clientY - rect.top) * VIEW_H / rect.height,
    }
  }

  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    const p = toSvgPoint(event)
    const distance = Math.hypot(p.x - center.x, p.y - center.y)
    if (distance <= 24 || tool === 'point' || tool === 'select') {
      setDragging(true)
      setCenter(p)
      setToast('P moved')
      event.currentTarget.setPointerCapture(event.pointerId)
    }
  }

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!dragging) return
    setCenter(toSvgPoint(event))
  }

  const copyScene = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(sceneGraph, null, 2))
      setToast('Scene Graph copied')
    } catch {
      setToast('Clipboard unavailable')
    }
  }

  const resetScene = () => {
    setCenter({ x: 498, y: 330 })
    setRadius(118)
    setStartAngle(-38)
    setEndAngle(84)
    setFrame(43)
    setToast('Scene reset')
  }

  return (
    <div className="relative h-screen overflow-hidden text-white">
      <Background />
      <main className="relative z-10 flex h-screen flex-col bg-black/10">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 bg-black/28 px-3 backdrop-blur-2xl md:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <a href="/" className="grid h-8 w-8 place-items-center rounded-md border border-white/12 bg-white/8 text-[13px] font-semibold text-white/80">S</a>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold tracking-normal md:text-base">Visual Sakumon Canvas</h1>
              <p className="hidden text-[11px] text-white/45 sm:block">通過領域を、画面操作と検証器から作問する v0</p>
            </div>
          </div>

          <div className="hidden items-center gap-1 rounded-md border border-white/10 bg-white/6 p-1 md:flex">
            {(['2d', 'passage', 'verifier'] as Mode[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className={`rounded px-3 py-1.5 text-[11px] font-medium transition ${mode === item ? 'bg-white text-black' : 'text-white/62 hover:bg-white/10'}`}
              >
                {item === '2d' ? '2D' : item === 'passage' ? 'Passage' : 'Verifier'}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsPlaying((value) => !value)}
              className="rounded-md border border-white/12 bg-white/8 px-3 py-1.5 text-[11px] font-medium text-white/78 hover:bg-white/12"
            >
              {isPlaying ? 'Pause' : 'Play'}
            </button>
            <button
              type="button"
              onClick={copyScene}
              className="hidden rounded-md bg-apple-blue px-3 py-1.5 text-[11px] font-semibold text-white shadow-lg shadow-blue-950/30 hover:bg-blue-500 sm:block"
            >
              Export JSON
            </button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_auto_minmax(190px,32vh)] gap-3 p-3 lg:grid-cols-[54px_minmax(0,1fr)_330px] lg:grid-rows-1">
          <aside className="order-2 flex gap-2 overflow-x-auto rounded-md border border-white/10 bg-black/30 p-2 backdrop-blur-2xl lg:order-none lg:flex-col lg:overflow-visible">
            {tools.map((item) => (
              <button
                key={item.id}
                type="button"
                title={`${item.label} (${item.shortcut})`}
                onClick={() => {
                  setTool(item.id)
                  if (item.id === 'trace') setMode('passage')
                  if (item.id === 'measure') setMode('verifier')
                }}
                className={`grid h-10 w-10 shrink-0 place-items-center rounded-md border text-white/76 transition ${tool === item.id ? 'border-apple-blue/60 bg-apple-blue/25 text-white shadow-glow' : 'border-white/8 bg-white/5 hover:bg-white/10'}`}
              >
                <ToolIcon path={item.icon} />
              </button>
            ))}
          </aside>

          <section className="order-1 flex min-h-0 flex-col overflow-hidden rounded-md border border-white/10 bg-slate-950/76 shadow-2xl shadow-black/35 backdrop-blur-xl lg:order-none">
            <div className="flex shrink-0 items-center justify-between border-b border-white/10 px-3 py-2">
              <div className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-apple-green shadow-[0_0_18px_rgba(48,209,88,0.8)]" />
                <span className="text-[11px] font-medium text-white/65">mode: {mode}</span>
                <span className="hidden text-[11px] text-white/38 sm:block">drag P to rewrite the scene</span>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-white/45">
                <span>{toast}</span>
                <button type="button" onClick={resetScene} className="rounded border border-white/10 px-2 py-1 text-white/62 hover:bg-white/8">Reset</button>
              </div>
            </div>

            <div className="relative min-h-0 flex-1 p-2 md:p-4">
              <svg
                ref={svgRef}
                viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
                role="img"
                aria-label="通過領域作問キャンバス"
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={() => setDragging(false)}
                onPointerLeave={() => setDragging(false)}
                className="h-full w-full touch-none rounded-md border border-white/10 bg-[#07101d] shadow-inner"
              >
                <defs>
                  <pattern id="visual-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                    <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(255,255,255,0.055)" strokeWidth="1" />
                  </pattern>
                  <linearGradient id="region-fill" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0%" stopColor="#18f1c8" stopOpacity="0.42" />
                    <stop offset="100%" stopColor="#0a84ff" stopOpacity="0.24" />
                  </linearGradient>
                  <filter id="soft-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                <rect width={VIEW_W} height={VIEW_H} fill="url(#visual-grid)" />
                <rect x={square.x} y={square.y} width={square.size} height={square.size} fill="rgba(255,255,255,0.025)" stroke="rgba(255,255,255,0.38)" strokeWidth="2" rx="4" />
                <text x={square.x + 12} y={square.y + 26} fill="rgba(255,255,255,0.62)" fontSize="18" fontWeight="600">S</text>

                {mode !== '2d' && (
                  <>
                    <polygon points={pointString(traces.hull)} fill="url(#region-fill)" stroke="rgba(34,211,238,0.9)" strokeWidth="2" filter="url(#soft-glow)" />
                    {traces.byVertex.map((path, index) => (
                      <path
                        key={index}
                        d={pathFrom(path)}
                        fill="none"
                        stroke={index === 0 ? '#7dd3fc' : index === 1 ? '#34d399' : '#fbbf24'}
                        strokeWidth="2"
                        strokeDasharray={index === 0 ? '0' : '8 8'}
                        opacity="0.7"
                      />
                    ))}
                  </>
                )}

                <line x1={center.x} y1={center.y} x2={vertices[0].x} y2={vertices[0].y} stroke="rgba(255,255,255,0.18)" strokeWidth="1.5" />
                <polygon points={pointString(vertices)} fill="rgba(255,255,255,0.09)" stroke="#ffffff" strokeWidth="2.5" />
                {vertices.map((p, index) => (
                  <g key={index}>
                    <circle cx={p.x} cy={p.y} r="7" fill={index === 0 ? '#7dd3fc' : index === 1 ? '#34d399' : '#fbbf24'} stroke="#07101d" strokeWidth="2" />
                    <text x={p.x + 12} y={p.y - 10} fill="white" fontSize="18" fontWeight="700">{String.fromCharCode(65 + index)}</text>
                  </g>
                ))}
                <g>
                  <circle cx={center.x} cy={center.y} r="15" fill="#0a84ff" fillOpacity="0.24" stroke="#0a84ff" strokeWidth="2.5" />
                  <circle cx={center.x} cy={center.y} r="3" fill="#ffffff" />
                  <text x={center.x + 18} y={center.y + 6} fill="#bfdbfe" fontSize="17" fontWeight="700">P</text>
                </g>

                {mode === 'verifier' && (
                  <g>
                    <rect x="28" y="28" width="288" height="92" rx="8" fill="rgba(0,0,0,0.46)" stroke="rgba(255,255,255,0.14)" />
                    <text x="46" y="58" fill="#d1fae5" fontSize="17" fontWeight="700">Verifier</text>
                    <text x="46" y="84" fill="rgba(255,255,255,0.72)" fontSize="14">area ≒ {Math.round(verifier.area).toLocaleString()} px^2</text>
                    <text x="46" y="106" fill="rgba(255,255,255,0.72)" fontSize="14">samples in S: {verifier.samplesInSquare}/{traces.all.length}</text>
                  </g>
                )}
              </svg>
            </div>

            <div className="grid shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-t border-white/10 px-3 py-2">
              <span className="text-[11px] text-white/42">{startAngle}°</span>
              <input
                aria-label="animation frame"
                type="range"
                min="0"
                max="100"
                value={frame}
                onChange={(event) => {
                  setIsPlaying(false)
                  setFrame(Number(event.target.value))
                }}
                className="accent-apple-blue"
              />
              <span className="text-[11px] text-white/42">{endAngle}°</span>
            </div>
          </section>

          <aside className="order-3 min-h-0 overflow-y-auto rounded-md border border-white/10 bg-black/34 p-3 backdrop-blur-2xl">
            <section className="rounded-md border border-white/10 bg-white/6 p-3">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Scene Graph</h2>
                <span className="rounded bg-white/8 px-2 py-1 text-[10px] text-white/55">{sceneGraph.objects.length} objects</span>
              </div>
              <div className="space-y-2">
                {sceneGraph.objects.map((obj) => (
                  <div key={obj.id} className="rounded border border-white/8 bg-black/18 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white/86">{obj.id}</span>
                      <span className="text-[10px] text-white/42">{obj.type}</span>
                    </div>
                    <pre className="mt-1 whitespace-pre-wrap break-all text-[10px] leading-4 text-white/46">{JSON.stringify(obj)}</pre>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-3 rounded-md border border-white/10 bg-white/6 p-3">
              <h2 className="mb-3 text-sm font-semibold">Verifier</h2>
              <div className="space-y-2">
                {[
                  ['center inside square', verifier.centerInside],
                  ['sweep angle >= 60deg', verifier.enoughSweep],
                  ['region intersects S', verifier.samplesInSquare > 0],
                  ['current triangle visible', verifier.currentInside > 0],
                ].map(([label, ok]) => (
                  <div key={String(label)} className="flex items-center justify-between rounded border border-white/8 bg-black/18 px-3 py-2 text-xs">
                    <span className="text-white/62">{label}</span>
                    <span className={ok ? 'text-apple-green' : 'text-apple-pink'}>{ok ? 'pass' : 'warn'}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-3 rounded-md border border-white/10 bg-white/6 p-3">
              <h2 className="mb-3 text-sm font-semibold">Parameters</h2>
              <div className="space-y-3">
                <label className="block">
                  <span className="mb-1 flex justify-between text-[11px] text-white/54"><span>triangle radius</span><span>{Math.round(radius)}</span></span>
                  <input type="range" min="72" max="170" value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="w-full accent-apple-green" />
                </label>
                <label className="block">
                  <span className="mb-1 flex justify-between text-[11px] text-white/54"><span>start angle</span><span>{startAngle}°</span></span>
                  <input type="range" min="-120" max="20" value={startAngle} onChange={(e) => setStartAngle(Number(e.target.value))} className="w-full accent-apple-blue" />
                </label>
                <label className="block">
                  <span className="mb-1 flex justify-between text-[11px] text-white/54"><span>end angle</span><span>{endAngle}°</span></span>
                  <input type="range" min="20" max="160" value={endAngle} onChange={(e) => setEndAngle(Number(e.target.value))} className="w-full accent-apple-blue" />
                </label>
              </div>
            </section>

            <section className="mt-3 rounded-md border border-white/10 bg-white/6 p-3">
              <h2 className="mb-2 text-sm font-semibold">Generated Problem</h2>
              <p className="text-xs leading-6 text-white/66">{generatedProblem}</p>
            </section>

            <section className="mt-3 rounded-md border border-white/10 bg-white/6 p-3">
              <h2 className="mb-3 text-sm font-semibold">Operation History</h2>
              <ol className="space-y-2">
                {operationHistory.map((item, index) => (
                  <li key={item} className="grid grid-cols-[22px_minmax(0,1fr)] gap-2 text-xs text-white/58">
                    <span className="grid h-5 w-5 place-items-center rounded bg-white/8 text-[10px] text-white/42">{index + 1}</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </section>
          </aside>
        </div>
      </main>
    </div>
  )
}
