import Link from 'next/link'
import {
  ArrowRight,
  BookOpenText,
  Check,
  Cpu,
  FlaskConical,
  GitBranch,
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
import styles from '@/app/mortra/mortra.module.css'

const timeline = [
  {
    date: 'COORDINATION',
    title: '異なる証明法をつなぐ',
    body: '演繹、座標、Wu法、Groebner消去が、それぞれの得意な方法で考え、途中結果を相互に利用します。',
  },
  {
    date: 'SELF-ORGANIZATION',
    title: '局所の判断から全体解へ',
    body: '一つの大きなモデルに判断を集中させず、複数の推論器が必要な情報だけを交換して答えへ進む方法を研究しています。',
  },
  {
    date: 'ADAPTIVE SEARCH',
    title: '必要な経路だけを深く探す',
    body: '簡単な探索から始め、解けない問題だけ計算を増やします。すべての候補を同じ深さまで調べる無駄を減らします。',
  },
  {
    date: 'HARDWARE',
    title: '探索の絞り込みを、回路に落とした',
    body: '候補検査の専用回路を設計し、1サイクル1件で流せる形にしました。10,000通りの入力でソフト実装と完全一致、Xilinx 7-seriesへの論理合成も通過。次は実機に載せて測ります。',
  },
]

export function MortraProductPage() {
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'MORTRA',
    applicationCategory: 'EducationalApplication',
    operatingSystem: 'Web',
    url: 'https://mortra.vercel.app/',
    description: '記号推論で数学問題、図、解答、検証過程を生成する数学研究システム。',
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
          <Link className={styles.wordmark} href="/" aria-label="MORTRA home">
            <span className={styles.mark}><RibbonMark size={28} cols={12} pad={9} radius={5} /></span>
            <span>MORTRA</span>
            <span className={styles.modelLabel}>Model 1</span>
          </Link>
          <nav className={styles.navLinks} aria-label="主要ナビゲーション">
            <a href="#results">Results</a>
            <a href="#architecture">Architecture</a>
            <Link href="/research">Research</Link>
            <a className={styles.navTry} href="#try"><Play size={13} aria-hidden="true" />Try MORTRA</a>
          </nav>
        </div>
      </header>

      <section className={styles.hero}>
        <ProofGraphScene className={styles.heroScene} progress={0.68} phase="searching" running />
        <div className={styles.heroFade} />
        <div className={styles.shell}>
          <div className={styles.heroContent}>
            <h1>MORTRA</h1>
            <p className={styles.heroLead}>
              数学の構造をつなぎ、問題と証明をつくる。異なる証明法が協調し、答えまでの過程を検証可能な形で残します。
            </p>
            <div className={styles.heroActions}>
              <a className={styles.primaryButton} href="#try"><Play size={15} aria-hidden="true" />Try MORTRA</a>
              <a className={styles.secondaryButton} href="#results">実験結果を見る<ArrowRight size={14} aria-hidden="true" /></a>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="try">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>01 / TRY MORTRA</p>
              <h2 className={styles.sectionTitle}>
                1問を解く。<br /><span className={styles.noBreak}>2問をつなぐ。</span>
              </h2>
            </div>
            <p className={styles.sectionCopy}>
              片方だけなら入力した問題を解き、両方なら二つの構造を融合します。問題文、図、模範解答、検証結果までを一つの成果物として返します。
            </p>
          </div>
          <MortraTryConsole />
        </div>
      </section>

      <section className={styles.sectionDark} id="results">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>02 / RESULTS</p>
              <h2 className={styles.sectionTitle}>IMO幾何 25 / 30。</h2>
            </div>
            <p className={styles.sectionCopy}>
              IMO-AG-30は、国際数学オリンピックの幾何30題を集めた標準的な評価です。
              MORTRAは外部LLMを使わず、複数の記号推論法を組み合わせて25題を証明しました。
            </p>
          </div>

          <div className={styles.resultDigest}>
            <div className={styles.resultScore}>
              <span>IMO-AG-30</span>
              <strong>25<small> / 30</small></strong>
              <p><b>17題から25題へ</b> / 8題増 / 正答率 +26.7ポイント</p>
            </div>
            <div className={styles.resultSpeed}>
              <span>探索全体</span>
              <div><s>701.4秒</s><ArrowRight size={18} aria-hidden="true" /><strong>254.7秒</strong></div>
              <p><b>63.7%短縮</b> / 2.75倍高速化</p>
            </div>
            <div className={styles.resultSpeed}>
              <span>候補の列挙</span>
              <div><s>69.83秒</s><ArrowRight size={18} aria-hidden="true" /><strong>7.01秒</strong></div>
              <p><b>90.0%短縮</b> / 9.96倍高速化</p>
            </div>
          </div>

          <div className={styles.benchmarkCompare}>
            <div className={styles.benchmarkCompareHead}>
              <h3>同じIMO-AG-30で比較</h3>
              <p>MORTRAは初代AlphaGeometryと同じ25/30。AlphaGeometry2とTongGeometryは、この30題では満点です。</p>
            </div>
            <div className={styles.benchmarkRows}>
              <div className={styles.benchmarkRow}>
                <span>AlphaGeometry (2024)</span><div><i style={{ width: '83.3%' }} /></div><b>25 / 30</b>
              </div>
              <div className={styles.benchmarkRow}>
                <span>金メダリスト平均</span><div><i style={{ width: '86.3%' }} /></div><b>25.9 / 30</b>
              </div>
              <div className={`${styles.benchmarkRow} ${styles.benchmarkRowMortra}`}>
                <span>MORTRA</span><div><i style={{ width: '83.3%' }} /></div><b>25 / 30</b>
              </div>
              <div className={styles.benchmarkRow}>
                <span>TongGeometry</span><div><i style={{ width: '100%' }} /></div><b>30 / 30</b>
              </div>
              <div className={styles.benchmarkRow}>
                <span>AlphaGeometry2 (2025)</span><div><i style={{ width: '100%' }} /></div><b>30 / 30</b>
              </div>
            </div>
            <p className={styles.benchmarkNote}>
              形式化された同じ30題で比較。AlphaGeometry2はこの30題では満点で、さらに広いIMO-AG-50（2000〜2024年の幾何全50題）でも42/50＝84%です。
              幾何ではMORTRAは届いていません。ただしAlphaGeometryもTongGeometryも幾何専用で、数列・確率・積分・整数は扱えません。
              MORTRAは同じ核で幾何以外も解きます。次の2つがその結果です。
            </p>
          </div>

          <div className={styles.benchmarkCompare}>
            <div className={styles.benchmarkCompareHead}>
              <h3>幾何専用ではない</h3>
              <p>AlphaGeometryもTongGeometryも幾何しか扱えません。MORTRAは同じ核で振り分けます。</p>
            </div>
            <div className={styles.resultDigest}>
              <div className={styles.resultScore}>
                <span>オリンピアード幾何（監査済み89題）</span>
                <strong>53<small> / 89</small></strong>
                <p>ロシアARMO 11/12 ・ 中国TST 5/7 ・ IMO Shortlist 5/10 ・ CGMO 5/5</p>
              </div>

            </div>
            <p className={styles.benchmarkNote}>
証明ファイルのハッシュが一致したものだけを数えています。
            </p>
          </div>

        </div>
      </section>

      <section className={styles.section} id="architecture">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>03 / ARCHITECTURE</p>
              <h2 className={styles.sectionTitle}>権限を、面で分ける。</h2>
            </div>
            <p className={styles.sectionCopy}>
              候補を出す面、解く面、順番を決める面、真偽を決める面、速くする面。情報は下へ流れ、権限は上へ戻らない。
            </p>
          </div>

          <div className={styles.pipelineFigure}>
            <ArchitectureFigure />
          </div>

          <div className={styles.pipelineFigure}>
            <AtlasFigure />
          </div>

          <div className={styles.pipelineFigure}>
            <PipelineDiagram />
          </div>

          <div className={styles.systemGrid}>
            <article className={styles.systemItem}>
              <Network size={19} aria-hidden="true" />
              <h3>別々の方法で考える</h3>
              <p>図形の演繹、座標計算、Wu法、Groebner消去を、無理に一つの方法へ統一しません。</p>
            </article>
            <article className={styles.systemItem}>
              <GitBranch size={19} aria-hidden="true" />
              <h3>途中結果を共有する</h3>
              <p>一つの方法で証明できた事実を、別の方法でも使える形へ変換して先へ進みます。</p>
            </article>
            <article className={styles.systemItem}>
              <ShieldCheck size={19} aria-hidden="true" />
              <h3>正しさは証明で決める</h3>
              <p>どの経路を調べるかは協調して決めますが、結論の正しさは多数決ではなく証明で確認します。</p>
            </article>
            <article className={styles.systemItem}>
              <Cpu size={19} aria-hidden="true" />
              <h3>絞り込みを回路へ</h3>
              <p>候補検査の専用回路が1サイクル1件で動き、10,000通りでソフト実装と完全一致。論理合成まで通過済みです。数字は実機で測ってから出します。</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.sectionDark} id="research">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>04 / RESEARCH</p>
              <h2 className={styles.sectionTitle}>LLMは、図で説明できない。</h2>
            </div>
            <div className={styles.sectionCopyBlock}>
              <p className={styles.sectionCopy}>
                文を書いてから、別に図を描くから。
              </p>
              <Link className={styles.secondaryButton} href="/research">
                <BookOpenText size={15} aria-hidden="true" />この研究について詳しく<ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
          </div>
          <div className={styles.pipelineFigure}>
            <WhyFiguresDiagram />
          </div>

          <div className={styles.timeline}>
            {timeline.map(item => (
              <article className={styles.timelineItem} key={item.date}>
                <p className={styles.timelineDate}>{item.date}</p>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className={`${styles.shell} ${styles.visionBand}`}>
          <div className={styles.visionCopy}>
            <h2>数学の標準模型をつくる。</h2>
            <p>
              式・図・運動を、一つの構造の別の見え方として持つ。
              下の立方体は飾りではありません。断面の多角形を毎フレーム計算しています。
            </p>
            <div className={styles.heroActions}>
              <span className={styles.textButton}><GitBranch size={14} aria-hidden="true" />同じ構造を、式でも図でも運動でも</span>
              <span className={styles.textButton}><FlaskConical size={14} aria-hidden="true" />指紋を固定した実験</span>
              <span className={styles.textButton}><Check size={14} aria-hidden="true" />規則名つきの導出列</span>
            </div>
          </div>
          <ScrollSolid className={styles.solidScene} />
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={`${styles.shell} ${styles.footerInner}`}>
          <span>MORTRA / Model 1</span>
          <span>Different methods. Shared proofs. Verifiable results.</span>
        </div>
      </footer>
    </main>
  )
}
