'use client'
import { RefObject, useMemo, useState } from 'react'
import type { ProblemWithRating } from '@/lib/types'
import { DIFFICULTY_COLOR, DIFFICULTY_LABEL, TOPIC_EMOJI } from '@/lib/types'
import { MathText } from './MathText'

const REPAIR_REASONS = [
  ['unnatural_connection', '接続が不自然'],
  ['too_easy', '簡単すぎる'],
  ['too_typical', '典型的すぎる'],
  ['short_proof', '構想が短い'],
  ['unnatural_wording', '文章が不自然'],
] as const

const TOPIC_JP: Record<string,string> = {
  analysis:'実解析', algebra:'代数', geometry:'幾何', number_theory:'整数論',
  complex:'複素数', recurrence:'漸化式', polynomial:'多項式',
  trigonometry:'三角関数', combinatorics:'組合せ', inequality:'不等式',
  probability:'確率', functional_eq:'関数方程式', modular:'合同算術', matrix:'行列',
}

interface Props {
  problem: ProblemWithRating
  index: number
  scrollRootRef?: RefObject<HTMLDivElement>
  showSol: boolean
  accessToken: string | null
  onStatusChange:  (id: string, status: string) => void
  onAnswerChange:  (id: string, correctedAnswer: string | null, isIncorrect: boolean) => void
  onPostClick: (p: ProblemWithRating) => void
}

