'use client'

import { useEffect, useRef, useState } from 'react'
import type { ProblemWithRating } from '@/lib/types'
import { MathText } from './MathText'
import { UpgradeModal } from './UpgradeModal'

const TOPIC_JP: Record<string, string> = {
  analysis: '実解析', algebra: '代数', geometry: '幾何', number_theory: '整数論',
  complex: '複素数', recurrence: '漸化式', polynomial: '多項式',
  trigonometry: '三角関数', combinatorics: '組合せ', inequality: '不等式',
  probability: '確率', functional_eq: '関数方程式', modular: '合同算術', matrix: '行列',
}

interface Props {
  selectedProblems: ProblemWithRating[]
  accessToken: string | null
  isAdmin: boolean
  userId: string | null
  onStatusChange: (id: string, status: string) => void
  onPostClick: (p: ProblemWithRating) => void
  onGenerated?: () => void | Promise<void>
}

type GenerationCard = {
  family_id?: string
  answer_tex?: string
  statement_tex?: string
  solution_tex?: string
  domain?: string
  morphism_chain?: string[]
  similarity?: { score?: number; max?: number }
  inherited_tags?: string[]
  bridged_tags?: string[]
  unmapped_tags?: string[]
  atlas_expansion?: boolean
  parent_ids?: string[]
  unresolved?: boolean
  discovery_status?: 'research_pending' | 'backend_candidate' | 'verified'
  verification?: {
    method?: string
    exact_backend?: boolean
    independent_check?: boolean
    confidence?: number
  }
  parent_coverage?: Array<{
    parentId: string
    anchors: string[]
    exact: string[]
    bridged: string[]
    passed: boolean
  }>
  fusion_derivation?: {
    passed: boolean
    reason: string
    ablationPassed: boolean
    assignments: Array<{
      parentId: string
      portId: string
      role: string
      matchedAnchors: string[]
      witnessSteps: string[]
    }>
    bridges: Array<{ id: string; witnessStep: string; consumes: string[]; produces: string }>
    intermediatePropositions?: Array<{
      parentId: string
      morphism: string
      source: string
      target: string
      proposition: string
      proved: boolean
    }>
  } | null
  search_evidence?: {
    hypotheses_evaluated?: number
    valid_hypotheses?: number
    elapsed_ms?: number
  }
  structure_blueprint?: {
    id?: string
    kernel?: string
    observable?: string
    executable?: boolean
    proofCertificate?: Array<{
      id: string
      claim: string
      verifier: string
    }>
  }
}

type GenerationResult = {
  generated: number
  requested: number
  engine: string
  cards: GenerationCard[]
  errors: string[]
  discovered?: number
  discoveryQueued?: boolean
  discoveryJobId?: string
  backgroundResearch?: boolean
  searchState?: {
    round?: number
    depth?: number
    hypotheses_evaluated?: number
    continuing?: boolean
    next_attempt_at?: string | null
    frontier?: Array<{ source: string; target: string; obligation: string }>
    stagnant_rounds?: number
    last_progress_at?: string
  }
  generalization?: {
    id: string
    method: string
    parent_ids: string[]
    target_sort: string | null
    common_operators: string[]
    common_sorts: string[]
    roadmap: Array<{
      id: string
      source: string
      target: string
      morphism: string
      preserves: string[]
      backend: string[]
      status: 'proved' | 'open'
      parent_ids: string[]
    }>
    proof_obligations: string[]
    language_analysis?: Array<{
      token_count: number
      parse_count: number
      parse_truncated: boolean
      clause_count: number
      quantifier_prefix: string[]
      definitions: Array<{ symbol: string; canonical: string; sort: string }>
      declarations: Array<{ symbol: string; sort: string; implicit_forall: boolean }>
      constraints: Array<{ operator: string; canonical: string }>
      unresolved_references: string[]
      diagnostics: string[]
    }>
    search_evidence?: {
      max_depth: number
      max_states: number
      states_explored: number
      exhausted: boolean
    }
  }
}

type StreamEvent = {
  phase: 'start' | 'searching' | 'researching' | 'inducing' | 'registering' | 'structuring' | 'novelty' | 'verifying' | 'saving' | 'complete' | 'error' | 'done'
  message?: string
  current?: number
  total?: number
  draft?: string
  familyId?: string
  morphisms?: string[]
  similarity?: number
  structureId?: string
  structureStatus?: 'new' | 'reused' | 'pending'
  result?: GenerationResult
}

const PHASE_INFO: Record<string, { label: string; note: string; color: string }> = {
  start: { label: 'MathOS 起動中', note: '生成セッションを準備しています', color: 'text-blue-300' },
  searching: { label: 'MathOS 試行中', note: '構成可能な経路を探索しています', color: 'text-blue-300' },
  researching: { label: '自律研究を継続中', note: '探索frontierを保存し、次の戦略を自動実行します', color: 'text-cyan-300' },
  inducing: { label: '新構造を構成中', note: '親問題から型付き対象と観測を導出しています', color: 'text-cyan-300' },
  registering: { label: '構造を登録中', note: '実行可能な射列をDBへ記録しています', color: 'text-fuchsia-300' },
  structuring: { label: '構造を構成中', note: '対象と射から問題文を組み立てています', color: 'text-cyan-300' },
  novelty: { label: '新規性を照合中', note: '既存問題との同型・表層類似を調べています', color: 'text-violet-300' },
  verifying: { label: '厳密検証中', note: '解と独立検算の証明書を確認しています', color: 'text-amber-300' },
  saving: { label: '問題を保存中', note: '検証済み候補をライブラリへ追加しています', color: 'text-emerald-300' },
  complete: { label: '次の問題へ', note: '1問の構築と検証が完了しました', color: 'text-emerald-300' },
  done: { label: '生成完了', note: '検証済み問題を保存しました', color: 'text-emerald-300' },
  partial: { label: '一部完了', note: '生成できた問題を保存し、残りは棄却しました', color: 'text-amber-300' },
  error: { label: '生成を停止', note: '処理内容を確認してください', color: 'text-rose-300' },
}

