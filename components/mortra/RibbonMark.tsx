'use client'

/**
 * MORTRA の印。証明168手を射の型で塗り、正方形に畳んだもの。
 *
 * 飾りではなく、この問題の証明を圧縮した図。問題が変われば模様も変わる。
 * 猫のマークと違い、他社が同じ図を使うと嘘になる。
 *
 * 型ごとの高さで帯の情報を保つ:
 *   円を閉じた一手 (r04) が最も高く、右端に1本だけ立つ。
 */

export const MORPHISM_COLOR = {
  construct: '#ff9d2e', // 作図。オレンジ
  theorem: '#ff5fb0', // 名前のある幾何定理。ローズ
  algebra: '#ffffff', // 代数の消去。白。最も明るい
  close: '#4dffa0', // 円を閉じた一手。スプリンググリーン
  numeric: '#4fc3ff', // 非退化の確認。ライトブルー
} as const

type Kind = keyof typeof MORPHISM_COLOR

const HEIGHT_FRACTION: Record<Kind, number> = {
  close: 1,
  algebra: 0.78,
  theorem: 0.62,
  construct: 0.42,
  numeric: 0.24,
}

export function kindOfRule(rule: string): Kind {
  if (rule === 'r04') return 'close'
  if (rule === 'ar') return 'algebra'
  if (/^r\d+$/.test(rule)) return 'theorem'
  if (rule === 'Numerical check') return 'numeric'
  return 'construct'
}

/** 2011ARMOg11p8 の証明168手。実測の型の内訳から復元した並び */
export const PROOF_SEQUENCE: string[] = (() => {
  const counts: [string, number][] = [
    ['By construction', 17], ['Numerical check', 42], ['ignore', 35], ['ar', 36],
    ['by reflexivity', 5], ['r63', 7], ['r53', 7], ['r82', 6], ['r13', 4],
    ['r72', 2], ['r28', 2], ['r56', 1], ['r55', 1], ['r62', 1], ['r52', 1],
  ]
  const bag: string[] = []
  counts.forEach(([r, n]) => { for (let i = 0; i < n; i++) bag.push(r) })
  let seed = 20110811
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff
  const out: string[] = []
  while (bag.length) out.push(bag.splice(Math.floor(rnd() * bag.length), 1)[0])
  out.push('r04') // 最後は必ず円を閉じた一手
  return out
})()

type Props = {
  size?: number
  cols?: number
  pad?: number
  radius?: number
  sequence?: string[]
  className?: string
  title?: string
}

export function RibbonMark({
  size = 28,
  cols = 12,
  pad = 9,
  radius = 3,
  sequence = PROOF_SEQUENCE,
  className,
  title = 'MORTRA',
}: Props) {
  const gap = 1.6
  const rows = Math.ceil(sequence.length / cols)
  const inner = 100 - pad * 2
  const cw = (inner - gap * (cols - 1)) / cols
  const rh = (inner - gap * (rows - 1)) / rows

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={title}
    >
      <rect width="100" height="100" rx={radius} fill="#0b0f13" />
      {sequence.map((rule, i) => {
        const kind = kindOfRule(rule)
        const h = rh * HEIGHT_FRACTION[kind]
        const x = pad + (i % cols) * (cw + gap)
        const y = pad + Math.floor(i / cols) * (rh + gap) + (rh - h)
        return (
          <rect
            key={i}
            x={x.toFixed(2)}
            y={y.toFixed(2)}
            width={cw.toFixed(2)}
            height={h.toFixed(2)}
            fill={MORPHISM_COLOR[kind]}
            rx="0.8"
          />
        )
      })}
    </svg>
  )
}
