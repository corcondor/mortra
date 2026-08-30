# Codex 向け引き継ぎ：MORTRA の対外発信

作成 2026-08-30。書いたのは Claude（Opus 5）。
**ここに書いてあるのは、この日に実地で確認したことだけです。** 推測は「未確認」と明記します。

この文書の目的は、**研究を進めている側（Codex）が、対外発信も自分で回せるようにする**ことです。
これまで研究と発信が分断され、発信側が研究の実態を把握しないまま作業した結果、
方向のずれた成果物が何度も作られました。その状態を終わらせます。

---

## 0. まず読む順序

```
1. lib/mortra/i18n.ts の FIGURES        数字の正本。ここ以外から数字を引かない
2. docs/research/README.md              研究記録の索引。ただし更新が遅れることがある
3. docs/research/ の最新日付のファイル    索引になくても日付で探す
4. この文書                              発信側の手順
5. docs/design/PROOF-REEL-PIPELINE.md   動画の作り方の詳細
```

**索引だけを信じないこと。** 2026-08-28 時点で `README.md` は 8/24 で止まっていたが、
実際の最新記録は 8/27 の `MORTRA-MINIMAL-REPRESENTATION-CHARTS-20260827.md` だった。

---

## 1. 数字（2026-08-30 時点）

```
76 / 89 = 85.39%   MORTRA 監査済み能力和
                   厳密ソルバ群の集合和。自動選択、問題ごとの分岐なし
28 / 89 = 31.5%    公式Newclid単体。同じ凍結89問、単一実行系
2.71x              比
25 / 30            IMO-AG-30
13 問               未証明
```

**この2つは同じ種類の数字ではない。** 28は1エンジンの通し実行、76は集合和。
本人が公開文でこの区別を明記しているので、**並べて「2.71倍」とだけ書かない。**

**主張の限界。本人が研究記録に書いている。勝手に強くしない。**

- 7チャートは**問題を見た後の post-hoc 追加**。76/89 は固定集合上の監査済み能力であり、
  **未見問題への汎化率ではない。**
- `2020IranGOAp2` `2017USAMOp3` は量化・分岐の**入力意味論の不一致**のため加点していない。
  探索不足ではない。
- 母集団外加算 0、空虚証明 0、残り13問への誤一致 0。回帰 168/168。

**過去の値（51 / 53 / 55 / 59 / 60 / 66 / 67 / 69）を現在値として引用しない。**
値は日ごとに動く。発信の直前に必ず `i18n.ts` を読み直すこと。

---

## 2. MORTRA の独自性（発信で言うべきこと）

**「幾何を解くプログラム」自体は珍しくない。** GeoGebra、GCLC、Newclid、Yuclid、JGEX。
個人が作る例も多い。2026-08-29 には別のユーザーが同種のものを投稿し、1.5万表示を得た。

**MORTRA が違うのは、解けることではなく、測り方と公開の仕方である。**

```
1  凍結split      固定89問の名簿を先に凍結し、分母と分子を同じ名簿から導く
                  母集団外の問題が分子に混入したら処理を拒否する仕組みがコードに入っている
2  証明書         1問ごとに SHA-256。誰でも再生できる
3  非空虚性        単位イデアル [1] による空虚な証明を検出して除外する
4  自己訂正の記録   得点計算の誤りを自分で見つけ、67→55 に下方修正した監査を公開している
5  経路にLLMなし   uses_external_llm: false / uses_expected_answer: false /
                  uses_problem_id_in_solver: false が artifact に記録されている
```

**4 が最も強い。** 数字を下げる訂正を自分から公開している例はほとんどない。
査読でも投資家でも、ここが信用の source になる。

**言い方の例。**

```
良い   固定89問の凍結splitで76問。証明書のSHA-256を発行しているので誰でも再生できる。
       外部LLMは経路に入っていない。
悪い   MORTRAは幾何が解けます（誰でも言える）
悪い   85%達成（分母と条件が抜けている）
```

---

