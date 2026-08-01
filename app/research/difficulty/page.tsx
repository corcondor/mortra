'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import history from '@/data/mathos/difficulty-history.json'
import progress from '@/data/mathos/research-progress.json'
import { MathText } from '@/components/MathText'

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

type AuditExample = (typeof progress.high_depth_examples)[number]

function StatusRail() {
  const rows = [
    { label: '型付き射の一本道', value: progress.summary.morphism_chains, total: progress.summary.problems, state: '実装済み', color: '#067647' },
    { label: '厳密計算 + 独立検算', value: progress.summary.verified, total: progress.summary.problems, state: '実装済み', color: '#067647' },
    { label: '証明依存グラフ（DAG）', value: progress.summary.proof_graphs, total: progress.summary.problems, state: '未実装', color: '#d92d20' },
    { label: '人間難易度モデル', value: 0, total: progress.summary.problems, state: `指標無効 AUC ${progress.summary.human_difficulty_auc}`, color: '#b54708' },
  ]
  return (
    <div className="divide-y divide-[#d8dee9] border-y border-[#d8dee9]">
      {rows.map(row => {
        const ratio = row.total ? row.value / row.total : 0
        return (
          <div key={row.label} className="grid gap-2 py-4 sm:grid-cols-[220px_1fr_180px] sm:items-center">
            <p className="text-sm font-medium">{row.label}</p>
            <div className="h-2 overflow-hidden bg-[#e4e7ec]" aria-label={`${row.value}/${row.total}`}>
              <div className="h-full" style={{ width: `${ratio * 100}%`, background: row.color }} />
            </div>
            <p className="text-xs tabular-nums text-[#475467] sm:text-right">
              <span style={{ color: row.color }} className="font-medium">{row.state}</span>
              {' '}· {row.value}/{row.total}
            </p>
          </div>
        )
      })}
    </div>
  )
}

function RepresentationDiagram({ example }: { example: AuditExample }) {
  const shown = example.morphisms.slice(0, 6)
  const remaining = example.morphisms.length - shown.length
  return (
    <div>
      <div className="flex min-w-max items-center gap-2 overflow-x-auto pb-3">
        <div className="w-28 shrink-0 border-2 border-[#175cd3] bg-white px-3 py-3 text-center text-xs font-medium">数学対象</div>
        {shown.map((morphism, index) => (
          <div key={`${morphism}-${index}`} className="contents">
            <span className="text-[#98a2b3]">→</span>
            <div className="w-40 shrink-0 border border-[#98a2b3] bg-white px-3 py-3 text-center text-[11px] leading-4">{morphism}</div>
          </div>
        ))}
        {remaining > 0 && <><span className="text-[#98a2b3]">→</span><div className="shrink-0 text-xs text-[#667085]">ほか{remaining}射</div></>}
        <span className="text-[#98a2b3]">→</span>
        <div className="w-24 shrink-0 border-2 border-[#067647] bg-white px-3 py-3 text-center text-xs font-medium">答え</div>
      </div>
      <div className="mt-4 grid gap-3 border-l-2 border-dashed border-[#d92d20] pl-4 text-xs text-[#667085] sm:grid-cols-4">
        {['補題の依存関係', '失敗した探索枝', '別解・同値な証明', '各辺の証明項'].map(label => (
          <div key={label}><span className="font-medium text-[#d92d20]">未保存</span><br />{label}</div>
        ))}
      </div>
    </div>
  )
}

