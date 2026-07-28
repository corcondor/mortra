'use client'

/**
 * 黒板 — MathOS が問題を作る過程を、授業の板書のように順に書き出す。
 *
 * 見せているのは演出ではなく実データである。トレースバック方式では
 *   構築 → 演繹閉包のノード → traceback で必要な前提を逆算 → 切り出し
 * という過程を経ており、その各段（前提・射の連鎖・問題文に現れない中間対象）が
 * 問題の記録にそのまま残っている。ここではそれを順番に表示しているだけで、
 * 文章を後から作っているわけではない。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MathText } from '@/components/MathText'
import verifiedBatch from '@/data/mathos/continuous_verified_problem_batch1.json'

type PoolProblem = {
  family_id?: string
  domain?: string
  statement_tex?: string
  answer_tex?: string
  solution_tex?: string
  lift_certificate?: { morphism_chain?: string[] }
  verification?: { method?: string }
  curriculum_certificate?: {
    lowering_chain?: string[]
    lowering_by_morphism?: { morphism?: string; primitives?: string[] }[]
  }
  parameters?: {
    construction?: string
    premises?: string[]
    hidden?: string[]
    scope?: string[]
    depth?: number
  }
}

type Step = {
  heading: string
  body: string
  tone: 'premise' | 'morphism' | 'hidden' | 'ask' | 'answer' | 'verify'
}

const POOL = (verifiedBatch as { problems: PoolProblem[] }).problems ?? []

/** 導出の跡を持つ問題だけが板書できる */
const TRACEABLE = POOL.filter(
  (problem) => (problem.parameters?.premises?.length ?? 0) > 0,
)

const TONE_COLOR: Record<Step['tone'], string> = {
  premise: '#f4f1e8',
  morphism: '#bfe3c6',
  hidden: '#f5d98b',
  ask: '#ffffff',
  answer: '#ffd9a0',
  verify: '#9fc4b4',
}

function buildSteps(problem: PoolProblem): Step[] {
  const steps: Step[] = []
  const parameters = problem.parameters ?? {}

  for (const premise of parameters.premises ?? []) {
    steps.push({ heading: '対象を構築する', body: premise, tone: 'premise' })
  }

  // 射ごとの還元先を使う。lowering_chain は重複を除いた集合なので、
  // 位置で対応づけると別の射の道具が並んでしまう。
  const chain = problem.lift_certificate?.morphism_chain ?? []
  const perMorphism = problem.curriculum_certificate?.lowering_by_morphism ?? []
  const toolsOf = new Map(
    perMorphism.map((entry) => [entry.morphism ?? '', entry.primitives ?? []]),
  )
  chain.forEach((morphism, index) => {
    const tools = toolsOf.get(morphism) ?? []
    const tail = tools.length ? `　→ 高校の道具: ${tools.join(' , ')}` : ''
    steps.push({
      heading: `導出 ${index + 1}/${chain.length}`,
      body: `${morphism}${tail}`,
      tone: 'morphism',
    })
  })

  for (const hidden of parameters.hidden ?? []) {
    steps.push({
      heading: '問題文に現れない中間対象',
      body: hidden,
      tone: 'hidden',
    })
  }

  if (problem.statement_tex) {
    steps.push({ heading: '切り出した問題', body: problem.statement_tex, tone: 'ask' })
  }
  if (problem.answer_tex) {
    steps.push({ heading: '答え', body: `\\(${problem.answer_tex}\\)`, tone: 'answer' })
  }
  if (problem.verification?.method) {
    steps.push({
      heading: '検証',
      body: `${problem.verification.method}（厳密計算 + 独立検算）`,
      tone: 'verify',
    })
  }
  return steps
}

