'use client'
import { AnimatePresence, motion } from 'framer-motion'
import { useState, useEffect, useRef } from 'react'
import type { ProblemWithRating } from '@/lib/types'

interface Props {
  problem:     ProblemWithRating | null
  accessToken: string | null
  onClose:     () => void
  onPosted:    (id: string) => void
}

export function PostModal({ problem, accessToken, onClose, onPosted }: Props) {
  const [posting,    setPosting]    = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [tweetUrl,   setTweetUrl]   = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [rendering,  setRendering]  = useState(false)
  const prevObjUrl = useRef<string | null>(null)

  // モーダルが開くたびにプレビュー画像をレンダリング
  useEffect(() => {
    // 前回のオブジェクト URL を解放
    if (prevObjUrl.current) {
      URL.revokeObjectURL(prevObjUrl.current)
      prevObjUrl.current = null
    }
    setPreviewUrl(null)
    setPreviewError(null)
    setError(null)
    setTweetUrl(null)

    if (!problem) return

    setRendering(true)
    fetch('/api/render', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        statement: problem.statement,
        answer:    problem.answer ?? '',
        topic:     problem.topic_a,
        score:     problem.total ?? 0,
      }),
    })
      .then(async res => {
        if (!res.ok) {
          const data = await res.json().catch(() => null)
          const detail = data?.stderr || data?.error || 'render failed'
          throw new Error(detail)
        }
        return res.blob()
      })
      .then(blob => {
        const url = URL.createObjectURL(blob)
        prevObjUrl.current = url
        setPreviewUrl(url)
      })
      .catch(e => setPreviewError(e instanceof Error ? e.message : String(e)))
      .finally(() => setRendering(false))
  }, [problem])

  // アンマウント時に解放
  useEffect(() => () => {
    if (prevObjUrl.current) URL.revokeObjectURL(prevObjUrl.current)
  }, [])

  const handlePost = async () => {
    if (!problem) return
    setPosting(true); setError(null); setTweetUrl(null)

    const res  = await fetch('/api/post', {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body:    JSON.stringify({
        problem_id: problem.id,
        statement:  problem.statement,
        answer:     problem.answer  ?? '',
        topic:      problem.topic_a,
        score:      problem.total   ?? 0,
      }),
    })
    const data = await res.json()
    setPosting(false)

    if (data.ok) {
      setTweetUrl(data.url ?? null)
      if (data.renderWarning) setPreviewError(data.renderWarning)
      onPosted(problem.id)
      setTimeout(onClose, 1800)
    } else {
      setError(data.error ?? '投稿に失敗しました')
    }
  }

  return (
    <AnimatePresence>
      {problem && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1,    opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 400 }}
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
          >
            <div className="glass rounded-2xl p-6 w-full max-w-xl space-y-4">

              {/* Header */}
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-white/30 uppercase tracking-widest">
                  𝕏 投稿プレビュー
                </span>
                <button onClick={onClose} className="text-white/30 hover:text-white/70 text-lg">✕</button>
              </div>

              {/* Image preview */}
              <div className="rounded-xl overflow-hidden bg-black/40 border border-white/8"
                   style={{ aspectRatio: '4/5' }}>
                {rendering ? (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-white/30 text-[13px]">
                    <div className="w-6 h-6 border-2 border-apple-blue border-t-transparent rounded-full animate-spin" />
                    <span>画像をレンダリング中…</span>
                  </div>
                ) : previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt="card preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-white/25 text-[13px] px-8 text-center">
                    <span>プレビューを生成できませんでした</span>
                    <span className="text-[11px] text-white/18">画像なし投稿に切り替えられます</span>
                  </div>
                )}
              </div>

              {/* Char hint */}
              <p className="text-[11px] text-white/25">
                {previewUrl
                  ? '✦ 問題文と解答を画像として添付します。投稿本文は短い案内文だけにします。'
                  : '✦ プレビューが無い場合はテキストのみで投稿します。X APIの環境変数が必要です。'}
              </p>

              {/* Success */}
              {tweetUrl && (
                <div className="flex items-center gap-2 text-[12px] text-apple-green">
                  <span>✅ 投稿完了！</span>
                  <a href={tweetUrl} target="_blank" rel="noopener noreferrer"
                     className="underline hover:text-apple-green/80">
                    ポストを見る →
                  </a>
                </div>
              )}

              {previewError && (
                <p className="text-[11px] text-yellow-300/75 leading-relaxed">
                  プレビュー: {previewError}
                </p>
              )}

              {/* Error */}
              {error && <p className="text-[12px] text-apple-pink">{error}</p>}

              {/* Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={onClose}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 text-white/50
                             text-[13px] hover:bg-white/5 transition-colors"
                >
                  キャンセル
                </button>
                <button
                  onClick={handlePost}
                  disabled={posting || !!tweetUrl || rendering}
                  className="flex-1 py-2.5 rounded-xl bg-black border border-white/20 text-white
                             text-[13px] font-semibold hover:bg-white/5 transition-colors
                             disabled:opacity-40"
                >
                  {posting ? '投稿中…' : tweetUrl ? '✓ 投稿済' : rendering ? '準備中…' : previewUrl ? '𝕏 画像で投稿する' : '𝕏 テキストで投稿する'}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
