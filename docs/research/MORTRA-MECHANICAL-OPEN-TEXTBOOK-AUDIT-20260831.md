# MORTRA 機械工学オープン教材監査

監査日: 2026-08-31

## 監査範囲

Open Textbook LibraryのMechanical Engineering分類に掲載された21冊について、書誌情報、概要、目次または公開本文への導線を確認し、MORTRAへ接続すべき意味層を分類した。全ページを精読したという意味ではない。製図、設計、製造、力学に直接関係する教材を優先して本文・図例を追い、熱、流体、通信、オペレーションズ・リサーチは実行器の設計上の位置を確認した。

## 21冊の分類

### A. 製図・CAD・製造へ直接接続する

1. `Interpretation of Metal Fab Drawings`
2. `Basic Blueprint Reading`
3. `Manufacturing Processes 4-5`
4. `Introduction to Mechanical Engineering Design`
5. `Introduction to Mechanical Design and Manufacturing`

採用する意味層は、正投影、線種、隠れ線、中心線、断面、寸法、表題欄、加工可能性、材料選択、製造順序である。形状生成と製造制約は分離し、前者を8射、後者を`constrain`と`annotate`へ接続する。

### B. 荷重・剛体・材料強度へ接続する

6. `Engineering Statics: Open and Interactive`
7. `Engineering Mechanics: Statics`
8. `Essential Mechanics - Statics and Strength of Materials with MATLAB and Octave`
9. `Stability of Ships and Other Bodies`

必要な表現は、自由物体図、作用点付き力、モーメント、拘束反力、分布荷重、せん断力図、曲げモーメント図、断面二次モーメント、応力・ひずみである。これらは新しい形状射ではなく、同じ幾何対象へ付く物理量と証明義務として扱う。

### C. 運動・システム・最適化へ接続する

10. `Werktuigkundige Systemen`
11. `Engineering Systems, Dynamics, Modelling, Simulation, and Design`
12. `From theORy to application: learning to optimize with Operations Research in an interactive way`
13. `A Guide to MATLAB for ME 160`

状態、入力、出力、拘束、目的関数、時間発展、ボンドグラフ、数値検証を、静的な形状構成グラフとは別の実行層として接続する。MORTRAの`transform`列を運動計画へ拡張する際の基盤となる。

### D. 熱・流体・空力へ接続する

14. `Basics of Fluid Mechanics`
15. `Fundamentals of Compressible Flow Mechanics`
16. `Intermediate Fluid Mechanics`
17. `Aerodynamics and Aircraft Performance`
18. `Introduction to Engineering Thermodynamics`
19. `Engineering Thermodynamics`

必要な表現は、領域、境界、流束、保存則、状態量、構成式、境界条件である。幾何の`slice`と`select`で解析領域と境界を取り出し、偏微分方程式または集中定数モデルの解析器へ渡す。形状だけから性能を推定したことにはしない。

### E. 周辺だが表現設計に利用できる

20. `Introduction to Communication Systems`
21. `Transitioning towards a circular (healthcare) economy: Circular Economy principles, leadership, policy and decision-making`

前者は信号・状態・通信路、後者はライフサイクル、再利用、資源循環の表現に関係する。いずれも現在の機械図面の実行経路へ直結させず、将来のシステム制約、部品表、ライフサイクル評価の参照とする。

## MORTRAへの反映

今回の監査から、幾何射を増やす前に次の型を追加すべきだと分かる。

```text
Load(point/region, vector, time)
BoundaryCondition(entity, kind, value)
Material(entity, constitutive_law)
Tolerance(feature, datum, zone)
Process(feature, manufacturing_method)
State(system, variables, time)
Objective(system, quantity, direction)
```

これらは`fillet`や`gear`のような部品・外観名ではない。同じ形状へ力学、製造、運動、熱流体の制約を付加する意味対象であり、幾何基底を膨らませずに工学範囲を広げる。

## 実装反映

同日、上の候補を個別の幾何射として追加せず、次の三形式へ縮約した。

```text
property(subject, symbol, value, unit)
relation(subject, symbol, objects, value)
action(subject, symbol, components, unit, frame)
```

現在接続したのは、材料、密度、加工法、直線・角度公差、表面粗さ、基準、接合、力、モーメントである。フランジ、薄肉筐体、螺旋ばねの3件で、意味追加前後のB-repと8操作の頻度が一致し、密度と体積から質量を導出して第三角法図面へ注記した。詳細は[工学意味層・12次元セル実行実験](MORTRA-ENGINEERING-SEMANTICS-AND-ND-GENERALIZATION-20260831.md)に記録した。

## 結論

21冊の監査は、3次元形状生成だけでは機械設計にならないことを明確にした。現在の8操作は幾何生成と図面導出の基底として維持し、次に増やすのは部品名ではなく、荷重、材料、境界条件、公差、加工、状態、目的関数の型である。これにより、意味情報を付与した同一の立体から、機械図面、解析モデル、製造条件を分けて生成できる。

## 一次資料

- Open Textbook Library, `Mechanical Engineering Textbooks`
- 各書籍の公開書誌ページ、概要、目次、公開本文へのリンク
- NASA KSC, `Engineering Drawing Practices, Volume I`
- FreeCAD TechDraw、CadQuery、build123dの公式実装
