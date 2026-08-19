export type DiagramPoint = { x: number; y: number }

export type DiagramShape =
  | {
      kind: 'polyline'
      points: DiagramPoint[]
      closed?: boolean
      tone?: 'primary' | 'secondary' | 'muted' | 'accent'
      dashed?: boolean
      fill?: boolean
    }
  | {
      kind: 'circle'
      center: DiagramPoint
      radius: number
      tone?: 'primary' | 'secondary' | 'muted' | 'accent'
      dashed?: boolean
    }
  | {
      kind: 'point'
      point: DiagramPoint
      label?: string
      tone?: 'primary' | 'secondary' | 'muted' | 'accent'
    }

export type PlaneProblemDiagram = {
  version: 1
  kind: 'plane'
  title: string
  caption: string
  viewport: { xMin: number; xMax: number; yMin: number; yMax: number }
  axes?: boolean
  shapes: DiagramShape[]
}

export type MorphismProblemDiagram = {
  version: 1
  kind: 'morphism'
  title: string
  caption: string
  nodes: string[]
}

export type StateProblemDiagram = {
  version: 1
  kind: 'state'
  title: string
  caption: string
  states: Array<{
    id: string
    label: string
    terminal?: boolean
    active?: boolean
  }>
  transitions: Array<{
    from: string
    to: string
    label?: string
  }>
}

export type VariationProblemDiagram = {
  version: 1
  kind: 'variation'
  title: string
  caption: string
  columns: string[]
  rows: Array<{
    label: string
    cells: string[]
    tone?: 'primary' | 'secondary' | 'muted' | 'accent'
  }>
}

export type ProblemDiagram =
  | PlaneProblemDiagram
  | MorphismProblemDiagram
  | StateProblemDiagram
  | VariationProblemDiagram

export type ProblemArtifactSource = {
  familyId?: string
  domain?: string
  parameters?: Record<string, number>
  morphismChain?: string[]
}

const point = (x: number, y: number): DiagramPoint => ({ x, y })

function parabolaDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const c = Math.max(1, parameters.c ?? 1)
  const a = 1
  const b = -1 / (c * c * a)
  const curve = Array.from({ length: 101 }, (_, index) => {
    const x = -1.55 + (3.1 * index) / 100
    return point(x, c * x * x)
  })
  const A = point(a, c * a * a)
  const B = point(b, c * b * b)
  const F = point(0, 1 / c)
  return {
    version: 1,
    kind: 'plane',
    title: '直角弦と定点',
    caption: '破線は OA, OB。直角条件から ab が一定になり、弦 AB は黄色の定点 F を通ります。',
    viewport: { xMin: -1.7, xMax: 1.7, yMin: -0.18, yMax: Math.max(2.6, c * 2.5) },
    axes: true,
    shapes: [
      { kind: 'polyline', points: curve, tone: 'primary' },
      { kind: 'polyline', points: [point(0, 0), A], tone: 'muted', dashed: true },
      { kind: 'polyline', points: [point(0, 0), B], tone: 'muted', dashed: true },
      { kind: 'polyline', points: [A, B], tone: 'secondary' },
      { kind: 'point', point: point(0, 0), label: 'O', tone: 'muted' },
      { kind: 'point', point: A, label: 'A', tone: 'primary' },
      { kind: 'point', point: B, label: 'B', tone: 'primary' },
      { kind: 'point', point: F, label: 'F', tone: 'accent' },
    ],
  }
}

function interceptRegionDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const c = Math.max(2, parameters.c ?? 6)
  const boundary = Array.from({ length: 81 }, (_, index) => {
    const x = (c * index) / 80
    return point(x, Math.pow(Math.sqrt(c) - Math.sqrt(x), 2))
  })
  const region = [point(0, 0), point(c, 0), ...boundary.slice().reverse()]
  const sampleValues = [0.22, 0.42, 0.62, 0.8]
  return {
    version: 1,
    kind: 'plane',
    title: '線分族の通過領域',
    caption: '灰色の線分を連続的に動かしたとき、薄青色の領域がちょうど一度以上通過されます。',
    viewport: { xMin: -0.4, xMax: c + 0.5, yMin: -0.4, yMax: c + 0.5 },
    axes: true,
    shapes: [
      { kind: 'polyline', points: region, closed: true, tone: 'primary', fill: true },
      ...sampleValues.map(value => ({
        kind: 'polyline' as const,
        points: [point(c * value, 0), point(0, c * (1 - value))],
        tone: 'muted' as const,
      })),
      { kind: 'polyline', points: boundary, tone: 'primary' },
      { kind: 'point', point: point(c, 0), label: 'A', tone: 'secondary' },
      { kind: 'point', point: point(0, c), label: 'B', tone: 'secondary' },
    ],
  }
}

function translatedDiskDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const radius = Math.max(1, parameters.radius ?? 2)
  const length = Math.max(2, parameters.length ?? 6)
  const upper = Array.from({ length: 41 }, (_, index) => {
    const angle = Math.PI / 2 + (Math.PI * index) / 40
    return point(radius * Math.cos(angle), radius * Math.sin(angle))
  })
  const lower = Array.from({ length: 41 }, (_, index) => {
    const angle = -Math.PI / 2 + (Math.PI * index) / 40
    return point(length + radius * Math.cos(angle), radius * Math.sin(angle))
  })
  return {
    version: 1,
    kind: 'plane',
    title: '円板と線分のMinkowski和',
    caption: '中心が破線上を動くため、通過領域は中央の長方形と両端の半円に分解できます。',
    viewport: { xMin: -radius - 1, xMax: length + radius + 1, yMin: -radius - 1, yMax: radius + 1 },
    axes: true,
    shapes: [
      { kind: 'polyline', points: [...upper, ...lower], closed: true, tone: 'primary', fill: true },
      { kind: 'circle', center: point(0, 0), radius, tone: 'secondary', dashed: true },
      { kind: 'circle', center: point(length, 0), radius, tone: 'secondary', dashed: true },
      { kind: 'polyline', points: [point(0, 0), point(length, 0)], tone: 'accent', dashed: true },
      { kind: 'point', point: point(0, 0), label: '0', tone: 'accent' },
      { kind: 'point', point: point(length, 0), label: 'L', tone: 'accent' },
    ],
  }
}

function rotatingRectangleDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const width = Math.max(2, parameters.width ?? 8)
  const height = Math.max(2, parameters.height ?? 4)
  const radius = Math.hypot(width / 2, height / 2)
  const rectangle = (angle: number) => {
    const corners = [
      point(-width / 2, -height / 2), point(width / 2, -height / 2),
      point(width / 2, height / 2), point(-width / 2, height / 2),
    ]
    return corners.map(({ x, y }) => point(
      x * Math.cos(angle) - y * Math.sin(angle),
      x * Math.sin(angle) + y * Math.cos(angle),
    ))
  }
  return {
    version: 1,
    kind: 'plane',
    title: '回転軌道と外接円板',
    caption: '長方形の向きを変えても半対角線は一定です。頂点の軌道が通過領域の外周を決めます。',
    viewport: { xMin: -radius * 1.25, xMax: radius * 1.25, yMin: -radius * 1.25, yMax: radius * 1.25 },
    axes: true,
    shapes: [
      { kind: 'circle', center: point(0, 0), radius, tone: 'primary' },
      { kind: 'polyline', points: rectangle(0), closed: true, tone: 'secondary', fill: true },
      { kind: 'polyline', points: rectangle(Math.PI / 5), closed: true, tone: 'muted', dashed: true },
      { kind: 'point', point: point(0, 0), label: 'O', tone: 'accent' },
    ],
  }
}

function fixedChordDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const radius = Math.max(2, parameters.radius ?? 5)
  const chord = Math.min(radius * 1.9, Math.max(1, parameters.chord ?? 6))
  const halfChord = chord / 2
  const h = Math.sqrt(Math.max(0, radius * radius - halfChord * halfChord))
  return {
    version: 1,
    kind: 'plane',
    title: '固定長弦が掃く円環',
    caption: '弦の中点から中心までの距離 h は一定です。弦を回転すると、内円と外円の間をすべて通過します。',
    viewport: { xMin: -radius * 1.25, xMax: radius * 1.25, yMin: -radius * 1.25, yMax: radius * 1.25 },
    axes: false,
    shapes: [
      { kind: 'circle', center: point(0, 0), radius, tone: 'primary' },
      { kind: 'circle', center: point(0, 0), radius: h, tone: 'muted', dashed: true },
      { kind: 'polyline', points: [point(-halfChord, h), point(halfChord, h)], tone: 'secondary' },
      { kind: 'polyline', points: [point(0, 0), point(0, h)], tone: 'accent', dashed: true },
      { kind: 'point', point: point(0, 0), label: 'O', tone: 'accent' },
      { kind: 'point', point: point(-halfChord, h), label: 'P', tone: 'secondary' },
      { kind: 'point', point: point(halfChord, h), label: 'Q', tone: 'secondary' },
    ],
  }
}

function gamblerStateDiagram(parameters: Record<string, number>): StateProblemDiagram {
  const N = Math.max(2, Math.floor(parameters.N ?? 8))
  const k = Math.max(1, Math.min(N - 1, Math.floor(parameters.k ?? Math.floor(N / 2))))
  const pa = Math.max(1, Math.floor(parameters.pa ?? 1))
  const pb = Math.max(1, Math.floor(parameters.pb ?? 1))
  const denominator = pa + pb
  const visible = [...new Set([0, 1, Math.max(1, k - 1), k, Math.min(N - 1, k + 1), N - 1, N])]
    .filter(value => value >= 0 && value <= N)
    .sort((left, right) => left - right)
  const states = visible.map(value => ({
    id: `s${value}`,
    label: String(value),
    terminal: value === 0 || value === N,
    active: value === k,
  }))
  const transitions: StateProblemDiagram['transitions'] = []
  for (const value of visible) {
    if (value > 0 && visible.includes(value - 1)) {
      transitions.push({ from: `s${value}`, to: `s${value - 1}`, label: `${pb}/${denominator}` })
    }
    if (value < N && visible.includes(value + 1)) {
      transitions.push({ from: `s${value}`, to: `s${value + 1}`, label: `${pa}/${denominator}` })
    }
  }
  return {
    version: 1,
    kind: 'state',
    title: '吸収状態をもつ確率過程',
    caption: `状態 ${k} から左右へ遷移し、0 と ${N} で吸収されます。この図から各状態の到達確率の漸化式を立てます。`,
    states,
    transitions,
  }
}

function complexRotationDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const k = Math.max(3, Math.min(47, Math.floor(parameters.k ?? 8)))
  const m = Math.max(1, Math.floor(parameters.m ?? 1))
  const shown = Math.min(k, 16)
  const orbit = Array.from({ length: shown + 1 }, (_, index) => {
    const angle = (2 * Math.PI * m * index) / k
    return point(Math.cos(angle), Math.sin(angle))
  })
  const points = Array.from({ length: shown }, (_, index) => {
    const angle = (2 * Math.PI * m * index) / k
    return {
      kind: 'point' as const,
      point: point(Math.cos(angle), Math.sin(angle)),
      label: index === 0 ? '1' : undefined,
      tone: index === 0 ? 'accent' as const : 'primary' as const,
    }
  })
  return {
    version: 1,
    kind: 'plane',
    title: '複素数列の回転軌道',
    caption: `1回ごとに偏角を 2π×${m}/${k} だけ加えます。初めて始点1へ戻る周回数が最小周期です。`,
    viewport: { xMin: -1.35, xMax: 1.35, yMin: -1.35, yMax: 1.35 },
    axes: true,
    shapes: [
      { kind: 'circle', center: point(0, 0), radius: 1, tone: 'muted' },
      { kind: 'polyline', points: orbit, tone: 'secondary' },
      ...points,
    ],
  }
}

