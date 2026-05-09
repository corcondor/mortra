'use client'
import { RefObject, useRef, useState } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
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
  scrollRootRef?: RefObject<HTMLDivElement>
  showSol: boolean
  accessToken: string | null
  onStatusChange: (id: string, status: string) => void
  onPostClick: (p: ProblemWithRating) => void
}

export function ProblemCardCuration({ problem: p, index, scrollRootRef, showSol, accessToken, onStatusChange, onPostClick }: Props) {
  const [busy,     setBusy]     = useState(false)
  const [expanded, setExpanded] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: cardRef,
    container: scrollRootRef,
    offset: ['start 92%', 'end 10%'],
  })
  const y = useTransform(scrollYProgress, [0, 0.45, 1], [118, 0, -96])
  const scale = useTransform(scrollYProgress, [0, 0.45, 1], [0.91, 1, 0.93])
  const rotateX = useTransform(scrollYProgress, [0, 0.45, 1], [15, 0, -13])
  const rotateZ = useTransform(scrollYProgress, [0, 0.45, 1], [1.6, 0, -1.2])
  const opacity = useTransform(scrollYProgress, [0, 0.12, 0.78, 1], [0.34, 1, 1, 0.5])

  const status   = p.rating?.status ?? 'pending'
  const xPosted  = p.rating?.x_posted ?? false
  const diff     = p.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C
  const ta = p.topic_a, tb = p.topic_b ?? ''
  const badge = `${TOPIC_JP[ta] ?? ta}${tb ? ` × ${TOPIC_JP[tb] ?? tb}` : ''}`

  const borderColor =
    xPosted               ? 'border-apple-blue/40 ring-1 ring-apple-blue/15' :
    status === 'selected' ? 'border-apple-green/40 ring-1 ring-apple-green/15' :
    status === 'rejected' ? 'border-zinc-300/80 opacity-60' : 'border-zinc-200/95'

  const setStatus = async (newStatus: string) => {
    setBusy(true)
    const toggle = (status === newStatus) ? 'pending' : newStatus
    await fetch('/api/status', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ problem_id: p.id, status: toggle }),
    })
    onStatusChange(p.id, toggle)
    setBusy(false)
  }

  return (
    <motion.div
      ref={cardRef}
      style={{ y, scale, rotateX, rotateZ, opacity, transformPerspective: 1200 }}
      data-note-index={index}
      className={`paper-note rounded-md p-5 md:p-7 flex flex-col gap-4 border ${borderColor} transition-colors max-w-3xl w-full mx-auto`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base text-zinc-500">{TOPIC_EMOJI[ta] ?? '∑'}</span>
        <span className="text-[10px] text-zinc-500 font-semibold tracking-wide">{badge}</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${diffClass}`}>
          {DIFFICULTY_LABEL[diff]}
        </span>
        <span className="text-[10px] text-zinc-400">Gen {p.generation}</span>
        {xPosted && <span className="text-[10px] text-apple-blue font-semibold ml-auto">✓ 投稿済</span>}
        {!xPosted && <span className="text-[10px] text-zinc-400 ml-auto">{(p.total||0).toFixed(1)}</span>}
      </div>

      {/* Statement — expand/collapse */}
      <div>
        <div
          className={`text-[15px] md:text-[16px] leading-[1.9] text-zinc-900 transition-all
            ${expanded ? '' : 'line-clamp-4'}`}
        >
          <MathText text={p.statement} />
        </div>
        {/* expand toggle — show only if text is long enough to be clipped */}
        {p.statement.length > 120 && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="mt-2 text-[11px] text-zinc-500 hover:text-apple-blue transition-colors"
          >
            {expanded ? '▲ 閉じる' : '▼ 続きを見る'}
          </button>
        )}
      </div>

      {/* Answer */}
      {p.answer && (
        <div className="text-[13px] text-emerald-700 leading-relaxed border-l-2 border-emerald-400/70 pl-3">
          <MathText text={p.answer} />
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
          <div
            className="h-full score-bar"
            style={{ width: `${Math.min(100, ((p.total||0)/10)*100)}%` }}
          />
        </div>
        <span className="text-[10px] text-zinc-400 tabular-nums">{(p.total||0).toFixed(1)}</span>
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
        <details className="text-[11px] text-zinc-500 cursor-pointer">
          <summary className="list-none text-zinc-400 hover:text-zinc-700">💡 着想</summary>
          <p className="mt-1.5 text-zinc-600 leading-relaxed">
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
        ${active ? activeClass : 'border-zinc-300 text-zinc-500 hover:border-zinc-500 hover:text-zinc-900 bg-white/45'}
        disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  )
}
