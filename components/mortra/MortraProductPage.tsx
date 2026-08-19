import Link from 'next/link'
import { ArrowRight, Check, CircleDot, FlaskConical, GitBranch, Play } from 'lucide-react'
import { MortraTryConsole } from './MortraTryConsole'
import { ProofGraphScene } from './ProofGraphScene'
import styles from '@/app/mortra/mortra.module.css'

const timeline = [
  {
    date: '2025 / Kernel',
    title: '文章から型付き構造へ',
    body: '問題文の表層ではなく、対象・制約・量化・観測を同じ中間表現へ移す核を作りました。',
  },
  {
    date: '2026 / Proof',
    title: '証明器を競わせる',
    body: '演繹、座標、Wu法、Gröbner消去が証明書を交換し、単独で閉じない義務を引き継ぎます。',
  },
  {
    date: '2026 / Search',
    title: '探索深さを固定しない',
    body: '浅い探索から始め、未解決のときだけ候補数・深さ・補助構成を段階的に増やします。',
  },
  {
    date: '2026 / MORTRA-1',
    title: '外から使える研究へ',
    body: '親問題、探索過程、証明ロードマップ、検証結果を隠さず返す公開βを切り出しました。',
  },
]

export function MortraProductPage() {
  return (
    <main className={styles.page}>
      <header className={styles.nav}>
        <div className={`${styles.shell} ${styles.navInner}`}>
          <Link className={styles.wordmark} href="/" aria-label="MORTRA-1 home">
            <span className={styles.mark}>M</span>
            <span>MORTRA-1</span>
            <span className={styles.beta}>PUBLIC BETA</span>
          </Link>
          <nav className={styles.navLinks} aria-label="主要ナビゲーション">
            <a href="#research">Research</a>
            <a href="#evidence">Evidence</a>
            <a href="#scope">Scope</a>
            <a className={styles.navTry} href="#try"><Play size={13} aria-hidden="true" />Try MORTRA</a>
          </nav>
        </div>
      </header>

      <section className={styles.hero}>
        <ProofGraphScene className={styles.heroScene} progress={0.68} phase="searching" running />
        <div className={styles.heroFade} />
        <div className={styles.shell}>
          <div className={styles.heroContent}>
            <p className={styles.eyebrow}><span className={styles.statusDot} />Symbolic mathematical intelligence</p>
            <h1>Mathematics,<br />in motion.</h1>
            <p className={styles.heroLead}>
              MORTRAは文章を続けるモデルではありません。数学的対象を型付けし、表現の間を移動し、
              複数の記号推論器が返す証明書をつないで、問題を解き、作ります。
            </p>
            <div className={styles.heroActions}>
              <a className={styles.primaryButton} href="#try"><Play size={15} aria-hidden="true" />Try MORTRA</a>
              <a className={styles.secondaryButton} href="#evidence">検証結果を見る<ArrowRight size={14} aria-hidden="true" /></a>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section} id="try">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>01 / EXECUTE</p>
              <h2 className={styles.sectionTitle}>2つの問題から、<br />新しい構造を探す。</h2>
            </div>
            <p className={styles.sectionCopy}>
              親問題を固定端点として、字句・構文・型付き意味を解析し、合成可能な射と中間命題を探索します。
              表示しているのは作文用の演出ではなく、生成APIと長時間workerの実行状態です。
            </p>
          </div>
          <MortraTryConsole />
        </div>
      </section>

      <section className={styles.sectionDark} id="evidence">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>02 / EVIDENCE</p>
              <h2 className={styles.sectionTitle}>主張ではなく、<br />再実行できる数字。</h2>
            </div>
            <p className={styles.sectionCopy}>
              公開βには、現在のコードと対応する検証結果だけを掲載します。開発問題の成功と未見問題の失敗を分け、
              未達を製品能力として数えません。古い評価系や異なる実験条件の数字は掲載しません。
            </p>
          </div>
          <div className={styles.evidenceGrid}>
            <article className={styles.evidenceItem}>
              <div className={styles.evidenceValue}>3<span> / 3</span></div>
              <h3>幾何 capability regression</h3>
              <p>既知能力の退行検査。証明書を再生して3問すべてを閉じました。</p>
            </article>
            <article className={styles.evidenceItem}>
              <div className={styles.evidenceValue}>0<span> / 3</span></div>
              <h3>固定未見 probe</h3>
              <p>未見3問では改善未確認。これを成功扱いせず、次の研究対象として固定しています。</p>
            </article>
            <article className={styles.evidenceItem}>
              <div className={styles.evidenceValue}>27<span> / 27</span></div>
              <h3>型付き適応探索テスト</h3>
              <p>問題ID・期待解・外部LLMを使わない契約を含む回帰テストです。</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.section} id="scope">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>03 / SCOPE</p>
              <h2 className={styles.sectionTitle}>できることを、<br />混ぜない。</h2>
            </div>
            <p className={styles.sectionCopy}>
              β版、研究版、未達を明示的に分離しています。研究用の試験ルートや古い評価実装は公開画面から外し、
              Try MORTRAが返せる範囲だけを製品能力として扱います。
            </p>
          </div>
          <div className={styles.domainGrid}>
            <div className={styles.domainColumn}>
              <h3><span className={styles.scopeLive} />公開β</h3>
              <ul>
                <li>通過領域・軌跡・円と三角形</li>
                <li>幾何と代数・整数の型付き融合</li>
                <li>複素変換・漸化式・合同式</li>
                <li>一部の積分漸化式・極限</li>
              </ul>
            </div>
            <div className={styles.domainColumn}>
              <h3><span className={styles.scopeResearch} />研究版</h3>
              <ul>
                <li>補助構成を含むオリンピック幾何</li>
                <li>3次元構成と実行可能な作図</li>
                <li>位相・離散構造・整数幾何の融合</li>
                <li>自己組織化する証明器ポートフォリオ</li>
              </ul>
            </div>
            <div className={styles.domainColumn}>
              <h3><span className={styles.scopeLimit} />未達</h3>
              <ul>
                <li>任意の高校数学問題の完全自動解答</li>
                <li>全生成問題の形式証明</li>
                <li>画像だけからの頑健な図形理解</li>
                <li>未知の原始法則を常に発見すること</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.sectionDark} id="research">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionIndex}>04 / RESEARCH LOG</p>
              <h2 className={styles.sectionTitle}>結果だけでなく、<br />どう変わったか。</h2>
            </div>
            <p className={styles.sectionCopy}>
              MORTRA-1は完成宣言ではなく、外部から検証できる研究境界です。更新では能力、失敗例、証明器、
              データ分割を明記し、数字だけの改善と構造的な改善を区別します。
            </p>
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
            <p className={styles.eyebrow}><CircleDot size={13} aria-hidden="true" />From proof to construction</p>
            <h2>数学を、画面の外へ。</h2>
            <p>
              同じ構成履歴を、証明DAG、動的な2D/3D図、そして将来のロボット作図へ送る。
              文章の答えだけでなく、数学的対象がどう動き、どこで条件を満たすかを実行可能な形で残します。
            </p>
            <div className={styles.heroActions}>
              <span className={styles.textButton}><GitBranch size={14} aria-hidden="true" />Typed morphisms</span>
              <span className={styles.textButton}><FlaskConical size={14} aria-hidden="true" />Verified experiments</span>
              <span className={styles.textButton}><Check size={14} aria-hidden="true" />Reversible trace</span>
            </div>
          </div>
          <ProofGraphScene className={styles.visionScene} progress={0.9} phase="complete" running />
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={`${styles.shell} ${styles.footerInner}`}>
          <span>MORTRA-1 / PUBLIC BETA</span>
          <span>Symbolic core. Typed search. Verifiable output.</span>
        </div>
      </footer>
    </main>
  )
}
