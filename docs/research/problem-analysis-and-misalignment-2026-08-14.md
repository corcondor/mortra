# 問題の所在と、今回の失敗の記録

日付: 2026-08-14

## 1. 標準模型はすでに存在していた

今回のセッションで新規に作る前に、リポジトリには既に次のものがあった。

- **標準模型（kernel-calculus）**: 5項構成子・4構造宣言・3判断・5実行サービスへ分離済み。
  参照: `docs/standard-model-kernel-audit-2026-08-10.md`、`docs/primary-source-mathematical-knowledge-core-2026-08-10.md`
- **談話IR → 型付き問題IR → backend**: `worker/semantics/problem_ir.py`、`worker/semantics/discourse_ir.py`
- **幾何 backend 群**: `worker/backend/wu_geometry_kernel.py`（多項式イデアル消去、dev 52/0/252）、
  `worker/backend/geometry_proof_hypergraph.py`（双方向定理ハイパーグラフ）、
  `worker/backend/geometry_natural_formalizer.py`（日本語→述語）、
  `worker/backend/geometry_diagram_grounder.py`（図→述語）
- **文献統合**: `docs/research/GEOMETRY-SYMBOLIC-LITERATURE-INTEGRATION-2026-08-14.md`
  — AlphaGeometry（Wu+DD/AR）以外に FormalGeo/FGPS、FGeo-Parser/HyperGNet、AutoGPS、
  Hilbert-Geo、Seed-Geometry/Seed-Prover の6系統を一次資料・公開コードまで監査済み。
  共通核5段と「未完了部分と実装順」が明記されている。
- **状態正本と作業規約**: `docs/MORTRA-STATE.md`（唯一の正本）、`AGENTS.md`
  （LLM不使用・誤答ゼロ優先・問題別パッチ禁止・測定の作法）

つまり「標準模型はすでにやってある」「AlphaGeometry以外の論文も統合してある」は事実であり、
私はそれを読む前に新規実装を始めた。

## 2. 何が問題で、なぜうまくいかないのか（既存監査の証拠）

問題は backend の数ではない。既存監査が具体的に示している。

1. **elaboration の失敗が最大のボトルネック** — 公開3,574問中 81.3% が `OpaqueSort`
   に落下し、統一核まで届かない（`docs/standard-model-kernel-audit-2026-08-10.md`）。
2. **統一核が答えていない** — 850正解のうち統一核の寄与は48。残り802は Python 側の
   個別 solver 群（`arithmetic_nl`、`quantity_reasoner`、個別 synthesis）が答えている。
   「共通核の性能」と見せかけられる数字が、個別パッチの寄せ集めだった。
3. **共通核へ統合されていない** — MathVision 3,040問の 206正答に provenance が139種あり、
   うち120種は一度しか発火していない（`MATHVISION-COMMON-KERNEL-PDCA-2026-08-14.md`）。
4. **角度・長さ・面積を別々に処理している** — 棄却2,834件の共起上位は「角度+面積 753」。
   同じ図を測度付きセル複体（C2→C1→C0、境界写像、各次元の測度）として扱う必要がある。
5. **chart の分離ができていない** — 角度系棄却300件中172件は角度問題ではない
   （投影・重なり・立体視など）。全視覚問題を点線 incidence へ押し込む設計が誤り。
6. **誤答ゼロは維持されている** — 全件 206/0（precision 100%）。これは土台として守る。

文献統合文書の「未完了部分と実装順」は、この1〜5の順で実装するよう既に明示していた。

## 3. 今回の失敗：LLMハイブリッド層

今回のセッションで私が作った `angle_chase_text_kernel.py` + `llm_proposer.py` +
`hybrid_prover.py` + `scripts/ab_hybrid.py` は、次の点で根本的に誤りだった。

- **MORTRA の定義に反する**: `AGENTS.md` は「推論経路にLLMを置かない」。
  文献統合文書も「T5、ViT、BLIP、外部API、LLMによる補助構成提案は、
  外部LLM不使用という実験条件と衝突する。有限文法・型付き項合成・列挙探索へ置き換える」
  と明記していた。LLM を提案器に使うのは、この条件の正面違反である。
- **既存資産を無視した**: `wu_geometry_kernel`（角度代数系を含む）、`geometry_diagram_grounder`、
  `geometry_natural_formalizer`、`mathvision_symbolic` を読まず、狭い角度テキストカーネルを新設した。
- **成果が小さい**: dev 304問で +1（問題1113、wrong 0、303 abstain）。既存の
  wu v2（52/0/252）や PDCA（206/0）と比べ、誤りに対する見返りが極端に小さい。
- **LLM 経路の負債**: 非決定的（同一入力で異なる relations）、並列直列化、キャッシュ・
  リトライが必要になり、calibration の A/B は完了できなかった。

## 4. 撤去と今後の方針

LLM ハイブリッド層（上記4ファイルと関連データ）は削除する。単なる削除ではなく、
「定義に反する作業」としてこの文書に記録し、コミットする。

### 方針決定（2026-08-14 追記）: 「最小限のLLM」構成

その後の議論で方向を確定した。**LLMを完全に捨てるのではなく、LLMの役割を
「型付き補助構成の提案」だけに限定する**。これは Gelernter(1959) の
「syntax computer が semantic（図）の推測を検証する」構造の現代版であり、
AlphaGeometry2 の実測（DDAR単独16/50 → LM併用42/50）が支える。

- LLM の出力は**補助構成のみ**（型付き有限文法: 中点・垂線の足・反射・角二等分線・
  交点・円中心など）。関係式・答え・証明を出させない
- 標準模型が提案をインスタンス化し、追加事実を生成 → 演繹閉包エンジンが再探索
- **閉じたときだけ回答**。誤答0は構造的に維持（検証は常にシンボリックエンジン）
- AG2 論文の明言どおり、LLM を検証器に使わない

### 実装順（文献統合文書に従う）

1. **標準模型の固定点閉包** — Chou/Gao/Zhang(2000) の演繹DB方式を実装。
   前向き閉包を固定点まで飽和させ、全導出可能性質を列挙（構造化DBで探索を制御）。
2. **アーベル幾何（全角法）** — 有向角を加法群として扱い、角度追跡を群上の
   線形代数へ（Chou/Gao/Zhang(1996)）。
3. **測度付きセル複体への統合** — 角度・長さ・面積を同一対象IDの C2→C1→C0 と
   境界写像・各次元測度として扱う（共起753の欠落を解消）。
4. **chart の分離** — 計量セル複体 / 半順序・層 / 群作用 / 有限関係モデル /
   状態作用観測の5 chart を分離（角度系172件の誤分類を解消）。
5. **elaboration の改善** — `OpaqueSort` を減らし、自然文・TeX・図の三経路を
   同じ対象同一性へ ground する。
6. **定理bank の拡張** — FormalGeo 196定理規模へ。各定理を型検査・反例検査する。
7. **最小LLMの接続** — 標準模型の固定点が閉じない問題にのみ、型付き補助構成の
   提案を試す。提案は常にシンボリックエンジンが検証する。

すべての作業で「誤答ゼロ」「holdout が dev を下回らない」「問題別パッチ禁止」を守り、
測定は `AGENTS.md` の作法（sha256、環境変数ablation、60s、前後で数字を出す）に従う。
成果はこのリポジトリへ逐次コミットする。
