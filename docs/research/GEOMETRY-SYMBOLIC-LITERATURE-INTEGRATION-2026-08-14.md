# 幾何記号推論の一次資料監査とMORTRA統合状況

記録日: 2026-08-14（古典系・AG2追記 2026-08-14）

## 結論

画像に挙がった研究は、すべて同じものではない。共通核は次の5段である。

まず既存監査（ML系6系統）を振り返り、その後に古典の一次資料（Gelernter、Chou/Gao/Zhang 三部作、Nevins）と AlphaGeometry2 を追記する。古典系が示すのは、現在の「LLM提案+記号検証」の構造が1960年代から存在し、MORTRAの「標準模型」は Chou/Gao/Zhang の演繹DB（固定点閉包）として既に定義可能であることだ。

1. 自然文・TeX・図を有限の型付き述語へ変換する。
2. 定理を、複数前提から結論へ向かうハイパーエッジとして表す。
3. 前向き閉包と後向きゴール分解を合流させる。
4. 補助点・補助線・中間命題を提案し、型検査と反例で絞る。
5. 角度追跡、距離・比、連立方程式、多項式イデアルを厳密backendで閉じる。

MORTRAへ直接採用できるのは記号部分である。T5、ViT、BLIP、外部API、LLMによる補助構成提案は、外部LLM不使用という実験条件と衝突する。その部分は有限文法、型付き項合成、列挙探索へ置き換える。

## 一次資料と公開実装