function EvidenceInspector() {
  const [selected, setSelected] = useState(0)
  const example = progress.high_depth_examples[selected]
  return (
    <div>
      <div className="mb-5 flex gap-2 overflow-x-auto pb-2">
        {progress.high_depth_examples.map((item, index) => (
          <button
            key={item.family_id}
            onClick={() => setSelected(index)}
            className="shrink-0 border px-3 py-2 text-left text-xs"
            style={{ borderColor: selected === index ? '#175cd3' : '#d0d5dd', background: selected === index ? '#eff4ff' : 'white' }}
          >
            深さ {item.morphisms.length} · {item.domain}
          </button>
        ))}
      </div>
      <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div>
          <p className="mb-3 text-sm leading-7 text-[#344054]"><MathText text={example.statement_tex} /></p>
          <RepresentationDiagram example={example} />
        </div>
        <dl className="border-l border-[#d8dee9] pl-5 text-xs leading-6 text-[#475467]">
          <dt className="text-[#667085]">保存形式</dt><dd className="font-medium text-[#14213d]">一本道の配列</dd>
          <dt className="mt-3 text-[#667085]">生成元</dt><dd>{example.source_generator}</dd>
          <dt className="mt-3 text-[#667085]">検証</dt><dd>{example.verification_method}</dd>
          <dt className="mt-3 text-[#667085]">判定</dt><dd className="font-medium text-[#d92d20]">証明グラフではない</dd>
        </dl>
      </div>
    </div>
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
          <h1 className="text-3xl font-medium tracking-normal sm:text-4xl">MathOS 進捗監査</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[#475467]">
            問題数ではなく、現在どこまで実装され、何が未実装かを実データから表示します。結論は、検証付きの一本道は動く一方、証明探索グラフと人間難易度モデルは未完成です。
          </p>
          <div className="mt-5 flex flex-wrap gap-3 text-xs">
            <Link href="/blackboard" className="border border-[#14213d] bg-[#14213d] px-3 py-2 text-white">実際の導出を見る</Link>
            <Link href="/research/selfauthored" className="border border-[#98a2b3] bg-white px-3 py-2">全問題.texの解析</Link>
            <span className="px-1 py-2 text-[#667085]">監査生成 {new Date(progress.generated_at).toLocaleString('ja-JP')}</span>
          </div>
        </header>

        <section className="border-b border-[#d8dee9] py-7">
          <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <div>
              <h2 className="text-xl font-medium">現在の判定</h2>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-[#344054]">
                以前の配信プールにあった「1つの数値を橋にした2段合成」{progress.summary.excluded_non_interacting_compositions}問を除外し、現在は{progress.summary.problems}問です。深さ10以上は{progress.structure.depth_10_or_more}問ですが、証明DAGを持つ難問候補は{progress.summary.proof_graphs}問です。
              </p>
            </div>
            <div className="border-l-4 border-[#d92d20] bg-[#fff1f0] px-5 py-4 text-sm leading-6 text-[#7a271a]">
              <strong>難易度上昇は未証明</strong><br />
              旧スコアと問題文長の相関は {progress.measurement_audit.legacy_score_vs_statement_length_pearson}。人手評価AUCは {progress.summary.human_difficulty_auc} で、難易度指標として無効です。
            </div>
          </div>
        </section>

        <section className="border-b border-[#d8dee9] py-8">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
            <div><h2 className="text-lg font-medium">実装状況</h2><p className="mt-1 text-xs text-[#667085]">現在の{progress.summary.problems}問を直接集計</p></div>
            <p className="text-xs text-[#667085]">保留研究候補 {progress.summary.unresolved}件 · 深さ下限 {progress.summary.unresolved_depth_floor}</p>
          </div>
          <StatusRail />
        </section>

        <section className="border-b border-[#d8dee9] py-8">
          <div className="mb-5">
            <h2 className="text-lg font-medium">証明表現の実物</h2>
            <p className="mt-1 text-xs text-[#667085]">最深部の問題を選択して、保存されている射と保存されていない証明情報を確認</p>
          </div>
          <EvidenceInspector />
        </section>

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
          <h2 className="text-lg font-medium">データセットの使われ方</h2>
          <div className="mt-4 grid gap-6 text-sm leading-7 text-[#344054] md:grid-cols-2">
            <p>世界コーパス{progress.summary.reference_corpus.toLocaleString('ja-JP')}問は主に表層新規性の照合に使われています。ユーザー問題{progress.summary.human_runtime_corpus}問は旧難易度特徴の参照に使われましたが、そのモデルはAUC {progress.summary.human_difficulty_auc}で失敗しました。</p>
            <p>つまり、渡された問題の証明をDAGへ変換して生成器へ還流する処理は未実装です。今後は問題文の類似度ではなく、補題依存・制約骨格・解法圧縮を抽出して学習対象にする必要があります。</p>
          </div>
        </section>
      </div>
    </main>
  )
}
