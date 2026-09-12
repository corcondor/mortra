# Task-directed closure and certificate-scoped reuse

This is a new implementation/verification record. It does not rewrite the
historical `built / partial / not built` statuses in THEORY.md or NEXT.md.
The normal comparison completed: 19 fresh-process runs, with the source versions
and command plan fixed before launch. Seventeen produced answers and two stopped
as specified below. All performed independent answer/distribution checks agreed.

## Checkout and provenance

- Expected and checked HEAD: `6eedcb7888c3f164933115b94392a557e4b78dca`.
- The existing checkout was on `handoff/mortra-exact-abstraction-20260912`,
  with unrelated working changes. Those changes were not reverted or included.
- Work is isolated at
  `C:/Users/81808/.openclaw/workspace/mortra-codex-private-handoff-20260913`,
  a detached worktree at that exact commit.
- The available repository's origin is the PUBLIC `corcondor/mortra`.
  Access to the requested `corcondor/mortra-codex-private` returned
  `Repository not found`. At the end of the development runs recorded below,
  no public push, private push, or commit had been made.
  This is local development at the matching commit, not a verified private
  remote checkout.

The subsequent commit-packaging step is documented in
[Q-DIRECTED-REPRODUCE-20260913.md](Q-DIRECTED-REPRODUCE-20260913.md).
It includes the exact 351-test command and repository-local copies of the raw
test logs. This does not relabel the historical runs as post-commit checks.

Read in order: AGENTS.md, THEORY.md, MORTRA-20260912.md, NEXT.md, then the
referenced implementation. Handoff performance figures are historical results,
not new measurements.

## Reproduced before modification

The 16 module groups listed in MORTRA-20260912.md passed:
335 tests, 116.821 seconds. Raw log:
`C:/Users/81808/.openclaw/reports/mortra-handoff-baseline-tests-20260913.txt`.

The small normal-entry run used degree 1, one term, certificate depth 3,
probe 4, independent verification at 5, answer at 8, reuse at 9. Its output is
`artifacts/research/q-directed-handoff-20260913/baseline-smoke`.
It offered 12 candidates, rejected 11 by the observable condition, admitted
a four-dimensional space, and selected the existing exact route after paying
19.301998 seconds for acquisition/certification. At length 5, maximum 5,
32 maximizing words and the entire distribution agreed with enumeration.
At length 8: maximum 8, 256 maximizing words, 65,536 total words.
Stored reuse at length 9: maximum 9, 512 maximizing words, 673 expanded nodes,
zero instrumented closure prover calls.
These are fresh baseline checks, not new mathematical discoveries.

## Implemented

### Task-directed construction

`self_directed_search.acquire_task_closure` supplies
`TaskSpec.observable_expression` and any `required_observables` to the EXISTING
`finite_generator_problem_dna.discover_action_observable_basis`.
There is no second closure algorithm, coordinate-specific basis, matrix,
readout or answer in this adapter. The CLI defaults to `q-directed`; the Python
API retains its historical enumeration default for compatibility.

For the supplied evaluations, the prover constructs the smallest common
invariant linear space of polynomial observables containing them. The existing
certificate derives the readout by exact span membership. All four generator
pullbacks are checked as polynomial identities. If the task is not supported
by that representation, the q-directed route uses the existing exact concrete
route; it does not silently waive the failed requirement.

The present fold adapter supports rational coefficients (`QQ`) and its existing
executable fold action. This is not an implementation for arbitrary actions or
coefficient fields. The cap is an explicit refusal, not a truncated certificate.
Zero/missing evaluations currently refuse this acquisition and use the concrete
fallback. A smaller nonlinear or reachable-state-specific representation is
outside the minimality claim.

### Applicable mathematical result

