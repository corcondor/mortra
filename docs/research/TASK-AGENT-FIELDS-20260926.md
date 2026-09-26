# The Task Agent: reproduced, placed, and tested where it was not yet

Branch: `research/task-agent-product-field-20260926`, from
`research/frontier-v13-structural-edit-prediction-20260925` (`4847a28`).
Protocol commit for the exact slip evaluation: `2db6426`.

Sources: the sandbox run recorded in `MORTRA_task_agent_verification.md` and
`MORTRA_fixed_field_theory_record_20260926.md` (2026-09-26), its script and CSVs,
and the package `experiments/task_agent/{core,exploration,online}.py` with
`tests/test_task_agent.py`, all delivered by the user. The package is committed
unmodified; its nine tests pass.

## 1. The sandbox run is the repository's run

The sandbox script imported `/mnt/data/mortra_integrated_response_system.py`,
which is not in the repository. `experiments/task_agent/checkpoint.py` is that
script with one change: the learner and world are the canonical, hash-checked
`experiments.game_frontier_v1.frozen.StructuralLearner` and
`experiments.game_frontier_v11.world.Engine`, reached through an adapter that
renames methods and nothing else. The eight worlds are the genomes in artifact
`theory-registration` (workflow run 36120576842), now committed with their
source SHA-256s in `experiments/task_agent/data/archived_worlds.json`.

| compared with the registered run | rows | differences |
|---|---|---|
| learned-state counts, 8 worlds × 4 budgets | 32 | **0** |
| task specifications | 368 | **0** |
| result rows (success, steps, shortest, product size) | 4416 | **0** |

From the committed files alone, with no downloaded data. The registered numbers
are therefore the repository's numbers, and everything below builds on them.

## 2. What the linear field is

`psi = (I - qK)^-1 g`, with `K` the uniform choice over **tried** actions and each
action's modal successor, is the successor representation (Dayan 1993) of that
policy on the **learned modal product chain**, applied to the acceptance
indicator. Acceptance is absorbing in these automata and no product state lacks
a tried action, so `psi(z) = E[q^tau] / (1 - q)`: the first-exit value of that
policy. It is equally the desirability of a linearly-solvable MDP (Todorov) with
that policy as passive dynamics and step cost `ln(1/q)`. Ascending it greedily is
one step of policy improvement from that policy. The SEQ / ALL / BRANCH memories
are finite automata over predicates on the entered state, so the product is the
reward-machine (Toro Icarte et al. 2018) or co-safe-LTL product construction.
Source superposition is the linearity of these values in the reward. The online
agent's plan-or-explore loop has the structure of E3 (Kearns and Singh 2002).

None of this is new, and none of it is lessened by being known. What is specific
to this work is empirical: the numbers on these worlds.

## 3. Deterministic worlds: the linear field against the shortest path

On exactly the same product graphs, with the same tie-break and executor, at
budget 8192:

| task type | tasks | linear field reaches the learned-graph shortest path | steps linear / shortest |
|---|---|---|---|
| sequence | 96 | 87 | 1908 / 1896 |
| all_of | 96 | 81 | 1553 / 1519 |
| condition_then | 96 | 92 | 956 / 952 |
| branch | 80 | 75 | 755 / 738 |
| **all** | **368** | **335** | **5172 / 5105 (+1.3%)** |

The worst case is branch 2303/41: 17 steps where 11 suffice. The reference
`optimal_product` ascends `q^d` on the same graph and is 368/368 **by
construction**: that number checks the implementation, it is not a result.
"Shortest" means shortest in the learned modal graph; on 18 of 368 tasks the
true world has a shorter route than the learned graph contains (9 in world 2101,
6 in 2808, 3 in 2202: actions the learner never tried).

Why the linear field loses, in four states. From `s`, action 0 goes to `a`, which
is one step from the goal but whose other three actions lead nowhere; action 1
goes to `b`, two clean steps from it. `psi(a) = 0.9·10/4 = 2.25`,
`psi(b) = 0.81·10 = 8.1`, so the delivered planner goes via `b` and takes three
steps where two exist. Averaging over dead-end actions dilutes a short route
(`test_the_delivered_planner_takes_the_three_step_route_when_two_steps_exist`).

