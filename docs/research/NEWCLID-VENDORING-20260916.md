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

## Fresh results (2026-09-16)

Tested implementation SHA: `0de002f5d4a707d1096dfbda83582c0856635c65`.
The source copy and integration were committed as
`88d217a1c47e8bdb5b53befae671a906a440ef5c`; the next commit only disables
pytest's cache provider for upstream tests. The results below come from fresh
executions, except where explicitly marked historical.

### Copy and installation integrity

The complete Newclid package subproject contains 188 files and 1,248,425 bytes,
including 143 Python package source files, packaging metadata, upstream tests,
datasets, LICENSE and NOTICE.md. It does not include sibling projects such as
Yuclid. The committed Git tree has 188/188 matching upstream blob hashes.
The Python package itself has 144 checked files (143 Python files and py.typed).

Both hosted jobs passed the full snapshot and installed-package checks before
and after execution. Both actually imported the package installed from their
own checkout's vendor/newclid. Both checked 188 snapshot files and 144 installed
files with no byte differences or line-ending differences. Their manifests and
installed dependency lists remained unchanged during execution.

The old Git-installed environment was also checked: its 143 Python source files
differed only in Windows line endings. The default local-origin gate correctly
refused that environment. This refusal checks that merely having an old
matching Newclid installed cannot falsely pass the new provenance check.

### Local repetitions

Local Python was 3.12.10 on Windows. The original upstream-installed environment
was left intact. A separate environment installed its own Newclid from the
snapshot, while sharing the original environment's scientific dependencies
through a .pth path. These local tests are therefore not fully isolated
dependency-installation tests; the hosted runs below supply that check.

The table lists each invocation, not a sum of distinct test cases.

| Invocation | Passed | Skipped | Deselected | Seconds |
| --- | ---: | ---: | ---: | ---: |
| Upstream-installed bridge/contract subset, before switch | 18 | 0 | 81 | 9.01 |
| Vendored snapshot and installation guards | 7 | 0 | 0 | 0.31 |
| Same bridge/contract subset, after switch | 18 | 0 | 81 | 9.69 |
| Upstream problem/build/permutation tests, after switch | 237 | 5 | 0 | 17.31 |
| Repeated vendor/closure/source-scope tests | 20 | 0 | 0 | 3.48 |

The local pip dependency check reported no broken requirements.
The upstream test selection is three files, not the entire upstream test suite.
Five upstream skips are marked expected construction failures by upstream;
the separate hosted MORTRA skip is an optional Yuclid comparison test.

### Two independent hosted runs

Both jobs installed the declared requirements in fresh Ubuntu-hosted Python
3.12.14 environments. Both selected the same unchanged 24-task configuration,
seed 917401, 90 seconds per task, depth 5, 257 states, 256 proof DSL candidates,
and 5 seconds per proof attempt. The exact plan and task order match the
historical comparison run. Both use only the initial library.

| Test group | Run 35102035517 | Run 35102040309 |
| --- | --- | --- |
| MORTRA library/contract/solver regressions | 286 passed, 1 skipped | 286 passed, 1 skipped |
| Selected unchanged upstream tests | 237 passed, 5 skipped | 237 passed, 5 skipped |
| Source-to-exact-state bridge subset | 10 passed, 76 deselected | 10 passed, 76 deselected |
| Exact proof/search gates | 64 passed | 64 passed |
| Total executed pass results per run | 597 | 597 |

There were no test failures in either hosted run. These are repeated results
for the same test selections, not 1,194 distinct cases.

| Normal cohort | Historical 35059517991 | Fresh 35102035517 | Fresh 35102040309 |
| --- | ---: | ---: | ---: |
| Proved tasks / 24 | 17 | 17 | 17 |
| Timed-out tasks / 24 | 7 | 7 | 7 |
| Accepted proofs replayed successfully | 17 | 17 | 17 |
| Accepted proof programs identical to historical | Reference | 17/17 | 17/17 |
| Sum of per-task subprocess wall time, seconds | 765.584 | 730.929 | 797.772 |

