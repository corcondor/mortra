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

Shared Actions references will be appended after the immutable-commit run
finishes. No solved-count improvement is asserted here.
