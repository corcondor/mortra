# 証明リールの作り方

証明成果物から、SNS用の縦動画（1080×1920）を書き出す手順。
**このパイプラインの原則は「文言も座標も数式も、スクリプトの中で作らない」。**
すべて MORTRA が実際に出力したファイルから読んで並べるだけにする。
作った瞬間に「実物を見せている」という性質が消えるため。

投稿先とアカウントの注意は `memory/video_posting_pipeline.md` を参照。
公式は Instagram `@mortra_ai`。

---

## 全体

```
[1] 証明成果物            data/hageo-exact-chart-*-runs-*/<問題>.chart-portfolio.json
                          data/hageo-exact-chart-*-runs-*/<問題>.proof.md
                          data/hageo-exact-chart-*-runs-*/<問題>.proof-focus.svg
      |
[2] 図の実座標を抽出       scripts/extract_proof_figure.py
      |                    -> build/proof-reel/<問題>.figure.json
      |
[3] フレーム書き出し       scripts/render_proof_reel.mjs {ja|en}
      |                    -> build/proof-reel/frames-{ja|en}/f00000.png ...
      |
[4] ffmpeg で結合          同スクリプト内で実行
                          -> build/proof-reel/mortra-proof-{ja|en}.mp4
```

実行はこの2コマンドだけ。

```bash
python scripts/extract_proof_figure.py \
  data/hageo-exact-chart-two-diameter-pedal-runs-2026-08-26/2011G3.proof-focus.svg \
  build/proof-reel/2011G3.figure.json

node scripts/render_proof_reel.mjs ja
node scripts/render_proof_reel.mjs en
```

依存は `sharp`（リポジトリの node_modules にある）と `ffmpeg`（PATH）。
`sharp` は mortra-1-release 直下でしか解決しないので、**スクリプトは必ずここから実行する。**

---

## [1] どのファイルから何を読むか

`<問題>.chart-portfolio.json` の `selected.certificate` が本体。

| 画面に出るもの | 読む場所 |
|---|---|
| 定理の文 | `<問題>.proof.md` の `## Theorem` 節 |
| 目標 | `selected.goal`（例 `coll m k1 k2`） |
| 証明の各手 | `certificate.proof_dag`（配列。1要素＝1手） |
| 表現の移動 | `certificate.representation_chart`（配列。`A -> B` の文字列） |
| 恒等式と残差 | `certificate.replay_residuals`（`{名前: 余り}`） |
| 証明書ハッシュ | `certificate.certificate_sha256` |
| 点の対応 | `selected.roles`（`{'A': 'd', ...}`） |

**`proof_dag` と `representation_chart` は英語のまま出す。** 日本語版でも訳さない。
MORTRA の出力そのものなので、訳した時点で「実物」ではなくなる。
日本語にするのは画面の見出し（定理・目標・厳密再生・証明書）だけ。

---

## [2] 図の座標抽出

`proof-focus.svg` は matplotlib が書き出したもの。白地・黒線なのでそのままでは使えないが、
**座標は正しい**ので、そこだけ取り出して MORTRA の配色で描き直す。

`scripts/extract_proof_figure.py` が拾うもの。

| 出力 | SVG のどこから |
|---|---|
| `labels` | `<g id="text_N">` の `<!-- A -->` コメントと `transform="translate(x y)"` |
| `scatter` | `<g id="PathCollection_N">` の `<use x= y=>` |
| `paths` | `<g id="patch_N">`（円）と `<g id="line2d_N">`（直線）の `d` |
| `viewBox` | ルートの `viewBox` |

**ラベル文字列はコメントから読む。** matplotlib は各 text グループの先頭に
`<!-- A -->` の形で元の文字列を残す。グリフ（`DejaVuSans-41` など）を組み直すより確実。

**ラベル位置と点の位置はずれている。** matplotlib はラベルを点から少し離して置くので、
`render_proof_reel.mjs` 側で各ラベルに最も近い散布点を探して座標を寄せ直している。

`2011G3` での実測。

```
ラベル 12個  A B C D E F K1 K2 M / pedal circle of E / pedal circle of F / radical axis
点     9個   PathCollection_1..9
パス   5本   patch_2,patch_3（2つのペダル円）/ line2d_1,line2d_2（根軸ほか）
viewBox      0 0 485.116981 347.04
```

---

