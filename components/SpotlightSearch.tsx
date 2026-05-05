'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ProblemWithRating } from '@/lib/types'
import { filterProblems } from '@/lib/utils'
import { ProblemCard } from './ProblemCard'
import { ProblemDetail } from './ProblemDetail'

interface Props {
  problems: ProblemWithRating[]
}

const TOPICS = ['analysis','algebra','geometry','number_theory','complex','recurrence','polynomial','trigonometry','combinatorics','inequality']

export function SpotlightSearch({ problems }: Props) {
  const [query, setQuery]         = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const [selected, setSelected]   = useState<ProblemWithRating | null>(null)
  const [topicFilter, setTopic]   = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const filtered = filterProblems(
    topicFilter ? problems.filter(p => p.topic_a === topicFilter || p.topic_b === topicFilter) : problems,
    query
  )

  // reset index when results change
  useEffect(() => { setActiveIdx(0) }, [query, topicFilter])

  // global ⌘K / Ctrl+K to focus
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  const handleKey = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[activeIdx]) {
      setSelected(filtered[activeIdx])
    }
  }, [filtered, activeIdx])

  return (
    <>
      <div className="flex flex-col items-center w-full px-4" style={{ paddingTop: '18vh' }}>

        {/* Logo / title */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16,1,0.3,1] }}
          className="mb-8 text-center"
        >
          <h1 className="text-3xl font-semibold tracking-tight text-white/90">
            Math Corpus
          </h1>
          <p className="text-sm text-white/35 mt-1">
            {problems.length} problems · ⌘K to focus
          </p>
        </motion.div>

        {/* Search bar */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.1, ease: [0.16,1,0.3,1] }}
          className="w-full max-w-2xl"
        >
          <div className="relative">
            {/* magnifier icon */}
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30 text-lg select-none pointer-events-none">
              ⌕
            </span>
            <input
              ref={inputRef}
              autoFocus
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKey}
              placeholder="問題を検索… (テーマ、キーワード)"
              className="spotlight-input w-full rounded-2xl pl-11 pr-4 py-4 text-base"
            />
            {query && (
              <button
                onClick={() => { setQuery(''); inputRef.current?.focus() }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/25 hover:text-white/60 transition-colors text-sm"
              >
                ✕
              </button>
            )}
          </div>

          {/* Topic chip filters */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="flex gap-2 flex-wrap mt-3 px-1"
          >
            {TOPICS.map(t => (
              <button
                key={t}
                onClick={() => setTopic(topicFilter === t ? null : t)}
                className={`text-[11px] px-2.5 py-1 rounded-full border transition-all duration-150
                  ${topicFilter === t
                    ? 'bg-apple-blue/20 border-apple-blue/50 text-apple-blue'
                    : 'border-white/10 text-white/35 hover:border-white/25 hover:text-white/60'
                  }`}
              >
                {t}
              </button>
            ))}
          </motion.div>
        </motion.div>

        {/* Results */}
        <motion.div
          className="w-full max-w-2xl mt-4 space-y-1.5 overflow-y-auto"
          style={{ maxHeight: 'calc(100vh - 36vh - 120px)' }}
        >
          <AnimatePresence mode="popLayout">
            {filtered.length > 0 ? (
              filtered.map((p, i) => (
                <ProblemCard
                  key={p.id}
                  problem={p}
                  index={i}
                  isActive={i === activeIdx}
                  onClick={() => setSelected(p)}
                  onHover={() => setActiveIdx(i)}
                />
              ))
            ) : query ? (
              <motion.p
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center text-white/30 text-sm py-8"
              >
                「{query}」に一致する問題が見つかりません
              </motion.p>
            ) : null}
          </AnimatePresence>
        </motion.div>

      </div>

      {/* Detail sheet */}
      <ProblemDetail problem={selected} onClose={() => setSelected(null)} />
    </>
  )
}
