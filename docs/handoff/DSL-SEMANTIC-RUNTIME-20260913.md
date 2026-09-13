# Semantic-runtime cost experiment

Baseline: `5b6c7b7d2c4cff608806cde7d07f035afd262d6a`, the report-only
successor of tested code d1e36278bd29f094ce98b73b57e058a6adcf054a.
The previous turn was progress (implemented editing and obtained a negative
generalization result), not completion of cumulative mathematical intelligence.

## Diagnosis before changes

Normal-entry cProfile on the previously seen 917334 regression cohort used a
fresh local 300-cycle learned archive, without changing the baseline sources.
This is development evidence, not an unseen-task capability claim.

- 24 queries, 9 solved, 8941 explored states.
- 49.758 profiler seconds overall; profiler overhead prevents comparison with
  unprofiled wall times.
- 18519 definition-table constructions: 5.422 cumulative seconds.
- 13779 SymPy expression parses: 12.048 cumulative seconds.
- 14249 representation materializations: 0.917 cumulative seconds.
- 458 semantic-equation validations: 0.125 cumulative seconds.

These call-tree times overlap and must not be summed. The evidence does not
support skipping proof checks as the main fix. The dominant redundant work is
syntax parsing and repeated reconstruction of unchanged definition tables.

Local evidence is under `C:/Users/81808/.openclaw/reports/`:
`dsl-edit-validation-profile-training-v1`, `dsl-edit-validation-profile-v2`,
and `dsl-edit-validation-profile-v2.prof`.

The first profiling attempt (`dsl-edit-validation-profile-v1`) was refused:
Linux source-seal keys use `/`, while Windows used `\\`. Normalizing just the
separators for diagnostic comparison found no changed content hashes. The
archive was not edited to bypass the guard. A separate local normal run was
used for the successful baseline profile.

## Generic changes

No solver, definition candidate, equation choice, task answer, or scheduling
rule changes. This is interpreter infrastructure, not runtime-acquired knowledge.

1. Cache parsing of literal integers and rational-number strings, bounded at
   512 entries. Do not cache arbitrary expression strings. Exact rational type
   checks remain. Cached objects are immutable SymPy values, not observations.
2. Reuse a detached execution definition table only if the canonical bytes of
   every current definition body match. This detects body edits and additions.
   Public `table()` still returns a fresh copy. Calls still validate current
   types, scope, arity, recursion, expansion limits and the table seal.
3. Clear these caches for every evaluation task. Record table builds, hits,
   serialized key bytes, elapsed table time and literal parse hits/misses.
   These counters describe interpreter overhead; existing arithmetic-work units
   retain their meaning. All overhead is included in wall time.
4. Normalize newly emitted source-seal paths with `as_posix()`. Content hashes
   and config equality are not relaxed. Archives from genuinely different code
   remain refused. Cross-platform reuse must be tested with the same new code
   version, not by rewriting a previous input manifest.

`--uncached-syntax` is a diagnostic normal-entry ablation, not a learned policy.
It rebuilds tables and reparses literals while using the same mathematics and
archive. Resume rejects changes to this setting within one training run.

## Frozen evaluation

Plan: `configs/theory-semantic-runtime-evaluation.json`.
Development harness seed: 917331. Regression: 917334/917335. Fresh: 918051/918052.
Previous fresh seeds 918041/918042 are no longer treated as unseen evidence.
All task files and separate primitive witnesses are fixed before either learner
runs. No witness or expected definition is passed to the normal solver.

The existing five A/L/F/B/C conditions remain, with one additional condition:
U uses the identical B archive and editing, but disables syntax caches.
The harness checks B/U equality of answers, program bodies, explored states,
arithmetic work and semantic rewrite traces. It records rather than assumes
any runtime improvement. It also retains B/C comparison, which isolates use of
learned semantic editing from mere interpreter optimization. A faster B than U
alone is not evidence of learning-induced capability growth.

The existing worker-ci.yml verification line runs this plan. It retains the
baseline 351 checks, q-directed acquisition/reuse/refusal, Theory checks, old
DSL loops, and prior expression/task regression. No duplicated workflow.

```bash
python -m pytest tests/test_theory_semantic_edit.py tests/test_theory_dsl.py \
  tests/test_theory_formation.py scripts/test_library_compression.py \
  scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_semantic_edit.py \
  --plan configs/theory-semantic-runtime-evaluation.json --output <fresh-output>
```

## Remaining capability issue

Correction to the first diagnosis: the actual definition budget is **8**, not
3. Only 3 definitions have been acquired, so five slots remain. Although
`Vocabulary.options()` counts archived rather than active definitions, this
limit is not the direct cause of the observed acquisition stop.

The observed block is the full **512-entry corpus**. `Vocabulary.record()`
rejects all new entries once this bound is reached. `last_learn_size` is also
512, and abstraction eligibility requires the corpus length to increase by the
configured interval (32). This condition can never become true again at that
bound. The final cycle-300 state and the source both confirm this condition.
New mathematical execution records continue to be archived elsewhere, but are
not inserted into the abstraction corpus. This is not evidence that refreshing
the corpus alone will produce capability; it identifies the next missing path
for testing cumulative learning. It is not changed in this cost experiment.
The long-term objective remains active; syntax speed is not its completion.
