'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, LoaderCircle, Play, RotateCcw, Square } from 'lucide-react'
import { ProofGraphScene } from './ProofGraphScene'
import { ProblemArtifact, type ProblemArtifactCard } from './ProblemArtifact'
import type { ProblemDiagram } from '@/lib/mortra/problem-artifact'
import type { Lang } from '@/lib/mortra/i18n'
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
  discovered?: number
  requested?: number
  cards?: GeneratedCard[]
  errors?: string[]
  discoveryQueued?: boolean
  discoveryJobId?: string
  engine?: string
  trace?: string[]
  searchState?: {
    round?: number
    depth?: number
    terms_enumerated?: number
    executable_goals?: number
    states_explored?: number
    frontier?: Array<{ source?: string; target?: string; obligation?: string }>
    continuing?: boolean
    next_attempt_at?: string | null
  }
}

type JobTelemetry = {
  elapsed_seconds?: number | null
  runtime_phase?: string | null
  runtime_message?: string | null
  worker_active?: boolean
  waiting_for_next_round?: boolean
  seconds_until_next_round?: number
  round?: number
  depth?: number
  terms_enumerated?: number
  executable_goals?: number
  states_explored?: number
  frontier_count?: number
  induced_laws?: number
}

type JobStatus = {
  status?: string
  logs?: Array<{ message?: string; ts?: string } | string>
  result?: GenerationResult
  error?: string | null
  replacement_job_id?: string | null
  telemetry?: JobTelemetry
}

type TraceLine = {
  id: string
  at: number | null
  text: string
}

const JOB_KEY = 'mortra-public-active-job'
const SEARCH_BUDGET_SECONDS = 90

