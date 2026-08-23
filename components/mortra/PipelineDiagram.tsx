'use client'

/**
 * 1問が MORTRA を通る経路の図。
 *
 * この図が言いたいのは「幾何専用ではない」ことと「答えないことがある」ことの2点。
 * 振り分け先が複数あるから幾何以外も通り、証明書に通らなければ棄権へ抜ける。
 *
 * 装飾ではなく、実際の経路をそのまま描いている。
 * 節の名前は worker/semantics/problem_ir.py の BACKEND_FOR_GOAL と対応する。
 */
import { useEffect, useRef, useState } from 'react'

const BACKENDS = [
  { id: 'geometry', label: '幾何の演繹', note: '点・線・円' },
  { id: 'cas', label: '式の計算', note: '極限・積分' },
  { id: 'inequality', label: '不等式', note: '範囲' },
  { id: 'proof', label: '証明', note: '示せ' },
  { id: 'solution_set', label: '解集合', note: 'すべて求めよ' },
]

export function PipelineDiagram() {
  const ref = useRef<SVGSVGElement | null>(null)
  const [on, setOn] = useState(false)

  // 画面に入ってから動かす。見えていない図を回し続けない
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { threshold: 0.25 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const W = 900
  const H = 380
  const xIn = 70
  const xIR = 250
  const xBE = 500
  const xCert = 700
  const xOut = 845

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="問題文を読み、目標を取り出し、目標の種類ごとに解き方を振り分け、証明書の検証を通ったものだけを答える経路の図"
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      <defs>
        <marker id="pdArrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L8 4 L0 8 z" fill="currentColor" opacity="0.5" />
        </marker>
      </defs>

      <g fontFamily="inherit" fill="currentColor">
        {/* 入口 */}
        <g transform={`translate(${xIn} ${H / 2})`}>
          <rect x="-52" y="-30" width="104" height="60" rx="8" fill="none" stroke="currentColor" strokeOpacity="0.35" />
          <text textAnchor="middle" y="-6" fontSize="13" fontWeight="600">問題文</text>
          <text textAnchor="middle" y="14" fontSize="11" opacity="0.6">日本語のまま</text>
        </g>

        {/* 目標抽出 */}
        <g transform={`translate(${xIR} ${H / 2})`}>
          <rect x="-72" y="-38" width="144" height="76" rx="8" fill="none" stroke="currentColor" strokeOpacity="0.35" />
          <text textAnchor="middle" y="-12" fontSize="13" fontWeight="600">何を訊かれたか</text>
          <text textAnchor="middle" y="8" fontSize="11" opacity="0.6">求めよ / 示せ /</text>
          <text textAnchor="middle" y="24" fontSize="11" opacity="0.6">すべて求めよ</text>
        </g>
        <line x1={xIn + 54} y1={H / 2} x2={xIR - 74} y2={H / 2}
          stroke="currentColor" strokeOpacity="0.3" markerEnd="url(#pdArrow)" />

        {/* 振り分け先 */}
        {BACKENDS.map((b, i) => {
          const y = 46 + i * 72
          return (
            <g key={b.id}>
              <path
                d={`M ${xIR + 74} ${H / 2} C ${xIR + 150} ${H / 2}, ${xBE - 150} ${y}, ${xBE - 76} ${y}`}
                fill="none" stroke="currentColor" strokeOpacity="0.22" markerEnd="url(#pdArrow)"
              />
              {on && (
                <circle r="3" fill="#5eead4">
                  <animateMotion
                    dur={`${2.4 + i * 0.35}s`} repeatCount="indefinite"
                    path={`M ${xIR + 74} ${H / 2} C ${xIR + 150} ${H / 2}, ${xBE - 150} ${y}, ${xBE - 76} ${y}`}
                  />
                  <animate attributeName="opacity" values="0;1;1;0" dur={`${2.4 + i * 0.35}s`} repeatCount="indefinite" />
                </circle>
              )}
              <g transform={`translate(${xBE} ${y})`}>
                <rect x="-74" y="-22" width="148" height="44" rx="6"
                  fill="currentColor" fillOpacity="0.04" stroke="currentColor" strokeOpacity="0.3" />
                <text textAnchor="middle" y="-2" fontSize="12" fontWeight="600">{b.label}</text>
                <text textAnchor="middle" y="14" fontSize="10" opacity="0.55">{b.note}</text>
              </g>
              <path d={`M ${xBE + 76} ${y} C ${xBE + 140} ${y}, ${xCert - 90} ${H / 2}, ${xCert - 46} ${H / 2}`}
                fill="none" stroke="currentColor" strokeOpacity="0.22" markerEnd="url(#pdArrow)" />
            </g>
          )
        })}

        {/* 検証 */}
        <g transform={`translate(${xCert} ${H / 2})`}>
          <rect x="-44" y="-38" width="88" height="76" rx="8"
            fill="none" stroke="#5eead4" strokeOpacity="0.55" />
          <text textAnchor="middle" y="-10" fontSize="12" fontWeight="600">検証</text>
          <text textAnchor="middle" y="8" fontSize="10" opacity="0.6">証明書を</text>
          <text textAnchor="middle" y="22" fontSize="10" opacity="0.6">作り直す</text>
        </g>

        {/* 通った / 通らない */}
        <path d={`M ${xCert + 46} ${H / 2 - 8} C ${xCert + 90} ${H / 2 - 8}, ${xOut - 60} 108, ${xOut - 34} 108`}
          fill="none" stroke="#5eead4" strokeOpacity="0.5" markerEnd="url(#pdArrow)" />
        <g transform={`translate(${xOut} 108)`}>
          <text textAnchor="middle" y="-4" fontSize="12" fontWeight="700" fill="#5eead4">答える</text>
          <text textAnchor="middle" y="14" fontSize="10" opacity="0.6">図と手順つき</text>
        </g>

        <path d={`M ${xCert + 46} ${H / 2 + 8} C ${xCert + 90} ${H / 2 + 8}, ${xOut - 60} 286, ${xOut - 34} 286`}
          fill="none" stroke="currentColor" strokeOpacity="0.3" strokeDasharray="4 4" markerEnd="url(#pdArrow)" />
        <g transform={`translate(${xOut} 286)`}>
          <text textAnchor="middle" y="-4" fontSize="12" fontWeight="700" opacity="0.75">答えない</text>
          <text textAnchor="middle" y="14" fontSize="10" opacity="0.55">推測を出さない</text>
        </g>

        <text x={xBE} y={H - 8} textAnchor="middle" fontSize="10.5" opacity="0.5">
          振り分け先が複数あるから、幾何以外も同じ核を通る
        </text>
      </g>
    </svg>
  )
}
