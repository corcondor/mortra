# Protocols for the second round (2026-09-26)

Each protocol below is committed before the run it governs. Git history is the
record of what was fixed when.

## P1. Exploration a field can steer (optimism)

Written after a pilot of the optimistic policies on nine tasks of the ORIGINAL
task set (worlds 2505 and 2202), before any episode on the task set below.

- Worlds: the eight archived worlds. Start: the canonical budget-512 snapshot,
  private copy per episode. Budget: 4096 environment steps. Planner:
  `CachingSparsePlanner` (the delivered ProductPlanner with a sparse solve).
- Tasks: a FRESH set, the registered generators with seeds 520000+seed and
  620000+seed (task-seed offset 400000), never used before.
- Policies: `structural`, `frontier_t0`, `task_conditioned_t0` (baselines);
  `optimistic_linear_rmax`, `optimistic_linear_shaped`, `optimistic_linear_goal`,
  `optimistic_optimal_rmax`, `optimistic_optimal_goal` (`optimism.py`).
- Unit of analysis: tasks with no accepting path in the budget-512 product graph.
- Primary hypothesis H1: `optimistic_optimal_goal` finishes in fewer steps than
  `frontier_t0` on more tasks than the reverse, two-sided sign test p < 0.05,
  AND it has more successes within 512 steps. Both or H1 is not supported.
- Secondary, reported whatever they show: every optimistic variant against
  `frontier_t0` and against `structural`; linear against optimal field at equal
  shaping; `rmax` against `goal` at equal field.
- Medians count failures at 4096. Per-world breakdowns are reported.

## P2. The online agent in slipping worlds

Written after checking, on world 2101, that `FieldPlanner` with reuse reproduces
the delivered sparse planner on 46/46 episodes at slip 0 and timing 20 episodes
at slip 0.2; no other P2 episode run.

- Worlds and tasks: the eight archived worlds, the 368 registered tasks.
- Noise: uniform slip e in {0.05, 0.10, 0.20}. Start: the canonical learner
  trained 8192 steps in the e-slipping world with seed `train:{world}:{e}` --
  the very model the exact evaluation froze -- copied per episode into a
  `VersionedLearner`.
- Agent: the delivered `OnlineTaskAgent`, exploration `FrontierFieldPolicy`
  with `low_count_threshold=0`, planner `FieldPlanner` linear or shortest.
  Budget 2048 steps. Three execution seeds per (world, task, e), shared by both
  planners (common random numbers by step index).
- Comparison: for each task, the online agent's mean cost over its three
  episodes, with every episode not finished within 512 steps charged 512,
  against the frozen model's exact expected cost for the same planner, task and
  e (`reports/task-agent-exact-slip`).
- Primary hypothesis H2: at e = 0.20, for BOTH planners, the online cost is
  lower than the frozen cost on more tasks than the reverse, sign test
  p < 0.05. Secondary: the same at 0.05 and 0.10; online linear against online
  shortest; success within 512 and within 2048.

## P3. Noise that is not uniform

Written after a regression check that the generalised evaluator reproduces the
committed uniform results exactly; no drift run before this.

- Worlds, tasks, planners, evaluation: exactly as `exact_slip.py`.
- Noise: `drift_state` (the slipped action is a fixed action per state, from a
  hash of the state) and `drift_global` (it is always action 0), at e in
  {0.05, 0.10, 0.20, 0.40}; and uniform at 0.40, which was not run before.
  Learned models are trained under the same noise.
- The prediction, from the kernel decomposition: under uniform slip the
  closed-loop kernel of any policy is (1-e) P_pi + e U, and U is exactly the
  kernel whose potential the linear oracle field computes; under drift it is
  (1-e) P_pi + e D and U does not appear. So the linear field's advantage
  should shrink under drift.
