'use client'

import { CheckCircle2, FileDown, FlaskConical } from 'lucide-react'
import { MathText } from '@/components/MathText'
import type { Lang } from '@/lib/mortra/i18n'
import {
  buildProblemDiagram,
  type DiagramShape,
  type PlaneProblemDiagram,
  type ProblemDiagram,
} from '@/lib/mortra/problem-artifact'
import type { CertifiedCalculusAnalysis } from '@/lib/mortra/calculus-analysis'
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

function PlaneFigure({ diagram }: { diagram: PlaneProblemDiagram }) {
  const { xMin, xMax, yMin, yMax } = diagram.viewport
  const x = (value: number) => PAD + ((value - xMin) / (xMax - xMin)) * (WIDTH - PAD * 2)
  const y = (value: number) => HEIGHT - PAD - ((value - yMin) / (yMax - yMin)) * (HEIGHT - PAD * 2)
  const rx = (value: number) => (value / (xMax - xMin)) * (WIDTH - PAD * 2)
  const ry = (value: number) => (value / (yMax - yMin)) * (HEIGHT - PAD * 2)
  const axisX = yMin <= 0 && yMax >= 0 ? y(0) : HEIGHT - PAD
  const axisY = xMin <= 0 && xMax >= 0 ? x(0) : PAD

  return (
    <svg className={styles.svg} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={diagram.title}>
      <defs>
        <pattern id="problem-grid" width="36" height="36" patternUnits="userSpaceOnUse">
          <path d="M 36 0 L 0 0 0 36" className={styles.gridLine} fill="none" />
        </pattern>
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
        return (
          <g key={index} className={toneClass(shape.tone)}>
            <circle cx={x(shape.point.x)} cy={y(shape.point.y)} r="5.5" className={styles.point} />
            {shape.label ? <text x={x(shape.point.x) + 9} y={y(shape.point.y) - 9} className={styles.pointLabel}>{shape.label}</text> : null}
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

function StateFigure({ diagram }: { diagram: Extract<ProblemDiagram, { kind: 'state' }> }) {
  const visibleEdges = diagram.transitions.filter(transition => {
    const from = diagram.states.findIndex(state => state.id === transition.from)
    const to = diagram.states.findIndex(state => state.id === transition.to)
    return from >= 0 && to >= 0 && Math.abs(from - to) === 1
  })
  return (
    <div className={styles.stateFigure} role="img" aria-label={diagram.title}>
      <svg viewBox="0 0 760 230" className={styles.stateSvg}>
        <defs>
          <marker id="state-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" className={styles.stateArrowHead} />
          </marker>
        </defs>
        {visibleEdges.map((transition, index) => {
          const from = diagram.states.findIndex(state => state.id === transition.from)
          const to = diagram.states.findIndex(state => state.id === transition.to)
          const fromX = 70 + (from * 620) / Math.max(1, diagram.states.length - 1)
          const toX = 70 + (to * 620) / Math.max(1, diagram.states.length - 1)
          const upper = to > from
          const y = upper ? 84 : 150
          return (
            <g key={`${transition.from}-${transition.to}-${index}`}>
              <path
                d={`M ${fromX + (upper ? 18 : -18)} 114 Q ${(fromX + toX) / 2} ${y} ${toX + (upper ? -22 : 22)} 114`}
                className={styles.stateEdge}
                markerEnd="url(#state-arrow)"
              />
              {transition.label ? <text x={(fromX + toX) / 2} y={upper ? y - 4 : y + 16} className={styles.stateEdgeLabel}>{transition.label}</text> : null}
            </g>
          )
        })}
        {diagram.states.slice(0, -1).map((state, index) => {
          const next = diagram.states[index + 1]
          const fromValue = Number(state.label)
          const toValue = Number(next.label)
          if (!Number.isFinite(fromValue) || !Number.isFinite(toValue) || toValue - fromValue <= 1) return null
          const fromX = 70 + (index * 620) / Math.max(1, diagram.states.length - 1)
          const toX = 70 + ((index + 1) * 620) / Math.max(1, diagram.states.length - 1)
          return <text key={`${state.id}-${next.id}-gap`} x={(fromX + toX) / 2} y="121" className={styles.stateGap}>⋯</text>
        })}
        {diagram.states.map((state, index) => {
          const cx = 70 + (index * 620) / Math.max(1, diagram.states.length - 1)
          return (
            <g key={state.id}>
              <circle
                cx={cx}
                cy="114"
                r={state.active ? 25 : 21}
                className={`${styles.stateNode} ${state.terminal ? styles.stateTerminal : ''} ${state.active ? styles.stateActive : ''}`}
              />
              <text x={cx} y="119" textAnchor="middle" className={styles.stateLabel}>{state.label}</text>
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
            <th>{diagram.variableLabel ?? 'x'}</th>
            {diagram.columns.map((column, index) => <th key={`${column}-${index}`}>{column}</th>)}
          </tr>
        </thead>
        <tbody>
          {diagram.rows.map(row => (
            <tr key={row.label} className={row.tone ? toneClass(row.tone) : undefined}>
              <th>{row.label}</th>
              {row.cells.map((cell, index) => <td key={`${row.label}-${index}`}>{cell}</td>)}
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
    obligationVerified: '検証済み',
    certificate: '証明書',
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
    obligationVerified: 'Verified',
    certificate: 'Certificate',
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
    <article className={`${styles.artifact} ${compact ? styles.compact : ''}`}>
      <header className={styles.artifactHead}>
        <div>
          <span>{verified ? 'VERIFIED SOLUTION ARTIFACT' : 'RESEARCH CANDIDATE'}</span>
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

      <ProblemFigure diagram={diagram} />

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
