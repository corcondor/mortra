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
