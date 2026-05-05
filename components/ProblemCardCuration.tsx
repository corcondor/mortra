'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import type { ProblemWithRating } from '@/lib/types'
import { DIFFICULTY_COLOR, DIFFICULTY_LABEL, TOPIC_EMOJI } from '@/lib/types'
import { MathText } from './MathText'

const TOPIC_JP: Record<string,string> = {
  analysis:'実解析', algebra:'代数', geometry:'幾何', number_theory:'整数論',
  complex:'複素数', recurrence:'漸化式', polynomial:'多項式',
  trigonometry:'三角関数', combinatorics:'組合せ', inequality:'不等式',
  probability:'確率', functional_eq:'関数方程式', modular:'合同算術', matrix:'行列',
}

interface Props {
  problem: ProblemWithRating
  index: number
  showSol: boolean
  onStatusChange: (id: string, status: string) => void
  onPostClick: (p: ProblemWithRating) => void
}

export function ProblemCardCuration({ problem: p, index, showSol, onStatusChange, onPostClick }: Props) {
  const [busy,     setBusy]     = useState(false)
  const [expanded, setExpanded] = useState(false)

  const status   = p.rating?.status ?? 'pending'
  const xPosted  = p.rating?.x_posted ?? false
  const diff     = p.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C
  const ta = p.topic_a, tb = p.topic_b ?? ''
  const badge = `${TOPIC_JP[ta] ?? ta}${tb ? ` × ${TOPIC_JP[tb] ?? tb}` : ''}`

  const borderColor =
    xPosted              ? 'border-apple-blue/40' :
    status === 'selected' ? 'border-apple-green/40' :
    status === 'rejected' ? 'border-white/5 opacity-50' : 'border-white/10'

  const setStatus = async (newStatus: string) => {
    setBusy(true)
    const toggle = (status === newStatus) ? 'pending' : newStatus
    await fetch('/api/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_id: p.id, status: toggle }),
    })
    onStatusChange(p.id, toggle)
    setBusy(false)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.3, ease: [0.16,1,0.3,1] }}
      className={`glass rounded-2xl p-4 flex flex-col gap-3 border ${borderColor} transition-colors`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base">{TOPIC_EMOJI[ta] ?? '∑'}</span>
        <span className="text-[10px] text-white/40 font-medium">{badge}</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${diffClass}`}>
          {DIFFICULTY_LABEL[diff]}
        </span>
        <span className="text-[10px] text-white/25">Gen {p.generation}</span>
        {xPosted && <span className="text-[10px] text-apple-blue font-semibold ml-auto">✓ 投稿済</span>}
        {!xPosted && <span className="text-[10px] text-white/25 ml-auto">{(p.total||0).toFixed(1)}</span>}
      </div>

      {/* Statement — expand/collapse */}
      <div>
        <div
          className={`text-[13px] leading-relaxed text-white/80 transition-all
            ${expanded ? '' : 'line-clamp-4'}`}
        >
          <MathText text={p.statement} />
        </div>
        {/* expand toggle — show only if text is long enough to be clipped */}
        {p.statement.length > 120 && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="mt-1 text-[11px] text-white/30 hover:text-apple-blue transition-colors"
          >
            {expanded ? '▲ 閉じる' : '▼ 続きを見る'}
          </button>
        )}
      </div>

      {/* Answer */}
      {p.answer && (
        <div className="text-[12px] text-apple-green/90 leading-relaxed">
          <MathText text={p.answer} />
        </div>
      )}

      {/* Solution */}
      {showSol && p.solution && (
        <div className="text-[11px] text-white/40 leading-relaxed border-t border-white/5 pt-2">
          {p.solution.slice(0, 200)}
        </div>
      )}

      {/* Score bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-[2px] bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full score-bar"
            style={{ width: `${Math.min(100, ((p.total||0)/10)*100)}%` }}
          />
        </div>
        <span className="text-[10px] text-white/25 tabular-nums">{(p.total||0).toFixed(1)}</span>
      </div>

      {/* Action buttons */}
      <div className="grid grid-cols-3 gap-1.5">
        <ActionBtn
          active={status === 'selected'}
          activeClass="bg-apple-green/20 border-apple-green/40 text-apple-green"
          onClick={() => setStatus('selected')}
          disabled={busy}
        >
          {status === 'selected' ? '✓ 選択中' : '⭐ 選択'}
        </ActionBtn>
        <ActionBtn
          active={status === 'rejected'}
          activeClass="bg-white/10 border-white/20 text-white/60"
          onClick={() => setStatus('rejected')}
          disabled={busy}
        >
          {status === 'rejected' ? '↩ 戻す' : 'スキップ'}
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

      {/* Inspiration toggle */}
      {p.inspiration && (
        <details className="text-[11px] text-white/35 cursor-pointer">
          <summary className="list-none text-white/30 hover:text-white/60">💡 着想</summary>
          <p className="mt-1.5 text-white/50 leading-relaxed">
            {p.inspiration.slice(0, 300)}
          </p>
        </details>
      )}
    </motion.div>
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
      className={`text-[11px] font-medium px-2 py-1.5 rounded-xl border transition-all
        ${active ? activeClass : 'border-white/10 text-white/40 hover:border-white/20 hover:text-white/70'}
        disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  )
}
