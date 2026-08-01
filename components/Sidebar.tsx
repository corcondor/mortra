'use client'
import { useEffect, useState, useCallback } from 'react'
import { usePathname } from 'next/navigation'

export interface Filters {
  topic: string | null
  status: string | null
  sort: 'newest' | 'total' | 'surprise' | 'topic'
  perPage: number
  showSol: boolean
}

interface Stats {
  total: number
  selected: number
  skipped: number
  posted: number
  pending: number
  generations: number
}

const TOPICS = [
  'analysis', 'algebra', 'geometry', 'number_theory', 'complex',
  'recurrence', 'polynomial', 'trigonometry', 'combinatorics',
  'inequality', 'probability', 'functional_eq', 'modular', 'matrix',
]

const TOPIC_JP: Record<string, string> = {
  analysis: '実解析', algebra: '代数', geometry: '幾何', number_theory: '整数論',
  complex: '複素数', recurrence: '漸化式', polynomial: '多項式',
  trigonometry: '三角関数', combinatorics: '組合せ', inequality: '不等式',
  probability: '確率', functional_eq: '関数方程式', modular: '合同算術', matrix: '行列',
}

interface Props {
  filters: Filters
  onChange: (filters: Filters) => void
  onReload?: () => void
  onClose?: () => void
}

