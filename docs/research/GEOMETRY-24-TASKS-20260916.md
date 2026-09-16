# Frozen autonomous geometry evaluation: 24 tasks

## Preregistered comparison

Repository: `corcondor/mortra`.
Branch: `codex/geometry-failure-location-20260915`.
Solver baseline: `f4334cead7ca669f044bf6d2c3143fae735cee79`.
No solver, parser, proof kernel, candidate policy, or learned library is changed
for this evaluation. The generic cohort-freezing utility only gains an option
to retain prior task inputs verbatim; it does not run the solver.

The first eight tasks exactly match `configs/theory-geometry-cohort.json`.
The next sixteen are source-ranked eligible task IDs absent from that prefix.
Selection is fixed before their results are inspected. These are new tasks for
this experiment, not a claim that no earlier project work ever saw them.
All supplied source auxiliary clauses are removed. No answers, intermediate
points, or desired proof procedures are supplied to the normal entry.

Source: Newclid commit `ac6550732a950564cf7614d605b5bf1eadd29701`,
`newclid/problems_datasets/jgex_ag_231.txt`.
LF bytes SHA256: `fc13f63c37d0e11d44e704e64074d60bbf7eae42f182ad2fd25aef4718d9ed91`.
The same text with CRLF has the prior recorded digest
`c661c8333f977cefd5415a0bba57a377635d70aba927c525c3341b71a144f546`.
The parser's normalization can swap equivalent equality sides and thus change
statement-based ranking. Retained tasks are checked against parsed source
semantics, then preserved byte-for-byte as JSON task objects.
Preliminary source/order checks were not solver runs and remain under reports.

```sh
PYTHONHASHSEED=0 python scripts/freeze_geometry_cohort.py \
  --dataset reports/source-newclid-ac655073/jgex_ag_231.txt \
  --output configs/theory-geometry-cohort-24-20260916.json \
  --count 24 --retain configs/theory-geometry-cohort.json
```

Frozen tasks digest: `8cad08f72303144d825902f791c207972ab153fadb908c13b7fba94105cff491`.
The runtime plan is `configs/theory-geometry-autonomous-solve-24-20260916.json`.
Its search settings and per-task limits are identical to the previous eight-task
plan: seed 917401, 256 construction attempts, depth 5, 256 proof-planner
applications, five seconds per proof attempt and 90 seconds per task.
The workflow-level ceiling is 60 minutes to accommodate the larger task count
and any automatic post-success stability checks; it does not increase any
problem's search budget.

```sh
PYTHONHASHSEED=0 python scripts/verify_theory_geometry.py \
  --plan configs/theory-geometry-autonomous-solve-24-20260916.json \
  --output reports/semantic-feedback-normal
```

The existing runner launches each task through `run_theory_formation.py`.
Accepted proofs require a fresh-process replay. Failure and timeout traces
remain in the artifact. The run must not be edited or supplemented after launch.
Results will separately report the retained eight, the additional sixteen,
proof/verification outcomes, procedure choices, and costs. There is no training
or acquired-library comparison in this evaluation.

## Fresh 24-task results

Actions run: https://github.com/corcondor/mortra/actions/runs/35059517991

Tested commit: `6df235b353153913bc50390ae6d628a267318aff`.
Artifact: https://github.com/corcondor/mortra/actions/runs/35059517991/artifacts/10431809829
Artifact digest: `sha256:468982721efd3c694d4ff1e233da11616e82095d490f0fae88c2d9afa2b932c0`.

Fresh tests: 279 passed and 1 skipped in the semantic suite, 10 passed in the
bridge subset, and 64 passed in the exact-kernel suite (353 passed total).
The solver proved 17/24 tasks, with independent replay passing for all 17.
The retained prefix remained 7/8; the additional tasks yielded 10/16.
Seven tasks reached the 90-second task limit. No false proof was detected.
All successful proofs used the original state, without auxiliary constructions
or an acquired library. This is not evidence of acquired-library improvement.
The runner's `minimum_scientific_success=false` refers to its stronger auxiliary
feedback criterion, not to failure of these 17 proof replays.

Task subprocess time totaled 765.583798 seconds. The traces contain 884 completed
proof attempts, 329 construction attempts started and 18 constructions executed.
The seven unresolved tasks are the original one-based positions 3, 9, 15, 17,
22, 23 and 24. Task 15 includes coefficient-domain conversion errors; task 22
has 17 individual five-second proof timeouts. Longer time alone is not assumed
to repair the conversion errors.

## Preregistered time-extension retry

At the user's request, retry every unresolved task, in its original order.
The new plan is `configs/theory-geometry-autonomous-solve-extended-20260916.json`.
All seven task objects are preserved exactly from the frozen cohort. This is
a retry of previously observed tasks, not a new held-out evaluation.

Only the task timeout (90 to 300 seconds) and individual proof timeout (5 to
30 seconds) change. Solver source, seed, depth, candidate budgets, worker reuse,
and algebraic limits remain fixed. These two time changes are evaluated together;
the experiment does not identify their separate causal effects.
No target lemma, auxiliary point, answer, or desired procedure is supplied.
The existing workflow and its 60-minute outer ceiling are reused.

```sh
PYTHONHASHSEED=0 python scripts/verify_theory_geometry.py \
  --plan configs/theory-geometry-autonomous-solve-extended-20260916.json \
  --output reports/semantic-feedback-normal
```

The retry will preserve successes, timeouts, errors and replay results separately,
and compare each task with run 35059517991. No code will be edited during the run.
