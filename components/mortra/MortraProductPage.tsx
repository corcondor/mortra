import Link from 'next/link'
import Image from 'next/image'
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
    title: '探索の一部を回路で速くする',
    body: '大量に繰り返す単純な候補検査をFPGAへ移し、難しい証明はCPU側に残す分業を試しています。',
  },
]

export function MortraProductPage() {
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'MORTRA',
    applicationCategory: 'EducationalApplication',
    operatingSystem: 'Web',
    url: 'https://sakumon-web.vercel.app/',
    description: '記号推論で数学問題、図、解答、検証過程を生成する数学研究システム。',
    softwareVersion: '1',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'JPY' },
  }
  return (
    <main className={styles.page}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <header className={styles.nav}>
        <div className={`${styles.shell} ${styles.navInner}`}>
          <Link className={styles.wordmark} href="/" aria-label="MORTRA home">
            <span className={styles.mark}><Image className={styles.brandIcon} src="/mortra-mark.png" alt="" width={28} height={28} priority /></span>
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
              <h2 className={styles.sectionTitle}>問題をつなぐ。</h2>
            </div>
            <p className={styles.sectionCopy}>
              親問題を別々の証明入力として解析し、両方が不可欠になる構造だけを生成します。完成時には問題文、図、模範解答、検証結果を返します。
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
              <p>MORTRAは、DeepMindのAlphaGeometryと同じ25/30。</p>
            </div>
            <div className={styles.benchmarkRows}>
              <div className={styles.benchmarkRow}>
                <span>AlphaGeometry</span><div><i style={{ width: '83.3%' }} /></div><b>25 / 30</b>
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
            </div>
            <p className={styles.benchmarkNote}>
              形式化された同じ30題で比較。AlphaGeometry、TongGeometry、MORTRAでは探索方法と計算予算が異なります。
            </p>
          </div>

          <div className={styles.modernBenchmark}>
            <div className={styles.modernBenchmarkHead}>
              <p className={styles.sectionIndex}>CURRENT LLM REFERENCE</p>
              <h3>最近の汎用モデルは、IMO級400問でどこまで解けるか。</h3>
              <p>Google DeepMindのIMO-AnswerBench。MORTRAの25/30とは別の評価です。</p>
            </div>
            <div className={styles.modernModelTable} role="table" aria-label="IMO-AnswerBench model scores">
              <div role="row"><span role="cell">Gemini Deep Think</span><b role="cell">80.0%</b></div>
              <div role="row"><span role="cell">Grok 4</span><b role="cell">73.1%</b></div>
              <div role="row"><span role="cell">GPT-5</span><b role="cell">65.6%</b></div>
              <div role="row"><span role="cell">DeepSeek R1</span><b role="cell">60.8%</b></div>
              <div role="row"><span role="cell">Claude Opus 4</span><b role="cell">22.3%</b></div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="architecture">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>03 / ARCHITECTURE</p>
              <h2 className={styles.sectionTitle}>証明器は、協調する。</h2>
            </div>
            <p className={styles.sectionCopy}>
              発想の手掛かりは多細胞生物です。細胞は近くの細胞と情報を交換しながら、全体として一つの組織をつくります。
              MORTRAでも、異なる推論器が得意な方法を保ち、必要な途中結果だけを交換します。
            </p>
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
              <h3>単純な反復をFPGAへ</h3>
              <p>大量の候補を調べる単純な処理を回路で速くし、CPUを本当に難しい証明へ使います。</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.sectionDark} id="research">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>04 / RESEARCH</p>
              <h2 className={styles.sectionTitle}>なぜ、この形の数学AIなのか。</h2>
            </div>
            <div className={styles.sectionCopyBlock}>
              <p className={styles.sectionCopy}>
                難しい数学では、図を見る、座標へ移す、補題を立てる、反例を探す、と考え方を切り替えます。
                MORTRAは、その往復を追跡できる計算過程として実装しようとしています。
              </p>
              <Link className={styles.secondaryButton} href="/research">
                <BookOpenText size={15} aria-hidden="true" />この研究について詳しく<ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
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
            <h2>数学を、画面の外へ。</h2>
            <p>
              証明に使った点、線、円、変換の履歴を、そのまま動的な2D・3D作図へ送る。
              将来はロボットアームによる作図や立体の切断まで、同じ数学表現から実行することを目指しています。
            </p>
            <div className={styles.heroActions}>
              <span className={styles.textButton}><GitBranch size={14} aria-hidden="true" />型付き変換</span>
              <span className={styles.textButton}><FlaskConical size={14} aria-hidden="true" />再現可能な実験</span>
              <span className={styles.textButton}><Check size={14} aria-hidden="true" />たどれる証明過程</span>
            </div>
          </div>
          <ProofGraphScene className={styles.visionScene} progress={0.9} phase="complete" running />
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
