'use client'
import { useState, useRef, useEffect } from 'react'
import type { ProblemWithRating } from '@/lib/types'
import { MathText } from './MathText'

const TOPIC_JP: Record<string,string> = {
  analysis:'実解析', algebra:'代数', geometry:'幾何', number_theory:'整数論',
  complex:'複素数', recurrence:'漸化式', polynomial:'多項式',
  trigonometry:'三角関数', combinatorics:'組合せ', inequality:'不等式',
  probability:'確率', functional_eq:'関数方程式', modular:'合同算術', matrix:'行列',
}

// ボットカーソルのステップ定義
const BOT_STEPS: Record<string, { emoji: string; label: string; color: string }> = {
  queued:     { emoji: '🕐', label: 'キュー待ち...',         color: 'text-white/50' },
  start:      { emoji: '🚀', label: '起動中...',             color: 'text-white/60' },
  opening:    { emoji: '🌐', label: 'Chrome/Gemini 接続中',  color: 'text-apple-blue' },
  typing:     { emoji: '⌨️', label: 'プロンプト入力中',       color: 'text-yellow-400' },
  waiting:    { emoji: '⏳', label: 'Gemini 応答待ち',        color: 'text-orange-400' },
  extracting: { emoji: '📋', label: '回答を抽出中',           color: 'text-purple-400' },
  saving:     { emoji: '💾', label: 'DB に保存中',            color: 'text-apple-green' },
  syncing:    { emoji: '☁️', label: 'Supabase に同期中',      color: 'text-apple-blue' },
  working:    { emoji: '⚙️', label: '処理中...',              color: 'text-white/50' },
  complete:   { emoji: '✅', label: '完了！',                 color: 'text-apple-green' },
  error:      { emoji: '❌', label: 'エラー',                 color: 'text-apple-pink' },
}

interface Props {
  selectedProblems: ProblemWithRating[]
  onStatusChange:   (id: string, status: string) => void
  onPostClick:      (p: ProblemWithRating) => void
}