/** 1行を左から右へ書いていく。KaTeX で組んだあと clip-path で出す */
function ChalkLine({
  step,
  active,
  done,
  speed,
}: {
  step: Step
  active: boolean
  done: boolean
  speed: number
}) {
  const [progress, setProgress] = useState(done ? 1 : 0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (done) { setProgress(1); return }
    if (!active) { setProgress(0); return }
    const duration = Math.max(500, Math.min(3200, step.body.length * 26)) / speed
    const started = performance.now()
    const tick = (now: number) => {
      const ratio = Math.min(1, (now - started) / duration)
      setProgress(ratio)
      if (ratio < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [active, done, step.body, speed])

  const visible = active || done
  return (
    <div
      className="mb-5"
      style={{ opacity: visible ? 1 : 0, transition: 'opacity .25s' }}
    >
      <div
        className="mb-1 text-[11px] tracking-[0.25em]"
        style={{ color: 'rgba(244,241,232,.45)' }}
      >
        {step.heading}
      </div>
      <div className="relative">
        <div
          style={{
            color: TONE_COLOR[step.tone],
            clipPath: `inset(0 ${(1 - progress) * 100}% 0 0)`,
            textShadow: '0 0 1px rgba(255,255,255,.55), 0 1px 2px rgba(0,0,0,.35)',
            fontSize: step.tone === 'ask' ? '1.15rem' : '1rem',
            lineHeight: 1.9,
          }}
        >
          <MathText text={step.body} />
        </div>
        {active && progress < 1 && (
          <span
            aria-hidden
            className="pointer-events-none absolute top-0 h-full w-[2px]"
            style={{
              left: `${progress * 100}%`,
              background: 'rgba(255,255,255,.75)',
              boxShadow: '0 0 8px rgba(255,255,255,.8)',
            }}
          />
        )}
      </div>
    </div>
  )
}

export default function BlackboardPage() {
  const [index, setIndex] = useState(0)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const boardRef = useRef<HTMLDivElement>(null)

  const problem = TRACEABLE[index] ?? null
  const steps = useMemo(() => (problem ? buildSteps(problem) : []), [problem])

  // 1行書き終わるごとに次へ進む
  useEffect(() => {
    if (!playing || cursor >= steps.length) return
    const body = steps[cursor]?.body ?? ''
    const writing = Math.max(500, Math.min(3200, body.length * 26)) / speed
    const timer = setTimeout(() => setCursor((c) => c + 1), writing + 420 / speed)
    return () => clearTimeout(timer)
  }, [playing, cursor, steps, speed])

  useEffect(() => {
    boardRef.current?.scrollTo({ top: boardRef.current.scrollHeight, behavior: 'smooth' })
  }, [cursor])

  const restart = useCallback(() => { setCursor(0); setPlaying(true) }, [])
  const nextProblem = useCallback(() => {
    setIndex((i) => (i + 1) % Math.max(TRACEABLE.length, 1))
    setCursor(0)
    setPlaying(true)
  }, [])
  const randomProblem = useCallback(() => {
    setIndex(Math.floor(Math.random() * Math.max(TRACEABLE.length, 1)))
    setCursor(0)
    setPlaying(true)
  }, [])

  if (!problem) {
    return (
      <main className="min-h-screen bg-[#1d2a24] p-10 text-[#f4f1e8]">
        導出の跡を持つ問題がまだありません。
      </main>
    )
  }

  const finished = cursor >= steps.length

  return (
    <main className="min-h-screen bg-[#12100e] px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h1 className="text-lg tracking-[0.3em] text-[#f4f1e8]">MathOS 板書</h1>
            <p className="mt-1 text-xs text-[#8b9a92]">
              構築から演繹閉包の1ノードを切り出すまでを、記録どおりに書き出しています
            </p>
          </div>
          <div className="text-xs text-[#8b9a92]">
            {index + 1} / {TRACEABLE.length}　·　{problem.domain}　·
            <span className="text-[#bfe3c6]">{problem.family_id}</span>
          </div>
        </header>

        {/* 黒板 */}
        <div
          ref={boardRef}
          className="relative overflow-y-auto rounded-sm p-6 sm:p-10"
          style={{
            height: '62vh',
            background:
              'radial-gradient(120% 90% at 30% 15%, #2c3f36 0%, #223028 55%, #1a241f 100%)',
            border: '10px solid #6b4a2c',
            boxShadow:
              'inset 0 0 90px rgba(0,0,0,.55), 0 18px 45px rgba(0,0,0,.45)',
            fontFamily:
              '"Yu Gothic", "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif',
            letterSpacing: '.04em',
          }}
        >
          {/* チョーク跡のざらつき */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.06]"
            style={{
              backgroundImage:
                'repeating-linear-gradient(115deg, #fff 0 1px, transparent 1px 5px)',
            }}
          />
          <div className="relative">
            {/* まだ書いていない行は描画しない。場所だけ取ると板が空白に見え、
                自動スクロールが下端へ飛んでしまう。 */}
            {steps.slice(0, cursor + 1).map((step, i) => (
              <ChalkLine
                key={`${index}-${i}`}
                step={step}
                active={i === cursor}
                done={i < cursor}
                speed={speed}
              />
            ))}
            {finished && (
              <div className="mt-6 text-[11px] tracking-[0.25em] text-[#7f9b8c]">
                — 1つの構築から，この閉包には他にもノードがあります —
              </div>
            )}
          </div>
        </div>

        {/* 操作 */}
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => setPlaying((p) => !p)}
            className="rounded border border-[#3c4f45] px-3 py-1.5 text-[#dfe8e2] hover:bg-[#22302a]"
          >
            {playing ? '一時停止' : '再生'}
          </button>
          <button
            onClick={restart}
            className="rounded border border-[#3c4f45] px-3 py-1.5 text-[#dfe8e2] hover:bg-[#22302a]"
          >
            最初から
          </button>
          <button
            onClick={() => setCursor(steps.length)}
            className="rounded border border-[#3c4f45] px-3 py-1.5 text-[#dfe8e2] hover:bg-[#22302a]"
          >
            全部表示
          </button>
          <button
            onClick={nextProblem}
            className="rounded border border-[#3c4f45] px-3 py-1.5 text-[#dfe8e2] hover:bg-[#22302a]"
          >
            次の問題
          </button>
          <button
            onClick={randomProblem}
            className="rounded border border-[#3c4f45] px-3 py-1.5 text-[#dfe8e2] hover:bg-[#22302a]"
          >
            ランダム
          </button>
          <span className="ml-2 text-[#7f9b8c]">速さ</span>
          {[0.5, 1, 2, 4].map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className="rounded border px-2 py-1"
              style={{
                borderColor: speed === s ? '#bfe3c6' : '#3c4f45',
                color: speed === s ? '#bfe3c6' : '#8b9a92',
              }}
            >
              ×{s}
            </button>
          ))}
        </div>
      </div>
    </main>
  )
}
