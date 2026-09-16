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
