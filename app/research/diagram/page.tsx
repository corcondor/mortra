'use client'

import { useMemo, useState } from 'react'

import demo from '@/data/finite-state-diagram-demo.json'
import experiment from '@/data/finite-state-diagram-experiment.json'

type Demo = typeof demo

function shortState(id: string) {
  return id.split(':state:').at(-1) ?? id
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export default function ExecutableDiagramResearchPage() {
  const artifact = demo as Demo
  const [step, setStep] = useState(0)
  const currentIndex = useMemo(() => {
    const { preperiod, length } = artifact.period
    return step < artifact.states.length
      ? step
      : preperiod + ((step - preperiod) % length)
  }, [artifact.period, artifact.states.length, step])
  const active = artifact.states[currentIndex]
  const byId = useMemo(() => new Map(artifact.states.map(state => [state.id, state])), [artifact.states])
  const maxStep = 18

  return (
    <main className="min-h-screen bg-[#09090b] text-zinc-100">
      <header className="border-b border-zinc-800 px-5 py-5 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-emerald-400">MORTRA Research / Diagram 01</p>
            <h1 className="mt-2 text-2xl font-semibold sm:text-3xl">実行可能な有限状態遷移図</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
              漸化式を法17で見た状態を、証明可能な遷移と周期に変換する。同じ状態から推論結果と表示を生成している。
            </p>
          </div>
          <div className="border-l-2 border-emerald-400 pl-4">
            <div className="text-xs text-zinc-500">CERTIFICATE</div>
            <div className="mt-1 font-mono text-sm text-emerald-300">CERTIFIED / exact replay</div>
          </div>
        </div>
      </header>

      <section className="border-b border-zinc-800 px-5 py-6 sm:px-8">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.7fr)]">
          <div className="min-w-0 border border-zinc-800 bg-[#111113] p-3 sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-xs text-zinc-500">STATE AT STEP {step}</div>
                <div className="mt-1 font-mono text-lg text-white">({active.values.join(', ')})</div>
              </div>
              <div className="text-right text-xs leading-5 text-zinc-400">
                <div>周期 {artifact.period.length}</div>
                <div>添字 {artifact.query.requestedIndex} → {artifact.query.reducedIndex}</div>
              </div>
            </div>

            <div className="aspect-[16/8] min-h-[250px] w-full overflow-hidden bg-black">
              <svg viewBox="0 0 1040 340" className="h-full w-full" role="img" aria-label="法17の漸化式が作る3状態の周期">
                <defs>
                  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
                  </marker>
                </defs>
                {artifact.transitions.map(edge => {
                  const from = byId.get(edge.from)
                  const to = byId.get(edge.to)
                  if (!from || !to) return null
                  const dx = to.x - from.x
                  const dy = to.y - from.y
                  const length = Math.hypot(dx, dy) || 1
                  const inset = 37
                  return (
                    <line
                      key={edge.id}
                      x1={from.x + (dx / length) * inset}
                      y1={from.y + (dy / length) * inset}
                      x2={to.x - (dx / length) * inset}
                      y2={to.y - (dy / length) * inset}
                      stroke="#71717a"
                      strokeWidth="3"
                      markerEnd="url(#arrow)"
                    />
                  )
                })}
                {artifact.states.map(state => {
                  const selected = state.index === currentIndex
                  return (
                    <g key={state.id} transform={`translate(${state.x} ${state.y})`}>
                      <circle
                        r="34"
                        fill={selected ? '#052e25' : '#18181b'}
                        stroke={selected ? '#34d399' : '#52525b'}
                        strokeWidth={selected ? 4 : 2}
                      />
                      <text y="5" textAnchor="middle" fill={selected ? '#a7f3d0' : '#e4e4e7'} fontSize="16" fontFamily="ui-monospace, monospace">
                        {shortState(state.id)}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>

            <div className="mt-5 grid grid-cols-[36px_auto_1fr_auto_36px] items-center gap-3">
              <button
                type="button"
                aria-label="一つ前の状態"
                title="一つ前の状態"
                onClick={() => setStep(value => Math.max(0, value - 1))}
                disabled={step === 0}
                className="h-9 w-9 border border-zinc-700 text-lg text-zinc-300 disabled:cursor-not-allowed disabled:opacity-30"
              >
                ‹
              </button>
              <span className="font-mono text-xs text-zinc-500">0</span>
              <input
                aria-label="遷移ステップ"
                type="range"
                min="0"
                max={maxStep}
                value={step}
                onChange={event => setStep(Number(event.target.value))}
                className="w-full accent-emerald-400"
              />
              <span className="font-mono text-xs text-zinc-500">{maxStep}</span>
              <button
                type="button"
                aria-label="次の状態"
                title="次の状態"
                onClick={() => setStep(value => Math.min(maxStep, value + 1))}
                disabled={step === maxStep}
                className="h-9 w-9 border border-zinc-700 text-lg text-zinc-300 disabled:cursor-not-allowed disabled:opacity-30"
              >
                ›
              </button>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="border-t border-zinc-700 pt-4">
              <div className="text-xs font-semibold uppercase text-zinc-500">Typed state</div>
              <p className="mt-2 font-mono text-sm leading-6 text-zinc-200">
                (aₙ, aₙ₊₁) ∈ (Z/17Z)²
              </p>
            </div>
            <div className="border-t border-zinc-700 pt-4">
              <div className="text-xs font-semibold uppercase text-zinc-500">Legal rewrite</div>
              <p className="mt-2 text-sm leading-6 text-zinc-300">
                完全な状態が再出現した後だけ、添字を周期3で縮約する。
              </p>
            </div>
            <div className="border-t border-zinc-700 pt-4">
              <div className="text-xs font-semibold uppercase text-zinc-500">Forgotten</div>
              <p className="mt-2 text-sm leading-6 text-zinc-300">
                元の整数の大きさと、初期状態から到達しない剰余状態。
              </p>
            </div>
            <div className="border-t border-zinc-700 pt-4">
              <div className="text-xs font-semibold uppercase text-zinc-500">Query</div>
              <p className="mt-2 text-sm leading-6 text-zinc-300">
                a<sub>{artifact.query.requestedIndex}</sub> mod 17 ={' '}
                <strong className="font-mono text-lg text-emerald-300">{artifact.query.answer}</strong>
              </p>
            </div>
          </aside>
        </div>
      </section>

      <section className="border-b border-zinc-800 px-5 py-7 sm:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-blue-400">Fixed A/B experiment</p>
              <h2 className="mt-2 text-xl font-semibold">図が探索量を変えたか</h2>
            </div>
            <div className="font-mono text-xs text-zinc-500">digest {experiment.dataset_digest}</div>
          </div>
          <div className="grid gap-px overflow-hidden border border-zinc-800 bg-zinc-800 sm:grid-cols-4">
            {[
              ['直接反復', pct(experiment.summary.baseline_certified_solve_rate)],
              ['遷移図', pct(experiment.summary.diagram_certified_solve_rate)],
              ['新規に閉じた問い', `${experiment.summary.newly_closed_proofs} / ${experiment.summary.cases}`],
              ['偽証明の受理', `${experiment.summary.tampered_certificates_false_accepts}`],
            ].map(([label, value]) => (
              <div key={label} className="bg-[#111113] px-4 py-5">
                <div className="text-xs text-zinc-500">{label}</div>
                <div className="mt-2 font-mono text-2xl text-white">{value}</div>
              </div>
            ))}
          </div>
          <p className="mt-4 max-w-4xl text-sm leading-6 text-zinc-400">
            比較対象は同じ型付き漸化式。直接反復は10,000ステップで棄却し、図側だけが到達軌道を周期で商にした。
            これは剰余漸化式18件の限定結果であり、数学全体の正答率ではない。
          </p>
        </div>
      </section>

      <section className="px-5 py-7 sm:px-8">
        <div className="mx-auto grid max-w-6xl gap-7 md:grid-cols-2">
          <div className="border-l-2 border-emerald-400 pl-4">
            <div className="text-xs font-semibold uppercase text-emerald-400">Certified semantic transport</div>
            <p className="mt-2 text-sm leading-6 text-zinc-300">
              状態、遷移、周期、添字縮約は漸化式から再計算され、各辺を独立に検査する。推論器が利用してよい情報はこちらだけ。
            </p>
          </div>
          <div className="border-l-2 border-amber-400 pl-4">
            <div className="text-xs font-semibold uppercase text-amber-400">Design heuristic</div>
            <p className="mt-2 text-sm leading-6 text-zinc-300">
              円周上の配置、色、間隔は読みやすさのための選択であり証明ではない。配置を変えても数学的な結論は変わらない。
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}
