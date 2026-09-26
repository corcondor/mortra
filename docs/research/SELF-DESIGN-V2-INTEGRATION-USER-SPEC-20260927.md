`corcondor/mortra` で、既存の **Self-Game-Design V2** と、検証済みの **task-blind virtual-frontier exploration** を統合して実験してください。

目的は新しいゲームDesignerをCodexが考案することではありません。

目的は、

**既存MORTRAのゲーム生成・自己プレイ・自己批評・ゲーム改良ループに、直前に検証したvirtual-frontier構造探索をそのまま接続し、MORTRA自身のゲーム制作を実行すること**

です。

---

## 1. 使用する既存コードを固定する

### A. Self-Game-Design V2

以下を正本として使用してください。

Branch:

```text
codex/self-game-design-v2-site-20260923
```

Commit:

```text
156abc04d3ae77f1ac42d151f5d60830585f6ae7
```

必須ファイル:

```text
scripts/evaluate_autonomous_game_design_loop.py
tests/test_self_game_design_v2.py
reports/self_game_design_v2/README.md
```

この実装に既に存在する以下の処理を変更・再設計してはいけません。

```text
MicroGame
StructuralLearner
solve_fixed_field
evaluate_random_player
critique_game
apply_targeted_mutation
apply_random_mutation
decide_acceptance
run_self_design_loop
```

つまり、

```text
ゲーム生成
→ 構造探索
→ fixed-field reasoning
→ MORTRA self-play
→ random baseline
→ self-critique
→ targeted mutation
→ candidate evaluation
→ accept/reject
→ 次iteration
```

という既存ループをそのまま使います。

---

### B. Task-blind Virtual Frontier

以下の検証済み実装を使用してください。

Commit:

```text
dd845c64b3ecfd82a17012b7ca4dabe315597e23
```

再現報告commit:

```text
19f79f3b6973b72cafc6ad311e38ad580f7e1c54
```

必須コード:

```text
experiments/task_agent/pretraining.py
experiments/task_agent/virtual_frontier.py
experiments/task_agent/core.py
experiments/task_agent/exploration.py
```

使用する既存クラスは、

```python
TaskBlindSelector("virtual_frontier")
```

です。

`TaskBlindSelector` が使用する

```python
VirtualFrontierPolicy(
    task_aware=False,
    task_source=False
)
```

を変更してはいけません。

sourceは既存実装どおり全virtual frontierで1です。

task、goal、oracle successor、将来のゲーム情報は探索器へ渡してはいけません。

---

## 2. 統合branchを新しく作る

過去の実験branchを直接変更しないでください。

新しいintegration branchを作ってください。

Self-Game-Design V2の最新コードと、上記task-agent実装を同じcheckoutで利用可能にしてください。

ファイルを都合よく再実装しないでください。

可能な限り上記commitのファイルをそのまま使用してください。

integrationのためのadapterは許可しますが、

- action scoring
- field equation
- q
- virtual frontier定義
- self-critique
- mutation規則
- acceptance規則
- game dynamics

をadapter内で変更してはいけません。

---

## 3. 変更する場所は1か所だけ

Self-Game-Design V2の

```python
evaluate_game(...)
```

内部には現在、

```python
learner = StructuralLearner(num_actions=NUM_ACTIONS)
curr_state = game.get_initial_state()
curr_u = learner.get_or_add_id(curr_state)

for _ in range(explore_steps):
    a = learner.select_action(curr_u)
    next_state = game.step(curr_state, a)
    next_u = learner.get_or_add_id(next_state)
    learner.record_transition(curr_u, a, next_u)
    curr_state = next_state
    curr_u = next_u
```

という初期構造探索があります。

**ここが今回の統合対象です。**

ゲーム生成、self-play、critique、mutation、accept/rejectは変更しません。

探索actionの選択だけを切替可能にしてください。

```text
structural
frontier_t0
virtual_frontier
```

の3条件です。

### structural

現在のコードそのもの:

```python
a = learner.select_action(curr_u)
```

