# Certified Morphism Contraction: mixed effects, scientific FAIL

## Verdict

Exact compilation and actual internal-point hiding passed. The combined
summary/guard/effect-ordering condition improved some unseen searches, with a
positive used-morphism ablation. However, hiding alone increased total search
work, and the combined condition lost a task solved by the primitive baseline.
The precommitted scientific gate is **FAIL**. No task, seed, budget, mechanism,
or gate was revised after observing the fresh evaluation.

The previous four-task negative result remains unchanged at commit
`39ce48368639f3c508bdd611b06339aad893f342`, Actions `34818657880`.
Its config, report, result and comparison file byte hashes still match the
[pre-implementation audit](GEOMETRY-MORPHISM-CONTRACTION-PRIOR-ART-20260914.md).
Those four tasks were used separately for regression, not for the new totals.

## Reproducible evidence

- Repository: `corcondor/mortra`.
- Branch: `codex/geometry-morphism-contraction-20260914`.
- Fixed experiment code: `adf05ea8e3437d254ec89bd9805636b6e39076a1`.
- [Actions run 34826898742](https://github.com/corcondor/mortra/actions/runs/34826898742).
- [Artifact 10341023202](https://github.com/corcondor/mortra/actions/runs/34826898742/artifacts/10341023202).
- [Permanent artifact copy](../../reports/geometry-contraction-actions-34826898742.zip).
- [Machine-readable analysis, per-task costs and paired traces](../../reports/geometry-contraction-actions-34826898742-analysis.json).
- [Exact reproduction commands](../handoff/GEOMETRY-CONTRACTION-REPRODUCE-20260914.md).

Primary results below are newly executed in the clean Actions checkout, not
Windows results or historical logs. Both workflow and target SHA are the exact
code SHA above. The workflow is the existing `worker-ci.yml`, dispatched with
`verification_suite=geometry-contraction` and an exact expected SHA.

Python was 3.12.10 on Linux 6.17.0-1022-azure x86_64, with SymPy 1.14.0,
python-flint 0.9.0, numpy 1.26.4 and pytest 8.4.1. Full dependency versions and
commands are inside the artifact. No new external prover was introduced.

The artifact's top-level q-directed verification is PASS: 351 tests, normal
acquisition, stored reuse and refusal. The contraction tests are 116 passed,
1 skipped in 34.95 seconds. Independent contraction replay passed: one acquired
contract, four source proofs, one summary, 44 submitted proofs out of 60
training/evaluation/ablation rows, and 221 visibility checks. Two separately
submitted historical regression proofs also replayed. There were zero false
submitted proofs. Replay took 11.467 seconds. The Actions job exits 1 because
`--require-scientific-pass` rejects the scientific result, not because a test or
exact replay failed.

## What changed

- `geometry_contraction.py` infers external inputs, boundary/final outputs and
  private locals from DAG references. It reuses certified rational witnesses
  to derive input/output polynomial relations, without general quantifier
  elimination. It preserves the original body and certificate.
- `theory_geometry_contraction.py` connects summaries to the existing typed
  planner. Only public coordinates are executed/exposed. Paid refinement can
  restore hidden points. Certified sufficient guards filter bindings before
  ranking/capping; conservative effect signatures reorder, never exclude,
  families. There are no task/definition-ID branches.
- The existing rational adapter and typed enumerator gained optional hooks and
  cost/event recording. Existing default behavior remains available as the
  exposed comparisons. The normal Theory entry selects the new adapter by mode.
- The fixed cohort generator, boundary/tamper tests, independent replay and
  existing Actions workflow complete the experiment. No selector,
  stratification mechanism or new solver was added.
- A post-run, JSON-only observer derives real dependency depths and paired
  visibility traces. It does not execute searches or modify experiment inputs.

The targeted prior-art audit was written before implementation. Hiding,
summary conditions and hierarchical refinement are established ideas. This is
an integration experiment, not a claim of a novel abstraction algorithm.

## What MORTRA actually acquired

Training solved 12/12 mechanically generated specifications using only midpoint
and perpendicular-foot primitives. Existing anti-unification examined 1,275
subterm pairs and produced one admissible multi-step acquired definition:

```text
Point + midpoint + perpendicular-foot
  -> 12 independently replayed training proofs
  -> H(p,a,b) = midpoint(p, midpoint(a,b))
     ID geom.a0247196c81e93c6fd89, supported by four training proofs
  -> P = true; Q: 4*y_x = 2*p_x+a_x+b_x, 4*y_y = 2*p_y+a_y+b_y
     summary.4b5cd43afbbad19d8f6b
  -> local0 private; local1 public; body retained for paid refinement
  -> later planner calls H on fresh task arguments
```

The compiler derives Q under the original sufficient preconditions through
rational substitution, denominator coverage and the existing triangular
uniqueness certificates. It does not infer universal equality from sample
coordinates. Normal acquisition happened with fixed code, without an injected
definition body or evaluator witness. H happens to equal the previously known
midpoint macro; this is reacquisition, not a new mathematical identity.

Training search cost was 31.631 seconds; its independent replay cost was 2.400
seconds. Acquisition cost was 0.190 seconds, including 0.104 seconds and eight
prover calls to certify H. Summary compilation cost was 0.081 seconds, including
another eight contract-replay calls plus two output-identity checks.
The existing text-compression calculation assigned H **-1,224 bits** of utility;
no positive description-length gain is claimed. The fixed geometry acquisition
policy selects by training support/compression/content hash, not by evaluation.

## Fixed fresh cohort

Seeds 101 and 211 supply 12 training tasks and eight evaluation tasks, disjoint
from one another and from the original four regression specifications. The
solver receives points, polynomial goals and nonzero assumptions, not a witness
program, required macro or witness depth. Every task is primitive-expressible.

Per task: 120 planner states/attempts, 360 primitive-equivalent operations,
120-second soft wall limit, 12 offered candidates per family, 256 examined
input tuples per family, search seed 17, Python hash seed 0. These limits are
identical across conditions. Primitive expression size is not artificially
restricted relative to macro size. Full macro bodies and refinement are charged.

The frozen generator's rejection prose incorrectly says it rejects initial-point
answers; its code does not do so. This was documented before evaluation, and
the cohort was not changed. One task is solved with zero construction steps.
Generation depth is not minimal solution depth or human difficulty.

## Fresh Actions comparison

A is primitive-only; B exposed syntactic macros; C exposed certified morphisms;
D summaries with guard filtering and effect ordering; E summaries without that
filtering/ordering. F removes the most-used H from D, chosen by the fixed rule.
All totals below cover the same eight tasks per condition, including timeouts.

| Condition | Solved | Expansions | Offered construction candidates | Offered refinements | Precondition-filtered bindings | Successful applications | Goal identity calls | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 5/8 | 456 | 527 | 0 | 0 | 212 | 2436 | 172.876 |
| B | 5/8 | 447 | 519 | 0 | 0 | 276 | 3252 | 167.590 |
| C | 5/8 | 447 | 519 | 0 | 0 | 276 | 3264 | 168.482 |
| D | 6/8 | 239 | 272 | 24 | 285 | 214 | 2206 | 150.034 |
| E | 5/8 | 460 | 507 | 44 | 0 | 311 | 3316 | 175.240 |
| F | 6/8 | 333 | 383 | 0 | 1022 | 259 | 3002 | 232.438 |

| Condition | Macro application attempts | Rejected applications | Exposed objects added | Hidden objects | Max / mean points per goal-checked state | Goal-checked states | Runtime contract checks | Primitive-equivalent operations |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| A | 0 | 244 | 212 | 0 | 6 / 5.536 | 220 | 262 | 456 |
| B | 162 | 171 | 406 | 0 | 7 / 5.746 | 283 | 499 | 609 |
| C | 162 | 171 | 406 | 0 | 7 / 5.746 | 284 | 337 | 609 |
| D | 109 | 25 | 214 | 95 | 6 / 4.968 | 222 | 216 | 371 |
| E | 153 | 149 | 311 | 126 | 6 / 5.197 | 319 | 312 | 657 |
| F | 0 | 74 | 259 | 0 | 6 / 5.622 | 267 | 333 | 333 |

All application rejections are logged after an attempt, including duplicate
points; guards are not silently counted as successful executions. In D, 24
refinement alternatives were offered and 23 executed; E executed 44. They cost
46 and 88 actual primitive steps respectively, included in operation charges.

Registration/replay costs remain separate from runtime goal calls:

| Condition | Acquired contract replay calls / seconds | Summary replay calls / seconds | Primitive schema registration calls / seconds | Precondition calls / seconds | Independent submitted-proof replay seconds |
|---|---|---|---|---|---:|
| A | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.656 |
| B | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1.642 |
| C | 64 / 0.670 | 0 / 0 | 0 / 0 | 0 / 0 | 1.250 |
| D | 64 / 0.677 | 80 / 0.649 | 256 / 4.978 | 186 / 5.926 | 2.137 |
| E | 64 / 0.674 | 80 / 0.645 | 256 / 4.881 | 0 / 0 | 1.723 |
| F | 0 / 0 | 0 / 0 | 256 / 5.012 | 612 / 23.833 | 1.635 |

Candidate generation includes precondition time; inclusive application time
includes execution and checking. Do not add overlapping timers. Per-task exact
timings, calls, object counts and proof lengths are in the analysis JSON.

Every condition times out on `fresh-evaluation-211-3`. The planner's final
`states_explored` and `states_retained` are unavailable on that exception.
Their sums over the other seven tasks are respectively A 356/164, B 354/222,
C 354/222, D 189/167, E 365/251, F 288/219. These are **partial sums**, not full
eight-task counts. Attempt counts and emitted events remain available.
The runtime field named expanded proof depth counts DAG nodes; the read-only
analysis separately computes actual longest-path depth. For D on 211-2 there
are three primitive nodes but depth two, and macro dependency depth two.

## Paired state trace and causal ablation

The following paired state example was selected for post-run explanation, not
used to select or tune evaluation tasks. In task 101-2, the same root call
`H(a,a,b)` is executed in B and E. The analysis stores exact event indexes and
state hashes:

```text
B event 12: H(a,a,b) -> expose [v3=midpoint(a,b), v4=H(a,a,b)]
  -> five points -> event 70 offers ten midpoint candidates
E event 13: H(a,a,b) -> expose [v3=H(a,a,b)], retain local0 privately
  -> four points -> event 82 offers six midpoint candidates
```

Thus the private point really leaves later candidate generation. This is not
merely a shorter printed proof. But both searches fail on this task, and E's
extra refinement branches offset savings elsewhere. Hiding alone is not an
aggregate search improvement in this cohort.

The fixed ablation removes `geom.a0247196c81e93c6fd89`, the only H used in D's
final proofs. It is not a wall-time-only comparison:

| Task | B expansions | D expansions | F without H | Interpretation |
|---|---|---|---|---|
| 101-2 | 119, unsolved | 119, unsolved | 45, solved | H consumes budget that primitives can use; A solves in 107 |
| 101-3 | 105, solved | 25, solved | 119, unsolved | Actual used-H causal benefit |
| 211-2 | 119, unsolved | 35, solved | 114, solved | H reduces attempts; removal does not remove expressibility |

On 101-3, D's actual program is `H(a,c,foot(c,a,d))`. On 211-2 it is
`H(foot(c,a,b),a,b)`. Both are composed by the normal planner after acquisition,
then independently expanded and verified. Their parameters were not supplied
as desired answers. On 101-3, E takes 116 expansions and 926 goal calls, versus
B's 105 and 854: hiding/refinement alone is worse there too.

The new combined mechanism has a real narrow positive result, but it cannot be
attributed to state hiding alone. D versus E also changes sufficient-guard
filtering and effect ordering; this experiment does not isolate those two
changes from each other. Removing H recovers 101-2, so D's six solves and F's
six solves are different sets, not interchangeable measures of capability.

## Freeze and limitations

- Overall FAIL has two explicit reasons: D loses A's solve on 101-2, and E has
  neither fewer aggregate expansions nor fewer goal calls than B. Correct
  summaries and positive single-task ablations do not override the gate.
- No exposed-macro solve is lost by hiding in this cohort. Restoration and
  outside-boundary preservation passed targeted artificial tests. This is not
  a proof that bounded planning will preserve every possible solve.
- Only one midpoint macro was acquired in the normal run. General foot and
  boundary cases in unit tests are development tests, not autonomous discoveries.
- The existing sufficient-guard checker is conservative. Filtering preserves
  bindings it can certify, not every mathematically legal binding. Effect shape
  is used only for ordering, not as a completeness theorem.
- Timeouts are machine-dependent. B and C differ in how far they got through
  the final expensive goal check, despite identical candidate sequences.
  The decisive 101-2/101-3/211-2 comparisons are state-budget/success cases,
  not claims drawn only from timeout-induced count reductions.
- No stratification, new selection system, alternate domain or task tuning was
  added after this FAIL. The negative result is retained as requested.

The separate Windows development run also has scientific FAIL, with 120 passed
and one skipped related test (four pre-existing uncommitted adapter tests are
not in the clean commit). Its recorded source seal differs from clean Actions
in four pre-existing files: `theory_geometry.py`, `freeze_geometry_cohort.py`,
`verify_theory_geometry.py`, `requirements-geometry.txt`. It is not substituted
for clean evidence. Local comparison expansions are A 434, B 426, C 425,
D 236, E 445, F 327; solve sets match Actions. All original unrelated edits
were preserved and excluded from the implementation commit.

Permanent snapshots are lossless repacks, not the original GitHub ZIP container.
Every extracted member was byte-compared: 130 Cloud files and 79 local files.

| Snapshot | SHA256 |
|---|---|
| reports/geometry-contraction-actions-34826898742.zip | 6a871cf0a30b1f2ea90ae2dcd43b4508ce82abf5cdb83d9686fe78e5d41b70e1 |
| reports/geometry-contraction-local-v1.zip | 09636b6522287244ee486b1207dc87cfe50c7bad7c0868a2a72e8f90ee0c358b |

The analysis JSON also records individual source-file byte hashes. Reporting
files and the JSON-only observer were added after the frozen experiment; they
do not alter its code, inputs, acquisitions, choices or scientific verdict.