- Primary hypothesis H3, at e = 0.20: (a) the mean cost gap of `linear_oracle`
  to `ssp_optimal` is larger under `drift_state` than under uniform (0.192),
  and (b) `linear_oracle` is cheaper than `shortest_oracle` on fewer tasks
  under `drift_state` than under uniform (336 of 368). Both, or H3 is not
  supported. The same two statements for `drift_global` are secondary.

## P4. One model carried across a sequence of tasks

Written after a smoke run of four tasks per policy on world 2303 that printed
only row counts and seconds; no P1 result had been read.

- Worlds and tasks: the eight archived worlds, the 46 registered tasks of each.
  Start: the canonical budget-512 snapshot, copied ONCE per sequence into a
  `VersionedLearner` and carried through all 46 tasks. Budget per task 4096.
- Orders: three random orders per world (`order:{seed}:{k}`), shared by every
  policy. Unit of analysis: a (world, order) sequence, 24 units.
- Policies: `structural`, `frontier_t0`, `optimistic_optimal_goal` (task-directed
  exploration), `optimistic_linear_rmax` (broad exploration: every untried
  action worth the same). Planner `FieldPlanner("linear")`, which reproduces the
  delivered planner's decisions.
- Primary hypothesis H4: with d = steps(`optimistic_optimal_goal`) -
  steps(`optimistic_linear_rmax`) summed over positions 0-22 (d1) and 23-45
  (d2), d2 > d1 -- the directed policy's advantage shrinks, or its disadvantage
  grows, once the model is richer -- on more units than the reverse, sign test
  p < 0.05. This is the claim that broad exploration pays for itself later.
- Secondary: total steps per policy and every pairwise sign test; the number of
  tasks that needed exploration, by position; failures.

## P5. The task automaton inferred from labelled traces

Written after unit tests on a ten-cell line world and a timing smoke on three
tasks of world 2303 that read only the seconds column.

- Worlds and tasks: the eight archived worlds, the 368 registered tasks.
  Planning and judging on the TRUE world graph (`exact_slip.true_graph`), so
  only the automaton is being inferred.
- Per task: the states from which the true task can be accomplished, less the
  registered start, shuffled by `pool:{seed}:{task}`; the first 16 are held-out
  starts, the next 16 demonstration starts. Per demonstration start: one
  shortest accomplishing run (ties at random), one 32-step random walk, and the
  shortest world route to where the demonstration ended; each labelled at every
  step by the true automaton, cut at the first acceptance. N in {2, 4, 8, 16};
  the sample for N is the first N rows of the sample for 16.
- Conditions: `goal_set` (no automaton: accomplished means reaching a state
  some demonstration ended in); `rpni_random` (N demonstrations + N random
  walks); `rpni_near_miss` (+ N direct routes); `rpni_counterexample`
  (`rpni_random`'s sample, then up to 16 rounds at the registered start of
  infer - plan - execute - add the observed trace).
- Measures: held-out success (the true automaton accepts along the executed
  plan), held-out optimal (in the true shortest number of steps), equivalence
  on this world from the registered and held-out starts, inferred memory size,
  rounds.
- The prediction, from how RPNI generalises and not from any P5 result: random
  walks almost never visit a task's landmark states, so nothing in
  `rpni_random`'s sample contradicts "reach where the demonstrations ended",
  and RPNI's greedy merging returns that; a direct route to the same end state
  that does not accomplish the task is exactly the contradiction.
- Primary hypothesis H5, at N = 16, on the 272 `sequence`, `all_of` and `branch`
  tasks: (a) `rpni_random`'s held-out success rate is within 0.05 of
  `goal_set`'s; and (b) `rpni_near_miss` and `rpni_counterexample` each have
  more held-out successes than `goal_set` on more tasks than the reverse, sign
  test p < 0.05. Both (a) and (b), or H5 is not supported.
- Secondary: everything at N = 2, 4, 8; the 96 `condition_then` tasks
  separately, where equivalence is predicted to be rare (states that satisfy
  "variable j = v" but never appeared are not transitions of the inferred
  automaton) while held-out success need not be low (a plan through a seen
  triggering state still accomplishes the task); rounds to success.
