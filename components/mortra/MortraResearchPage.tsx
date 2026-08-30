import Image from 'next/image'
import Link from 'next/link'
import type { CSSProperties } from 'react'
import {
  ArrowRight,
  ArrowUpRight,
  Braces,
  FileJson2,
  Github,
  Network,
  TerminalSquare,
} from 'lucide-react'
import { LabNotchNav } from './LabNotchNav'
import { LiveProofObservatory } from './LiveProofObservatory'
import { LiveResearchStream } from './LiveResearchStream'
import { ResearchSystemMap } from './ResearchSystemMap'
import { ShaderField } from './ShaderField'
import type { Lang } from '@/lib/mortra/i18n'
import {
  GEOMETRY_FIGURES,
  REPRESENTATION_PATHS,
  RESEARCH_METRICS,
  RESEARCH_RECORDS,
  researchText,
} from '@/lib/mortra/research-data'
import styles from '@/app/research/research.module.css'

export function MortraResearchPage({ lang = 'en' }: { lang?: Lang }) {
  const text = researchText(lang)
  const ja = lang === 'ja'
  const home = ja ? '/ja' : '/'

  return (
    <main className={styles.page} id="top">
      <ShaderField className={styles.backgroundField} />
      <div className={styles.backgroundVeil} aria-hidden="true" />
      <LabNotchNav lang={lang} active="research" />

      <section className={styles.hero}>
        <div className={styles.shell}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}><span />{text.eyebrow}</p>
            <h1>{text.title}</h1>
            <p>{text.lead}</p>
            <div className={styles.heroMeta}>
              <span><i />REPOSITORY SYNC / 60s</span>
              <span>CERTIFIED TRACE / REPLAY</span>
              <span>BRANCH / release/mortra-1-beta</span>
            </div>
          </div>

          <div className={styles.observatoryGrid}>
            <LiveProofObservatory lang={lang} />
            <LiveResearchStream lang={lang} />
          </div>
          <p className={styles.replayNote}>{text.traceNote}</p>
        </div>
      </section>

      <section className={styles.section} id="system-map">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>01 / EXECUTABLE SYSTEM MAP</p>
              <h2>{text.systemTitle}</h2>
            </div>
            <p>{text.systemCopy}</p>
          </div>
          <ResearchSystemMap lang={lang} />
        </div>
      </section>

      <section className={`${styles.section} ${styles.geometrySection}`} id="geometry-basis">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>02 / GEOMETRY AS A GENERATIVE BASIS</p>
              <h2>{text.geometryTitle}</h2>
            </div>
            <p>{text.geometryCopy}</p>
          </div>

          <div className={styles.geometryLab}>
            <div className={styles.figureStrip}>
              {GEOMETRY_FIGURES.map((figure, index) => (
                <figure key={figure.code} style={{ '--figure-index': index } as CSSProperties}>
                  <Image src={figure.src} alt={ja ? figure.ja : figure.en} fill sizes="(max-width: 700px) 45vw, 15vw" />
                  <figcaption><span>{figure.code}</span>{ja ? figure.ja : figure.en}</figcaption>
                </figure>
              ))}
            </div>

            <div className={styles.policyComparison}>
              <div className={styles.policyImage}>
                <Image
                  src="/research/same-figure-four-render-policies.png"
                  alt={ja ? '同じ意味図形を4種類の描画方針で表現した比較' : 'One semantic figure rendered with four visual policies'}
                  fill
                  sizes="(max-width: 900px) 100vw, 64vw"
                />
              </div>
              <div className={styles.policyCopy}>
                <span>ONE STRUCTURE / FOUR RENDERS</span>
                <strong>{ja ? '構成と質感を分ける。' : 'Separate construction from appearance.'}</strong>
                <p>{ja
                  ? '線・円・交点の意味は変えず、technical、ink、blueprint、washへ描画方針だけを切り替えています。'
                  : 'The lines, circles and intersections remain identical while only the technical, ink, blueprint and wash policies change.'}</p>
                <div className={styles.policyFacts}>
                  <span><b>9</b>{ja ? '既存操作' : 'existing operations'}</span>
                  <span><b>0</b>{ja ? '新規幾何射' : 'new morphisms'}</span>
                  <span><b>4</b>{ja ? '合成深さ中央値' : 'median depth'}</span>
                </div>
              </div>
            </div>

            <div className={styles.representationRail}>
              {REPRESENTATION_PATHS.map(path => (
                <div key={path.en}>
                  <span>{ja ? path.ja : path.en}</span>
                  <code>{path.detail}</code>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className={`${styles.section} ${styles.engineeringSection}`} id="engineering-geometry">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>03 / ENGINEERING GEOMETRY</p>
              <h2>{ja ? '同じ8射から、立体と図面を生成する。' : 'One set of eight morphisms produces solids and drawings.'}</h2>
            </div>
            <p>{ja
              ? '型付き構成から、厳密な3D形状、第三角法、隠れ線、断面、寸法、STEP・DXFを同時に導出します。'
              : 'A typed construction derives exact 3D geometry, third-angle views, hidden lines, sections, dimensions, STEP and DXF together.'}</p>
          </div>

          <div className={styles.engineeringPreview}>
            <div className={styles.engineeringImage}>
              <Image
                src="/research/engineering-geometry/contact-sheet.png"
                alt={ja ? 'MORTRAが生成した11部品の機械図面一覧' : 'Eleven mechanical drawings generated by MORTRA'}
                fill
                sizes="(max-width: 900px) 100vw, 70vw"
              />
            </div>
            <div className={styles.engineeringCopy}>
              <span>DIMENSION-INDEPENDENT BASIS</span>
              <strong>{ja ? '部品名を増やさず、未見の形状族まで。' : 'New shape families without adding part names.'}</strong>
              <p>{ja
                ? '基底5族、寸法未見3件、形状族未見3件を同じ演算集合で実行。11件すべてが妥当な単一B-repとして再生されました。'
                : 'Five basis families, three parameter holdouts and three topology holdouts ran through one operator set. All eleven replayed as valid single B-reps.'}</p>
              <div className={styles.engineeringFacts}>
                <span><b>8</b>{ja ? '共通射' : 'morphisms'}</span>
                <span><b>11 / 11</b>{ja ? '形状成功' : 'valid solids'}</span>
                <span><b>0</b>{ja ? '未見用の新演算' : 'new holdout ops'}</span>
              </div>
              <Link className={styles.primaryAction} href={ja ? '/ja/research/engineering-geometry' : '/research/engineering-geometry'}>
                {ja ? '実験と図面を見る' : 'Open the experiment'}<ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="evidence">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>04 / REPRODUCIBLE EVIDENCE</p>
              <h2>{text.evidenceTitle}</h2>
            </div>
            <p>{ja
              ? '異なる評価単位を一つの点数に混ぜず、それぞれの再現条件と成果物へ直接つなぎます。'
              : 'Different evaluation units remain separate, each linked to its own conditions and artifacts.'}</p>
          </div>
          <div className={styles.metricGrid}>
            {RESEARCH_METRICS.map(metric => (
              <article key={metric.en} data-tone={metric.tone}>
                <strong>{metric.value}</strong>
                <h3>{ja ? metric.ja : metric.en}</h3>
                <p>{ja ? metric.noteJa : metric.noteEn}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={`${styles.section} ${styles.recordsSection}`} id="records">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>05 / RESEARCH RECORDS</p>
              <h2>{text.recordsTitle}</h2>
            </div>
            <p>{ja
              ? '結論だけでなく、目的、方法、結果、考察、再現手順を日付つきで残しています。'
              : 'Each record keeps its objective, method, result, discussion and reproduction steps.'}</p>
          </div>
          <div className={styles.recordList}>
            {RESEARCH_RECORDS.map(record => (
              <a key={`${record.date}-${record.en}`} href={record.href} target="_blank" rel="noreferrer">
                <span>{record.date}</span>
                <div><code>{record.tag}</code><strong>{ja ? record.ja : record.en}</strong></div>
                <ArrowUpRight size={17} aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.developerSection} id="developers">
        <div className={`${styles.shell} ${styles.developerGrid}`}>
          <div className={styles.developerCopy}>
            <p className={styles.sectionIndex}>06 / FOR DEVELOPERS</p>
            <h2>{text.developerTitle}</h2>
            <p>{text.developerCopy}</p>
            <Link className={styles.primaryAction} href={`${home}#try`}>
              {ja ? 'MORTRAを実行' : 'Run MORTRA'}<ArrowRight size={14} />
            </Link>
          </div>
          <div className={styles.developerLinks}>
            <a href="https://github.com/corcondor/mortra" target="_blank" rel="noreferrer"><Github size={18} /><span><b>Repository</b><small>source / issues / commits</small></span><ArrowUpRight size={14} /></a>
            <a href="https://github.com/corcondor/mortra/tree/release/mortra-1-beta/docs/research" target="_blank" rel="noreferrer"><Braces size={18} /><span><b>Research records</b><small>method / result / discussion</small></span><ArrowUpRight size={14} /></a>
            <a href="/api/research-stream" target="_blank" rel="noreferrer"><FileJson2 size={18} /><span><b>Activity API</b><small>GitHub commits / JSON / 60s cache</small></span><ArrowUpRight size={14} /></a>
            <a href="#system-map"><Network size={18} /><span><b>System map</b><small>typed morphisms / proof DAG</small></span><ArrowUpRight size={14} /></a>
            <a href="#top"><TerminalSquare size={18} /><span><b>Certified replay</b><small>trace / typed IR / certificate</small></span><ArrowUpRight size={14} /></a>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.shell}>
          <span>MORTRA / Model 1</span>
          <span>Finite primitives. Infinite mathematics.</span>
        </div>
      </footer>
    </main>
  )
}
