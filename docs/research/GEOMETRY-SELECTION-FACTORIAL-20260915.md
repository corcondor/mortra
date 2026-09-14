# Fixed geometry library x selection: preregistered comparison

## Status before implementation

Baseline: `616bff0d0d11a1a073e7a02099d40cb99b40a4d9`, branch
`codex/geometry-semantic-feedback-20260915`, repository `corcondor/mortra`.
Tracked baseline is clean; historical untracked run files are retained.
The AGENTS-referenced `.agents/skills/mortra-autonomous-research/SKILL.md`
is absent from this checkout. No historical files are restored.

The previous recursive acquisition result is retained. This experiment does
not acquire more definitions, extend the grammar, or teach a search policy.
It reads all 16 certified definitions from run `34889840285`; the old run is
input provenance, NOT evidence that this experiment succeeded.

## Frozen factors and inputs

The executable specification is `configs/theory-geometry-selection-factorial.json`.

| Arm | Library | Order |
|---|---|---|
| A | initial primitives | existing fair search |
| B | initial primitives | contract-guided, fair |
| C | initial primitives + all 16 stored definitions | existing fair search |
| D | initial primitives + all 16 stored definitions | contract-guided, fair |

The primary contrast for solved counts is `(D-C)-(B-A)`, with per-task paired
outcomes retained. Costs are separate measurements, not converted into a scalar
reward. Report each arm and the D-vs-B comparison as well as the interaction.
One fixed run cannot establish a population-level statistical effect.

Candidate membership must be identical for A/B and C/D at the SAME state.
The primitive/library contrast necessarily changes the grammar. Different
search orders also reach different states; full-run candidate sets are not
required to coincide. Reordering occurs AFTER the existing per-family candidate
generation and truncation. No relevance filter, new binding generator, or
solution-derived intermediate goal is permitted.

Use the existing symmetry-aware `align_candidate_atoms` and the existing
general predicate-transition information for ranking only. Conditional
postconditions may propose relevance, never establish a fact. The existing
exact applicability, effect and goal checks remain authoritative. Keep one
offer from each live family per fair round, and the original family order every
fourth round. Include selection, lookahead, matching and replay costs.

Keep the 16 old tasks as development/regression instances. Before any evaluated
search, generate all 16 new instances by the config's fixed seed and coordinate
rule; preserve the goal templates. Save the literal tasks and hashes. Do not
retain only instances a chosen library can solve. This is new-instance transfer
within known goal templates, NOT unseen mathematical-family generalization.
Development tests use artificial small configurations, not this cohort.

## Evidence and diagnosis

For each candidate retain proposed family/binding, source contract, direct
postcondition alignment, original/new position, selection, execution/refusal,
and source state. A conditional match is not proof of applicability. For solved
tasks retain the planner's construction dependency DAG, the final answer term,
primitive replay and exact instance goal certificates. Count ancestor acquired
calls separately from acquired calls remaining in the final answer term.
Neither syntactic appearance nor ancestor membership alone proves necessity.

After evaluation only, run the frozen wider budget on the old tasks unsolved
by A, under A and D. A found replayed path is an existence witness within that
budget. Failure remains unresolved; do not call it an oracle upper bound or a
proof that the fixed library has no useful construction. No diagnostic result
may modify the already frozen selector or evaluation inputs.

Use the normal `run_theory_formation.py` entry and the existing geometry Actions
workflow. Keep archive loading/revalidation, search, ranking, execution,
independent replay and serialization costs distinct. Record code/input hashes,
environment, exact commands, negative results and the workflow run ID. Failed
versions are separate runs, never repaired while running.

## Interpretation rules

- Recursive DSL acquisition is an existing result, not re-proved by this test.
- Improvement in B as well as D may be ordinary primitive selection improvement.
- A positive interaction is evidence for this library/selector/cohort/budget,
  not proof that every acquired definition is useful.
- D-only success plus a replayed acquired-call dependency is stronger evidence;
  no task-specific definition is inserted to obtain it.
- No improvement remains a valid negative result. Do not respond by extending
  the training horizon or tuning on the new evaluation cohort.

## Implementation and development checks

The plan was committed before selector implementation at `b07d911`.

- `theory_geometry_feedback.candidate_rows` exposes the unchanged candidate
  generator; its original caller preserves old ordering.
- `SelectionDomain` instantiates the stored contract's relation templates with
  actual candidate bindings and fresh symbolic output names. Every goal
  conjunct refers to the same prospective output. It reuses
  `typed_candidate_alignment.align_candidate_atoms` and
  `_forward_predicate_distances(euclidean_relation_theorems(), ...)`.
  These are approximate ranking features, not an optimal policy or a proof.
- The shared typed planner optionally sorts one buffered offer from every live
  family in each fair round. No offer is removed. Every fourth round preserves
  the original family order. Lookahead generation and alignment are timed.
- Normal entry adds `domain.mode = selection_factorial`. Acquisition is never
  called. Stored contracts are revalidated once before the comparisons, with
  that shared setup cost recorded separately.
