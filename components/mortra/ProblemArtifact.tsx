'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronLeft, ChevronRight, FileDown, FlaskConical, Pause, Play } from 'lucide-react'
import { MathText } from '@/components/MathText'
import { diagramMathToPlainText } from '@/lib/mortra/diagram-text'
import type { Lang } from '@/lib/mortra/i18n'
import {
  buildProblemDiagram,
  type DiagramShape,
  type PlaneProblemDiagram,
  type ProblemDiagram,
  type VisualExplanation,
} from '@/lib/mortra/problem-artifact'
import type { CertifiedCalculusAnalysis } from '@/lib/mortra/calculus-analysis'
import { certifiedFusionKind } from '@/lib/mortra/certified-fusion-kind'
import styles from './problemArtifact.module.css'

export type ProblemArtifactCard = {
  statement_tex?: string
  answer_tex?: string
  solution_tex?: string
  family_id?: string
  domain?: string
  parameters?: Record<string, number>
  morphism_chain?: string[]
  diagram?: ProblemDiagram
  visual_explanation?: VisualExplanation
  calculus_analysis?: CertifiedCalculusAnalysis
  solution_document_tex?: string
  diagram_tikz?: string
  proof_trace?: string[]
  proof_roadmap?: Array<{
    morphism_id?: string
    label_ja?: string
    source_ja?: string
    target_ja?: string
    role_ja?: string
  }>
  proof_obligations?: Array<{
    id?: string
    claim_ja?: string
    status?: string
  }>
  generation_audit?: {
    passed?: boolean
    reversePlaybackOnly?: boolean
    tracedParentIds?: string[]
    minimalPremiseIds?: string[]
    unusedPremiseIds?: string[]
    checks?: {
      premiseMinimality?: boolean
      allParentDependence?: boolean
      crossParentComposition?: boolean
    }
  }
  verification?: {
    method?: string
    exact_backend?: boolean
    independent_check?: boolean
    certificate_sha256?: string
  }
}

type Props = {
  card: ProblemArtifactCard
  compact?: boolean
  showVerification?: boolean
  lang?: Lang
}

const WIDTH = 720
const HEIGHT = 390
const PAD = 34

const toneClass = (tone: DiagramShape['tone']) => {
  if (tone === 'primary') return styles.primary
  if (tone === 'secondary') return styles.secondary
  if (tone === 'accent') return styles.accent
  return styles.muted
}

const naturalLanguagePattern = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u

function VariationValue({ value, forceMath = false }: { value: string; forceMath?: boolean }) {
  const trimmed = value.trim()
  if (!trimmed) return null
  const directional = trimmed.match(/^([\u2197\u2198])\s*(.*)$/u)
  const prefix = directional?.[1]
  const body = directional?.[2] ?? trimmed
  const plain = naturalLanguagePattern.test(body) || body === 'undefined'
  return (
    <span>
      {prefix ? <span aria-hidden="true">{prefix} </span> : null}
      {plain && !forceMath ? body : <MathText text={`\\(${body}\\)`} />}
    </span>
  )
}

