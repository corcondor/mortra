# Mechanism, method, and conditions for autonomous geometry search

## Scope and baseline

Repository: `corcondor/mortra`.
Branch: `codex/geometry-failure-location-20260915`.
Starting commit: `89fb48869fb81c8c3108b3079c9edc3b0ddea37e`.
Existing untracked reports are preserved, not adopted as fresh evidence.
The existing normal entry is `scripts/run_theory_formation.py` with
`domain.mode=symbolic_solve`. No new solver entry or task-specific formula is added.

The fixed regression input remains
`configs/theory-geometry-autonomous-solve-worker-reuse.json`: eight tasks,
seed 917401, 256 charged construction attempts, depth 5, 90 seconds per task,
5 seconds per proof attempt. Its task digest is
`e1a1f61de6caab913dcd00351b22277ebefb4186b5d3ddda5966ba9844ecd572`.
The cohort is developer-exposed regression material, not an unseen benchmark.

## Mathematical obligations and executable paths

Let X be symbolic states, including assumptions and proof scope. For fixed L,
define F(S) = I union S union Post_L(S). Relational Post preserves increasing
unions. Thus its least fixed point is the union of finite iterates from the
empty set. This describes reachable states; it does not imply inexpensive
search or finite termination for an infinite geometry state space.

`search_action_domain` installs typed state actions into
`synthesize_typed_plan`. The latter interleaves state/family streams. The
assumptions for eventual coverage include terminating candidate enumeration,
fair execution, a sufficiently large depth allowance, and no unsound state
merging. The actual runs have finite budgets, numerical proposal filters, and
incomplete construction verification. Therefore they are not complete searches
of Euclidean geometry. A timeout or application limit is not a fixed point.

`test_geometry_closure_contract.py` compares that existing planner with an
independent finite-set closure and replays a path to a goal. These are artificial
algorithm tests, not autonomous mathematics or evidence of geometry completeness.

Goal-directed predecessors are already proposed by
`GeometryDomain.native_candidates` using backward obligations and typed
contracts. They order a prefix of candidates; `SymbolicDSLDomain.candidates`
retains the complete binding stream as a fallback. No claim is made that the
finite backward proposal list computes the full predecessor fixed point.