- Each solution records its actual state, construction ancestor calls, and
  the corresponding planner dependency DAG in addition to its answer term
  and independent primitive replay. This does not certify that each ancestor
  was necessary to the solution.

Initial `python -m pytest ...` used the system interpreter and failed collection
because `newclid` was absent (3 collection errors, saved in
`reports/selection-baseline-tests.xml`). No math result was produced. The
checkout's existing isolated environment, installed from the declared geometry
requirements, is used below; no dependency definitions were changed.

```
$env:PYTHONHASHSEED='0'
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_semantic_feedback.py tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py scripts/test_library_compression.py --junitxml=reports/selection-baseline-venv-tests.xml
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_selection.py --junitxml=reports/selection-development-v1.xml
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_selection.py math_os_prototype/test_runtime_typed_planner.py tests/test_geometry_semantic_feedback.py tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py scripts/test_library_compression.py --junitxml=reports/selection-regression-v1.xml
```

Results: baseline 156 passed / 1 skipped in 110.38 s; artificial selection tests
26 passed in 9.04 s; full related regression 184 passed / 1 skipped in 100.73 s.
The skip is the existing optional external-comparison test. The baseline XML
completed before the first solver-source edit. These are local test results,
not a normal-run capability claim.

## Frozen execution command

```
PYTHONHASHSEED=0 python scripts/run_theory_formation.py --config configs/theory-geometry-selection-factorial.json --output reports/semantic-feedback-normal
```

The existing `Verify paper-guided geometry portfolio` Actions workflow now
defaults to this configuration, and keeps both old acquisition configurations
available through `workflow_dispatch`. The exact-kernel job is unchanged.
Push triggers on the touched implementation/test/config paths. No new workflow,
main merge, force push, parser change, or new geometric axiom is included.

## Fresh Actions result: no acquired-library benefit demonstrated

The preregistered comparison completed without source changes or reacquisition.
Both cohorts have A = B = C = D = 8/16 solved. Ranking saves 18 applications
in both B versus A and D versus C. The acquired-library interaction is zero
for solved count and application count. Acquired constructions execute more
often in D, but none occurs in a solved construction dependency path.

This is a negative downstream-capability result, not a reversal of the earlier
recursive-acquisition result. It does not establish that the library is useless
under every binding generator, ordering, task, or budget.

### Source, environment, and fresh verification

- Tested source: `5d9fc5cb6095d24ced7010e300be6077c9f7c26e`.
- Repository: `corcondor/mortra`; branch:
  `codex/geometry-semantic-feedback-20260915`.
