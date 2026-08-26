'use client'

/**
 * MORTRA の面分離アーキテクチャ。論文の Figure 1 として描く。
 *
 * 出典は worker/backend/mortra_unified_architecture.py の manifest と、
 * validate_unified_geometry_architecture() が拒否する条件。
 * 図に描いてある制約は、すべてコードで機械検査されている。
 *
 * この図の主張は一つ。情報は上へ流れるが、権限は流れない。
 *   提案面は候補を出すが、真偽を決めない  (numerical_proposals_are_not_truth)
 *   協調面は優先順位と予算だけを決める      (authority: search priority and budget only)
 *   真理面は証明書の再生だけで決める        (accepts_priority_without_certificate: False)
 *   実行面は速くするが真理を変えない        (changes_mathematical_truth: False)
 */

import type { Lang } from '@/lib/mortra/i18n'

type Plane = {
  id: string
  label: string
  role: string
  items: string[]
  authority: 'none' | 'priority' | 'truth' | 'speed'
}

const TEXT = {
  ja: {
    alt: 'MORTRAの面分離アーキテクチャ。提案・局所形式言語・知識・協調・真理・実行の6面。情報は上から下へ流れるが、真偽を決める権限は真理面だけが持つ。',
    figTitle: 'FIG. 1 — 面の分離と権限の非伝播',
    footA: '情報は下へ流れる。真偽を決める権限は真理面だけが持ち、上へ戻らない。',
    footB: 'この4つの制約は validate_unified_geometry_architecture() が実行時に検査し、破れば例外で落ちる。',
    notes: ['真理ではない', '優先順位と予算だけ', '証明書の再生のみ', '真理を変えない'],
    planes: [
      { id: 'proposal', label: 'PROPOSAL', role: '候補を出す', items: ['HAGeo 数値incidence', 'Tong 型付き構成'], authority: 'none' },
      { id: 'local', label: 'LOCAL FORMAL LANGUAGES', role: '各々の言語のまま解く', items: ['Newclid DD閉包', 'Newclid 型付き遷移', 'AR残差', 'GCLC-Wu 多項式義務', 'SyGuS 開義務'], authority: 'none' },
      { id: 'knowledge', label: 'KNOWLEDGE', role: '意味を保って写す', items: ['OpenMath 項', 'MMT theory graph', 'interface view'], authority: 'none' },
      { id: 'coordination', label: 'COORDINATION', role: '優先順位と予算だけ', items: ['exact 証明書交換（既定）', 'Sheaf-ADMM（実験・既定OFF）'], authority: 'priority' },
      { id: 'truth', label: 'TRUTH', role: 'ここだけが真偽を決める', items: ['型付き native 証明書の再生'], authority: 'truth' },
      { id: 'execution', label: 'EXECUTION', role: '速くする。真理は変えない', items: ['RISC-V 型付き命令スケジューリング', 'FPGA bitset関係閉包 / 有界多項式核'], authority: 'speed' },
    ] as Plane[],
  },
  en: {
    alt: "MORTRA's plane-separated architecture: proposal, local formal languages, knowledge, coordination, truth and execution. Information flows downward, but only the truth plane may decide whether something holds.",
    figTitle: 'FIG. 1 — Separation of planes, non-propagation of authority',
    footA: 'Information flows down. Only the truth plane decides what holds, and that authority never flows back up.',
    footB: 'These four constraints are checked at runtime by validate_unified_geometry_architecture(); a violation raises.',
    notes: ['not truth', 'priority and budget only', 'certificate replay only', 'does not change truth'],
    planes: [
      { id: 'proposal', label: 'PROPOSAL', role: 'proposes candidates', items: ['HAGeo numeric incidence', 'Tong typed construction'], authority: 'none' },
      { id: 'local', label: 'LOCAL FORMAL LANGUAGES', role: 'each solves in its own language', items: ['Newclid DD closure', 'Newclid typed transitions', 'AR residual', 'GCLC-Wu polynomial obligations', 'SyGuS open obligations'], authority: 'none' },
      { id: 'knowledge', label: 'KNOWLEDGE', role: 'transports meaning', items: ['OpenMath terms', 'MMT theory graph', 'interface view'], authority: 'none' },
      { id: 'coordination', label: 'COORDINATION', role: 'priority and budget only', items: ['exact certificate exchange (default)', 'Sheaf-ADMM (experimental, off)'], authority: 'priority' },
      { id: 'truth', label: 'TRUTH', role: 'the only plane that decides', items: ['replay of typed native certificates'], authority: 'truth' },
      { id: 'execution', label: 'EXECUTION', role: 'makes it fast, not true', items: ['RISC-V typed instruction scheduling', 'FPGA bitset closure / bounded polynomial core'], authority: 'speed' },
    ] as Plane[],
  },
} as const