References: [Tarski, Theorem 1](https://people.csail.mit.edu/carroll/probSem/Documents/Tarski.pdf)
for monotone fixed points, and [Cousot and Cousot](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml)
for abstract semantics and fixed-point approximation. The mapping to this code
and the finite tests are this project's formulation, not claims from those papers.

## Conservative construction extension

Write the original assumptions as Gamma(x), construction relations as C(x,y),
and the original goal as Q(x). An auxiliary is safe if a rational witness r(x)
is defined everywhere in the declared original scope and

    Gamma(x) implies C(x,r(x)).

Then proving Gamma(x) and C(x,y) implies Q(x) proves the original goal by
substitution y=r(x). This requires existence, not merely observing one numerical
diagram. Unproved denominator conditions cannot be added to Gamma.

Two existing-path defects are addressed:

1. Some registered constructors have no name-specific coordinate handler.
   The fallback reads the existing declarative definition, finds a full-rank
   affine subsystem in its predicate equations, and derives its unique rational
   witness. It verifies every declared effect, including nonlinear effects not
   used in the solve. It keeps determinant and declared requirement guards.
   Underdetermined, nonlinear-only, unsupported, or inconsistent definitions
   are refused. No point coordinates, task ID, or desired goal are supplied.
2. Existing supported multi-locus constructions can introduce local parameters
   even when the resulting point has rational coordinates. The extension gate
   now reuses `_compress_affine_clause`, retaining its forward/reverse identity
   certificates. It eliminates only newly introduced variables. It preserves
   the old coordinates and equations, checks pre-elimination guards again, and
   requires all remaining nonzero factors to follow from the original scope.

Chart parameters and polynomial-ring generators are distinct. The witness
domain is the original chart's parameter field, not just its elimination-ring
generators. Free/algebraic variables that survive elimination remain refused.

The fallback does not turn every registered constructor into an executable
operation. It also does not add these operations to the acquired-library
fragment automatically. A new executable source constructor, a learned
definition, and downstream learning improvement are separate claims.

## Experimental separation

- Development uses synthetic definitions, wrong effects, degenerate guards,
  unknown branches, and unchanged-source checks.
- Normal execution uses the unchanged eight-task plan. The program chooses
  proof requests, construction families, and bindings. No mid-run input is
  supplied. Source seals and all failure events are retained.
- Goal acceptance still requires the existing exact proof gate and an
  independent replay. No sampled equality or unknown proof is accepted.
- Costs include rejected proposals, witness derivation, proof attempts,
  numerical construction, and process overhead.
- Learned-library benefit is not measured here: the initial archive is empty.

## Fresh development evidence

Before edits, the three related test files produced 74 passed, 1 skipped in
108.62 seconds (`reports/geometry-closure-baseline-tests.xml`).
The first new-test attempt failed during collection because of the dependency's
import cycle. That failed output is retained as `geometry-affine-dev-01.xml`.
Correcting the test import order produced 12 passed in 4.27 seconds
(`geometry-affine-dev-02.xml`). These are not normal-run acquisitions.

The five independent finite-closure tests passed in 0.68 seconds
(`reports/geometry-fixed-point-tests-01.xml`).

The local normal run `reports/geometry-affine-normal-01` was stopped after
repeated worker-startup timeouts. On task 0 all 11 completed proof attempts
reached the fixed 5-second deadline without a worker-ready message. The local
regression suite was running concurrently. `stop-note.json` records the stop;
the partial outputs remain. This is not a completed mathematical comparison.
No input, witness, or runtime source was changed during that execution.

## First immutable-commit result: rational witness derivation

Commit: `e556ab8ec58eb3fb3f3e44bd3d2bdfba8f15d5b0`.
[Actions 35056838364](https://github.com/corcondor/mortra/actions/runs/35056838364)
passed: 271 tests, 1 skipped; the separate exact-kernel job also passed.
The unchanged eight-task cohort produced six proved and independently replayed
goals, one application-budget stop, and one timeout. All six were already
provable at the original state; no acquired library was used. The witness
derivation change did not improve this cohort's solved count.

The run's `minimum_scientific_success=false` is retained. A successful workflow
means the experiment and its checks ran, not that the research objective was met.
The downloaded artifact is under `reports/geometry-affine-actions-35056838364/`.

## Separate source-scope correction

The installed Newclid implementation `newclid/jgex/geometries.py`, function
`reduce_intersection`, rejects an intersection of two loci if it coincides
with any previously existing point. In contrast, a single locus samples a
point and does not use that two-locus rejection loop. The existing polynomial
bridge only retained some structurally obvious existing-root exclusions.

The new optional `source_scope` proof-request operation translates the existing
two-locus noncoincidence premise into nonzero squared distances. This is a
source-language premise, NOT a theorem derived from the equality constraints,
nor a choice of the desired goal's branch. It does not enforce numerical
sampling tolerances or select between two still-admissible distinct roots.
Its use is explicitly recorded in the certificate's semantic assumptions.
Only recognized line/circle locus constructors are handled; no claim is made
about arbitrary constructors or natural-language inputs.

The existing typed planner can choose this operation and compose it with the
other exact representation operations. No task-dependent option is supplied.
The request space changes, but the frozen cohort and all budgets remain fixed.
Auxiliary extension certification and independent replay use the same scope
option. If a new auxiliary adds noncoincidence premises absent from the
original scope, the conservative-extension gate refuses it; no such premise
may be smuggled into a proof of the original problem.

Eight synthetic source-scope development tests passed in 11.14 seconds
(`reports/geometry-source-scope-dev-01.xml`). They include automatic selection
of the new operation, point renaming, a false single-locus claim, and refusal
of auxiliary scope strengthening. These are developer-authored regression
fixtures, not autonomous discoveries or unseen evaluation results.
This correction is evaluated at a separate immutable commit and Actions run.

## Second immutable-commit result: source scope

Commit: `f4334cead7ca669f044bf6d2c3143fae735cee79`.
[Actions 35057342456](https://github.com/corcondor/mortra/actions/runs/35057342456)
ran on Linux x86_64, Python 3.12.14, using the declared
`requirements-geometry-contracts.txt`. Neither Yuclid package nor executable
was present. Tests: 279 passed, 1 skipped in the feedback/regression suite;
10 passed, 76 deselected in the targeted existing bridge suite; 64 passed in
the exact-kernel job. The one warning is the intentionally renamed development
definition's enum serialization, not a proof failure.

The exact normal command on both Actions runs was:

```sh
python scripts/verify_theory_geometry.py --plan configs/theory-geometry-autonomous-solve-worker-reuse.json --output reports/semantic-feedback-normal
```

Each task is launched through `scripts/run_theory_formation.py`. The actual
per-task commands, resolved tasks and budgets, source hashes, environment,
failures, proof requests and replay results are in the uploaded artifacts.
Source hashes were unchanged during each run. No task answer, desired proof
request, auxiliary construction, or run-time edit was supplied. This is an
operational record, not a cryptographic proof that intervention was impossible.

| Measurement across the same eight regression tasks | e556ab8 | f4334ce |
| --- | ---: | ---: |
| Proved and separately replayed goals | 6 | 7 |
| Application-budget stops | 1 | 0 |
| Task timeouts | 1 | 1 |
| Completed proof attempts in the saved trace | 430 | 315 |
| Construction attempts started | 407 | 153 |
| Construction applications completed | 22 | 8 |
| Sum of task subprocess wall times, seconds | 213.827 | 155.787 |
| Acquired calls in successful goal paths | 0 | 0 |

These are single-run wall times, not a statistical speedup claim. Fewer
construction attempts mostly reflect earlier proof termination, not improved
construction efficiency. Counts from timeouts cover the saved trace and do not
pretend that an interrupted attempt finished.

The new success is task index 4,
`examples/complete2/011/complete_003_6_GDD_FULL_21-40_34.gex`.
The fixed planner generated this actual proof program:

```text
Original formal assumptions and goal
  -> relational_chart
  -> source_scope
  -> certify
  -> remainder = 0, exact_replay = true
  -> separate-process replay passed
```

For this task, the request with only `relational_chart` failed in 0.184 seconds
with a nonzero remainder. The otherwise identical request adding `source_scope`
passed in 0.614 seconds. Its used nonzero condition is the squared distance
between the new intersection and an existing point, translated from the source
two-locus rule. It has no untransported conditions and no vacuous unit ideal.
The selected certificate SHA256 is
`f78c9bb5062a237e2145f64c8f42cb066d004b2acdd396480dd32169e7441ba3`.
This within-run comparison supports attribution to retained source scope,
not simply to spending longer on the same polynomial request.

Finding the proof took 10 exact attempts and 62 planner applications. Charged
proof search took 4.743 seconds including its worker startup. Registering the
existing primitive library plus search took 7.184 seconds; independent replay
took 2.103 seconds. The outer task process took 11.392 seconds, including
additional startup and reporting. In the first run the same task timed out at
90 seconds. Replay uses a fresh process with the same exact backend, not a
second independent theorem-proving algorithm.

Task index 2 remains unresolved. Its cost worsened: 260 proof attempts and
70.089 seconds in the first run became 295 completed proof attempts and a
90.012-second timeout in the second run. The expanded request vocabulary can
consume budget without finding a proof. No impossibility or false-theorem claim
is inferred from this timeout or a nonzero reduction remainder.

All seven successes are original-state proofs. The acquired archive is empty,
and no auxiliary construction was needed for a successful goal. Consequently
`minimum_scientific_success=false` remains in `verification.json`: autonomous
selection of a sound existing proof procedure improved, but this run does NOT
establish learned-morphism benefit, autonomous theorem acquisition, or unseen
generalization. The earlier DSL feedback achievements remain separate evidence.

## What the mathematics guarantees, and what remains experimental

1. A monotone reachability operator describes the least reachable closure.
   Enumeration realizes it only under coverage, fairness, termination of each
   step, adequate depth, and semantics-preserving state comparison. The finite
   reference tests exercise this contract, not all geometry.
2. A certified composition preserves its premises and conclusions. The new
   witness checks enforce existence in the original scope; the source-scope
   correction preserves a premise that was already in the input semantics.
   Neither permits adding a convenient unproved premise.
3. If an acquired definition has a finite primitive expansion with identical
   semantics and applicable guards, adding it does not enlarge unlimited
   semantic reachability: expand each call to obtain a primitive program.
   It can change bounded-cost reachability and search ordering. Whether this
   lowers total cost, including acquisition and matching, must be measured.
4. The active vocabulary, finite timeouts, numerical proposal filters and
   restricted witness language prevent a general completeness claim here.
   Fixed-point existence alone proves neither efficient search nor cumulative
   learning. A future comparison must attribute any learned-library benefit
   to its actual use in proof dependencies and a matched ablation.

## Shared evidence

- First [artifact](https://github.com/corcondor/mortra/actions/runs/35056838364/artifacts/10430669759):
  archive digest `sha256:a9a625b57f06986c381038c1cd914d22cc10d6b2ebabf5f22da3cb8d0ef96e8a`.
- Second [artifact](https://github.com/corcondor/mortra/actions/runs/35057342456/artifacts/10431321712):
  archive digest `sha256:5478d202c66d018a1ca4fc65d2ab214fed1f7f1e90ec49ba0c578e02d4df7faa`.
- Local downloads: `reports/geometry-affine-actions-35056838364/` and
  `reports/geometry-source-scope-actions-35057342456/`.
- Interrupted Windows runs and failed collection output remain separately
  retained; they are not substituted for the fresh Actions results.