Cost: on the 368 final-budget graphs (912 product states on average) the `q^d`
field takes 0.39 ms against 2.19 ms for the sparse LU of the linear one, and the
whole method runs in 11.3 s against 13.8 s.

## 4. Exploration: the online agent from a partial model

The delivered `OnlineTaskAgent`, from the budget-512 model, 4096 environment
steps per episode, on the 368 registered tasks; 211 of them have no accepting
path in the starting product graph and need exploration. A confirmation on 368
new tasks (generator seeds +200000, zero overlap), with its outcome and decision
rule fixed before it ran, gives 205 such tasks. Medians count every failure at
4096.

| policy | success ≤512 | ≤1024 | ≤4096 | median steps | confirmation ≤512 | ≤4096 | median |
|---|---|---|---|---|---|---|---|
| structural (canonical) | 142 | 169 | 202 | 363 | 139 | 194 | 324 |
| task_conditioned, as delivered | 91 | 146 | **211** | 684 | 99 | **205** | 592 |
| frontier, as delivered | 87 | 133 | 211 | 781 | — | — | — |
| frontier_t0 | 160 | 196 | 211 | 296 | 166 | 205 | 221 |
| task_conditioned_t0 | **168** | 196 | 211 | **250** | 165 | 205 | 220 |
| uncertainty | 64 | 91 | 163 | 1396 | — | — | — |

`_t0` is the same class with `low_count_threshold=0`, added after a three-task
pilot and labelled post hoc in the first run; the confirmation fixed it in
advance. Paired over the tasks that needed exploration (fewer steps, a failure
costing more than any success):

| comparison | first run | confirmation |
|---|---|---|
| task_conditioned vs structural | 49 / 118, p = 1e-7 | 40 / 117, p = 6e-10 |
| task_conditioned_t0 vs structural | 117 / 38 (post hoc) | **91 / 50, p = 0.0007** |
| task_conditioned_t0 vs frontier_t0 | 77 / 48, p = 0.012 (post hoc) | **61 / 63, p = 0.93** |

Three mechanisms explain the table, and each is checked.

**The task-conditioned policy's field term cannot fire.** `OnlineTaskAgent`
asks the policy for an action only when `choose_action` returns `None`, which
happens exactly when the product graph from the current state contains no
accepting state, which is exactly when `psi` is `None`. The field term of the
relevance is therefore always zero (7,260 of 7,260 instrumented calls in the
review), and what remains is "go to a known state that satisfies the next
predicate", with ties broken by lowest state id where frontier uses discovery
order. `alpha_unknownness` and `beta_task` never change an action. So this data
cannot say whether field-guided exploration helps: that was never tested.

**The threshold, not the task, is what separates the policies.** With
`low_count_threshold=1` a state whose actions were each tried once still counts
as frontier; at the budget-512 start that is every known state in four worlds,
so the policies stop navigating and re-probe known deterministic transitions by
lowest action index (on 2505 tasks 3 and 4, about 32% of their steps try a new
pair, against 96% for the same policy at threshold 0 and 99% for the canonical
explorer). At threshold 0 both frontier-type
policies beat the canonical explorer, and the confirmation confirms it for the
task-conditioned one (91/50). But against the same navigation with no task term
the confirmation finds nothing (61/63): the first run's 77/48 did not replicate.

**Completeness is the delivered policy's one clear property.** As delivered it is
slower than the canonical explorer on most tasks, but it finished every task in
both runs. The canonical explorer failed 9 and 11, all in world 2202, the world
whose 8192-step map is incomplete. The comparison with it flips sign by world
(2202: 23/2 for task_conditioned; 2505: 0/37).

No policy had a head start from the snapshot: its `node_visits` equals the
summed `action_visits` everywhere, and the frontier policies that inherit the
same bookkeeping beat the policy that produced it.

## 5. Slip: which field when actions misfire, evaluated exactly

A first Monte-Carlo run (`run_noisy.py`, kept in `reports/task-agent-noisy/`)
could not rank the fields: one episode per task, tasks and models regenerated at
every slip level, a frozen executor that failed on the first unseen state, and
success differences that were coverage artefacts (paired p ≥ 0.06). It is
superseded, not reported.