## 3. アカウントの実態

```
Instagram  @mortra_ai   投稿1件  フォロワー1人
X          @MORTRA_AI   投稿2件  フォロワー1人
```

**旧アカウント名を記録に残さないこと。** 公式は `@mortra_ai` / `@MORTRA_AI` のみ。

**`@corcondor` は本人の個人アカウント。公式の投稿先ではない。**
Chrome の既定ログインがこちらのことがあるので、投稿前に必ず確認する。

```js
document.querySelector('img[alt$="のプロフィール写真"]').alt
// -> "mortra_aiのプロフィール写真" なら正しい
```

### 現在の到達数（2026-08-30）

```
X 動画（1本目）    42 impressions  いいね1  リポスト1
X テキスト（2本目） 28 impressions  いいね1  リポスト1
```

**参考値。** 同種の内容を投稿した個人アカウントが 1.5万表示・いいね52。
差はフォロワー数と文脈（日本語・院試という導入）による。**内容の質の差ではない。**

### プロフィール（X、現行）

```
MORTRA / @MORTRA_AI
Finite primitives. Infinite mathematics.
Toward a Standard Model of Mathematical Intelligence.
Beyond LLMs through structure, morphisms and verification.
mortra.ai
```

**参考にした他社の形。**

```
OpenAI     OpenAI's mission is to ensure that artificial general intelligence
           benefits all of humanity. We're hiring: openai.com/jobs
Anthropic  We're an AI safety and research company that builds reliable,
           interpretable, and steerable AI systems. Talk to our AI assistant
           @claudeai on claude.ai
Nintendo   お知らせと更新情報を配信します。問い合わせには応答しません
```

**3社に共通する形。** 2文。「何の組織か」を平叙文で言う。読者が次にできることを1つ置く。
スローガンを並べない。

---

## 4. 投稿の実務（実地で確認済み）

**API も分割送信スクリプトも不要。** Chrome MCP で両方に投稿できる。
`scripts/x-post-video.mjs` と `automation/pipeline/x_post.py` は**もう使わなくてよい。**
どちらも鍵が `@corcondor` のもので、投稿先が違う。

### Instagram

```
1  instagram.com/mortra_ai/ でアカウントを確認
2  左メニューの「＋」（座標およそ 35,401）
3  find で file input を探す。ダイアログ内のものを選ぶ（複数ヒットする）
4  file_upload に mp4 の絶対パスを渡す（.openclaw 配下、10MBまで）
5  ★ change を自分で発火させる。これが無いと必ず詰まる
6  切り取り画面 → 左下の拡大アイコン → 比率 9:16
7  次へ → カバー写真は下記
8  次へ → キャプションを type
9  シェア → トランスコードに30〜40秒
```

**手順5のコード。** ファイルは input に入るが React が検知しないので、画面が初期状態に戻る。

```js
const i = [...document.querySelectorAll('input[type=file]')]
  .find(x => x.files && x.files.length === 1);
i.dispatchEvent(new Event('input',  { bubbles: true }));
i.dispatchEvent(new Event('change', { bubbles: true }));
```

**カバー写真のスライダーは効かない。** ffmpeg で良いコマを jpg に抜き、
「コンピュータから選択」の file input に `file_upload` して、同じく change を発火させる。
1コマ目は内容が薄くサムネイルとして弱いので必ず差し替える。

### X

```
1  x.com/home で投稿欄をクリック
2  find で file input → file_upload に mp4 の絶対パス
3  ★ 触らずに30秒待つ。「Edit」ボタンと1コマ目が出れば読み込み完了
4  投稿欄をクリックして type
5  Post
```

**change の発火は不要。** ただし**順序が決定的。動画を先、文章を後。**
文章を先に入れると `Preparing media...` が 83% で止まり、
`input[type=file]` の `files` が 0 に戻って二度と進まない。

**無料枠は 280 字。** 超えると末尾が赤くなり Post が押せない。
長い説明は Instagram 側に置く。

