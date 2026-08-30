'use client'

import { useMemo, useState } from 'react'
import type { Lang } from '@/lib/mortra/i18n'
import styles from '@/app/mortra/mortra.module.css'

type MapProps = {
  lang: Lang
  phase: string
  progress: number
  running: boolean
  inputCount: 1 | 2
  residual?: number | null
  frontier?: number | null
}

type RouteNode = {
  id: string
  label: string
  ja: string
  en: string
  depth: number
  mixture: [number, number, number]
  kind: 'input' | 'representation' | 'engine' | 'obligation' | 'certificate'
  residual: number
}

const NODES: RouteNode[] = [
  { id: 's0', label: 'S₀', ja: '入力端点', en: 'Input endpoint', depth: 0, mixture: [0.82, 0.12, 0.06], kind: 'input', residual: 1 },
  { id: 'ir', label: 'N₁', ja: '型付き意味IR', en: 'Typed semantic IR', depth: 1, mixture: [0.64, 0.25, 0.11], kind: 'representation', residual: 0.81 },
  { id: 'dd', label: 'D₂', ja: '関係閉包', en: 'Relational closure', depth: 2, mixture: [0.72, 0.1, 0.18], kind: 'engine', residual: 0.58 },
  { id: 'chart', label: 'C₂', ja: '座標チャート', en: 'Coordinate chart', depth: 2, mixture: [0.22, 0.69, 0.09], kind: 'engine', residual: 0.53 },
  { id: 'ar', label: 'A₃', ja: '角度・比の代数', en: 'Angle and ratio algebra', depth: 3, mixture: [0.16, 0.64, 0.2], kind: 'engine', residual: 0.34 },
  { id: 'open', label: 'O₃', ja: '未閉鎖の証明義務', en: 'Open proof obligation', depth: 3, mixture: [0.43, 0.36, 0.21], kind: 'obligation', residual: 0.42 },
  { id: 'dag', label: 'P₄', ja: '証明DAG', en: 'Proof DAG', depth: 4, mixture: [0.33, 0.34, 0.33], kind: 'representation', residual: 0.17 },
  { id: 'cert', label: 'Q₅', ja: '検証済み証明書', en: 'Verified certificate', depth: 5, mixture: [0.07, 0.12, 0.81], kind: 'certificate', residual: 0 },
]

const EDGES: Array<[string, string, string]> = [
  ['s0', 'ir', 'elaborate'],
  ['ir', 'dd', 'deduce'],
  ['ir', 'chart', 'project'],
  ['dd', 'ar', 'transfer'],
  ['chart', 'ar', 'normalize'],
  ['dd', 'open', 'residual'],
  ['chart', 'open', 'counterexample'],
  ['ar', 'dag', 'lemma'],
  ['open', 'dag', 'discharge'],
  ['dag', 'cert', 'compose'],
]

const KIND_COLOR = {
  input: '#d7e2e5',
  representation: '#62d8e8',
  engine: '#ffb866',
  obligation: '#ff78ad',
  certificate: '#64e6b2',
}

function fisherRao(a: RouteNode['mixture'], b: RouteNode['mixture']) {
  const affinity = a.reduce((sum, value, index) => sum + Math.sqrt(value * b[index]), 0)
  return 2 * Math.acos(Math.min(1, Math.max(-1, affinity)))
}

function project(mixture: RouteNode['mixture']) {
  const h = mixture.map(Math.sqrt) as [number, number, number]
  return {
    x: 430 + (h[1] - h[0]) * 450,
    y: 245 - (2 * h[2] - h[0] - h[1]) * 142,
  }
}

