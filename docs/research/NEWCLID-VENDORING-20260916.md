# Unmodified Newclid vendoring

## Frozen change and comparison

Starting MORTRA commit: `734ed88b8a939ecc44c7708fe54babce05439383`.
Branch: `codex/geometry-failure-location-20260915`.
Newclid revision remains `ac6550732a950564cf7614d605b5bf1eadd29701`.

The complete upstream `newclid/` subproject is copied to `vendor/newclid/`.
No upstream source, license, notice, test or dataset is edited. Every Git blob
hash and size is recorded in `vendor/newclid.upstream.json`. The import source
changes from a remote Git install to a local package install. Both geometry
requirements files refer to the same local snapshot. Scientific dependencies
remain unchanged; this is not removal of external mathematical infrastructure.

The MORTRA solver, parser adapter, planner, proof machinery, candidate order,
24-task configuration and its budgets are unchanged. No acquired library,
answers, auxiliary constructions or online hints are added. Upstream fixtures
are used only for upstream regression tests, not the MORTRA normal run.

Before switching, the upstream-installed environment passed 18 selected local
regression tests (81 deselected) in 9.01 seconds. The command was:

```sh
python -B -m pytest -q tests/test_geometry_closure_contract.py tests/test_geometry_source_scope.py worker/backend/test_jgex_exact_constraint_bridge.py -k 'test_fair_planner or test_forward_backward or test_budget_stop or two_locus or line_circle or affine_compression or altered_congruence or point_renaming or segment' -p no:cacheprovider --junitxml=reports/newclid-upstream-before-tests.xml
```

After development, use a separate local environment to avoid modifying the
existing upstream-installed environment. For this controlled local comparison,
the new environment may share its scientific dependencies but must install its
own Newclid from `vendor/newclid`. Shared dependencies must be disclosed. GitHub
Actions installs all declared requirements in a fresh hosted job.

The frozen evaluation is two independent dispatches of the existing workflow,
both selecting `configs/theory-geometry-autonomous-solve-24-20260916.json` at
the same implementation commit. Each runs the existing MORTRA suite, the bridge
subset, upstream parser/state regressions, the same 24 tasks and independent
replay of accepted proofs. Package-content and actual-installation-origin audits
run before and after, with results and versions included in the artifact.

The previous 17/24 result is historical comparison data, not a fresh run.
Compare per-task status, accepted proof and replay, rather than just the count.
Time-limited search can vary with machine load; report any differences instead
of silently changing budgets or task selection. No speedup or capability gain
is presumed from vendoring.

## Reproduction

Run from the repository root:

```sh
python -m pip install -r requirements-geometry-contracts.txt
python scripts/verify_vendored_newclid.py --output reports/newclid-before.json
PYTHONHASHSEED=0 python scripts/verify_theory_geometry.py --plan configs/theory-geometry-autonomous-solve-24-20260916.json --output reports/newclid-cohort
python scripts/verify_vendored_newclid.py --output reports/newclid-after.json
```

`verify_vendored_newclid.py` requires this checkout's local-install provenance;
a matching old Git-installed package is rejected. It checks all imported package
sources as well as the full vendored snapshot. Windows CRLF-only differences in
an installed package are explicitly reported, not treated as source changes.
The vendored snapshot itself must match upstream bytes exactly.

Results will be appended only after fresh test and normal-run completion.
