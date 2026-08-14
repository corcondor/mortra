'use client'

import { useEffect, useRef } from 'react'
import katex from 'katex'
import './landing.css'

/* 作問ノート — Sakumon by MORTRA ランディング
 * Anthropic Frontend Design メソッドで設計された静的デザインの
 * Next.js 移植版。.sakumon-landing を body に付与して CSS をスコープする。
 */

function MathDisplay({ tex, className = '' }: { tex: string; className?: string }) {
  const html = katex.renderToString(tex.trim(), {
    displayMode: true,
    throwOnError: false,
    strict: false,
  })
  return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

const STAGES = ['経路探索', '型構成', '構造登録', '新規性', '厳密検証', '保存'] as const

export default function Landing() {
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    /* ---------- スクロール出現 ---------- */
    const revealEls = Array.from(root.querySelectorAll<HTMLElement>('.reveal'))
    let io: IntersectionObserver | null = null
    if (reduced || !('IntersectionObserver' in window)) {
      revealEls.forEach((el) => el.classList.add('is-in'))
    } else {
      io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-in')
              io?.unobserve(entry.target)
            }
          })
        },
        { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
      )
      revealEls.forEach((el) => io?.observe(el))
    }

    /* ---------- 生成工程パイプライン ---------- */
    const stagesEl = root.querySelector<HTMLOListElement>('#pipeline-stages')
    const tokenEl = root.querySelector<HTMLElement>('#pipeline-token')
    const statusEl = root.querySelector<HTMLElement>('#pipeline-status')
    let timer: ReturnType<typeof setInterval> | null = null
    let idx = 0
    const advance = () => {
      if (!stagesEl || !tokenEl || !statusEl) return
      const items = Array.from(stagesEl.children) as HTMLLIElement[]
      items.forEach((li) => li.classList.remove('is-active'))
      items[idx].classList.add('is-active')
      statusEl.textContent = items[idx].getAttribute('data-stage')
      tokenEl.style.transform = `translateX(${idx * 100}%)`
      idx = (idx + 1) % items.length
    }
    if (stagesEl && tokenEl && statusEl) {
      advance()
      if (!reduced) {
        timer = setInterval(advance, 2400)
        const onVis = () => {
          if (document.hidden) {
            if (timer) clearInterval(timer)
            timer = null
          } else if (!timer) {
            timer = setInterval(advance, 2400)
          }
        }
        document.addEventListener('visibilitychange', onVis)
        return () => {
          document.removeEventListener('visibilitychange', onVis)
          if (timer) clearInterval(timer)
          io?.disconnect()
        }
      } else {
        tokenEl.style.transform = 'translateX(0%)'
      }
    }

    /* ---------- トップバー ---------- */
    const bar = root.querySelector<HTMLElement>('#topbar')
    const onScroll = () => bar?.classList.toggle('is-scrolled', window.scrollY > 8)
    if (bar) {
      window.addEventListener('scroll', onScroll, { passive: true })
      onScroll()
    }

    return () => {
      io?.disconnect()
      if (timer) clearInterval(timer)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])

  return (
    <div ref={rootRef} className="sakumon-landing">
      <div className="topbar" id="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#top" aria-label="Sakumon ホームへ">
            <span className="brand-mark">Σ</span>
            <span className="brand-name">
              Sakumon<em> by MORTRA</em>
            </span>
          </a>
          <nav className="topnav" aria-label="ページ内ナビゲーション">
            <a href="#flow">工程</a>
            <a href="#engine">MathOS</a>
            <a href="#review">レビュー</a>
            <a href="#exams">過去問DB</a>
            <a href="#pricing">料金</a>
          </nav>
          <a className="btn btn-primary btn-small" href="#pricing">
            ワークスペースに入る
          </a>
        </div>
      </div>

      <main className="page">
        {/* ============ HERO ============ */}
        <section className="hero" id="top">
          <div className="hero-rule" aria-hidden="true"></div>
          <div className="hero-grid" aria-hidden="true"></div>

          <div className="hero-copy">
            <p className="eyebrow reveal">表現の間を移動する研究基盤 MORTRA の、最初の応用です。</p>
            <h1 className="hero-title reveal">
              数学問題を<span className="red">つくる</span>人のための
              <br />
              作業場。
            </h1>
            <p className="hero-lead reveal">
              種を選び、生成し、検証し、比べ、直し、図にし、書き出す。
              <br />
              作問の全工程を一つの画面で扱います。
            </p>
            <div className="hero-actions reveal">
              <a className="btn btn-primary" href="#pricing">
                ワークスペースに入る
              </a>
              <a className="btn btn-ghost" href="#exams">
                過去問DBをのぞく
              </a>
            </div>
            <p className="hero-auth-note reveal">
              Google アカウントで認証します。認証後、問題一覧・生成履歴・過去問DBを利用できます。
            </p>

            <div className="pipeline reveal" aria-label="生成工程">
              <div className="pipeline-label">
                <span>生成工程</span>
                <span className="pipeline-status" id="pipeline-status">
                  経路探索
                </span>
              </div>
              <ol className="pipeline-stages" id="pipeline-stages">
                {STAGES.map((s, i) => (
                  <li key={s} data-stage={s} className={i === 0 ? 'is-active' : ''}>
                    {s}
                  </li>
                ))}
              </ol>
              <div className="pipeline-track">
                <span className="pipeline-token" id="pipeline-token" aria-hidden="true"></span>
              </div>
            </div>
          </div>

          {/* 作問ノート : シグネチャカード */}
          <aside className="notebook reveal" aria-label="作問ノートの例">
            <div className="notebook-ruling" aria-hidden="true"></div>
            <header className="notebook-head">
              <span className="note-no">問題 No.1247</span>
              <span className="note-gen">Gen 7</span>
              <span className="badge badge-b">B 難</span>
            </header>

            <div className="note-body">
              <p className="note-kicker">問題文</p>
              <p className="note-problem">
                <MathDisplay tex={String.raw`\text{実数 } x,\,y \text{ が } x^{2}+y^{2}=1 \text{ を満たすとき, } xy \text{ の最小値を求めよ。}`} />
              </p>

              <p className="note-kicker">答え</p>
              <p className="note-answer">
                <MathDisplay tex={String.raw`\boxed{-\dfrac{1}{2}}`} />
              </p>

              <p className="note-kicker">図プレビュー</p>
              <div className="note-figure">
                <svg viewBox="0 0 200 200" role="img" aria-label="単位円と極小点の図">
                  <g className="fig-axes">
                    <line x1="12" y1="100" x2="188" y2="100" />
                    <line x1="100" y1="12" x2="100" y2="188" />
                  </g>
                  <circle cx="100" cy="100" r="70" />
                  <line x1="100" y1="100" x2="100" y2="149.5" />
                  <line x1="100" y1="149.5" x2="149.5" y2="149.5" />
                  <line x1="100" y1="100" x2="149.5" y2="149.5" className="fig-min" />
                  <circle cx="149.5" cy="149.5" r="4" />
                  <g className="fig-labels">
                    <text x="154" y="148">
                      P
                    </text>
                    <text x="16" y="188">
                      O
                    </text>
                  </g>
                </svg>
              </div>

              <p className="note-kicker">評価</p>
              <ul className="note-scores">
                {[
                  ['意外性', '72%', '72'],
                  ['ミニマル', '91%', '91'],
                  ['接続性', '84%', '84'],
                  ['必然性', '88%', '88'],
                  ['計算難度', '35%', '35'],
                ].map(([label, w, val]) => (
                  <li key={label}>
                    <span>{label}</span>
                    <i className="score-bar">
                      <b style={{ '--w': w } as React.CSSProperties}></b>
                    </i>
                    <em>{val}</em>
                  </li>
                ))}
              </ul>

              <div className="note-stamps">
                <span className="stamp stamp-ok">検証済み</span>
                <span className="stamp stamp-ok">cvc5 検査</span>
                <span className="stamp stamp-red">独立監査済</span>
              </div>
            </div>

            <footer className="note-foot">
              <span>親: 円の軌跡 / 相加・相乗平均</span>
              <span className="note-date">検証 14:32 · 3 段</span>
            </footer>
          </aside>
        </section>

        {/* ============ 工程 一〜七 ============ */}
        <section className="flow" id="flow">
          <header className="section-head reveal">
            <p className="section-eyebrow">工程 — 一画面に収まった作問</p>
            <h2 className="section-title">つくる、の全工程。</h2>
            <p className="section-sub">
              種から書き出しまで。画面を切り替えずに、作問の流れを一周できます。
            </p>
          </header>

          <ol className="flow-list">
            {[
              ['一', '種を選ぶ', '過去問DB・自作・MathOSの最新問題から「種」を選びます。選んだ問題は、融合・類題生成の親になります。', '過去問DB / 自作 / 最新MathOS'],
              ['二', '生成する', '融合生成・一括類題・深層探索。2問以上を選ぶと、構造を混ぜて新しい問題を構成します。', '融合生成 / 一括類題 / 深層探索'],
              ['三', '検証する', '形式計算・独立監査・cvc5検査。答えと証明書が揃わなければ、問題は保存されません。', '形式計算済 / 独立監査済 / cvc5検査'],
              ['四', '比べる', '意外性・ミニマル・接続性・必然性・計算難度の5軸でスコアリング。総合スコアで一覧に並びます。', '5軸スコア / 総合順'],
              ['五', '直す', '修正後の答えを入力（LaTeX可）。構造は「修復候補」として残り、あとで再利用できます。', '答え修正（LaTeX可） / 修復候補'],
              ['六', '図にする', 'TikZコードをコンパイル検証して図プレビュー。PDF保存でそのままプリントに載せられます。', 'TikZ / コンパイル検証済 / PDF保存'],
              ['七', '書き出す', '問題文と解答を画像にしてXへ投稿。WolframAlphaでの簡約化検証も、そのまま同じ画面で。', 'X投稿（画像添付） / Wolfram検証'],
            ].map(([no, name, desc, tag]) => (
              <li className="flow-row reveal" key={no}>
                <span className="flow-no">{no}</span>
                <h3 className="flow-name">{name}</h3>
                <p className="flow-desc">{desc}</p>
                <p className="flow-tag">{tag}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ============ MathOS : 黒板 ============ */}
        <section className="engine" id="engine">
          <div className="engine-grid" aria-hidden="true"></div>
          <div className="engine-inner">
            <header className="section-head reveal">
              <p className="section-eyebrow">MathOS — 作問エンジン</p>
              <h2 className="section-title">生成は、検証のついた証明付きで。</h2>
              <p className="section-sub">
                MathOSは圏論スタイルの型付き対象と射で問題を構成します。探索から保存まで6工程。途中のすべてに証明書が残ります。
              </p>
            </header>

            <ol className="engine-stages">
              {[
                ['01', '経路探索', '構成可能な経路を探索しています'],
                ['02', '型構成', '親問題から型付き対象と観測を導出しています'],
                ['03', '構造登録', '実行可能な射列をDBへ記録しています'],
                ['04', '新規性', '既存問題との同型・表層類似を調べています'],
                ['05', '厳密検証', '解と独立検算の証明書を確認しています'],
                ['06', '保存', '検証済み問題を保存しました'],
              ].map(([no, name, desc]) => (
                <li className="estage reveal" key={no}>
                  <span className="estage-no">{no}</span>
                  <h3>{name}</h3>
                  <p>{desc}</p>
                </li>
              ))}
            </ol>

            <ul className="engine-chips reveal" aria-label="検証要素">
              <li>探索証明書</li>
              <li>融合証明書 — 全親が不可欠</li>
              <li>親除去テスト: 通過</li>
              <li>構造正規形 一意</li>
              <li>有限解証明済み</li>
              <li>cvc5</li>
              <li>egglog</li>
            </ul>

            <p className="engine-note reveal">
              <span className="note-sym">＊</span>
              探索ジョブは8時間を超えてバックグラウンド研究を継続できます。次回アクセス時に自動再接続します。
            </p>
          </div>
        </section>

        {/* ============ レビュー ============ */}
        <section className="review" id="review">
          <header className="section-head reveal">
            <p className="section-eyebrow">レビュー — 採点と保存</p>
            <h2 className="section-title">生成された問題は、あなたが採点する。</h2>
            <p className="section-sub">
              問題を比較し、選択した候補を「選択・生成」で融合・類題生成できます。状態は5種類、評価は6軸。
            </p>
          </header>

          <div className="review-grid">
            <div className="review-stamps reveal" aria-label="レビュー状態">
              <h3>状態</h3>
              <ul>
                <li>
                  <span className="stamp stamp-plain">未判定</span>
                </li>
                <li>
                  <span className="stamp stamp-ok">選択済み</span>
                </li>
                <li>
                  <span className="stamp stamp-ok">投稿済み</span>
                </li>
                <li>
                  <span className="stamp stamp-red">除外</span>
                </li>
                <li>
                  <span className="stamp stamp-red">要修正</span>
                </li>
              </ul>
            </div>

            <div className="review-axes reveal" aria-label="評価軸">
              <h3>評価の6軸</h3>
              <ul>
                {[
                  ['意外性', '72%'],
                  ['ミニマル', '91%'],
                  ['接続性', '84%'],
                  ['必然性', '88%'],
                  ['計算難度', '35%'],
                  ['総合', '82%'],
                ].map(([label, w], i) => (
                  <li key={label}>
                    <span>{label}</span>
                    <i className={`score-bar${i === 5 ? ' score-total' : ''}`}>
                      <b style={{ '--w': w } as React.CSSProperties}></b>
                    </i>
                  </li>
                ))}
              </ul>
            </div>

            <div className="review-diff reveal" aria-label="難易度">
              <h3>難易度</h3>
              <ul>
                <li>
                  <span className="badge badge-a">A</span> 超難
                </li>
                <li>
                  <span className="badge badge-b">B</span> 難
                </li>
                <li>
                  <span className="badge badge-c">C</span> 標準
                </li>
                <li>
                  <span className="badge badge-d">D</span> 基礎
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ============ 過去問DB ============ */}
        <section className="exams" id="exams">
          <header className="section-head reveal">
            <p className="section-eyebrow">過去問DB — 国公立大学 入試数学 2010〜2025</p>
            <h2 className="section-title">入試問題が、種になる。</h2>
            <p className="section-sub">
              18大学・前期後期の過去問から選んで、その場で融合生成できます。データソース: mathexamtest.jp
            </p>
          </header>

          <div className="exams-toolbar reveal">
            <label className="exams-select">
              <span>大学</span>
              <select aria-label="大学で絞り込む" defaultValue="すべての大学">
                <option>すべての大学</option>
                <option>東京大学</option>
                <option>京都大学</option>
                <option>東京工業大学</option>
                <option>大阪大学</option>
                <option>東北大学</option>
                <option>北海道大学</option>
                <option>九州大学</option>
              </select>
            </label>
            <label className="exams-select">
              <span>年度</span>
              <select aria-label="年度で絞り込む" defaultValue="すべての年度">
                <option>すべての年度</option>
                <option>2025</option>
                <option>2024</option>
                <option>2023</option>
                <option>2022</option>
              </select>
            </label>
            <label className="exams-toggle">
              <input type="checkbox" defaultChecked aria-label="後期日程を含める" />
              <span>後期を含む</span>
            </label>
            <button className="btn btn-primary" type="button">
              ⚡ 選択した問題で融合生成
            </button>
          </div>

          <div className="exams-table reveal" role="table" aria-label="過去問一覧">
            <div className="exams-row exams-head" role="row">
              <span>大学</span>
              <span>年度</span>
              <span>区分</span>
              <span className="ta-r">問題</span>
            </div>
            {[
              ['東京大学', '東大', '2024', '前期'],
              ['京都大学', '京大', '2024', '前期'],
              ['東京工業大学', '東工大', '2023', '後期'],
              ['大阪大学', '阪大', '2023', '前期'],
              ['名古屋大学', '名大', '2022', '前期'],
              ['東北大学', '東北大', '2022', '前期'],
              ['一橋大学', '一橋', '2021', '後期'],
              ['筑波大学', '筑波大', '2020', '前期'],
            ].map(([name, short, year, term]) => (
              <a className="exams-row" href="#pricing" key={name}>
                <span>
                  <b>{name}</b> / {short}
                </span>
                <span>{year}</span>
                <span>{term}</span>
                <span className="ta-r">問題を見る →</span>
              </a>
            ))}
          </div>
        </section>

        {/* ============ 書き出し ============ */}
        <section className="export" id="export">
          <header className="section-head reveal">
            <p className="section-eyebrow">書き出し — 問題は、発表されて完成する</p>
            <h2 className="section-title">図にして、検証して、投稿する。</h2>
          </header>
          <div className="export-grid">
            <figure className="export-tile reveal">
              <span className="export-sym">図</span>
              <figcaption>
                <h3>TikZ 図プレビュー</h3>
                <p className="export-code">
                  <code>{String.raw`\draw[axis] (0,0) -- (4,0);`}</code>
                  <br />
                  <code>{String.raw`\draw (0,0) parabola (2,4);`}</code>
                </p>
                <span className="export-status">✓ コンパイル検証済</span>
              </figcaption>
            </figure>
            <figure className="export-tile reveal">
              <span className="export-sym">検</span>
              <figcaption>
                <h3>Wolfram 検証</h3>
                <p>WolframAlpha で簡約化成功 / 検証結果をその場で表示</p>
                <span className="export-status">✓ 簡約化成功</span>
              </figcaption>
            </figure>
            <figure className="export-tile reveal">
              <span className="export-sym">P</span>
              <figcaption>
                <h3>PDF 保存</h3>
                <p>組版してPDF保存。プリント・模試の原稿にそのまま使えます</p>
                <span className="export-status">PDF 生成</span>
              </figcaption>
            </figure>
            <figure className="export-tile reveal">
              <span className="export-sym">𝕏</span>
              <figcaption>
                <h3>X 投稿</h3>
                <p>問題文と解答を画像として添付。投稿プレビューで確認してから投稿</p>
                <span className="export-status">✓ 投稿完了！</span>
              </figcaption>
            </figure>
          </div>
        </section>

        {/* ============ 料金 ============ */}
        <section className="pricing" id="pricing">
          <header className="section-head reveal">
            <p className="section-eyebrow">料金 — まずは無料枠で</p>
            <h2 className="section-title">作問の練習は、無料ではじめられます。</h2>
          </header>
          <div className="price-grid">
            <article className="price-card price-free reveal">
              <h3>無料プラン</h3>
              <p className="price-amount">
                ¥0 <span>/ 月</span>
              </p>
              <ul>
                <li>月10回まで生成可能</li>
                <li>問題一覧・レビュー・過去問DB</li>
                <li>TikZ / PDF / X投稿</li>
              </ul>
              <a className="btn btn-ghost" href="#top">
                ワークスペースに入る
              </a>
            </article>
            <article className="price-card price-premium reveal">
              <span className="price-flag">作問者向け</span>
              <h3>プレミアム 月額プラン</h3>
              <p className="price-amount">
                ¥980 <span>/ 月</span>
              </p>
              <ul>
                <li>生成回数 無制限</li>
                <li>全問題へのアクセス</li>
                <li>優先サポート</li>
              </ul>
              <a className="btn btn-primary" href="#top">
                プレミアムにアップグレード
              </a>
              <p className="price-note">Visa・MasterCard・クレジットカード対応（Stripe で決済）</p>
            </article>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <p className="footer-logo">
              <span className="brand-mark">Σ</span> Sakumon <em>by MORTRA</em>
            </p>
            <p className="footer-desc">
              表現の間を移動する研究基盤 MORTRA の、最初の応用です。
              <br />
              数学問題をつくる人のための作業場。
            </p>
          </div>
          <div className="footer-credit">
            <p className="footer-credit-line">
              このデザインは{' '}
              <a
                href="https://github.com/anthropics/skills/tree/main/skills/frontend-design"
                target="_blank"
                rel="noopener"
              >
                Anthropic Frontend Design
              </a>{' '}
              の方法論で作られました。
            </p>
            <ul className="footer-stats">
              <li>
                <b>167,000</b>
                <span>GitHub スター</span>
              </li>
              <li>
                <b>758,000</b>
                <span>インストール</span>
              </li>
              <li>
                <b>open source</b>
                <span>Anthropic 管理</span>
              </li>
            </ul>
          </div>
        </div>
        <p className="footer-base">Sakumon — 解く人から、創る人へ。</p>
      </footer>
    </div>
  )
}
