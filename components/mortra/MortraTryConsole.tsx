'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Play, RotateCcw, Square, TimerReset } from 'lucide-react'
import { ProofGraphScene } from './ProofGraphScene'
import styles from '@/app/mortra/mortra.module.css'

type ProgressMessage = {
  phase?: string
  message?: string
  current?: number
  total?: number
  draft?: string
  familyId?: string
  morphisms?: string[]
  result?: GenerationResult
}

type GeneratedCard = {
  statement_tex?: string
  answer_tex?: string
  solution_tex?: string
  family_id?: string
  morphism_chain?: string[]
  verification?: { method?: string }
}

type GenerationResult = {
  generated?: number
  requested?: number
  cards?: GeneratedCard[]
  errors?: string[]
  discoveryQueued?: boolean
  discoveryJobId?: string
  engine?: string
  generalization?: {
    target_sort?: string
    common_invariants?: string[]
  }
}

type JobStatus = {
  id?: string
  status?: string
  logs?: Array<{ message?: string; ts?: string } | string>
  result?: GenerationResult & {
    searchState?: Record<string, unknown>
  }
  error?: string | null
  replacement_job_id?: string | null
  telemetry?: {
    elapsed_seconds?: number | null
    seconds_since_update?: number | null
    worker_active?: boolean
    waiting_for_next_round?: boolean
    runtime_phase?: string | null
    runtime_message?: string | null
    round?: number
    depth?: number
    terms_enumerated?: number
    executable_goals?: number
    states_explored?: number
    frontier_count?: number
  }
}

type TraceLine = {
  id: string
  at: number | null
  text: string
}

const DEFAULT_PARENT_A = String.raw`\text{放物線 }C:y=x^2\text{ と直線 }\ell:y=mx+1\text{ の交点を }P,Q\text{ とする。}`
const DEFAULT_PARENT_B = String.raw`\text{三角形 }ABC\text{ の重心 }G\text{ が動くとき、その軌跡と面積を求めよ。}`
const JOB_KEY = 'mortra-public-active-job'

const PHASES = [
  { key: 'semantic', label: '意味解析' },
  { key: 'typing', label: '型形成' },
  { key: 'search', label: '射探索' },
  { key: 'proof', label: '証明' },
  { key: 'verify', label: '検証' },
]

function parentId(text: string, index: number) {
  let hash = 2166136261
  for (let offset = 0; offset < text.length; offset += 1) {
    hash ^= text.charCodeAt(offset)
    hash = Math.imul(hash, 16777619)
  }
  return `public-parent-${index}-${(hash >>> 0).toString(36)}`
}

function stageForPhase(phase: string) {
  if (['complete', 'done', 'saving'].includes(phase)) return 4
  if (['verifying', 'novelty'].includes(phase)) return 3
  if (['searching', 'inducing', 'structuring'].includes(phase)) return 2
  if (['registering'].includes(phase)) return 1
  return 0
}