const CYAN = '#5eead4'
const AMBER = '#f0a03c'

export function ArchitectureFigure({ lang = 'en' }: { lang?: Lang }) {
  const c0 = TEXT[lang]
  const PLANES = c0.planes
  const W = 940
  const rowH = 66
  const gap = 10
  const top = 44
  const xL = 150
  const boxW = 600
  const H = top + PLANES.length * (rowH + gap) + 46

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={c0.alt}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      <g fill="currentColor" fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
        <text x="0" y="18" fontSize="11.5" opacity="0.5" letterSpacing="0.1em">
          {c0.figTitle}
        </text>

        {PLANES.map((p, i) => {
          const y = top + i * (rowH + gap)
          const isTruth = p.authority === 'truth'
          const stroke = isTruth ? CYAN : 'currentColor'
          const op = isTruth ? 0.6 : 0.26
          return (
            <g key={p.id}>
              {/* 面の名前 */}
              <text x={xL - 16} y={y + 24} textAnchor="end" fontSize="10.5"
                letterSpacing="0.08em" opacity={isTruth ? 0.95 : 0.6}
                fill={isTruth ? CYAN : 'currentColor'}>{p.label}</text>
              <text x={xL - 16} y={y + 42} textAnchor="end" fontSize="10" opacity="0.42">{p.role}</text>

              {/* 面の帯 */}
              <rect x={xL} y={y} width={boxW} height={rowH} rx="4"
                fill={isTruth ? CYAN : 'currentColor'} fillOpacity={isTruth ? 0.06 : 0.025}
                stroke={stroke} strokeOpacity={op} />

              {/* 中の要素 */}
              {p.items.map((it, j) => {
                const perRow = p.items.length > 3 ? 3 : p.items.length
                const cw = (boxW - 24) / perRow
                const cx = xL + 12 + (j % perRow) * cw
                const cy = y + (p.items.length > 3 ? 18 + Math.floor(j / perRow) * 26 : rowH / 2 + 4)
                return (
                  <text key={it} x={cx} y={cy} fontSize="10.5" opacity="0.82">{it}</text>
                )
              })}

              {/* 面と面をつなぐ情報の流れ */}
              {i < PLANES.length - 1 && (
                <path d={`M ${xL + boxW / 2} ${y + rowH} L ${xL + boxW / 2} ${y + rowH + gap}`}
                  stroke="currentColor" strokeOpacity="0.3" />
              )}
            </g>
          )
        })}

        {/* 右側: 権限の注記。これがこの図の主張 */}
        {(() => {
          const notes = [
            { i: 0, t: c0.notes[0], c: AMBER },
            { i: 3, t: c0.notes[1], c: AMBER },
            { i: 4, t: c0.notes[2], c: CYAN },
            { i: 5, t: c0.notes[3], c: AMBER },
          ]
          return notes.map(n => {
            const y = top + n.i * (rowH + gap) + rowH / 2
            return (
              <g key={n.i}>
                <line x1={xL + boxW} y1={y} x2={xL + boxW + 20} y2={y}
                  stroke={n.c} strokeOpacity="0.5" strokeDasharray="3 3" />
                <text x={xL + boxW + 26} y={y + 4} fontSize="10" fill={n.c} opacity="0.9">{n.t}</text>
              </g>
            )
          })
        })()}

        {/* 左の縦線: 権限が上へ戻らないことを示す */}
        <g>
          <line x1={xL - 132} y1={top + 3 * (rowH + gap)} x2={xL - 132}
            y2={top + 4 * (rowH + gap) + rowH} stroke={AMBER} strokeOpacity="0.35" strokeDasharray="4 4" />
          <g transform={`translate(${xL - 132} ${top + 4 * (rowH + gap) - 2})`}>
            <circle r="9" fill="#0b0d0f" stroke={AMBER} strokeOpacity="0.7" />
            <path d="M-3.5 -3.5 L3.5 3.5 M3.5 -3.5 L-3.5 3.5" stroke={AMBER} strokeWidth="1.5" />
          </g>
        </g>

        <text x="0" y={H - 22} fontSize="10.5" opacity="0.55">
          {c0.footA}
        </text>
        <text x="0" y={H - 6} fontSize="10" opacity="0.38">
          {c0.footB}
        </text>
      </g>
    </svg>
  )
}
