# Geometry construction budget extension

## Preregistered comparison

Repository: `corcondor/mortra`.
Branch: `codex/geometry-failure-location-20260915`.
Source result: https://github.com/corcondor/mortra/actions/runs/35060935705
Report baseline: `7a918060c68cadc180ecc013e3452837d2161115`.
Unchanged solver source: `f4334cead7ca669f044bf6d2c3143fae735cee79`.

At the user's request, retry all three tasks whose previous status was
`application_budget`, in the original order. Their original cohort positions
are 3, 17 and 23. Selection uses the recorded stopping condition, not a desired
answer or a manually selected promising construction. All task objects are
copied unchanged from the previous plan. The four tasks with other stopping
conditions are not rerun in this comparison; their unresolved status remains.

The construction budget increases from 256 to 1024 attempts. In the existing
normal-entry planner this is `max_states=1025`, including one initial state.
The per-task timeout increases from 300 to 1200 seconds so the old time limit
does not immediately mask the larger construction budget. These resources
change together; separate causal effects are not claimed.

The following remain unchanged: seed 917401, maximum depth 5, candidate order,
proof-planner budget 256, per-proof limit 30 seconds, worker reuse, primitive
operation ceiling 6000, and backend algebraic limits. The symbolic domain uses
`iter_complete_typed_candidates` after a priority prefix. Its overridden candidate
iterator has no per-family slicing; the existing `per_family_limit=8` setting
is not a cap of eight total bindings in that iterator. The finite attempt and
depth budgets still limit actual search, so this is not complete exploration.

No solver, parser, kernel, candidate generator, or selection code is changed.
No source archive is supplied. There is no acquisition or library-improvement
claim. Inputs are formal JGEX tasks, not natural-language comprehension tests.

```sh
PYTHONHASHSEED=0 python scripts/verify_theory_geometry.py \
  --plan configs/theory-geometry-autonomous-solve-1024-20260916.json \
  --output reports/semantic-feedback-normal
```

The existing workflow exposes the new plan and allows 90 minutes only for this
plan; other plans retain their 60-minute ceiling. Code and input are fixed before
dispatch. Any accepted proof requires the existing independent replay. No hints
or auxiliary points will be injected during execution.

Record per task: outcome, completed proof attempts, proof timeouts/errors,
construction attempts and executions, observed depth and refusal reasons, and
subprocess wall time. Compare the first 256 construction attempts to the previous
run and count newly attempted constructions beyond that prefix. Preserve resource
stops without claiming the full search space has been exhausted.
