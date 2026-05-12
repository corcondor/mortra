'use client'
import { useState, useMemo } from 'react'

// ── 大学マスタ ────────────────────────────────────────────────────────────────
export const UNIVERSITIES = [
  { name: '東京大学',         code: '10261', short: '東大' },
  { name: '京都大学',         code: '10541', short: '京大' },
  { name: '東京工業大学',     code: '10267', short: '東工大' },
  { name: '大阪大学',         code: '10561', short: '阪大' },
  { name: '名古屋大学',       code: '10481', short: '名大' },
  { name: '東北大学',         code: '10081', short: '東北大' },
  { name: '北海道大学',       code: '10001', short: '北大' },
  { name: '九州大学',         code: '10842', short: '九大' },
  { name: '一橋大学',         code: '10272', short: '一橋' },
  { name: '神戸大学',         code: '10601', short: '神戸大' },
  { name: '筑波大学',         code: '10162', short: '筑波大' },
  { name: '横浜国立大学',     code: '10301', short: '横国' },
  { name: '千葉大学',         code: '10241', short: '千葉大' },
  { name: '大阪公立大学',     code: '11562', short: '大阪公立' },
] as const

// 試験区分
const EXAM_TYPES = [
  { label: '前期', code: '01' },
  { label: '後期', code: '02' },
] as const

// ── URL生成 ──────────────────────────────────────────────────────────────────
function examUrl(univCode: string, year: number, typeCode: string) {
  const base = `${year}${univCode}${typeCode}00`
  return `https://mathexamtest.jp/${year}/${year}${univCode}/${base}mj.html`
}

// ── 問題エントリ型 ────────────────────────────────────────────────────────────
export interface PastExamEntry {
  id:        string
  univCode:  string
  univName:  string
  univShort: string
  year:      number
  type:      string   // '前期' | '後期'
  typeCode:  string
  url:       string
}

// ── 全エントリ生成（2010〜2025） ──────────────────────────────────────────────
function buildEntries(): PastExamEntry[] {
  const entries: PastExamEntry[] = []
  const years = Array.from({ length: 16 }, (_, i) => 2025 - i) // 2025→2010
  for (const univ of UNIVERSITIES) {
    for (const year of years) {
      for (const type of EXAM_TYPES) {
        entries.push({
          id:        `${univ.code}-${year}-${type.code}`,
          univCode:  univ.code,
          univName:  univ.name,
          univShort: univ.short,
          year,
          type:      type.label,
          typeCode:  type.code,
          url:       examUrl(univ.code, year, type.code),
        })
      }
    }
  }
  return entries
}

const ALL_ENTRIES = buildEntries()

// ── Props ────────────────────────────────────────────────────────────────────
interface Props {
  onStartFusion: (parents: PastExamEntry[]) => void
  isAdmin:       boolean
}

