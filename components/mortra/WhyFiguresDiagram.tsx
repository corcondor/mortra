'use client'

/**
 * MORTRA の主張そのものを図にする。
 *
 * これまでここは3段落の文章だった。図で説明する数学を作ると言いながら、
 * 自分の説明を文章でやっていた。だから図にした。
 *
 * 左: LLM は文を書いてから、別の経路で図のコードを吐く。
 *     二つを突き合わせる仕組みが無いので、食い違っても気づけない。
 *     図の三角形はわざと鈍角に描いてある。文は「鋭角三角形」と言っている。
 * 右: MORTRA は一つの段から主張と図が同時に出る。座標を共有しているので、
 *     食い違いようがない。
 */
import { useEffect, useRef, useState } from 'react'
import type { Lang } from '@/lib/mortra/i18n'

const TEXT = {
  ja: {
    alt: '左はLLM。文と図を別々に作るので食い違う。右はMORTRA。一つの段から主張と図が同時に出るので食い違わない。',
    problem: '問題',
    writeSentence: '文を書く',
    emitFigureCode: '図のコードを吐く',
    claim: '「鋭角三角形ABCで」',
    written: '…と書いてある',
    actuallyObtuse: '実際は鈍角',
    noCheck: '照合する仕組みが無い',
    oneStep: '証明の一段',
    hasCoords: '座標を持つ',
    cannotDiverge: '同じ座標から出るので、食い違えない',
    staysAcute: '鋭角のまま',
    summaryLeft: '図は文の後付け',
    summaryRight: '図は証明そのもの',
  },
  en: {
    alt: 'Left: an LLM writes the sentence and the figure separately, so they can disagree. Right: MORTRA emits the claim and the figure from one proof step, so they cannot.',
    problem: 'Problem',
    writeSentence: 'Write the prose',
    emitFigureCode: 'Emit figure code',
    claim: '“In acute triangle ABC…”',
    written: '…is what it says',
    actuallyObtuse: 'actually obtuse',
    noCheck: 'nothing checks the two',
    oneStep: 'One proof step',
    hasCoords: 'carries coordinates',
    cannotDiverge: 'Same coordinates, so they cannot disagree',
    staysAcute: 'stays acute',
    summaryLeft: 'Figure bolted on after the prose',
    summaryRight: 'Figure is the proof',
  },
} as const

