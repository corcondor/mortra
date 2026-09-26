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