[CLUE, Algorithm 2 and Supplement Proposition I.1](https://arxiv.org/pdf/2004.11961)
were checked, including the minimality proof. The reading covered those sections
and their surrounding context, not the complete paper.

The prerequisite is a finite-dimensional vector space over one field with
linear actions. Here each polynomial pullback preserves the ambient degree,
so bounded-degree monomials form such a finite space over QQ. Repeatedly adjoining
the pullbacks of the current rows terminates when invariant. Every invariant
space containing the starting rows contains every added row by induction.
The ODE Jacobian construction in CLUE is not used.

This construction and the counting theorem are supplied algorithms/theorems.
MORTRA acquires the task-specific space and matrices; it did not invent CLUE.

### Reuse contract

`representation_reuse` matches the executable action, alphabet, coefficient
field, domain, legality contract, goal predicate, counted objects and length
meaning. It checks the stored certificate's scope and binding to the stored
basis/matrices. Every required evaluation must lie in that space; the readout
is derived by exact linear algebra without re-acquiring the space.

Display task names do not authorize execution. Within an all-finite-words
certificate, an integer centre and a verified reachable frame may be used as
a different start. A bounded certificate requires the same start and cannot
answer beyond its checked length. Legacy name-only certificates cannot enter
the new stored-reuse route.

The one-step verification now checks that the verified frame set is closed,
not merely that sampled steps agree. The complete premise is retained when
saving an observation representation. The fold-observable domain previously
dropped parts of that premise; this integration defect was fixed as well.

Source fingerprints bind executable versions; they are not proofs about
arbitrary Python callbacks or maliciously edited ledgers. The existing
`legal_always` assertion remains a supplied task contract. Certificate scope
does not include physical collision avoidance unless that requirement passes
its own check. In particular, centre/frame observations do not preserve the
whole panel history.

### Cost records and run separation

Each trace separates acquisition, certification, answer and reuse. It also
reports independent verification and the remaining comparison/bookkeeping time.
The older `acquisition_cost` aggregate remains for compatibility with selection;
it includes acquisition AND certification and must not be double-counted.
`costs` is the separated comparison record.

Acquisition includes candidate generation and the existing closure prover's
own identity checks. Certification separately measures the kinematics premise
and task sufficiency checks. Closure prover calls and task certifier calls are
different counters. Search-node units are recorded by phase; candidate counts
are not DP state counts. Instrumented primitive counts do not include every
matrix arithmetic operation. Timings include tracing overhead and are single
measurements, not repeated uninstrumented performance rankings.

The normal CLI seals source hashes/inputs before computation, saves completed
task records incrementally, reloads the saved ledger for reuse, and checks
source hashes afterwards. The comparison launcher fixes its entire command
plan before starting and launches only the normal CLI. Hashes detect the
changes they measure; they do not prove an absence of every possible intervention.

## New development verification

After the initial baseline, development tests exposed a missing saved premise
and old fixtures using depth-bounded certificates beyond their range. The
premise was preserved and those fixtures now supply the actual one-step proof.
The guard was not weakened. Failed development log:
`C:/Users/81808/.openclaw/reports/mortra-handoff-development-tests-20260913.txt`.

The subsequent 17 module groups passed: **351 tests, 58.769 seconds**.
Raw log:
`C:/Users/81808/.openclaw/reports/mortra-handoff-development-tests-v2-20260913.txt`.
The added 16 tests include rational non-coordinate evaluations, several required
observables, dimension-cap refusal, collision refusal/fallback, renamed tasks,
changed starts/readouts, mismatched actions/fields/requirements, invalid frames,
bounded scope, old certificates and changed stored matrices. Reuse tests patch
acquisition/system-building/task-certification entry points to raise if called.
These are developer-written tests, not autonomous discoveries.

## What the acquisition means

The acquired basis, action matrices and readout have executable meanings:
encode a state, update its observations by the selected generator, recover the
task's evaluation, and count word multiplicities without restoring the full
state when the certificate permits. Those statements are stored and checked.
This is mathematical representation acquisition, not string packaging.

It is a limited operational notion of understanding. The user still supplies
the task and evaluation, and developers supply general search, algebra and
proof procedures. This experiment does not show autonomous research-theme
selection, invention of new methods, general mathematical understanding, new
pi formulas, or benchmark improvements outside these tasks.

## Reproduce the new normal comparison

```powershell
python scripts/compare_q_directed_routes.py --output artifacts/research/q-directed-handoff-20260913/normal-comparison-new
```

Use a fresh output directory. A/B/C use fresh processes for the same four named
tasks. A is existing exact, B is 144-candidate enumeration, C is direct closure.
D reads C's ledger, with the changed-start task deliberately reading the
original-start ledger. Collision-constrained D is a negative control.
Three long D runs use the normal q-directed route to verify lookup before
acquisition. The named tasks are pre-existing development fixtures, not novel
questions selected by MORTRA.

## New normal-run results

Output directory: `artifacts/research/q-directed-handoff-20260913/normal-comparison-v1`.
`plan.json` contains the fixed commands and source hashes; `results.json` contains
separated metrics for every process. Each subdirectory contains `input-seal.json`,
`result-seal.json`, `traces.json`, `ledger.json` and human-readable logs.
All 19 process exit codes were zero and all 19 result seals reported unchanged
sources. B's collision-constrained task and D's collision-constrained reuse
stopped rather than producing an uncertified answer; a successful process exit
does not turn either stop into a solved task.

### Costs at length 6

All times below are seconds. Acquisition includes candidate generation and the
closure prover; certification is the separate task/premise stage. Answer time
excludes independent verification. Reuse time is store compatibility and readout
checking, not the answer computation. The total is the task wall time including
verification, comparisons and bookkeeping, but not process startup or ledger
I/O in the launcher. The JSON records those process/ledger times separately.

| Arm / task | Acquisition | Certification | Answer | Reuse | Total | Answer nodes |
|---|---:|---:|---:|---:|---:|---:|
| A axis1 | 0 | 0 | 0.205011 | 0 | 0.237297 | 2297 |
| A c1-plus-c2 | 0 | 0 | 0.191669 | 0 | 0.225243 | 2297 |
| A axis1-from-AG | 0 | 0 | 0.198979 | 0 | 0.227919 | 2297 |
| A collision-free | 0 | 0 | 3.928248 | 0 | 4.167579 | 5125 |
| B axis1 | 210.016544 | 13.204264 | 0.228898 | 0 | 225.979553 | 2297 |
| B c1-plus-c2 | 219.314137 | 13.960417 | 0.246228 | 0 | 234.717988 | 2297 |
| B axis1-from-AG | 216.118694 | 14.131094 | 0.220500 | 0 | 232.736047 | 2297 |
| B collision-free, stopped | 202.919748 | 26.342893 | 0 | 0 | 229.628124 | 0 |
| C axis1 | 0.937273 | 0.700175 | 0.212385 | 0.008329 | 2.335129 | 2297 |
| C c1-plus-c2 | 1.276406 | 0.600488 | 0.214529 | 0.011132 | 2.771234 | 2297 |
| C axis1-from-AG | 0.983873 | 0.712490 | 0.214979 | 0.011618 | 2.408879 | 2297 |
| C collision-free, concrete fallback | 0.936990 | 0.783574 | 4.202307 | 0.007622 | 6.208847 | 5125 |
| D axis1 | 0 | 0 | 0.080108 | 0.201265 | 0.340797 | 249 |
| D c1-plus-c2 | 0 | 0 | 0.228160 | 0.091907 | 0.388473 | 717 |
| D axis1-from-AG | 0 | 0 | 0.088605 | 0.218486 | 0.363963 | 249 |
| D collision-free, refused | 0 | 0 | 0 | 0.015224 | 0.015785 | 0 |

B offered 144 candidates and invoked the closure prover 144 times and the task
certifier 144 times per task. C offered one task-directed starting evaluation
and invoked each once, including the rejected collision case. D offered no
candidates and invoked neither. A likewise acquired/certified no representation.

C reduced acquisition time relative to B by 99.554%, 99.418%, 99.545%, and
99.538% respectively. Including the separate certification stage, the reductions
were 99.266%, 99.195%, 99.263%, and 99.250%. These are this run's instrumented
measurements, not guaranteed speedups on arbitrary tasks. All initially solvable
B/C tasks selected the existing concrete answer route after acquisition; the
small workload did not repay acquisition. D reduced answer nodes but its lookup
overhead meant the whole call was not faster than A at this small length.

In the frozen v1 batch, the historical `TIE_BREAK` prose referred to primitive calls, whereas
the implemented `tie_key` and the explicit `tie_break_workload.rule` use wall
time. The table reports the implemented rule; it must not be read as selection
by primitive calls. Likewise, legacy `grammar` settings remained in C's trace but
were not executed: `closure_method` and `candidates_offered` identify its direct
construction from the task. After the batch, this explanation was corrected,
and the direct route now identifies the task as its input source in `grammar`.
Only diagnostic text/metadata changed; the v1 costs are not relabelled as a run
of that later source version. The post-clarification checks have separate files.

### Actual acquired data and its use

Each of the three unconstrained C tasks acquired a four-dimensional space.
For `c1-plus-c2`, the saved basis is:

```text
c1 + c2
F11 + F12 - F31 - F32 + c1 + c2
F11 + F12 + F31 + F32 + c1 + c2
F21 + F22 + F31 + F32 + c1 + c2
```

`c` is the doubled centre and `F` is the frame in the executable fold model.
The first row is the supplied task evaluation, not a discovered question.
The other rows, four action matrices and the readout `[1,0,0,0]` were derived
by the runtime. Their recorded identity licenses their use at any finite word
length in the certified domain. They do not reconstruct the whole object.

For collision legality, C produced the explicit counterexample `AAG` versus
`AAT`: both encode to `[0,-1,-1,0]`, but appending label `T` is legal for the
first and illegal for the second. It refused the reduced representation and
used the concrete state carrying panel history. Its maximum, maximizing-word
count and full distribution agreed with independent enumeration at lengths 3
and 5; at length 5 there were 948 legal words and 32 maximizing words.

Every one of the 17 answer-producing main runs checked lengths 3 and 5 against
independent enumeration. The two stopped runs did not run that answer check.
The negative D control could not reuse the unconstrained certificate for the
collision requirement and did not re-acquire a different representation.

### Longer words and reuse across starts

The three D-long processes used the normal q-directed entry with C's saved
ledger. Each retrieved before acquisition, recorded `acquired_again: false`,
and had zero acquisition cost, zero closure prover calls and zero task certifier
calls. `axis1-from-AG` used the ledger acquired for the ORIGINAL start, not the
separate C run for the AG start. Only its initial observation and subsequent
calculation changed.

| Task | n=12 maximum / maximizing words | n=14 maximum / maximizing words | n=14 nodes |
|---|---:|---:|---:|
| axis1 | 12 / 4096 | 14 / 16384 | 1849 |
| c1-plus-c2 | 23 / 4 | 27 / 4 | 6605 |
| axis1-from-AG | 14 / 4096 | 16 / 16384 | 1849 |

Each length-14 result accounts for 268,435,456 words. These were computed by
certified counting, NOT by enumerating that many words. These concrete values
are not a proof of a closed formula for arbitrary n. The certificate proves
that the represented counting calculation is valid at the requested n.

The n=12 D-long answer times were 0.432468, 1.507888 and 0.434416 seconds;
lookup/readout checks cost 0.212869, 0.094737 and 0.220420 seconds respectively.
All separately performed small-n checks agreed. The source seals remained
unchanged throughout all 19 runs. No candidate, auxiliary observable, lemma or
answer was inserted after a run started.

## Final diagnostic clarification and rechecks

After the frozen comparison, the selection-unit explanation and direct-route
input-source metadata were clarified. The full 351 tests passed again in
54.516 seconds; log:
`C:/Users/81808/.openclaw/reports/mortra-handoff-final-tests-20260913.txt`.

A separate normal invocation, `post-clarification-normal-v2`, began with C's
original `axis1` ledger and the usual four tasks. It reused that representation
for `axis1` and the AG start, acquired the missing `c1-plus-c2` space, and used
the concrete fallback for collision legality. All small-n checks agreed.

The textual renderer was then adjusted to display the STORED certificate scope
during reuse, instead of empty fields for a proof that was not rerun. This did
not change acquisition, certification or answer algorithms. Its related 82 tests
passed in 30.308 seconds; log:
`C:/Users/81808/.openclaw/reports/mortra-handoff-final-display-tests-20260913.txt`.

The final normal-entry run is `final-reuse-display-v3`. It used C's original
ledger for `axis1-from-AG`, offered zero candidates, acquired nothing, checked
lengths 3 and 5 independently, and computed lengths 12 and 14 from the stored
certificate. Length 14 returned maximum 16 and 16,384 maximizing words with
1,849 expanded nodes. The certificate has no finite maximum length in its
declared domain; the JSON `maximum_length: null` means unbounded, not a missing
proof. These later runs have their own seals and are not mixed into v1's cost
comparison. No further mathematical code changes followed that comparison.

## Changed files

- `self_directed_search.py`: direct closure adapter, pre-acquisition reuse,
  scope-aware routing, concrete fallback, separated cost records, truthful
  acquisition/selection/reuse explanations.
- `representation_reuse.py` (new): structural contracts, scope and readout
  compatibility, binding stored certificates to basis/matrices.
- `representation_certificate.py`: rational observation evaluation, explicit
  action/field binding, task-expression consistency and stored scope/readouts.
- `fold_observable_system.py`: verified frame set and its closure check.
- `fold_observable_domain.py`: retain the complete one-step premise in storage.
- `representation_benchmarks.py`: enforce scope before represented counting.
- `representation_ledger.py`: structural execution lookup; legacy name lookup
  remains available only for existing display/policy callers.
- `scripts/run_representation_tasks.py`: normal route/store options, source/input
  seals, task checkpoints, disk reload, result checks and accurate route labels.
- `scripts/run_route.py`: use structurally matched stored certificates.
- `scripts/compare_q_directed_routes.py` (new): the frozen comparison launcher.
- `scripts/test_q_directed_representation.py` (new): 16 new regression tests.
- `scripts/test_quotient_counting.py` and `scripts/test_representation_evaluation.py`:
  give existing long-scope fixtures the actual one-step premise they require.
- This report and the recorded experiment outputs. No historical handoff status
  files were rewritten, and the original dirty working tree was not altered.
