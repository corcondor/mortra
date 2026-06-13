'use client'
/**
 * /ideas — 作問アイデアツリー
 * 左: インデント箇条書きエディタ / 右: ツリー可視化 (SVG)
 * AIブラッシュアップ → 問題化 → 鉄緑会風PDF保存
 * 水墨画風和風UI
 */
import { useEffect, useMemo, useState } from 'react'
import { InkBackground } from '@/components/InkBackground'

interface TreeNode {
  id: number
  text: string
  depth: number
  children: TreeNode[]
  x: number
  y: number
}

const STORAGE_KEY = 'idea-outline-v1'

const DEFAULT_OUTLINE = `- 通過領域・軌跡もの
  - 正三角形がx軸上を転がる
    - [素材] 頂点の軌跡は円弧の接続
  - 線分の中点の軌跡
- 整数 × 数列の融合
  - $p^n + n^p$ 型の素数判定
- 確率漸化式
  - じゃんけんで「あいこ」が続く確率`

/** インデント箇条書き → ツリー構造にパース */
function parseOutline(text: string): TreeNode[] {
  const roots: TreeNode[] = []
  const stack: TreeNode[] = []
  let id = 0

  for (const raw of text.split('\n')) {
    if (!raw.trim()) continue
    const m = raw.match(/^(\s*)-\s*(.+)$/)
    if (!m) continue
    const depth = Math.floor(m[1].length / 2)
    const node: TreeNode = { id: id++, text: m[2].trim(), depth, children: [], x: 0, y: 0 }

    while (stack.length > depth) stack.pop()
    if (stack.length === 0) roots.push(node)
    else stack[stack.length - 1].children.push(node)
    stack[depth] = node
    stack.length = depth + 1
  }
  return roots
}

/** tidy tree レイアウト: 葉に連番y、内部ノードは子の平均 */
function layout(roots: TreeNode[]): { nodes: TreeNode[]; links: [TreeNode, TreeNode][]; height: number } {
  const nodes: TreeNode[] = []
  const links: [TreeNode, TreeNode][] = []
  let leafY = 0

  function visit(n: TreeNode) {
    nodes.push(n)
    n.x = 30 + n.depth * 230
    if (n.children.length === 0) {
      n.y = 40 + leafY * 64
      leafY++
    } else {
      for (const c of n.children) { links.push([n, c]); visit(c) }
      n.y = n.children.reduce((s, c) => s + c.y, 0) / n.children.length
    }
  }
  for (const r of roots) visit(r)
  return { nodes, links, height: Math.max(200, 40 + leafY * 64 + 40) }
}

const DEPTH_STYLE = [
  { fill: '#ffffff', stroke: '#2a2a2e', text: '#2a2a2e' },   // テーマ
  { fill: '#eef4ff', stroke: '#3b6bb5', text: '#27496d' },   // 観点
  { fill: '#fdf0ee', stroke: '#b54b3b', text: '#7a2e22' },   // 素材
  { fill: '#eefaf0', stroke: '#3b8a4e', text: '#1f5e2e' },   // 方針
]

type Phase = 'idle' | 'brushup' | 'problemize' | 'compiling'

