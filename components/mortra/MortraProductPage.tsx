import Link from 'next/link'
import Image from 'next/image'
import {
  ArrowRight,
  BookOpenText,
  Check,
  Cpu,
  FlaskConical,
  GitBranch,
  Github,
  Languages,
  Network,
  Play,
  ShieldCheck,
} from 'lucide-react'
import { MortraTryConsole } from './MortraTryConsole'
import { ProofScrollScene } from './ProofScrollScene'
import { PipelineDiagram } from './PipelineDiagram'
import { WhyFiguresDiagram } from './WhyFiguresDiagram'
import { ArchitectureFigure } from './ArchitectureFigure'
import { AtlasFigure } from './AtlasFigure'
import ScrollSolid from '../ScrollSolid'
import { ProofGraphScene } from './ProofGraphScene'
import { getCopy, type Lang } from '@/lib/mortra/i18n'
import styles from '@/app/mortra/mortra.module.css'

const systemIcons = [Network, GitBranch, ShieldCheck, Cpu]

export function MortraProductPage({ lang = 'en' }: { lang?: Lang }) {
  const t = getCopy(lang)
  const home = lang === 'ja' ? '/ja' : '/'

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'MORTRA',
    applicationCategory: 'EducationalApplication',
    operatingSystem: 'Web',
    url: 'https://mortra.ai/',
    description: t.meta.description,
    softwareVersion: '1',
    sameAs: [
      'https://github.com/corcondor/sakumon-station',
      'https://x.com/MORTRA_AI',
    ],
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'JPY' },
  }

  return (
    <main className={styles.page}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <ProofScrollScene className={styles.proofScene} />
      <div className={styles.proofVeil} aria-hidden="true" />

      <header className={styles.nav}>
        <div className={`${styles.shell} ${styles.navInner}`}>
          <Link className={styles.wordmark} href={home} aria-label="MORTRA home">
            <span className={styles.mark}>
              <Image src="/brand/mortra-incidence-mark.svg" alt="" width={28} height={28} priority />
            </span>
            <span>MORTRA</span>
            <span className={styles.modelLabel}>Model 1</span>
          </Link>
          <nav className={styles.navLinks} aria-label={lang === 'ja' ? '主要ナビゲーション' : 'Primary navigation'}>
            <a href="#results">{t.nav.results}</a>
            <a href="#architecture">{t.nav.architecture}</a>
            <Link href="/research">{t.nav.research}</Link>
            <a
              className={styles.navIcon}
              href="https://github.com/corcondor/sakumon-station"
              target="_blank"
              rel="noreferrer"
              aria-label={lang === 'ja' ? 'MORTRAのGitHubを開く' : 'Open MORTRA on GitHub'}
              title="GitHub"
            >
              <Github size={16} aria-hidden="true" />
            </a>
            <a className={styles.navTry} href="#try"><Play size={13} aria-hidden="true" />{t.nav.try}</a>
            <Link className={styles.langToggle} href={t.langToggle.href} hrefLang={lang === 'ja' ? 'en' : 'ja'}>
              <Languages size={13} aria-hidden="true" />
              {t.langToggle.to}
            </Link>
          </nav>
        </div>
      </header>

      {/* ── HERO ───────────────────────────────────────────────────────── */}
      <section className={styles.hero}>
        <ProofGraphScene className={styles.heroScene} progress={0.68} phase="searching" running />
        <div className={styles.heroFade} />
        <div className={styles.shell}>
          <div className={styles.heroContent}>
            <p className={styles.heroWordmark}>{t.hero.slogan}</p>
            <h1 className={styles.heroTitle}>MORTRA</h1>
            <p className={styles.heroStandardModel}>{t.hero.standardModel}</p>
            <p className={styles.heroLead}>{t.hero.lead}</p>
            <div className={styles.heroActions}>
              <a className={styles.primaryButton} href="#try"><Play size={15} aria-hidden="true" />{t.hero.tryCta}</a>
              <a className={styles.secondaryButton} href="#results">{t.hero.resultsCta}<ArrowRight size={14} aria-hidden="true" /></a>
            </div>
          </div>
        </div>
      </section>

      {/* ── 01 TRY ─────────────────────────────────────────────────────── */}
      <section className={styles.section} id="try">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>{t.try.index}</p>
              <h2 className={styles.sectionTitle}>
                {t.try.title}<br /><span className={styles.noBreak}>{t.try.titleBreak}</span>
              </h2>
            </div>
            <p className={styles.sectionCopy}>{t.try.copy}</p>
          </div>
          <MortraTryConsole lang={lang} />
        </div>
      </section>

      {/* ── 02 WHY FIGURES ─────────────────────────────────────────────── */}
      <section className={styles.sectionDark} id="why">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>{t.why.index}</p>
              <h2 className={styles.sectionTitle}>{t.why.title}</h2>
            </div>
            <div className={styles.sectionCopyBlock}>
              <p className={styles.sectionCopy}>{t.why.copy}</p>
              <Link className={styles.secondaryButton} href="/research">
                <BookOpenText size={15} aria-hidden="true" />{t.why.more}<ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
          </div>
          <div className={styles.pipelineFigure}>
            <WhyFiguresDiagram lang={lang} />
          </div>
        </div>
      </section>

      {/* ── 03 RESULTS ─────────────────────────────────────────────────── */}
      <section className={styles.section} id="results">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>{t.results.index}</p>
              <h2 className={styles.sectionTitle}>{t.results.title}</h2>
            </div>
            <p className={styles.sectionCopy}>{t.results.copy}</p>
          </div>

          <div className={styles.resultMetricGrid}>
            {t.results.metrics.map(metric => (
              <article className={styles.resultMetric} data-tone={metric.tone} key={metric.label}>
                <strong>{metric.value}</strong>
                <h3>{metric.label}</h3>
                <p>{metric.body}</p>
              </article>
            ))}
          </div>

          <div className={styles.benchmarkCompare}>
            <div className={styles.benchmarkCompareHead}>
              <h3>{t.results.cross.heading}</h3>
              <p>{t.results.cross.copy}</p>
            </div>
            <ul className={styles.domainList}>
              {t.results.cross.domains.map(domain => (
                <li key={domain}><Check size={13} aria-hidden="true" />{domain}</li>
              ))}
            </ul>
            <p className={styles.benchmarkNote}>{t.results.cross.note}</p>
          </div>
        </div>
      </section>

      {/* ── 04 ARCHITECTURE ────────────────────────────────────────────── */}
      <section className={styles.sectionDark} id="architecture">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>{t.architecture.index}</p>
              <h2 className={styles.sectionTitle}>{t.architecture.title}</h2>
            </div>
            <p className={styles.sectionCopy}>{t.architecture.copy}</p>
          </div>

          <div className={styles.pipelineFigure}><ArchitectureFigure lang={lang} /></div>
          <div className={styles.pipelineFigure}><AtlasFigure lang={lang} /></div>
          <div className={styles.pipelineFigure}><PipelineDiagram lang={lang} /></div>

          <div className={styles.systemGrid}>
            {t.architecture.items.map((item, i) => {
              const Icon = systemIcons[i] ?? Network
              return (
                <article className={styles.systemItem} key={item.title}>
                  <Icon size={19} aria-hidden="true" />
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── 05 RESEARCH ────────────────────────────────────────────────── */}
      <section className={styles.section} id="research">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>{t.research.index}</p>
              <h2 className={styles.sectionTitle}>{t.vision.title}</h2>
            </div>
            <p className={styles.sectionCopy}>{t.hero.standardModel}</p>
          </div>
          <div className={styles.timeline}>
            {t.research.timeline.map(item => (
              <article className={styles.timelineItem} key={item.date}>
                <p className={styles.timelineDate}>{item.date}</p>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── VISION ─────────────────────────────────────────────────────── */}
      <section className={styles.sectionDark}>
        <div className={`${styles.shell} ${styles.visionBand}`}>
          <div className={styles.visionCopy}>
            <h2>{t.hero.slogan}</h2>
            <p>{t.vision.copy}</p>
            <div className={styles.heroActions}>
              {t.vision.chips.map((chip, i) => {
                const Icon = [GitBranch, FlaskConical, Check][i] ?? Check
                return (
                  <span className={styles.textButton} key={chip}>
                    <Icon size={14} aria-hidden="true" />{chip}
                  </span>
                )
              })}
            </div>
          </div>
          <ScrollSolid className={styles.solidScene} />
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={`${styles.shell} ${styles.footerInner}`}>
          <span>{t.footer.left}</span>
          <div className={styles.footerLinks}>
            <a href="https://github.com/corcondor/sakumon-station" target="_blank" rel="noreferrer">
              <Github size={14} aria-hidden="true" />GitHub
            </a>
            <a href="https://x.com/MORTRA_AI" target="_blank" rel="noreferrer">
              <span aria-hidden="true">X</span>@MORTRA_AI
            </a>
            <span>{t.footer.right}</span>
          </div>
        </div>
      </footer>
    </main>
  )
}
