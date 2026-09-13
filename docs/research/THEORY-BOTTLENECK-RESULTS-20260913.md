# Autonomous Acquisition and the Present Plateau

MORTRA's acquired rules have a causal downstream benefit in the fixed bounded
evaluation. Increasing term size or allowing the last pending fold concept to
expand did NOT produce further held-out capability. These are separate results.
No new mathematical mechanism was added for this study.

## Identity and Reproduction

- Repository: `corcondor/mortra`; branch: `codex/theory-formation-20260913`.
- Frozen mathematical SHA: `14d18a42c3a7c640a7c54c86c36b7238c419df56`.
- Measurement/workflow SHA: `69134b21a9c45346c4139d949e66073fecc21761`.
- [Fresh Actions run34726315203](https://github.com/corcondor/mortra/actions/runs/34726315203): success; job103640931267; attempt1.
- [Artifact10308159689](https://github.com/corcondor/mortra/actions/runs/34726315203/artifacts/10308159689): `q-directed-34726315203-1`,105111291 compressed bytes.
- Artifact digest: `sha256:25cf762fc558c4ca36766c42e7eedf18f0199e57455f686c77b69c207dfc16b8`.
- Local download: `C:/Users/81808/.openclaw/reports/bottleneck-study-20260913/actions-34726315203`.
- Linux6.17.0-1022-azure, x86_64, Python3.12.10; runner image20260907.300.1.
- SymPy1.14.0, NumPy1.26.4, pytest8.4.1, python-flint0.9.0; full versions in `environment.json` and `dependencies.txt`.
- Fresh351 related tests passed,0 failed; q-directed acquisition, stored reuse,
  collision-free refusal and reuse-only refusal passed. Additional theory22,
  measurement9 and observer5 tests passed. These are this Actions run's results.
- All11 normal runs completed; their independent replay totaled94668 checks,
  zero failures. This is a sum across conditions, not94668 distinct discoveries.

Exact dispatch used:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra --ref codex/theory-formation-20260913 -f verification_suite=bottleneck-study -f target_ref=14d18a42c3a7c640a7c54c86c36b7238c419df56 -f expected_sha=14d18a42c3a7c640a7c54c86c36b7238c419df56
```

The workflow checked out the control and mathematical commits separately.
Its study command was `python control/scripts/measure_theory_bottleneck.py
--plan control/configs/theory-bottleneck-study.json --output "$OUT/bottleneck-study"`,
with `MORTRA_BASELINE_ROOT` pointing at the target checkout. The exact expanded
normal-entry commands are in `bottleneck-study/verification.json`; each calls
`observe_theory_run.py`, which executes the unchanged `run_theory_formation.main`.
The fixed plan, every effective config, inputs, states, decisions, certificates,
cycle/expansion logs, checkpoint evaluations, four ablations and profiles are
inside the artifact. No local historical success log supplies a result here.

Read the [pre-instrumentation cap inventory](BOTTLENECK-CAP-INVENTORY-20260913.md)
and [frozen protocol](../handoff/THEORY-BOTTLENECK-STUDY-20260913.md).
The inventory describes the previous process/job watchdogs. This study's
outer watchdogs were900s per normal process and180min per Actions job.

## What MORTRA Actually Did

The initial knowledge includes typed primitives, exact models, proof kernels,
the closure algorithm, enumeration policy and a recurrence evaluator. These
were not invented during this experiment. Inputs contain domain, seed and
resource limits, not target identities or expected representations. The normal
learner never receives the held-out questions, posthoc useful-rule selection,
candidate census or blocked-candidate simplifications.

Concrete saved sequence in `theory-fold-frames-size-9/normal/state.json`:

1. Cycle1: the existing scheduler/generator selected `pull_A(F11)` and admitted
   concept `C-b8f032907b167b70`, with `provenance=self_generated`.
2. Cycle3: MORTRA derived representation `R-b8f032907b167b70`. It is a3-dimensional
   invariant function space on24 declared orientations, with four derived3x3
   action matrices and readout `[1,0,0]`. Closure residuals are all zero.
3. Cycle4: that representation produced `T-recurrence-4380b586bf287038`, with
   characteristic polynomial `r**2+1`, initial values `[0,1]`, and the executable
   recurrence `a[k+2]=-a[k]`. The closure was reused, not reacquired.
4. Cycles5 and6: the stored recurrence returned values-1 and0 at lengths11 and12.
   Both agreed with independent model execution. These calls recorded zero
   acquisition calls and zero proof calls; verification work is charged apart.

Across this fold run there are14 recorded closure-to-new-recurrence uses,
28 new-length procedure uses, and1104 rewrite executions. The recurrence
parameters are acquired executable data; the recurrence evaluator is supplied
infrastructure, not a newly invented general algorithm. This scope certifies
the declared finite orientations and repeated actions, not collision-free paper.

The held-out effect is independently visible. On `H-00-associativity`, both
domains initially exceed the32-node prover-input limit with34 nodes. Algebra
later uses independently acquired rules `T-024f470ed519482e` (commutativity,
cycle5) and `T-ea8d2dc7e49bc6d8` (double negation, cycle610), reducing input to30.
Fold uses `T-3f111b56bdc2592a`, `pull_C(F13)=F33`, proved at cycle335 on all24
orientations, reducing input to32. Both then prove the held-out equality.
These are ordinary known identities compiled into reusable reductions, not
claims of new mathematical laws. No exact held-out query appeared in the
training conjectures in any of the11 conditions, including the larger caps.

## Term-Size Sweep

Seed20260913, held-out seed739182, eight contexts/64 questions per domain;
archive128, active target32, batch12, candidate limit16000, representation
limit4/dimension24, cycle ceiling12000 and original action-body limit600s.
Only term size varies. The extension changes only the cycle ceiling to24000.

`Expanded` counts nonseed acquired concepts; `T` is theorem count. `H` counts
correct proofs AND refutations out of64. Wall time is the complete normal-entry
process, including observation/output overhead, excluding post-run diagnosis.

| Domain / size | Cycles | Expanded | T | H | Prover calls | Rule inspections | Normal wall seconds | Stop |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Algebra9 |3679|124|91|51|3311|3574595|161.310|Bounded frontier exhausted|
| Algebra12 |6505|124|117|51|5934|10752468|465.212|Bounded frontier exhausted|
| Algebra14 |7254|121|123|51|6613|13833156|622.211|600s action limit|
| Algebra18 |5834|77|113|51|5272|10690897|614.363|600s action limit|
| Algebra36 |5645|73|108|51|5079|10628973|613.716|600s action limit|
| Fold9 |12000|116|487|54|11338|38682013|116.531|Cycle limit|
| Fold12 |12000|110|508|54|11349|40866793|129.145|Cycle limit|
| Fold14 |12000|110|508|54|11349|40866793|121.600|Cycle limit|
| Fold18 |12000|110|508|54|11349|40866793|118.343|Cycle limit|
| Fold36 |12000|110|508|54|11349|40866793|121.231|Cycle limit|
| Fold9 extended |12184|117|488|54|11513|39744411|116.798|Bounded frontier exhausted|

All conditions have the SAME archived semantic concepts as their size9 control:
124 acquired algebra concepts and117 fold concepts (128 total including seeds).
Algebra has zero representation spaces; fold has four records spanning two
distinct spaces. No condition adds a new space. Recorded concept-parent depth
stays2/1 and theorem dependency depth3/2 for algebra/fold. Parent records omit
some operand ancestry; they are not a complete mathematical dependency graph.

At larger caps, more composition outputs are permitted. Their post-run exact
semantic census changes from872 to1796 distinct generated algebra meanings at
size9/12, and1457 to1477 for fold9/12. These outputs were NOT all admitted,
executed or acquired by the learner. At size9/36 the semantic duplicate fraction
among distinct eligible syntax is71.50%/62.70% for algebra and76.78%/76.42% for
fold. The full candidate/type/size census is stored per condition.

The algebra14/18/36 runs are censored by the action-time limit, so their final
rows are NOT equal-cycle comparisons. Raising size eventually REDUCED the
number of expanded concepts within that time. Finishing early by bounded
frontier exhaustion at9/12 is also not proof of exhausting mathematics.

## Matched Budget and Fold Scheduling

At exactly1000 prover calls, every size has the same algebra score48/64 at
cycle1096, with11095 prover-input nodes and544577 rule inspections. Every fold
size has53/64 at cycle1097, with6303 nodes and388411 inspections. There is no
early efficiency gain. Equal call counts do not generally mean equal CPU work;
the raw nodes, inspections and timing remain separate in `trajectory.json`.

At cycle4000 all larger algebra caps have51/64; fold has54/64. Algebra9 already
finished at3679 with51/64. This common early diagnostic does not repair the
censored late equal-cycle comparison. No result supports a size-induced gain.

Remaining fold concept `C-b0e8a1d192f09bc3`, `F21+(F11+F33)`, was acquired at578
and reinserted at10262. Its first pre-step observation at10263 is position10
(zero-based) among11 pending concepts, age9685. Its position moves monotonically
to0; it is not continually overtaken. There are1738 recorded observations,
1650 settle actions and88 invent actions. At12000 it is first, but29 open
conjectures exceed the invent-offer threshold24. The original scheduler offers
only settle then. Full per-cycle positions, options, ages and costs are saved.

Without changing scheduling, it expands at12008:129 candidates,97 size-eligible.
The extended run exhausts its bounded frontier at12184 with one extra theorem,
no new concept/representation/depth, and the same54/64 score. At the common
11338-prover-call checkpoint, the size9 and extended states are identical after
removing config and timing fields. This is finite queue delay plus cutoff,
not demonstrated permanent starvation or a hidden useful held-out capability.

## Learned Benefit Versus Lookup Cost

These are post-run diagnostic interventions on discarded evaluation copies.
Useful rules mean rules actually used in held-out or later recorded reductions;
this selection never changes the learning policy. Theorem truth certificates
remain stored; the intervention disables executable reductions only.

| Size9 condition | Algebra H | Algebra rules / median answer ms | Fold H | Fold rules / median answer ms |
| --- | ---: | ---: | ---: | ---: |
| Full |51|91 /24.233|54|425 /5.014|
| Useful only |51|65 /18.891|54|231 /2.840|
| Unused only |40|26 /8.155|48|194 /2.292|
| No learned rules |40|0 /0.856|48|0 /0.634|

All other caps and the fold extension have the same four score outcomes.
Thus learned reductions enable11 additional algebra and6 additional fold tasks
under the fixed32-node bound. Useful-only filtering reduces inspections from
187202 to134672 (algebra), and786771 to427945 (fold), at unchanged score.
Median lookup changes24.058 to18.622ms and4.158 to2.092ms respectively.
Full knowledge is beneficial for bounded coverage, but slower in latency on
this workload. No single scalar "net benefit" follows without pricing those
different objectives. This is not an equal-total-CPU intelligence benchmark.

The function profiles explain where lookup spends work. Across64 unbounded
diagnostic queries, algebra9 inspects187202 rules and performs430 accepted
replacements; root-pattern successes577, failures186442. Fold9 inspects786771
rules and performs53 replacements. Fold uses exact-subtree equality, so its
universal-pattern counter is inapplicable, not missing pattern failures.
Algebra36 inspects221394 rules for the same430 replacements; fold36 inspects
825537 for the same53. Repeated full scans dominate lookup. Same-function
semantic duplicates are50/91 and366/425 rules at size9, but different rewrite
patterns with equal semantics are NOT safely interchangeable or deletable.

For algebra9, profiled `match_term` inclusive time is3.745s within4.943s of
subtree traversal; fold9 traversal itself takes0.366s of its0.471s inclusive
time. These instrumented times are NOT the unprofiled primary timings above.
Whole evaluation profiles are dominated by `deepcopy` for discarded isolated
states (7.391s algebra;16.664s fold inclusive). Do not call this learner search.
Profiles of24 later steps also identify repeated type checks and symbolic
parsing costs; that small early window does not attribute all late-run cost.

Candidate generation, normalisation, matching, proof and execution function
profiles are saved. Inclusive categories overlap and must not be added.
Certificate scope checks are inline in `rewrite`; their standalone time was
NOT isolated. Memory records are raw process peak RSS,312.2..821.5MiB, including
startup and observation. They are not incremental knowledge-only memory costs.

The11 normal processes totaled3200.461s (53m20s). Complete condition measurement
totaled5916.381s (98m36s), leaving2715.920s for replay/evaluation/diagnosis. The
Actions job, including tests and artifact upload, took101m12s. These quantities
must not all be described as autonomous exploration time.

## Answers to the Ten Questions

1. The29 parents hit `Theory.invent`'s PRE-REWRITE `size(t)<=9` gate at line201.
   All have size9. Each generates130 scalar candidates of size10..19, excess1..10.
   All3770 were dropped, not deferred. Full traces are in `blocked-concepts/`.
   Of174 candidates reducible to at most9 using then-available rules, ALL are
   already-semantic duplicates. There are226 duplicates among all3770 candidates.
2. Larger caps permit additional expressions and proved identities, as quantified
   above; they do not add archived mathematical meanings at archive128.
3. No additional archived semantic concept or representation space was acquired.
   The independent archive128/256 study also found no held-out gain; see below.
4. Learning from K0 improves40 to51 and48 to54; relaxing size adds ZERO solved
   tasks beyond that baseline. No source changes supplied the learned rules.
5. Dependency depths do not grow beyond2/1 for recorded concepts and3/2 for proofs.
6. The fold concept expands eight cycles past the old cutoff. No scheduler fix
   was necessary; the delay was not shown to prevent a useful result.
7. Inside answer computation, repeated rule scans dominate matching cost; in
   complete isolated evaluation, state copying is a different major cost.
8. Accumulated rules have positive bounded-coverage benefit and negative latency
   overhead. Unused rules add cost with no measured coverage benefit.
9. Observed throughput is lookup-limited; capability bottleneck resolution is
   negative (categoryF). Size gates are real, but relaxing them does not resolve
   capability growth. Representation-limited is a hypothesis, NOT established:
   `Theory.settle` does not route these held-out tasks through stored spaces.
   Neither proof incapacity nor useful-candidate starvation was demonstrated.
   Archive-size interactions and later equal-cycle outcomes of censored runs
   remain untested; neither isolated sweep proves all joint settings equivalent.
10. Proposed next minimal change, NOT implemented: a structural rule-candidate
    index at `Theory.rules`/`rewrite`, preserving original rule order, all wildcard
    candidates, certificate validation and strictly decreasing replacements.
    Estimated40..80 production lines and60..120 regression-test lines. Require
    identical reductions, dependencies, refusal behavior and held-out outcomes
    before measuring speed. This is a throughput experiment, not a promised
    capability increase. No new solver, scheduler, generator or theorem engine
    is justified by this result. Moving the size check after simplification is
    not supported as a capability fix by the174 duplicate-only recoveries.

The independent fresh [archive-only study](ARCHIVE-CAPACITY-RESULTS-20260913.md),
[Actions34725274254](https://github.com/corcondor/mortra/actions/runs/34725274254),
held the term cap at9 and increased archive128 to256. Its unchanged51/64 and
54/64 scores are corroborating evidence, not a combined size/archive experiment.

## Changes and Nonclaims

The control commit adds measurement wrappers, a frozen study plan, analysis,
observer tests, documentation and one mode in the existing workflow. Mathematical
source and normal entry remain identical to14d18a42. The observers invoke original
methods once and forward original results; parity tests check this on a bounded
trace. Hashes and parity tests are evidence of these checks, not an absolute
proof of absence of every possible intervention.

The post-run `scripts/summarize_theory_bottleneck.py` only reads JSON; it imports
no MORTRA mathematics. It aggregates archived results and checks the deterministic
scheduler prefix. Its local output is
`C:/Users/81808/.openclaw/reports/bottleneck-study-20260913/post-run-summary.json`.
Recreate after downloading the artifact with:

```bash
python scripts/summarize_theory_bottleneck.py --artifact <downloaded-artifact> --output <new-summary.json>
```

This establishes bounded autonomous selection, certification and consequential
reuse using supplied mathematical kernels. It does not establish world-first
theorems, unbounded cumulative growth, autonomous invention of a new general
solver, unrestricted mathematical understanding, or physically legal origami.