export function WhyFiguresDiagram({ lang = 'en' }: { lang?: Lang }) {
  const c = TEXT[lang]
  const ref = useRef<SVGSVGElement | null>(null)
  const [on, setOn] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { threshold: 0.3 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <svg
      ref={ref}
      viewBox="0 0 880 340"
      role="img"
      aria-label={c.alt}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      <defs>
        <marker id="wfA" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L8 4 L0 8 z" fill="currentColor" opacity="0.55" />
        </marker>
      </defs>

      <g fill="currentColor" fontFamily="inherit">
        {/* ================= 左: LLM ================= */}
        <text x="20" y="26" fontSize="12" letterSpacing="0.08em" opacity="0.55">LLM</text>

        <g transform="translate(60 100)">
          <rect x="-46" y="-19" width="92" height="38" rx="6" fill="none" stroke="currentColor" strokeOpacity="0.35" />
          <text textAnchor="middle" y="5" fontSize="12">{c.problem}</text>
        </g>

        {/* 二本に分かれる。互いを見ない */}
        <path d="M 108 92 C 150 92, 170 62, 205 62" fill="none" stroke="currentColor" strokeOpacity="0.35" markerEnd="url(#wfA)" />
        <path d="M 108 110 C 150 110, 170 200, 205 200" fill="none" stroke="currentColor" strokeOpacity="0.35" markerEnd="url(#wfA)" />

        <g transform="translate(266 62)">
          <rect x="-58" y="-20" width="116" height="40" rx="6" fill="currentColor" fillOpacity="0.04" stroke="currentColor" strokeOpacity="0.3" />
          <text textAnchor="middle" y="4" fontSize="11.5">{c.writeSentence}</text>
        </g>
        <g transform="translate(266 200)">
          <rect x="-58" y="-20" width="116" height="40" rx="6" fill="currentColor" fillOpacity="0.04" stroke="currentColor" strokeOpacity="0.3" />
          <text textAnchor="middle" y="4" fontSize="11.5">{c.emitFigureCode}</text>
        </g>

        {/* 出力: 文と図。突き合わせていないので矛盾する */}
        <text x="336" y="58" fontSize="11.5" opacity="0.85">{c.claim}</text>
        <text x="336" y="76" fontSize="10.5" opacity="0.5">{c.written}</text>

        {/* わざと鈍角に描く */}
        <g transform="translate(348 176)">
          <polygon points="0,34 108,34 88,4" fill="none" stroke="#f0a03c" strokeOpacity="0.9" strokeWidth="1.4" />
          <text x="0" y="48" fontSize="10" fill="#f0a03c" opacity="0.9">{c.actuallyObtuse}</text>
        </g>

        {/* 突き合わせが無いことを示す */}
        <line x1="330" y1="96" x2="330" y2="164" stroke="#f0a03c" strokeOpacity="0.5" strokeDasharray="3 5" />
        <g transform="translate(330 130)">
          <circle r="11" fill="#0b0d0f" stroke="#f0a03c" strokeOpacity="0.75" />
          <path d="M-4 -4 L4 4 M4 -4 L-4 4" stroke="#f0a03c" strokeWidth="1.6" />
        </g>
        <text x="348" y="134" fontSize="10.5" fill="#f0a03c" opacity="0.9">{c.noCheck}</text>

        {/* 仕切り */}
        <line x1="470" y1="16" x2="470" y2="316" stroke="currentColor" strokeOpacity="0.12" />

        {/* ================= 右: MORTRA ================= */}
        <text x="500" y="26" fontSize="12" letterSpacing="0.08em" fill="#5eead4" opacity="0.85">MORTRA</text>

        <g transform="translate(546 130)">
          <rect x="-46" y="-19" width="92" height="38" rx="6" fill="none" stroke="currentColor" strokeOpacity="0.35" />
          <text textAnchor="middle" y="5" fontSize="12">{c.problem}</text>
        </g>

        <path d="M 594 130 L 646 130" fill="none" stroke="currentColor" strokeOpacity="0.35" markerEnd="url(#wfA)" />

        {/* 一つの段。ここから両方が出る */}
        <g transform="translate(706 130)">
          <rect x="-52" y="-30" width="104" height="60" rx="8" fill="#5eead4" fillOpacity="0.07" stroke="#5eead4" strokeOpacity="0.55" />
          <text textAnchor="middle" y="-4" fontSize="12" fontWeight="600">{c.oneStep}</text>
          <text textAnchor="middle" y="14" fontSize="10" opacity="0.6">{c.hasCoords}</text>
        </g>

        {on && (
          <>
            <circle r="3" fill="#5eead4">
              <animateMotion dur="2.6s" repeatCount="indefinite" path="M 758 118 C 792 118, 796 74, 820 74" />
            </circle>
            <circle r="3" fill="#5eead4">
              <animateMotion dur="2.6s" repeatCount="indefinite" path="M 758 142 C 792 142, 796 196, 820 196" />
            </circle>
          </>
        )}
        <path d="M 758 118 C 792 118, 796 74, 820 74" fill="none" stroke="#5eead4" strokeOpacity="0.45" markerEnd="url(#wfA)" />
        <path d="M 758 142 C 792 142, 796 196, 820 196" fill="none" stroke="#5eead4" strokeOpacity="0.45" markerEnd="url(#wfA)" />

        <text x="700" y="222" fontSize="10.5" opacity="0.55" textAnchor="middle">{c.cannotDiverge}</text>

        {/* 出力: 文と、条件を満たす図 */}
        <text x="778" y="60" fontSize="11.5" opacity="0.85">{c.claim}</text>
        <g transform="translate(790 168)">
          <polygon points="0,34 70,34 38,0" fill="none" stroke="#5eead4" strokeOpacity="0.9" strokeWidth="1.4" />
          <text x="0" y="48" fontSize="10" fill="#5eead4" opacity="0.9">{c.staysAcute}</text>
        </g>

        {/* 下段の要約。文字数を絞る */}
        <text x="240" y="312" textAnchor="middle" fontSize="11.5" opacity="0.6">{c.summaryLeft}</text>
        <text x="700" y="312" textAnchor="middle" fontSize="11.5" fill="#5eead4" opacity="0.8">{c.summaryRight}</text>
      </g>
    </svg>
  )
}
