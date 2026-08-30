'use client'

import Image from 'next/image'
import { Check, ChevronRight, Copy, Pause, Play, RotateCcw, StepForward } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { Lang } from '@/lib/mortra/i18n'
import { CERTIFIED_PROOF_REPLAY } from '@/lib/mortra/research-data'
import styles from '@/app/research/research.module.css'

type TraceTab = 'trace' | 'ir' | 'certificate'

export function LiveProofObservatory({ lang }: { lang: Lang }) {
  const proof = CERTIFIED_PROOF_REPLAY
  const [activeStep, setActiveStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [tab, setTab] = useState<TraceTab>('trace')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      setActiveStep(value => (value + 1) % proof.steps.length)
    }, 1600)
    return () => window.clearInterval(timer)
  }, [playing, proof.steps.length])

  const labels = lang === 'ja'
    ? { replay: 'CERTIFIED TRACE / REPLAY', trace: '射列', ir: '型付きIR', certificate: '証明書', pause: '停止', play: '再生', reset: '最初から', next: '次の射', copied: 'コピー済み' }
    : { replay: 'CERTIFIED TRACE / REPLAY', trace: 'MORPHISMS', ir: 'TYPED IR', certificate: 'CERTIFICATE', pause: 'Pause', play: 'Play', reset: 'Restart', next: 'Next morphism', copied: 'Copied' }

  const ascii = useMemo(() => [
    '  A,B,C ───────┐',
    '  I ──foot── E,F├── polar(A)=EF ── M',
    '  O,Γ ─────────┘                  │',
    '                  tangents ── S,T ── TI∩OA ── J',
    '                                     │',
    '       eqangle(ASJ,IST) ◄── factor ◄─┘',
  ], [])

  const copyCertificate = async () => {
    await navigator.clipboard.writeText(proof.certificate)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <section className={styles.proofPanel} aria-label={lang === 'ja' ? '保存済み証明の再生' : 'Certified proof replay'}>
      <header className={styles.panelHeader}>
        <div>
          <span className={styles.replayIndicator}><i />{labels.replay}</span>
          <strong>{proof.artifact}</strong>
        </div>
        <div className={styles.iconControls}>
          <button type="button" onClick={() => setPlaying(value => !value)} title={playing ? labels.pause : labels.play} aria-label={playing ? labels.pause : labels.play}>
            {playing ? <Pause size={14} /> : <Play size={14} fill="currentColor" />}
          </button>
          <button type="button" onClick={() => { setActiveStep(0); setPlaying(true) }} title={labels.reset} aria-label={labels.reset}>
            <RotateCcw size={14} />
          </button>
          <button type="button" onClick={() => { setPlaying(false); setActiveStep(value => (value + 1) % proof.steps.length) }} title={labels.next} aria-label={labels.next}>
            <StepForward size={14} />
          </button>
        </div>
      </header>

      <div className={styles.proofStageRail} aria-label={`${activeStep + 1} / ${proof.steps.length}`}>
        {proof.steps.map((step, index) => (
          <button
            type="button"
            key={step.id}
            data-state={index < activeStep ? 'done' : index === activeStep ? 'active' : 'pending'}
            onClick={() => { setPlaying(false); setActiveStep(index) }}
            title={`${step.engine}: ${lang === 'ja' ? step.ja : step.en}`}
            aria-label={`${index + 1}. ${lang === 'ja' ? step.ja : step.en}`}
          >
            <span>{index < activeStep ? <Check size={10} /> : index + 1}</span>
          </button>
        ))}
      </div>

      <div className={styles.proofWorkspace}>
        <div className={styles.proofFigure}>
          <Image src={proof.figure} alt={lang === 'ja' ? '再生中の幾何証明図' : 'Geometry figure for the replayed proof'} fill sizes="(max-width: 900px) 100vw, 36vw" priority />
          <span>FIGURE / CONSTRUCTION STATE</span>
        </div>

        <div className={styles.terminal}>
          <div className={styles.terminalTabs} role="tablist" aria-label={lang === 'ja' ? '証明表示' : 'Proof views'}>
            {(['trace', 'ir', 'certificate'] as const).map(item => (
              <button key={item} type="button" role="tab" aria-selected={tab === item} onClick={() => setTab(item)}>
                {labels[item]}
              </button>
            ))}
          </div>

          {tab === 'trace' && (
            <div className={styles.traceView}>
              <pre aria-label={lang === 'ja' ? '証明のASCII図' : 'ASCII proof graph'}>{ascii.join('\n')}</pre>
              <ol>
                {proof.steps.map((step, index) => (
                  <li key={step.id} data-state={index < activeStep ? 'done' : index === activeStep ? 'active' : 'pending'}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <code>{step.engine}</code>
                    <p>{lang === 'ja' ? step.ja : step.en}</p>
                    <small>{step.detail}</small>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {tab === 'ir' && (
            <div className={styles.irView}>
              <code>theorem {proof.theorem}</code>
              <code>chart   {proof.chart}</code>
              <code>goal    {proof.goal}</code>
              <code>bridge  contact_polar → tangent_linear → directed_angle</code>
              <code>verify  exact_identity[{proof.identityCount}] → zero</code>
              <pre>{ascii.join('\n')}</pre>
            </div>
          )}

          {tab === 'certificate' && (
            <div className={styles.certificateView}>
              <div>
                <span>SHA-256</span>
                <button type="button" onClick={() => void copyCertificate()} aria-label={lang === 'ja' ? '証明書ハッシュをコピー' : 'Copy certificate hash'} title={copied ? labels.copied : 'SHA-256'}>
                  <Copy size={13} />
                </button>
              </div>
              <code>{proof.certificate}</code>
              <ul>
                {proof.residuals.map(residual => <li key={residual}><Check size={11} />{residual}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      <footer className={styles.proofFooter}>
        <span><i data-running={playing} />{proof.steps[activeStep].engine}</span>
        <p>{lang === 'ja' ? proof.steps[activeStep].ja : proof.steps[activeStep].en}</p>
        <code>{activeStep + 1} / {proof.steps.length}</code>
        <ChevronRight size={13} aria-hidden="true" />
      </footer>
    </section>
  )
}