**詰まったとき。** `window.onbeforeunload = null` を実行してから
`navigate` に `force: true` を渡すと、投稿欄を捨ててやり直せる。

### 動画の要件

```
9:16  1080x1920  h264  yuv420p  +faststart
無音AAC を必ず足す（anullsrc）。X は音声トラックが無いと変換に失敗する
```

---

## 5. 動画の作り方

詳細は `docs/design/PROOF-REEL-PIPELINE.md`。ここでは要点だけ。

```
scripts/survey_proof_charts.py     12問の一覧。どれが動かせるかを見る
scripts/extract_proof_figure.py    proof-focus.svg から実座標を抽出
scripts/render_proof_motion.mjs    図を主役にした版（推奨）
scripts/render_proof_reel.mjs      文字を主役にした版（旧）
```

**原則。文言も座標も数式も、スクリプトの中で作らない。**
すべて MORTRA が実際に出力したファイルから読んで並べるだけにする。
作った瞬間に「実物を見せている」という性質が消える。

### 動きは数学から取る

**装飾のアニメーションを付けない。証明に現れる連続変換をそのまま動かす。**

```
2023SAGFp8   w -> p + q - pq*conj(w)      鏡映。三角形が辺の直線で折り返される
2011G3       U+V = E+F                    アフィン平行四辺形
その他        相似・反転・回転・射影も同様に連続で動かせる
```

始点と終点は厳密な座標。途中の位置は演出。**この区別をコメントに書いておくこと。**

### 12問の素材（2026-08-30 時点）

```
問題                動かせる変換
2016USATSTSTp6      中点・円束・射影・接線・根軸   5種類。最も動く
2023SAGFp8          中点・対蹠・鏡映              作成済み
2017G4              円束・接線・根軸
2023RMMSLG3         射影・根軸・鏡映
2011G3              中点・射影・根軸              作成済み
ShuZhiMiGeo635      接線・重心
2016CTSTp5          中点
2023VietnamTSTp3    接線
2023MOSTMockp2      （記述に変換語なし）
2024KoMaLA877       （同上）
2023SerbiaMOp6      20点で最も密
2022G5              恒等式33本で最多
```

**別の問題に移すとき書き直すのは `SCENE` の対応表だけ。** それ以外はそのまま動く。
ただし**どのパスが何かは SVG を実際に見て決めること。** group 名では決まらない。
`2011G3` では `line2d_1` が四角形の輪郭、`line2d_2` が根軸だった。
最初これを取り違えて、四角形が緑になった。

---

## 6. デザインの制約（本人が却下したもの）

**これは好みではなく、確定した制約。破ると差し戻される。**

```
使う      #ff9d2e オレンジ   作図・元の表現
          #ff5fb0 ローズ     名前のある幾何定理
          #ffffff 白         代数の消去
          #4dffa0 グリーン   閉じた一手・結論
          #4fc3ff ライトブルー 非退化の確認
          地は #05070a。中間色は青へ寄せる（#7d919e / #2b3742）

使わない   灰色（純グレーは「選んでいない色」に見える）
          シアン、紫・ヴァイオレット、彩度の低い色、地と同化する色
          Inter / Space Grotesk（AI生成の既定に見える）
          クリーム地＋セリフ＋テラコッタ（同上）
          絵文字、ハッシュタグ、ヒント、ラベル
```

**線は細く、彩度を高く、二重描画で発光させる。** 太さで見せると子供っぽくなる。
広く薄いにじみを加算合成で置き、その上に細い芯を引く。
単層で `shadowBlur` を掛けても、芯が太いままでは光って見えない。

**余白は多めに。**

---

## 7. 使えるスキル

### リポジトリ内（`.claude/skills/`）

