# Contraction measurement completion and the geometry objective

## Objective, not a replacement objective

The user's core architecture is:

```text
fixed small predicate vocabulary
+ fixed small construction-morphism vocabulary
+ native exact deduction
+ autonomous auxiliary search
```

Construction composition may introduce more points and relations to make a
proof reachable. Fewer primitives, fewer points, or fewer states is not itself
the objective. Certified contraction is an optional optimization of acquired
procedures, not a prerequisite for mathematical capability. Its failure cannot
be treated as failure of that architecture or as evidence of an expressivity
limit. We must distinguish native consequence discovery, auxiliary search,
acquisition, and the cost of reusing an acquired operation.

## Scope of this correction

The experiment at `adf05ea8e3437d254ec89bd9805636b6e39076a1` remains frozen.
Its clean Actions run is `34826898742`; its archived data and FAIL verdict are
not changed. The earlier four-task negative at
`39ce48368639f3c508bdd611b06339aad893f342` is also unchanged.

Three measurement defects are corrected, without changing search order,
construction generation, refinement, preconditions, task selection, seeds,
budgets, or the scientific gate:

1. The typed planner retains observational progress counters even when a domain
   budget exception exits search. Completed application slots plus initial
   facts remain the meaning of `states_explored`. Started but interrupted
   applications are counted separately. Retained facts are counted separately.
2. Primitive proof node count and longest dependency depth are separate fields.
   `measurement_version: 2` marks the corrected meaning of
   `expanded_primitive_proof_depth`. Macro dependency depth also includes the
   prerequisite acquired action when an internal point is restored. The
   relevant-action slice retains that prerequisite too.
3. Independent replay recomputes every frozen scientific criterion from the
   comparison rows and checks both saved verdicts. It no longer copies the
   producing experiment's boolean as its own scientific conclusion.

The first two corrections are general measurement infrastructure, not acquired
mathematical knowledge. Tests use synthetic examples for development only.
No expectation or synthetic definition is supplied to the normal run.

## Attribution that must remain separate

The previous clean result had a primitive-baseline loss on task 101-2. The
exposed syntactic and exposed certified macros already lost the same task.
Therefore this observation is not evidence of a loss caused by hiding.

The hiding-only condition lost no solved task against the exposed syntactic
condition, but increased aggregate expansions from 447 to 460. Hiding includes
the paid restoration mechanism: it offered 44 restorations, executed 44, and
charged 88 primitive-equivalent operations. Removing these costs from the
record, or removing restoration without preserving access to needed internal
points, would manufacture an apparent improvement.

The summarized condition reduced expansions to 239 and solved 6/8, but combines
hiding with precondition filtering and effect ordering. This is not a measured
hiding-only gain. The new independent audit reports losses by baseline and
restoration costs; it preserves the original conservative FAIL gate.

These figures are previous clean-run evidence, not a fresh measurement in this
completion. Any subsequent run is a separate instrumented regression, not a
new unseen evaluation: the eight-task cohort has now been observed.

## Existing execution paths must not be conflated

At base commit `19258af141c514addd9bf5c262a2123063c35c35`:

- `geometry_contracts.py` declares midpoint and perpendicular-foot constructors,
  and midpoint, collinearity and vector-orthogonality predicates. Its rational
  witnesses and polynomial identities are checked by MORTRA's existing exact
  bridge, using SymPy/flint arithmetic, not an external geometric prover.
- `RationalGeometryDomain` autonomously enumerates and composes those
  constructions and checks candidate output coordinates against the given
  polynomial goal. This is not a general closure engine that discovers every
  geometric consequence.
- The committed broader `GeometryDomain` still offers external Newclid/Yuclid
  deduction backends followed by independent exact certification. Existing
  uncommitted work adds `close_exact` and bounded consequence generation. That
  work predates this correction and is deliberately not included in this
  commit or counted as a newly verified shared capability.

The existence of all these files does not establish that a single shared
normal run joins all four architectural elements across general geometry.

## Reproduction

Use the existing `worker-ci.yml` dispatch with `verification_suite` set to
`geometry-contraction`, and pin `target_ref` and `expected_sha` to the correction
commit. Keep `configs/theory-geometry-morphism-contraction.json` unchanged.
The existing workflow executes the q-directed baseline, the related geometry
tests, the normal comparison, and independent replay, then uploads artifacts
even if the unchanged scientific gate fails.

The normal run and replay commands remain those in
`docs/handoff/GEOMETRY-CONTRACTION-REPRODUCE-20260914.md`. For measurements from
version 2, supersede only its old caveats about null state counters and the
misnamed primitive depth. Do not reinterpret or rewrite version-1 data.

Development validation: the six-module geometry test command in the existing
handoff passed 133 tests with 1 skip in 66.51 seconds. Four passing tests belong
to pre-existing uncommitted broader-geometry work, so this is not a clean
checkout count. The focused contraction module passed 34 tests in 23.88 seconds.
Raw records are `reports/geometry-contraction-measurement-tests.log` and `.xml`.

The corrected independent replay on the **previous** clean Actions artifact
passed all correctness checks and independently retained scientific FAIL.
Its record is `reports/geometry-contraction-independent-gate-v2.json`.
The failed criteria are `no_lost_baseline_solve` and
`hiding_only_aggregate_search_lower`; no loss is attributed to hiding relative
to the exposed baseline. This is fresh checking of old data, not a fresh normal
run or unseen evaluation.

New run IDs, exact commit identifiers, and normal-run measurements are recorded
separately after execution. A completed correction is not a claim that
contraction improves search, and does not authorize implementing stratification,
a new selector, or another solver.