function formatClock(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function cardFromResult(result: GenerationResult | null) {
  return result?.cards?.[0] ?? null
}

export function MortraTryConsole() {
  const [parentA, setParentA] = useState(DEFAULT_PARENT_A)
  const [parentB, setParentB] = useState(DEFAULT_PARENT_B)
  const [budget, setBudget] = useState(90)
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState('idle')
  const [stage, setStage] = useState(0)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [draft, setDraft] = useState('')
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [telemetry, setTelemetry] = useState<JobStatus['telemetry'] | null>(null)
  const [trace, setTrace] = useState<TraceLine[]>([
    { id: 'ready', at: null, text: '親問題を2つ固定すると、型付き構造の共通部分から探索を開始します。' },
  ])
  const abortRef = useRef<AbortController | null>(null)

  const addTrace = useCallback((text: string, at = Date.now()) => {
    if (!text.trim()) return
    setTrace(lines => {
      if (lines.at(-1)?.text === text) return lines
      return [...lines.slice(-79), { id: `${at}-${lines.length}`, at, text }]
    })
  }, [])

  useEffect(() => {
    if (!running || startedAt === null) return
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [running, startedAt])

  useEffect(() => {
    const stored = window.localStorage.getItem(JOB_KEY)
    if (!stored) return
    setJobId(stored)
    setRunning(true)
    setPhase('searching')
    setStartedAt(Date.now())
    addTrace(`継続中の探索 ${stored.slice(0, 8)} を再接続しました。`)
  }, [addTrace])

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer = 0

    const poll = async () => {
      try {
        const response = await fetch(`/api/job-status?job_id=${encodeURIComponent(jobId)}`, { cache: 'no-store' })
        if (!response.ok) throw new Error(`状態取得 ${response.status}`)
        const data = await response.json() as JobStatus
        if (cancelled) return
        if (data.replacement_job_id && data.replacement_job_id !== jobId) {
          window.localStorage.setItem(JOB_KEY, data.replacement_job_id)
          setJobId(data.replacement_job_id)
          addTrace(`探索を次のworker ${data.replacement_job_id.slice(0, 8)} へ引き継ぎました。`)
          return
        }
        setTelemetry(data.telemetry)
        if (typeof data.telemetry?.elapsed_seconds === 'number') setElapsed(data.telemetry.elapsed_seconds)
        if (data.telemetry?.runtime_phase) {
          setPhase(data.telemetry.runtime_phase)
          setStage(stageForPhase(data.telemetry.runtime_phase))
        }
        if (data.telemetry?.runtime_message) addTrace(data.telemetry.runtime_message)
        for (const entry of data.logs ?? []) {
          const text = typeof entry === 'string' ? entry : entry.message ?? ''
          const at = typeof entry === 'string' ? Date.now() : Date.parse(entry.ts ?? '') || Date.now()
          addTrace(text, at)
        }
        const jobResult = data.result ?? null
        const generated = jobResult?.cards?.length ?? jobResult?.generated ?? 0
        if (data.status === 'done' || generated > 0) {
          setResult(jobResult)
          setDraft(cardFromResult(jobResult)?.statement_tex ?? '')
          setPhase('complete')
          setStage(4)
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace('検証済み問題を受信しました。')
          return
        }
        if (data.status === 'failed') {
          setResult(jobResult)
          setPhase('error')
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace(data.error || '探索は証明可能な候補を返せませんでした。')
          return
        }
      } catch (error) {
        if (!cancelled) addTrace(`状態を再取得します: ${error instanceof Error ? error.message : String(error)}`)
      }
      if (!cancelled) timer = window.setTimeout(poll, 4000)
    }

    void poll()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [addTrace, jobId])

  const handleProgress = useCallback((event: ProgressMessage) => {
    const nextPhase = event.phase ?? 'searching'
    if (nextPhase !== 'done') {
      setPhase(nextPhase)
      setStage(stageForPhase(nextPhase))
    }
    if (event.message) addTrace(event.message)
    if (event.draft) setDraft(event.draft)
    if (event.result) {
      setResult(event.result)
      const first = cardFromResult(event.result)
      if (first?.statement_tex) setDraft(first.statement_tex)
      if (event.result.discoveryQueued && event.result.discoveryJobId) {
        setJobId(event.result.discoveryJobId)
        window.localStorage.setItem(JOB_KEY, event.result.discoveryJobId)
        setPhase('searching')
        setStage(2)
        addTrace(`長時間worker ${event.result.discoveryJobId.slice(0, 8)} へ探索を移しました。`)
      } else {
        setRunning(false)
        setPhase((event.result.generated ?? 0) > 0 ? 'complete' : 'error')
      }
    }
  }, [addTrace])

  const run = async () => {
    const a = parentA.trim()
    const b = parentB.trim()
    if (!a || !b) {
      addTrace('親問題を2つ入力してください。')
      setPhase('error')
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true)
    setPhase('start')
    setStage(0)
    setStartedAt(Date.now())
    setElapsed(0)
    setResult(null)
    setDraft('')
    setTelemetry(null)
    setTrace([])
    addTrace('2つの親問題を固定端点として受理しました。')

    try {
      const response = await fetch('/api/mathos-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          count: 1,
          stream: true,
          mode: 'fusion',
          searchDepth: 'deep',
          searchBudgetSeconds: budget,
          parents: [
            { id: parentId(a, 1), statement: a },
            { id: parentId(b, 2), statement: b },
          ],
        }),
      })
      if (!response.ok) {
        const detail = await response.text()
        throw new Error(detail || `生成API ${response.status}`)
      }
      if (!response.body) throw new Error('進行ストリームを開始できません')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const packets = buffer.split('\n\n')
        buffer = packets.pop() ?? ''
        for (const packet of packets) {
          const payload = packet.split('\n').find(line => line.startsWith('data: '))?.slice(6)
          if (!payload) continue
          handleProgress(JSON.parse(payload) as ProgressMessage)
        }
      }
    } catch (error) {
      if (controller.signal.aborted) {
        addTrace('画面上の監視を停止しました。長時間workerへ移行済みなら探索自体は継続します。')
      } else {
        addTrace(error instanceof Error ? error.message : String(error))
        setPhase('error')
        setRunning(false)
      }
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    setRunning(false)
  }

  const reset = () => {
    abortRef.current?.abort()
    setParentA(DEFAULT_PARENT_A)
    setParentB(DEFAULT_PARENT_B)
    setResult(null)
    setDraft('')
    setTelemetry(null)
    setTrace([{ id: 'ready', at: Date.now(), text: '入力を初期化しました。' }])
    setPhase('idle')
    setStage(0)
    setElapsed(0)
    setStartedAt(null)
  }

  const card = cardFromResult(result)
  const progress = phase === 'complete' ? 1 : Math.min(0.92, (stage + 0.55) / PHASES.length)
  const eta = running && !jobId ? Math.max(0, budget - elapsed) : null
  const statusText = running
    ? jobId ? 'background worker' : 'live synthesis'
    : phase === 'complete' ? 'verified' : phase === 'error' ? 'needs review' : 'ready'

  const metricValues = useMemo(() => [
    ['経過', formatClock(elapsed)],
    ['予想残り', eta === null ? (jobId ? '探索継続中' : '—') : formatClock(eta)],
    ['深さ', String(telemetry?.depth ?? stage)],
    ['探索状態', String(telemetry?.states_explored ?? telemetry?.terms_enumerated ?? trace.length)],
  ], [elapsed, eta, jobId, stage, telemetry, trace.length])

  return (
    <div className={styles.console}>
      <section className={styles.inputPanel} aria-label="MORTRA入力">
        <div className={styles.panelHead}>
          <span className={styles.panelLabel}>Parent problems</span>
          <span className={styles.panelState}>2 endpoints required</span>
        </div>
        <div className={styles.inputBody}>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-a"><span>P1</span><span>始点</span></label>
            <textarea id="mortra-parent-a" value={parentA} onChange={event => setParentA(event.target.value)} />
          </div>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-b"><span>P2</span><span>終点</span></label>
            <textarea id="mortra-parent-b" value={parentB} onChange={event => setParentB(event.target.value)} />
          </div>
          <div className={styles.budgetRow}>
            <label htmlFor="mortra-budget"><span>探索時間</span><span>{budget}秒</span></label>
            <input
              id="mortra-budget"
              type="range"
              min={30}
              max={180}
              step={15}
              value={budget}
              onChange={event => setBudget(Number(event.target.value))}
            />
          </div>
          <div className={styles.inputActions}>
            <button className={styles.runButton} type="button" onClick={() => void run()} disabled={running}>
              <Play size={15} aria-hidden="true" />
              構造を探索する
            </button>
            <button className={styles.iconButton} type="button" onClick={stop} disabled={!running} title="監視を停止">
              <Square size={15} aria-hidden="true" />
            </button>
            <button className={styles.iconButton} type="button" onClick={reset} title="入力を初期化">
              <RotateCcw size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      <section className={styles.tracePanel} aria-label="MORTRA探索過程">
        <div className={styles.panelHead}>
          <span className={styles.panelLabel}>Executable proof graph</span>
          <span className={styles.panelState}>{statusText}</span>
        </div>
        <ProofGraphScene className={styles.consoleScene} phase={phase} progress={progress} running={running} />
        <div className={styles.phaseStrip} aria-label="生成段階">
          {PHASES.map((item, index) => (
            <div
              key={item.key}
              className={`${styles.phaseItem} ${index < stage ? styles.phaseDone : index === stage ? styles.phaseActive : ''}`}
            >
              {item.label}
            </div>
          ))}
        </div>
        <div className={styles.traceBody}>
          <div className={styles.liveLog} aria-live="polite">
            {trace.map((line, index) => (
              <div key={line.id} className={`${styles.logLine} ${index === trace.length - 1 ? styles.logCurrent : ''}`}>
                <span className={styles.logTime}>{line.at === null ? '--:--:--' : new Date(line.at).toLocaleTimeString('ja-JP', { hour12: false }).slice(0, 8)}</span>
                <span className={styles.logText}>{line.text}</span>
              </div>
            ))}
          </div>
          <div className={styles.resultPane}>
            <div className={styles.metricGrid}>
              {metricValues.map(([label, value]) => (
                <div className={styles.metric} key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20 }}>
              {card || draft ? (
                <>
                  <p className={styles.resultTitle}>Problem draft</p>
                  <p className={styles.resultStatement}>{card?.statement_tex ?? draft}</p>
                  {card?.answer_tex ? <div className={styles.resultAnswer}>answer: {card.answer_tex}</div> : null}
                </>
              ) : (
                <p className={styles.emptyResult}>
                  <TimerReset size={14} aria-hidden="true" style={{ marginRight: 8, verticalAlign: -2 }} />
                  型検査を通った中間構造と検証済み問題だけをここに表示します。
                </p>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
