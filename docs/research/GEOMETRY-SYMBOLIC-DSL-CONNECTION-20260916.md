# 記号幾何ソルバーと取得DSLの接続

## 目的と基準点

既存の問題解決能力を捨てず、その操作をMORTRAの通常の候補生成、実行、定義取得、後続利用へ接続する。折りの実験を拡張する作業ではない。折りのソースと過去の記録は削除していない。

- repository: `corcondor/mortra`
- branch: `codex/geometry-failure-location-20260915`
- 開発開始HEAD: `e9a09ba1a8da166ad5995e9aea1514976d1b5252`
- 作業領域: `C:/Users/81808/.openclaw/workspace/mortra-failure-location-20260915`

8月の89/89は `MORTRA-CODEX-FUSED-REMAINING11-CLOSURE-20260828.md` に記録されている。問題別のチャートをCodexが追加した開発上の能力測定であり、当時の自律探索や今回の再検証の実績とは扱わない。

## 実行経路

通常入口は `scripts/run_theory_formation.py`。設定の `domain.mode=symbolic_dsl` で以下を実行する。

1. `geometry_symbolic_dsl.run_symbolic_feedback` が、JGEX形式の仮定と目標から `SymbolicDSLDomain` を作る。初期ライブラリは空であり、期待する取得定義を渡さない。
2. `SymbolicDSLDomain` は既存の `theory_geometry.GeometryDomain` を継承する。JGEXの読み込み、状態、証明条件、目標判定は既存実装を使用する。数値図は候補の図示可能性の検査であり、証明ではない。
3. `search_action_domain` が既存の `runtime_typed_planner.synthesize_typed_plan` を呼ぶ。各状態と各構成族の候補列を交互に進める。継続周期では状態と実行済み候補を保持する。
4. `native_candidates` は既存の `synthesize_backward_obligations`、`stratify_backward_obligations`、`synthesize_contract_candidates` を使用する。優先候補の後に `iter_complete_typed_candidates` を続ける。優先候補の件数制限を、候補全体の除外条件にはしない。
5. 取得射は `GeometryLibrary.archive` から読み、同じ構成族の辞書へ追加する。呼び出しの引数は通常の候補生成器が選ぶ。依存定義は既存の `library_compression` により展開する。
6. `compile_call` は局所変数の衝突を避け、同じ部分式を共有し、既存のJGEX構成列へ変換する。`certify_extension` は元の仮定を勝手に強めないことを検査する。`certify_compilation` はDSLとJGEXの座標が記号的に一致することを検査する。
7. `GeometryDomain.certify` は `geometry_proof_dsl.search_exact_proof` を通して既存の厳密な証明器を呼ぶ。明示的座標、関係式による座標、局所消去、目標部分への制限、アフィン補題、構造補題の設定を、既存の型付き探索で組み合わせる。
8. 成功した構成の項と証拠を `histories` に保存する。既存の `theory_geometry_feedback.acquire` が共通構造を抽出し、実際の使用箇所と定義費用を測り、`certify_definition`、`GeometryLibrary.register` を通して保存する。
9. 次周期は同じ状態群に対して更新されたライブラリを読む。後付けの補助点・定義・解答は渡さない。

証明手続きDSLの中間ノードは「処理方法の指定」であり、独立に計算済みの多項式系ではない。実計算は `certify` が既存の `lower_jgex_to_exact_obligation` を実行した時点で起こる。手続きの選択と、数学的な中間表現の自律取得は別である。

## 接続で修正した不備

### 証明範囲の引き継ぎ

元の三角形の正規化で既に宣言された非零条件を、補助構成の検証器が読んでいなかった。分母由来の条件に加え、元の `normalization_assumptions` に明示された多項式の非零条件を使用する。新しい非零条件を仮定する変更ではない。

### 点の引数化

共通部分の抽出では、両方の実行に同じ点名が出現するとその名前が定義に残る。汎用定義の検証はこれを正しく拒否していた。`close_point_parameters` は残ったPoint変数を引数へ変換する。同じ点の複数出現には同じ引数を使い、既存の引数と定義参照は保持する。これは一般化候補の生成であり、証明の代わりではない。元の呼び出しとの往復検査と一般的な構成証明を引き続き行う。

### 既存点を返す手続き

Point型の手続きは、必ず新しい別の点を返すとは限らない。数値図形の構成器はその場合を拒否する。`alias_existing_points` は省略前の構成全体の合法性を証明した後で、記号座標の恒等式により既存点を再利用する。数値的な近さで点を同一視しない。省略前の証明、実際の構成、別々の費用を保存する。恒等的な呼び出しの成功を、新しい幾何状態への到達とは数えない。

## 保証範囲と未接続部分

