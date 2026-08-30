'use client'

import { useMemo, useState } from 'react'
import type { Lang } from '@/lib/mortra/i18n'
import styles from '@/app/research/research.module.css'

type SystemNode = {
  id: string
  x: number
  y: number
  kind: 'input' | 'representation' | 'reasoner' | 'certificate' | 'output'
  label: string
  ja: string
  en: string
}

const NODES: SystemNode[] = [
  { id: 'statement', x: 70, y: 270, kind: 'input', label: 'STATEMENT', ja: '自然文・TeX・図', en: 'Natural language, TeX and figure' },
  { id: 'typed-ir', x: 225, y: 270, kind: 'representation', label: 'TYPED IR', ja: '対象・量化・関係・目標', en: 'Objects, quantifiers, relations and goal' },
  { id: 'deduction', x: 410, y: 95, kind: 'reasoner', label: 'DEDUCTION', ja: '図形関係の前向き閉包', en: 'Forward closure of geometric relations' },
  { id: 'coordinate', x: 410, y: 205, kind: 'reasoner', label: 'COORDINATE', ja: 'アフィン・複素・三角表現', en: 'Affine, complex and trigonometric charts' },
  { id: 'ddar', x: 410, y: 315, kind: 'reasoner', label: 'DDAR', ja: '角度・比・正弦の代数', en: 'Angle, ratio and sine algebra' },
  { id: 'elimination', x: 410, y: 425, kind: 'reasoner', label: 'WU / GROEBNER', ja: '多項式消去と非退化条件', en: 'Polynomial elimination and nondegeneracy' },
  { id: 'blackboard', x: 610, y: 260, kind: 'representation', label: 'PROOF DAG', ja: '型付き中間命題を交換', en: 'Exchange typed intermediate obligations' },
  { id: 'certificate', x: 760, y: 260, kind: 'certificate', label: 'CERTIFICATE', ja: '再生・残差0・SHA-256', en: 'Replay, zero residuals and SHA-256' },
  { id: 'solution', x: 925, y: 105, kind: 'output', label: 'SOLUTION', ja: '高校数学で読める解答', en: 'Human-readable solution' },
  { id: 'figure', x: 925, y: 210, kind: 'output', label: 'FIGURE', ja: '証明と同じ状態から作図', en: 'Figure from the proof state' },
  { id: 'problem', x: 925, y: 315, kind: 'output', label: 'NEW PROBLEM', ja: '可逆チャートによる作問', en: 'Problem generation through reversible charts' },
  { id: 'design', x: 925, y: 420, kind: 'output', label: 'DESIGN', ja: '製図・建築・生成アート', en: 'Drafting, architecture and generative art' },
]

const EDGES: Array<[string, string, string]> = [
  ['statement', 'typed-ir', 'elaborate'],
  ['typed-ir', 'deduction', 'project'],
  ['typed-ir', 'coordinate', 'chart'],
  ['typed-ir', 'ddar', 'lower'],
  ['typed-ir', 'elimination', 'polynomialize'],
  ['deduction', 'blackboard', 'lemma'],
  ['coordinate', 'blackboard', 'relation'],
  ['ddar', 'blackboard', 'invariant'],
  ['elimination', 'blackboard', 'certificate fragment'],
  ['blackboard', 'deduction', 'obligation'],
  ['blackboard', 'coordinate', 'residual'],
  ['blackboard', 'ddar', 'transfer'],
  ['blackboard', 'elimination', 'ideal'],
  ['blackboard', 'certificate', 'compose'],
  ['certificate', 'solution', 'explain'],
  ['certificate', 'figure', 'render'],
  ['certificate', 'problem', 'reverse'],
  ['certificate', 'design', 'represent'],
]

const KIND_COLORS = {
  input: '#dfe9eb',
  representation: '#62d8e8',
  reasoner: '#ffb866',
  certificate: '#64e6b2',
  output: '#ff78ad',
}

export function ResearchSystemMap({ lang }: { lang: Lang }) {
  const [selected, setSelected] = useState('blackboard')
  const nodeMap = useMemo(() => new Map(NODES.map(node => [node.id, node])), [])
  const selectedNode = nodeMap.get(selected) ?? NODES[0]
  const connected = useMemo(() => new Set(EDGES.flatMap(([from, to]) => from === selected || to === selected ? [from, to] : [])), [selected])

  const curve = (from: SystemNode, to: SystemNode) => {
    const bend = Math.max(45, Math.abs(to.x - from.x) * 0.42)
    return `M ${from.x} ${from.y} C ${from.x + bend} ${from.y}, ${to.x - bend} ${to.y}, ${to.x} ${to.y}`
  }

  return (
    <div className={styles.systemMap}>
      <svg viewBox="0 0 1000 520" role="img" aria-label={lang === 'ja' ? 'MORTRAの型付き射と推論器のグラフ' : 'Graph of MORTRA typed morphisms and reasoners'}>
        <defs>
          <filter id="node-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <g className={styles.mapGrid} aria-hidden="true">
          {Array.from({ length: 20 }, (_, i) => <line key={`v${i}`} x1={i * 50} y1="0" x2={i * 50} y2="520" />)}
          {Array.from({ length: 11 }, (_, i) => <line key={`h${i}`} x1="0" y1={i * 52} x2="1000" y2={i * 52} />)}
        </g>
        <g className={styles.mapEdges}>
          {EDGES.map(([fromId, toId, label], index) => {
            const from = nodeMap.get(fromId)
            const to = nodeMap.get(toId)
            if (!from || !to) return null
            const active = selected === fromId || selected === toId
            const d = curve(from, to)
            return (
              <g key={`${fromId}-${toId}`} data-active={active}>
                <path d={d} />
                <path className={styles.mapPulse} d={d} style={{ animationDelay: `${index * -0.31}s` }} />
                {active && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 7}>{label}</text>}
              </g>
            )
          })}
        </g>
        <g className={styles.mapNodes}>
          {NODES.map(node => {
            const active = node.id === selected
            const dimmed = selected !== node.id && !connected.has(node.id)
            return (
              <g
                key={node.id}
                data-active={active}
                data-dimmed={dimmed}
                transform={`translate(${node.x} ${node.y})`}
                onPointerEnter={() => setSelected(node.id)}
                onFocus={() => setSelected(node.id)}
                role="button"
                tabIndex={0}
                aria-label={`${node.label}: ${lang === 'ja' ? node.ja : node.en}`}
              >
                <circle className={styles.mapHalo} r={active ? 25 : 18} fill={KIND_COLORS[node.kind]} />
                <circle className={styles.mapCore} r={active ? 7 : 5} fill={KIND_COLORS[node.kind]} filter={active ? 'url(#node-glow)' : undefined} />
                <text y={active ? 40 : 31}>{node.label}</text>
              </g>
            )
          })}
        </g>
      </svg>
      <div className={styles.mapInspector} data-kind={selectedNode.kind}>
        <span>{selectedNode.kind.toUpperCase()}</span>
        <strong>{selectedNode.label}</strong>
        <p>{lang === 'ja' ? selectedNode.ja : selectedNode.en}</p>
      </div>
    </div>
  )
}