function endpointIntegralDiagram(parameters: Record<string, number>): PlaneProblemDiagram {
  const lambda = Math.max(1, parameters.lambda ?? 1)
  const curves = [2, 6, 15].map((n, index) => ({
    kind: 'polyline' as const,
    points: Array.from({ length: 91 }, (_, pointIndex) => {
      const x = pointIndex / 90
      return point(x, Math.pow(x, n) / (1 + lambda * x))
    }),
    tone: (index === 2 ? 'accent' : index === 1 ? 'primary' : 'muted') as 'accent' | 'primary' | 'muted',
  }))
  return {
    version: 1,
    kind: 'plane',
    title: '積分核の端点集中',
    caption: 'n を大きくすると被積分関数は x=1 の近くへ集中します。図の形と正の剰余評価を組み合わせて極限を挟み撃ちします。',
    viewport: { xMin: -0.05, xMax: 1.08, yMin: -0.02, yMax: Math.max(0.38, 1 / (1 + lambda) * 1.18) },
    axes: true,
    shapes: curves,
  }
}

function formatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value)
  return String(Math.round(value * 1000) / 1000)
}

function quadraticVariationDiagram(parameters: Record<string, number>): VariationProblemDiagram {
  const a = parameters.a ?? 1
  const b = parameters.b ?? 0
  const c = parameters.c ?? 0
  const vertexX = -b / (2 * a)
  const vertexY = a * vertexX * vertexX + b * vertexX + c
  return {
    version: 1,
    kind: 'variation',
    title: '導関数の符号と増減',
    caption: `頂点 x=${formatNumber(vertexX)} の前後で導関数の符号が変わります。表とグラフを対応させて最大・最小を判定します。`,
    columns: ['-∞', formatNumber(vertexX), '+∞'],
    rows: [
      { label: "f'(x)", cells: a > 0 ? ['-', '0', '+'] : ['+', '0', '-'], tone: 'primary' },
      { label: 'f(x)', cells: a > 0 ? ['↘', formatNumber(vertexY), '↗'] : ['↗', formatNumber(vertexY), '↘'], tone: 'accent' },
    ],
  }
}

function morphismDiagram(source: ProblemArtifactSource): MorphismProblemDiagram {
  const chain = (source.morphismChain ?? []).filter(Boolean)
  const nodes = chain.length >= 2 ? chain.slice(0, 7) : [
    source.domain || 'MathematicalObject',
    'Constraint',
    'Invariant',
    'Observable',
  ]
  return {
    version: 1,
    kind: 'morphism',
    title: '解答で使う変換の順序',
    caption: '各矢印は、前の数学的対象から次の対象へ移る検証可能な変換を表します。',
    nodes,
  }
}

/**
 * Build a serializable explanatory figure from the same typed information used
 * by the solver. Unknown families fall back to the proof/morphism route rather
 * than inventing an unrelated geometric sketch.
 */
export function buildProblemDiagram(source: ProblemArtifactSource): ProblemDiagram {
  const familyId = source.familyId ?? ''
  const parameters = source.parameters ?? {}
  if (familyId.includes('parabola_right_angle_chord')) return parabolaDiagram(parameters)
  if (familyId.includes('axis_intercept_segment_swept_region')) return interceptRegionDiagram(parameters)
  if (familyId.includes('translated_disk_swept_region')) return translatedDiskDiagram(parameters)
  if (familyId.includes('rotating_rectangle_swept_region')) return rotatingRectangleDiagram(parameters)
  if (familyId.includes('fixed_chord_swept_region')) return fixedChordDiagram(parameters)
  if (familyId.includes('gambler_ruin_probability')) return gamblerStateDiagram(parameters)
  if (familyId.includes('complex_rotation_period')) return complexRotationDiagram(parameters)
  if (familyId.includes('weighted_integral') || familyId.includes('integral_endpoint') || familyId.includes('integral_state')) return endpointIntegralDiagram(parameters)
  if (familyId.includes('quadratic') && (familyId.includes('extrem') || familyId.includes('range') || familyId.includes('variation'))) {
    return quadraticVariationDiagram(parameters)
  }
  return morphismDiagram(source)
}
