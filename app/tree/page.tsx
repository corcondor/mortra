'use client'
/**
 * /tree — 概念ツリー作問エンジン (MathOS)
 * 数学概念を型付き積み木として木構造ネットワークに組み、
 * 検証済み(記号証明/数値認証)の問題を引き当てる。木を組み替えると別問題になる。
 */
import { useMemo, useState } from 'react'
import { Background } from '@/components/Background'
import { AuthGuard } from '@/components/AuthGuard'
import { MathText } from '@/components/MathText'
import poolData from '@/data/mathos/concept_tree_pool.json'

type PoolProblem = {
  tree_signature: string
  statement_tex: string
  answer_tex: string
  answer_exact: string
  query: string
  certification: string
  extreme_value_numeric: number
  maximizer_t_numeric: number
}

const POOL = (poolData as { problems: PoolProblem[] }).problems
const BY_SIG = new Map(POOL.map((p) => [p.tree_signature, p]))

const C_VALUES = [4, 5, 6, 7, 8, 9, 10, 12]
const K_VALUES = [2, 3, 4, 5]

function singleSig(q: string, c: number, k: number): string {
  return `${q}[](HullArea[](Embed[k=${k}](EvenQuartic[c=${c}]())))`
}
function branchSig(q: string, c: number, k1: number, k2: number): string {
  const [a, b] = k1 < k2 ? [k1, k2] : [k2, k1]
  return `${q}[](Difference[](HullArea[](Embed[k=${a}](EvenQuartic[c=${c}]())),HullArea[](Embed[k=${b}](EvenQuartic[c=${c}]()))))`
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`h-8 min-w-[2.2rem] rounded-md border px-3 text-[13px] font-medium transition-colors ${
        active
          ? 'border-[#175cd3] bg-[#eff6ff] text-[#175cd3]'
          : 'border-[#d0d5dd] bg-white text-[#475467] hover:border-[#98a2b3]'
      }`}
    >
      {children}
    </button>
  )
}

function TreeBox({
  x,
  y,
  title,
  sub,
  tone,
}: {
  x: number
  y: number
  title: string
  sub: string
  tone: string
}) {
  const tones: Record<string, [string, string, string]> = {
    gray: ['#f2f4f7', '#d0d5dd', '#344054'],
    blue: ['#eff6ff', '#b2ccff', '#175cd3'],
    teal: ['#effcf6', '#a6e9c8', '#0f766e'],
    purple: ['#f5f3ff', '#d1c4f5', '#6941c6'],
    amber: ['#fffaeb', '#fde68a', '#b54708'],
  }
  const [bg, br, tx] = tones[tone]
  return (
    <g>
      <rect x={x} y={y} width={150} height={44} rx={8} fill={bg} stroke={br} />
      <text x={x + 75} y={y + 19} textAnchor="middle" fontSize={13} fontWeight={500} fill={tx}>
        {title}
      </text>
      <text x={x + 75} y={y + 35} textAnchor="middle" fontSize={11} fill={tx}>
        {sub}
      </text>
    </g>
  )
}