export default function IdeasPage() {
  const [outline, setOutline] = useState(DEFAULT_OUTLINE)
  const [prevOutline, setPrevOutline] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [generated, setGenerated] = useState<{ title: string; statement: string; solution: string } | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) setOutline(saved)
  }, [])
  useEffect(() => {
    const t = setTimeout(() => localStorage.setItem(STORAGE_KEY, outline), 400)
    return () => clearTimeout(t)
  }, [outline])

  const tree = useMemo(() => layout(parseOutline(outline)), [outline])
  const width = 30 + (Math.max(0, ...tree.nodes.map(n => n.depth)) + 1) * 230 + 40

  async function brushup() {
    setPhase('brushup'); setError(null)
    try {
      const res = await fetch('/api/idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'brushup', outline }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)
      setPrevOutline(outline)
      setOutline(data.outline)
    } catch (e: any) { setError(e.message) } finally { setPhase('idle') }
  }

  async function problemize() {
    setPhase('problemize'); setError(null)
    try {
      const res = await fetch('/api/idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'problemize', outline }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)
      setGenerated(data)
    } catch (e: any) { setError(e.message) } finally { setPhase('idle') }
  }

  async function savePdf() {
    if (!generated) return
    setPhase('compiling'); setError(null)
    try {
      const res = await fetch('/api/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc: generated }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.log ? `${data.error}\n${data.log}` : data.error)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      setPdfUrl(prev => { if (prev) URL.revokeObjectURL(prev); return url })
      const a = document.createElement('a')
      a.href = url
      a.download = `${generated.title}.pdf`
      a.click()
    } catch (e: any) { setError(e.message) } finally { setPhase('idle') }
  }

  const busy = phase !== 'idle'

  return (
    <div className="min-h-screen text-[#2a2a2e]" style={{ fontFamily: '"Hiragino Mincho ProN", "Yu Mincho", serif' }}>
      <InkBackground />

      <div className="p-5 max-w-[1600px] mx-auto space-y-4">
        {/* ヘッダ */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-baseline gap-3">
            <h1 className="text-xl font-bold tracking-wider">想樹</h1>
            <span className="text-[11px] text-black/40 tracking-widest">作問アイデアツリー</span>
            <a href="/" className="text-[11px] text-black/40 hover:text-black/70">← Sakumon Station</a>
            <a href="/scan" className="text-[11px] text-black/40 hover:text-black/70">墨写 →</a>
          </div>
          <div className="flex gap-2">
            {prevOutline && (
              <button onClick={() => { setOutline(prevOutline); setPrevOutline(null) }}
                className="px-3 py-1.5 rounded-xl border border-black/20 text-[12px] bg-white/60 hover:bg-white">
                ↩ 元に戻す
              </button>
            )}
            <button onClick={brushup} disabled={busy}
              className="px-4 py-1.5 rounded-xl border border-[#2a2a2e] text-[13px] bg-white/60 hover:bg-white disabled:opacity-40">
              {phase === 'brushup' ? '深掘り中…' : '✦ AIブラッシュアップ'}
            </button>
            <button onClick={problemize} disabled={busy}
              className="px-4 py-1.5 rounded-xl bg-[#2a2a2e] text-white text-[13px] hover:bg-black disabled:opacity-40">
              {phase === 'problemize' ? '作問中…' : '⚡ 問題化'}
            </button>
          </div>
        </div>

        {error && (
          <p className="text-[12px] text-red-700/90 whitespace-pre-wrap bg-red-50/70 rounded-xl p-3 border border-red-200">{error}</p>
        )}

        <div className="grid lg:grid-cols-[380px_1fr] gap-4">
          {/* アウトラインエディタ */}
          <section>
            <label className="text-[11px] text-black/40 tracking-widest">アウトライン（「- 」+ 2スペースインデント）</label>
            <textarea
              value={outline}
              onChange={e => setOutline(e.target.value)}
              spellCheck={false}
              className="w-full rounded-2xl border border-black/15 bg-white/60 backdrop-blur-sm px-4 py-3 text-[13px] font-mono leading-relaxed focus:outline-none focus:border-black/40"
              style={{ height: 'calc(100vh - 180px)', minHeight: 300 }}
            />
          </section>

          {/* ツリー可視化 */}
          <section className="rounded-2xl border border-black/10 bg-white/50 backdrop-blur-sm overflow-auto"
            style={{ height: 'calc(100vh - 180px)', minHeight: 300 }}>
            <svg width={width} height={tree.height}>
              {tree.links.map(([a, b]) => (
                <path key={`${a.id}-${b.id}`}
                  d={`M ${a.x + 200} ${a.y} C ${a.x + 230} ${a.y}, ${b.x - 30} ${b.y}, ${b.x} ${b.y}`}
                  fill="none" stroke="#2a2a2e" strokeWidth={1} opacity={0.5} />
              ))}
              {tree.nodes.map(n => {
                const s = DEPTH_STYLE[Math.min(n.depth, DEPTH_STYLE.length - 1)]
                const lines = n.text.match(/.{1,14}/g) ?? [n.text]
                const h = Math.max(34, lines.length * 16 + 14)
                return (
                  <g key={n.id} transform={`translate(${n.x}, ${n.y - h / 2})`}>
                    <rect width={200} height={h} rx={n.depth === 0 ? h / 2 : 10}
                      fill={s.fill} stroke={s.stroke} strokeWidth={1.2} />
                    {lines.slice(0, 4).map((l, i) => (
                      <text key={i} x={100} y={22 + i * 16} textAnchor="middle"
                        fontSize={11.5} fill={s.text} fontWeight={n.depth === 0 ? 700 : 500}>
                        {l}
                      </text>
                    ))}
                  </g>
                )
              })}
            </svg>
          </section>
        </div>

        {/* 生成された問題 */}
        {generated && (
          <section className="rounded-2xl border border-black/15 bg-white/70 backdrop-blur-sm p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-bold">【{generated.title}】</h2>
              <button onClick={savePdf} disabled={busy}
                className="px-4 py-1.5 rounded-xl bg-[#2a2a2e] text-white text-[13px] hover:bg-black disabled:opacity-40">
                {phase === 'compiling' ? '組版中…' : '📄 鉄緑会風PDFで保存'}
              </button>
            </div>
            <div>
              <div className="text-[11px] text-black/40 tracking-widest mb-1">問題文</div>
              <pre className="text-[12px] font-mono whitespace-pre-wrap bg-white/70 rounded-xl p-3 border border-black/10">{generated.statement}</pre>
            </div>
            <details>
              <summary className="text-[12px] cursor-pointer text-black/50">模範解答を表示</summary>
              <pre className="text-[12px] font-mono whitespace-pre-wrap bg-white/70 rounded-xl p-3 border border-black/10 mt-2">{generated.solution}</pre>
            </details>
            {pdfUrl && (
              <object data={pdfUrl} type="application/pdf" className="w-full rounded-xl border border-black/10 bg-white" style={{ height: 480 }} />
            )}
          </section>
        )}
      </div>
    </div>
  )
}