```
html                     概念・仕組みをHTMLの説明ドキュメントにする
                         design-system/ に document.css と component-samples.html が完備
                         背景 #FAF9F6、白地・黒罫線、有彩色は青と赤のみ、図は黒一色の線画
                         ★ MORTRAのブランド（黒地・5色）と衝突する。用途で使い分けること
ja-text-communication    日本語の書き方。何かを書く前に必ず読む
                         一文一義、数値に分母と集計範囲、主張→根拠の順、圧縮の禁止
explain                  概念の解説文の構成
survey                   複数ソースの調査レポート
paper-details            論文の詳細解説
documenting-with-sources 出典表記の作法
writing-quotation        引用の書式（コードフェンス、>は使わない）
```

### システム側

```
artifact-design          成果物の設計規律。AI生成に見える既定パターンの回避
artifact-diagramming     図の判断基準。名前ではなく機構を描く、矢印にラベル
algorithmic-art          p5.js の生成アート。Anthropicブランドのテンプレートが必須なので
                         MORTRAの成果物には使えない。原則だけ借りる
oil-motion               MiniMaxのAI動画流水線。コードで描く図には合わない
```

---

## 8. 参考にした外部資料

```
mathbullet/skills                     スキルを階層化して出力の一貫性を担保する構成
https://github.com/mathbullet/skills  （このリポジトリの .claude/skills はこれ）

surya.website/rling-qwen-to-paint-with-code
  Qwen に p5.brush のコードを書かせて水彩画を出す RL。
  教訓は「主観的な創作では、設計問題が報酬関数の設計になる」。
  9指標を並べたときは頭打ちで、対比較に変えたら抜けた。
  → 作る前に「良い」の基準を言語化する。これをやらないと平凡な所で止まる

arXiv 2511.15398  One algebra for all: geometric algebra methods for
                  neurosymbolic XR scene authoring, animation and neural rendering
  幾何代数が点・直線・平面・球と変換を1種類の multivector に統一する。
  MORTRA の円束・半角複素数・Hermitian内積と同じ方向。
  「表現を移すと問題が小さくなる」という主張の外部裏付けとして使える

arXiv 2502.03544  AlphaGeometry2
  IMO-AG-50 で 42/50。記号エンジン単体は 16/50。
  公開されているのは記号側（DDAR）のみで、言語モデルは非公開。
  ★ 本人の判断で、公開資料に他社比較は載せないことになっている。
    内部の判断材料としてのみ使う
```

---

## 9. Vercel とサイト

```
プロジェクト   mortra（旧 sakumon-web からリネーム）
リポジトリ     github.com/corcondor/mortra
本番ブランチ   master
ドメイン       mortra.ai（本番）/ mortra.vercel.app / sakumon-web.vercel.app
              後ろ2つは貼った先が切れないよう残してある
```

**`master` に push すると Vercel が自動でビルドして本番に反映される。**
所要はおよそ 1〜2 分。

**ビルドが落ちても Vercel は黙っている。** 2026-08-23 に5時間気づかなかった。
原因は TypeScript の型エラーで、ローカルビルドは通っていた（手元に未コミットの修正があったため）。

**push 前に必ずこれをやること。** HEAD だけを別ディレクトリに取り出して型チェックする。

```bash
git worktree add --detach /tmp/headcheck HEAD
# node_modules をジャンクションで貼る（Windows）
New-Item -ItemType Junction -Path /tmp/headcheck/node_modules -Target ./node_modules
node ./node_modules/typescript/bin/tsc --noEmit -p /tmp/headcheck/tsconfig.json
```

**デプロイ後の確認はキャッシュを迂回する。** `?cb=<乱数>` を付ける。
`X-Vercel-Cache: HIT` のまま古い内容を返すことがある。

```bash
curl -s "https://mortra.ai/mortra?cb=$RANDOM" | grep -c "確認したい文字列"
```

**Vercel の操作はトークンで自動化できる。** `VERCEL_TOKEN` が環境変数にある。
プロジェクトの削除・リネーム・ドメイン追加・証明書発行まで API で実行済み。

---

## 10. Codex への依頼（このまま渡してよい）