- 既存の38構成族を登録している。ただし、登録は実行可能性の証明ではない。自由点、代数的な枝、未対応の構成名は、現在の有理的な保守拡張検証で拒否され得る。拒否理由は全件記録する。外心の `circumcenter` と既存DSLの `circle` は同じ既存バックエンド操作であり、その既知の別名対応をDSLへの入力時に正規化する。
- 定義取得で扱うのは既存の有理的Point構成の範囲である。部分式の合成は任意の宣言実座標と証明された適用条件に対して検証する。有限個の数値図での一致を一般定理にしない。
- 過去の問題別チャート集合、すべての履歴上の証明操作、自然言語の意味解析まで共通DSLへ接続済みとは主張しない。今回の証明手続きの選択は既存の汎用的な厳密ブリッジへの接続である。
- 小規模設定は `closure_steps=0`。述語規則の提案と後向き条件生成は呼ばれるが、新しい中間述語の証明を繰り返す設定ではない。
- 折りの3次元姿勢を、この2次元Point状態がそのまま内包するとは主張しない。数学的な共通性と、実装上の型・状態の同一性は区別する。
- 評価2課題は開発上の回帰確認である。初期DSLでも解けるので、正答数が維持されても能力拡張の証拠ではない。

## 保存済みの途中結果

すべて今回のローカル実行であり、過去のWindowsログの転載ではない。各ディレクトリにコード内容のハッシュ一覧、入力、実行環境、候補・拒否・証明の記録がある。未コミット開発中の実行なので、HEADだけでなく `input.json` の `source_seal` を参照する。

| 実行 | 結果 | 判定 |
| --- | --- | --- |
| `reports/symbolic-dsl-normal-01` | 履歴18件、定義0件 | 初期の接続不備を含む |
| `reports/symbolic-dsl-normal-02` | 履歴35件、定義0件。独立再生35/35 | 引数化で停止 |
| `reports/symbolic-dsl-normal-03` | 履歴35件、適格候補7件、定義0件 | 異なる2課題での支持が不足 |
| `reports/symbolic-dsl-integration-01` | 履歴121件、定義2件。取得射9試行、成功履歴0件。独立再生121/121 | 数値構成器が同一点の呼び出しを拒否 |
| `reports/symbolic-dsl-integration-02` | 履歴223件、定義2件。取得射18試行、成功履歴18件。独立再生223/223 | 18件すべて既存点を返す呼び出し。能力改善ではない |

`integration-02` と同じコード内容・入力は、commit `c8810babd2f1755ae9f49e5966682cddcd150927` の [Actions 35051030925](https://github.com/corcondor/mortra/actions/runs/35051030925) でも再現した。関連テスト244成功・1スキップ、別の厳密カーネル検査64成功。ソースのハッシュ一覧、取得定義のIDと本体、223履歴、取得射18成功がローカルと一致した。数値比較専用の外部Yuclidテスト1件は意図的なスキップである。

この段階では外心の24実行が学習対象外となっていた。前述の既知の別名対応の修正後は、新しいコード版で再実行する。共有runの成功結果を修正後の結果に転用しない。

短い設定は2周期、各周期・各課題96試行。長い設定は同じ課題と採用条件で4周期、各周期・各課題192試行。取得が出るように特定の定義を追加したり、2課題の支持条件や正の圧縮利益という採用条件を緩めたりしていない。

## 再現手順

依存定義は `requirements-geometry-contracts.txt`。既存のGitHub Actions `Verify paper-guided geometry portfolio` に設定選択と独立再生を追加した。新しい重複ワークフローは作成していない。

```sh
python -m pip install -r requirements-geometry-contracts.txt
PYTHONHASHSEED=0 python scripts/run_theory_formation.py --config configs/theory-geometry-symbolic-dsl-integration.json --output reports/fresh-symbolic-dsl
python scripts/verify_geometry_symbolic_dsl.py --run reports/fresh-symbolic-dsl
python -m pytest -q tests/test_geometry_symbolic_dsl.py tests/test_geometry_complete_enumeration.py tests/test_geometry_selection.py math_os_prototype/test_runtime_typed_planner.py tests/test_geometry_semantic_feedback.py tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py scripts/test_library_compression.py worker/backend/test_typed_geometry_stalk.py
```

PowerShellでは起動前に `$env:PYTHONHASHSEED='0'` を設定する。

費用は、候補展開、展開前の基本操作換算、実際の数値構成、点の同一性検査、保守拡張の証明、定義の取得・認証、独立再生を区別する。`closure_seconds` と `certification_seconds` は包含する処理があるため、各欄を無条件に合算しない。

## 最終実行

最終固定コードでの結果とActionsの参照は、完走・独立再生を確認してから追記する。