const CONSOLE_TEXT = {
  ja: {
    parentA: '方程式 $x^2-5x+6=0$ を解け。',
    parentB: '方程式 $y^2-y-1=0$ の根を考える。',
    fusionPhases: ['構造化', '候補生成', '融合検査', '厳密検証', '保存'],
    solvePhases: ['構造化', '制約化', '厳密計算', '検証', '解答'],
    labelA: '問題',
    labelB: '問題（任意）',
    placeholderA: '一つ目の問題をLaTeXまたは日本語で入力',
    placeholderB: '融合するときだけ、二つ目の問題を入力',
    solving: '解いています',
    generating: '生成しています',
    solveOne: '問題を解く',
    fuseTwo: '融合問題を生成',
    stopWatch: '画面上の監視を停止',
    resetInput: '入力を初期化',
    progressAria: '生成の進行状況',
    solveDone: '解答完了',
    generateDone: '生成完了',
    idle: '待機中',
    phaseStripAria: '実際の生成段階',
    telemetryAria: '自律探索の現在地',
    tState: '状態', tRound: 'ラウンド', tDepth: '探索深さ',
    tStates: '検査状態', tGoals: '実行候補', tFrontier: '未閉鎖義務',
    traceSummary: '処理記録',
    researchNotice: '公開版の2問融合は、次数2〜4の一変数モニック整数多項式に対応しています。Newton和と終結式が一致した問題だけを表示します。',
    searching: '探索中',
    nextRound: (s: number) => `次の探索まで ${s} 秒`,
    resuming: '再開準備中',
    locale: 'ja-JP',
    tr: {
      reconnected: (id: string) => `継続中の探索 ${id} に再接続しました。`,
      statusFetch: (code: number) => `状態取得 ${code}`,
      handedOver: (id: string) => `探索を次の実行系 ${id} へ引き継ぎました。`,
      received: '問題文、図、解答、検証証明書を受信しました。',
      savedResearch: '研究候補を保存しました。検証は継続中です。',
      noProvable: '証明可能な候補を返せませんでした。',
      refetch: (m: string) => `状態を再取得します: ${m}`,
      movedToLong: '長時間の探索へ移行しました。画面を閉じても処理は継続します。',
      needInput: 'AまたはBに問題を入力してください。',
      acceptedSolve: '入力問題を解答対象として受理しました。',
      acceptedFusion: '親問題AとBを、別々の証明入力として受理しました。',
      solveApi: (code: number) => `解答API ${code}`,
      generateApi: (code: number) => `生成API ${code}`,
      noStream: '進行ストリームを開始できません',
      watchStopped: '画面上の監視を停止しました。長時間探索へ移行済みなら処理は継続します。',
    },
  },
  en: {
    parentA: 'Solve the equation $x^2-5x+6=0$.',
    parentB: 'Consider the roots of $y^2-y-1=0$.',
    fusionPhases: ['Structure', 'Candidates', 'Fusion check', 'Exact verify', 'Save'],
    solvePhases: ['Structure', 'Constraints', 'Exact compute', 'Verify', 'Answer'],
    labelA: 'Problem',
    labelB: 'Problem (optional)',
    placeholderA: 'Enter the first problem, in LaTeX or plain language',
    placeholderB: 'Add a second problem only if you want the two fused',
    solving: 'Solving',
    generating: 'Generating',
    solveOne: 'Solve this problem',
    fuseTwo: 'Fuse into a new problem',
    stopWatch: 'Stop watching on screen',
    resetInput: 'Reset input',
    progressAria: 'Generation progress',
    solveDone: 'Solved',
    generateDone: 'Generated',
    idle: 'Idle',
    phaseStripAria: 'Actual generation stages',
    telemetryAria: 'Current state of the autonomous search',
    tState: 'State', tRound: 'Round', tDepth: 'Depth',
    tStates: 'States seen', tGoals: 'Executable goals', tFrontier: 'Open obligations',
    traceSummary: 'Execution log',
    researchNotice: 'Public two-parent fusion currently supports degree 2–4 monic univariate integer polynomials. A problem is shown only when Newton sums and an independent resultant agree.',
    searching: 'Searching',
    nextRound: (s: number) => `Next round in ${s}s`,
    resuming: 'Resuming',
    locale: 'en-US',
    tr: {
      reconnected: (id: string) => `Reconnected to the running search ${id}.`,
      statusFetch: (code: number) => `Status fetch ${code}`,
      handedOver: (id: string) => `Search handed over to runner ${id}.`,
      received: 'Received the statement, figure, solution and verification certificate.',
      savedResearch: 'Research candidate saved. Verification continues.',
      noProvable: 'No provable candidate was returned.',
      refetch: (m: string) => `Refetching state: ${m}`,
      movedToLong: 'Moved to long-running search. Processing continues even if you close this page.',
      needInput: 'Enter a problem in A or B.',
      acceptedSolve: 'Accepted the input problem as the target to solve.',
      acceptedFusion: 'Accepted parents A and B as separate proof inputs.',
      solveApi: (code: number) => `Solve API ${code}`,
      generateApi: (code: number) => `Generate API ${code}`,
      noStream: 'Could not open the progress stream',
      watchStopped: 'Stopped watching on screen. If the long-running search already started, it continues.',
    },
  },
} as const

function parentId(text: string, index: number) {
  let hash = 2166136261
  for (let offset = 0; offset < text.length; offset += 1) {
    hash ^= text.charCodeAt(offset)
    hash = Math.imul(hash, 16777619)
  }
  return `public-parent-${index}-${(hash >>> 0).toString(36)}`
}