Every planner here is a stationary policy on (world state, memory), so its
performance under a known slip kernel is computed exactly by propagating the
state distribution for 512 steps. Tasks are the 368 registered ones at every
level; slip replaces the intended action with a uniform one with probability `e`.
Protocol in `exact_slip.py`, committed before the run. Mean expected steps
(failure charged at 512):

**With a correct model** of the deterministic dynamics:

| slip | linear field | shortest path | optimum under the true kernel |
|---|---|---|---|
| 0 | 13.94 | **13.78** | 13.78 |
| 0.05 | **14.84** | 14.91 | 14.67 |
| 0.10 | **15.86** | 16.23 | 15.68 |
| 0.20 | **18.33** | 19.57 | 18.14 |

The linear field is within 0.2 steps of the optimum at every slip level and
beats the shortest path on 314, 319 and 336 of 368 tasks at 0.05, 0.10 and 0.20;
without slip the shortest path is optimal and the linear field loses 0.16. The
"many ways through" argument for the linear field is right, **for this noise
model** -- and uniform-action slip is exactly the averaging the uniform-policy
field performs, so it is the most favourable case. Non-uniform noise is untested.

**With the learned model** trained in the slipping world, the model dominates:

| slip | linear | shortest | linear, empirical | certainty-equivalent | optimum |
|---|---|---|---|---|---|
| 0.05 | 24.84 | 25.90 | 24.42 | 24.77 | 14.67 |
| 0.10 | 49.43 | 50.92 | 44.98 | 44.30 | 15.68 |
| 0.20 | 64.80 | 61.58 | 63.32 | 59.72 | 18.14 |

Success falls to 0.92–0.93 at slip 0.2 and cost is three times the optimum,
almost entirely from model error: states the learner never saw, and actions
whose single training sample slipped. Per task the linear fields win more
often; on mean cost the certainty-equivalent planner is lowest at 0.10 and
0.20; success rates differ by at most 0.01 between planners at any level. No
field fixes a wrong model. The remedy is to keep learning during execution -- the
online agent in the slipping world -- which this run does not test.

## 6. What is not claimed

* The linear field, the product construction and the plan-or-explore loop are
  known constructions (section 2). Nothing here is a new kind of planner.
* `optimal_product` 368/368 is by construction.
* "Shortest" and "optimal" are relative to the learned graph unless marked as
  the true kernel.
* The online data does not test field-guided exploration: the field term never
  fired. It tests frontier navigation, a threshold, and a tie-break.
* The threshold-0 result is confirmed against the canonical explorer only; its
  attribution to task conditioning is refuted by the confirmation.
* The exact slip result is for uniform-action slip on a frozen model.
* Tasks are sampled from the canonical explorer's own 8192-step map, so success
  rates are upper bounds where that map is incomplete.

## 7. Next

1. **Exploration that the field can actually steer**: optimism in the product
   (untried `(u, a)` leading to a virtual node that carries source mass, R-max /
   UCRL style) or a progress-shaped source, measured against `frontier_t0`.
2. **The online agent under slip**, so model errors become cost, not failure.
3. **Non-uniform noise**, where the uniform-policy field has no built-in
   advantage.
4. **Sequential tasks on one model**, where task-agnostic exploration should
   pay for itself.
5. Then the delivered document's own next step: the automaton from a less
   privileged description.

## 8. Running it

```
python -m pytest tests/test_task_agent.py tests/test_task_agent_fields.py
python -m experiments.task_agent.run_checkpoint --output reports/task-agent-checkpoint
python -m experiments.task_agent.run_online --output reports/task-agent-online
python -m experiments.task_agent.run_online --output reports/task-agent-online-confirmation \
    --task-seed-offset 200000 --policies structural task_conditioned frontier_t0 task_conditioned_t0
python -m experiments.task_agent.summarize_online reports/task-agent-online
python -m experiments.task_agent.run_exact_slip --output reports/task-agent-exact-slip
python -m experiments.task_agent.run_exact_slip --summarise reports/task-agent-exact-slip
```
