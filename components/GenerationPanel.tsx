'use client'
import { useState, useRef, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'
import type { ProblemWithRating } from '@/lib/types'
import { MathText } from './MathText'
import { UpgradeModal } from './UpgradeModal'

const TOPIC_JP: Record<string,string> = {
  analysis:'実解析', algebra:'代数', geometry:'幾何', number_theory:'整数論',
  complex:'複素数', recurrence:'漸化式', polynomial:'多項式',
  trigonometry:'三角関数', combinatorics:'組合せ', inequality:'不等式',
  probability:'確率', functional_eq:'関数方程式', modular:'合同算術', matrix:'行列',
}

interface Props {
  selectedProblems: ProblemWithRating[]
  accessToken:      string | null
  isAdmin:          boolean
  userId:           string | null
  onStatusChange:   (id: string, status: string) => void
  onPostClick:      (p: ProblemWithRating) => void
}

// Supabase クライアント（Realtime用）
function getSupabaseClient() {
  const url  = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  return createClient(url, anon)
}

// ── ログからフェーズ・進捗を解析 ─────────────────────────────────────────────
interface Progress {
  current: number
  total: number
  phase: 'analyzing' | 'generating' | 'verifying' | 'saving' | 'purging' | 'done'
  label: string
}

function parseProgress(logs: string[]): Progress | null {
  for (let i = logs.length - 1; i >= 0; i--) {
    const line = logs[i]

    // [生成 X/N], [検証 X/N], [保存 X/N], [完了 X/N]
    const m = line.match(/\[(?:生成|検証|保存|完了)\s*(\d+)\/(\d+)\]/)
    if (m) {
      const current = parseInt(m[1])
      const total   = parseInt(m[2])
      const phase = line.includes('[検証') ? 'verifying'
        : line.includes('[保存')           ? 'saving'
        : line.includes('[完了')           ? 'done'
        : 'generating'
      // 完了は current 問分が終わった → 0-indexed で current が完了数
      const progress = phase === 'done' ? current / total : (current - 1) / total
      return { current, total, phase, label: `問題 ${current}/${total}` }
      // suppress unused var
      void progress
    }

    // 分析フェーズ
    if (line.includes('[分析]')) {
      return { current: 0, total: 1, phase: 'analyzing', label: '分析中' }
    }

    // 淘汰フェーズ
    if (line.includes('[淘汰]')) {
      return { current: 1, total: 1, phase: 'purging', label: '整理中' }
    }
  }
  return null
}

/** ログ行のカラー分類 */
function logLineColor(line: string): string {
  if (line.includes('❌') || line.includes('FAIL') || line.includes('エラー') || line.includes('失敗'))
    return 'text-red-400/80'
  if (line.includes('⚠') || line.includes('warn') || line.includes('スキップ'))
    return 'text-yellow-400/70'
  if (line.includes('✅') || line.includes('✓') || line.includes('完了') || line.includes('PASS'))
    return 'text-emerald-400/80'
  if (line.includes('🎯') || line.includes('[生成'))
    return 'text-blue-300/70'
  if (line.includes('🔍') || line.includes('[検証') || line.includes('[分析'))
    return 'text-purple-300/70'
  if (line.includes('💾') || line.includes('[保存'))
    return 'text-cyan-300/70'
  if (line.includes('🔧'))
    return 'text-orange-300/70'
  return 'text-white/40'
}

/** フェーズ → アイコン */
const PHASE_INFO: Record<string, { emoji: string; label: string; color: string }> = {
  analyzing:  { emoji: '🔍', label: '構造分析中',       color: 'text-purple-400' },
  generating: { emoji: '⏳', label: 'DeepSeek 生成中',  color: 'text-blue-400' },
  verifying:  { emoji: '🔬', label: '数学的検証中',     color: 'text-yellow-400' },
  saving:     { emoji: '💾', label: 'Supabase 保存中',  color: 'text-cyan-400' },
  purging:    { emoji: '🗑️', label: '未選択を整理中',   color: 'text-pink-400' },
  done:       { emoji: '✅', label: '完了！',            color: 'text-emerald-400' },
  queued:     { emoji: '🕐', label: 'キュー待ち...',    color: 'text-white/50' },
  start:      { emoji: '🚀', label: 'Worker 起動中',    color: 'text-blue-400' },
  error:      { emoji: '❌', label: 'エラー',            color: 'text-red-400' },
}

export function GenerationPanel({ selectedProblems, accessToken, isAdmin, userId, onStatusChange, onPostClick }: Props) {
  const [generating,    setGenerating]    = useState(false)
  const [uiPhase,       setUiPhase]       = useState<string>('start')
  const [logs,          setLogs]          = useState<string[]>([])
  const [genDone,       setGenDone]       = useState<{ ok: boolean; message: string } | null>(null)
  const [fusionCount,   setFusionCount]   = useState(3)
  const [batchCount,    setBatchCount]    = useState(4)
  const [chosenIds,     setChosenIds]     = useState<string[]>([])
  const [showUpgrade,   setShowUpgrade]   = useState(false)
  const [upgradeUsed,   setUpgradeUsed]   = useState(0)
  const logEndRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const channelRef = useRef<any>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // ── 生成リクエスト ──────────────────────────────────────────────────────
  const run = async (parents: ProblemWithRating[], mode: string, count: number) => {
    setGenerating(true); setLogs([]); setGenDone(null); setUiPhase('queued')

    const parentData = parents.map(p => ({
      id: p.id, topic_a: p.topic_a, topic_b: p.topic_b,
      statement: p.statement, answer: p.answer,
      inspiration: p.inspiration, total: p.total, solution: p.solution,
    }))

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const enqueueUrl  = supabaseUrl
      ? `${supabaseUrl}/functions/v1/enqueue-generation`
      : '/api/generate'   // フォールバック（旧SSE方式）

    if (enqueueUrl === '/api/generate') {
      await runLegacySSE(enqueueUrl, parentData, mode, count)
      return
    }

    setUiPhase('start')

    let jobId: string | null = null
    try {
      const res = await fetch(enqueueUrl, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ parents: parentData, mode, count }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => null)
        const message = data?.error ?? `エンキューエラー: ${res.status}`
        if (res.status === 402) {
          setUpgradeUsed(data?.used ?? 0)
          setShowUpgrade(true)
          setGenerating(false)
          return
        }
        setLogs(prev => [...prev, message])
        setUiPhase('error')
        setGenDone({ ok: false, message })
        setGenerating(false)
        return
      }

      const { job_id } = await res.json()
      jobId = job_id as string
      setLogs([`🚀 ジョブ受付: ${jobId}`])
      setUiPhase('generating')
    } catch (e) {
      const message = `エンキュー失敗: ${e}`
      setLogs(prev => [...prev, message])
      setUiPhase('error')
      setGenDone({ ok: false, message })
      setGenerating(false)
      return
    }

    if (!jobId) return

    // ── Supabase Realtime で generation_jobs を監視 ──────────────────────
    const sb = getSupabaseClient()

    if (channelRef.current) {
      await sb.removeChannel(channelRef.current)
      channelRef.current = null
    }

    const channel = sb
      .channel(`job-${jobId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'generation_jobs', filter: `id=eq.${jobId}` },
        (payload) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const job = payload.new as any

          // ── ライブログ更新 ──────────────────────────────────────────────
          const jobLogs: { level: string; message: string }[] = job.logs ?? []
          if (jobLogs.length > 0) {
            const messages = jobLogs.map((l: { level: string; message: string }) => l.message)
            setLogs(messages)

            // フェーズ推定（最後のログから）
            const last = messages[messages.length - 1] ?? ''
            if (last.includes('[分析]'))      setUiPhase('analyzing')
            else if (last.includes('[生成'))  setUiPhase('generating')
            else if (last.includes('[検証'))  setUiPhase('verifying')
            else if (last.includes('[保存'))  setUiPhase('saving')
            else if (last.includes('[淘汰]')) setUiPhase('purging')
          }

          // ── 完了/失敗 ──────────────────────────────────────────────────
          if (job.status === 'done' || job.status === 'failed') {
            const ok = job.status === 'done' && job.result?.ok === true
            const generated = job.result?.generated?.length ?? 0
            const total     = job.result?.total ?? count
            const message   = ok
              ? `✅ 完了: ${generated}/${total} 問生成。表示を更新してください。`
              : (job.error ?? `❌ 失敗: 0/${total} 問生成`)

            setUiPhase(ok ? 'done' : 'error')
            setLogs(prev => [...prev, message])
            setGenDone({ ok, message })
            setGenerating(false)

            sb.removeChannel(channel)
            channelRef.current = null
          }
        },
      )
      .subscribe()

    channelRef.current = channel

    // ── ポーリングフォールバック（Realtimeが届かない場合の保険） ─────────
    // Realtimeが有効でも無効でも、5秒ごとにAPIで状態を確認する
    let pollDone = false
    const pollInterval = setInterval(async () => {
      if (pollDone) return
      try {
        const res = await fetch(`/api/job-status?job_id=${jobId}`)
        if (!res.ok) return
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const job = await res.json() as any

        // ログ更新（Realtimeより遅れて来た場合もここで補完）
        const jobLogs: { level: string; message: string }[] = job.logs ?? []
        if (jobLogs.length > 0) {
          const messages = jobLogs.map((l: { level: string; message: string }) => l.message)
          setLogs(messages)
          const last = messages[messages.length - 1] ?? ''
          if (last.includes('[分析]'))      setUiPhase('analyzing')
          else if (last.includes('[生成'))  setUiPhase('generating')
          else if (last.includes('[検証'))  setUiPhase('verifying')
          else if (last.includes('[保存'))  setUiPhase('saving')
          else if (last.includes('[淘汰]')) setUiPhase('purging')
        }

        // 完了/失敗の検出
        if (job.status === 'done' || job.status === 'failed') {
          pollDone = true
          clearInterval(pollInterval)
          const ok      = job.status === 'done' && job.result?.ok === true
          const generated = job.result?.generated?.length ?? 0
          const total     = job.result?.total ?? count
          const message   = ok
            ? `✅ 完了: ${generated}/${total} 問生成。表示を更新してください。`
            : generated === 0
              ? `❌ 0/${total} 問生成 — 全問が検証でスキップされました`
              : (job.error ?? `❌ 失敗: ${generated}/${total} 問生成`)

          setUiPhase(ok ? 'done' : 'error')
          setLogs(prev => {
            const last = prev[prev.length - 1]
            return last === message ? prev : [...prev, message]
          })
          setGenDone({ ok, message })
          setGenerating(false)
          await sb.removeChannel(channel)
          channelRef.current = null
        }
      } catch { /* ignore polling errors */ }
    }, 5000)

    // ── タイムアウトフォールバック（15分） ───────────────────────────────
    setTimeout(() => {
      if (pollDone) return
      pollDone = true
      clearInterval(pollInterval)
      const message = '⏱️ タイムアウト（Workerの状態を確認してください）'
      setUiPhase('error')
      setGenDone({ ok: false, message })
      setLogs(prev => [...prev, message])
      setGenerating(false)
      sb.removeChannel(channel)
      channelRef.current = null
    }, 15 * 60 * 1000)
  }

  // ── 旧SSEフォールバック ────────────────────────────────────────────────
  const runLegacySSE = async (
    url: string,
    parentData: unknown[],
    mode: string,
    count: number,
  ) => {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ parents: parentData, mode, count }),
    })

    if (!res.ok) {
      const data = await res.json().catch(() => null)
      const message = data?.error ?? `生成APIエラー: ${res.status}`
      if (res.status === 402) { setUpgradeUsed(data?.used ?? 0); setShowUpgrade(true); setGenerating(false); return }
      setLogs(prev => [...prev, message]); setUiPhase('error'); setGenDone({ ok: false, message }); setGenerating(false); return
    }
    if (!res.body) {
      const message = '生成APIのストリームが空です'
      setLogs(prev => [...prev, message]); setUiPhase('error'); setGenDone({ ok: false, message }); setGenerating(false); return
    }

    const reader = res.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let doneSeen = false
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n'); buffer = parts.pop() ?? ''
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue
        try {
          const ev = JSON.parse(part.slice(6)); const message = String(ev.message ?? ev.msg ?? '')
          if (ev.type === 'status') { setUiPhase(ev.step ?? 'generating'); if (message) setLogs(prev => [...prev, message]) }
          if (ev.type === 'log' && message) setLogs(prev => [...prev, message])
          if (ev.type === 'error') { doneSeen = true; setUiPhase('error'); setLogs(prev => [...prev, message || '生成エラー']); setGenDone({ ok: false, message: message || '生成エラー' }); setGenerating(false) }
          if (ev.type === 'done') { doneSeen = true; const ok = ev.ok === true; const dm = message || (ok ? '生成完了' : '生成に失敗しました'); setUiPhase(ok ? 'done' : 'error'); setLogs(prev => [...prev, dm]); setGenDone({ ok, message: dm }); setGenerating(false) }
        } catch { /* ignore */ }
      }
    }
    if (!doneSeen) { const msg = '生成ストリームが完了イベントなしで終了しました'; setUiPhase('error'); setGenDone({ ok: false, message: msg }); setLogs(prev => [...prev, msg]) }
    setGenerating(false)
  }

  useEffect(() => {
    return () => {
      if (channelRef.current) {
        const sb = getSupabaseClient()
        sb.removeChannel(channelRef.current)
      }
    }
  }, [])

  const toggleChosen = (id: string) =>
    setChosenIds(ids => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])

  const chosen       = selectedProblems.filter(p => chosenIds.includes(p.id))
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
      <div className="glass rounded-2xl p-6 text-center text-white/30 text-sm">
        問題一覧タブで ⭐ 選択 を押すと、ここに表示されます
      </div>
    )
  }

  const FREE_LIMIT = 10

  // ── 進捗パース ──────────────────────────────────────────────────────────
  const progress = parseProgress(logs)
  const phaseInfo = PHASE_INFO[uiPhase] ?? PHASE_INFO.start

  // 進捗バーの割合計算
  let progressPct = 0
  if (progress) {
    const completedCount = logs.filter(l => l.includes('[完了')).length
    const totalCount     = progress.total
    if (totalCount > 0) progressPct = Math.min(100, Math.round((completedCount / totalCount) * 100))
  }

  return (
    <div className="space-y-4">
      {showUpgrade && (
        <UpgradeModal accessToken={accessToken} used={upgradeUsed} limit={FREE_LIMIT} onClose={() => setShowUpgrade(false)} />
      )}

      {/* ── Sticky 生成コントロール ─────────────────────────────────────── */}
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

        {/* 完了メッセージ */}
        {genDone && !generating && (
          <div className={`text-[11px] mt-1 ${genDone.ok ? 'text-apple-green' : 'text-apple-pink'}`}>
            {genDone.message}
          </div>
        )}
      </div>

      {/* ── 選択済み問題リスト ──────────────────────────────────────────── */}
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

          <label className="flex items-center gap-2 mt-3 cursor-pointer select-none">
            <input type="checkbox" checked={chosenIds.includes(p.id)}
              onChange={() => toggleChosen(p.id)} className="accent-apple-blue" />
            <span className="text-[11px] text-white/40">融合生成に含める</span>
          </label>
        </div>
      ))}

      {/* ── フローティング進捗パネル ────────────────────────────────────── */}
      {(generating || genDone !== null) && (
        <div className={`fixed bottom-6 right-6 z-50 w-80 rounded-2xl p-4 shadow-2xl
                         border transition-all duration-300
                         ${generating
                           ? 'backdrop-blur-2xl bg-black/75 border-white/15'
                           : genDone?.ok
                             ? 'bg-emerald-950/80 border-emerald-500/30 backdrop-blur-xl'
                             : 'bg-red-950/80 border-red-500/30 backdrop-blur-xl'}`}>

          {/* ヘッダー：フェーズ + アニメーション */}
          <div className="flex items-center gap-3 mb-2.5">
            <span className={`text-xl ${generating ? 'animate-bounce' : ''}`}>{phaseInfo.emoji}</span>
            <div className="flex-1 min-w-0">
              <div className={`text-[13px] font-semibold ${phaseInfo.color}`}>{phaseInfo.label}</div>
              {/* 問題番号表示 */}
              {progress && generating && (
                <div className="text-[10px] text-white/40 tabular-nums">
                  問題 {progress.current}/{progress.total}
                  {uiPhase === 'verifying' && ' — 検証中'}
                  {uiPhase === 'saving'    && ' — 保存中'}
                </div>
              )}
              {!progress && generating && (
                <div className="text-[10px] text-white/30">Worker 処理中...</div>
              )}
            </div>
            {generating && (
              <div className="flex gap-0.5 shrink-0">
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-apple-blue animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            )}
          </div>

          {/* プログレスバー */}
          {generating && progress && progress.total > 1 && (
            <div className="mb-2.5">
              <div className="flex justify-between text-[9px] text-white/25 mb-1">
                <span>
                  {logs.filter(l => l.includes('[完了')).length}/{progress.total} 問完了
                </span>
                <span>{progressPct}%</span>
              </div>
              <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all duration-700"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}

          {/* ログ表示 */}
          {logs.length > 0 && (
            <div className="max-h-36 overflow-y-auto space-y-0.5 border-t border-white/8 pt-2">
              {logs.slice(-10).map((line, i) => (
                <div key={i} className={`text-[10px] leading-snug font-mono ${logLineColor(line)}`}>
                  {line.length > 76 ? line.slice(0, 73) + '...' : line}
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