```
MORTRA の対外発信を、研究の進捗に追随させてほしい。

【背景】
研究と発信が分断されていて、発信側が研究の実態を把握しないまま作業した結果、
方向のずれた成果物が繰り返し作られた。実験を進めている側が発信も回す形にしたい。

【最初に読むもの】
docs/design/CODEX-SNS-HANDOFF.md（この文書）
docs/design/PROOF-REEL-PIPELINE.md
lib/mortra/i18n.ts の FIGURES

【やってほしいこと】

1. 残り10問の証明動画
   scripts/render_proof_motion.mjs の SCENE 対応表を問題ごとに書き、
   図を主役にした 9:16 の動画を作る。
   どのパスが何かは proof-focus.svg を実際に見て決める。group 名では決まらない。
   証明に現れる連続変換（鏡映・相似・反転・回転）をそのまま動かす。
   装飾のアニメーションは付けない。

2. 新しい証明が出たら自動で素材化する
   新しい chart run が data/ に増えたとき、
   extract_proof_figure.py → render_proof_motion.mjs が通るところまで自動にする。
   SCENE の対応表だけは人が書く必要があるので、雛形を出力するところまででよい。

3. 数字の同期
   研究記録の値が動いたら lib/mortra/i18n.ts の FIGURES を更新する。
   数字はここ以外に書かない設計になっている。
   サイト・動画・キャプションはすべてここから読む。

4. 英語版と日本語版
   render_proof_motion.mjs に ja / en の切り替えを入れる
   （render_proof_reel.mjs には実装済み。同じ形にする）。
   証明の本文（proof_dag / representation_chart）は
   MORTRA の出力そのものなので、どちらの版でも英語のまま出す。
   訳すと「実物を見せている」という性質が消える。
   日本語にするのは画面の見出しだけ。

【守ること】
- 文言も座標も数式も、スクリプトの中で作らない。実物を読んで並べるだけ
- 灰色を使わない。中間色は青へ寄せる
- 出典を落とさない（IMO問題なら imo-official.org）
- 数字には必ず分母と条件を添える
- 主張の限界（post-hoc追加、未見集合ではない）を削らない

【投稿】
公式は Instagram @mortra_ai と X @MORTRA_AI。
@corcondor は個人アカウントなので投稿先ではない。
手順はこの文書の第4節。API は不要で、Chrome MCP で通る。
```

---

## 11. 未確認・未着手

**私が確認できていないこと。Codex 側で補ってほしい。**

- **研究の現在の焦点。** 残り13問のうち、いまどれに着手しているか。
  4つのチャート候補（角の二等分線の射影・極・調和束／接線・方べき・円周角／
  反転・相似中心／3次元と順序条件）のどれが進行中か。
- **投稿頻度と反応の関係。** 現在2投稿・42表示では判断材料が足りない。
  10本ほど出したところで、どの形式が伸びたかを測る。
- **英語圏と日本語圏のどちらを主戦場にするか。** 未決定。
  内容は英語圏（定理証明・形式手法の研究者）に向いているが、
  文脈のある日本語圏の方が初速は出やすい。
- **Instagram Graph API。** `IG_ACCESS_TOKEN` / `IG_USER_ID` が未設定。
  設定すれば公開URLを渡すだけで投稿でき、ブラウザ操作が不要になる。

## 12. 今日つくったもの

```
scripts/survey_proof_charts.py       12問の一覧と、動かせる変換の判定
scripts/extract_proof_figure.py      proof-focus.svg から実座標を抽出
scripts/render_proof_motion.mjs      図を主役にした動画（2023SAGFp8 で動作確認）
scripts/render_proof_reel.mjs        文字を主役にした動画（2011G3、ja/en）
scripts/gen_x_header.mjs             X ヘッダー 1500x500
scripts/gen_brand_icons.mjs          SNS アイコン 5サイズ
docs/design/PROOF-REEL-PIPELINE.md   動画の作り方
docs/design/VISUAL-EXPLAINER-20260828.md  Web版の設計判断
docs/design/CODEX-SNS-HANDOFF.md     この文書
```