export function Sidebar({ filters, onChange, onReload, onClose }: Props) {
  const pathname = usePathname()
  const [stats, setStats] = useState<Stats | null>(null)

  const fetchStats = useCallback(() => {
    fetch('/api/stats')
      .then(response => response.json())
      .then(setStats)
      .catch(() => setStats(null))
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])

  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })
  const reload = () => {
    fetchStats()
    onReload?.()
  }

  return (
    <aside className="flex h-full w-[232px] shrink-0 flex-col overflow-y-auto border-r border-[#d8dee9] bg-white">
      <div className="flex h-16 items-center justify-between border-b border-[#e4e7ec] px-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[15px] font-bold text-[#14213d]">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-[#14213d] text-sm text-white">Σ</span>
            <span>作問ステーション</span>
          </div>
          <div className="ml-9 mt-0.5 text-[10px] text-[#667085]">MathOS 作問・検証</div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center text-lg text-[#667085] md:hidden"
            aria-label="メニューを閉じる"
          >
            ×
          </button>
        ) : null}
      </div>

      <div className="space-y-5 px-4 py-4">
        <nav className="space-y-1 border-b border-[#e4e7ec] pb-4" aria-label="ワークスペース">
          {[
            ['∑', 'キュレーション', '/'],
            ['▣', 'スキャン・PDF', '/scan'],
            ['⑂', 'アイデアツリー', '/ideas'],
            ['◈', '概念ツリー作問', '/tree'],
          ].map(([icon, label, href]) => {
            const active = pathname === href
            return (
              <a
                key={href}
                href={href}
                className={`flex h-9 items-center gap-2 rounded px-3 text-[12px] font-medium transition-colors ${
                  active
                    ? 'bg-[#eff6ff] text-[#175cd3]'
                    : 'text-[#475467] hover:bg-[#f8fafc] hover:text-[#14213d]'
                }`}
              >
                <span className="w-4 text-center" aria-hidden>{icon}</span>
                <span>{label}</span>
              </a>
            )
          })}
        </nav>

        <section aria-labelledby="summary-label">
          <div className="mb-2 flex items-center justify-between">
            <Label id="summary-label">サマリー</Label>
            <button
              type="button"
              onClick={reload}
              className="text-[11px] font-medium text-[#175cd3] hover:text-[#004eeb]"
            >
              更新
            </button>
          </div>
          <dl className="divide-y divide-[#eef0f4] border-y border-[#e4e7ec] text-[12px]">
            <Stat label="総問題数" value={stats?.total} />
            <Stat label="選択済み" value={stats?.selected} tone="blue" />
            <Stat label="未判定" value={stats?.pending} />
            <Stat label="投稿済み" value={stats?.posted} tone="green" />
            <Stat label="除外" value={stats?.skipped} tone="red" />
          </dl>
          {stats ? (
            <p className="mt-2 text-[10px] text-[#98a2b3]">生成世代 Gen {stats.generations}</p>
          ) : null}
        </section>

        <section>
          <Label>領域</Label>
          <select
            value={filters.topic ?? ''}
            onChange={event => set({ topic: event.target.value || null })}
            className="mt-2 h-9 w-full rounded border border-[#cfd6e1] bg-white px-2.5 text-[12px] text-[#344054] outline-none focus:border-[#84adff]"
          >
            <option value="">すべての領域</option>
            {TOPICS.map(topic => (
              <option key={topic} value={topic}>{TOPIC_JP[topic] ?? topic}</option>
            ))}
          </select>
        </section>

        <section>
          <Label>ステータス</Label>
          <div className="mt-2 overflow-hidden rounded border border-[#d8dee9]">
            {([
              ['すべて', null],
              ['未判定', 'pending'],
              ['選択済み', 'selected'],
              ['除外', 'rejected'],
            ] as [string, string | null][]).map(([label, value]) => {
              const active = filters.status === value
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => set({ status: value })}
                  className={`flex h-9 w-full items-center justify-between border-b border-[#eef0f4] px-3 text-left text-[12px] last:border-0 ${
                    active
                      ? 'bg-[#eff6ff] font-semibold text-[#175cd3]'
                      : 'bg-white text-[#475467] hover:bg-[#f8fafc]'
                  }`}
                >
                  <span>{label}</span>
                  <span aria-hidden>{active ? '●' : '○'}</span>
                </button>
              )
            })}
          </div>
        </section>

        <section>
          <Label>並び順</Label>
          <select
            value={filters.sort}
            onChange={event => set({ sort: event.target.value as Filters['sort'] })}
            className="mt-2 h-9 w-full rounded border border-[#cfd6e1] bg-white px-2.5 text-[12px] text-[#344054] outline-none focus:border-[#84adff]"
          >
            <option value="newest">新着順</option>
            <option value="total">品質スコア順</option>
            <option value="surprise">新規性順</option>
            <option value="topic">トピック順</option>
          </select>
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <Label>表示件数</Label>
            <span className="text-[11px] font-semibold tabular-nums text-[#344054]">{filters.perPage}件</span>
          </div>
          <input
            type="range"
            min={4}
            max={20}
            step={4}
            value={filters.perPage}
            onChange={event => set({ perPage: Number(event.target.value) })}
            className="h-1 w-full accent-[#175cd3]"
          />
        </section>

        <label className="flex cursor-pointer items-center justify-between border-t border-[#e4e7ec] pt-4">
          <span className="text-[12px] font-medium text-[#344054]">解答・解説を表示</span>
          <input
            type="checkbox"
            checked={filters.showSol}
            onChange={event => set({ showSol: event.target.checked })}
            className="h-4 w-4 accent-[#175cd3]"
          />
        </label>
      </div>
    </aside>
  )
}

function Label({ children, id }: { children: React.ReactNode; id?: string }) {
  return (
    <h2 id={id} className="text-[10px] font-bold uppercase text-[#667085]">
      {children}
    </h2>
  )
}

function Stat({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value?: number
  tone?: 'default' | 'blue' | 'green' | 'red'
}) {
  const toneClass = {
    default: 'text-[#344054]',
    blue: 'text-[#175cd3]',
    green: 'text-[#067647]',
    red: 'text-[#b42318]',
  }[tone]

  return (
    <div className="flex items-center justify-between py-2">
      <dt className="text-[#667085]">{label}</dt>
      <dd className={`font-semibold tabular-nums ${toneClass}`}>{value ?? '—'}</dd>
    </div>
  )
}
