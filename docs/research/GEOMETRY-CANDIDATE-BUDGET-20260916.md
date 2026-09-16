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

## Fresh Actions results

Run: https://github.com/corcondor/mortra/actions/runs/35084901403

Tested SHA: `f0f0807b1d7c6c1376fc7bfabff8adb460c997a8`.
Artifact: https://github.com/corcondor/mortra/actions/runs/35084901403/artifacts/10443791636
The downloaded archive SHA256 is
`ca14e7d1b8ff6306a94c252551fc4dcad832bddfc0df977d240f97e61429bf2c`.
The executed plan equals the committed plan. Source hashes stayed unchanged.
The artifact records 279 passed / 1 skipped in the main test subset and
10 passed / 76 deselected in the bridge subset.

All three tasks stopped at `application_budget`, with no additional proof.
The combined previously reported cohort remains 17/24; this retry did not rerun
the other 21 tasks. This is not a fresh 24-task validation.

| Original position | Prior attempts | New attempts | Matching initial attempts | Verified constructions | Proof attempts | Wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 256 | 1024 | 256 | 58 | 1440 | 449.567 |
| 17 | 256 | 1024 | 256 | 66 | 1600 | 1181.292 |
| 23 | 256 | 1024 | 256 | 62 | 1800 | 1184.239 |

Prefix equality compares each parent-state key and candidate key, in order.
Every task has 1024 distinct such pairs and 768 attempts beyond the old prefix.
All reached depth 3, below the permitted depth 5. All 38 construction families
were attempted: 36 families 27 times and two families 26 times, per task.
There were no completed proof-attempt timeouts or logged RuntimeError refusals
in these three tasks. Total task subprocess time was 2815.098 seconds.

Construction certification refused 966, 958 and 962 attempts respectively.
Reasons include unproved nonzero conditions, non-affine or algebraic extensions,
changes to normalization scope, false guards and unsupported `nperp` requirements.
These counts are not evidence that every refused construction is mathematically
invalid: some are outside the implemented certificate fragment. Detailed counts,
frontier data and costs are in the companion JSON. Increasing the budget alone
did not solve these tasks; this run does not isolate a single sufficient cause.

The fixed DSL generated and tried the candidates, without runtime hints or LLM
calls. No acquired library was supplied, and `acquisition_performed=false`.
This tests autonomous search within the supplied language, not online learning.

## Local storage recovery

C: had zero free bytes while retrieving the artifact. No files were deleted.
Partial NTFS compression of the existing environment at
`C:/Users/81808/.openclaw/workspace/mortra-geometry-semantic-feedback-20260915/.venv`
was followed by 3,837,550,592 observed free bytes. Compression was intentionally
stopped after sufficient space was available; full compression is not claimed.
Python, SymPy, NumPy and Newclid imports succeeded afterwards. The command below
passed 13 tests in 5.78 seconds locally; these are separate from the Actions tests.

```powershell
& 'C:/Users/81808/.openclaw/workspace/mortra-geometry-semantic-feedback-20260915/.venv/Scripts/python.exe' -B -m pytest -q tests/test_geometry_closure_contract.py tests/test_geometry_source_scope.py -p no:cacheprovider
```

The artifact download was resumed, completed and checked against the published
digest. ZIP entries were read without expanding a second copy of the large logs.

## Newclid dependency and cost distinction

This run uses MORTRA's exact proof path, not Newclid's deductive engine.
However, removing the package is not currently supported: `GeometryDomain`
uses its JGEX parser, construction definitions and initial diagram builder;
`SymbolicDSLDomain.apply` uses its problem classes and numerical constructor;
the exact constraint bridge uses its parser/definitions; and
`native_rule_theorems` imports its declarative rules. These are supplied knowledge
and infrastructure, not mathematics acquired during this run.

The local Newclid 3.0.1 package plus metadata occupies 1,742,831 logical bytes
(about 1.66 MiB), excluding dependencies and checkout copies. Shared scientific
packages cannot be attributed exclusively to Newclid or safely removed with it.

Across these three tasks, measured numerical construction took 0.101922 seconds
and initial construction took 0.008802 seconds. Exact proof calls took
1803.215047 seconds and construction-extension certification took 968.419998
seconds. Costs are nested and must not be added indiscriminately. Imports, rule
loading and parsing inside certification are not separately isolated by these
timers. The evidence does not identify Newclid as the dominant slowdown.

A semantics-preserving replacement of the remaining input/construction boundary
could retain proof capability, but a complete removal comparison has not been
performed. No unchanged-score or speedup claim is made. Merely uninstalling the
package would currently break runtime imports. Solver code and dependencies were
not changed during this storage recovery and evidence audit.
