'use client'
import { useEffect, useState, useCallback } from 'react'

export interface Filters {
  topic: string | null
  status: string | null
  sort: 'total' | 'surprise' | 'topic'
  perPage: number
  showSol: boolean
}

interface Stats {
  total: number; selected: number; skipped: number
  posted: number; pending: number; generations: number
}

const TOPICS = [
  'analysis','algebra','geometry','number_theory','complex',
  'recurrence','polynomial','trigonometry','combinatorics',
  'inequality','probability','functional_eq','modular','matrix',
]
const TOPIC_JP: Record<string,string> = {
  analysis:'実解析', algebra:'代数', geometry:'幾何', number_theory:'整数論',
  complex:'複素数', recurrence:'漸化式', polynomial:'多項式',
  trigonometry:'三角関数', combinatorics:'組合せ', inequality:'不等式',
  probability:'確率', functional_eq:'関数方程式', modular:'合同算術', matrix:'行列',
}

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
  onReload?: () => void
}

export function Sidebar({ filters, onChange, onReload }: Props) {
  const [stats,    setStats]    = useState<Stats | null>(null)
  const [syncing,  setSyncing]  = useState(false)
  const [purging,  setPurging]  = useState(false)
  const [opResult, setOpResult] = useState<string | null>(null)

  const fetchStats = useCallback(() =>
    fetch('/api/stats').then(r => r.json()).then(setStats), [])

  useEffect(() => { fetchStats() }, [fetchStats])

  const handleSync = async () => {
    setSyncing(true); setOpResult(null)
    const res  = await fetch('/api/sync', { method: 'POST' })
    const data = await res.json()
    setSyncing(false)
    setOpResult(data.ok ? '✅ 同期完了' : `❌ ${data.error ?? '失敗'}`)
    fetchStats()
    onReload?.()
  }

  const handlePurge = async () => {
    if (!confirm('selected/posted 以外の問題を SQLite + Supabase から削除します。よろしいですか？')) return
    setPurging(true); setOpResult(null)
    const res  = await fetch('/api/purge', { method: 'POST' })
    const data = await res.json()
    setPurging(false)
    setOpResult(data.ok ? `✅ ${data.deleted} 件削除` : `❌ ${data.error ?? '失敗'}`)
    fetchStats()
    onReload?.()
  }

  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })

  return (
    <aside className="w-56 shrink-0 flex flex-col gap-4 py-6 px-4
                      border-r border-white/8 bg-black/20 overflow-y-auto">

      {/* Brand */}
      <div>
        <div className="text-[17px] font-bold tracking-tight text-white/90">
          ✦ Sakumon<span className="text-apple-blue"> Station</span>
        </div>
        <div className="text-[11px] text-white/35 mt-0.5">数学問題 キュレーション</div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-2">
          {[
            ['総数', stats.total],
            ['選択', stats.selected],
            ['スキップ', stats.skipped],
            ['X 投稿', stats.posted],
          ].map(([label, value]) => (
            <div key={label as string} className="glass rounded-xl p-2.5 text-center">
              <div className="text-lg font-semibold text-white/90">{value}</div>
              <div className="text-[10px] text-white/35">{label}</div>
            </div>
          ))}
        </div>
      )}
      {stats && (
        <div className="text-[11px] text-white/30">
          未判定 {stats.pending}件 · Gen {stats.generations}
        </div>
      )}

      <div className="border-t border-white/8" />

      {/* Topic filter */}
      <div>
        <Label>トピック</Label>
        <select
          value={filters.topic ?? ''}
          onChange={e => set({ topic: e.target.value || null })}
          className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2
                     text-[13px] text-white/80 outline-none mt-1.5"
        >
          <option value="">すべて</option>
          {TOPICS.map(t => (
            <option key={t} value={t}>{TOPIC_JP[t] ?? t}</option>
          ))}
        </select>
      </div>

      {/* Status filter */}
      <div>
        <Label>ステータス</Label>
        <div className="flex flex-col gap-1 mt-1.5">
          {[
            ['すべて', null],
            ['未判定', 'pending'],
            ['選択済', 'selected'],
            ['スキップ', 'rejected'],
          ].map(([label, val]) => (
            <button
              key={label as string}
              onClick={() => set({ status: val as string | null })}
              className={`text-left text-[12px] px-3 py-1.5 rounded-lg transition-colors
                ${filters.status === val
                  ? 'bg-apple-blue/20 text-apple-blue'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Sort */}
      <div>
        <Label>並び順</Label>
        <div className="flex flex-col gap-1 mt-1.5">
          {[
            ['スコア順', 'total'],
            ['驚き順', 'surprise'],
            ['トピック順', 'topic'],
          ].map(([label, val]) => (
            <button
              key={val}
              onClick={() => set({ sort: val as Filters['sort'] })}
              className={`text-left text-[12px] px-3 py-1.5 rounded-lg transition-colors
                ${filters.sort === val
                  ? 'bg-white/10 text-white/90'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Per page */}
      <div>
        <Label>表示数: {filters.perPage}</Label>
        <input
          type="range" min={4} max={20} step={4}
          value={filters.perPage}
          onChange={e => set({ perPage: Number(e.target.value) })}
          className="w-full mt-1.5 accent-apple-blue"
        />
      </div>

      {/* Show sol */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox" checked={filters.showSol}
          onChange={e => set({ showSol: e.target.checked })}
          className="accent-apple-blue"
        />
        <span className="text-[12px] text-white/50">解法を表示</span>
      </label>

      <div className="border-t border-white/8" />

      {/* Operations */}
      <div className="flex flex-col gap-2">
        <button
          onClick={onReload}
          className="text-[12px] text-white/40 hover:text-white/70 px-3 py-2
                     rounded-xl border border-white/10 hover:border-white/20 transition-colors"
        >
          🔄 表示を更新
        </button>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-[12px] text-apple-blue/70 hover:text-apple-blue px-3 py-2
                     rounded-xl border border-apple-blue/20 hover:border-apple-blue/40 transition-colors
                     disabled:opacity-40"
        >
          {syncing ? '同期中…' : '☁️ SQLite→Supabase 同期'}
        </button>
        <button
          onClick={handlePurge}
          disabled={purging}
          className="text-[12px] text-apple-pink/60 hover:text-apple-pink px-3 py-2
                     rounded-xl border border-apple-pink/20 hover:border-apple-pink/40 transition-colors
                     disabled:opacity-40"
        >
          {purging ? '削除中…' : '🗑️ 未選択を淘汰'}
        </button>
        <a
          href="/api/setup-gemini"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] text-white/25 hover:text-white/50 px-3 py-2
                     rounded-xl border border-white/8 hover:border-white/15 transition-colors text-center"
        >
          🔑 Gemini ログイン設定
        </a>
      </div>

      {opResult && (
        <div className="text-[11px] text-white/50 px-1">{opResult}</div>
      )}
    </aside>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold text-white/30 uppercase tracking-widest">
      {children}
    </div>
  )
}
