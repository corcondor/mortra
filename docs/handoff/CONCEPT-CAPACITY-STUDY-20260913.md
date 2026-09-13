# Concept Archive Capacity: Fixed-Code Study

Historical stage1 protocol: use control commit
`4c06d309105495debba6598210e6c42b8f215e69` for the term-size9 plans below.
The current branch's capacity plans are stage2, at term-size12; see
[the configuration-only interaction protocol](ARCHIVE-TERM-INTERACTION-20260913.md).

## Decision being tested

The frontier connection experiment (Actions 34723806396) reactivated acquired
concepts and produced later theorems, but did not increase held-out success.
Both domains had reached their 128-concept cap. Therefore, test archive capacity
as a single factor before adding mathematical mechanisms.

Mathematical target: `14d18a42c3a7c640a7c54c86c36b7238c419df56`.
No mathematical source, normal entry, scheduler, solver, prover, primitive,
grammar, representation language, retrieval policy or procedure synthesis is
changed. Control changes are two committed plans, an evaluation/provenance
aggregator, guard tests, and an option in the existing Actions workflow.

## Frozen comparison

Use `configs/persistent-learning-capacity-128.json` and
`configs/persistent-learning-capacity-256.json`. Only
`budget_override.concepts` differs. Both start from K0 in fresh processes, on
the same exact mathematical SHA, in the same Actions job. The smaller capacity
is freshly rerun, not replaced by an old successful log.

All other settings remain: training seed 20260913; held-out seed 739182;
12000 cycles; 600 accounted engine seconds; 16000 candidates; 32 active
concepts; term size 9; 4 representation records; 8 held-out contexts (64
questions/domain); three evaluation repeats; proof-input budget 32 AST nodes.
Domains are the existing differential ring and the existing 24 fold frames.
No mid-run candidate, target, helper quantity, or theorem is supplied.

Both plans and both complete challenges are committed/frozen before learning.
Preparation verifies that K0 has both solved and budget-exceeded questions.
Any mismatch halts the experiment without retuning. Evaluation never returns
answers or new state to training. Existing checked resume preserves each arm.

## Measurements and causal comparison

Retain the existing per-cycle archive sizes, semantic representation families,
theorem dependency depths, downstream reuse, held-out outcomes, proof input,
rule inspections, matching time, engine time, total execution time and replay
checks. Additionally compute recorded concept-parent depth, newly acquired
concepts absent from the smaller-capacity final archive, their expansion,
their children, and theorems with recorded concept-generation dependencies.
Parent links are not a complete DAG of all operands; report this limitation.

For both capacities compare K0, Kt and the existing all-rule/earliest-rule
ablations. Predeclare this additional C: disable every theorem present only
in the 256-condition final archive and its recorded proof descendants on a
discarded copy; evaluate the same fixed questions with the same budget.
This tests dependence on the *additional* acquisition, not on initial learned
rules that already worked at 128. Do not choose a target theorem after seeing
which ablation produces the most favorable result.

Unbounded evaluation is also saved. K0 already solves that suite unbounded;
bounded improvements are not claims of previously unknown mathematics.
More concepts or deeper syntax alone do not constitute capability growth.
Single-seed results do not establish robustness or monotonic improvement.

The representation cap remains 4. Zero new representations still cannot
establish that the representation language is insufficient. Capacity may
increase matching cost, change the internal task sequence, or worsen success;
retain those outcomes. No new implementation is authorized by a positive or
negative result in this experiment.

## Execution

Dispatch the existing `worker-ci.yml` with suite `capacity-study`, target_ref
and expected_sha both equal to the mathematical target above, from the
committed control branch. The job repeats q-directed tests, normal/reuse/refusal
runs and theory guards, freezes evaluation, then invokes the existing
`measure_persistent_learning.py` twice and performs discarded-copy analysis.

The artifact `capacity-study/` includes preparation records, both fresh normal
runs, source seals, actual commands, fixed inputs, checkpoints, trajectory CSV
and JSON, concept lineage, ablation outcomes and verification.json. The outer
artifact records run ID, mathematical SHA, control SHA and environment versions.
Use those immutable IDs, not an ambiguous latest branch, for comparison.
