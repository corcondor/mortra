import Link from 'next/link'
import {
  ArrowLeft,
  ArrowRight,
  Cpu,
  ExternalLink,
  GitBranch,
  Network,
  ShieldCheck,
} from 'lucide-react'
import { ProofGraphScene } from './ProofGraphScene'
import styles from '@/app/mortra/mortra.module.css'

export function MortraResearchPage() {
  return (
    <main className={styles.page}>
      <header className={styles.nav}>
        <div className={`${styles.shell} ${styles.navInner}`}>
          <Link className={styles.wordmark} href="/" aria-label="MORTRA-1 home">
            <span className={styles.mark}>M</span>
            <span>MORTRA-1</span>
            <span className={styles.beta}>RESEARCH</span>
          </Link>
          <nav className={styles.navLinks} aria-label="研究記事ナビゲーション">
            <Link href="/#results">Results</Link>
            <Link className={styles.navTry} href="/#try"><ArrowLeft size={13} aria-hidden="true" />Try MORTRA</Link>
          </nav>
        </div>
      </header>

      <section className={styles.researchHero}>
        <ProofGraphScene className={styles.researchHeroScene} progress={0.82} phase="verifying" running />
        <div className={styles.researchHeroShade} />
        <div className={styles.shell}>
          <div className={styles.researchHeroCopy}>
            <p className={styles.sectionIndex}>MORTRA RESEARCH / AUGUST 2026</p>
            <h1>数学AIを、ひとつの脳から、<br />協調する系へ。</h1>
            <p>
              なぜ記号推論器を協調させるのか。なぜ生物の自己組織化を参考にするのか。
              そして、なぜ数学の探索をFPGAで速くしようとしているのか。
            </p>
            <div className={styles.researchMeta}>
              <span>RESEARCH NOTE 01</span><span>約8分</span><span>再現用成果物あり</span>
            </div>
          </div>
        </div>
      </section>

      <div className={styles.researchBody}>
        <aside className={styles.researchToc}>
          <span>CONTENTS</span>
          <a href="#origin">研究の出発点</a>
          <a href="#organization">自己組織化</a>
          <a href="#proof">証明器の協調</a>
          <a href="#fpga">FPGAによる高速化</a>
          <a href="#result">得られた結果</a>
          <a href="#future">この先にあるもの</a>
        </aside>

        <article className={styles.researchArticle}>
          <section id="origin">
            <p className={styles.articleIndex}>01 / ORIGIN</p>
            <h2>研究の出発点は、数学を文章生成だけで扱うことへの違和感でした。</h2>
            <p>
              数学の問題を解くとき、人は一つの表現に留まりません。図を見て関係を予想し、座標へ移し、
              式を変形し、補題を立て、もう一度図へ戻ります。重要なのは文章の長さではなく、同じ数学的対象を
              別の表現から見直せることです。
            </p>
            <p>
              MORTRAは、問題文を「点・線・数・集合などの対象」「対象の間の関係」「証明したい結論」に分け、
              それらを動かせる形で保持します。解答は文章を一度に生成するのではなく、小さな変換と証明を積み重ねて作ります。
            </p>
            <blockquote>
              一つの万能な解法を作るのではなく、異なる数学の見方が協力できる共通基盤を作る。
            </blockquote>
          </section>

          <section id="organization">
            <p className={styles.articleIndex}>02 / SELF-ORGANIZATION</p>
            <h2>手掛かりは、多細胞生物の自己組織化です。</h2>
            <p>
              多細胞生物では、一個の細胞が身体全体を直接制御しているわけではありません。各細胞は局所的な情報を受け取り、
              周囲と信号を交換しながら、組織として一貫した働きを作ります。MORTRAでは、この考え方を複数の記号推論器へ移します。
            </p>
            <div className={styles.articlePrinciples}>
              <div><Network size={19} /><strong>局所</strong><span>各推論器は、自分が理解できる関係だけを扱う。</span></div>
              <div><GitBranch size={19} /><strong>共有</strong><span>証明できた事実と、まだ必要な条件だけを交換する。</span></div>
              <div><ShieldCheck size={19} /><strong>検証</strong><span>合意ではなく、証明を再実行して正しさを決める。</span></div>
            </div>
            <p>
              Sheaf-ADMMは、どの推論器に計算時間を配るか、どの途中結果を優先するかの調整に使います。
              連続値の合意や多数決が数学的な真偽を決めることはありません。探索の調整と証明の検証を分けることが、この設計の要点です。
            </p>
          </section>

          <section id="proof">
            <p className={styles.articleIndex}>03 / COOPERATIVE PROVING</p>
            <h2>証明器は、競争するのではなく、途中の仕事を引き継ぎます。</h2>
            <p>
              幾何の演繹は図形の関係を素早く広げられます。座標法は関係を方程式へ変えられます。
              Wu法とGroebner消去は、多項式として結論を確かめられます。どれか一つへ統一すると、他の方法の強みを失います。
            </p>
            <div className={styles.researchFlow} aria-label="MORTRA証明フロー">
              <span>図形の演繹</span><i>→</i><span>未解決の条件</span><i>→</i><span>座標・多項式</span><i>→</i><span>証明書の再実行</span>
            </div>
            <p>
              MORTRAは、途中の命題を型付きの共通形式へ変換します。これにより、ある証明器が止まった場所から、
              別の証明器が仕事を続けられます。最後に証明書を最初から再実行し、同じ結論へ到達したものだけを正答にします。
            </p>
          </section>

          <section id="fpga">
            <p className={styles.articleIndex}>04 / FPGA</p>
            <h2>FPGA化の目的は、より深く探索するための時間を作ることです。</h2>
            <p>
              難しい問題では、補助点や補助線の候補が急速に増えます。測定すると、CPU時間の多くは最終的な証明ではなく、
              「二点は同じではないか」「三点は一直線上にないか」といった単純な候補検査に使われていました。
            </p>
            <div className={styles.fpgaExplainer}>
              <Cpu size={22} aria-hidden="true" />
              <div>
                <h3>FPGAとは</h3>
                <p>用途に合わせて内部回路を書き換えられる半導体です。同じ単純計算を大量に流す処理を、並列の専用回路として実行できます。</p>
              </div>
            </div>
            <p>
              MORTRAでは、候補の列挙と明らかに使えない候補の除外だけをFPGA向け回路へ移します。
              動的な代数処理と最終的な証明はCPU側に残します。つまり、FPGAは答えを決める装置ではなく、
              証明器が調べるべき候補を高速に送り出す装置です。
            </p>
            <div className={styles.articleNumbers}>
              <div><strong>2.75×</strong><span>探索全体を高速化<br />701.4秒 → 254.7秒</span></div>
              <div><strong>9.96×</strong><span>候補列挙を高速化<br />69.83秒 → 7.01秒</span></div>
              <div><strong>1候補/clock</strong><span>FPGA回路の設計値<br />Xilinx 7-series向け</span></div>
            </div>
            <p className={styles.articleNote}>
              現在はRTLシミュレーションと論理合成まで完了しています。FPGA実機上の速度ではなく、回路として実装できることを確認した段階です。
            </p>
          </section>

          <section id="result">
            <p className={styles.articleIndex}>05 / RESULT</p>
            <h2>IMO幾何は17題から25題へ。AlphaGeometryと同数です。</h2>
            <p>
              IMO-AG-30は、2000年から2022年までの国際数学オリンピック幾何30題を形式化した評価です。
              基準となる記号推論器は17/30でした。MORTRAは複数の証明法と構成探索を統合し、25/30まで伸ばしました。
            </p>
            <div className={styles.articleScore}>
              <div><span>BASELINE</span><strong>17 / 30</strong></div>
              <ArrowRight size={22} aria-hidden="true" />
              <div><span>MORTRA</span><strong>25 / 30</strong></div>
              <div className={styles.articleScoreGain}><strong>+8題</strong><span>+26.7ポイント</span></div>
            </div>
            <p>
              DeepMindのAlphaGeometryも同じ評価で25/30を報告しています。AlphaGeometryはニューラル言語モデルと記号推論の組み合わせ、
              MORTRAは外部LLMを使わない記号推論器の協調という違いがあります。
            </p>
          </section>

          <section id="future">
            <p className={styles.articleIndex}>06 / NEXT</p>
            <h2>証明から、作問、動的な作図、ロボットによる構成へ。</h2>
            <p>
              証明の過程を点、線、円、変換の履歴として保存できれば、そのまま図を動かし、立体を切断し、
              ロボットアームへ作図命令を送れます。同じ仕組みを逆向きに使えば、条件を満たす新しい問題の探索にもつながります。
            </p>
            <p>
              MORTRAが目指しているのは、答えを文章で返すだけの数学AIではありません。
              数学的な対象を理解し、動かし、検証し、現実の作図までつなげられる計算基盤です。
            </p>
            <Link className={styles.primaryButton} href="/#try">MORTRAを試す<ArrowRight size={14} aria-hidden="true" /></Link>
          </section>

          <section className={styles.sources}>
            <p className={styles.articleIndex}>SOURCES</p>
            <h2>資料と再現結果</h2>
            <a href="https://deepmind.google/blog/alphageometry-an-olympiad-level-ai-system-for-geometry/" target="_blank" rel="noreferrer">
              Google DeepMind: AlphaGeometry <ExternalLink size={13} />
            </a>
            <a href="https://www.nature.com/articles/s42256-025-01164-x" target="_blank" rel="noreferrer">
              Nature Machine Intelligence: TongGeometry and IMO-AG-30 comparison <ExternalLink size={13} />
            </a>
            <a href="https://arxiv.org/abs/2605.31005" target="_blank" rel="noreferrer">
              Self-Organizing Multi-Agent Intelligence via Learned Sheaf-ADMM <ExternalLink size={13} />
            </a>
            <a href="https://arxiv.org/abs/2512.00097" target="_blank" rel="noreferrer">
              HAGeo: auxiliary construction search <ExternalLink size={13} />
            </a>
            <a href="https://github.com/corcondor/sakumon-station/tree/master/docs/research" target="_blank" rel="noreferrer">
              MORTRA research records and reproduction artifacts <ExternalLink size={13} />
            </a>
          </section>
        </article>
      </div>
    </main>
  )
}