function TreeInner() {
  const [mode, setMode] = useState<'single' | 'branch'>('single')
  const [c, setC] = useState(5)
  const [k, setK] = useState(3)
  const [k2, setK2] = useState(5)
  const [query, setQuery] = useState('Maximize')

  const sig =
    mode === 'single' ? singleSig(query, c, k) : branchSig(query, c, k, k2)
  const problem = BY_SIG.get(sig)
  const kSame = mode === 'branch' && k === k2

  return (
    <div className="relative min-h-screen">
      <Background />
      <div className="relative mx-auto max-w-4xl px-5 py-10">
        <header className="mb-6">
          <h1 className="text-[22px] font-bold text-[#14213d]">概念ツリー作問エンジン</h1>
          <p className="mt-1 text-[13px] leading-6 text-[#667085]">
            数学概念を型付きの積み木として木構造に組む。木を組み替えると別の問題になる。
            表示される問題は MathOS が検証(記号証明または数値認証)を通したものだけ。
          </p>
        </header>

        <div className="grid gap-5 md:grid-cols-[1fr_1.1fr]">
          {/* 左: 木を組む */}
          <section className="rounded-xl border border-[#e4e7ec] bg-white p-5">
            <h2 className="mb-4 text-[13px] font-semibold text-[#14213d]">積み木を組む</h2>

            <div className="mb-4">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                組み方
              </div>
              <div className="flex gap-2">
                <Chip active={mode === 'single'} onClick={() => setMode('single')}>
                  一直線
                </Chip>
                <Chip active={mode === 'branch'} onClick={() => setMode('branch')}>
                  枝分かれ(差)
                </Chip>
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                基底 x⁴ − c x² + t の c
              </div>
              <div className="flex flex-wrap gap-2">
                {C_VALUES.map((v) => (
                  <Chip key={v} active={c === v} onClick={() => setC(v)}>
                    {v}
                  </Chip>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                埋め込み 各実根 r → (r, rᵏ)
              </div>
              <div className="flex flex-wrap gap-2">
                {K_VALUES.map((v) => (
                  <Chip key={v} active={k === v} onClick={() => setK(v)}>
                    k={v}
                  </Chip>
                ))}
              </div>
            </div>

            {mode === 'branch' && (
              <div className="mb-4">
                <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                  もう一方の埋め込み (r, rᵏ²)
                </div>
                <div className="flex flex-wrap gap-2">
                  {K_VALUES.map((v) => (
                    <Chip key={v} active={k2 === v} onClick={() => setK2(v)}>
                      k={v}
                    </Chip>
                  ))}
                </div>
              </div>
            )}

            <div className="mb-2">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                問い(凸包の面積の…)
              </div>
              <div className="flex gap-2">
                <Chip active={query === 'Maximize'} onClick={() => setQuery('Maximize')}>
                  最大値
                </Chip>
                <Chip active={query === 'Minimize'} onClick={() => setQuery('Minimize')}>
                  最小値
                </Chip>
              </div>
            </div>

            {/* 木の図 */}
            <svg viewBox="0 0 320 250" className="mt-4 w-full">
              {mode === 'single' ? (
                <>
                  <TreeBox x={85} y={10} title={query === 'Maximize' ? '最大値' : '最小値'} sub="問い" tone="amber" />
                  <TreeBox x={85} y={70} title="凸包の面積" sub="HullArea" tone="teal" />
                  <TreeBox x={85} y={130} title="埋め込み" sub={`(r, r^${k})`} tone="blue" />
                  <TreeBox x={85} y={190} title={`x⁴−${c}x²+t`} sub="の4実根" tone="gray" />
                  <line x1={160} y1={54} x2={160} y2={70} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={160} y1={114} x2={160} y2={130} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={160} y1={174} x2={160} y2={190} stroke="#d0d5dd" strokeWidth={2} />
                </>
              ) : (
                <>
                  <TreeBox x={85} y={10} title={query === 'Maximize' ? '最大値' : '最小値'} sub="問い" tone="amber" />
                  <TreeBox x={85} y={70} title="差" sub="Difference" tone="purple" />
                  <TreeBox x={5} y={130} title="面積" sub={`(r, r^${k})`} tone="teal" />
                  <TreeBox x={165} y={130} title="面積" sub={`(r, r^${k2})`} tone="teal" />
                  <TreeBox x={85} y={190} title={`x⁴−${c}x²+t`} sub="の4実根" tone="gray" />
                  <line x1={160} y1={54} x2={160} y2={70} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={140} y1={114} x2={80} y2={130} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={180} y1={114} x2={240} y2={130} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={80} y1={174} x2={140} y2={190} stroke="#d0d5dd" strokeWidth={2} />
                  <line x1={240} y1={174} x2={180} y2={190} stroke="#d0d5dd" strokeWidth={2} />
                </>
              )}
            </svg>
          </section>

          {/* 右: 結果 */}
          <section className="rounded-xl border border-[#e4e7ec] bg-white p-5">
            <h2 className="mb-4 text-[13px] font-semibold text-[#14213d]">組み上がった問題</h2>

            {kSame ? (
              <div className="rounded-lg border border-[#fde68a] bg-[#fffaeb] p-4 text-[13px] text-[#b54708]">
                差をとる2つの埋め込みは別の指数にしてください（k ≠ k²）。
              </div>
            ) : problem ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-[#e4e7ec] bg-[#fcfcfd] p-4">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#98a2b3]">
                    問題
                  </div>
                  <div className="text-[15px] leading-8 text-[#14213d]">
                    <MathText text={problem.statement_tex} />
                  </div>
                </div>

                <div className="rounded-lg border border-[#b2ccff] bg-[#eff6ff] p-4">
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[#175cd3]">
                    答え
                  </div>
                  <div className="text-[20px] text-[#175cd3]">
                    <MathText text={`\\(${problem.answer_tex}\\)`} large />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  {problem.certification.startsWith('symbolic') ? (
                    <span className="rounded-full border border-[#a6e9c8] bg-[#effcf6] px-2.5 py-1 font-medium text-[#0f766e]">
                      ✓ 記号的に証明済み
                    </span>
                  ) : (
                    <span className="rounded-full border border-[#fde68a] bg-[#fffaeb] px-2.5 py-1 font-medium text-[#b54708]">
                      ✓ 数値認証(1e-9)
                    </span>
                  )}
                  <span className="rounded-full border border-[#e4e7ec] bg-white px-2.5 py-1 text-[#667085]">
                    最適 t ≈ {problem.maximizer_t_numeric}
                  </span>
                  <span className="rounded-full border border-[#e4e7ec] bg-white px-2.5 py-1 font-mono text-[#667085]">
                    {problem.tree_signature.split('[')[0]} → {problem.answer_exact}
                  </span>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-[#e4e7ec] bg-[#fcfcfd] p-4 text-[13px] leading-6 text-[#667085]">
                この組み合わせは検証で棄却されました。極値が境界で退化する
                (4実根が重なる)か、答えが綺麗な閉形式にならない木です。
                <span className="mt-2 block text-[#98a2b3]">
                  「美しい結果」だけが残る — これがエンジンの選別です。別の k や問いを試してください。
                </span>
              </div>
            )}

            <div className="mt-5 border-t border-[#e4e7ec] pt-4 text-[11px] leading-5 text-[#98a2b3]">
              収録済み: {POOL.length} 問（一直線 {POOL.filter((p) => !p.tree_signature.includes('Difference')).length} ・
              枝分かれ {POOL.filter((p) => p.tree_signature.includes('Difference')).length}）。
              基底族を増やすほど組める木が増えます。
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export default function TreePage() {
  return (
    <AuthGuard>
      <TreeInner />
    </AuthGuard>
  )
}