const STAGES = [
  { key: 'searching', label: '経路探索' },
  { key: 'inducing', label: '型構成' },
  { key: 'registering', label: '構造登録' },
  { key: 'novelty', label: '新規性' },
  { key: 'verifying', label: '厳密検証' },
  { key: 'saving', label: '保存' },
] as const

const PHASE_RANK: Record<string, number> = {
  start: -1,
  searching: 0,
  researching: 0,
  inducing: 1,
  registering: 2,
  structuring: 2,
  novelty: 3,
  verifying: 4,
  saving: 5,
  complete: 6,
  done: 6,
  partial: 6,
}

const ACTIVE_RESEARCH_JOB_KEY = 'mathos.activeResearchJob'

function logLineColor(line: string): string {
  if (line.includes('失敗') || line.includes('停止') || line.includes('エラー')) return 'text-rose-300'
  if (line.includes('完了') || line.includes('保存しました')) return 'text-emerald-300'
  if (line.includes('検証')) return 'text-amber-200'
  if (line.includes('DB') || line.includes('登録')) return 'text-fuchsia-200'
  if (line.includes('構造') || line.includes('探索') || line.includes('射列')) return 'text-blue-200'
  return 'text-zinc-400'
}

export function GenerationPanel({
  selectedProblems,
  accessToken,
  onStatusChange,
  onPostClick,
  onGenerated,
}: Props) {
  const [generating, setGenerating] = useState(false)
  const [uiPhase, setUiPhase] = useState('start')
  const [logs, setLogs] = useState<string[]>([])
  const [genDone, setGenDone] = useState<{ ok: boolean; partial?: boolean; message: string } | null>(null)
  const [fusionCount, setFusionCount] = useState(3)
  const [batchCount, setBatchCount] = useState(4)
  const [chosenIds, setChosenIds] = useState<string[]>([])
  const [showUpgrade, setShowUpgrade] = useState(false)
  const [upgradeUsed, setUpgradeUsed] = useState(0)
  const [current, setCurrent] = useState(0)
  const [total, setTotal] = useState(1)
  const [completed, setCompleted] = useState(0)
  const [familyId, setFamilyId] = useState<string | null>(null)
  const [structureId, setStructureId] = useState<string | null>(null)
  const [structureStatus, setStructureStatus] = useState<'new' | 'reused' | 'pending' | null>(null)
  const [morphisms, setMorphisms] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const [visibleDraft, setVisibleDraft] = useState('')
  const [windowOpen, setWindowOpen] = useState(false)
  const [deepSearch, setDeepSearch] = useState(true)
  const [searchBudgetSeconds, setSearchBudgetSeconds] = useState(90)
  const [generatedCards, setGeneratedCards] = useState<GenerationCard[]>([])
  const [roadmap, setRoadmap] = useState<NonNullable<GenerationResult['generalization']>['roadmap']>([])
  const [roadmapTarget, setRoadmapTarget] = useState<string | null>(null)
  const [languageAnalysis, setLanguageAnalysis] = useState<NonNullable<GenerationResult['generalization']>['language_analysis']>([])
  const [searchEvidence, setSearchEvidence] = useState<NonNullable<GenerationResult['generalization']>['search_evidence']>(undefined)
  const [activeParents, setActiveParents] = useState<Array<{ id: string; statement: string }>>([])
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    if (!draft) {
      setVisibleDraft('')
      return
    }
    setVisibleDraft('')
    let index = 0
    const timer = window.setInterval(() => {
      index = Math.min(index + 3, draft.length)
      setVisibleDraft(draft.slice(0, index))
      if (index >= draft.length) window.clearInterval(timer)
    }, 12)
    return () => window.clearInterval(timer)
  }, [draft])

  useEffect(() => {
    const jobId = window.localStorage.getItem(ACTIVE_RESEARCH_JOB_KEY)
    if (!jobId) return
    setGenerating(true)
    setWindowOpen(true)
    setLogs([`未完了の探索ジョブ ${jobId.slice(0, 8)} を再接続しています。`])
    void pollDiscoveryJob(jobId).finally(() => setGenerating(false))
    // Mount-time recovery deliberately runs once for the persisted job id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const finish = (data: GenerationResult) => {
    const lines = data.cards.map((card, index) => {
      if (card.unresolved) {
        return `${index + 1}. ${card.structure_blueprint?.observable ?? card.family_id ?? '?'} / 要検証`
      }
      const similarity = card.similarity?.score ?? card.similarity?.max
      const suffix = typeof similarity === 'number'
        ? ` / 最大類似度 ${(similarity * 100).toFixed(0)}%`
        : ''
      return `${index + 1}. ${card.family_id ?? '?'} → ${card.answer_tex ?? '?'}${suffix}`
    })
    const discovered = data.discovered ?? 0
    const ok = data.generated > 0 || discovered > 0
    const partial = ok && data.generated < data.requested
    const message = discovered > 0 && data.generated === 0
      ? `未知構造を一から探索し、中間構造候補 ${discovered} 件を研究キューへ保存しました。未証明のため公開問題にはまだ追加していません。`
      : ok
      ? `${partial ? '一部完了' : '完了'}: ${data.generated}/${data.requested} 問を生成・検証・保存しました。${partial ? ' 残りは構造条件または新規性検査で棄却されました。' : ''}`
      : `生成できませんでした（${data.errors[0] ?? '理由不明'}）`
    setUiPhase(discovered > 0 ? 'done' : partial ? 'partial' : ok ? 'done' : 'error')
    setCurrent(data.requested)
    setTotal(data.requested)
    setCompleted(data.generated || discovered)
    setGeneratedCards(data.cards)
    setRoadmap(data.generalization?.roadmap ?? [])
    setRoadmapTarget(data.generalization?.target_sort ?? null)
    setLanguageAnalysis(data.generalization?.language_analysis ?? [])
    setSearchEvidence(data.generalization?.search_evidence)
    const finalCard = data.cards[0]
    if (finalCard) {
      setDraft(finalCard.statement_tex ?? '')
      setFamilyId(finalCard.family_id ?? null)
      setMorphisms(finalCard.morphism_chain ?? [])
      setStructureId(finalCard.structure_blueprint?.id ?? null)
      setStructureStatus(finalCard.unresolved ? 'pending' : 'new')
    }
    setLogs(previous => [...previous, ...lines, ...data.errors, message].slice(-30))
    setGenDone({ ok, partial, message })
    if (data.generated > 0) {
      window.localStorage.removeItem(ACTIVE_RESEARCH_JOB_KEY)
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        new Notification('MathOS 作問完了', { body: `${data.generated}問を生成・検証しました。` })
      }
      void onGenerated?.()
    }
  }

  const pollDiscoveryJob = async (jobId: string) => {
    let activeJobId = jobId
    window.localStorage.setItem(ACTIVE_RESEARCH_JOB_KEY, activeJobId)
    setUiPhase('inducing')
    setCompleted(0)
    setStructureId(null)
    setStructureStatus(null)
    setFamilyId(null)
    setMorphisms([])
    setDraft('選択した親問題を再解析し、実行可能な中間命題を探索しています。')
    setLogs(previous => [
      ...previous,
      '既存Atlas外の構造です。選択した問題本文から対象・射・制約を再構成します。',
      `探索ジョブ ${activeJobId.slice(0, 8)} をMathOS本体へ渡しました。`,
    ].slice(-30))
    let deliveredLogs = 0
    let observedRound = 0
    for (let attempt = 0; attempt < 5_760; attempt++) {
      if (attempt > 0) await new Promise(resolve => window.setTimeout(resolve, 5_000))
      const response = await fetch(`/api/job-status?job_id=${encodeURIComponent(activeJobId)}`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`未知構造探索の状態取得に失敗しました: ${response.status}`)
      const job = await response.json() as {
        status: 'pending' | 'processing' | 'done' | 'failed'
        logs?: Array<{ message?: string }> | string[]
        result?: GenerationResult
        error?: string | null
        resume_requested?: boolean
        replacement_job_id?: string | null
      }
      if (job.replacement_job_id) {
        activeJobId = job.replacement_job_id
        window.localStorage.setItem(ACTIVE_RESEARCH_JOB_KEY, activeJobId)
        deliveredLogs = 0
        setLogs(previous => [
          ...previous,
          `期限切れジョブの探索状態を ${activeJobId.slice(0, 8)} へ引き継ぎ、直ちに再開しました。`,
        ].slice(-30))
        continue
      }
      const allJobLines = (job.logs ?? []).map(item => typeof item === 'string' ? item : item.message ?? '').filter(Boolean)
      const jobLines = allJobLines.slice(deliveredLogs)
      deliveredLogs = allJobLines.length
      if (jobLines.length) setLogs(previous => [...previous, ...jobLines].slice(-30))
      if (job.resume_requested) {
        setLogs(previous => [...previous, '期限切れを検出し、この探索ジョブを直ちに再開しました。'].slice(-30))
      }
      if (job.status === 'done' && job.result) {
        finish(job.result)
        return
      }
      if (job.status === 'failed') {
        window.localStorage.removeItem(ACTIVE_RESEARCH_JOB_KEY)
        throw new Error(job.error ?? '未知構造探索が失敗しました')
      }
      const state = job.result?.searchState
      const generalization = job.result?.generalization
      if (generalization) {
        setRoadmap(generalization.roadmap ?? [])
        setRoadmapTarget(generalization.target_sort ?? null)
        setLanguageAnalysis(generalization.language_analysis ?? [])
        setSearchEvidence(generalization.search_evidence)
        setActiveParents(previous => previous.length
          ? previous
          : generalization.parent_ids.map(id => ({ id, statement: '保存済み親問題' })))
      }
      const researchCards = job.result?.cards ?? []
      if (job.status === 'processing' && researchCards.length > 0) {
        setGeneratedCards(researchCards)
        const leading = researchCards[0]
        setDraft(leading.statement_tex ?? '中間構造候補を検証しています。')
        setFamilyId(leading.family_id ?? null)
        setMorphisms(leading.morphism_chain ?? [])
        setStructureId(leading.structure_blueprint?.id ?? null)
        setStructureStatus('pending')
      }
      if (state?.round && state.round !== observedRound) {
        observedRound = state.round
        setLogs(previous => [
          ...previous,
          `自律探索 round ${state.round} / 深さ ${state.depth ?? '?'} / 累積仮説 ${state.hypotheses_evaluated ?? '?'}`,
          state.stagnant_rounds
            ? `同一frontierが ${state.stagnant_rounds} 回続いています。型付き列挙と実行backendだけで次候補を探索します。`
            : `未解決frontier ${state.frontier?.length ?? 0} 件を保持。次回も自動再開します。`,
        ].slice(-30))
      }
      setUiPhase(state?.continuing ? 'researching' : job.status === 'processing' ? 'inducing' : 'searching')
    }
    const message = `探索ジョブ ${activeJobId.slice(0, 8)} は8時間を超えてバックグラウンド研究を継続しています。次回アクセス時に自動再接続します。`
    setUiPhase('researching')
    setLogs(previous => [...previous, message].slice(-30))
    setGenDone({ ok: true, partial: true, message })
  }

  const applyEvent = async (event: StreamEvent) => {
    if (event.phase === 'done' && event.result) {
      if (event.result.discoveryQueued && event.result.discoveryJobId) {
        await pollDiscoveryJob(event.result.discoveryJobId)
        return
      }
      finish(event.result)
      return
    }
    setUiPhase(event.phase)
    if (typeof event.current === 'number') setCurrent(event.current)
    if (typeof event.total === 'number') setTotal(event.total)
    if (event.draft) setDraft(previous => previous === event.draft ? previous : event.draft!)
    if (event.familyId) setFamilyId(event.familyId)
    if (event.structureId) setStructureId(event.structureId)
    if (event.structureStatus) setStructureStatus(event.structureStatus)
    if (event.morphisms) setMorphisms(event.morphisms)
    if (event.phase === 'complete') setCompleted(value => Math.min(value + 1, event.total ?? total))
    if (event.message) setLogs(previous => [...previous, event.message!].slice(-30))
  }

  // MathOS は外部 LLM を使わず、構造探索・厳密計算・独立検証を順に実行する。
  const run = async (parents: ProblemWithRating[], mode: string, count: number) => {
    setGenerating(true)
    setLogs([])
    setGenDone(null)
    setUiPhase('start')
    setCurrent(0)
    setTotal(count)
    setCompleted(0)
    setFamilyId(null)
    setStructureId(null)
    setStructureStatus(null)
    setMorphisms([])
    setDraft('')
    setGeneratedCards([])
    setRoadmap([])
    setRoadmapTarget(null)
    setLanguageAnalysis([])
    setSearchEvidence(undefined)
    setActiveParents(parents.map(parent => ({ id: parent.id, statement: parent.statement })))
    setWindowOpen(true)

    const domain = parents[0]?.topic_a || undefined
    setLogs([
      `MathOS で ${count} 問を構築します（${mode}${domain ? ` / ${domain}` : ''}）`,
      '対象・射・制約を探索し、厳密計算と独立検算を行います。',
    ])

    try {
      const response = await fetch('/api/mathos-generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
          count,
          domain,
          stream: true,
          searchDepth: deepSearch ? 'deep' : 'standard',
          searchBudgetSeconds: deepSearch ? searchBudgetSeconds : 30,
          mode,
          parents: parents.map(parent => ({
            id: parent.id,
            topic_a: parent.topic_a,
            topic_b: parent.topic_b,
            statement: parent.statement,
            answer: parent.answer,
            solution: parent.solution,
            inspiration: parent.inspiration,
            meta: parent.meta,
          })),
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const message = data?.error ?? `生成エラー: ${response.status}`
        if (response.status === 402) {
          setUpgradeUsed(data?.used ?? 0)
          setShowUpgrade(true)
          setWindowOpen(false)
          return
        }
        throw new Error(message)
      }

      if (!response.body) throw new Error('生成ストリームを開始できませんでした')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let receivedFinal = false

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() ?? ''
        for (const chunk of chunks) {
          const dataLine = chunk.split('\n').find(line => line.startsWith('data: '))
          if (!dataLine) continue
          const event = JSON.parse(dataLine.slice(6)) as StreamEvent
          if (event.phase === 'done') receivedFinal = true
          await applyEvent(event)
        }
      }
      if (!receivedFinal) throw new Error('生成結果を受信する前に接続が終了しました')
    } catch (error) {
      const message = `生成失敗: ${error instanceof Error ? error.message : String(error)}`
      setLogs(previous => [...previous, message])
      setUiPhase('error')
      setGenDone({ ok: false, message })
    } finally {
      setGenerating(false)
    }
  }

  const toggleChosen = (id: string) =>
    setChosenIds(ids => ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id])

  const chosen = selectedProblems.filter(problem => chosenIds.includes(problem.id))
  // 融合は画面内の「選択済み全件」へ暗黙に広げない。チェックした親だけを送る。
  const fusionTarget = chosen
  const fusionDisabled = generating || chosen.length < 2

  const deselect = async (id: string) => {
    await fetch('/api/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
      body: JSON.stringify({ problem_id: id, status: 'pending' }),
    })
    onStatusChange(id, 'pending')
  }

  if (selectedProblems.length === 0) {
    return (
      <div className="glass rounded-md p-6 text-center text-sm text-zinc-400">
        問題一覧タブで「選択」を押すと、ここに表示されます
      </div>
    )
  }

  const phaseInfo = PHASE_INFO[uiPhase] ?? PHASE_INFO.start
  const phaseRank = PHASE_RANK[uiPhase] ?? -1
  const withinProblem = Math.max(0, Math.min(1, (phaseRank + 1) / STAGES.length))
  const progressPct = Math.round(Math.min(1, (completed + (generating ? withinProblem : 0)) / Math.max(total, 1)) * 100)
  const FREE_LIMIT = 10

  return (
    <div className="space-y-4">
      {showUpgrade && (
        <UpgradeModal accessToken={accessToken} used={upgradeUsed} limit={FREE_LIMIT} onClose={() => setShowUpgrade(false)} />
      )}

      <div className="sticky top-0 z-20 space-y-3 rounded-md border border-zinc-800 bg-[#141416] p-4 shadow-[0_10px_30px_rgba(0,0,0,0.28)]">
        <div className="text-[11px] font-semibold uppercase text-zinc-500">生成コントロール</div>

        <div className="flex items-center gap-2.5">
          <div className="w-24 shrink-0">
            <div className="text-[11px] font-medium text-zinc-200">融合生成</div>
            <div className="text-[10px] text-zinc-500">
              {chosen.length >= 2 ? `${chosen.length} 問選択` : '2問以上をチェック'}
            </div>
          </div>
          <input type="range" min={1} max={6} value={fusionCount}
            onChange={event => setFusionCount(+event.target.value)}
            className="h-1 flex-1 accent-blue-500" />
          <span className="w-5 text-right text-[11px] tabular-nums text-zinc-400">{fusionCount}</span>
          <button
            onClick={() => run(fusionTarget, 'fusion', fusionCount)}
            disabled={fusionDisabled}
            className="shrink-0 rounded bg-blue-600 px-4 py-1.5 text-[12px] font-semibold text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
          >生成</button>
        </div>
        {chosen.length === 1 && <p className="pl-24 text-[10px] text-rose-300">2 問以上チェックしてください</p>}

        <div className="flex items-center gap-2.5">
          <div className="w-24 shrink-0">
            <div className="text-[11px] font-medium text-zinc-200">一括類題</div>
            <div className="text-[10px] text-zinc-500">全 {selectedProblems.length} 問</div>
          </div>
          <input type="range" min={2} max={10} value={batchCount}
            onChange={event => setBatchCount(+event.target.value)}
            className="h-1 flex-1 accent-blue-500" />
          <span className="w-5 text-right text-[11px] tabular-nums text-zinc-400">{batchCount}</span>
          <button
            onClick={() => run(selectedProblems, 'batch', batchCount)}
            disabled={generating}
            className="shrink-0 rounded border border-zinc-700 bg-zinc-900 px-4 py-1.5 text-[12px] font-semibold text-zinc-200 transition-colors hover:border-zinc-500 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
          >類題</button>
        </div>

        <label className="flex cursor-pointer items-center justify-between border-t border-zinc-800 pt-3">
          <span>
            <span className="block text-[11px] font-medium text-zinc-200">深層探索</span>
            <span className="block text-[9px] text-zinc-500">選択した全問題の構造署名を保持して中間仮説を比較</span>
          </span>
          <input
            type="checkbox"
            checked={deepSearch}
            onChange={event => setDeepSearch(event.target.checked)}
            disabled={generating}
            className="h-4 w-4 accent-blue-500"
          />
        </label>

        {deepSearch && (
          <label className="flex items-center gap-2.5">
            <span className="w-24 shrink-0 text-[10px] text-zinc-400">探索上限</span>
            <input
              type="range"
              min={60}
              max={120}
              step={15}
              value={searchBudgetSeconds}
              onChange={event => setSearchBudgetSeconds(Number(event.target.value))}
              disabled={generating}
              className="h-1 flex-1 accent-blue-500"
            />
            <span className="w-10 text-right text-[10px] tabular-nums text-zinc-400">{searchBudgetSeconds}秒</span>
          </label>
        )}

        {genDone && !generating && (
          <div className={`mt-1 text-[11px] ${genDone.partial ? 'text-amber-300' : genDone.ok ? 'text-emerald-300' : 'text-rose-300'}`}>
            {genDone.message}
          </div>
        )}
      </div>

      {generatedCards.length > 0 && (
        <section className="space-y-2" aria-labelledby="generated-results-heading">
          <div className="flex items-end justify-between">
            <div>
              <h2 id="generated-results-heading" className="text-[14px] font-semibold text-zinc-100">
                {generatedCards.some(card => card.unresolved) ? '今回発見した構造候補' : '今回生成した問題'}
              </h2>
              <p className="text-[10px] text-zinc-500">
                {generatedCards.some(card => card.unresolved)
                  ? '選択問題から一から構成・未証明候補は研究キューで継続検証'
                  : 'その場で新規構成・検証済み・問題一覧にも自動反映'}
              </p>
            </div>
            <span className="text-[10px] tabular-nums text-emerald-300">
              {generatedCards.length} {generatedCards.some(card => card.unresolved) ? '件' : '問'}
            </span>
          </div>
          {generatedCards.map((card, index) => (
            <article key={`${card.family_id}-${index}`} className={`rounded-md border p-4 ${card.unresolved ? 'border-amber-500/25 bg-amber-500/[0.04]' : 'border-emerald-500/25 bg-emerald-500/[0.04]'}`}>
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[9px] text-zinc-500">
                <span className={`font-semibold ${card.unresolved ? 'text-amber-300' : 'text-emerald-300'}`}>
                  {card.unresolved ? '研究候補' : '生成'} {index + 1}
                </span>
                <span>{card.family_id ?? 'unknown family'}</span>
                {card.morphism_chain?.length ? <span>{card.morphism_chain.length} 検証段</span> : null}
                {card.parent_ids?.length ? <span>親: {card.parent_ids.join(', ')}</span> : null}
                {card.verification?.exact_backend ? (
                  <span className="text-emerald-300">形式計算済み</span>
                ) : card.verification?.independent_check ? (
                  <span className="text-amber-300">独立監査済み・形式検証待ち</span>
                ) : null}
                {card.search_evidence?.hypotheses_evaluated ? (
                  <span>
                    仮説 {card.search_evidence.hypotheses_evaluated.toLocaleString()} 件 / {Math.round((card.search_evidence.elapsed_ms ?? 0) / 1000)} 秒
                  </span>
                ) : null}
              </div>
              {card.parent_coverage?.length ? (
                <details className="mb-2 text-[10px] text-zinc-500">
                  <summary className="cursor-pointer text-cyan-300">選択問題ごとの構造保持を確認</summary>
                  <ul className="mt-1 space-y-1 border-l border-zinc-800 pl-3">
                    {card.parent_coverage.map(coverage => (
                      <li key={coverage.parentId}>
                        <span className={coverage.passed ? 'text-emerald-300' : 'text-rose-300'}>{coverage.passed ? '保持' : '不一致'}</span>
                        <span className="ml-2">{coverage.parentId}: {coverage.exact.join(' / ') || coverage.bridged.join(' / ')}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
              {card.fusion_derivation?.passed ? (
                <details className="mb-2 text-[10px] text-zinc-500">
                  <summary className="cursor-pointer text-fuchsia-300">
                    {card.unresolved ? '探索証明書: 全親を別々の入力として使用' : '融合証明書: 全親が不可欠'}
                  </summary>
                  <ul className="mt-1 space-y-1 border-l border-zinc-800 pl-3">
                    {card.fusion_derivation.assignments.map(assignment => (
                      <li key={`${assignment.parentId}-${assignment.portId}`}>
                        {assignment.parentId} → <span className="text-zinc-300">{assignment.portId}</span>
                        <span className="ml-2">({assignment.role}: {assignment.matchedAnchors.join(' / ')})</span>
                      </li>
                    ))}
                    {card.fusion_derivation.bridges.map(bridge => (
                      <li key={bridge.id} className="text-blue-300">
                        {bridge.consumes.join(' + ')} → {bridge.produces} [{bridge.witnessStep}]
                      </li>
                    ))}
                    <li className="text-emerald-300">
                      {card.unresolved ? '親除去で候補の構造署名が変化' : '親除去テスト: 通過'}
                    </li>
                  </ul>
                  {card.fusion_derivation.intermediatePropositions?.length ? (
                    <ol className="mt-2 max-h-40 space-y-1 overflow-y-auto border-l border-zinc-800 pl-3">
                      {card.fusion_derivation.intermediatePropositions.map((item, propositionIndex) => (
                        <li key={`${item.parentId}-${item.morphism}-${propositionIndex}`}>
                          <span className={item.proved ? 'text-emerald-300' : 'text-amber-300'}>
                            {item.proved ? '検証済み' : '要検証'}
                          </span>
                          <span className="ml-2 text-zinc-300">{item.source} → {item.target}</span>
                          <span className="ml-2">{item.proposition}</span>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </details>
              ) : null}
              {card.inherited_tags?.length ? (
                <div className="mb-2 text-[10px] text-cyan-300">
                  選択元から継承: {card.inherited_tags.join(' / ')}
                </div>
              ) : null}
              {card.bridged_tags?.length ? (
                <div className="mb-2 text-[10px] text-fuchsia-300">
                  Atlas上の隣接射で変換: {card.bridged_tags.join(' / ')}
                </div>
              ) : null}
              {card.structure_blueprint?.id ? (
                <div className="mb-2 text-[10px] text-zinc-500">
                  {card.unresolved ? '保留構造' : card.structure_blueprint.executable ? '実行構造' : '誘導構造'}: {card.structure_blueprint.id}
                </div>
              ) : null}
              {card.structure_blueprint?.proofCertificate?.length ? (
                <details className="mb-3 border-y border-zinc-800 py-2">
                  <summary className="cursor-pointer text-[10px] text-blue-300">
                    検証証明書 {card.structure_blueprint.proofCertificate.length} 段を表示
                  </summary>
                  <ol className="mt-2 max-h-48 space-y-1 overflow-y-auto pr-2 text-[9px] leading-4 text-zinc-500">
                    {card.structure_blueprint.proofCertificate.map((step, stepIndex) => (
                      <li key={`${step.id}-${stepIndex}`}>
                        <span className="mr-2 tabular-nums text-zinc-700">{stepIndex + 1}</span>
                        <span className="text-zinc-300">{step.id}</span>
                        <span className="ml-2">{step.claim}</span>
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}
              {card.atlas_expansion && card.unmapped_tags?.length ? (
                <div className="mb-2 text-[10px] text-amber-300">
                  Atlas拡張候補: {card.unmapped_tags.join(' / ')}
                </div>
              ) : null}
              <div className="text-[13px] leading-7 text-zinc-100">
                <MathText text={card.statement_tex ?? ''} />
              </div>
              {card.answer_tex && (
                <div className="mt-2 border-t border-zinc-800 pt-2 text-[12px] text-emerald-300">
                  答え: <MathText text={card.answer_tex} />
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      {selectedProblems.map(problem => (
        <div key={problem.id} className="glass rounded-md p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-[10px] text-zinc-300">{TOPIC_JP[problem.topic_a] ?? problem.topic_a}</span>
                {problem.topic_b && <span className="text-[10px] text-zinc-500">× {TOPIC_JP[problem.topic_b] ?? problem.topic_b}</span>}
                <span className="text-[10px] text-zinc-600">Gen {problem.generation}</span>
                <span className="text-[10px] text-blue-400">{(problem.total || 0).toFixed(1)}</span>
              </div>
              <div className="text-[13px] leading-relaxed text-zinc-200"><MathText text={problem.statement} /></div>
              {problem.answer && (
                <div className="mt-1.5 text-[12px] leading-relaxed text-emerald-300"><MathText text={problem.answer} /></div>
              )}
            </div>

            <div className="flex shrink-0 flex-col gap-1.5">
              <ActionButton onClick={() => run([problem], 'similar', 3)} disabled={generating}>類題</ActionButton>
              <ActionButton onClick={() => run([problem], 'expand', 2)} disabled={generating}>高次元</ActionButton>
              <ActionButton onClick={() => !problem.rating?.x_posted && onPostClick(problem)} disabled={!!problem.rating?.x_posted}>
                {problem.rating?.x_posted ? '投稿済み' : 'X 投稿'}
              </ActionButton>
              <ActionButton onClick={() => deselect(problem.id)}>解除</ActionButton>
            </div>
          </div>

          <label className="mt-3 flex cursor-pointer select-none items-center gap-2">
            <input type="checkbox" checked={chosenIds.includes(problem.id)}
              onChange={() => toggleChosen(problem.id)} className="accent-blue-500" />
            <span className="text-[11px] text-zinc-500">融合生成に含める</span>
          </label>
        </div>
      ))}

      {windowOpen && (generating || genDone !== null) && (
        <aside
          className="mathos-generation-window fixed bottom-3 left-3 right-3 z-50 overflow-hidden rounded-md border border-zinc-700 bg-[#111113] shadow-[0_24px_80px_rgba(0,0,0,0.62)] sm:bottom-6 sm:left-auto sm:right-6 sm:w-[440px]"
          aria-live="polite"
          aria-label="MathOS生成状況"
        >
          <header className="flex h-12 items-center gap-3 border-b border-zinc-800 px-4">
            <span className={`h-2.5 w-2.5 rounded-full ${generating ? 'animate-pulse bg-blue-400' : genDone?.partial ? 'bg-amber-400' : genDone?.ok ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            <div className="min-w-0 flex-1">
              <div className={`text-[12px] font-semibold ${phaseInfo.color}`}>{phaseInfo.label}</div>
              <div className="truncate text-[10px] text-zinc-500">{phaseInfo.note}</div>
            </div>
            <span className="text-[10px] tabular-nums text-zinc-500">{Math.min(current || 1, total)}/{total}</span>
            {!generating && (
              <button
                type="button"
                onClick={() => setWindowOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded text-lg text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                aria-label="生成状況を閉じる"
              >×</button>
            )}
          </header>

          <div className="space-y-3 p-4">
            <details open className="rounded border border-zinc-800 bg-[#0a0a0b]">
              <summary className="cursor-pointer px-3 py-2 text-[9px] font-semibold uppercase text-zinc-500">
                固定端点 {activeParents.length} 問
              </summary>
              <div className="max-h-28 space-y-2 overflow-y-auto border-t border-zinc-800 px-3 py-2">
                {activeParents.map((parent, index) => (
                  <div key={parent.id} className="text-[9px] leading-4 text-zinc-400">
                    <span className="mr-2 font-mono text-blue-300">P{index + 1} {parent.id.slice(0, 8)}</span>
                    <span>{parent.statement.replace(/\s+/g, ' ').slice(0, 100)}</span>
                  </div>
                ))}
              </div>
            </details>

            <div className="grid grid-cols-6 gap-1" aria-label="生成工程">
              {STAGES.map((stage, index) => {
                const active = generating && index === Math.min(phaseRank, STAGES.length - 1)
                const passed = phaseRank > index || uiPhase === 'done'
                return (
                  <div key={stage.key} className="min-w-0">
                    <div className={`mb-1 h-1 rounded-full transition-colors duration-300 ${passed ? 'bg-emerald-400' : active ? 'animate-pulse bg-blue-400' : 'bg-zinc-800'}`} />
                    <div className={`truncate text-[9px] ${passed ? 'text-emerald-300' : active ? 'text-blue-300' : 'text-zinc-600'}`}>{stage.label}</div>
                  </div>
                )
              })}
            </div>

            {languageAnalysis && languageAnalysis.length > 0 && (
              <details className="rounded border border-zinc-800 bg-[#0a0a0b]">
                <summary className="cursor-pointer px-3 py-2 text-[9px] font-semibold uppercase text-zinc-500">
                  字句・構文・意味解析 {languageAnalysis.length}/{activeParents.length} 親
                </summary>
                <div className="max-h-40 space-y-2 overflow-y-auto border-t border-zinc-800 px-3 py-2 text-[9px] leading-4 text-zinc-400">
                  {languageAnalysis.map((analysis, index) => (
                    <div key={index} className="border-b border-zinc-900 pb-2 last:border-0">
                      <div className="text-zinc-300">
                        P{index + 1}: {analysis.token_count} token / {analysis.clause_count} 節 / {analysis.parse_count} 構文候補
                        {analysis.parse_truncated ? '（上限到達）' : ''}
                      </div>
                      {analysis.quantifier_prefix.length > 0 && <div>量化: {analysis.quantifier_prefix.join(' → ')}</div>}
                      {analysis.declarations?.length > 0 && <div>宣言: {analysis.declarations.map(item => `${item.symbol}:${item.sort}`).join(' / ')}</div>}
                      {analysis.definitions.length > 0 && <div>定義: {analysis.definitions.map(item => `${item.symbol}:${item.sort}`).join(' / ')}</div>}
                      {analysis.constraints?.length > 0 && <div>関係式: {analysis.constraints.map(item => item.operator).join(' / ')}</div>}
                      {analysis.unresolved_references.length > 0 && <div className="text-amber-300">未解決参照: {analysis.unresolved_references.join(', ')}</div>}
                    </div>
                  ))}
                  {searchEvidence && (
                    <div className="text-cyan-300">
                      深さ {searchEvidence.max_depth} / 状態上限 {searchEvidence.max_states.toLocaleString()} / 検査 {searchEvidence.states_explored.toLocaleString()}
                    </div>
                  )}
                </div>
              </details>
            )}

            <div className="overflow-hidden rounded border border-zinc-800 bg-[#0a0a0b]">
              <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
                <span className="text-[9px] font-semibold uppercase text-zinc-500">Problem draft</span>
                <span className="max-w-[230px] truncate text-[9px] text-zinc-600">
                  {structureId
                    ? `${structureStatus === 'new' ? 'NEW' : structureStatus === 'reused' ? 'REUSE' : 'PENDING'} ${structureId}`
                    : familyId
                      ? `${familyId} / ${morphisms.length} verified steps`
                      : 'waiting for structure'}
                </span>
              </div>
              <div className="min-h-[92px] max-h-36 overflow-y-auto whitespace-pre-wrap px-3 py-2.5 font-mono text-[11px] leading-5 text-zinc-200">
                {visibleDraft || '構成可能な対象と射を探索しています...'}
                {generating && <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-blue-400 align-middle" />}
              </div>
            </div>

            {morphisms.length > 0 && (
              <div className="truncate border-t border-zinc-800 pt-2 font-mono text-[9px] text-cyan-300">
                {morphisms.length} 検証段: {morphisms.slice(-4).join(' → ')}
              </div>
            )}

            {roadmap.length > 0 && (
              <div className="rounded border border-cyan-500/20 bg-cyan-500/[0.03] p-2.5">
                <div className="mb-2 flex items-center justify-between text-[9px]">
                  <span className="font-semibold uppercase text-cyan-300">Proof roadmap</span>
                  <span className="max-w-[210px] truncate text-zinc-500">target: {roadmapTarget ?? 'searching'}</span>
                </div>
                <div className="max-h-36 space-y-1.5 overflow-y-auto pr-1">
                  {roadmap.slice(0, 20).map((step, index) => (
                    <div key={`${step.id}-${index}`} className="grid grid-cols-[18px_1fr] gap-1.5 font-mono text-[9px] leading-4">
                      <span className={`flex h-[18px] w-[18px] items-center justify-center rounded-full border ${step.status === 'proved' ? 'border-emerald-500/50 text-emerald-300' : 'border-amber-500/40 text-amber-300'}`}>
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate text-zinc-200">{step.source} → {step.target}</div>
                        <div className="truncate text-cyan-400">{step.morphism}</div>
                        <div className="truncate text-zinc-600">保存: {step.preserves.join(' / ') || '検証中'} · {step.backend.join(' / ') || 'backend探索中'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="mb-1.5 flex items-center justify-between text-[9px] text-zinc-500">
                <span>{completed}/{total} 問完了</span>
                <span>{progressPct}%</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-zinc-800">
                <div className="h-full rounded-full bg-blue-500 transition-[width] duration-500" style={{ width: `${progressPct}%` }} />
              </div>
            </div>

            <div className="max-h-24 space-y-1 overflow-y-auto border-t border-zinc-800 pt-2 font-mono">
              {logs.slice(-6).map((line, index) => (
                <div key={`${line}-${index}`} className={`text-[9px] leading-4 ${logLineColor(line)}`}>
                  <span className="mr-1.5 text-zinc-700">›</span>{line}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}

function ActionButton({ children, onClick, disabled = false }: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-[10px] text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}
