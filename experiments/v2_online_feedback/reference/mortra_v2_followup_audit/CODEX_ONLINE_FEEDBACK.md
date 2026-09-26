# Codex: V2の自己プレイ経験を学習へ接続する小規模実験

## 目的と範囲
新しいDesignerを作らない。既存のゲーム・批評・mutation・採否は保存する。
未攻略時の自己プレイが経験を増やし、同じゲームの次の試行に使えるかを検証する。
既報の8 seedのうち79020004の失敗を見て計画した開発実験であり、独立確認実験ではない。
今回の統合結果を成功と読み替えない。virtual-frontierやtargeted designerの優位性は未確認のまま。

## 正本
Repository: corcondor/mortra
実行コードcommit: 5f8b36744a29327928c87d6db888f2f045dbea79
結果commit: 724220d29f02b79633b0ba43adf57242ad922cb9
Run: 36273640831

使用するコード:
- scripts/evaluate_autonomous_game_design_loop.py
  MicroGame / StructuralLearner / solve_fixed_field / evaluate_game
  evaluate_random_player / critique_game / apply_targeted_mutation /
  apply_random_mutation / decide_acceptance / run_self_design_loop
- experiments/task_agent/pretraining.py
  TaskBlindSelector / SingletonMemory
- experiments/task_agent/virtual_frontier.py
- experiments/task_agent/core.py
- experiments/task_agent/exploration.py
- experiments/self_design_v2_integration/adapter.py
  既存の読み込み、計測・再生の構造を参照する。

新規branchに追加モジュールとテストを作る。過去コード・結果の上書きは禁止。
旧版V2のStructuralLearnerを別クラスへ交換しない。q=0.90、成功判定、
同点選択、既存field solver、既存未攻略判定は固定する。

## すでに判明した実装箇所
旧evaluate_gameでは2500手の初期探索後にKとpsiを一度計算する。
自己プレイ中にはrecord_transitionも再計画も行わない。
未攻略時のfallbackはコメントに反してuniform randomではなく
best_a = trial % NUM_ACTIONS である。
この既存動作は対照群にそのまま保存する。

## 第0段階: 保存記録の照合
まずseed79020004、method=virtual_frontier、targeted/evaluation_000の
保存game・learner・actionsを読み込み、今回添付のfailure_audit.jsonと照合。
元artifact ID10917048485、SHA256:
326e01cad269f56b84b6e075a47c3e87fa3068cac73a27f2d9098b5aa9ba30ea
期待値: 448 states、1716 state-action pairs、記録2500遷移、既知goal state0。
自己プレイ50試行は全て各試行内100回の一定action、計5000操作、成功0。
自己プレイには保存learnerに無い新しいtransition tripleが0。
ランダム評価の成功5/50をoracleや教師データとして流用しない。

## 第1段階: 同一ゲーム上のフィードバック比較
8 seed79020000..79020007全ての、virtual-frontier初期探索のevaluation_000を使う。
各seedの同一2500手学習snapshotから3つの独立コピーを開始。
Designerによるゲーム変更はまだ実行しない。元の初期ゲームとgoalを全条件固定する。

A frozen:
  旧自己プレイのfield/readout/fallbackをそのまま使う。追加観測を学習に戻さない。
B record-and-replan:
  Aと同じreadout/fallback。ただし実行した(state,action,next_state)を
  V2のget_or_add_id/record_transitionで追加し、構造や観測済goal集合が
  変わったら既存build_k_support/solve_fixed_fieldで再計算する。
C record-replan-and-explore:
  Bに加え、旧fallback条件(best_a is None or best_val <= 1e-8)に入った時だけ、
  TaskBlindSelector('virtual_frontier').choose(learner,current_state)を呼ぶ。
  selectorはcurrent_stateをlearnerへ登録した後に呼ぶ。
  それ以外のreadout、同点処理、q、source=1は変更しない。

Bは「記録と再計画だけ」の効果、C-Bは「未攻略時の探索接続」の追加効果を測る。
Cの改善が出ても単一変更や表現発明と呼ばない。

全条件で追加経験予算は最大5000ではなく正確に5000環境action。
各rolloutは成功または100操作でリセットし、予算まで続ける。
最終rolloutは残予算で打ち切る。リセットを実行action由来の遷移として記録しない。
リセット数、総実行action、計算時間を別記する。
checkpointは追加0,1000,5000操作。途中結果による予算変更は禁止。

checkpointではlearnerの独立コピーを凍結し、旧V2と同じreadout/fallback/
trial番号依存の同点処理で50試行を実行。評価中は更新しない。
元evaluate_gameをそのまま呼んで2500手再学習することは避け、
そのプレイ部分を学習済snapshot入力として取り出す最小adapterを作る。
追加0の評価は保存trial0行動・全試行成否と一致することをテスト。
評価コピー、追加学習、ランダム評価はメモリを共有しない。
評価時の行動列や成功ラベルは追加学習へ戻さない。
50試行を50独立ゲームと扱わず、独立単位は8 seedとする。

初期学習はtask-blindのまま。タスク遂行中のpublic is_goalの利用は許す。
oracle距離、完全グラフ、隠れsuccessor、baseline成功軌跡の流用は禁止。
source predictor、NN、新しいcritique/fitness/representationは追加しない。

## テスト
- Aは元の自己プレイの行動・成否を再現する。
- B/Cのupdateは実行された遷移のみ。resetの架空edgeが無い。
- BはAのfallbackを保存し、Cだけがその箇所で既存selectorを呼ぶ。
- 初期goal未発見から、経験でgoalが見つかった場合にfieldを再計算する。
- ゲーム・goal・規則のhashは全条件一致し全期間不変。
- 凍結評価前後でlearner fingerprintが一致する。
- 学習試行成功と、凍結後の評価成功を別に記録する。
- 最終actionで成功したケースの計数は一度だけ。
- 既存テストに加えて上記を検査。丸め差と離散行動差を区別して保存。

## 保存と判断
各seed×条件×checkpointで成功、費用、実環境操作数、known states/pairs、
初回goal観測時刻、fallback回数、selector呼出回数、CPU、全行動・状態を保存。
失敗seedだけでなく全8 seedを報告。比較はC-B、B-A、C-Aをすべて掲載。

同一ゲームの能力が改善したことを確認してから、同じ変更を
run_self_design_loop内のevaluate_gameへの別版adapterとして接続する。
既存のcritique、mutation、採否を変えない。ゲーム版が変わった時はlearnerを
新規化し、旧版で得た遷移を無検証で持ち越さない。
元のループとの大規模比較や3D化は、この開発結果を見る前に自動開始しない。

失敗した場合も「構造学習全体が不可能」と一般化しない。
今回はこの固定snapshot・経験予算・既存readoutでの結果だけを報告する。
