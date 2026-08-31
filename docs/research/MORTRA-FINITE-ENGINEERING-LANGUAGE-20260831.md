# MORTRA 有限工学言語・高次元セル実行実験

実験日: 2026-08-31

## 目的

3次元部品を生成できたという作例だけでは、MORTRAの8射が汎化したとは言えない。従来のCAD実験には、任意のB-repを入力セルへ直接埋め込める抜け道があり、複雑さを入力へ隠せた。本実験ではこの抜け道を閉じ、次を検証する。

1. 外部入力を有限で直列化可能な文法へ制限しても、既存8射で機械部品を構成できるか。
2. 部品名やモチーフ名を新しい射として追加せず、未見の曲線断面・螺旋経路を扱えるか。
3. 同じ型規則を4次元以上でも実行できるか。
4. 外部CAD corpusの操作を、現在の実行系がどこまで構造的に覆うか。
5. `fillet`、`shell`、`offset2D`を個別命令として増やさず、共通の幾何操作へ縮約できるか。

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

Python関数、コールバック、native CAD objectは受け取らない。入力種ごとに必須引数と許可引数を閉じ、未知の引数、前方参照、不正な制約名は実行前に拒否する。円弧の意味はCadQuery公式実装の`threePointArc`と`radiusArc`を追跡し、始点・通過点・終点または符号付き半径から構成した。

### 2. 有限文法から既存8射へのコンパイル

JSONの各stepは既存`CadExecutor`へ直接写す。押出しは直線経路の`sweep`、螺旋ばねは明示経路の`sweep`、穴は`combine(difference)`、鏡映と拡大縮小は`transform`のパラメータである。新しい幾何射は追加していない。

評価対象は次の6件とした。

| ケース | 文法上の特徴 | 主な射 |
|---|---|---|
| 6穴フランジ | 円、反復配置、差 | transform / sweep / combine |
| 圧縮ばね | 円断面、螺旋経路 | transform / sweep |
| 丸端リンク板 | 線分、3点円弧、半径円弧、2穴 | sweep / combine |
| 角丸ガスケット | 境界の平行集合、差、押出し | select / sweep / combine |
| 開放薄肉箱 | 面選択、法線方向の境界層 | select / sweep |
| 4辺角丸柱 | 辺選択、円板扇形による包絡 | select / sweep |

### 3. 法線束の掃引

`fillet`、`shell`、`offset2D`を9番目以降の射として追加しなかった。いずれも、選択した境界層に固定断面を法線方向へ運ぶ同じ`sweep`として表した。

```text
planar offset = boundary × normal interval -> parallel set
shell         = selected faces × normal interval -> boundary layer
fillet        = selected edge/vertex × disk sector -> rolling envelope
```

公開JSONでは`trajectory = normal_bundle`とし、許可する組を上の3種類へ閉じた。OpenCascadeの専用演算は数値的に頑健な実行方法として使うが、MORTRAの構成DAGへ記録する意味は一つの型付き`sweep`である。部品名や外観名は引数にできない。

### 4. 高次元backend

`nd_cell_backend.py`に、任意の有限次元に対する有理数座標のアフィン多面体backendを実装した。点から各軸方向へ`sweep`して4、5、6次元立方体を作り、有理行列で2次元へ`project`した。座標、辺、射の履歴はすべて厳密な分数として保存する。

これは一般の滑らかな4次元CADではない。現在の実行範囲は有限頂点・有限辺を持つアフィンセルである。

### 5. 外部corpusの構造監査

ローカルへ固定したCADTestBench生成コード2,400件をASTで解析した。各メソッド呼び出しを次へ分類した。

- 現在の8射または有限入力で表せる
- 幾何構成ではない検査・数値処理
- 有限入力文法の不足
- 既存8射の実装上の不足
- 未分類

この監査はCADを実行して正解判定するベンチマークではなく、操作語彙の静的被覆測定である。

### 6. 公開研究と公式実装から採用した判断

今回の実装は、公開資料を名前だけ並べて接続したものではない。各資料が扱う数学対象と検証方法を分け、現在のMORTRAで再現できる部分だけを採用した。

