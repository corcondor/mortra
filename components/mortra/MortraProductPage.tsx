import Link from 'next/link'
import {
  ArrowRight,
  BookOpenText,
  Check,
  Cpu,
  FlaskConical,
  GitBranch,
  Languages,
  Network,
  Play,
  ShieldCheck,
} from 'lucide-react'
import { MortraTryConsole } from './MortraTryConsole'
import { ProofScrollScene } from './ProofScrollScene'
import { RibbonMark } from './RibbonMark'
import { PipelineDiagram } from './PipelineDiagram'
import { WhyFiguresDiagram } from './WhyFiguresDiagram'
import { ArchitectureFigure } from './ArchitectureFigure'
import { AtlasFigure } from './AtlasFigure'
import ScrollSolid from '../ScrollSolid'
import { ProofGraphScene } from './ProofGraphScene'
import { getCopy, FIGURES, type Lang } from '@/lib/mortra/i18n'
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
            <span className={styles.mark}><RibbonMark size={28} cols={12} pad={9} radius={5} /></span>
            <span>MORTRA</span>
            <span className={styles.modelLabel}>Model 1</span>
          </Link>
          <nav className={styles.navLinks} aria-label={lang === 'ja' ? '主要ナビゲーション' : 'Primary navigation'}>
            <a href="#results">{t.nav.results}</a>
            <a href="#architecture">{t.nav.architecture}</a>
            <Link href="/research">{t.nav.research}</Link>
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
            <p className={styles.heroWordmark}>MORTRA</p>
            <h1 className={styles.heroSlogan}>{t.hero.slogan}</h1>
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

          {/* A. 主指標 — 同一条件のベースライン比 */}
          <div className={styles.headlineResult}>
            <p className={styles.headlineCaption}>{t.results.primary.caption}</p>
            <div className={styles.headlineRows}>
              <div className={`${styles.headlineRow} ${styles.headlineRowSelf}`}>
                <span>{t.results.primary.mortraLabel}</span>
                <div><i style={{ width: '100%' }} /></div>
                <b>{FIGURES.hageo.mortra} / {FIGURES.hageo.total}</b>
                <em>{FIGURES.hageo.pct}</em>
              </div>
              <div className={styles.headlineRow}>
                <span>{t.results.primary.newclidLabel}</span>
                <div><i style={{ width: `${(FIGURES.newclid.score / FIGURES.hageo.mortra) * 100}%` }} /></div>
                <b>{FIGURES.newclid.score} / {FIGURES.newclid.total}</b>
                <em>{FIGURES.newclid.pct}</em>
              </div>
            </div>
            <p className={styles.headlineRatio}>{t.results.primary.ratio}</p>
          </div>

          {/* B. IMO-AG-30 — ニューラル有無と対応範囲の列を足した比較 */}
          <div className={styles.benchmarkCompare}>
            <div className={styles.benchmarkCompareHead}>
              <h3>{t.results.table.heading}</h3>
              <p>{t.results.table.copy}</p>
            </div>
            <div className={styles.compareTable} role="table">
              <div className={styles.compareHead} role="row">
                <span role="columnheader">IMO-AG-30</span>
                <span role="columnheader" aria-hidden="true" />
                <span role="columnheader" aria-hidden="true" />
                <span role="columnheader">{t.results.table.colNeural}</span>
                <span role="columnheader">{t.results.table.colScope}</span>
              </div>
              {t.results.table.rows.map(row => (
                <div
                  key={row.name}
                  role="row"
                  className={[
                    styles.compareRow,
                    row.self ? styles.compareRowSelf : '',
                    row.human ? styles.compareRowHuman : '',
                  ].filter(Boolean).join(' ')}
                >
                  <span className={styles.compareName} role="cell">{row.name}</span>
                  <div className={styles.compareBar} role="cell"><i style={{ width: row.width }} /></div>
                  <b className={styles.compareScore} role="cell">{row.score}</b>
                  <span
                    className={`${styles.compareFlag} ${row.self ? styles.compareFlagGood : ''}`}
                    role="cell"
                  >
                    {row.neural}
                  </span>
                  <span
                    className={`${styles.compareFlag} ${row.self ? styles.compareFlagGood : ''}`}
                    role="cell"
                  >
                    {row.scope}
                  </span>
                </div>
              ))}
            </div>
            <p className={styles.benchmarkNote}>{t.results.table.note}</p>
          </div>

          {/* C. 幾何専用ではない — 競合がそもそも列を持たない領域 */}
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
          <span>{t.footer.right}</span>
        </div>
      </footer>
    </main>
  )
}
