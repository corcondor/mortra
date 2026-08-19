'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ProblemWithRating } from '@/lib/types'
import { DIFFICULTY_COLOR, DIFFICULTY_LABEL, TOPIC_EMOJI } from '@/lib/types'
import { MathText } from './MathText'
import { ProblemFigure } from './mortra/ProblemArtifact'
import { buildProblemDiagram, type ProblemDiagram } from '@/lib/mortra/problem-artifact'

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

type TikzState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; code: string; type: string; verified?: boolean }
  | { status: 'error'; message: string }

type VerifyState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; result: string; valid: boolean }
  | { status: 'error'; message: string }

type PdfState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }

interface ProblemMeta {
  title?: string
  tags?: string[]
  points?: number
  features?: string
  difficulty10?: number
  tikz?: string
  tikz_type?: string
  tikz_verified?: boolean
  familyId?: string
  parameters?: Record<string, number>
  morphismChain?: string[]
  diagram?: ProblemDiagram
}

export function ProblemDetail({ problem, onClose }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [tikz, setTikz] = useState<TikzState>({ status: 'idle' })
  const [verify, setVerify] = useState<VerifyState>({ status: 'idle' })
  const [pdf, setPdf] = useState<PdfState>({ status: 'idle' })
  const [tikzPreviewUrl, setTikzPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const meta: ProblemMeta = useMemo(() => {
    if (!problem?.meta) return {}
    try { return JSON.parse(problem.meta) } catch { return {} }
  }, [problem?.meta])

  useEffect(() => {
    if (problem) {
      scrollRef.current?.scrollTo(0, 0)
      // キャッシュ済み TikZ があれば即表示
      if (meta.tikz) {
        setTikz({ status: 'done', code: meta.tikz, type: meta.tikz_type ?? 'auto', verified: meta.tikz_verified })
      } else {
        setTikz({ status: 'idle' })
      }
      setVerify({ status: 'idle' })
      setPdf({ status: 'idle' })
      setTikzPreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return null })
    }
  }, [problem?.id])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  async function verifyAnswer() {
    if (!problem) return
    setVerify({ status: 'loading' })
    try {
      const res = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_id: problem.id }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? 'Unknown error')
      setVerify({ status: 'done', result: data.wolfram_result, valid: data.valid })
    } catch (e: any) {
      setVerify({ status: 'error', message: e.message })
    }
  }

  /** 鉄緑会風 解説プリント PDF をダウンロード */
  async function downloadPdf() {
    if (!problem) return
    setPdf({ status: 'loading' })
    try {
      const res = await fetch('/api/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_id: problem.id }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.log ? `${data.error}\n${data.log}` : data.error)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `sakumon-${problem.id.slice(0, 8)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      setPdf({ status: 'idle' })
    } catch (e: any) {
      setPdf({ status: 'error', message: e.message })
    }
  }

  /** TikZ 図のみコンパイルしてインラインプレビュー */
  async function previewTikz() {
    if (!problem) return
    setPreviewLoading(true)
    try {
      const res = await fetch('/api/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_id: problem.id, mode: 'tikz' }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error)
      }
      const blob = await res.blob()
      setTikzPreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob) })
    } catch (e: any) {
      setTikz(t => t.status === 'done' ? t : { status: 'error', message: e.message })
      alert(`図プレビュー失敗: ${e.message}`)
    } finally {
      setPreviewLoading(false)
    }
  }

  function copyTikz() {
    if (tikz.status !== 'done') return
    navigator.clipboard.writeText(tikz.code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const diff = problem?.difficulty ?? 'C'
  const diffClass = DIFFICULTY_COLOR[diff] ?? DIFFICULTY_COLOR.C
  const answerDiagram = problem?.source_file === 'mathos_live_session' || meta.diagram
    ? meta.diagram ?? buildProblemDiagram({
        familyId: meta.familyId ?? problem?.topic_b ?? undefined,
        domain: problem?.topic_a,
        parameters: meta.parameters,
        morphismChain: meta.morphismChain,
      })
    : null

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

          {/* Sheet */}
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
                    <span className="text-2xl">{TOPIC_EMOJI[problem.topic_a] ?? '∑'}</span>
                    <span className={`text-xs font-semibold px-2 py-1 rounded-lg border ${diffClass}`}>
                      {DIFFICULTY_LABEL[diff]}
                      {meta.difficulty10 ? ` ${meta.difficulty10}/10` : ''}
                    </span>
                    {meta.points && (
                      <span className="text-xs font-semibold px-2 py-1 rounded-lg border text-white/60 border-white/15 bg-white/5">
                        {meta.points}点
                      </span>
                    )}
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

                {/* Tags */}
                {meta.tags && meta.tags.length > 0 && (
                  <div className="flex gap-1.5 flex-wrap -mt-2">
                    {meta.tags.map(t => (
                      <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-apple-blue/10 text-apple-blue/90 border border-apple-blue/20">
                        {t}
                      </span>
                    ))}
                  </div>
                )}

                {/* Statement */}
                <section>
                  <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">問題文</h3>
                  <div className="glass rounded-2xl px-5 py-4 text-[15px] leading-relaxed text-white/90">
                    <MathText text={problem.statement} large />
                  </div>
                </section>

                {answerDiagram && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">解答で用いる図</h3>
                    <ProblemFigure diagram={answerDiagram} />
                  </section>
                )}

                {/* Features (特徴・狙い) */}
                {meta.features && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">特徴・狙い</h3>
                    <div className="glass rounded-2xl px-5 py-4 text-[13px] leading-relaxed text-white/70">
                      <MathText text={meta.features} />
                    </div>
                  </section>
                )}

                {/* Action buttons */}
                <div className="flex gap-2 flex-wrap">
                  {/* TikZ figure preview */}
                  {tikz.status === 'done' && (
                    <button
                      onClick={previewTikz}
                      disabled={previewLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass glass-hover text-[12px] text-white/70 hover:text-white transition-colors disabled:opacity-50"
                    >
                      {previewLoading ? (
                        <>
                          <span className="inline-block w-3 h-3 border border-white/40 border-t-white/80 rounded-full animate-spin" />
                          描画中…
                        </>
                      ) : (
                        <>
                          <span className="text-base leading-none">🖼️</span>
                          図プレビュー
                        </>
                      )}
                    </button>
                  )}

                  {/* PDF download (鉄緑会風) */}
                  <button
                    onClick={downloadPdf}
                    disabled={pdf.status === 'loading'}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass glass-hover text-[12px] text-white/70 hover:text-white transition-colors disabled:opacity-50"
                  >
                    {pdf.status === 'loading' ? (
                      <>
                        <span className="inline-block w-3 h-3 border border-white/40 border-t-white/80 rounded-full animate-spin" />
                        組版中…
                      </>
                    ) : (
                      <>
                        <span className="text-base leading-none">📄</span>
                        PDF保存
                      </>
                    )}
                  </button>

                  {/* Wolfram verify button */}
                  {problem.answer && (
                    <button
                      onClick={verifyAnswer}
                      disabled={verify.status === 'loading'}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass glass-hover text-[12px] text-white/70 hover:text-white transition-colors disabled:opacity-50"
                    >
                      {verify.status === 'loading' ? (
                        <>
                          <span className="inline-block w-3 h-3 border border-white/40 border-t-white/80 rounded-full animate-spin" />
                          検証中…
                        </>
                      ) : (
                        <>
                          <span className="text-base leading-none">🔢</span>
                          Wolfram 検証
                        </>
                      )}
                    </button>
                  )}
                </div>

                {pdf.status === 'error' && (
                  <p className="text-[12px] text-red-400/80 whitespace-pre-wrap">PDF生成エラー: {pdf.message}</p>
                )}

                {/* TikZ figure preview (compiled PDF) */}
                {tikzPreviewUrl && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">図プレビュー</h3>
                    <object
                      data={tikzPreviewUrl}
                      type="application/pdf"
                      className="w-full rounded-2xl bg-white"
                      style={{ height: 360 }}
                    >
                      <a href={tikzPreviewUrl} target="_blank" className="text-apple-blue text-[12px]">PDFを開く</a>
                    </object>
                  </section>
                )}

                {/* Wolfram result */}
                {verify.status === 'done' && (
                  <section>
                    <h3 className="text-[11px] uppercase tracking-widest text-white/30 mb-3">
                      Wolfram 検証結果
                    </h3>
                    <div className={`glass rounded-2xl px-5 py-4 text-[13px] border ${verify.valid ? 'border-green-500/30' : 'border-yellow-500/30'}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span>{verify.valid ? '✅' : '⚠️'}</span>
                        <span className="text-white/50 text-[11px]">
                          {verify.valid ? 'WolframAlpha で簡約化成功' : '結果なし / 簡約化不可'}
                        </span>
                      </div>
                      {verify.result && (
                        <p className="font-mono text-white/80 text-[12px] mt-2">{verify.result}</p>
                      )}
                    </div>
                  </section>
                )}
                {verify.status === 'error' && (
                  <p className="text-[12px] text-red-400/80">検証エラー: {verify.message}</p>
                )}

                {/* TikZ result */}
                {tikz.status === 'done' && (
                  <section>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-[11px] uppercase tracking-widest text-white/30">
                        TikZ コード
                        <span className="ml-2 normal-case text-white/20">({tikz.type})</span>
                        {tikz.verified && (
                          <span className="ml-2 normal-case text-green-400/70">✓ コンパイル検証済</span>
                        )}
                      </h3>
                      <button
                        onClick={copyTikz}
                        className="text-[11px] text-white/40 hover:text-white/70 transition-colors"
                      >
                        {copied ? '✓ コピー済' : 'コピー'}
                      </button>
                    </div>
                    <pre className="glass rounded-2xl px-4 py-4 text-[11px] font-mono text-white/70 overflow-x-auto leading-relaxed whitespace-pre-wrap break-all">
                      {tikz.code}
                    </pre>
                  </section>
                )}
                {tikz.status === 'error' && (
                  <p className="text-[12px] text-red-400/80">TikZ表示エラー: {tikz.message}</p>
                )}

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
                      <ScoreRow label="意外性"   value={problem.surprise} />
                      <ScoreRow label="ミニマル" value={problem.minimality} />
                      <ScoreRow label="接続性"   value={problem.connection} />
                      <ScoreRow label="必然性"   value={problem.inevitability} />
                      <ScoreRow label="計算難度" value={problem.diff_cal} />
                      <div className="pt-2 border-t border-white/10">
                        <ScoreRow label="総合"   value={problem.total} />
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