| 資料 | 確認した構造 | MORTRAへ反映した判断 |
|---|---|---|
| [SketchGraphs](https://github.com/PrincetonLIPS/SketchGraphs) | 線分・円などの原始図形を頂点、幾何制約を辺とする制約グラフ。1,500万スケッチを公開 | 入力を完成B-repではなく、有限な原始図形と制約の直列化データに限定 |
| [CADTestBench](https://github.com/dimitrismallis/CADTestBench) | 生成物を参照画像との近さではなく、B-rep上の実行可能な幾何・位相述語で判定 | 妥当性、連結成分数、体積式、投影領域を独立した検査として保存 |
| [BenchCAD](https://arxiv.org/abs/2605.10865) | 106工業部品族・17,900件の実行確認済みCadQueryプログラム。未見部品族への一般化不足を報告 | 部品名の命令を増やさず、曲線経路、断面列、ねじれを共通`sweep`のデータ差として扱う |
| [CADBench](https://arxiv.org/abs/2605.10873) / [CADEngBench](https://arxiv.org/abs/2608.09296) | 形状族、細部、パラメータ変更、B-rep妥当性、製造可能性を分けて評価 | 同じ操作列のパラメータ変更と、異なる位相を持つ固定形状の両方を試験 |
| [FutureCAD / BRepGround](https://arxiv.org/abs/2603.11831) | 角丸や面取りでは、画像上の類似だけでなくB-rep上の対象辺・面との対応が必要 | `select`で対象境界を明示し、生成後のB-rep妥当性と単一ソリッド性を検査 |
| [Ortho2CAD](https://arxiv.org/abs/2607.08891) | STEPから隠れ線と主要寸法を含む正投影図を生成し、編集可能なCadQueryへ接続 | 表示輪郭を手書きせず、同じB-repから正投影、隠れ線、断面、寸法を導出 |
| [Training AI to Paint with Code](https://surya.website/rling-qwen-to-paint-with-code) | 長いAPI説明より、実在する少数操作の厳格な許可リストと実行結果による評価が有効だった実験 | 8射以外の任意操作、Pythonコールバック、native objectを外部プログラムから拒否 |
| [CadQuery](https://github.com/CadQuery/cadquery) / [build123d](https://github.com/gumyr/build123d) | OpenCascade上の円弧、経路sweep、B-rep、STEP・STL・DXF出力の実装 | `radiusArc`の符号、断面座標枠、経路sweep、直列STLメッシュ化をソースと実行結果で照合 |
| [Basic Blueprint Reading](https://open.umn.edu/opentextbooks/textbooks/990) / [NASA KSC-GP-435 Vol. I](https://ntrs.nasa.gov/citations/20205010487) | 正投影、線種、中心線、断面、寸法、図面用紙、第三角法の製図要素 | 同じB-repから第三角法、隠れ線、中心線、断面ハッチ、主要寸法を導出 |

`mathbullet/skills`は、外部資料の調査、引用、論文解説、日本語記録の作法を提供する。CAD kernelや新しい幾何射は提供しない。そのため、研究記録の方法には利用したが、構造被覆率や生成能力の根拠には数えていない。

## 結果

### 有限言語と高次元実行

- native CAD objectを外部入力として受け取る経路: 0
- 未知入力種・コールバック・前方参照の拒否: 回帰テストで確認
- 6つの宣言的CADプログラム: すべて実行可能
- 6穴フランジ: `23890.17850237051 mm^3`、閉形式期待値と一致
- 3巻き螺旋ばね: `1980.19235467032 mm^3`、`pi r^2 L`と0.01以内で一致
- 丸端2穴リンク板: `1013.62830044411 mm^3 = 800 + 68pi`と一致
- 角丸ガスケット: `824.54866776462 mm^3`と解析式が一致
- 開放薄肉箱: `7152 mm^3`と外箱・内箱の体積差が一致
- 4辺角丸柱: `5922.74333882308 mm^3`と角丸断面の解析式が一致
- 6件すべて: valid B-rep、単一ソリッド、STEPを確認
- 螺旋ばねを除く5件: STL、第三角法SVG、DXF、断面図を生成
- 4次元立方体: 16頂点、32辺
- 5次元立方体: 32頂点、80辺
- 6次元立方体: 64頂点、192辺
- 4、5、6次元から2次元への射影: 厳密有理数で再生
- 追加した幾何射: 0
- 関連回帰テスト: 36 / 36成功

### CADTestBench構造監査

| 指標 | 結果 |
|---|---:|
| 解析対象 | 2,400 / 2,400ファイル |
| 幾何構成呼び出し | 24,213 |
| 現runtimeで構造的に表現可能 | 23,946 |
| 呼び出し被覆率 | 98.8973% |
| 全構成呼び出しが被覆されたファイル | 2,277 / 2,400 |
| ファイル被覆率 | 94.875% |

前回未接続だった`fillet` 135回、`shell` 21回、`offset2D` 3回、合計159呼び出しを一つの法線束掃引へ接続した。有限入力側では一般`arc` 9回、一般`spline` 6回が残る。`chamfer`、`split`、`interpPlate`、`text`と低頻度の未分類呼び出しも残るため、98.8973%をCAD正答率とは呼ばない。

## 考察

### 何が改善したか

従来は、複雑な形状をPython関数で作って`input_cell`へ渡せた。その状態では「8射で生成した」のか「入力で完成していた」のかを区別できない。今回、入力を有限JSONへ制限したことで、形状の変化は入力データと8射の履歴へ明示的に残る。

螺旋ばねは新しい`spring`命令ではなく、円断面と螺旋pathの`sweep`として動いた。丸端リンク板も`rounded_link`命令を使わず、線分と円弧の閉曲線から構成できた。これは部品名の暗記ではなく、入力幾何と合成の再利用である。

螺旋ばねは厳密STEPと証明書までを採点した。管状sweepのSTL分割が固定OCP環境で長時間化したため、STL・第三角法図面を完了扱いにはしていない。フランジとリンク板はSTEP、STL、SVG、DXFを生成し、図面を画像化して目視検査した。

### 失敗から修正した点

最初のばね断面は固定`YZ`平面に置かれ、螺旋の始点接線と直交していなかった。B-repはvalidかつsingle solidだったが、体積は約`3.74e-6 mm^3`で実体がなかった。有限文法へ任意局所座標枠を追加し、断面法線を接線へ一致させ、`pi r^2 L`で体積を検査した。

最初のリンク板では符号付き半径の向きが逆で、右円弧が内側へ曲がり、右穴が外周へ開いていた。画像検査で発見し、半径符号を修正した上で`800 + 68pi`の閉形式体積を制約へ追加した。この二例から、`is_valid`と`single_solid`だけでは意味上の正しさを保証しないことが確認できた。

4、5、6次元立方体はOpenCascadeの3次元制約を越えて実行できた。重要なのは高次元ごとの新しい射を追加しなかった点である。同じ`sweep`と`project`を、厳密アフィンセルbackendが実行した。回帰テストでは1次元から7次元まで、頂点数`2^n`と辺数`n 2^(n-1)`を照合した。

### 3操作を一つへ縮約できた理由

3操作は見た目もCAD API名も異なるが、数学的には「選択した境界の各点に法線方向の断面を対応させ、その全体を掃く」という同じ構造を持つ。違いは運ぶ断面と得る対象である。

- `offset2D`: 法線区間を運んだ平行集合。
- `shell`: 面上で法線区間を運んだ境界層。
- `fillet`: 辺または頂点上で円板扇形を運んだ包絡。

この縮約は、API呼び出しを同じ名前へ置換しただけではない。2次元角丸と3次元角丸が同じ公開構文で動くこと、距離だけを変えて操作集合を変えずに形状が変わること、ガスケット・薄肉箱・角丸柱で有効B-repが得られることを別々に試験した。ただし、自己交差、曲率半径を越えるオフセット、複数連結成分の位相変化は追加試験が必要である。

### 現在の工学的境界

この実験が扱うのは幾何、位相、投影、基本注記である。材料、荷重、応力、疲労、熱、加工法、公差、表面粗さ、GD&T、組立順序、BOMは未接続である。機械製図として出力できても、ASMEまたはISO適合を認証したわけではない。

## 結論

MORTRAの3次元生成は、任意B-repを入力へ隠す方式から、有限入力文法と8射の宣言的プログラムへ移行した。未見の螺旋経路と線・円弧sketchに加え、平面オフセット、薄肉化、2次元・3次元角丸を一つの法線束掃引として実行した。4、5、6次元では厳密有理セルを同じ射で構成・射影した。外部2,400プログラムの静的監査では、幾何構成呼び出しの98.8973%が現在のruntimeへ構造的に対応した。

ただし、この数値は正答率ではない。次の本質的課題は、一般splineとchamferを同じ有限言語へ接続し、未知部品族、パラメータ摂動、機能編集を含む外部CAD課題を実行してB-rep述語で採点することである。高次元については、滑らかな法線束ではなく有限アフィンセルまでが現在の実行範囲である。

## 同日追補

後続の[工学意味層・12次元セル実行実験](MORTRA-ENGINEERING-SEMANTICS-AND-ND-GENERALIZATION-20260831.md)で、材料・製造・公差・基準・荷重を`property / relation / action`へ接続した。厳密アフィンセルの実行範囲は12次元まで測定した。これは物理的な高次元CADではなく、同じ型規則を別backendで実行できることの試験である。

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
  --output artifacts\declarative-engineering-generalization-20260831-normal-bundle\cadtestbench-operator-coverage-v2.json

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\experiment_declarative_engineering_generalization.py `
  --output artifacts\declarative-engineering-generalization-20260831-normal-bundle
```