function stageForPhase(phase: string) {
  if (['complete', 'completed', 'done', 'saving'].includes(phase)) return 4
  if (phase === 'verifying') return 3
  if (phase === 'novelty') return 2
  if (['searching', 'structuring', 'executing_round', 'researching', 'waiting_next_round', 'stalled_waiting'].includes(phase)) return 1
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

export function MortraTryConsole({ lang = 'en' }: { lang?: Lang }) {
  const c = CONSOLE_TEXT[lang]
  const tr = c.tr
  const FUSION_PHASES = c.fusionPhases.map((label, i) => ({ key: `fusion-${i}`, label }))
  const SOLVE_PHASES = c.solvePhases.map((label, i) => ({ key: `solve-${i}`, label }))
  const [parentA, setParentA] = useState<string>(c.parentA)
  const [parentB, setParentB] = useState<string>(c.parentB)
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState('idle')
  const [stage, setStage] = useState(-1)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [draft, setDraft] = useState('')
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [telemetry, setTelemetry] = useState<JobTelemetry | null>(null)
  const [trace, setTrace] = useState<TraceLine[]>([])
  const [taskMode, setTaskMode] = useState<'solve' | 'fusion'>('fusion')
  const abortRef = useRef<AbortController | null>(null)
  const traceSequenceRef = useRef(0)
  const seenRemoteLogsRef = useRef(new Set<string>())

  const addTrace = useCallback((text: string, at = Date.now()) => {
    if (!text.trim()) return
    setTrace(lines => {
      if (lines.at(-1)?.text === text) return lines
      const id = `${at}-${traceSequenceRef.current++}`
      return [...lines.slice(-79), { id, at, text }]
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
    addTrace(tr.reconnected(stored.slice(0, 8)))
  }, [addTrace])

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer = 0

    const poll = async () => {
      try {
        const response = await fetch(`/api/job-status?job_id=${encodeURIComponent(jobId)}`, { cache: 'no-store' })
        if (!response.ok) throw new Error(tr.statusFetch(response.status))
        const data = await response.json() as JobStatus
        if (cancelled) return
        if (data.replacement_job_id && data.replacement_job_id !== jobId) {
          window.localStorage.setItem(JOB_KEY, data.replacement_job_id)
          setJobId(data.replacement_job_id)
          addTrace(tr.handedOver(data.replacement_job_id.slice(0, 8)))
          return
        }
        setTelemetry(data.telemetry ?? null)
        if (typeof data.telemetry?.elapsed_seconds === 'number') setElapsed(data.telemetry.elapsed_seconds)
        if (data.telemetry?.runtime_phase) {
          setPhase(data.telemetry.runtime_phase)
          setStage(stageForPhase(data.telemetry.runtime_phase))
        }
        if (data.telemetry?.runtime_message) addTrace(data.telemetry.runtime_message)
        for (const [index, entry] of (data.logs ?? []).entries()) {
          const text = typeof entry === 'string' ? entry : entry.message ?? ''
          const at = typeof entry === 'string' ? Date.now() : Date.parse(entry.ts ?? '') || Date.now()
          const remoteKey = typeof entry === 'string'
            ? `string:${index}:${text}`
            : `object:${entry.ts ?? index}:${text}`
          if (seenRemoteLogsRef.current.has(remoteKey)) continue
          seenRemoteLogsRef.current.add(remoteKey)
          addTrace(text, at)
        }
        const jobResult = data.result ?? null
        const completedCard = cardFromResult(jobResult)
        const generated = jobResult?.cards?.length ?? jobResult?.generated ?? 0
        if (jobResult) {
          setResult(jobResult)
          if (completedCard?.statement_tex) setDraft(completedCard.statement_tex)
        }
        if (data.status === 'done' || (generated > 0 && isResolvedCard(completedCard))) {
          const resolved = isResolvedCard(completedCard)
          setPhase(resolved ? 'complete' : 'researching')
          setStage(resolved ? 4 : 1)
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace(resolved
            ? tr.received
            : tr.savedResearch)
          return
        }
        if (data.status === 'failed') {
          setResult(jobResult)
          setPhase('error')
          setRunning(false)
          setJobId(null)
          window.localStorage.removeItem(JOB_KEY)
          addTrace(data.error || tr.noProvable)
          return
        }
      } catch (error) {
        if (!cancelled) addTrace(tr.refetch(error instanceof Error ? error.message : String(error)))
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
    for (const error of event.result.errors ?? []) addTrace(error)
    const first = cardFromResult(event.result)
    if (first?.statement_tex) setDraft(first.statement_tex)
    if (event.result.discoveryQueued && event.result.discoveryJobId) {
      setJobId(event.result.discoveryJobId)
      window.localStorage.setItem(JOB_KEY, event.result.discoveryJobId)
      setPhase('searching')
      setStage(1)
      addTrace(tr.movedToLong)
      return
    }

    const resolved = isResolvedCard(first)
    setRunning(false)
    setPhase(resolved ? 'complete' : (event.result.generated ?? 0) > 0 ? 'researching' : 'error')
  }, [addTrace])

  const run = async () => {
    const a = parentA.trim()
    const b = parentB.trim()
    const inputs = [a, b].filter(Boolean)
    if (inputs.length === 0) {
      addTrace(tr.needInput)
      setPhase('error')
      return
    }
    const nextMode = inputs.length === 1 ? 'solve' : 'fusion'
    setTaskMode(nextMode)

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true)
    setPhase('start')
    setStage(0)
    setStartedAt(Date.now())
    setElapsed(0)
    setTelemetry(null)
    setResult(null)
    setDraft('')
    setTrace([])
    addTrace(nextMode === 'solve'
      ? tr.acceptedSolve
      : tr.acceptedFusion)

    try {
      if (nextMode === 'solve') {
        setPhase('structuring')
        setStage(0)
        const response = await fetch('/api/solve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({ problem: inputs[0] }),
        })
        const raw = await response.text()
        let solved: GenerationResult & { error?: string }
        try {
          solved = JSON.parse(raw) as GenerationResult & { error?: string }
        } catch {
          throw new Error(tr.solveApi(response.status))
        }
        for (const line of solved.trace ?? []) addTrace(line)
        if (!response.ok) throw new Error(solved.error || tr.solveApi(response.status))
        setStage(4)
        setPhase('complete')
        setResult(solved)
        const solvedCard = cardFromResult(solved)
        setDraft(solvedCard?.statement_tex ?? inputs[0])
        setRunning(false)
        return
      }

      const response = await fetch('/api/mathos-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          count: 1,
          stream: true,
          mode: 'fusion',
          surface: 'public_try',
          searchDepth: 'deep',
          searchBudgetSeconds: SEARCH_BUDGET_SECONDS,
          parents: inputs.map((statement, index) => ({ id: parentId(statement, index + 1), statement })),
        }),
      })
      if (!response.ok) {
        const detail = await response.text()
        throw new Error(detail || tr.generateApi(response.status))
      }
      if (!response.body) throw new Error(tr.noStream)

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
        addTrace(tr.watchStopped)
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
    setParentA(c.parentA)
    setParentB(c.parentB)
    setResult(null)
    setDraft('')
    setTrace([])
    setPhase('idle')
    setStage(-1)
    setElapsed(0)
    setTelemetry(null)
    setStartedAt(null)
    setTaskMode('fusion')
    traceSequenceRef.current = 0
    seenRemoteLogsRef.current.clear()
  }

  const card = cardFromResult(result)
  const currentInputCount = parentA.trim() && parentB.trim() ? 2 : 1
  const visibleMode = running || card ? taskMode : currentInputCount === 1 ? 'solve' : 'fusion'
  const phases = visibleMode === 'solve' ? SOLVE_PHASES : FUSION_PHASES
  const progress = phase === 'complete' ? 1 : Math.max(0.08, Math.min(0.92, (stage + 0.7) / phases.length))
  const currentMessage = trace.at(-1)?.text ?? ''
  const showExecution = running || trace.length > 0 || Boolean(draft) || Boolean(card)
  const researchCandidate = card && !isResolvedCard(card)
  const workerState = telemetry?.worker_active
    ? c.searching
    : telemetry?.waiting_for_next_round
      ? c.nextRound(telemetry.seconds_until_next_round ?? 0)
      : running
        ? c.resuming
        : null

  return (
    <>
      <div className={styles.console}>
        <div className={styles.parentGrid}>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-a"><span>A</span><span>{c.labelA}</span></label>
            <textarea
              id="mortra-parent-a"
              value={parentA}
              onChange={event => setParentA(event.target.value)}
              placeholder={c.placeholderA}
            />
          </div>
          <div className={styles.parentField}>
            <label htmlFor="mortra-parent-b"><span>B</span><span>{c.labelB}</span></label>
            <textarea
              id="mortra-parent-b"
              value={parentB}
              onChange={event => setParentB(event.target.value)}
              placeholder={c.placeholderB}
            />
          </div>
        </div>

        <div className={styles.mergeRail} aria-hidden="true"><span /></div>

        <div className={styles.inputActions}>
          <button className={styles.runButton} type="button" onClick={() => void run()} disabled={running}>
            {running ? <LoaderCircle className={styles.spin} size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {running ? (visibleMode === 'solve' ? c.solving : c.generating) : currentInputCount === 1 ? c.solveOne : c.fuseTwo}
          </button>
          {running ? (
            <button className={styles.iconButton} type="button" onClick={stop} title={c.stopWatch} aria-label={c.stopWatch}>
              <Square size={15} aria-hidden="true" />
            </button>
          ) : null}
          <button className={styles.iconButton} type="button" onClick={reset} title={c.resetInput} aria-label={c.resetInput}>
            <RotateCcw size={15} aria-hidden="true" />
          </button>
        </div>

        {showExecution ? (
          <section className={styles.execution} aria-label={c.progressAria}>
            <div className={styles.executionVisual}>
              <ProofGraphScene className={styles.consoleScene} phase={phase} progress={progress} running={running} inputCount={visibleMode === 'solve' ? 1 : 2} />
              <div className={styles.executionStatus} aria-live="polite">
                <span className={styles.executionPhase}>
                  {phase === 'complete' ? <Check size={14} aria-hidden="true" /> : running ? <LoaderCircle className={styles.spin} size={14} aria-hidden="true" /> : null}
                  {phase === 'complete' ? (visibleMode === 'solve' ? c.solveDone : c.generateDone) : phases[Math.max(0, stage)]?.label ?? c.idle}
                </span>
                {running ? <time>{formatClock(elapsed)}</time> : null}
              </div>
            </div>

            <ol className={styles.phaseStrip} aria-label={c.phaseStripAria}>
              {phases.map((item, index) => {
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

            {jobId && telemetry ? (
              <div className={styles.searchTelemetry} aria-label={c.telemetryAria}>
                <div><span>{c.tState}</span><strong>{workerState}</strong></div>
                <div><span>{c.tRound}</span><strong>{telemetry.round ?? 0}</strong></div>
                <div><span>{c.tDepth}</span><strong>{telemetry.depth ?? 0}</strong></div>
                <div><span>{c.tStates}</span><strong>{(telemetry.states_explored ?? 0).toLocaleString(c.locale)}</strong></div>
                <div><span>{c.tGoals}</span><strong>{telemetry.executable_goals ?? 0}</strong></div>
                <div><span>{c.tFrontier}</span><strong>{telemetry.frontier_count ?? 0}</strong></div>
              </div>
            ) : null}

            {currentMessage ? <p className={`${styles.currentMessage} ${phase === 'error' ? styles.errorMessage : ''}`}>{currentMessage}</p> : null}
            {trace.length > 1 ? (
              <details className={styles.traceDisclosure}>
                <summary>{c.traceSummary}</summary>
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

      {card ? (
        <div className={styles.generatedArtifact}>
          <ProblemArtifact card={card} lang={lang} />
          {researchCandidate && running ? (
            <p className={styles.researchNotice}>
              {c.researchNotice}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  )
}
