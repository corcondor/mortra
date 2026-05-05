'use client'
import { motion } from 'framer-motion'
import type { ProblemWithRating } from '@/lib/types'
import { DIFFICULTY_COLOR, DIFFICULTY_LABEL, TOPIC_EMOJI } from '@/lib/types'
import { extractSnippet } from '@/lib/utils'
import { MathText } from './MathText'

interface Props {
  problem: ProblemWithRating
  index: number
  isActive: boolean
  onClick: () => void
  onHover: () => void
}

export function ProblemCard({ problem: p, index, isActive, onClick, onHover }: Props) {
  const diff = p.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C
  const emoji = TOPIC_EMOJI[p.topic_a] ?? '∑'
  const snippet = extractSnippet(p.statement, 72)

  return (
    <motion.button
      key={p.id}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ delay: index * 0.04, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      onMouseEnter={onHover}
      className={`
        w-full text-left rounded-2xl px-4 py-3.5
        glass glass-hover
        flex items-start gap-3
        cursor-pointer select-none
        ${isActive ? 'bg-white/10 border-white/20' : ''}
      `}
    >
      {/* Topic icon */}
      <span className="text-xl mt-0.5 opacity-70 shrink-0 w-7 text-center">
        {emoji}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {/* Difficulty badge */}
          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md border ${diffClass}`}>
            {DIFFICULTY_LABEL[diff]}
          </span>
          {/* Topic */}
          <span className="text-[11px] text-white/40 truncate">
            {p.topic_a}{p.topic_b ? ` · ${p.topic_b}` : ''}
          </span>
          {/* Score */}
          {p.total > 0 && (
            <span className="ml-auto text-[11px] text-white/30 shrink-0">
              {p.total.toFixed(1)}
            </span>
          )}
        </div>

        {/* Statement snippet */}
        <p className="text-sm text-white/80 leading-snug line-clamp-2">
          <MathText text={snippet} />
        </p>
      </div>

      {/* Chevron */}
      <span className="text-white/20 text-sm shrink-0 mt-1">›</span>
    </motion.button>
  )
}
