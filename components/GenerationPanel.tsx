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
  structure_blueprint?: {
    id?: string
    kernel?: string
    observable?: string
    executable?: boolean
  }
}

type GenerationResult = {
  generated: number
  requested: number
  engine: string
  cards: GenerationCard[]
  errors: string[]
}

type StreamEvent = {
  phase: 'start' | 'searching' | 'inducing' | 'registering' | 'structuring' | 'novelty' | 'verifying' | 'saving' | 'complete' | 'error' | 'done'
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
  const [generatedCards, setGeneratedCards] = useState<GenerationCard[]>([])
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

  const finish = (data: GenerationResult) => {
    const lines = data.cards.map((card, index) => {
      const similarity = card.similarity?.score ?? card.similarity?.max
      const suffix = typeof similarity === 'number'
        ? ` / 最大類似度 ${(similarity * 100).toFixed(0)}%`
        : ''
      return `${index + 1}. ${card.family_id ?? '?'} → ${card.answer_tex ?? '?'}${suffix}`
    })
    const ok = data.generated > 0
    const partial = ok && data.generated < data.requested
    const message = ok
      ? `${partial ? '一部完了' : '完了'}: ${data.generated}/${data.requested} 問を生成・検証・保存しました。${partial ? ' 残りは構造条件または新規性検査で棄却されました。' : ''}`
      : `生成できませんでした（${data.errors[0] ?? '理由不明'}）`
    setUiPhase(partial ? 'partial' : ok ? 'done' : 'error')
    setCompleted(data.generated)
    setGeneratedCards(data.cards)
    setLogs(previous => [...previous, ...lines, ...data.errors, message].slice(-30))
    setGenDone({ ok, partial, message })
    if (ok) void onGenerated?.()
  }

  const applyEvent = (event: StreamEvent) => {
    if (event.phase === 'done' && event.result) {
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
          applyEvent(event)
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
  const fusionTarget = chosen.length >= 2 ? chosen : selectedProblems
  const fusionDisabled = generating || (chosen.length > 0 && chosen.length < 2)

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
              {chosen.length >= 2 ? `${chosen.length} 問選択` : `全 ${selectedProblems.length} 問`}
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
            <span className="block text-[9px] text-zinc-500">選択問題の構造を保ち、最大240秒探索</span>
          </span>
          <input
            type="checkbox"
            checked={deepSearch}
            onChange={event => setDeepSearch(event.target.checked)}
            disabled={generating}
            className="h-4 w-4 accent-blue-500"
          />
        </label>

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
              <h2 id="generated-results-heading" className="text-[14px] font-semibold text-zinc-100">今回生成した問題</h2>
              <p className="text-[10px] text-zinc-500">その場で新規構成・検証済み・問題一覧にも自動反映</p>
            </div>
            <span className="text-[10px] tabular-nums text-emerald-300">{generatedCards.length} 問</span>
          </div>
          {generatedCards.map((card, index) => (
            <article key={`${card.family_id}-${index}`} className="rounded-md border border-emerald-500/25 bg-emerald-500/[0.04] p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[9px] text-zinc-500">
                <span className="font-semibold text-emerald-300">生成 {index + 1}</span>
                <span>{card.family_id ?? 'unknown family'}</span>
                {card.morphism_chain?.length ? <span>{card.morphism_chain.length} morphisms</span> : null}
                {card.parent_ids?.length ? <span>親: {card.parent_ids.join(', ')}</span> : null}
              </div>
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
                  実行構造: {card.structure_blueprint.id}
                </div>
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

            <div className="overflow-hidden rounded border border-zinc-800 bg-[#0a0a0b]">
              <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
                <span className="text-[9px] font-semibold uppercase text-zinc-500">Problem draft</span>
                <span className="max-w-[230px] truncate text-[9px] text-zinc-600">
                  {structureId
                    ? `${structureStatus === 'new' ? 'NEW' : structureStatus === 'reused' ? 'REUSE' : 'PENDING'} ${structureId}`
                    : familyId
                      ? `${familyId} / ${morphisms.length} morphisms`
                      : 'waiting for structure'}
                </span>
              </div>
              <div className="min-h-[92px] max-h-36 overflow-y-auto whitespace-pre-wrap px-3 py-2.5 font-mono text-[11px] leading-5 text-zinc-200">
                {visibleDraft || '構成可能な対象と射を探索しています...'}
                {generating && <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-blue-400 align-middle" />}
              </div>
            </div>

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
