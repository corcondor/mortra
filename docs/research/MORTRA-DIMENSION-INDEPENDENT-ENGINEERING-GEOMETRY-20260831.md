# MORTRA 次元非依存幾何基底・3D機械製図実験

実験日: 2026-08-31

IR: `math_os_prototype/engineering_geometry_ir.py`

CAD実行: `math_os_prototype/engineering_cad_backend.py`
実験: `scripts/experiment_engineering_geometry_basis.py`

## 目的

MORTRAの平面幾何と作図で使ってきた考え方を、部品名ごとの命令へ増殖させずに3次元設計へ拡張する。具体的には次を同時に満たすことを目的とした。

1. `Extrude`、`Revolve`、`Loft`などを別々の原始操作として記憶しない。
2. 同じ型付き構成DAGから、厳密な3D形状、第三角法、隠れ線、断面、寸法、STEP、STL、SVG、DXFを生成する。
3. 寸法を変えた未見例だけでなく、基底側にない形状族でも新しい演算族を追加せずに実行する。
4. 3次元固有の名前を増やさず、将来の4次元以上でも同じ型規則を使えるようにする。

## 仮説

工業部品の構成を次の8射へ縮約できると仮定した。

```text
transform  sweep  combine  select
slice      project constrain annotate
```

ここで、押出し、回転、ロフトはすべて「断面を経路に沿って運ぶ」`sweep`のパラメータである。正投影と等角投影は`project`、断面図は`slice`、穴や和・差は`combine`である。部品名や外観名は原始操作にしない。

型は `Cell(k, R^n)`、すなわち「`n`次元空間に埋め込まれた`k`次元セル」とした。射のシグネチャは次元を数値として扱う。

```text
sweep_d : Cell(k, R^n) -> Cell(min(k+d,n), R^n)
slice_c : Cell(k, R^n) -> Cell(k-c, R^n)
project_m : Cell(k, R^n) -> Cell(min(k,m), R^m)
```

## 一次資料と採用した原理

### 機械製図