export function InformationGeometryMap({ lang, phase, progress, running, inputCount, residual, frontier }: MapProps) {
  const [selected, setSelected] = useState('dag')
  const nodes = useMemo(() => inputCount === 1 ? NODES : [
    ...NODES,
    { id: 's1', label: 'S₁', ja: '第二端点', en: 'Second endpoint', depth: 0, mixture: [0.77, 0.08, 0.15], kind: 'input', residual: 1 } satisfies RouteNode,
  ], [inputCount])
  const edges = useMemo(() => inputCount === 1 ? EDGES : [['s1', 'ir', 'elaborate'], ...EDGES] as Array<[string, string, string]>, [inputCount])
  const byId = useMemo(() => new Map(nodes.map(node => [node.id, node])), [nodes])
  const selectedNode = byId.get(selected) ?? nodes[0]
  const reachedDepth = phase === 'complete' ? 5 : Math.max(0, Math.min(5, progress * 5.35))

  return (
    <section className={styles.informationMap} aria-label={lang === 'ja' ? '情報幾何学的な証明探索地図' : 'Information-geometric proof exploration map'}>
      <header className={styles.runtimePaneHeader}>
        <div>
          <span>INFORMATION-GEOMETRIC PROOF MAP</span>
          <small>{lang === 'ja' ? '平方根写像によるFisher–Rao球面の2次元射影' : '2D projection of the Fisher–Rao sphere through the square-root map'}</small>
        </div>
        <div className={styles.mapLegend}>
          <span><i data-tone="representation" />IR</span>
          <span><i data-tone="engine" />ENGINE</span>
          <span><i data-tone="obligation" />OPEN</span>
          <span><i data-tone="certificate" />CERTIFIED</span>
        </div>
      </header>

      <div className={styles.informationMapCanvas}>
        <svg viewBox="0 0 920 490" role="img">
          <defs>
            <filter id="ig-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          <g className={styles.metricContours} aria-hidden="true">
            {[0, 1, 2, 3].map(index => <ellipse key={index} cx="458" cy="248" rx={170 + index * 88} ry={68 + index * 38} />)}
            <line x1="38" y1="410" x2="880" y2="410" />
            <line x1="74" y1="35" x2="74" y2="438" />
            <text x="825" y="432">θ₁ / chart balance</text>
            <text x="82" y="53">θ₂ / verified mass</text>
          </g>
          <g className={styles.informationEdges}>
            {edges.map(([fromId, toId, morphism], index) => {
              const from = byId.get(fromId)
              const to = byId.get(toId)
              if (!from || !to) return null
              const a = project(from.mixture)
              const b = project(to.mixture)
              const active = to.depth <= reachedDepth
              const path = `M ${a.x} ${a.y} Q ${(a.x + b.x) / 2} ${(a.y + b.y) / 2 - 18}, ${b.x} ${b.y}`
              return (
                <g key={`${fromId}-${toId}`} data-active={active}>
                  <path d={path} />
                  <path className={styles.informationFlow} d={path} style={{ animationDelay: `${index * -0.32}s` }} />
                  <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 13}>{morphism} · d={fisherRao(from.mixture, to.mixture).toFixed(2)}</text>
                </g>
              )
            })}
          </g>
          <g className={styles.informationNodes}>
            {nodes.map(node => {
              const point = project(node.mixture)
              const active = node.depth <= reachedDepth
              const selectedState = selected === node.id
              const radius = 7 + node.residual * 5
              return (
                <g
                  key={node.id}
                  transform={`translate(${point.x} ${point.y})`}
                  data-active={active}
                  data-selected={selectedState}
                  role="button"
                  tabIndex={0}
                  onPointerEnter={() => setSelected(node.id)}
                  onFocus={() => setSelected(node.id)}
                  aria-label={`${node.label}: ${lang === 'ja' ? node.ja : node.en}`}
                >
                  <circle r={radius + 10} fill={KIND_COLOR[node.kind]} opacity={selectedState ? 0.2 : 0.07} />
                  <circle r={radius} fill={KIND_COLOR[node.kind]} filter={selectedState ? 'url(#ig-glow)' : undefined} />
                  <text y={radius + 21}>{node.label}</text>
                </g>
              )
            })}
          </g>
        </svg>

        <aside className={styles.mapInspectorPanel} data-kind={selectedNode.kind}>
          <span>{selectedNode.kind.toUpperCase()} / DEPTH {selectedNode.depth}</span>
          <strong>{selectedNode.label} · {lang === 'ja' ? selectedNode.ja : selectedNode.en}</strong>
          <div>
            <code>p = [{selectedNode.mixture.map(value => value.toFixed(2)).join(', ')}]</code>
            <code>r = {(selectedNode.id === 'open' && typeof residual === 'number' ? residual : selectedNode.residual).toExponential(2)}</code>
            <code>frontier = {frontier ?? (selectedNode.kind === 'obligation' ? 1 : 0)}</code>
          </div>
        </aside>
      </div>

      <footer className={styles.mapMethodNote}>
        <span><i data-running={running} />{phase.toUpperCase()}</span>
        <p>{lang === 'ja'
          ? '各点は推論器の混合比 p を持ち、√p を単位球面へ写した位置です。円の大きさは未消去残差を表します。'
          : 'Each state has a reasoner mixture p; its position projects √p on the unit sphere. Radius encodes unresolved residual.'}</p>
      </footer>
    </section>
  )
}
