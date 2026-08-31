# MORTRA 有限工学言語・高次元セル実行実験

実験日: 2026-08-31

## 目的

3次元部品を生成できたという作例だけでは、MORTRAの8射が汎化したとは言えない。従来のCAD実験には、任意のB-repを入力セルへ直接埋め込める抜け道があり、複雑さを入力へ隠せた。本実験ではこの抜け道を閉じ、次を検証する。

1. 外部入力を有限で直列化可能な文法へ制限しても、既存8射で機械部品を構成できるか。
2. 部品名やモチーフ名を新しい射として追加せず、未見の曲線断面・螺旋経路を扱えるか。
3. 同じ型規則を4次元以上でも実行できるか。
4. 外部CAD corpusの操作を、現在の実行系がどこまで構造的に覆うか。

## 仮説

幾何操作は次の8射へ固定できる。

```text
transform  sweep  combine  select
slice      project constrain annotate
```

一方、円、線分、円弧、螺旋などは射ではなく有限な入力データである。複雑な部品は「入力データの組」と「8射の合成」で表す。高次元ではOpenCascadeを無理に拡張せず、同じ射を別backendで実行する。

## 方法

### 1. 任意B-rep入力を禁止した有限文法

`engineering_program_spec.py`に、JSONだけで表せる入力文法を実装した。

```text
disk  rectangle  polygon
segment_path  polyline_path  circle_path  helix_path
sketch(line | arc3 | radius_arc)
```

Python関数、コールバック、native CAD objectは受け取らない。未知の入力種、前方参照、不正な制約名は実行前に拒否する。円弧の意味はCadQuery公式実装の`threePointArc`と`radiusArc`を追跡し、始点・通過点・終点または符号付き半径から構成した。

### 2. 有限文法から既存8射へのコンパイル

JSONの各stepは既存`CadExecutor`へ直接写す。押出しは直線経路の`sweep`、螺旋ばねは明示経路の`sweep`、穴は`combine(difference)`、鏡映と拡大縮小は`transform`のパラメータである。新しい幾何射は追加していない。

評価対象は次の3件とした。

| ケース | 文法上の特徴 | 主な射 |
|---|---|---|
| 6穴フランジ | 円、反復配置、差 | transform / sweep / combine |
| 圧縮ばね | 円断面、螺旋経路 | transform / sweep |
| 丸端リンク板 | 線分、3点円弧、半径円弧、2穴 | sweep / combine |

### 3. 高次元backend

`nd_cell_backend.py`に、任意の有限次元に対する有理数座標のアフィン多面体backendを実装した。点から各軸方向へ`sweep`して4、5、6次元立方体を作り、有理行列で2次元へ`project`した。座標、辺、射の履歴はすべて厳密な分数として保存する。

これは一般の滑らかな4次元CADではない。現在の実行範囲は有限頂点・有限辺を持つアフィンセルである。

### 4. 外部corpusの構造監査

ローカルへ固定したCADTestBench生成コード2,400件をASTで解析した。各メソッド呼び出しを次へ分類した。

- 現在の8射または有限入力で表せる
- 幾何構成ではない検査・数値処理
- 有限入力文法の不足
- 既存8射の実装上の不足
- 未分類

この監査はCADを実行して正解判定するベンチマークではなく、操作語彙の静的被覆測定である。

### 5. 公開研究と公式実装から採用した判断

今回の実装は、公開資料を名前だけ並べて接続したものではない。各資料が扱う数学対象と検証方法を分け、現在のMORTRAで再現できる部分だけを採用した。

