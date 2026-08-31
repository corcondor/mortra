# MORTRA 工学意味層・12次元セル実行実験

実験日: 2026-08-31

実装:

- `math_os_prototype/engineering_semantics.py`
- `math_os_prototype/engineering_program_spec.py`
- `math_os_prototype/engineering_cad_backend.py`
- `math_os_prototype/nd_cell_backend.py`
- `scripts/experiment_engineering_semantics_dimension_scaling.py`

成果物:

- `artifacts/engineering-semantics-dimension-scaling-20260831/summary.json`
- 各部品のSTEP、STL、第三角法SVG、DXF、再生JSON
- `exact-8d-projection.svg`

## 目的

前段の実験では、3次元部品と機械図面を次の8個の幾何操作へ縮約した。

```text
transform  sweep  combine  select
slice      project constrain annotate
```

しかし、形状だけでは機械設計にならない。材料、公差、表面粗さ、加工法、基準、接合、荷重は、同じ形状へ付く工学的意味である。本実験では、これらを部品別の新しい幾何操作として追加せず、少数の再利用可能な意味形式へ接続できるかを測った。

同時に、幾何核が3次元の名前へ固定されていないことを、4、6、8、10、12次元の厳密セル実行で確認した。

## 仮説

### 仮説1: 工学注記は三形式へ縮約できる

工学的意味を次の三形式で保持する。

```text
property(subject, symbol, value, unit)
relation(subject, symbol, objects, value)
action(subject, symbol, components, unit, frame)
```

- `property`: 材料、密度、加工法、公差、表面粗さ
- `relation`: 基準、接合
- `action`: 力、モーメント。力は `R^n` のベクトル、モーメントは座標平面ごとの反対称二階テンソルとして保持する

これらは形状を生成しないため、9番目以降の幾何操作にはしない。

### 仮説2: 同じ構成グラフから複数の成果物を導ける

構成グラフとは、処理の依存関係を循環なく記録した有向グラフである。一つの宣言的プログラムから、立体の境界表現（B-rep）、質量、第三角法、注記、STEP、STL、SVG、DXF、JSONを導く。意味情報の有無で形状または幾何演算列が変わった場合、この仮説は不成立とする。

### 仮説3: 幾何型は有限次元に一般化できる

物理的な機械図面は3次元だが、型付き幾何核は `Cell(k, R^n)` として任意の有限次元を扱える。OpenCascadeによる滑らかな境界表現と、高次元の厳密アフィンセルは別の実行器で処理し、同じ操作名を共有する。

## 一次資料から採用した原理

### 機械製図と設計