For both fresh runs, every task's proved/timeout status matches the historical
run. All 17 accepted proof-program records, including certificate hashes,
match exactly. The seven unresolved tasks remain unresolved. Timed-out searches
do not have a completed result or proof replay; null fields in the companion
JSON are not zero measurements or successful checks.

The fresh runs have different timings and different timeout-bounded search
traces. The same package source and solver code do not imply identical work
under a wall-time budget. This comparison supports unchanged outcomes for this
cohort; it does not establish a speedup or equivalence for every possible task.
The historical run is not a newly executed unvendored 24-task control.

The normal-run verification's minimum_scientific_success remains false in both
runs: no accepted solution required a new auxiliary construction or learned
definition. That research criterion is distinct from successful vendoring.
All completed results report no acquisition, no external deduction, and no LLM
calls. Vendoring supplies existing infrastructure; it is not MORTRA learning
Newclid or independently inventing its mathematics.

### Records and exact reproduction

The existing workflow is Verify paper-guided geometry portfolio. The exact
commands and console outputs are in its job logs. The main and bridge test
commands are unchanged except for adding the seven vendor tests. Upstream
tests use:

```sh
python -m pytest -q --import-mode=importlib -p no:cacheprovider vendor/newclid/tests/test_problem.py vendor/newclid/tests/test_jgex_builds.py vendor/newclid/tests/test_permutation_generator.py --junitxml=reports/newclid-upstream-tests.xml
```

The original .pytest_cache behavior would add files inside the immutable
snapshot. The two initial runs 35101868135 and 35101872464 at 88d217a were
cancelled before the normal cohort, not counted as successful normal runs.
The one-line correction was committed before starting either successful run.
No inputs, source code or hints were changed during those successful runs.
An earlier local development guard also caught CRLF conversion while exporting
the source; the export was redone with original bytes before the source commit.

- [First completed run](https://github.com/corcondor/mortra/actions/runs/35102035517)
- [First artifact](https://github.com/corcondor/mortra/actions/runs/35102035517/artifacts/10448774947)
- [Second completed run](https://github.com/corcondor/mortra/actions/runs/35102040309)
- [Second artifact](https://github.com/corcondor/mortra/actions/runs/35102040309/artifacts/10448799944)
- [Historical comparison](https://github.com/corcondor/mortra/actions/runs/35059517991)

Downloaded ZIP digests match the GitHub-published SHA256 digests:

- Run 35102035517: 1865f8715f905f2f3280c2bb5628155198fa3622fe98c7bcb9193b0b8f39e690
- Run 35102040309: 08731fd1f36aa1bc0592166eb00313bda8cf0535fa2eb91c7682adfbaf8b59aa

Each artifact contains test logs/XML, the exact executed plan, task results,
normal-run verification, proof/search traces, and before/after source-origin
reports including Python and dependency versions. The exact-kernel job's
64-test result is in its workflow log. The companion
NEWCLID-VENDORING-20260916.json records per-task comparisons, versions and
artifact identities. Local test XML files remain under reports/newclid-*.

Only the two geometry requirement files, existing workflow, vendor snapshot
and provenance, .gitattributes, integrity checker/tests, and this report changed.
A diff against 734ed88 confirms no changes in math_os_prototype, worker/backend,
the normal entrypoint/verifier or configs. No main merge or force push occurred.

### Conclusion and limits

Unmodified local Newclid installation is working in repeated Windows checks
and two independent hosted normal runs. The recorded task outcomes and accepted
proofs were preserved. Newclid source installation no longer needs the remote
Git repository. NumPy, SymPy and other package dependencies remain external.
The source copy does not remove their disk footprint or compute cost.
No dependency pruning, solver replacement, new mathematics or autonomous
capability gain is claimed.