### frontier_t0

検証済み

```python
TaskBlindSelector("frontier_t0")
```

を使ってください。

### virtual_frontier

検証済み

```python
TaskBlindSelector("virtual_frontier")
```

を使ってください。

selectorは1 evaluationにつき1回生成し、2500-step exploration中で使い回してください。

例:

```python
selector = TaskBlindSelector(exploration_method)

for _ in range(explore_steps):
    if exploration_method == "structural":
        a = learner.select_action(curr_u)
    else:
        decision, telemetry = selector.choose(learner, curr_state)
        a = int(decision.action)

    next_state = game.step(curr_state, a)
    next_u = learner.get_or_add_id(next_state)
    learner.record_transition(curr_u, a, next_u)

    curr_state = next_state
    curr_u = next_u
```

これは概念例です。

実際のintegrationでは既存クラスを直接使い、同じ処理を重複実装しないでください。

---

## 4. StructuralLearnerはSelf-Game-Design側を維持する

重要です。

Self-Game-Design V2内の既存

```python
StructuralLearner
```

を、別実装へ勝手に置き換えないでください。

今回検証したいのは、

**同じゲーム学習器に対して、探索action selectorだけを変更した効果**

です。

`TaskBlindSelector` / `VirtualFrontierPolicy` がSelf-Game-Design V2のlearner interfaceで動くことをadapter testで確認してください。

必要なinterfaceは少なくとも、

```text
num_actions
state_to_id
id_to_state
node_visits
action_visits
counts
dest_map
get_or_add_id
record_transition
```

です。

互換性がない場合、アルゴリズムを改造して合わせてはいけません。

不足interfaceと停止位置を報告してください。

---

## 5. Oracleは禁止

今回のゲーム制作実験では、

```text
完全状態グラフ
oracle shortest path
oracle successor
oracle task distance
full transition enumeration
未来状態の直接参照
```

をMORTRAの探索・批評・mutation・acceptanceに与えてはいけません。

既存Self-Game-Design V2は経験したtransitionだけでStructuralLearnerを作るので、その境界を維持してください。

テスト・監査目的でも、oracle情報がpolicy decisionへ流れないことを確認してください。

---

## 6. 最初に原版V2を再現する

統合版を評価する前に、

```text
156abc04...
```

のSelf-Game-Design V2を変更なしで再現してください。

実行:

```bash
python -m pip install -r requirements-game-tests.txt
python -m pytest tests/test_self_game_design_v2.py -q
python scripts/evaluate_autonomous_game_design_loop.py --output <NEW_BASELINE_REPRO>
```

保存済みV2について少なくとも以下を照合してください。

```text
initial game
final targeted game
final random-control game
accepted edit count
iterationごとのaccept/reject
critique sequence
main metrics
trial-0 replay actions/states
```

再現できない場合はintegration実験へ進まず停止してください。

浮動小数差だけの場合は、action・game state・accept/rejectが同一か別に報告してください。

---

## 7. Virtual-frontier側の再現証拠も維持する

以下の既存再現結果を改変しないでください。

```text
864試行の成否・手数一致
72 snapshot一致
training/evaluation action列一致
最大内部float差 3.33e-16
```

今回のintegrationのために、

```text
q
tie break
source
virtual frontier construction
field solver
```

を変更してはいけません。

---

## 8. まず小さい統合smoke testを実行する

いきなり大規模にしないでください。

同一の1つのfresh initial gameを使い、

```text
structural
frontier_t0
virtual_frontier
```

の3条件を比較してください。

全条件で、

```text
同じinitial game seed
同じmutation RNG seed
explore_steps = 2500
self_play_trials = 50
max_play_steps = 100
q = 0.90
```

を使います。

最初は

```text
5 design iterations
```

だけ実行してください。

各条件で保存:

```text
training actions
training observations
known states
known state-action pairs
field telemetry
self-play trajectory
random trajectory
critique
mutation
candidate metrics
accept/reject
current game
```

このsmokeで例外・oracle leakage・不正なinterface変更がないことを確認します。