function PlaneFigure({ diagram }: { diagram: PlaneProblemDiagram }) {
  const { xMin, xMax, yMin, yMax } = diagram.viewport
  const xRange = Math.max(xMax - xMin, Number.EPSILON)
  const yRange = Math.max(yMax - yMin, Number.EPSILON)
  const drawWidth = WIDTH - PAD * 2
  const drawHeight = HEIGHT - PAD * 2
  const preserveMetric = diagram.shapes.some(shape => shape.kind === 'circle' || shape.kind === 'arc')
  const uniformScale = Math.min(drawWidth / xRange, drawHeight / yRange)
  const xScale = preserveMetric ? uniformScale : drawWidth / xRange
  const yScale = preserveMetric ? uniformScale : drawHeight / yRange
  const xOffset = PAD + (drawWidth - xRange * xScale) / 2
  const yOffset = PAD + (drawHeight - yRange * yScale) / 2
  const x = (value: number) => xOffset + (value - xMin) * xScale
  const y = (value: number) => yOffset + (yMax - value) * yScale
  const rx = (value: number) => value * xScale
  const ry = (value: number) => value * yScale
  const axisX = yMin <= 0 && yMax >= 0 ? y(0) : HEIGHT - PAD
  const axisY = xMin <= 0 && xMax >= 0 ? x(0) : PAD

  return (
    <svg className={styles.svg} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={diagram.title}>
      <defs>
        <pattern id="problem-grid" width="36" height="36" patternUnits="userSpaceOnUse">
          <path d="M 36 0 L 0 0 0 36" className={styles.gridLine} fill="none" />
        </pattern>
        <marker id="plane-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="context-stroke" />
        </marker>
      </defs>
      <rect width={WIDTH} height={HEIGHT} fill="url(#problem-grid)" />
      {diagram.axes ? (
        <g className={styles.axes}>
          <line x1={PAD} y1={axisX} x2={WIDTH - PAD} y2={axisX} />
          <line x1={axisY} y1={PAD} x2={axisY} y2={HEIGHT - PAD} />
        </g>
      ) : null}
      {diagram.shapes.map((shape, index) => {
        const className = `${styles.shape} ${toneClass(shape.tone)} ${'dashed' in shape && shape.dashed ? styles.dashed : ''}`
        if (shape.kind === 'polyline') {
          const d = shape.points.map((value, pointIndex) => `${pointIndex === 0 ? 'M' : 'L'} ${x(value.x)} ${y(value.y)}`).join(' ')
          return <path key={index} d={`${d}${shape.closed ? ' Z' : ''}`} className={`${className} ${shape.fill ? styles.filled : ''}`} />
        }
        if (shape.kind === 'circle') {
          return (
            <ellipse
              key={index}
              cx={x(shape.center.x)}
              cy={y(shape.center.y)}
              rx={Math.abs(rx(shape.radius))}
              ry={Math.abs(ry(shape.radius))}
              className={className}
            />
          )
        }
        if (shape.kind === 'arc') {
          const start = (shape.startAngle * Math.PI) / 180
          const end = (shape.endAngle * Math.PI) / 180
          const startPoint = {
            x: shape.center.x + shape.radius * Math.cos(start),
            y: shape.center.y + shape.radius * Math.sin(start),
          }
          const endPoint = {
            x: shape.center.x + shape.radius * Math.cos(end),
            y: shape.center.y + shape.radius * Math.sin(end),
          }
          const span = Math.abs(shape.endAngle - shape.startAngle) % 360
          return (
            <path
              key={index}
              d={`M ${x(startPoint.x)} ${y(startPoint.y)} A ${Math.abs(rx(shape.radius))} ${Math.abs(ry(shape.radius))} 0 ${span > 180 ? 1 : 0} ${shape.endAngle >= shape.startAngle ? 0 : 1} ${x(endPoint.x)} ${y(endPoint.y)}`}
              className={className}
              markerEnd={shape.arrowEnd ? 'url(#plane-arrow)' : undefined}
            />
          )
        }
        if (shape.kind === 'vector') {
          return (
            <g key={index} className={toneClass(shape.tone)}>
              <line
                x1={x(shape.from.x)}
                y1={y(shape.from.y)}
                x2={x(shape.to.x)}
                y2={y(shape.to.y)}
                className={className}
                markerEnd="url(#plane-arrow)"
              />
              {shape.label ? (
                <text
                  x={(x(shape.from.x) + x(shape.to.x)) / 2}
                  y={(y(shape.from.y) + y(shape.to.y)) / 2 - 9}
                  textAnchor="middle"
                  className={styles.diagramLabel}
                >{diagramMathToPlainText(shape.label)}</text>
              ) : null}
            </g>
          )
        }
        if (shape.kind === 'label') {
          return (
            <text
              key={index}
              x={x(shape.point.x)}
              y={y(shape.point.y)}
              textAnchor="middle"
              className={`${styles.diagramLabel} ${toneClass(shape.tone)}`}
            >{diagramMathToPlainText(shape.text)}</text>
          )
        }
        return (
          <g key={index} className={toneClass(shape.tone)}>
            <circle cx={x(shape.point.x)} cy={y(shape.point.y)} r="5.5" className={styles.point} />
            {shape.label ? <text x={x(shape.point.x) + 9} y={y(shape.point.y) - 9} className={styles.pointLabel}>{diagramMathToPlainText(shape.label)}</text> : null}
          </g>
        )
      })}
    </svg>
  )
}

function MorphismFigure({ diagram }: { diagram: Extract<ProblemDiagram, { kind: 'morphism' }> }) {
  return (
    <div className={styles.morphismFigure} role="img" aria-label={diagram.title}>
      {diagram.nodes.map((node, index) => (
        <div className={styles.morphismStep} key={`${node}-${index}`}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <b>{node}</b>
          {index < diagram.nodes.length - 1 ? <i aria-hidden="true">→</i> : null}
        </div>
      ))}
    </div>
  )
}