// ── コンポーネント ────────────────────────────────────────────────────────────
export function PastExamDB({ onStartFusion, isAdmin }: Props) {
  const [filterUniv,  setFilterUniv]  = useState<string>('')     // univCode or ''
  const [filterYear,  setFilterYear]  = useState<number | ''>('')
  const [filterType,  setFilterType]  = useState<string>('')     // '前期'|'後期'|''
  const [checked,     setChecked]     = useState<Set<string>>(new Set())

  // フィルタ適用
  const filtered = useMemo(() => {
    return ALL_ENTRIES.filter(e => {
      if (filterUniv && e.univCode !== filterUniv) return false
      if (filterYear && e.year    !== filterYear)  return false
      if (filterType && e.type    !== filterType)  return false
      return true
    })
  }, [filterUniv, filterYear, filterType])

  // 選択されたエントリ
  const selectedEntries = ALL_ENTRIES.filter(e => checked.has(e.id))

  const toggle = (id: string) => {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        if (next.size >= 2) return prev // 最大2件
        next.add(id)
      }
      return next
    })
  }

  const years = Array.from({ length: 16 }, (_, i) => 2025 - i)

  return (
    <div className="flex flex-col gap-4">

      {/* ヘッダー */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-white/90">過去問データベース</h1>
          <p className="text-[12px] text-white/30 mt-0.5">
            国公立大学 入試数学 2010〜2025 ·{' '}
            <a href="https://mathexamtest.jp" target="_blank" rel="noopener noreferrer"
               className="text-apple-blue/70 hover:text-apple-blue underline">
              mathexamtest.jp
            </a>
          </p>
        </div>

        {/* 融合生成ボタン */}
        {checked.size > 0 && (
          <button
            onClick={() => onStartFusion(selectedEntries)}
            disabled={!isAdmin}
            className="flex items-center gap-2 bg-apple-blue hover:bg-apple-blue/80 disabled:opacity-40
                       text-white text-[13px] font-semibold px-4 py-2 rounded-xl transition-all"
          >
            <span>⚡</span>
            <span>選択した {checked.size} 問で融合生成</span>
          </button>
        )}
      </div>

      {/* 選択中バッジ */}
      {selectedEntries.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedEntries.map(e => (
            <div key={e.id}
                 className="flex items-center gap-1.5 bg-apple-blue/15 border border-apple-blue/30
                            rounded-lg px-2.5 py-1 text-[11px] text-apple-blue">
              <span>{e.univShort} {e.year} {e.type}</span>
              <button onClick={() => toggle(e.id)}
                      className="text-apple-blue/60 hover:text-apple-blue">✕</button>
            </div>
          ))}
          <span className="text-[11px] text-white/25 self-center">
            （最大2問まで選択可）
          </span>
        </div>
      )}

      {/* フィルタ行 */}
      <div className="flex flex-wrap gap-2">
        {/* 大学 */}
        <select
          value={filterUniv}
          onChange={e => setFilterUniv(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-xl px-3 py-1.5
                     text-[12px] text-white/70 outline-none min-w-[120px]"
        >
          <option value="">すべての大学</option>
          {UNIVERSITIES.map(u => (
            <option key={u.code} value={u.code}>{u.short}</option>
          ))}
        </select>

        {/* 年度 */}
        <select
          value={filterYear}
          onChange={e => setFilterYear(e.target.value ? Number(e.target.value) : '')}
          className="bg-white/5 border border-white/10 rounded-xl px-3 py-1.5
                     text-[12px] text-white/70 outline-none"
        >
          <option value="">すべての年度</option>
          {years.map(y => <option key={y} value={y}>{y}年</option>)}
        </select>

        {/* 区分 */}
        <div className="flex gap-1">
          {['', '前期', '後期'].map(t => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 text-[12px] rounded-xl transition-all
                ${filterType === t
                  ? 'bg-white/15 text-white/90'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5'}`}
            >
              {t || 'すべて'}
            </button>
          ))}
        </div>

        <span className="text-[11px] text-white/25 self-center ml-auto">
          {filtered.length} 件
        </span>
      </div>

      {/* テーブル */}
      <div className="glass rounded-2xl overflow-hidden">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-white/8 text-white/30 text-[10px] uppercase tracking-widest">
              <th className="py-2.5 px-3 text-left w-8"></th>
              <th className="py-2.5 px-3 text-left">大学</th>
              <th className="py-2.5 px-3 text-left">年度</th>
              <th className="py-2.5 px-3 text-left">区分</th>
              <th className="py-2.5 px-3 text-left">リンク</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map((e, i) => {
              const isChecked = checked.has(e.id)
              const disabled  = !isChecked && checked.size >= 2
              return (
                <tr
                  key={e.id}
                  onClick={() => !disabled && toggle(e.id)}
                  className={`border-b border-white/5 transition-colors cursor-pointer
                    ${isChecked  ? 'bg-apple-blue/10'        : ''}
                    ${disabled   ? 'opacity-30 cursor-default' : 'hover:bg-white/4'}
                    ${i % 2 === 0 ? '' : 'bg-white/[0.015]'}`}
                >
                  {/* チェックボックス */}
                  <td className="py-2.5 px-3">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={disabled}
                      onChange={() => {}}
                      className="accent-apple-blue w-3.5 h-3.5"
                    />
                  </td>

                  {/* 大学名 */}
                  <td className="py-2.5 px-3">
                    <span className="font-semibold text-white/80">{e.univShort}</span>
                    <span className="text-white/30 ml-1 hidden sm:inline">
                      {e.univName !== UNIVERSITIES.find(u => u.code === e.univCode)?.short
                        ? '' : ''}
                    </span>
                  </td>

                  {/* 年度 */}
                  <td className="py-2.5 px-3 text-white/60 tabular-nums">{e.year}</td>

                  {/* 区分 */}
                  <td className="py-2.5 px-3">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium
                      ${e.type === '前期' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-orange-500/15 text-orange-400'}`}>
                      {e.type}
                    </span>
                  </td>

                  {/* 外部リンク */}
                  <td className="py-2.5 px-3" onClick={e2 => e2.stopPropagation()}>
                    <a
                      href={e.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-apple-blue/60 hover:text-apple-blue transition-colors"
                    >
                      問題を見る →
                    </a>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="py-12 text-center text-white/25 text-sm">
            条件に一致する問題がありません
          </div>
        )}
        {filtered.length > 200 && (
          <div className="py-3 text-center text-white/25 text-[11px]">
            絞り込んで表示中（200件まで）
          </div>
        )}
      </div>
    </div>
  )
}