---

## 9. Smokeが通ったら、完全20-iteration実験

同一のfresh initial seedから、

### Condition S

```text
Self-Game-Design V2
+
structural exploration
```

### Condition F

```text
Self-Game-Design V2
+
frontier_t0 task-blind exploration
```

### Condition V

```text
Self-Game-Design V2
+
virtual-frontier task-blind exploration
```

をそれぞれ20 iterations回してください。

各条件は完全に独立して実行します。

同じ初期ゲームから開始しますが、critiqueが異なれば以後のmutation sequenceが異なるのは正常です。

Codexが条件間のmutationを揃えるために介入してはいけません。

---

## 10. Random-mutation controlも各探索条件で維持する

Self-Game-Design V2には既存の

```python
apply_random_mutation
```

controlがあります。

これを削除しないでください。

したがって各探索方式について、

```text
targeted self-designer
random mutation control
```

を両方実行してください。

これにより、

**探索器が強くなっただけなのか、self-critiqueによる改良が実際に意味を持つのか**

を分けて確認できます。

新しいcontrolは作らないでください。

---

## 11. Fresh seed

過去の

```text
101
201
302
403
504
605
```

はfresh評価には使わないでください。

新規seed集合を実行前に固定して記録してください。

最初の本実験は小さく、

```text
8 fresh creation seeds
```

で十分です。

seedは結果を見る前にmanifestへ保存してください。

失敗したseedを交換してはいけません。

---

## 12. 評価するもの

ゲームの「面白さ」をCodexが主観評価してはいけません。

既存V2 metricsをそのまま使用してください。

最低限:

```text
MORTRA success rate
random success rate
strategic gap
mean actions to goal
state coverage
edge coverage
unique successful trajectories
action entropy
repeated loop rate
dead end rate
unexplored regions
goal reuse
accepted edit count
```

加えて今回の探索統合について:

```text
initial exploration known states
initial exploration known state-action pairs
virtual field solve CPU
total evaluation CPU
training action trace
```

を保存してください。

---

## 13. ゲーム制作主体について

ゲーム設計主体はMORTRAです。

Codexは以下を考案してはいけません。

```text
新しいcritique category
新しいmutation
新しいacceptance rule
新しいgame mechanic
新しいfitness
人手によるcandidate選択
```

Codexは、

```text
コード統合
実行
計測
テスト
ログ保存
再現監査
```

だけを担当します。

---

## 14. 重要な注意

今回の目的は、

```text
virtual_frontierがTask-Agent benchmarkで良かった
```

ことをもう一度確認することではありません。

確認したいのは、

**検証済みのtask-blind structural exploration改善を、実際のMORTRA self-game-design loopの中へ入れたとき、MORTRAが自分でゲームを作る閉ループ全体がどう変わるか**

です。

したがってSelf-Game-Designとpretrainingを別実験として扱わないでください。

同じMORTRAの、

```text
世界を探索して構造を獲得する部分
```

を改善した結果が、

```text
自己プレイ
→ 自己批評
→ ゲーム改良
```

へ伝播するかを見る統合実験です。

---

## 15. 最終報告

以下を必ず出してください。

### 再現

- Self-Game-Design V2 original reproduction
- task-blind exploration implementation hashes
- integration source hashes
- tests

### Smoke

- 3探索条件の実行結果
- oracle leakageなし
- interface compatibility
- action traces

### Fresh experiment

各seed・各条件について:

- initial game
- final game
- 全iteration history
- critiques
- proposed mutations
- accepted/rejected edits
- metrics
- trajectories
- random controls
- CPU / memory

### 比較

```text
structural vs frontier_t0
structural vs virtual_frontier
frontier_t0 vs virtual_frontier
```

についてworld/seed単位で比較してください。

### 失敗

途中で停止した場合は、

**Codexが代替Designerや代替探索器を作らず、その地点で停止し、正確なcall stackと不足interfaceを保存してください。**

結果を見た後にアルゴリズムを変更して再実行してはいけません。