- [Basic Blueprint Reading](https://open.umn.edu/opentextbooks/textbooks/990)と[Interpretation of Metal Fab Drawings](https://open.umn.edu/opentextbooks/textbooks/interpretation-of-metal-fab-drawings)から、正投影、隠れ線、中心線、断面、寸法、表題欄を別々の意味層として扱う構成を採った。
- [Open Textbook LibraryのMechanical Engineering一覧](https://open.umn.edu/opentextbooks/subjects/mechanical)を監査し、製図に直接関係する上記2冊に加え、[Manufacturing Processes 4-5](https://open.umn.edu/opentextbooks/textbooks/manufacturing-processes-4-5)、[Introduction to Mechanical Engineering Design](https://open.umn.edu/opentextbooks/textbooks/introduction-to-mechanical-engineering-design)、[Introduction to Mechanical Design and Manufacturing](https://open.umn.edu/opentextbooks/textbooks/introduction-to-mechanical-design-and-manufacturing)を、加工制約を図形生成と混同しないための参照にした。
- NASA KSCの[Engineering Drawing Practices, Volume I](https://standards.nasa.gov/sites/default/files/standards/KSC/H/1/GP-435-Vol-I-Chg-H-1.pdf)が要求するnative CAD、DXF、PDF、annotated STEPという複数成果物の考え方を、同一B-repからの複数出力として採った。ただし今回の図面をNASA、ASME、ISO適合とは判定していない。

### CAD実行と隠れ線

- [FreeCAD TechDrawのDrawViewPart.cpp](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/TechDraw/App/DrawViewPart.cpp)は、3D B-repからOpenCascadeのhidden-line removalを使って2D投影を導く。MORTRAでも手書きの2D輪郭を廃し、同じ方式で可視線と隠れ線を分離した。
- [FreeCAD TechDraw SectionView](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDraw_SectionView.md)に従い、断面は独立した絵ではなく基準形状と切断面から導出した。
- [build123d](https://github.com/gumyr/build123d)の`Drawing`、`TechnicalDrawing`、STEP/STL/SVG/DXF exporterを、監査したrevision `51f251b854b1b8e4b5d6fd4698f5a41d40f839fc`へ固定した。
- [build123d technical drawing example](https://github.com/gumyr/build123d/blob/dev/docs/technical_drawing.py)から、投影、寸法、レイヤー、SVGを同じB-repへ接続する実装方法を確認した。

### 実行可能評価

- [CADTestBench](https://github.com/dimitrismallis/CADTestBench)は、レンダリング画像ではなく実行可能なB-rep述語でCADを評価する。MORTRAでも`is_valid`、単一ソリッド、正体積、閉形式体積を画像評価から分離した。監査revisionは`e29283cc61db7329039d95b429766a50bfd37f89`である。
- [BenchCAD](https://github.com/BenchCAD/BenchCAD-main)の実行検証済みCADプログラムという考え方を参照し、各成果物に構成DAG、演算頻度、制約結果をJSONで保存した。
- [RLearning Qwen to Paint with Code](https://surya.website/rling-qwen-to-paint-with-code)では、長いAPIと相関した多数の評価が探索を悪化させ、小さい許可APIと独立した実行評価が有効だった。MORTRAでは部品別APIを増やさず、8射のallowlistと独立制約を採った。
- [mathbullet/skills](https://github.com/mathbullet/skills)は幾何実装へ混ぜず、事実、根拠、MORTRAでの解釈を分離する研究記録の書式だけに利用した。監査revisionは`fe96c626b39abba47fad2d4a4ef738e8a27602b1`である。

## 方法

### 1. 固定型の縮約

従来の12個の3D名を次のように8射へ写した。

| 従来名 | 共通射 | パラメータ |
|---|---|---|
| `Rotate3` | `transform` | rigid rotation |
| `Extrude` | `sweep` | line trajectory |
| `Revolve` | `sweep` | circular trajectory |
| `Loft` | `sweep` | section family |
| `Boundary` | `select` | boundary selector |
| `CrossSection` | `slice` | affine flat |

`Line3`、`Curve3`、`Surface`などは操作ではなく`Cell(k, R^3)`のデータ型であるため、射の個数には数えない。

### 2. 基底側の5形状族

- 穴配列を持つフランジ
- 中空段付き軸
- 二面ブラケット
- 角形から円形へ遷移するダクト
- 建築格子パネル

### 3. 未見評価

二種類を分けて測った。

- 寸法未見3件: フランジ、軸、ダクトの寸法・穴数を変更。
- トポロジー未見3件: スポーク車輪、クレビス、三軸交差流路ブロック。基底5形状族には含めなかった。

後者は新しい部品名を原始操作にせず、既存8射の構成プログラムとしてのみ記述した。

### 4. 図面生成

各B-repから次を自動生成した。

1. TOP、FRONT、RIGHTを共通縮尺で第三角法配置。
2. 等角図を独立した表示縮尺で配置。
3. OpenCascade HLRから可視線と隠れ線を分離。
4. 正確なB-repと平面の交差から断面面を得る。
5. 45度平行線を各断面面で厳密にclipしてハッチを作る。
6. 中心線、全体寸法、パラメータ由来の主要寸法、表題欄を配置。
7. 同じ形状からSTEP、STL、SVG、DXF、再生JSONを保存。

## 結果

| 項目 | 結果 |
|---|---:|
| 基底形状族 | 5 |
| 寸法未見 | 3 / 3成功 |
| トポロジー未見 | 3 / 3成功 |
| 全部品 | 11 / 11成功 |
| B-rep妥当 | 11 / 11 |
| 単一ソリッド | 11 / 11 |
| 断面・ハッチ生成 | 11 / 11 |
| 投影領域内への収容 | 44 / 44 view |
| STEP/STL/SVG/DXF | 44 / 44非空 |
| 未見側が要求した新演算族 | 0 |
| 使用した演算族 | 7 / 8 |
| 回帰テスト | 16 / 16成功 |
| 11部品の全成果物生成時間 | 101.12秒 |

`select`は基底に含むが、今回の11部品では明示的な面・辺選択を必要としなかったため未使用だった。未見側に合わせて削除も追加もしていない。

成果物:

- `artifacts/engineering-geometry-basis-20260831/gallery.html`
- `artifacts/engineering-geometry-basis-20260831/contact-sheet.png`
- `artifacts/engineering-geometry-basis-20260831/summary.json`
- 各部品ディレクトリのSTEP、STL、SVG、DXF、JSON

## 考察

### 何が汎化したか

寸法未見だけでなく、スポークによる反復・二枚のラグ・三軸の交差穴という異なるトポロジーでも、操作集合は変わらなかった。差は`transform`の反復数、`sweep`の経路、`combine`の和差、制約値に現れた。したがって、この有限実験では部品名ごとの射を増やす必要はなかった。

図面も別モデルではない。3D形状、断面、隠れ線、寸法、ファイル出力が同じDAGとB-repを共有するため、2D図と3Dモデルの食い違いを構造的に減らせる。

### 何をまだ示していないか

- 11部品は有限実験であり、任意の工業製品を8射で完全に表せるという完全性定理ではない。
- 幾何と図面は生成したが、材料、荷重、疲労、熱、加工公差、表面粗さ、GD&T、組立順序、BOMは未実装である。
- STEPは形状交換用であり、今回の出力はannotated AP242 PMIを保証しない。
- 図面は第三角法、隠れ線、断面、基本寸法を備えるが、ASME Y14またはISO 128/129への適合認証は行っていない。
- トポロジー未見は人が選んだ3族であり、CADTestBenchやBenchCAD全体での外部ベンチマークは次段階である。

### 次元拡張の境界

IRの型検査では、同じ`sweep`が`Cell(2,R^3)->Cell(3,R^3)`と`Cell(3,R^4)->Cell(4,R^4)`の両方で動くことをテストした。したがって語彙は3次元に固定されていない。

一方、今回の具体的B-rep実行はOpenCascadeに依存するため`R^3`までである。4次元以上を実行するには、凸多面体・セル複体・記号制約を扱う別backendが必要になる。必要なのは新しい部品別射ではなく、同じ8射を実行する別表現である。

## 結論

MORTRAの3D拡張は、12個の3D固有名を増やす方式から、次元添字を持つセルと8個の共通射へ移行した。11部品の有限実験では、基底にない3形状族を含めて新しい演算族なしで厳密B-rep、第三角法、隠れ線、断面ハッチ、寸法、STEP/STL/SVG/DXFを生成できた。

次に増やすべきものは部品名や外観名ではない。材料・公差・力学・加工・組立を`constrain`と`annotate`へ型付きで接続すること、そして外部の凍結CAD課題で同じ8射の被覆率を測ることである。

## 再実行

```powershell
C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe -m pytest `
  math_os_prototype\test_engineering_geometry_ir.py `
  math_os_prototype\test_engineering_cad_backend.py -q

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\experiment_engineering_geometry_basis.py `
  --drawings all `
  --output artifacts\engineering-geometry-basis-20260831

C:\Users\81808\.cache\mortra-cad-venv\Scripts\python.exe `
  scripts\build_engineering_geometry_gallery.py `
  artifacts\engineering-geometry-basis-20260831
```
