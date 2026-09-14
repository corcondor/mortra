# Internal temporal utility: fixed protocol

Base: `3dc0e10f3fcec2ea407ff6b5cd08667d9b71d02c` in
`corcondor/mortra`, `codex/theory-formation-20260913`.
The preceding 30,661 late admissions and DSL/semantic editing feedback loop
remain established evidence, not a question this experiment repeats.

## Question and scope

Does earlier acquired knowledge reduce the cost of processing later natural
experience? Acquisition-time compression and later utility are distinct.
The present implementation measures finite-model scalar/bool observations,
certified action-word readouts, scalar recurrences and typed acquired macros.
It does not certify panel legality, prove universal computation, add a solver,
or generate a new mathematical frontier. A small primitive count is not an
argument for an expressivity ceiling. Expressivity and autonomous discovery
of useful intermediate representations are different research questions.

## Execution path

`Theory` creates `Vocabulary`, with the optional frozen temporal plan.
`register_observation`, `register_recurrence`, and accepted `learn` results
register immutable mathematical descriptions at the current unique-experience
sequence. Existing certificates, scope, signature and acquisition source IDs
are retained. `record` observes each new unique computation BEFORE admitting it
to the FIFO sample. Duplicates do not advance this clock.

Every measured experience is processed using the prefix's four operation masks.
Only afterwards can bounded paired measurements update future evidence and the
active mask. The active producer also passes that mask to normal `synthesize`;
`solve_observation` accepts the same mask. Inactive calls are lowered using
their archived meanings, not deleted with dangling references. Dependencies
remain available to execute a selected top-level operation. Ablation removes
dependent top-level operations transitively, including recurrence/readout links.

Acquisition evidence uses the retained acquisition sources and a bounded prefix
sample. Macros use their original acquisition compression score. Readouts and
recurrences use the bounded prefix's description saving, with implementation
cost. Sampling/lowering/matching costs are recorded. This is a heuristic
selection score, not future evidence or a newly acquired mathematical theorem.

Future evidence has `sequence > acquired_after` and excludes acquisition sample
IDs. It stores both sides of each counterfactual, input/source/context, exact
outcome and measured work. No external task result is sent to this observer.

## Four conditions and causal limits

The existing normal Theory producer uses seed 20260913, FIFO 512, semantic
editing, eligible source filtering, and unchanged mathematical budgets. Only
its wall-time safety ceiling increases to 3,600 seconds to accommodate charged
instrumentation. All four conditions see the same prefix archive and the same
natural program stream, in order:

- A: all certified operations available, including certified operator aliases.
- B: six operations ranked by acquisition utility, then age and content key.
- C: at most six operations, chosen by measured future utility.
- D: initial operations; acquired calls in incoming experiences are fully
  lowered, and their lowering/computation cost is charged.

This is a shared-stream counterfactual experiment, NOT four independently
evolving learning curricula. Its target is causal downstream utility, not
curriculum effects. An additional 2,000-experience normal run uses the temporal
mask in the actual producer. Its stream may differ and is not a paired gain
comparison. `dsl_active_generation` events expose what the generator received.

Every window also evaluates C-fixed: active operations AND semantic equations
frozen at its start. New equations during the window cannot leak into this
condition. Windows 1..1,000 through 10,001..11,000 measure K0 through K10000.
Library cost includes dependency implementations and certificates, deduplicated
by content, once per window. Program costs and library costs stay separate.
The exact immutable archive is shared as a decoder, not silently offered as
extra synthesis operations to D. Definition-call depth is reported; mathematical
semantic-abstraction depth is explicitly unmeasured, not inferred from nesting.

## Selection and measurement limits

There is no weighted reward. Description bits, search applications, proof calls,
model node evaluations, action steps, matrix arithmetic, recurrence arithmetic,
matching, validation, solution success and cross-context reuse are separate
coordinates. Missing measurements are `null`, not zero. Arithmetic event counts
are not bit complexity. Wall times are recorded but do not rank candidates.

The temporal selector uses Pareto dominance. Different measurement coverage is
incomparable. The no-use baseline can exclude an operation weakly worse on all
measured coordinates and strictly worse on one. Within a Pareto front the fixed
tie-break is: measured before unmeasured, smaller body, older acquisition,
content key. These are declared heuristic choices, not an optimality theorem.
Six is an upper bound, not a requirement to fill bad branches. Certified
objects are never erased by selection. The least-measured archive member,
then oldest measurement and content key, receives the next probe, including
inactive members. Changed later evidence can reactivate an archived object.

Main bounds: 11,000 experiences; window 1,000; shadow every 128, at most 96 pairs;
internal value-goal search every 1,000, at most 12 comparisons; 100,000 charged
operations per execution; 128 search applications and 100,000 work per search;
16 recent measurements per operation. Archive/probe limits and stops are
recorded, not interpreted as mathematical exhaustion. Finite probes do not
guarantee that every useful operation will be discovered.

The internal search target is the just-observed complete-model value vector;
its constructing program is NOT given to the existing goal-directed planner.
All masks have identical input seeds and resource limits. A rotating selected
operation is ablated with dependencies, on the same target. Search/proof costs
are measured only at these probes, not fabricated for every execution.
Ordinary certified execution requires no new prover call; independent original
execution/replay is separate, never inferred to be free.

Cold interpreter and pattern caches are used for every paired processing case.
Expansion, equation matching, type/scope checks, original-action lowering,
execution, independent replay, selector measurements and persistence are
recorded. Total time includes instrumentation. Cost categories in the parent
Theory report can overlap observer time; do not sum nested times. Failed cases
remain failures; `common_solved_costs` is the comparison on identical successful
inputs, rather than claiming fewer operations from earlier failure.

## Reproduction and external isolation

Install `requirements-test.txt`, then:

```text
python -m pytest -q tests/test_temporal_utility.py tests/test_theory_dsl.py tests/test_theory_semantic_edit.py tests/test_theory_corpus.py scripts/test_library_compression.py scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py tests/test_theory_formation.py
python scripts/verify_temporal_utility.py --plan configs/theory-temporal-utility.json --output <new-directory>
```

The normal entry is still `scripts/run_theory_formation.py`, now with
`--temporal-plan <json>`. The comparison harness invokes it, preserves exact
commands/source seals/plan/environment, and retains any failed run. Saved
Theory snapshots preserve versions, evidence, masks and cursors. Boundary tests
use artificial fixtures, not autonomous-acquisition evidence.

The prior 48 value-goal tasks (917334/917335) remain regression evaluation.
Another 24 tasks (seed 920914) are reserved by the plan. The existing task
generator freezes all specifications before training; witnesses stay only in
the evaluator. Evaluation starts after training/selection finish. All four
final masks are frozen before the first query, and the acquired state digest
must remain unchanged. External results never train selection. Development
mode excludes ALL those targets and uses only 600 internal observations.

`worker-ci.yml` keeps the q-directed tests/normal/reuse/refusal checks. Research
pushes now run this temporal experiment instead of repeating the already
established long DSL-feedback comparisons. The previous comparisons remain
available as `workflow_dispatch: dsl-feedback`. `temporal-utility` explicitly
dispatches this study. Artifacts preserve normal states, learning curves,
counterfactual evidence, active choices, queries, failures and verification.

No claim of capability improvement is made by this protocol. The results must
separate mechanism correctness, internal prequential benefit, external
generalization, and the still-unmeasured use of folded panel structure.
