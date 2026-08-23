'use client'

/**
 * FIG.2 — 表現Atlas。同じ対象が chart ごとに別の顔を持つ。
 *
 * 出典は docs/research/MORTRA-REPRESENTATION-ATLAS-CEGIS-EXPERIMENT-20260822.md。
 * lequation/perp を計量chartでは内積・二次形式へ、
 * incidence/affine をアフィンchartでは行列式・rank へ移す。
 *
 * 情報理論の対応も図に入れる。
 *   chart = encoder / bridge = channel / certificate replay = decoder / residual = syndrome
 * ただし意味欠落は確率的雑音ではないので、そこは線を引いてある。
 *
 * この図が同時に示すのは、2026-08-22 に測った失敗である。
 * 橋は完成した証明書を運ぶが、未完成の義務を別の原子で作り直す経路が無い。
 * だから実問題での chart 経由候補は 0 だった。
 */

const CYAN = '#5eead4'
const AMBER = '#f0a03c'

const CHARTS = [
  {
    id: 'relation',
    title: '関係 chart',
    sub: 'Newclid DD',
    atoms: ['perp(A,B,C,D)', 'coll(A,B,C)', 'cyclic(A,B,C,D)'],
    x: 60,
  },
  {
    id: 'metric',
    title: '計量 chart',
    sub: '偏極・内積',
    atoms: ['⟨u,v⟩ = 0', '二次形式 q(x)', '距離の等式'],
    x: 352,
  },
  {
    id: 'affine',
    title: 'アフィン chart',
    sub: '行列式・rank',
    atoms: ['det[...] = 0', 'rank M ≤ 2', '線形従属'],
    x: 644,
  },
]

export function AtlasFigure() {
  const W = 940
  const H = 400
  const boxW = 236
  const boxH = 128
  const yBox = 74

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="表現Atlas。同じ幾何対象が関係chart・計量chart・アフィンchartで別の原子として表れる。chartの間はtransition mapで結ばれ、証明書は検証してから運ばれる。"
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      <g fill="currentColor" fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
        <text x="0" y="18" fontSize="11.5" opacity="0.5" letterSpacing="0.1em">
          FIG. 2 — 表現 Atlas と transition map
        </text>

        {/* 同一の対象。上に置く */}
        <g transform={`translate(${W / 2} 46)`}>
          <text textAnchor="middle" fontSize="11" opacity="0.55">
            一つの幾何対象 — 三角形ABCとその垂心
          </text>
        </g>

        {CHARTS.map((c, i) => (
          <g key={c.id}>
            {/* 対象から chart へ */}
            <path
              d={`M ${W / 2} 54 C ${W / 2} 64, ${c.x + boxW / 2} 60, ${c.x + boxW / 2} ${yBox}`}
              fill="none" stroke="currentColor" strokeOpacity="0.22"
            />
            <rect x={c.x} y={yBox} width={boxW} height={boxH} rx="6"
              fill="currentColor" fillOpacity="0.025"
              stroke={i === 0 ? CYAN : 'currentColor'} strokeOpacity={i === 0 ? 0.5 : 0.26} />
            <text x={c.x + 14} y={yBox + 24} fontSize="12" fontWeight="600"
              fill={i === 0 ? CYAN : 'currentColor'} opacity={i === 0 ? 0.95 : 0.85}>{c.title}</text>
            <text x={c.x + 14} y={yBox + 41} fontSize="10" opacity="0.45">{c.sub}</text>
            {c.atoms.map((a, j) => (
              <text key={a} x={c.x + 14} y={yBox + 66 + j * 19} fontSize="10.5" opacity="0.8">{a}</text>
            ))}
            <text x={c.x + 14} y={yBox + boxH - 8} fontSize="9.5" opacity="0.4">原子</text>
          </g>
        ))}

        {/* transition map */}
        {[0, 1].map(i => {
          const x1 = CHARTS[i].x + boxW
          const x2 = CHARTS[i + 1].x
          const y = yBox + boxH / 2
          return (
            <g key={i}>
              <path d={`M ${x1 + 4} ${y} L ${x2 - 4} ${y}`} fill="none"
                stroke={CYAN} strokeOpacity="0.4" />
              <path d={`M ${x2 - 12} ${y - 4} L ${x2 - 4} ${y} L ${x2 - 12} ${y + 4}`}
                fill="none" stroke={CYAN} strokeOpacity="0.5" />
              <path d={`M ${x1 + 12} ${y + 12} L ${x1 + 4} ${y + 8} L ${x1 + 12} ${y + 4}`}
                fill="none" stroke={CYAN} strokeOpacity="0.5" />
              <text x={(x1 + x2) / 2} y={y - 10} textAnchor="middle" fontSize="9.5"
                fill={CYAN} opacity="0.75">transition</text>
            </g>
          )
        })}

        {/* 情報理論の対応 */}
        <g transform="translate(60 246)">
          <text fontSize="10.5" opacity="0.5" letterSpacing="0.06em">情報理論の対応</text>
          {[
            ['chart', 'encoder'],
            ['bridge', 'channel'],
            ['certificate replay', 'decoder / verifier'],
            ['residual', 'syndrome'],
          ].map(([a, b], i) => (
            <g key={a} transform={`translate(${i * 208} 22)`}>
              <text fontSize="10.5" opacity="0.85">{a}</text>
              <text y="16" fontSize="10.5" fill={CYAN} opacity="0.7">= {b}</text>
            </g>
          ))}
          <text y="60" fontSize="9.5" fill={AMBER} opacity="0.75">
            ただし意味の欠落は確率的な通信雑音ではない。同一視しない。
          </text>
        </g>

        {/* 測った失敗 */}
        <g transform="translate(60 344)">
          <rect x="-8" y="-18" width="824" height="46" rx="5"
            fill={AMBER} fillOpacity="0.05" stroke={AMBER} strokeOpacity="0.35" />
          <text fontSize="10.5" fill={AMBER} opacity="0.95">
            2026-08-22 の測定: 橋は完成した証明書を運ぶ。未完成の義務を別の原子で作り直す経路が無い。
          </text>
          <text y="17" fontSize="10.5" opacity="0.7">
            構成エラー 7→0 / 静的反証 2,395件 / テスト 130/130 — それでも実問題の chart 経由候補は 0、追加正答 0/3。
          </text>
        </g>
      </g>
    </svg>
  )
}
