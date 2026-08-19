'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, LoaderCircle, Play, RotateCcw, Square } from 'lucide-react'
import { ProofGraphScene } from './ProofGraphScene'
import { ProblemArtifact, type ProblemArtifactCard } from './ProblemArtifact'
import type { ProblemDiagram } from '@/lib/mortra/problem-artifact'
import styles from '@/app/mortra/mortra.module.css'

type ProgressMessage = {
  phase?: string
  message?: string
  draft?: string
  result?: GenerationResult
}

type GeneratedCard = ProblemArtifactCard & {
  statement_tex?: string
  answer_tex?: string
  solution_tex?: string
  parameters?: Record<string, number>
  diagram?: ProblemDiagram
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
}

type JobStatus = {
  status?: string
  logs?: Array<{ message?: string; ts?: string } | string>
  result?: GenerationResult
  error?: string | null
  replacement_job_id?: string | null
  telemetry?: {
    elapsed_seconds?: number | null
    runtime_phase?: string | null
    runtime_message?: string | null
  }
}

type TraceLine = {
  id: string
  at: number | null
  text: string
}

const DEFAULT_PARENT_A = String.raw`\text{三次方程式 }x^3-6x^2+11x-6=0\text{ の3実根の対称式を求めよ。}`
const DEFAULT_PARENT_B = String.raw`\text{三角形の3辺から、面積と内接円・外接円の半径の関係を調べよ。}`
const JOB_KEY = 'mortra-public-active-job'
const SEARCH_BUDGET_SECONDS = 90

const PHASES = [
  { key: 'structure', label: '構造化' },
  { key: 'candidate', label: '候補生成' },
  { key: 'fusion', label: '融合検査' },
  { key: 'verify', label: '厳密検証' },
  { key: 'save', label: '保存' },
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
  if (phase === 'verifying') return 3
  if (phase === 'novelty') return 2
  if (['searching', 'structuring'].includes(phase)) return 1
  if (['start', 'inducing', 'registering'].includes(phase)) return 0
  return -1
}