export function GenerationPanel({ selectedProblems, onStatusChange, onPostClick }: Props) {
  const [generating,   setGenerating]   = useState(false)
  const [currentStep,  setCurrentStep]  = useState('start')
  const [logs,         setLogs]         = useState<string[]>([])
  const [genDone,      setGenDone]      = useState<{ ok: boolean } | null>(null)
  const [fusionCount,  setFusionCount]  = useState(3)
  const [batchCount,   setBatchCount]   = useState(4)
  const [chosenIds,    setChosenIds]    = useState<string[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)

  // ログ末尾に自動スクロール
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // ── SSE ストリーミング生成 ──────────────────────────────────────────
  const run = async (parents: ProblemWithRating[], mode: string, count: number) => {
    setGenerating(true); setLogs([]); setGenDone(null); setCurrentStep('start')

    const parentData = parents.map(p => ({
      id: p.id, topic_a: p.topic_a, topic_b: p.topic_b,
      statement: p.statement, answer: p.answer,
      inspiration: p.inspiration, total: p.total, solution: p.solution,
    }))

    const res = await fetch('/api/generate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ parents: parentData, mode, count }),
    })

    if (!res.body) { setGenerating(false); return }

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let   buffer  = ''

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue
        try {
          const ev = JSON.parse(part.slice(6))
          if (ev.type === 'status') setCurrentStep(ev.step)
          if (ev.type === 'log')    setLogs(prev => [...prev, ev.message])
          if (ev.type === 'done')   { setGenDone({ ok: ev.ok }); setGenerating(false) }
        } catch { /* ignore parse error */ }
      }
    }
    setGenerating(false)
  }

  const toggleChosen = (id: string) =>
    setChosenIds(ids => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])

  const chosen       = selectedProblems.filter(p => chosenIds.includes(p.id))
  const fusionTarget = chosen.length >= 2 ? chosen : selectedProblems
  const fusionDisabled = generating || (chosen.length > 0 && chosen.length < 2)

  const deselect = async (id: string) => {
    await fetch('/api/status', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ problem_id: id, status: 'pending' }),
    })
    onStatusChange(id, 'pending')
  }

  if (selectedProblems.length === 0) {
    return (
      <div className="glass rounded-2xl p-6 text-center text-white/30 text-sm">
        問題一覧タブで ⭐ 選択 を押すと、ここに表示されます
      </div>
    )
  }

  const stepInfo = BOT_STEPS[currentStep] ?? BOT_STEPS.working

  return (
    <div className="space-y-4">

      {/* ── Sticky 生成コントロール ───────────────────────────────────── */}
      <div className="sticky top-0 z-20 backdrop-blur-2xl bg-black/50
                      border border-white/12 rounded-2xl p-4 shadow-xl space-y-3">
        <div className="text-[11px] font-semibold text-white/30 uppercase tracking-widest">
          生成コントロール
        </div>

        {/* 融合生成 */}
        <div className="flex items-center gap-2.5">
          <div className="shrink-0 w-24">
            <div className="text-[11px] text-white/60 font-medium">融合生成</div>
            <div className="text-[10px] text-white/30">
              {chosen.length >= 2 ? `${chosen.length} 問選択` : `全 ${selectedProblems.length} 問`}
            </div>
          </div>
          <input type="range" min={1} max={6} value={fusionCount}
            onChange={e => setFusionCount(+e.target.value)}
            className="flex-1 accent-apple-blue h-1" />
          <span className="text-[11px] text-white/40 tabular-nums w-5 text-right">{fusionCount}</span>
          <button
            onClick={() => run(fusionTarget, 'fusion', fusionCount)}
            disabled={fusionDisabled}
            className="shrink-0 px-4 py-1.5 bg-apple-blue text-white text-[12px] font-semibold
                       rounded-xl hover:bg-apple-blue/80 transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >融合</button>
        </div>
        {chosen.length === 1 && (
          <p className="text-[10px] text-apple-pink/70 pl-24">2 問以上チェックしてください</p>
        )}

        {/* 一括類題 */}
        <div className="flex items-center gap-2.5">
          <div className="shrink-0 w-24">
            <div className="text-[11px] text-white/60 font-medium">一括類題</div>
            <div className="text-[10px] text-white/30">全 {selectedProblems.length} 問</div>
          </div>
          <input type="range" min={2} max={10} value={batchCount}
            onChange={e => setBatchCount(+e.target.value)}
            className="flex-1 accent-apple-blue h-1" />
          <span className="text-[11px] text-white/40 tabular-nums w-5 text-right">{batchCount}</span>
          <button
            onClick={() => run(selectedProblems, 'similar', batchCount)}
            disabled={generating}
            className="shrink-0 px-4 py-1.5 bg-white/10 text-white/80 text-[12px] font-semibold
                       rounded-xl border border-white/15 hover:bg-white/15 transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >類題</button>
        </div>

        {/* 生成完了メッセージ */}
        {genDone && !generating && (
          <div className={`text-[11px] mt-1 ${genDone.ok ? 'text-apple-green' : 'text-apple-pink'}`}>
            {genDone.ok ? '✅ 生成・同期完了！ページを再読み込みすると新問題が表示されます。' : '❌ エラーが発生しました。ログを確認してください。'}
          </div>
        )}
      </div>

      {/* ── 選択済み問題リスト ─────────────────────────────────────────── */}
      {selectedProblems.map(p => (
        <div key={p.id} className="glass rounded-2xl p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-[10px] text-white/40">{TOPIC_JP[p.topic_a] ?? p.topic_a}</span>
                {p.topic_b && <span className="text-[10px] text-white/25">× {TOPIC_JP[p.topic_b] ?? p.topic_b}</span>}
                <span className="text-[10px] text-white/25">Gen {p.generation}</span>
                <span className="text-[10px] text-apple-blue/60">{(p.total||0).toFixed(1)}</span>
              </div>
              <div className="text-[13px] text-white/70 leading-relaxed">
                <MathText text={p.statement} />
              </div>
              {p.answer && (
                <div className="text-[12px] text-apple-green/80 mt-1.5 leading-relaxed">
                  <MathText text={p.answer} />
                </div>
              )}
            </div>

            {/* 個別アクション */}
            <div className="flex flex-col gap-1.5 shrink-0">
              <button onClick={() => run([p], 'similar', 3)} disabled={generating}
                className="text-[11px] px-2.5 py-1.5 rounded-xl border border-white/10
                           text-white/50 hover:border-apple-blue/40 hover:text-apple-blue transition-all
                           disabled:opacity-40">🔁 類題</button>
              <button onClick={() => run([p], 'expand', 2)} disabled={generating}
                className="text-[11px] px-2.5 py-1.5 rounded-xl border border-white/10
                           text-white/50 hover:border-purple-400/40 hover:text-purple-400 transition-all
                           disabled:opacity-40">📐 高次元</button>
              <button
                onClick={() => !p.rating?.x_posted && onPostClick(p)}
                disabled={!!p.rating?.x_posted}
                className={`text-[11px] px-2.5 py-1.5 rounded-xl border transition-all disabled:opacity-40
                  ${p.rating?.x_posted
                    ? 'border-apple-blue/30 text-apple-blue'
                    : 'border-white/10 text-white/50 hover:border-apple-blue/40 hover:text-apple-blue'}`}
              >{p.rating?.x_posted ? '✓ 済' : '𝕏 投稿'}</button>
              <button onClick={() => deselect(p.id)}
                className="text-[10px] px-2.5 py-1 rounded-xl border border-white/8
                           text-white/25 hover:text-white/50 transition-colors">解除</button>
            </div>
          </div>

          {/* 融合チェック */}
          <label className="flex items-center gap-2 mt-3 cursor-pointer select-none">
            <input type="checkbox" checked={chosenIds.includes(p.id)}
              onChange={() => toggleChosen(p.id)} className="accent-apple-blue" />
            <span className="text-[11px] text-white/40">融合生成に含める</span>
          </label>
        </div>
      ))}

      {/* ── ボットカーソルパネル（生成中は常時表示） ──────────────────── */}
      {(generating || (genDone !== null)) && (
        <div className={`fixed bottom-6 right-6 z-50 w-72 rounded-2xl p-4 shadow-2xl
                         border transition-all duration-300
                         ${generating
                           ? 'backdrop-blur-2xl bg-black/70 border-white/15'
                           : genDone?.ok
                             ? 'bg-apple-green/10 border-apple-green/30'
                             : 'bg-apple-pink/10 border-apple-pink/30'}`}>

          {/* ヘッダー */}
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-2xl ${generating && currentStep === 'waiting' ? 'animate-spin' : 'animate-bounce'}`}>
              {stepInfo.emoji}
            </span>
            <div className="flex-1">
              <div className={`text-[13px] font-semibold ${stepInfo.color}`}>
                {stepInfo.label}
              </div>
              {generating && (
                <div className="text-[10px] text-white/30">最大15分かかります</div>
              )}
            </div>
            {generating && (
              <div className="flex gap-0.5">
                {[0,1,2].map(i => (
                  <div key={i}
                    className="w-1.5 h-1.5 rounded-full bg-apple-blue animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* ライブログ（最新 6 行） */}
          {logs.length > 0 && (
            <div className="max-h-28 overflow-y-auto space-y-0.5 border-t border-white/8 pt-2 mt-1">
              {logs.slice(-6).map((line, i) => (
                <div key={i}
                  className={`text-[10px] leading-snug font-mono
                    ${line.startsWith('E') || line.includes('ERROR')
                      ? 'text-apple-pink/70'
                      : 'text-white/35'}`}
                >
                  {line.slice(0, 72)}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
