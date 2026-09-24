# MORTRA Future-Equivalence Refinement Core — Codex Handoff

## What changed from the failed BIC implementation

The previous `PredictiveMDLSymbolizer` optimized a local regression/compression
criterion.  This replacement does **not** use BIC, MSE, a symbol-count penalty,
or a one-step predictive clustering objective.

It implements the design we actually wanted:

1. **OLD's strong mechanism is preserved**
   - start from current-observation states;
   - when the same abstract state and same action produce different abstract
     successors, that is a counterexample;
   - split only in response to such a counterexample.

2. **No fixed history horizon**
   - exact observed histories are stored in a persistent parent-pointer DAG;
   - for each contradiction, the shortest history suffix that distinguishes the
     witness histories is selected;
   - there is no `max_depth=6`, `H`, or other fixed cap.

3. **Multi-step future distinctions propagate backward**
   - if a downstream state splits because an action reveals a difference, its
     predecessors can then acquire different successor abstract states;
   - the contradiction therefore propagates backward one action at a time;
   - the included test verifies `b` splits first and then upstream action `a`
     splits.

4. **UNKNOWN is not equivalence**
   - missing action rows are absent;
   - incomplete states cannot merge merely because they have the same missing
     actions;
   - partial empirical pair relations are exactly:
     `DIFFERENT`, `EQUIVALENT`, `UNKNOWN`.

5. **Merge requires an exact certificate**
   - only states with all action rows observed are merge-eligible;
   - observation labels must match;
   - exact rational action-conditioned successor distributions must match under
     fixed-point partition refinement;
   - `eps_action` must be exactly zero.

6. **Belief is recursive**
   - belief update runs on the learned quotient graph;
   - an unobserved action propagates the explicit `UNKNOWN` marker;
   - full-history reconstruction uses exactly the same recursion, so it can be
     tested against incremental belief update.

7. **No task objective in the world-state core**
   - no goal
   - no reward
   - no q
   - no discount
   - no fixed planning horizon

## Files

- `future_refinement_core.py`
  New state/world-model core.
- `tests/exact_moore_oracle.py`
  Independent exact Moore oracle.
- `tests/microbench_fixtures.py`
  Hand-auditable 0/1/2/3-step, cycle, cue, delayed-bit fixtures.
- `tests/test_exact_moore_oracle.py`
  Independent oracle validation.
- `tests/test_future_refinement_core.py`
  New-core validation.

## Validation already completed

Run:

```bash
PYTHONPATH=.:tests python -m pytest -q \
  tests/test_exact_moore_oracle.py \
  tests/test_future_refinement_core.py
```

Observed result:

```text
26 passed
```

The validation includes:

- all 5,832 labelled deterministic Moore machines with
  3 states / 2 actions / 2 outputs;
- exact agreement of the new conservative quotient with the independent oracle
  on all 5,832 complete machines;
- a required history distinction deeper than 6 steps;
- multi-step backward counterexample propagation;
- incomplete rows remain UNKNOWN and do not merge;
- fully observed equivalent states do merge;
- explicit shortest observed distinguishing words;
- recursive belief equals full-history reconstruction;
- missing transitions propagate explicit UNKNOWN.

## Integration instructions

Do **not** rewrite OLD planning or the game generator first.

### Stage 0
Use this core exactly as supplied on tiny finite systems.

### Stage 1
Adapter only:
- replace OLD `HistoryModel` state-construction calls with
  `FutureRefinementCore`;
- keep the same external observation symbols and actions;
- keep OLD reasoner unchanged for the first A/B comparison;
- do not introduce raw pixels yet.

This isolates state construction.

### Stage 2
Run the small development tournament:
- OLD state core + OLD reasoner
- FutureRefinementCore + SAME OLD reasoner

Same generated game seeds, same action budget, same game edit budget.

Only if Stage 1/2 do not collapse should we move to larger benchmarks.

### Stage 3
Then test the new belief/reachability reasoner separately.

## Important limitation

This module starts from **hashable observation symbols**.  It is the replacement
for the world-state/history layer, not yet a universal raw-image front end.

That separation is intentional.  The earlier failure mixed sensory compression
with state construction and destroyed useful distinctions before the world
model could recover them.

For the first valid experiment, keep OLD's existing observation interface and
change only the state-construction core.

## Complexity of this reference implementation

Let:
- T = number of unique observed history-prefix nodes,
- A = number of actions,
- R = number of accepted refinement rules,
- D = largest selected history depth.

Persistent history storage itself is O(T).

Suffixes are built only when needed and cached.  The transparent reference
`rebuild()` rescans empirical transitions and witness pairs after each split.
Its worst case is deliberately not claimed to be production-optimal; adversarial
data can make witness-pair search super-quadratic.

This is acceptable for Stage-0/Stage-1 microbenchmarks.  Do not optimize it
before we know that the state semantics are correct.

After semantic validation, optimize by:
- indexing witness groups;
- memoizing pairwise distinguishing depth;
- incremental refinement rather than whole-graph rebuild.

Any optimization must preserve:
- every selected split depth,
- final leaf assignments,
- certified quotient partition,
- UNKNOWN/DIFFERENT/EQUIVALENT answers,
- belief updates.

## Do not do

- no BIC
- no MSE-based merge
- no fixed max history depth
- no majority-successor imputation
- no self-loop imputation for unknown actions
- no goal-aware state construction
- no changing OLD at the same time
- no 100-environment / raw-visual run before small A/B passes