function formatClock(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function cardFromResult(result: GenerationResult | null) {
  return result?.cards?.[0] ?? null
}

function isResolvedCard(card: GeneratedCard | null | undefined) {
  return Boolean(card?.answer_tex?.trim() && card?.solution_tex?.trim())
}

export function MortraTryConsole() {
  const [parentA, setParentA] = useState(DEFAULT_PARENT_A)
  const [parentB, setParentB] = useState(DEFAULT_PARENT_B)
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState('idle')
  const [stage, setStage] = useState(-1)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [draft, setDraft] = useState('')
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [trace, setTrace] = useState<TraceLine[]>([])
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
    const sharedJob = new URL(window.location.href).searchParams.get('job')
    const stored = sharedJob || window.localStorage.getItem(JOB_KEY)
    if (!stored) return
    setJobId(stored)
    setRunning(true)
    setPhase('searching')
    setStage(1)
    setStartedAt(Date.now())
    addTrace(`継続中の探索 ${stored.slice(0, 8)} に再接続しました。`)
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
          addTrace(`探索を次の実行系 ${data.replacement_job_id.slice(0, 8)} へ引き継ぎました。`)
          return
        }
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
        const completedCard = cardFromResult(jobResult)
        const generated = jobResult?.cards?.length ?? jobResult?.generated ?? 0
        if (data.status === 'done' || (generated > 0 && isResolvedCard(completedCard))) {
          setResult(jobResult)
          setDraft(completedCard?.statement_tex ?? '')
          const resolved = isResolvedCard(completedCard)
          setPhase(resolved ? 'complete' : 'researching')
          setStage(resolved ? 4 : 1)
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace(resolved
            ? '問題文、図、解答、検証証明書を受信しました。'
            : '研究候補を保存しました。検証は継続中です。')
          return
        }
        if (data.status === 'failed') {
          setResult(jobResult)
          setPhase('error')
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace(data.error || '証明可能な候補を返せませんでした。')
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
    if (!event.result) return

    setResult(event.result)
    const first = cardFromResult(event.result)
    if (first?.statement_tex) setDraft(first.statement_tex)
    if (event.result.discoveryQueued && event.result.discoveryJobId) {
      setJobId(event.result.discoveryJobId)
      window.localStorage.setItem(JOB_KEY, event.result.discoveryJobId)
      setPhase('searching')
      setStage(1)
      addTrace('長時間の探索へ移行しました。画面を閉じても処理は継続します。')
      return
    }

    const resolved = isResolvedCard(first)
    setRunning(false)
    setPhase(resolved ? 'complete' : (event.result.generated ?? 0) > 0 ? 'researching' : 'error')
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
    setTrace([])
    addTrace('親問題AとBを、別々の証明入力として受理しました。')

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
          searchBudgetSeconds: SEARCH_BUDGET_SECONDS,
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
        addTrace('画面上の監視を停止しました。長時間探索へ移行済みなら処理は継続します。')
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
    setTrace([])
    setPhase('idle')
    setStage(-1)
    setElapsed(0)
    setStartedAt(null)
  }

  const card = cardFromResult(result)
  const progress = phase === 'complete' ? 1 : Math.max(0.08, Math.min(0.92, (stage + 0.7) / PHASES.length))
  const currentMessage = trace.at(-1)?.text ?? ''
  const showExecution = running || trace.length > 0 || Boolean(draft) || Boolean(card)

  return (
    <>
      <div className={styles.console}>
        <div className={styles.parentGrid}>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-a"><span>A</span><span>親問題</span></label>
            <textarea
              id="mortra-parent-a"
              value={parentA}
              onChange={event => setParentA(event.target.value)}
              placeholder="一つ目の問題をLaTeXまたは日本語で入力"
            />
          </div>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-b"><span>B</span><span>親問題</span></label>
            <textarea
              id="mortra-parent-b"
              value={parentB}
              onChange={event => setParentB(event.target.value)}
              placeholder="二つ目の問題をLaTeXまたは日本語で入力"
            />
          </div>
        </div>

        <div className={styles.mergeRail} aria-hidden="true"><span /></div>

        <div className={styles.inputActions}>
          <button className={styles.runButton} type="button" onClick={() => void run()} disabled={running}>
            {running ? <LoaderCircle className={styles.spin} size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {running ? '生成しています' : '融合問題を生成'}
          </button>
          {running ? (
            <button className={styles.iconButton} type="button" onClick={stop} title="画面上の監視を停止" aria-label="画面上の監視を停止">
              <Square size={15} aria-hidden="true" />
            </button>
          ) : null}
          <button className={styles.iconButton} type="button" onClick={reset} title="入力を初期化" aria-label="入力を初期化">
            <RotateCcw size={15} aria-hidden="true" />
          </button>
        </div>

        {showExecution ? (
          <section className={styles.execution} aria-label="生成の進行状況">
            <div className={styles.executionVisual}>
              <ProofGraphScene className={styles.consoleScene} phase={phase} progress={progress} running={running} />
              <div className={styles.executionStatus} aria-live="polite">
                <span className={styles.executionPhase}>
                  {phase === 'complete' ? <Check size={14} aria-hidden="true" /> : running ? <LoaderCircle className={styles.spin} size={14} aria-hidden="true" /> : null}
                  {phase === 'complete' ? '生成完了' : PHASES[Math.max(0, stage)]?.label ?? '待機中'}
                </span>
                {running ? <time>{formatClock(elapsed)}</time> : null}
              </div>
            </div>

            <ol className={styles.phaseStrip} aria-label="実際の生成段階">
              {PHASES.map((item, index) => {
                const complete = phase === 'complete' || index < stage
                const active = running && index === stage
                return (
                  <li
                    key={item.key}
                    className={`${styles.phaseItem} ${complete ? styles.phaseDone : ''} ${active ? styles.phaseActive : ''}`}
                    aria-current={active ? 'step' : undefined}
                  >
                    <span>{complete ? <Check size={12} aria-hidden="true" /> : null}</span>
                    {item.label}
                  </li>
                )
              })}
            </ol>

            {currentMessage ? <p className={`${styles.currentMessage} ${phase === 'error' ? styles.errorMessage : ''}`}>{currentMessage}</p> : null}
            {trace.length > 1 ? (
              <details className={styles.traceDisclosure}>
                <summary>処理記録</summary>
                <div className={styles.liveLog}>
                  {trace.map(line => (
                    <div key={line.id} className={styles.logLine}>
                      <span className={styles.logTime}>{line.at === null ? '--:--:--' : new Date(line.at).toLocaleTimeString('ja-JP', { hour12: false }).slice(0, 8)}</span>
                      <span className={styles.logText}>{line.text}</span>
                    </div>
                  ))}
                </div>
              </details>
            ) : null}
          </section>
        ) : null}
      </div>

      {card && isResolvedCard(card) ? (
        <div className={styles.generatedArtifact}>
          <ProblemArtifact card={card} />
        </div>
      ) : null}
    </>
  )
}
