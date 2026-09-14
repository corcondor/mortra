# Geometry candidate truncation: diagnosis and revalidation

## Withdrawn interpretation

The previous 8/16 solve result does not assess the complete declared candidate
space. The previous statement about fair exploration was insufficient: only
the surviving candidate prefix was fairly scheduled. This document replaces
that interpretation. No conclusion about MORTRA's underlying principle follows.

The recorded functions were connected: on the second regression task the old
A/C trace executes midpoint, mirror, foot; B/D executes foot first. On the
ninth task C executes 37 acquired constructions and D executes 44. The defect
is not a wholly disconnected toggle. It is that useful bindings can be removed
before either selector sees them.

## Origin and affected stages

The first geometry semantic-feedback configuration was added by
`a6bd74fcb65b473d96cb6ce7085516d51f7b0c55`. It already contained
`per_family_limit: 3` and `max_input_tuples: 128`. No mathematical justification
for those numbers is recorded in that change. They are engineering search
limits, not consequences of geometric type, precondition, or proof.

The eight-cycle configuration at `023cedd` inherited them. The factorial
configuration at `b07d911` inherited them again. Therefore both the experience
used to acquire the library and the evaluation of its usefulness are affected.
Repeating only the final evaluation would not correct the acquisition sample.

Old path:

1. `SemanticGeometryDomain.candidate_rows` calls the existing typed enumerator.
2. `_bounded_family_points` can remove points for high-arity constructions.
3. `_family_inputs` enumerates arguments modulo the declared primitive symmetry.
4. The enumerator stops after 128 tuples, including guard failures.
5. Structural ordering and `_role_balanced_prefix` retain at most 3 candidates.
6. `SelectionDomain.proposals` ranks that retained prefix only.
7. The planner interleaves families, but its old argument stream can drain an
   older state's candidates before using newly produced states.

Increasing only the application budget cannot recover a binding permanently
excluded from a fixed state's prefix. Finding 0 witnesses in the old wider
diagnostic is therefore not evidence of absence from the full language.

## Inventory audit

`scripts/audit_geometry_execution.py` aggregates the full previous event file,
not a selected successful trace. `reports/geometry-prefix-audit/inventory.md`
lists all 7 primitives and 16 acquired definitions across all 10 cohort/arm
groups. `audit.json` includes their bodies, parameters, generations, dependency
references, contracts, proposals, executions, and refusal types.

The seven primitives are midpoint, mirror, foot, circle (a circumcenter Point),
orthocenter, reflect, and intersection_ll. In successful constructions the old
log records consumed `diff`, `ncoll`, and `npara` premises. Acquired contracts
also carry coll, cong, midp, and perp effects. The goals additionally query
cyclic. The old log does NOT contain every failed predicate request. Its missing
requests cannot be reconstructed from success totals; the audit explicitly
marks that limitation. The corrected run logs every request and its outcome.

## Correction, not a new geometric solver

- `iter_complete_typed_candidates` uses the existing declared family symmetries
  but does not apply a point subset, tuple prefix, or candidate-count cutoff.
  Types do not imply applicability: existing exact guards still reject
  degenerate bindings, and the existing executor and replay remain authoritative.
- Geometry's default is `candidate_enumeration: complete`. The obsolete prefix
  limits are removed from all three current geometry experiment configs. The
  older bounded enumerator remains available to unrelated callers and explicit
  `legacy_prefix` reproduction; it is not the new normal-run default.
- The shared planner keeps an iterator for each unary state-action pair and
  interleaves retained states as well as operations. A new state's iterator
  enters the next round, without waiting for older streams to be exhausted.
  The feature is opt-in for unary action adapters; other planner uses retain
  their prior behavior.
- Selection buffers 16 eligible candidates at a time. This is a bounded ranking
  window, not a total candidate limit: every candidate in a page is offered,
  and the next page is then read from the same retained iterator. All four
  selection arms use the same window size. Every fourth round retains original
  order. Ranking still cannot certify a fact or bypass applicability.
- Complete tuple scans record the family, state, ordinal, arguments, and either
  eligibility or a proved-false input guard. Predicate calls record source,
  arguments, and outcome. Event aggregation never feeds back into selection.

Remaining limits are explicit resource/representation conditions: 112 attempted
applications per primary task/window, 6000 primitive operations, 600 seconds per
search window, depth 6000, and 100000 total tuple guard checks per domain lifetime.
The diagnostic uses its already declared 448 applications and 24000 primitive
operations. Hitting a limit means pending work, not mathematical impossibility.
The new guard-check budget is global, not a prefix restriction separately
reapplied to every operation and state.

These iterators are retained during a search. Subsequent calls on the same
domain re-enumerate and skip completed attempts using the existing attempt set.
This is not a newly implemented cross-process checkpoint facility. General
typed languages with non-unary state actions are outside this scheduling change.

Acquisition retains its existing budgets: 3000 abstraction pairs, 4 parameters,
4 expanded primitive steps per candidate definition, 2 certifications/admissions
per cycle, and corpus capacity 512. They are reported, not claimed to establish
unbounded concept formation. No new solver, axiom, target lemma, or target
definition was added.

## Frozen rerun

`configs/theory-geometry-complete-revalidation.json` starts from the initial DSL.
The existing 8-cycle A/B/C/E acquisition and D inactive control are rerun using
the old fixed tasks, seeds and application budgets, with complete enumeration.
The resulting C archive, of whatever size the run actually produces, is passed
automatically to the 2x2 selector comparison in the SAME normal invocation.
The old 16-definition archive is not loaded.

The existing regression tasks, coordinate-generation seed and later bounded
diagnostic are retained. All are now regression data: no new unseen-family
generalization claim is allowed. Both stage configurations are materialized
before acquisition. Later choices are produced by fixed code, not supplied by
the developer after viewing results.

```
PYTHONHASHSEED=0 python scripts/run_theory_formation.py --config configs/theory-geometry-complete-revalidation.json --output reports/semantic-feedback-normal
```

The existing Actions workflow defaults to this invocation. No extra workflow,
main merge, force push, or external solver replacement is involved.

## Development verification

Artificial tests check every declared symmetry tuple for all seven families,
all 32768 tuples of an eight-point, five-argument repeated-input schema, page
continuation, execution after the former third candidate, global-budget stops,
fair use of a child before its parent's long stream is exhausted, and repeated
search calls without reexecuting completed calls. These are infrastructure
tests, not MORTRA discoveries.

Initial focused run: 43 passed in 61.38 s. Related regression run:

```
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_complete_enumeration.py tests/test_geometry_selection.py math_os_prototype/test_runtime_typed_planner.py tests/test_geometry_semantic_feedback.py tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py scripts/test_library_compression.py worker/backend/test_typed_geometry_stalk.py --junitxml=reports/complete-enumeration-regression-v1.xml
```

Result: 226 passed, 1 skipped in 128.32 s. The skip is unchanged. Test XMLs
and the source-level inventory are separate from the forthcoming frozen run.
Passing tests do not establish that removing the prefixes improves solving.

## Fresh run result

Pending execution on the committed source. Do not reuse the old 8/16 figures
as the result of this revision.
