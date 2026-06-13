'use client'
import { useEffect, useState, useCallback } from 'react'
import { usePathname } from 'next/navigation'

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
  onClose?: () => void
}

export function Sidebar({ filters, onChange, onClose }: Props) {
  const pathname = usePathname()
  const [stats, setStats] = useState<Stats | null>(null)

  const fetchStats = useCallback(() =>
    fetch('/api/stats').then(r => r.json()).then(setStats), [])

  useEffect(() => { fetchStats() }, [fetchStats])

  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })

  return (
    <aside className="w-64 h-full shrink-0 flex flex-col gap-4 py-6 px-4
                      border-r border-white/8 bg-[#07060f]/95 overflow-y-auto">

      {/* Brand + close button */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[17px] font-bold tracking-tight text-white/90">
            ✦ Sakumon<span className="text-apple-blue"> Station</span>
          </div>
          <div className="text-[11px] text-white/35 mt-0.5">数学問題 キュレーション</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden text-white/30 hover:text-white/70 text-xl leading-none p-1"
          >✕</button>
        )}
      </div>

      {/* Page nav */}
      <nav className="flex flex-col gap-1">
        {[
          ['✦', 'キュレーション', '/'],
          ['📷', 'スキャン（写真→PDF）', '/scan'],
          ['🌳', 'アイデアツリー', '/ideas'],
        ].map(([icon, label, href]) => (
          <a
            key={href}
            href={href}
            className={`flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-lg transition-colors
              ${pathname === href
                ? 'bg-apple-blue/20 text-apple-blue'
                : 'text-white/40 hover:text-white/70 hover:bg-white/5'}`}
          >
            <span>{icon}</span>{label}
          </a>
        ))}
      </nav>

      <div className="border-t border-white/8" />

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
