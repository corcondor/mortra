# Structural definitions and program-search capability

This experiment preserves the working DSL acquisition/execution/dependency
cycle. It changes the evaluation, not the learner's target selection or its
definition bodies. It starts from code commit
`2b21189a65e7978ea935a9cb2583688cba07363f`.

## Why a second protocol

The first value-synthesis protocol disabled every acquired operation in C,
including represented observations. It did not isolate structural definitions.
Its 12-node surface bound also needed a separate check before interpreting any
advantage of a macro. Those results are retained, not relabelled:

- Actions run 34749782822, SHA `2b21189a65e7978ea935a9cb2583688cba07363f`.
- Artifact 10315338210, digest
  `ffd3c9c6afe67c69b7405753d6e57595ff542fa1497d6174e8d2ee3ce68d0dfb`.
- Local independent checkout results are under
  `C:/Users/81808/.openclaw/reports/dsl-semantic-2b21189-917332/` and
  `C:/Users/81808/.openclaw/reports/dsl-semantic-2b21189-917333/`.
- Local A/B/C solved counts were 10/8/10 and 13/12/13, out of 24 each.
  No formerly unsolved task became solved. No size refusal occurred in those
  runs. These local results are not the later Cloud measurements.

The still earlier `eb086d561cc12ad93799736148c1edd466afb588` run's fold
structural wrappers were unused. Its representation and recurrence calls are
not retroactively counted as uses of those wrappers. The later compositional
definitions have their own runtime IDs and execution records.

## Fixed evaluation inputs

The existing initial-language random generator creates 24 distinct complete
finite-model value specifications before training. Source depths remain
4 at depth 0, 4 at depth 2, 8 at depth 4, and 8 at depth 6.
Only duplicate specifications are rejected. No acquired definition, learned
answer, or evaluation success is consulted in target generation.

The new measurement seeds are fixed as **917334 and 917335** before either new
measurement. Both will be reported. Earlier development uses seed 917331; the
earlier protocol used 917332 and 917333. Development has seen those earlier
results and the learned library. The new inputs are not selected for that
library, but this is not a claim that developers have never seen its structure.

Every task supplies exact rational values on all 24 orientation states, scope,
and budgets. It supplies no expression, witness, h, g, or preferred route.
The evaluator stores the primitive witness separately and never passes it to
the normal process. Thus all tasks are expressible in the initial language.
The evaluation additionally verifies that every witness fits the same bounds.
Semantic overlap with the learning corpus is labelled afterwards; overlapping
tasks are not silently advertised as unseen mathematics or removed from the set.

## Conditions and resource accounting

- A: initial operations only.
- B: the learned archive, including structural definitions, represented
  observations, and certified recurrences.
- C: the identical saved archive with structural definitions disabled only.
  Represented observations and recurrences remain available. No dependencies
  are deleted. The enabled-operation lists and archive digests are checked.

All use the same planner, initial arguments, and round-robin candidate policy.
Each task permits 512 states (initial facts plus attempted applications),
1,000,000 interpreter work units, depth 64, surface size 4096, and expanded size
4096. The size limits are safety limits, not short-expression scoring. The
verification gate requires **zero size refusals in A/B/C**, as well as primitive
witness admissibility. A positive result with binding size limits would not
pass this protocol.

Work is charged before execution: one unit per expanded data visit, finite-model
AST node evaluation, action step, or rational multiply-add. This is a declared
interpreter operation count, not bit complexity or hardware instructions.
Type/scope checking, definition lookup, symbolic parsing, hashing, registration,
and serialization are included in wall time. Type/lookup counts, expansion
visits, macro expansions, representation calls, recurrence calls, and independent
verification checks are also reported separately. No pattern-rewrite matching
is used by this synthesizer; its matching counter is explicitly zero. The
retained 48-expression compressor separately measures its actual rule matching.

Every external task starts with cold interpreter caches. Caches are infrastructure,
not learned knowledge. Independent primitive replay is charged to the same work
budget. A candidate that runs out of budget before verification is not solved.
No acquisition or task-theorem proof occurs during query evaluation.

The returned wall time includes all query phases. Expansion/type validation
time inside evaluation is a nested measurement and must not be added again to
evaluation time. Exact commands and per-process logs also retain startup and
archive-load overhead; the harness records total experiment time.

Description lengths use canonical JSON bits. Each structural body, signature,
scope and dependency record is charged once. Active certified spaces, readouts
and procedure records are charged separately, including their certificate
records. This is a conservative stored representation cost, not a claim of
minimal encoding. The same stored archive cost remains visible in C. Suite
description length charges the active library once plus solved programs; because
conditions can solve different tasks, a second comparison uses only their
common solved subset. Learning cost is reported separately and is not free.

## Reproduction and interpretation

```bash
python -m pytest tests/test_theory_dsl.py tests/test_theory_formation.py \
  scripts/test_library_compression.py scripts/test_expand_for_execution.py \
  scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917334 --output <fresh-directory-334>
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917335 --output <fresh-directory-335>
```

Use the existing `worker-ci.yml` `dsl-feedback` dispatch with an exact
`target_ref` and `expected_sha`. It retains the 351-test baseline,
normal/reuse/refusal, theory regression, and 48-expression evaluation tests.
It runs both new task sets and uploads the evidence, including failures.

The run report separates acquisition of executable definitions, actual later
calls, h-to-g dependency, search capability changes, and total cost. Infrastructure
checks passing does not imply that learned definitions improve search. Negative
and regressive results remain in the report. This protocol concerns exact
functions of the finite orientation model, not collision-free folding or all
origami geometry.
