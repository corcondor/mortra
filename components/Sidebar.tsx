'use client'
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
  stats: Stats
  onChange: (filters: Filters) => void
  onReload?: () => void
  onClose?: () => void
}

export function Sidebar({ filters, stats, onChange, onReload, onClose }: Props) {
  const pathname = usePathname()

  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })
  const reload = () => {
    onReload?.()
  }

  return (
    <aside className="flex h-full w-[232px] shrink-0 flex-col overflow-y-auto border-r border-zinc-800 bg-[#111113]">
      <div className="flex h-16 items-center justify-between border-b border-zinc-800 px-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[15px] font-bold text-zinc-100">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-blue-600 text-sm text-white">Σ</span>
            <span>Sakumon</span>
          </div>
          <div className="ml-9 mt-0.5 text-[10px] tracking-[0.12em] text-zinc-500">by MORTRA</div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center text-lg text-zinc-500 md:hidden"
            aria-label="メニューを閉じる"
          >
            ×
          </button>
        ) : null}
      </div>

      <div className="space-y-5 px-4 py-4">
        <nav className="space-y-1 border-b border-zinc-800 pb-4" aria-label="ワークスペース">
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
                    ? 'bg-blue-500/10 text-blue-300'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100'
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
              className="text-[11px] font-medium text-blue-400 hover:text-blue-300"
            >
              更新
            </button>
          </div>
          <dl className="divide-y divide-zinc-800 border-y border-zinc-800 text-[12px]">
            <Stat label="表示中" value={stats.total} />
            <Stat label="選択済み" value={stats.selected} tone="blue" />
            <Stat label="未評価" value={stats.pending} />
            <Stat label="投稿済み" value={stats.posted} tone="green" />
            <Stat label="修復候補" value={stats.skipped} tone="red" />
          </dl>
          <p className="mt-2 text-[10px] text-zinc-600">表示中の最大世代 Gen {stats.generations}</p>
        </section>

        <section>
          <Label>領域</Label>
          <select
            value={filters.topic ?? ''}
            onChange={event => set({ topic: event.target.value || null })}
            className="mt-2 h-9 w-full rounded border border-zinc-700 bg-zinc-900 px-2.5 text-[12px] text-zinc-200 outline-none focus:border-blue-400"
          >
            <option value="">すべての領域</option>
            {TOPICS.map(topic => (
              <option key={topic} value={topic}>{TOPIC_JP[topic] ?? topic}</option>
            ))}
          </select>
        </section>

        <section>
          <Label>ステータス</Label>
          <div className="mt-2 overflow-hidden rounded border border-zinc-800">
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
                  className={`flex h-9 w-full items-center justify-between border-b border-zinc-800 px-3 text-left text-[12px] last:border-0 ${
                    active
                      ? 'bg-blue-500/10 font-semibold text-blue-300'
                      : 'bg-[#151517] text-zinc-400 hover:bg-zinc-900'
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
            className="mt-2 h-9 w-full rounded border border-zinc-700 bg-zinc-900 px-2.5 text-[12px] text-zinc-200 outline-none focus:border-blue-400"
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
            <span className="text-[11px] font-semibold tabular-nums text-zinc-300">{filters.perPage}件</span>
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

        <label className="flex cursor-pointer items-center justify-between border-t border-zinc-800 pt-4">
          <span className="text-[12px] font-medium text-zinc-300">解答・解説を表示</span>
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
    <h2 id={id} className="text-[10px] font-bold uppercase text-zinc-500">
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
    default: 'text-zinc-300',
    blue: 'text-blue-400',
    green: 'text-emerald-400',
    red: 'text-rose-400',
  }[tone]

  return (
    <div className="flex items-center justify-between py-2">
      <dt className="text-zinc-500">{label}</dt>
      <dd className={`font-semibold tabular-nums ${toneClass}`}>{value ?? '—'}</dd>
    </div>
  )
}