| 系統 | 一次資料 | 論文・コードで確認した中核 | MORTRAでの扱い |
|---|---|---|---|
| Wu + DD/AR | [arXiv:2404.06405](https://arxiv.org/abs/2404.06405), [AlphaGeometry](https://github.com/google-deepmind/alphageometry) | Wu単独15/30、Wu+DD+角度/比/距離追跡21/30、AlphaGeometryとのensemble 27/30。DDとARを交互に飽和させ、依存を追跡する。 | 多項式化、座標ゲージ固定、消去イデアル、一意正値fiberを実装。完全なWu特性列法とは区別する。DD/ARの依存追跡は定理ハイパーグラフへ統合する。 |
| FormalGeo / FGPS | [arXiv:2310.18021](https://arxiv.org/abs/2310.18021), [FormalGeo](https://github.com/FormalGeo/FormalGeo), [FGPS](https://github.com/BitSecret/FGPS) | 88述語、196定理、CDL/PDDL/TDDL/GPL、前向き・後向き探索。goal依存との交差、新規未知量の最小化、既知量との重なりを探索制御に使う。 | GPL本体は組み込まず、型付きHornハイパーエッジ、後向きrelevance slice、前向き閉包、依存最小化順位を独立実装。 |
| FGeo-Parser / HyperGNet | [FGeo-Parser](https://www.mdpi.com/2073-8994/17/1/8), [GeoParser code](https://github.com/RuRuo0/GeoParser), [IJCAI 2025 paper](https://www.ijcai.org/proceedings/2025/0527.pdf), [HyperGNet code](https://github.com/BitSecret/HyperGNet) | Parserは自然文と図から形式言語へ変換する。HyperGNetは証明状態のハイパーグラフから次定理を予測し、適用を反復する。 | 形式言語・データ仕様は参考にする。T5/ViT/BLIPとニューラル定理予測は採用せず、有限文法と型付き探索の比較ablationにする。 |
| AutoGPS | [arXiv:2505.23381](https://arxiv.org/abs/2505.23381), [code](https://github.com/Jayce-Ping/AutoGPS) | multimodal formalizerと、proof graph上の前向き導出・後向きgoal分解を行う記号推論器を分離。stepwise coherence 99%を報告。 | 外部APIを使うformalizerは採用しない。記号reasonerの双方向proof graph、代数推論、証明再生の設計を独立実装する。取得版にライセンスファイルがないためコードはコピーしない。 |
| Hilbert-Geo | [CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Xu_Hilbert-Geo_Solving_Solid_Geometric_Problems_by_Neural-Symbolic_Reasoning_CVPR_2026_paper.html), [arXiv:2605.16385](https://arxiv.org/abs/2605.16385) | 立体幾何用CDL、Parse2Reason、定理bank。SolidFGeo2k 77.3%、PlaneFGeo3k 80.2%を報告。 | 公開論文から立体の点・直線・平面・包含・平行・垂直・距離・角の型を独立実装する。論文が予告する公式コードは監査時点で確認できないので完全再現とは呼ばない。 |
| Seed-Geometry / Seed-Prover | [ByteDance primary page](https://seed.bytedance.com/public_papers/seed-prover-deep-and-broad-reasoning-for-automated-theorem-proving), [arXiv:2507.23726](https://arxiv.org/abs/2507.23726), [code](https://github.com/ByteDance-Seed/Seed-Prover) | deep/broad探索、補題単位の証明提案、検証器feedback、自己要約。Seed-GeometryはIMO-AG-50で43/50を報告。 | LLM提案器は採用しない。探索frontierの多様化、補助構成の型付き列挙、検証失敗からの制約追加を実装対象にする。 |

## 取得して監査した公開コード

| repository | 固定commit | ライセンス監査 |
|---|---|---:|
| google-deepmind/alphageometry | `6777cb5` | Apache-2.0 |
| FormalGeo/FormalGeo | `e7d9042` | GPL-3.0、直接組込みなし |
| BitSecret/FGPS | `4fbee33` | MIT |
| RuRuo0/GeoParser | `59b974a` | 取得版にLICENSEなし、コピーなし |
| BitSecret/HyperGNet | `80dc8c5` | MIT |
| Jayce-Ping/AutoGPS | `f2095a2` | 取得版にLICENSEなし、コピーなし |

## 古典の一次資料（追記）

ML系6系統だけでは「LLM提案+記号検証」の由来を説明できない。以下が原典である。

| 系統 | 一次資料 | 中核 | MORTRAでの扱い |
|---|---|---|---|
| 図を意味モデルにした最初の幾何証明器 | H. Gelernter, "Realization of a geometry theorem proving machine", IFIP Congress, 1959, 273-281; 同 "Intelligent behavior in problem-solving machines", IBM JRD 2(4), 1958 | 形式系の**図（semantic model）**を探索のheuristicに使う。syntax computer が推測を検証し、semantic（図）が候補を絞る。図は形式的証明と1対1対応でなくてよく、「十分な数の点で一致すれば」有用と明言 | MORTRAの「図は証明の挿絵ではなく同じ証明状態の眺め」はこの構造の現代版。図は標準模型（座標付き構成）から射影として描き、検証はsyntax側（CAS/証明)が行う |
| 面積法 | S.-C. Chou, X.-S. Gao, J.-Z. Zhang, "Machine Proofs in Geometry", World Scientific, 1994 | 幾何不変量（有向線分比・符号付き面積・Pythagoras差）で構成点を逆順に消去。**構成的幾何文のクラスで完全**。478題を自動証明し、読みやすい短い証明を出す | MORTRAの `wu_geometry_kernel`（座標多項式・消去イデアル）とは別の、座標フリーの消去法。可読証明生成（教育目的）は MORTRA の Experience 軸に直接つながる |
| 全角法（アーベル幾何） | S.-C. Chou, X.-S. Gao, J.-Z. Zhang, "Automated generation of readable proofs with geometric invariants, II: Proving theorems with full-angles", JAR 17(3), 1996, 349-370 | 有向角（full angle）を**加法群**として扱い、角度追跡を代数化する。Wuが角の合同を代数式にしたのを発展させ、2α=2β から α=β または α=β+∠[1] の分岐を得る | MORTRAの「アーベル幾何」の原典。角度のアーベル群構造（角追跡=群上の線形代数）を型付き対象として実装する |
| 演繹DB（標準模型の原典） | S.-C. Chou, X.-S. Gao, J.-Z. Zhang, "A deductive database approach to automated geometry theorem proving and discovering", JAR 25(3), 2000, 219-246 | 幾何構成に対して固定規則集合で**前向き固定点**を求め、導出可能な全性質を列挙。構造化DBで100倍削減、data-based探索、**補助点の追加方法と数値図モデルの自動構成**も扱う。160構成でテスト | MORTRAの「標準模型」を固定点閉包として定義する根拠。前向き閉包・構造化DB・補助点Skolem化は theorem hypergraph と統合する |
| 前向き連鎖の先駆 | A. J. Nevins, "Plane geometry theorem proving using forward chaining", Artif. Intell. 6, 1975, 1-23 | 前向き連鎖を主とした平面幾何証明 | 前向き閉包の実装基礎 |
| 面積法の形式化 | P. Janičić, J. Narboux, P. Quaresma, "The Area Method: a recapitulation"（Coqで健全性証明済み） | 面積法の公理系・補題をCoqで機械検証。アルゴリズムと実装詳細の完全な記述 | MORTRAが「証明した」と呼ぶための検証基準の参考 |

## AlphaGeometry2（追記）

一次資料: arXiv:2502.03544 / JMLR 26(241), 2025 / [google-deepmind/alphageometry2](https://github.com/google-deepmind/alphageometry2)（Apache-2.0系の要監査）

- IMO-AG-50（2000-2024のIMO幾何50問）で **42/50 = 84%**。金メダル平均（40.9）を超えた
- **AG2 DDAR 単独は16/50**。LMの付加で42/50へ。LMの役割は**補助構成の提案と探索の多様化**のみ
- 言語拡張: 物体の運動、角度・比・距離の**線形方程式**、非構成的問題。IMO被覆率 66%→88%
- SKEST（Shared Knowledge Ensemble of Search Trees）: 複数探索木の知識共有
- 重要な比較: TongGeometry DD（Zhang et al. 2024）は純記号的DDで18/30（AG1 DDAR単独14/30を上回る）。Wu+AG1 DDAR（Sinha et al. 2024）は27/30
- LM検証器の否定: 「LLMをverifierに使う流儀は前提が怪しい。IMO幾何は多数の精密な代数操作を一貫して行う必要があり、LLMは基本演算でさえ信頼できない」と明記。**検証はシンボリックエンジンのみ**

この表の意味: 「最小限のLLM（補助構成提案のみ）＋シンボリック検証」は、AG2の実測（16/50→42/50）と古典の演繹DB（固定点閉包）の両方が支える構成である。MORTRAは外部LLMを実行経路に置かないが、もしLLMを使うなら役割は「型付き補助構成の提案」に限定し、検証は常にシンボリックエンジンが行う。この構造はGelernter(1959)の「syntax computer が semantic の推測を検証する」と同一である。

## 今回実装した共通核

### 1. 実行可能な多項式幾何

`worker/backend/wu_geometry_kernel.py`

入力述語を座標多項式へ変換し、既知の非零線分で平面の並進・回転自由度を固定する。辞書的Gröbner基底から観測変数だけを含む消去イデアルを取り出し、正の実数解が一意のときだけ回答する。

修正前は存在しない`SymPy.eliminate`を呼んでおり、この経路は実行不能だった。修正後は、ラベルと数値を変えた直角三角形、長方形、正方形で同じ射列が再利用される。

これはWuの完全な特性列・擬除算実装ではない。現在の正確な名称は「多項式イデアル消去backend」である。

### 2. 双方向定理ハイパーグラフ

`worker/backend/geometry_proof_hypergraph.py`

- 対象: 型付き述語`Atom`
- 射: 複数前提から結論への`Theorem`
- 後向き処理: goalから関係する定理だけを切り出すrelevance slice
- 前向き処理: 与件からの閉包
- 探索順位: goalとの対象共有を最大化し、新規対象導入を最小化
- 出力: 使用前提まで遡れるproof DAG

ラベルを全交換した問題と、同じ定理を任意深さに反復する問題で同じschemaが発火する。無関係な与件は最終proof sliceへ入らない。

## 数値結果

MathVision 3,040問の固定評価で、多項式消去経路だけを再実行した。

| 版 | 正答 | 誤答 | 棄却 | exact rate | answered precision |
|---|---:|---:|---:|---:|---:|
| 変更前 | 290 | 0 | 2,750 | 9.5395% | 100% |
| 消去backend修正後 | 291 | 0 | 2,749 | 9.5724% | 100% |

改善は1問であり、AlphaGeometry相当とは言えない。これが示すのは、壊れていたbackendが1つ閉じたことだけである。大きな差は、図から述語を得るformalization、196規模の定理bank、補助構成探索、立体CDLに残る。

また、既存`mathvision_symbolic.py`には68個の狭いscalar solver dispatchが残る。最終20版の291正答はそれらを含むため、「普遍核だけのスコア」ではない。今回追加しかけた同種の個別分岐`general_composition_kernel`は監査で除外したが、既存分もstructure-only ablationで分離し、段階的に共通射へ置換する必要がある。

## 解法暗記を防ぐ受理条件

1. 問題ID、正解、固有の数値をsolverへ渡さない。
2. 問題文の固有フレーズを条件にした答え関数を禁止する。
3. ラベル置換、数値変更、与件順序変更で同じcertificateを要求する。
4. 異なる構造は混同せず、閉包できなければ棄却する。
5. proof DAGの各辺を独立再生できることを要求する。
6. frozen splitは最終評価以外で内容を閲覧しない。

## 未完了部分と実装順

1. FormalGeo規模へ定理bankを拡張し、各定理を型検査・反例検査する。
2. DD/ARと多項式消去を、同じproof DAGのbackend辺として統合する。
3. 補助点・補助線を型付き構成項として列挙し、deep/broad frontierを実装する。
4. 点・直線・平面・多面体の立体CDLと射影/断面操作を追加する。
5. 自然文・TeX・図の三経路を、同じ対象同一性へgroundする。
6. MathVision、FormalGeo7K、IMO-AG、SolidFGeo系で個別対策なしのablationを行う。

「6論文を読んだ」ことと「6システムを完全再現した」ことは分ける。現時点で一次資料と公開コードの監査は完了したが、完全再現は未完了である。MORTRAへ入れるべき共通機構は上記の順に明確化した。