## [3] 証明の手と図の段を対応させる

**ここがこのパイプラインの核心。** 「証明1段＝図1段＝文1段」を成立させる部分。

`render_proof_reel.mjs` の `figure(step, sub)` が、第 `step` 手までの図を返す。
`sub` は同じ手の中での進み具合（0→1）で、これで1手が滑らかに現れる。

`2011G3` の対応。**この割り当ては `proof_dag` の記述を読んで人が決めている。**
自動ではないので、別の問題に移すときは書き直しが要る。

| step | proof_dag の記述 | 図に足す要素 |
|---|---|---|
| 0 | （初期構成） | 四角形 ABCD、共有点 E, F |
| 1 | Complete omega_E with the projection of E onto DA. | ペダル円 ω_E（`patch_2`） |
| 2 | Complete omega_F with the projection of F onto BC. | ペダル円 ω_F（`patch_3`） |
| 3 | Transfer both new projections across the opposite carrier line. | （図の追加なし） |
| 4 | Construct U and V as the two crossed perpendicular intersections. | 弦 EF |
| 5 | Use cyclic secants to prove U and V have equal powers... | 中点 M |
| 6 | Use E+F=U+V to put the midpoint of EF on line UV... | 共有点 K1, K2 |
| 7 | The supplied common points K1,K2 span that same radical axis. | 根軸（`line2d_*`） |

色は射の型に対応させる。`lib/mortra/i18n.ts` と同じ5色。

```
construct #ff9d2e   作図・元の表現         E, F
theorem   #ff5fb0   名前のある幾何定理      ペダル円
algebra   #ffffff   代数の消去             弦 EF、中点 M
close     #4dffa0   閉じた一手             K1, K2、根軸
numeric   #4fc3ff   非退化の確認・問題ID
```

---

## [4] 書き出しと ffmpeg

30fps、1シーンあたりの秒数はスクリプト冒頭の `SEC` で決める。
`2011G3` の構成は 35.1 秒・1053 フレーム。

```
定理        5.0 秒
証明 各手    2.9 秒 × 7
恒等式       5.4 秒
証明書       4.4 秒
```

ffmpeg の引数はこう固定している。理由つき。

```
-framerate 30              フレーム番号から組む
-f lavfi -i anullsrc=...   無音AACを足す。X は音声トラックが無いと変換に失敗する
-c:v libx264 -crf 18       文字が多いので低圧縮寄り
-pix_fmt yuv420p           これが無いと一部プレイヤーで再生できない
-preset slow               1000フレーム程度なら許容範囲
-shortest                  無音トラックが映像より長くならないように
-movflags +faststart       先頭にメタデータを置く。SNS のプレイヤー向け
```

---

## 別の問題に移すとき

`chart-portfolio.json` の構造は7チャート共通なので、[1][2][4] はそのまま動く。
**書き直しが要るのは [3] の対応表だけ。**

```
1. RUN と NAME をスクリプト冒頭で差し替える
2. extract_proof_figure.py を新しい svg に対して実行する
3. 抽出されたラベル名を確認する（点の名前が問題ごとに違う）
4. figure() の中の対応を、その問題の proof_dag に合わせて書き直す
```

`2016USATSTSTp6`、`2023SAGFp8`、`2016CTSTp5`、`2023RMMSLG3`、
`ShuZhiMiGeo635`、`2023VietnamTSTp3` でも同じ手順が使える。

---

## やってはいけないこと

- **`proof_dag` や `representation_chart` を要約・意訳しない。** そのまま出す。
- **図を自分で作図し直さない。** 抽出した座標だけを使う。
- **数値をスクリプトに直書きしない。** 恒等式の本数も残差も証明書も JSON から読む。
- **灰色を使わない。** 中間色は青へ寄せる（`#7d919e` / `#2b3742`）。
- **出典を落とさない。** 全フレーム下部に問題の出典を入れる。
  `2011G3` なら `IMO 2011 Shortlist G3 / imo-official.org / IMO2011SL.pdf`。

## 関連ファイル

```
scripts/extract_proof_figure.py     図の座標抽出
scripts/render_proof_reel.mjs       フレーム書き出しと ffmpeg 実行
build/proof-reel/                   出力先（git 管理外）
docs/design/VISUAL-EXPLAINER-20260828.md   同じ題材の Web 版と設計判断
```