export function ProblemCardCuration({
  problem: p, index, scrollRootRef, showSol,
  accessToken, onStatusChange, onAnswerChange, onPostClick,
}: Props) {
  const [busy,           setBusy]           = useState(false)
  const [expanded,       setExpanded]       = useState(false)
  const [editingAnswer,  setEditingAnswer]  = useState(false)
  const [answerDraft,    setAnswerDraft]    = useState('')
  const [savingAnswer,   setSavingAnswer]   = useState(false)
  const [feedbackReasons, setFeedbackReasons] = useState<string[]>(() => {
    try {
      const note = p.rating?.note ? JSON.parse(p.rating.note) : null
      return Array.isArray(note?.curation_feedback?.reasons)
        ? note.curation_feedback.reasons.filter((reason: unknown): reason is string => typeof reason === 'string')
        : []
    } catch {
      return []
    }
  })

  void scrollRootRef

  const status      = p.rating?.status      ?? 'pending'
  const xPosted     = p.rating?.x_posted    ?? false
  const isIncorrect = p.rating?.is_incorrect ?? false
  const correctedAns = p.rating?.corrected_answer ?? null
  const displayAnswer = correctedAns ?? p.answer

  const diff      = p.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C
  const ta = p.topic_a, tb = p.topic_b ?? ''
  const badge = `${TOPIC_JP[ta] ?? ta}${tb ? ` × ${TOPIC_JP[tb] ?? tb}` : ''}`
  const meta = useMemo<Record<string, unknown>>(() => {
    try { return p.meta ? JSON.parse(p.meta) as Record<string, unknown> : {} }
    catch { return {} }
  }, [p.meta])
  const tags = useMemo(() => {
    const raw = Array.isArray(meta.tags) ? meta.tags : []
    return raw.filter((tag): tag is string => typeof tag === 'string' && tag.trim().length > 0).slice(0, 6)
  }, [meta])
  const features = typeof meta.features === 'string' ? meta.features : null
  const sourceLabel = typeof meta.university_short === 'string'
    ? `${meta.university_short}${typeof meta.year === 'string' ? ` ${meta.year}` : ''}`
    : null

  const borderColor =
    isIncorrect            ? 'border-red-400/50 ring-1 ring-red-400/20' :
    xPosted                ? 'border-apple-blue/40 ring-1 ring-apple-blue/15' :
    status === 'selected'  ? 'border-apple-green/40 ring-1 ring-apple-green/15' :
    status === 'rejected'  ? 'border-zinc-300/80 opacity-60' : 'border-zinc-200/95'

  const authHeaders = (): Record<string, string> => ({
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  })

  const setStatus = async (newStatus: string) => {
    setBusy(true)
    const toggle = (status === newStatus) ? 'pending' : newStatus
    await fetch('/api/status', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ problem_id: p.id, status: toggle }),
    })
    onStatusChange(p.id, toggle)
    setBusy(false)
  }

  const toggleFeedbackReason = async (reason: string) => {
    const next = feedbackReasons.includes(reason)
      ? feedbackReasons.filter(item => item !== reason)
      : [...feedbackReasons, reason]
    setFeedbackReasons(next)
    await fetch('/api/status', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        problem_id: p.id,
        status: 'rejected',
        feedback_reasons: next,
      }),
    })
  }

  const toggleIncorrect = async () => {
    setBusy(true)
    const next = !isIncorrect
    await fetch('/api/correct', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ problem_id: p.id, is_incorrect: next }),
    })
    onAnswerChange(p.id, correctedAns, next)
    if (next) {
      setAnswerDraft(correctedAns ?? p.answer ?? '')
      setEditingAnswer(true)
    } else {
      setEditingAnswer(false)
    }
    setBusy(false)
  }

  const saveAnswer = async () => {
    setSavingAnswer(true)
    const trimmed = answerDraft.trim() || null
    await fetch('/api/correct', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        problem_id:       p.id,
        is_incorrect:     true,
        corrected_answer: trimmed,
      }),
    })
    onAnswerChange(p.id, trimmed, true)
    setEditingAnswer(false)
    setSavingAnswer(false)
  }

  return (
    <article
      data-note-index={index}
      className={`paper-note rounded-md p-4 md:p-5 flex flex-col gap-3 border ${borderColor} transition-colors w-full`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-zinc-500" aria-hidden>{TOPIC_EMOJI[ta] ?? '∑'}</span>
        <span className="text-[10px] text-zinc-500 font-semibold tracking-wide">{badge}</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${diffClass}`}>
          {DIFFICULTY_LABEL[diff]}
        </span>
        <span className="text-[10px] text-zinc-400">
          {sourceLabel ?? `Gen ${p.generation}`}
        </span>

        {/* 数値ゼロバッジ：問題文に数字が一つもない場合 */}
        {!/\d/.test(p.statement) && (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border
                           border-amber-400/50 bg-amber-50 text-amber-600"
                title="問題文に数字なし・一行完全列挙型">
            ✦ 数値ゼロ
          </span>
        )}

        {/* 誤問バッジ */}
        {isIncorrect && (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border
                           border-red-400/40 bg-red-50 text-red-500">
            ⚠ 誤問{correctedAns ? '（修正済）' : '（未修正）'}
          </span>
        )}

        {xPosted && <span className="text-[10px] text-apple-blue font-semibold ml-auto">✓ 投稿済</span>}
        {!xPosted && <span className="text-[10px] text-zinc-400 ml-auto">{(p.total||0).toFixed(1)}</span>}
      </div>

      {(tags.length > 0 || features) && (
        <div className="flex flex-col gap-2 border-y border-zinc-200/70 py-2">
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map(tag => (
                <span
                  key={tag}
                  className="rounded-md border border-zinc-300 bg-white/60 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {features && (
            <p className="text-[11px] leading-relaxed text-zinc-500">{features}</p>
          )}
        </div>
      )}

      {/* Statement */}
      <div>
        <div className={`text-[14px] md:text-[15px] leading-[1.8] text-zinc-900 transition-all
          ${expanded ? '' : 'line-clamp-4'}`}>
          <MathText text={p.statement} />
        </div>
        {p.statement.length > 120 && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="mt-2 text-[11px] text-zinc-500 hover:text-apple-blue transition-colors"
          >
            {expanded ? '▲ 閉じる' : '▼ 続きを見る'}
          </button>
        )}
      </div>

      {/* Answer — 通常表示 or 編集モード */}
      {displayAnswer && !editingAnswer && (
        <div className={`text-[13px] leading-relaxed border-l-2 pl-3 flex items-start gap-2
          ${isIncorrect
            ? correctedAns
              ? 'border-emerald-400/70 text-emerald-700'
              : 'border-red-300 text-red-600'
            : 'border-emerald-400/70 text-emerald-700'}`}
        >
          <MathText text={displayAnswer} />
          {isIncorrect && (
            <button
              onClick={() => { setAnswerDraft(displayAnswer); setEditingAnswer(true) }}
              className="shrink-0 text-[10px] text-zinc-400 hover:text-zinc-700 ml-1 mt-0.5"
            >
              ✏ 編集
            </button>
          )}
        </div>
      )}

      {/* Answer 編集パネル */}
      {editingAnswer && (
        <div className="flex flex-col gap-2 border border-red-200 rounded-md p-3 bg-red-50/50">
          <p className="text-[11px] text-red-500 font-medium">修正後の答えを入力（LaTeX可）</p>
          <textarea
            value={answerDraft}
            onChange={e => setAnswerDraft(e.target.value)}
            rows={3}
            className="w-full text-[13px] text-zinc-800 bg-white border border-zinc-300 rounded
                       px-3 py-2 outline-none focus:border-apple-blue resize-y font-mono"
            placeholder="修正後の答え..."
          />
          {answerDraft.trim() && (
            <div className="text-[12px] text-emerald-700 border-l-2 border-emerald-400/70 pl-2">
              <MathText text={answerDraft} />
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={saveAnswer}
              disabled={savingAnswer}
              className="px-3 py-1 bg-emerald-600 text-white text-[11px] font-semibold
                         rounded hover:bg-emerald-700 disabled:opacity-40 transition-colors"
            >
              {savingAnswer ? '保存中…' : '保存'}
            </button>
            <button
              onClick={() => setEditingAnswer(false)}
              className="px-3 py-1 text-zinc-500 text-[11px] hover:text-zinc-800 transition-colors"
            >
              キャンセル
            </button>
          </div>
        </div>
      )}

      {/* Solution */}
      {showSol && p.solution && (
        <div className="text-[11px] text-zinc-500 leading-relaxed border-t border-zinc-200 pt-3">
          {p.solution.slice(0, 200)}
        </div>
      )}

      {/* Score bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-[2px] bg-zinc-200 rounded-full overflow-hidden">
          <div className="h-full score-bar" style={{ width: `${Math.min(100, ((p.total||0)/10)*100)}%` }} />
        </div>
        <span className="text-[10px] text-zinc-400 tabular-nums">{(p.total||0).toFixed(1)}</span>
      </div>

      {/* Action buttons — 4列 */}
      <div className="grid grid-cols-4 gap-1.5">
        <ActionBtn
          active={status === 'selected'}
          activeClass="bg-apple-green/20 border-apple-green/40 text-apple-green"
          onClick={() => setStatus('selected')} disabled={busy}
        >
          {status === 'selected' ? '✓ 選択中' : '⭐ 選択'}
        </ActionBtn>
        <ActionBtn
          active={status === 'rejected'}
          activeClass="bg-zinc-100 border-zinc-300 text-zinc-700"
          onClick={() => setStatus('rejected')} disabled={busy}
        >
          {status === 'rejected' ? '↩ 戻す' : 'スキップ'}
        </ActionBtn>
        <ActionBtn
          active={isIncorrect}
          activeClass="bg-red-50 border-red-400/40 text-red-500"
          onClick={toggleIncorrect} disabled={busy}
        >
          {isIncorrect ? '✓ 誤問' : '⚠ 誤問'}
        </ActionBtn>
        <ActionBtn
          active={xPosted}
          activeClass="bg-apple-blue/20 border-apple-blue/40 text-apple-blue"
          onClick={() => !xPosted && onPostClick(p)}
          disabled={busy || xPosted}
        >
          {xPosted ? '✓ 済' : '𝕏 投稿'}
        </ActionBtn>
      </div>

      {status === 'rejected' && (
        <div className="border-t border-zinc-200 pt-2">
          <p className="mb-2 text-[10px] font-semibold text-zinc-500">改善理由（構造は修復候補として残します）</p>
          <div className="flex flex-wrap gap-1.5">
            {REPAIR_REASONS.map(([value, label]) => {
              const active = feedbackReasons.includes(value)
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => toggleFeedbackReason(value)}
                  className={`rounded border px-2 py-1 text-[10px] transition-colors ${
                    active
                      ? 'border-[#175cd3] bg-[#eff6ff] font-semibold text-[#175cd3]'
                      : 'border-zinc-300 bg-white text-zinc-500 hover:border-zinc-400'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Inspiration */}
      {p.inspiration && (
        <details className="text-[11px] text-zinc-500 cursor-pointer">
          <summary className="list-none text-zinc-400 hover:text-zinc-700">💡 着想</summary>
          <p className="mt-1.5 text-zinc-600 leading-relaxed">{p.inspiration.slice(0, 300)}</p>
        </details>
      )}
    </article>
  )
}

function ActionBtn({
  children, active, activeClass, onClick, disabled,
}: {
  children: React.ReactNode; active: boolean; activeClass: string
  onClick: () => void; disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-[11px] font-medium px-2 py-1.5 rounded border transition-all
        ${active ? activeClass : 'border-zinc-300 text-zinc-500 hover:border-zinc-500 hover:text-zinc-900 bg-white/45'}
        disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  )
}
