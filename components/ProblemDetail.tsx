'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useRef } from 'react'
import type { ProblemWithRating } from '@/lib/types'
import { DIFFICULTY_COLOR, DIFFICULTY_LABEL, TOPIC_EMOJI } from '@/lib/types'
import { MathText } from './MathText'

interface Props {
  problem: ProblemWithRating | null
  onClose: () => void
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  const pct = (value / 10) * 100
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-white/50">
        <span>{label}</span>
        <span>{value.toFixed(1)}</span>
      </div>
      <div className="h-[3px] rounded-full bg-white/10">
        <div className="score-bar" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function ProblemDetail({ problem, onClose }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // reset scroll on open
  useEffect(() => {
    if (problem) scrollRef.current?.scrollTo(0, 0)
  }, [problem?.id])

  // Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const diff = problem?.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C

  return (
    <AnimatePresence>
      {problem && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm"
            style={{ zIndex: 40 }}
            onClick={onClose}
          />

          {/* Sheet — slides up from bottom (iOS modal style) */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320, mass: 0.9 }}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={{ top: 0, bottom: 0.3 }}
            onDragEnd={(_, info) => { if (info.offset.y > 120) onClose() }}
            className="fixed left-0 right-0 bottom-0 glass rounded-t-3xl overflow-hidden"
            style={{ zIndex: 50, maxHeight: '88vh' }}
          >
            {/* Drag handle */}
            <div className="pt-3 pb-0">
              <div className="drag-handle" />
            </div>

            {/* Scrollable content */}
            <div ref={scrollRef} className="overflow-y-auto" style={{ maxHeight: 'calc(88vh - 24px)' }}>
              <div className="px-6 pb-10 space-y-6">

                {/* Header */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-2xl">
                      {TOPIC_EMOJI[problem.topic_a] ?? '∑'}
                    </span>
                    <span className={`text-xs font-semibold px-2 py-1 rounded-lg border ${diffClass}`}>
                      {DIFFICULTY_LABEL[diff]}
                    </span>
                    <span className="text-xs text-white/40">
                      {problem.topic_a}{problem.topic_b ? ` · ${problem.topic_b}` : ''}
                    </span>
                  </div>
                  <button
                    onClick={onClose}
                    className="text-white/30 hover:text-white/70 transition-colors text-xl leading-none shrink-0"
                  >
                    ✕
                  </button>
                </div>

                {/* Statement */}
                <section>
                  <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">問題文</h3>
                  <div className="glass rounded-2xl px-5 py-4 text-[15px] leading-relaxed text-white/90">
                    <MathText text={problem.statement} large />
                  </div>
                </section>

                {/* Answer */}
                {problem.answer && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">答え</h3>
                    <div className="glass rounded-2xl px-5 py-4 text-[15px] leading-relaxed">
                      <MathText text={problem.answer} large />
                    </div>
                  </section>
                )}

                {/* Inspiration */}
                {problem.inspiration && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">着想</h3>
                    <div className="glass rounded-2xl px-5 py-4 text-[14px] leading-relaxed text-white/75">
                      <MathText text={problem.inspiration} />
                    </div>
                  </section>
                )}

                {/* Solution */}
                {problem.solution && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">解法メモ</h3>
                    <div className="glass rounded-2xl px-5 py-4 text-[13px] leading-relaxed text-white/60">
                      <MathText text={problem.solution} />
                    </div>
                  </section>
                )}

                {/* Scores */}
                {problem.total > 0 && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-4">評価</h3>
                    <div className="glass rounded-2xl px-5 py-4 space-y-3">
                      <ScoreRow label="意外性"     value={problem.surprise} />
                      <ScoreRow label="ミニマル"   value={problem.minimality} />
                      <ScoreRow label="接続性"     value={problem.connection} />
                      <ScoreRow label="必然性"     value={problem.inevitability} />
                      <ScoreRow label="計算難度"   value={problem.diff_cal} />
                      <div className="pt-2 border-t border-white/10">
                        <ScoreRow label="総合"       value={problem.total} />
                      </div>
                    </div>
                  </section>
                )}

              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