function stateLabelLines(label: string): string[] {
  for (const separator of [': ', ', ']) {
    const index = label.indexOf(separator)
    if (index > 0) return [label.slice(0, index), label.slice(index + separator.length)]
  }
  return [label]
}

function StateFigure({ diagram }: { diagram: Extract<ProblemDiagram, { kind: 'state' }> }) {
  const fitStateLayout = diagram.states.length <= 3
  const stateLabel = (index: number) => diagramMathToPlainText(diagram.states[index]?.label ?? '')
  const stateRadiusX = (index: number) => {
    const longestLine = Math.max(...stateLabelLines(stateLabel(index)).map(line => Array.from(line).length))
    return Math.max(27, Math.min(74, 13 + longestLine * 6.2))
  }
  const maxStateRadiusX = Math.max(27, ...diagram.states.map((_, index) => stateRadiusX(index)))
  const canvasWidth = diagram.states.length <= 2
    ? 420
    : diagram.states.length === 3
      ? 560
      : Math.max(760, diagram.states.length * 170)
  const horizontalInset = maxStateRadiusX + 18
  const stateX = (index: number) => horizontalInset
    + (index * (canvasWidth - 2 * horizontalInset)) / Math.max(1, diagram.states.length - 1)
  const visibleEdges = diagram.transitions.filter(transition => {
    const from = diagram.states.findIndex(state => state.id === transition.from)
    const to = diagram.states.findIndex(state => state.id === transition.to)
    return from >= 0 && to >= 0 && Math.abs(from - to) === 1
  })
  const forwardTransition = (index: number) => {
    const state = diagram.states[index]
    const next = diagram.states[index + 1]
    return visibleEdges.find(transition => transition.from === state?.id && transition.to === next?.id)
      ?? visibleEdges.find(transition => transition.from === next?.id && transition.to === state?.id)
  }
  return (
    <div className={styles.stateFigure} role="img" aria-label={diagram.title}>
      <div className={styles.stateMobileFlow} aria-hidden="true">
        {diagram.states.map((state, index) => {
          const transition = index < diagram.states.length - 1 ? forwardTransition(index) : undefined
          return (
            <div className={styles.stateMobileItem} key={`mobile-${state.id}`}>
              <div
                className={`${styles.stateMobileNode} ${state.terminal ? styles.stateMobileTerminal : ''} ${state.active ? styles.stateMobileActive : ''}`}
              >
                {diagramMathToPlainText(state.label)}
              </div>
              {index < diagram.states.length - 1 ? (
                <div className={styles.stateMobileConnector}>
                  {transition?.label ? <span>{diagramMathToPlainText(transition.label)}</span> : null}
                  <i />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
      <svg
        viewBox={`0 0 ${canvasWidth} 230`}
        className={styles.stateSvg}
        style={fitStateLayout ? { minWidth: 0 } : undefined}
      >
        <defs>
          <marker id="state-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" className={styles.stateArrowHead} />
          </marker>
        </defs>
        {visibleEdges.map((transition, index) => {
          const from = diagram.states.findIndex(state => state.id === transition.from)
          const to = diagram.states.findIndex(state => state.id === transition.to)
          const fromX = stateX(from)
          const toX = stateX(to)
          const upper = to > from
          const y = upper ? 84 : 150
          const fromRadiusX = stateRadiusX(from)
          const toRadiusX = stateRadiusX(to)
          return (
            <g key={`${transition.from}-${transition.to}-${index}`}>
              <path
                d={`M ${fromX + (upper ? fromRadiusX : -fromRadiusX)} 114 Q ${(fromX + toX) / 2} ${y} ${toX + (upper ? -toRadiusX : toRadiusX)} 114`}
                className={styles.stateEdge}
                markerEnd="url(#state-arrow)"
              />
              {transition.label ? <text x={(fromX + toX) / 2} y={upper ? y - 4 : y + 16} className={styles.stateEdgeLabel}>{diagramMathToPlainText(transition.label)}</text> : null}
            </g>
          )
        })}
        {diagram.states.slice(0, -1).map((state, index) => {
          const next = diagram.states[index + 1]
          const fromValue = Number(state.label)
          const toValue = Number(next.label)
          if (!Number.isFinite(fromValue) || !Number.isFinite(toValue) || toValue - fromValue <= 1) return null
          const fromX = stateX(index)
          const toX = stateX(index + 1)
          return <text key={`${state.id}-${next.id}-gap`} x={(fromX + toX) / 2} y="121" className={styles.stateGap}>⋯</text>
        })}
        {diagram.states.map((state, index) => {
          const cx = stateX(index)
          const labelLines = stateLabelLines(stateLabel(index))
          const multiline = labelLines.length > 1
          return (
            <g key={state.id}>
              <ellipse
                cx={cx}
                cy="114"
                rx={stateRadiusX(index) + (state.active ? 3 : 0)}
                ry={state.active ? (multiline ? 31 : 27) : (multiline ? 29 : 23)}
                className={`${styles.stateNode} ${state.terminal ? styles.stateTerminal : ''} ${state.active ? styles.stateActive : ''}`}
              />
              <text
                x={cx}
                y={multiline ? 111 : 119}
                textAnchor="middle"
                className={`${styles.stateLabel} ${multiline ? styles.stateLabelMultiline : ''}`}
              >
                {labelLines.map((line, lineIndex) => (
                  <tspan key={`${state.id}-${lineIndex}`} x={cx} dy={lineIndex === 0 ? 0 : 13}>{line}</tspan>
                ))}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function VariationFigure({ diagram }: { diagram: Extract<ProblemDiagram, { kind: 'variation' }> }) {
  return (
    <div className={styles.variationWrap} role="img" aria-label={diagram.title}>
      <table className={styles.variationTable}>
        <thead>
          <tr>
            <th><VariationValue value={diagram.variableLabel ?? 'x'} forceMath /></th>
            {diagram.columns.map((column, index) => (
              <th key={`${column}-${index}`}><VariationValue value={column} forceMath /></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {diagram.rows.map(row => (
            <tr key={row.label} className={row.tone ? toneClass(row.tone) : undefined}>
              <th><VariationValue value={row.label} forceMath /></th>
              {row.cells.map((cell, index) => (
                <td key={`${row.label}-${index}`}><VariationValue value={cell} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CalculusFigure({ diagram }: { diagram: Extract<ProblemDiagram, { kind: 'calculus' }> }) {
  const variable = diagram.variable
  return (
    <div className={styles.calculusFigure}>
      <div className={styles.calculusIdentity}>
        <div><span>FUNCTION</span><MathText text={`\\(f(${variable})=${diagram.functionTex}\\)`} /></div>
        <div><span>DERIVATIVE</span><MathText text={`\\(f'(${variable})=${diagram.derivativeTex}\\)`} /></div>
        <div><span>DOMAIN</span><MathText text={`\\(${diagram.domainTex}\\)`} /></div>
      </div>
      <VariationFigure diagram={diagram.variation} />
      <PlaneFigure diagram={diagram.plot} />
      <div className={styles.calculusCertificate}>
        <span>CALCULUS CERTIFICATE</span>
        <code>{diagram.certificateMethod}</code>
      </div>
    </div>
  )
}

export function ProblemFigure({ diagram }: { diagram: ProblemDiagram }) {
  return (
    <figure className={styles.figure}>
      <div className={styles.figureHead}>
        <span>FIGURE</span>
        <strong>{diagram.title}</strong>
      </div>
      {diagram.kind === 'plane'
        ? <PlaneFigure diagram={diagram} />
        : diagram.kind === 'state'
          ? <StateFigure diagram={diagram} />
          : diagram.kind === 'variation'
            ? <VariationFigure diagram={diagram} />
            : diagram.kind === 'calculus'
              ? <CalculusFigure diagram={diagram} />
          : <MorphismFigure diagram={diagram} />}
      <figcaption>{diagram.caption}</figcaption>
    </figure>
  )
}

function VisualExplanationStepper({
  explanation,
  lang,
}: {
  explanation: VisualExplanation
  lang: Lang
}) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const steps = explanation.steps
  const activeIndex = Math.min(selectedIndex, Math.max(0, steps.length - 1))
  const activeStep = steps[activeIndex]

  const goTo = (index: number) => setSelectedIndex(Math.max(0, Math.min(steps.length - 1, index)))
  const previousLabel = lang === 'ja' ? '前の手順' : 'Previous step'
  const nextLabel = lang === 'ja' ? '次の手順' : 'Next step'
  const playLabel = lang === 'ja' ? '図解を再生' : 'Play visual explanation'
  const pauseLabel = lang === 'ja' ? '図解を一時停止' : 'Pause visual explanation'

  useEffect(() => {
    if (!playing || steps.length < 2) return undefined
    const timer = window.setTimeout(() => {
      setSelectedIndex(current => {
        if (current >= steps.length - 1) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, 2200)
    return () => window.clearTimeout(timer)
  }, [playing, activeIndex, steps.length])

  const togglePlayback = () => {
    if (!playing && activeIndex === steps.length - 1) setSelectedIndex(0)
    setPlaying(current => !current)
  }

  if (!activeStep) return null

  return (
    <section className={styles.visualStepper} aria-label={explanation.title}>
      <header className={styles.visualStepperHead}>
        <div>
          <span>VISUAL REASONING</span>
          <strong>{explanation.title}</strong>
        </div>
        <b>{String(activeIndex + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}</b>
      </header>

      <nav className={styles.visualStepNav} aria-label={lang === 'ja' ? '解答の手順' : 'Solution steps'}>
        {steps.map((step, index) => (
          <button
            type="button"
            key={step.id}
            className={index === activeIndex ? styles.visualStepActive : styles.visualStepButton}
            aria-current={index === activeIndex ? 'step' : undefined}
            aria-label={`${lang === 'ja' ? '手順' : 'Step'} ${index + 1}: ${step.title}`}
            title={step.title}
            onClick={() => goTo(index)}
          >
            {String(index + 1).padStart(2, '0')}
          </button>
        ))}
      </nav>

      <div className={styles.visualStepCopy} aria-live="polite">
        <span>{activeStep.morphism.label_ja}</span>
        <h3>{activeStep.title}</h3>
        <p>{activeStep.explanation_ja}</p>
        {activeStep.formula_tex ? (
          <div className={styles.visualStepFormula}><MathText text={activeStep.formula_tex} /></div>
        ) : null}
      </div>

      <div key={activeStep.id} className={styles.visualStepFigure}>
        <ProblemFigure diagram={activeStep.diagram} />
      </div>

      <footer className={styles.visualStepperControls}>
        <div>
          <button
            type="button"
            onClick={togglePlayback}
            aria-label={playing ? pauseLabel : playLabel}
            title={playing ? pauseLabel : playLabel}
          >
            {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={() => goTo(activeIndex - 1)}
            disabled={activeIndex === 0}
            aria-label={previousLabel}
            title={previousLabel}
          >
            <ChevronLeft size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => goTo(activeIndex + 1)}
            disabled={activeIndex === steps.length - 1}
            aria-label={nextLabel}
            title={nextLabel}
          >
            <ChevronRight size={17} aria-hidden="true" />
          </button>
        </div>
      </footer>
    </section>
  )
}

const ARTIFACT_TEXT = {
  ja: {
    saveTex: '解答TeXを保存',
    verified: '検証済み',
    candidate: '検証継続中',
    statement: '問題文',
    answer: '答え',
    undecided: '未確定',
    solution: '解答・図の読み方',
    solutionPending: '現在は型付き構造まで形成済みです。証明と反例検査が完了するまで、模範解答としては公開しません。',
    proofRoute: '証明の経路',
    proofObligations: '証明義務',
    generationAudit: '生成監査',
    generationAuditPassed: '公開条件を通過',
    generationAuditPending: '監査未完了',
    allParentsUsed: '親問題への依存',
    crossParentComposition: '構造の交差合成',
    premiseMinimality: '条件の必要性',
    obligationVerified: '検証済み',
    certificate: '証明書',
    structuralFusion: '構造融合',
    proofComposition: '証明合成',
    verifiedSolution: '検証済み解答',
    researchCandidate: '研究継続中',
  },
  en: {
    saveTex: 'Save the solution as TeX',
    verified: 'Verified',
    candidate: 'Verification in progress',
    statement: 'Statement',
    answer: 'Answer',
    undecided: 'Not yet determined',
    solution: 'Solution and how to read the figure',
    solutionPending: 'The typed structure is in place. The worked solution is withheld until the proof and counterexample search complete.',
    proofRoute: 'Proof route',
    proofObligations: 'Proof obligations',
    generationAudit: 'Generation audit',
    generationAuditPassed: 'Publication checks passed',
    generationAuditPending: 'Audit incomplete',
    allParentsUsed: 'Parent dependence',
    crossParentComposition: 'Cross-parent composition',
    premiseMinimality: 'Premise necessity',
    obligationVerified: 'Verified',
    certificate: 'Certificate',
    structuralFusion: 'Structural fusion',
    proofComposition: 'Proof composition',
    verifiedSolution: 'Verified solution',
    researchCandidate: 'Research in progress',
  },
} as const

export function ProblemArtifact({ card, compact = false, showVerification = true, lang = 'en' }: Props) {
  const a = ARTIFACT_TEXT[lang]
  const proofRoadmap = card.proof_roadmap?.length
    ? card.proof_roadmap
    : (card.morphism_chain ?? []).slice(1).map((morphismId, index, chain) => ({
        morphism_id: morphismId === 'VerifiedAnswer' ? 'certificate.replay.verify' : morphismId,
        label_ja: morphismId,
        source_ja: index === 0 ? (card.morphism_chain?.[0] ?? '問題文') : chain[index - 1],
        target_ja: morphismId,
        role_ja: lang === 'ja'
          ? '証明書に記録された型付き射を実行し、次の表現へ変換します。'
          : 'Executes the typed morphism recorded in the certificate and produces the next representation.',
      }))
  const diagram = card.diagram ?? buildProblemDiagram({
    familyId: card.family_id,
    domain: card.domain,
    parameters: card.parameters,
    morphismChain: card.morphism_chain,
    calculusAnalysis: card.calculus_analysis,
  })
  const hasResolvedAnswer = Boolean(card.answer_tex?.trim() && card.solution_tex?.trim())
  const hasCertificate = Boolean(
    card.verification?.method ||
    card.verification?.exact_backend ||
    card.verification?.independent_check,
  )
  const verified = hasResolvedAnswer && hasCertificate
  const fusionKind = certifiedFusionKind(card.family_id)
  const artifactKind = !verified
    ? 'research'
    : fusionKind === 'structural'
      ? 'structural'
      : fusionKind === 'proof_composition'
        ? 'proof-composition'
        : 'solution'
  const artifactLabel = artifactKind === 'research'
    ? a.researchCandidate
    : artifactKind === 'structural'
      ? a.structuralFusion
      : artifactKind === 'proof-composition'
        ? a.proofComposition
        : a.verifiedSolution
  const downloadTex = () => {
    if (!card.solution_document_tex) return
    const blob = new Blob([card.solution_document_tex], { type: 'application/x-tex;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = href
    anchor.download = 'mortra-solution.tex'
    anchor.click()
    URL.revokeObjectURL(href)
  }

  return (
    <article className={`${styles.artifact} ${compact ? styles.compact : ''}`} data-artifact-kind={artifactKind}>
      <header className={styles.artifactHead}>
        <div>
          <span className={styles.artifactKind}>{artifactLabel}</span>
          <strong>{card.family_id ?? 'verified.structure'}</strong>
        </div>
        <div className={styles.artifactActions}>
          {card.solution_document_tex ? (
            <button type="button" className={styles.texButton} onClick={downloadTex} title={a.saveTex}>
              <FileDown size={14} aria-hidden="true" />TeX
            </button>
          ) : null}
          {showVerification ? (
            verified
              ? <span className={styles.verified}><CheckCircle2 size={13} aria-hidden="true" />{a.verified}</span>
              : <span className={styles.candidate}><FlaskConical size={13} aria-hidden="true" />{a.candidate}</span>
          ) : null}
        </div>
      </header>

      <section className={styles.statementSection}>
        <p className={styles.label}>{a.statement}</p>
        <div className={styles.statement}><MathText text={card.statement_tex ?? ''} large={!compact} /></div>
      </section>

      {card.visual_explanation?.steps.length ? (
        <VisualExplanationStepper explanation={card.visual_explanation} lang={lang} />
      ) : (
        <ProblemFigure diagram={diagram} />
      )}

      <div className={styles.solutionGrid}>
        <section>
          <p className={styles.label}>{a.answer}</p>
          <div className={styles.answer}><MathText text={card.answer_tex?.trim() || a.undecided} large /></div>
        </section>
        <section>
          <p className={styles.label}>{a.solution}</p>
          <div className={styles.solution}>
            <MathText text={card.solution_tex?.trim() || a.solutionPending} />
          </div>
        </section>
      </div>

      {proofRoadmap.length ? (
        <section className={styles.proofAudit} aria-labelledby="proof-route-title">
          <div className={styles.proofAuditHead}>
            <p className={styles.label} id="proof-route-title">{a.proofRoute}</p>
            <span>{proofRoadmap.length} MORPHISMS</span>
          </div>
          <ol className={styles.proofRouteList}>
            {proofRoadmap.map((step, index) => (
              <li className={styles.proofRouteItem} key={`${step.morphism_id ?? 'morphism'}-${index}`}>
                <span className={styles.proofRouteIndex}>{String(index + 1).padStart(2, '0')}</span>
                <div className={styles.proofRouteBody}>
                  <strong>{step.label_ja || step.morphism_id || `Morphism ${index + 1}`}</strong>
                  {(step.source_ja || step.target_ja) ? (
                    <div className={styles.proofRouteMap}>
                      <span>{step.source_ja || '入力'}</span>
                      <i aria-hidden="true">→</i>
                      <span>{step.target_ja || '出力'}</span>
                    </div>
                  ) : null}
                  {step.role_ja ? <p>{step.role_ja}</p> : null}
                  {step.morphism_id ? <code>{step.morphism_id}</code> : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {card.proof_obligations?.length ? (
        <section className={styles.obligationAudit} aria-labelledby="proof-obligations-title">
          <div className={styles.proofAuditHead}>
            <p className={styles.label} id="proof-obligations-title">{a.proofObligations}</p>
            <span>{card.proof_obligations.length} CHECKS</span>
          </div>
          <ul className={styles.obligationList}>
            {card.proof_obligations.map((obligation, index) => {
              const obligationId = obligation.id || `O${index + 1}`
              const obligationVerified = obligation.status === 'verified'
              return (
                <li className={styles.obligationItem} key={`${obligationId}-${index}`}>
                  <CheckCircle2
                    size={16}
                    aria-hidden="true"
                    className={obligationVerified ? styles.obligationCheck : styles.obligationPending}
                  />
                  <div>
                    <span>{obligationId} / {obligationVerified ? a.obligationVerified : obligation.status || a.candidate}</span>
                    <p>{obligation.claim_ja || a.solutionPending}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      ) : null}

      {card.generation_audit ? (
        <section className={styles.obligationAudit} aria-labelledby="generation-audit-title">
          <div className={styles.proofAuditHead}>
            <p className={styles.label} id="generation-audit-title">{a.generationAudit}</p>
            <span>{card.generation_audit.passed ? a.generationAuditPassed : a.generationAuditPending}</span>
          </div>
          <ul className={styles.obligationList}>
            {[
              {
                id: 'parent-dependence',
                label: a.allParentsUsed,
                passed: card.generation_audit.checks?.allParentDependence === true,
                detail: lang === 'ja'
                  ? `${card.generation_audit.tracedParentIds?.length ?? 0}件の親問題を最終目標まで逆追跡しました。`
                  : `Traced ${card.generation_audit.tracedParentIds?.length ?? 0} parents to the final goal.`,
              },
              {
                id: 'cross-parent-composition',
                label: a.crossParentComposition,
                passed: card.generation_audit.checks?.crossParentComposition === true,
                detail: lang === 'ja'
                  ? '異なる親問題の途中結果を一つの証明操作で合成しました。'
                  : 'Combined intermediate results from distinct parents in one proof operation.',
              },
              {
                id: 'premise-minimality',
                label: a.premiseMinimality,
                passed: card.generation_audit.checks?.premiseMinimality === true,
                detail: lang === 'ja'
                  ? `未使用の条件は${card.generation_audit.unusedPremiseIds?.length ?? 0}件です。`
                  : `${card.generation_audit.unusedPremiseIds?.length ?? 0} unused premises.`,
              },
            ].map(item => (
              <li className={styles.obligationItem} key={item.id}>
                <CheckCircle2
                  size={16}
                  aria-hidden="true"
                  className={item.passed ? styles.obligationCheck : styles.obligationPending}
                />
                <div>
                  <span>{item.label} / {item.passed ? a.obligationVerified : a.candidate}</span>
                  <p>{item.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {showVerification && card.verification?.method ? (
        <footer className={styles.verificationLine}>
          <div>
            <span>VERIFY</span>
            <code>{card.verification.method}</code>
          </div>
          {card.verification.certificate_sha256 ? (
            <div>
              <span>{a.certificate}</span>
              <code>{card.verification.certificate_sha256}</code>
            </div>
          ) : null}
        </footer>
      ) : null}
    </article>
  )
}