| 資料 | 確認した構造 | MORTRAへ反映した判断 |
|---|---|---|
| [SketchGraphs](https://github.com/PrincetonLIPS/SketchGraphs) | 線分・円などの原始図形を頂点、幾何制約を辺とする制約グラフ。1,500万スケッチを公開 | 入力を完成B-repではなく、有限な原始図形と制約の直列化データに限定 |
| [CADTestBench](https://github.com/dimitrismallis/CADTestBench) | 生成物を参照画像との近さではなく、B-rep上の実行可能な幾何・位相述語で判定 | 妥当性、連結成分数、体積式、投影領域を独立した検査として保存 |
| [BenchCAD](https://arxiv.org/abs/2605.10865) | 106工業部品族・17,900件の実行確認済みCadQueryプログラム。未見部品族への一般化不足を報告 | 部品名の命令を増やさず、曲線経路、断面列、ねじれを共通`sweep`のデータ差として扱う |
| [Ortho2CAD](https://arxiv.org/abs/2607.08891) | STEPから隠れ線と主要寸法を含む正投影図を生成し、編集可能なCadQueryへ接続 | 表示輪郭を手書きせず、同じB-repから正投影、隠れ線、断面、寸法を導出 |
| [Training AI to Paint with Code](https://surya.website/rling-qwen-to-paint-with-code) | 長いAPI説明より、実在する少数操作の厳格な許可リストと実行結果による評価が有効だった実験 | 8射以外の任意操作、Pythonコールバック、native objectを外部プログラムから拒否 |
| [CadQuery](https://github.com/CadQuery/cadquery) / [build123d](https://github.com/gumyr/build123d) | OpenCascade上の円弧、経路sweep、B-rep、STEP・STL・DXF出力の実装 | `radiusArc`の符号、断面座標枠、経路sweep、直列STLメッシュ化をソースと実行結果で照合 |

`mathbullet/skills`は、外部資料の調査、引用、論文解説、日本語記録の作法を提供する。CAD kernelや新しい幾何射は提供しない。そのため、研究記録の方法には利用したが、構造被覆率や生成能力の根拠には数えていない。

## 結果

### 有限言語と高次元実行

- native CAD objectを外部入力として受け取る経路: 0
- 未知入力種・コールバック・前方参照の拒否: 回帰テストで確認
- 3つの宣言的CADプログラム: すべて実行可能
- 6穴フランジ: `23890.17850237051 mm^3`、閉形式期待値と一致
- 3巻き螺旋ばね: `1980.19235467032 mm^3`、`pi r^2 L`と0.01以内で一致
- 丸端2穴リンク板: `1013.62830044411 mm^3 = 800 + 68pi`と一致
- 4次元立方体: 16頂点、32辺
- 5次元立方体: 32頂点、80辺
- 6次元立方体: 64頂点、192辺
- 4、5、6次元から2次元への射影: 厳密有理数で再生
- 追加した幾何射: 0
- 関連回帰テスト: 27 / 27成功

### CADTestBench構造監査

| 指標 | 結果 |
|---|---:|
| 解析対象 | 2,400 / 2,400ファイル |
| 幾何構成呼び出し | 24,213 |
| 現runtimeで構造的に表現可能 | 23,787 |
| 呼び出し被覆率 | 98.2406% |
| 全構成呼び出しが被覆されたファイル | 2,166 / 2,400 |
| ファイル被覆率 | 90.25% |

未接続の主要操作は`fillet` 135回、`shell` 21回、`offset2D` 3回である。有限入力側では一般`arc` 9回、一般`spline` 6回が残る。低頻度の未分類呼び出しも残るため、98.24%をCAD正答率とは呼ばない。

## 考察

### 何が改善したか

従来は、複雑な形状をPython関数で作って`input_cell`へ渡せた。その状態では「8射で生成した」のか「入力で完成していた」のかを区別できない。今回、入力を有限JSONへ制限したことで、形状の変化は入力データと8射の履歴へ明示的に残る。

螺旋ばねは新しい`spring`命令ではなく、円断面と螺旋pathの`sweep`として動いた。丸端リンク板も`rounded_link`命令を使わず、線分と円弧の閉曲線から構成できた。これは部品名の暗記ではなく、入力幾何と合成の再利用である。

螺旋ばねは厳密STEPと証明書までを採点した。管状sweepのSTL分割が固定OCP環境で長時間化したため、STL・第三角法図面を完了扱いにはしていない。フランジとリンク板はSTEP、STL、SVG、DXFを生成し、図面を画像化して目視検査した。

### 失敗から修正した点

最初のばね断面は固定`YZ`平面に置かれ、螺旋の始点接線と直交していなかった。B-repはvalidかつsingle solidだったが、体積は約`3.74e-6 mm^3`で実体がなかった。有限文法へ任意局所座標枠を追加し、断面法線を接線へ一致させ、`pi r^2 L`で体積を検査した。

最初のリンク板では符号付き半径の向きが逆で、右円弧が内側へ曲がり、右穴が外周へ開いていた。画像検査で発見し、半径符号を修正した上で`800 + 68pi`の閉形式体積を制約へ追加した。この二例から、`is_valid`と`single_solid`だけでは意味上の正しさを保証しないことが確認できた。

4、5、6次元立方体はOpenCascadeの3次元制約を越えて実行できた。重要なのは高次元ごとの新しい射を追加しなかった点である。同じ`sweep`と`project`を、厳密アフィンセルbackendが実行した。回帰テストでは1次元から7次元まで、頂点数`2^n`と辺数`n 2^(n-1)`を照合した。

### なぜ残る3操作を安易に射へ追加しないか

`fillet`、`shell`、`offset2D`を各々9番目以降の原始射にすれば被覆率は上がる。しかし、それだけでは基底が縮約されているとは言えない。

- `fillet`: 境界選択、局所オフセット、包絡、trimの合成として分解できる可能性がある。
- `shell`: 境界選択、法線方向オフセット、内外境界の差として分解できる可能性がある。
- `offset2D`: 変換ではなく、距離場またはMinkowski和として`combine`へ接続すべき可能性がある。

次の実験では、これらを名前だけ追加せず、既存射と一般的な幾何対象へ分解した場合の正しさ、特異点、位相変化を測る。

### 現在の工学的境界

この実験が扱うのは幾何、位相、投影、基本注記である。材料、荷重、応力、疲労、熱、加工法、公差、表面粗さ、GD&T、組立順序、BOMは未接続である。機械製図として出力できても、ASMEまたはISO適合を認証したわけではない。

## 結論

MORTRAの3次元生成は、任意B-repを入力へ隠す方式から、有限入力文法と8射の宣言的プログラムへ移行した。未見の螺旋経路と線・円弧sketchを同じruntimeで実行し、4、5、6次元では厳密有理セルを同じ射で構成・射影した。外部2,400プログラムの静的監査では、幾何構成呼び出しの98.24%が現在のruntimeへ構造的に対応した。

ただし、この数値は正答率ではない。次の本質的課題は、`fillet`、`shell`、`offset2D`と一般splineを、部品固有命令へせずに再利用可能な幾何分解として実装し、外部CAD課題を実行してB-rep述語で採点することである。

## 再実行

```powershell
C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe -m pytest `
  math_os_prototype\test_engineering_program_spec.py `
  math_os_prototype\test_nd_cell_backend.py `
  math_os_prototype\test_engineering_geometry_ir.py `
  math_os_prototype\test_engineering_cad_backend.py -q

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\audit_cadtestbench_operator_coverage.py `
  C:\Users\81808\.cache\mortra-research-sources\CADTestBench `
  --output artifacts\engineering-geometry-basis-20260831\cadtestbench-operator-coverage.json

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\experiment_declarative_engineering_generalization.py
```