- [Actions run 34899138144](https://github.com/corcondor/mortra/actions/runs/34899138144)
  completed successfully. The two jobs were `exact-kernel` and
  `semantic-feedback`. Workflow success means the checks and experiment
  completed; it does not mean that mathematical capability improved.
- Fresh exact-kernel tests: 64 passed in 1.25 s.
- Fresh semantic-feedback and selection tests: 184 passed, 1 skipped,
  0 failures, 0 errors in 53.23 s. The skip is unchanged.
- Python 3.12.14; Linux 6.17.0-1022-azure x86_64; `PYTHONHASHSEED=0`.
  Selected dependency versions: newclid 3.0.1, sympy 1.14.0, numpy 1.26.4,
  pytest 8.4.1. Full versions are in the fresh `environment.json`.
- The normal command is the frozen command above. The exact test commands
  and fresh outputs for both jobs are retained in `workflow-run.log`.
- Fresh normal execution: 590.226425 s, including both cohorts, diagnostics,
  shared library validation, and instrumented output work. Source sealing
  passed, the library remained unchanged, reacquisitions were 0, and policy
  learning was disabled.

### Four-arm results

Each row totals 16 tasks. An application is an actually attempted construction,
including rejected attempts; it is not the number of all proposals generated.
Each task has the same limit of 112 applications and the same other resource
limits. Primitive operations account for expansion of acquired definitions.
Task time includes matching, ranking, exact execution, independent replay,
and event recording; the shared library setup is reported separately below.

| Cohort | Arm | Solved | Applications | Primitive operations | Task time (s) |
|---|---|---:|---:|---:|---:|
| Regression | A | 8/16 | 922 | 922 | 27.373948 |
| Regression | B | 8/16 | 904 | 904 | 26.471855 |
| Regression | C | 8/16 | 922 | 1682 | 40.812662 |
| Regression | D | 8/16 | 904 | 1686 | 44.376238 |
| New coordinates | A | 8/16 | 922 | 922 | 27.295018 |
| New coordinates | B | 8/16 | 904 | 904 | 27.400587 |
| New coordinates | C | 8/16 | 922 | 1682 | 40.534292 |
| New coordinates | D | 8/16 | 904 | 1686 | 45.385147 |

The solve outcomes agree task by task, not merely in their totals. The
new-coordinate cohort preserves known goal templates and is not evidence
about unseen mathematical families.

For `(D-C)-(B-A)`, both cohorts have 0 solves, 0 applications, and +22 primitive
operations. Task-time interactions are +4.465668 s for regression and
+4.745287 s for new coordinates. Positive time means extra cost, not benefit.
No statistical timing claim is made from this single fixed run.

### What ranking improved, and what it did not

On the eight tasks solved by every arm, A and C require applications
`1,3,4,5,1,3,4,5`; B and D require `1,1,1,1,1,1,1,1`.
The 18-application reduction therefore comes entirely from already-solvable
primitive constructions, without a learned construction in the solution.

| Cohort | A solved-task time (s) | B | C | D |
|---|---:|---:|---:|---:|
| Regression, same eight solved tasks | 0.546335 | 0.315134 | 0.754279 | 0.862389 |
| New coordinates, same eight solved tasks | 0.562127 | 0.325174 | 0.777787 | 1.056927 |

In regression, candidate generation on these solved tasks takes 0.008594 s
in C and 0.329996 s in D; in new coordinates it takes 0.010137 s in C and
0.509844 s in D. D buffers and considers acquired-family proposals before
choosing the primitive solution. Thus fewer executions do not by themselves
imply lower total time. This overhead is measured, not omitted.

### Costs and failure-stage evidence

The following are regression totals for all 16 tasks. Predicate prover calls
and applicability prover calls are separately instrumented counters, not an
additive estimate of unique proofs. Timers can be nested: for example,
generation includes its guard work. Do not add every timer as independent cost.
The analogous full new-coordinate measurements are in `verification.json`.

| Arm | Predicate prover calls | Applicability prover calls | Ranking (s) | Execution (s) | Independent replay (s) | Successful acquired executions |
|---|---:|---:|---:|---:|---:|---:|
| A | 19302 | 652 | 0.000688 | 19.085818 | 0.161958 | 0 |
| B | 18256 | 646 | 0.063321 | 18.712714 | 0.154615 | 0 |
| C | 18683 | 1068 | 0.000748 | 29.243635 | 0.344567 | 302 |
| D | 21777 | 1082 | 0.122965 | 31.632526 | 0.411648 | 352 |

Shared source loading takes 0.086995 s. Shared certificate revalidation and
registration takes 13.744790 s (46 certification prover calls and 234
registration prover calls). Recorded JSON output work takes 0.598694 s;
event output takes 4.062050 s already included in the task times. These are
instrumented intervals, not an exhaustive decomposition of the 590.226425 s
normal-entry total.

The trace separates candidate input guards, conditional relation alignment,
proposal order, selection, execution/refusal, and goal checking. C and D do
reach and execute acquired constructions. All solved answer terms contain
0 acquired calls, and all solved construction ancestor paths contain 0 acquired
calls. Merely increasing successful acquired calls from 302 to 352 did not
create a goal witness. Every unsolved primary task exhausted the 112-application
budget. Exact failure/refusal details remain in the event stream.

The two within-library comparisons produced 64 task-pair checks, covering
956 common `(state, family)` pairs, with 0 membership mismatches. Each proposal
batch additionally checks that reordering is a permutation. This is observed
same-state membership plus regression-test coverage, not an enumeration of
every mathematically possible state or binding.

### Wider diagnostic, after evaluation

The eight old unsolved tasks were then searched under A and D with the frozen
448-application limit (four times the main limit). All 16 arm-task executions
used 448 applications and remained unsolved. None reached the primitive-operation
or wall-time limit first; the recorded stop is `window_or_candidate_budget`.
There are 0 replayed existence witnesses.

This bounded diagnostic leaves the question unresolved: a useful fixed-library
path may be absent, or it may remain outside the generated bindings or search
trajectory. The per-family limit of 3 and input-tuple limit of 128 are unchanged.
It is not an oracle upper bound and does not prove the absence of a useful path.
No diagnostic binding, auxiliary construction, or result was fed back into the
selector or evaluation tasks. No further selector tuning was performed.

### Preserved evidence and conclusion

[Fresh Actions artifact](https://github.com/corcondor/mortra/actions/runs/34899138144/artifacts/10369964282):
`semantic-geometry-5d9fc5cb6095d24ced7010e300be6077c9f7c26e-34899138144`.
The uploaded artifact digest is
`fdb7e1e3c283ba0a9094589dc27f6835b07f45f8b4eed907b13c301bcb52d4b5`.

`reports/geometry-selection-factorial-evidence.zip` retains the downloaded
artifact and the complete fresh workflow log. It is a repackaging of this run,
not another experiment. Size: 18,509,144 bytes. SHA-256:
`7059d6fffbee238e789354861857b381170e0438221c576b90f64cd10d2abfa7`.
ZIP integrity was checked after creation. Its normal-output directory includes
the frozen literal tasks, inputs, library provenance and contracts, all arm
results, construction dependency paths, candidate membership checks, detailed
events, diagnostic runs, environment, and machine-readable verification.

The factorial instrumentation and soft contract ordering are implemented and
verified. Ordinary primitive ordering improved on the already-solved tasks.
Additional problem-solving benefit from the frozen acquired library was NOT
demonstrated. Neither deeper acquisition nor a learned selection policy was
implemented in response to this negative result. The earlier recursive DSL
milestone is retained; the usefulness of these 16 constructions for the eight
unresolved goals is still unestablished.
