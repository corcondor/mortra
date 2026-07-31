'use client'

import { useMemo, useState } from 'react'
import history from '@/data/mathos/difficulty-history.json'

type Snapshot = (typeof history.snapshots)[number]

const W = 1040
const H = 430
const M = { top: 28, right: 28, bottom: 54, left: 58 }

function formatDate(timestamp: string) {
  return new Intl.DateTimeFormat('ja-JP', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Tokyo',
  }).format(new Date(timestamp))
}

function pathFor(
  rows: Snapshot[],
  x: (row: Snapshot) => number,
  y: (value: number) => number,
  read: (row: Snapshot) => number,
) {
  return rows.map((row, index) => `${index ? 'L' : 'M'}${x(row)},${y(read(row))}`).join(' ')
}

function DifficultyChart({ rows }: { rows: Snapshot[] }) {
  const [selected, setSelected] = useState(rows.length - 1)
  const times = rows.map(row => new Date(row.timestamp).getTime())
  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)
  const x = (row: Snapshot) => M.left + (
    (new Date(row.timestamp).getTime() - minTime) / Math.max(1, maxTime - minTime)
  ) * (W - M.left - M.right)
  const y = (value: number) => H - M.bottom - value / 14 * (H - M.top - M.bottom)
  const current = rows[selected]
  const ticks = [0, 2, 4, 6, 8, 10, 12, 14]
  const dateTicks = Array.from({ length: 6 }, (_, index) => {
    const time = minTime + (maxTime - minTime) * index / 5
    return { time, x: M.left + (W - M.left - M.right) * index / 5 }
  })

  function selectAt(clientX: number, target: SVGSVGElement) {
    const rect = target.getBoundingClientRect()
    const svgX = (clientX - rect.left) * W / rect.width
    let best = 0
    let distance = Infinity
    rows.forEach((row, index) => {
      const next = Math.abs(x(row) - svgX)
      if (next < distance) { best = index; distance = next }
    })
    setSelected(best)
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[#14213d]">検証済み構造深度</p>
          <p className="text-xs text-[#667085]">1問を構成する型付き変換の段数</p>
        </div>
        <p className="text-sm tabular-nums text-[#344054]">
          {formatDate(current.timestamp)}　中央値 <strong>{current.morphism_depth.median}</strong>
          　上位10% <strong>{current.morphism_depth.p90}</strong>
          　最大 <strong>{current.morphism_depth.max}</strong>
        </p>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block w-full touch-none"
        role="img"
        aria-label="2026年7月26日から31日までのMathOS問題構造深度。中央値、上位10パーセント点、最大値を表示。"
        onPointerMove={event => selectAt(event.clientX, event.currentTarget)}
        onPointerDown={event => selectAt(event.clientX, event.currentTarget)}
      >
        <title>MathOS問題構造深度の推移</title>
        {ticks.map(tick => (
          <g key={tick}>
            <line x1={M.left} x2={W - M.right} y1={y(tick)} y2={y(tick)} stroke="#d8dee9" />
            <text x={M.left - 12} y={y(tick) + 4} textAnchor="end" fontSize="12" fill="#667085">{tick}</text>
          </g>
        ))}
        {dateTicks.map(tick => (
          <text key={tick.time} x={tick.x} y={H - 18} textAnchor="middle" fontSize="12" fill="#667085">
            {new Intl.DateTimeFormat('ja-JP', { month: 'numeric', day: 'numeric', timeZone: 'Asia/Tokyo' }).format(new Date(tick.time))}
          </text>
        ))}
        <path d={pathFor(rows, x, y, row => row.morphism_depth.max)} fill="none" stroke="#98a2b3" strokeWidth="2" />
        <path d={pathFor(rows, x, y, row => row.morphism_depth.p90)} fill="none" stroke="#067647" strokeWidth="2.5" />
        <path d={pathFor(rows, x, y, row => row.morphism_depth.median)} fill="none" stroke="#175cd3" strokeWidth="4" />
        <line x1={x(current)} x2={x(current)} y1={M.top} y2={H - M.bottom} stroke="#344054" strokeWidth="1" />
        <circle cx={x(current)} cy={y(current.morphism_depth.median)} r="6" fill="#175cd3" stroke="white" strokeWidth="2" />
        <circle cx={x(current)} cy={y(current.morphism_depth.p90)} r="5" fill="#067647" stroke="white" strokeWidth="2" />
        <circle cx={x(current)} cy={y(current.morphism_depth.max)} r="5" fill="#98a2b3" stroke="white" strokeWidth="2" />
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-6 gap-y-2 text-xs text-[#475467]">
        <span><i className="mr-2 inline-block h-0.5 w-5 bg-[#175cd3] align-middle" />中央値</span>
        <span><i className="mr-2 inline-block h-0.5 w-5 bg-[#067647] align-middle" />上位10%点</span>
        <span><i className="mr-2 inline-block h-0.5 w-5 bg-[#98a2b3] align-middle" />最大値</span>
      </div>
      <div className="mt-4 border-l-2 border-[#175cd3] pl-3 text-sm text-[#344054]">
        <p className="font-medium">{current.message}</p>
        <p className="mt-1 text-xs text-[#667085]">
          {current.problem_count}問・{current.family_count}族・独立検証率 {(current.verified_rate * 100).toFixed(0)}%・commit {current.commit}
        </p>
      </div>
    </div>
  )
}

function CountChart({ rows }: { rows: Snapshot[] }) {
  const max = Math.max(...rows.map(row => row.problem_count))
  const minTime = Math.min(...rows.map(row => new Date(row.timestamp).getTime()))
  const maxTime = Math.max(...rows.map(row => new Date(row.timestamp).getTime()))
  const x = (row: Snapshot) => M.left + (
    (new Date(row.timestamp).getTime() - minTime) / Math.max(1, maxTime - minTime)
  ) * (W - M.left - M.right)
  const y = (value: number) => 230 - 34 - value / max * (230 - 54)
  return (
    <svg viewBox={`0 0 ${W} 230`} className="block w-full" role="img" aria-label="問題数と構造族数の推移">
      <title>問題数と構造族数の推移</title>
      {[0, 200, 400, 600].map(tick => (
        <g key={tick}>
          <line x1={M.left} x2={W - M.right} y1={y(tick)} y2={y(tick)} stroke="#e4e7ec" />
          <text x={M.left - 12} y={y(tick) + 4} textAnchor="end" fontSize="12" fill="#667085">{tick}</text>
        </g>
      ))}
      <path d={pathFor(rows, x, y, row => row.problem_count)} fill="none" stroke="#175cd3" strokeWidth="3" />
      <path d={pathFor(rows, x, y, row => row.family_count)} fill="none" stroke="#d97706" strokeWidth="2" />
      <text x={W - M.right} y={y(rows.at(-1)?.problem_count ?? 0) - 10} textAnchor="end" fontSize="12" fill="#14213d">
        問題 {rows.at(-1)?.problem_count}
      </text>
      <text x={W - M.right} y={y(rows.at(-1)?.family_count ?? 0) + 18} textAnchor="end" fontSize="12" fill="#14213d">
        族 {rows.at(-1)?.family_count}
      </text>
    </svg>
  )
}

export default function DifficultyResearchPage() {
  const rows = useMemo(
    () => [...history.snapshots].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp)),
    [],
  )
  const first = rows[0]
  const latest = rows.at(-1)!

  return (
    <main className="h-screen overflow-y-auto bg-[#f7f9fc] text-[#14213d]">
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-7 lg:py-12">
        <header className="border-b border-[#d8dee9] pb-6">
          <p className="text-xs font-medium uppercase tracking-widest text-[#175cd3]">MathOS Research Meter</p>
          <h1 className="mt-2 text-3xl font-medium tracking-normal sm:text-4xl">問題生成の構造難度</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[#475467]">
            Gitに保存された{rows.length}時点を同じ規則で再計算。数値の大きさではなく、答えまでに必要な検証済み変換の段数を追跡しています。
          </p>
        </header>

        <section className="grid gap-5 border-b border-[#d8dee9] py-6 sm:grid-cols-3">
          <div><p className="text-xs text-[#667085]">構造深度の中央値</p><p className="mt-1 text-3xl font-medium tabular-nums">{first.morphism_depth.median} → {latest.morphism_depth.median}</p></div>
          <div><p className="text-xs text-[#667085]">最大構造深度</p><p className="mt-1 text-3xl font-medium tabular-nums">{first.morphism_depth.max} → {latest.morphism_depth.max}</p></div>
          <div><p className="text-xs text-[#667085]">検証済み構造数</p><p className="mt-1 text-3xl font-medium tabular-nums">{first.problem_count} → {latest.problem_count}</p></div>
        </section>

        <section className="py-8">
          <DifficultyChart rows={rows} />
        </section>

        <section className="border-t border-[#d8dee9] py-8">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-medium">検証済み問題と族</h2>
            <p className="text-xs text-[#667085]">同じ数値変種は構造数に重複計上しない</p>
          </div>
          <CountChart rows={rows} />
        </section>

        <section className="border-t border-[#d8dee9] py-8">
          <h2 className="text-lg font-medium">読み方</h2>
          <div className="mt-4 grid gap-6 text-sm leading-7 text-[#344054] md:grid-cols-2">
            <p>中央値は3から6へ上昇し、標準的な生成問題は多段化しました。一方、最大値は11から12、上位10%点は10から8です。最高難度が一様に伸びたという証拠ではありません。</p>
            <p>この指標は構造の複雑さです。人間が感じる難しさとの既存スコアのAUCは0.086で未較正のため、入試難易度や数オリ級を表す値としては使用していません。</p>
          </div>
        </section>
      </div>
    </main>
  )
}