[Open Textbook LibraryのMechanical Engineering分類](https://open.umn.edu/opentextbooks/subjects/mechanical)は、2026-08-31時点で3ページ、21冊だった。全21書誌を分類し、製図・設計・製造・力学に直接関係する教材の目次と公開本文を優先して確認した。全書籍の全ページを精読したという意味ではない。

- [Basic Blueprint Reading](https://open.umn.edu/opentextbooks/textbooks/990)と[Interpretation of Metal Fab Drawings](https://open.umn.edu/opentextbooks/textbooks/interpretation-of-metal-fab-drawings)から、線種、正投影、断面、寸法、加工・溶接注記を形状と分離する必要性を採った。
- [Engineering Statics: Open and Interactive](https://open.umn.edu/opentextbooks/textbooks/1047)から、力とモーメントを作用対象・成分・座標枠付きの量として持つ構造を採った。
- [Introduction to Mechanical Engineering Design](https://open.umn.edu/opentextbooks/textbooks/introduction-to-mechanical-engineering-design)と[Introduction to Mechanical Design and Manufacturing](https://open.umn.edu/opentextbooks/textbooks/introduction-to-mechanical-design-and-manufacturing)から、形状、要求、材料、加工、検証を別の責務として保持する判断を採った。
- [NASA Engineering Drawing Practices](https://ntrs.nasa.gov/citations/20205010487)とNASAの公開機械図面例から、第三角法、寸法・公差、材料・仕上げ、表題欄を同一図面へ置く構成を確認した。
- [FreeCAD TechDraw ProjectionGroup](https://reqrefusion.github.io/FreeCAD-Documentation-html/wiki/TechDraw_ProjectionGroup.html)から、共通縮尺を持つ正投影群と第三角法の配置を確認した。

### CADを画像でなくプログラムとして持つ

- [DeepCAD](https://arxiv.org/abs/2105.09492)は、形状を編集可能なCAD操作列として扱い、178,238個のCAD操作列を公開した。MORTRAでは学習モデルを移植せず、構成列を第一級成果物として残す原理を採った。
- [SketchGraphs](https://github.com/PrincetonLIPS/SketchGraphs)は、1,500万スケッチを原始図形と制約のグラフとして公開している。MORTRAの有限JSONも、完成画像ではなく原始図形、制約、構成列を保存する。
- [Vitruvion](https://arxiv.org/abs/2109.14124)は、設計意図を原始図形だけでなく参照可能な制約として表す。MORTRAでは公差、基準、荷重も対象参照を失わない型付きassertionにした。
- [ShapeAssembly](https://arxiv.org/abs/2009.08026)は、3D形状を低水準の組立DSLとして構成する。MORTRAでは部品名を命令にせず、反復、変換、合成を既存操作の列として持つ。
- [CADMorph](https://arxiv.org/abs/2512.11480)は、CADの操作列と可視形状を同時に保ち、plan-generate-verifyで編集する。MORTRAでは意味追加の前後で形状と演算列が不変かを直接比較した。

### コード描画と研究記録

[Training AI to Paint with Code](https://surya.website/rling-qwen-to-paint-with-code)から採ったのは、画像生成モデルではなく次の設計判断である。

1. コードを編集可能な成果物として残す。
2. 長い任意APIではなく、実在する少数操作の許可リストへ閉じる。
3. 実行可能性の合否判定と、視覚的な良さの評価を分離する。
4. 相関した多数の指標を重ねず、独立した少数の評価へ整理する。

MORTRAでは幾何の正しさを美的評価で決めない。境界表現、制約、証明書で真偽を固定した後、同じ数学図形へ別の描画規則を適用する。将来、製図、建築表現、生成アートを比較する場合も、この順序を守る。

[mathbullet/skills](https://github.com/mathbullet/skills)はCAD実装ではない。調査、引用、論文解説、日本語記録の手順だけに利用し、幾何能力の根拠には数えていない。

## 方法

### 1. 閉じた工学意味語彙

今回の実装は、任意文字列を新しい命令として実行しない。三形式の内部で許す記号と単位を閉じた。

```text
property:
  material, density[kg/m^3], manufacturing_process,
  linear_tolerance[mm], angular_tolerance[deg],
  surface_roughness[um]

relation:
  datum, joint

action:
  force[N], moment[N*mm]
```

未知記号、単位不一致、存在しない対象、次元と成分数が一致しない作用は実行前に拒否する。`n` 次元の力は `n` 成分、モーメントは `n(n-1)/2` 成分を要求する。密度と境界表現から得た体積が揃った場合だけ質量を導出する。

### 2. 因果比較

既存の次の3プログラムを、意味情報なしと意味情報ありで二重実行した。

- 6穴フランジ
- 開放薄肉筐体
- 螺旋ばね

比較項目は体積、表面積、ソリッド数、面数、辺数、境界箱、B-rep妥当性、8操作の頻度である。すべて一致し、質量と図面注記だけが増えた場合を成功とした。

### 3. 図面生成

同じB-repから次を生成した。

- TOP、FRONT、RIGHTの第三角法
- 等角図
- 隠れ線、中心線
- 断面とハッチ
- 主要寸法、材料、密度、加工法、公差、粗さ、基準、荷重、質量
- STEP、STL、SVG、DXF、再生JSON

注記数が増えても表題欄へ重ならないよう、注記領域の行間と文字寸法を内容量から計算するよう修正し、SVGを画像化して目視確認した。

### 4. 4から12次元の厳密実行

各次元で原点から座標軸方向へ`sweep`を繰り返し、n次元超立方体を構成した。期待値は次である。

```text
vertices = 2^n
edges    = n * 2^(n-1)
```

座標はすべて有理数として保持した。8次元セルは、8方向の対称な有理射影で2次元へ写し、SVGにした。

## 結果

### 工学意味層

| ケース | 形状不変 | 演算列不変 | 導出質量 |
|---|---:|---:|---:|
| 6穴フランジ | 成功 | 成功 | 0.187538 kg |
| 開放薄肉筐体 | 成功 | 成功 | 0.0191674 kg |
| 螺旋ばね | 成功 | 成功 | 0.0154455 kg |

- 成功: 3 / 3
- 新しい幾何操作: 0
- 追加した意味形式: 3
- STEP/STL/SVG/DXF/JSON: 3部品すべて生成
- 工学意味層、宣言的CAD、高次元セルの回帰テスト: 26 / 26成功
- 生成幾何、異分野間幾何変換を加えた広域回帰テスト: 57 / 57成功

### 高次元セル

| 次元 | 頂点 | 辺 | 期待値一致 | 有理数厳密実行 |
|---:|---:|---:|---:|---:|
| 4 | 16 | 32 | 成功 | 成功 |
| 6 | 64 | 192 | 成功 | 成功 |
| 8 | 256 | 1,024 | 成功 | 成功 |
| 10 | 1,024 | 5,120 | 成功 | 成功 |
| 12 | 4,096 | 24,576 | 成功 | 成功 |

## 考察

### 何が汎化したか

材料、加工法、公差、基準、荷重を追加しても、形状と8操作の列は変わらなかった。これは、工学情報を部品固有命令へ増殖させず、同じ対象へ付く意味として保持できたことを示す。

高次元側でも、4次元用、8次元用、12次元用の操作は追加していない。点、掃引、射影の型規則と実行器だけを共有した。

### 製図・建築・生成アートへどう接続するか

同じ構成グラフは次の二層へ分ける。

```text
mathematical construction
  -> exact boundary representation / constraint graph / proof certificate
  -> drawing policy
       technical drawing / architectural linework / ink / WebGL / SVG
```

ロゼット、格子、ファサード、エンブレムを新しい幾何操作にしない。既存の点、線、円、交点、変換、掃引、合成、射影の列として作り、見せ方だけを描画規則へ分離する。コード描画の評価は、まず実行可能性、幾何制約、不変量の合否を判定し、その後に対称性、可読性、視覚的多様性を測る。

### まだ示していないこと

- ASME Y14、ISO 128/129、JISへの適合認証はしていない。
- feature control frameを含む完全GD&T、溶接記号、BOM、組立順序、締結部品規格は未実装である。
- 荷重を記録できるが、応力、疲労、熱、流体の解析器へは未接続である。
- 12次元結果は数学的なアフィンセル実行であり、12次元の物理部品を主張しない。
- 滑らかなB-repと機械図面の実行範囲は現在3次元である。
- 3部品は意味層の因果試験であり、任意工業製品への完全性を証明しない。

## 結論

MORTRAは、既存8個の幾何操作を増やさず、材料・製造・公差・基準・荷重を`property / relation / action`の三形式へ接続した。3部品の比較では、形状と演算列を変えずに質量と第三角法注記を生成できた。

同じ型規則は、厳密アフィンセルとして12次元まで実行できた。したがって現在の設計は、物理的な3次元CADと、任意有限次元の数学的構成核を混同せずに共有できる。

次の最小追加は新しい部品名ではない。完全GD&Tと溶接記号を`relation`へ、境界条件と分布荷重を`action`へ、材料構成則と解析結果を`property`へ接続し、外部の凍結CAD課題でB-rep、図面、機能制約を同時採点することである。

## 再実行

```powershell
C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe -m pytest `
  math_os_prototype\test_engineering_semantics.py `
  math_os_prototype\test_engineering_program_spec.py `
  math_os_prototype\test_nd_cell_backend.py -q

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\experiment_engineering_semantics_dimension_scaling.py
```
