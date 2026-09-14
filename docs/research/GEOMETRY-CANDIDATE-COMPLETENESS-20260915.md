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
marks that limitation. The corrected run logs requests through the domain's
`prove` entrypoint and their outcomes. Recursive nondegeneracy subchecks inside
`certify_atom` are not separate trace events; successful certificates retain
their prerequisite trees. Failed internal subchecks are not individually traced.

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
  eligibility or a proved-false input guard. Domain-level predicate calls record
  source, arguments, and outcome. Event aggregation never feeds back into selection.

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

The frozen source is `f966f3efa4004be1b817c5fe08a412a86357f8e5` on
`codex/geometry-semantic-feedback-20260915` in `corcondor/mortra`.
[Actions run 34908552962](https://github.com/corcondor/mortra/actions/runs/34908552962)
completed successfully. The geometry job took 18m35s. Its related suite passed
226 tests with 1 unchanged skip in 30.66s; the separate exact-kernel job passed
64 tests in 1.42s. This is fresh Linux evidence, not the development XML.
The environment was Python 3.12.14, Linux 6.17.0-1022-azure, glibc 2.39.
`environment.json` records all installed versions.

The normal invocation above completed both stages. Source seals and stage
configuration hashes were unchanged. `old_library_loaded` is false. Acquisition
took 629.482s and selection took 396.367s, including their respective output
costs. The raw counters distinguish candidate guards, certificate checks,
execution, expansion, primitive replay, and output costs. These overlapping
timing counters must not be added to each other as independent time savings.

### Candidate coverage actually observed

The C training trajectory successfully executed 10 distinct bindings of `mirror`
from the same initial state, including `(d,a)`. In C training, 152 state/family
pairs had more than 3 successful bindings across the eight continuing windows.
Each success has a primitive replay. This demonstrates that subsequent windows
can use the portion formerly discarded; it is not just a generator unit test.

The short evaluation must be reported separately. In the factorial run, the
maximum distinct bindings actually executed per task/state/family were A=3,
B=2, C=2, D=2. Even the wider diagnostic reached at most 3. This is NOT a new
hard cutoff: the retained streams and the training continuation above contradict
that interpretation. The number of state/action streams expands rapidly, so
the fixed application budget is spent before most individual streams progress.
Removing permanent exclusion has not solved budget allocation. It would be
misleading to describe this run as exhaustively evaluating all legal bindings.

The selector stage recorded 719438 tuple scans, 33508 ranking pages, 15092
selected executions, and 187488 domain-level predicate requests, including
failed requests. Internal recursive subchecks are excluded from that event count.
There were 64 cross-arm membership checks and zero mismatches. Scanned tuples,
ranked candidates and executed constructions are different counts.
The scan ordinals reached 85 (zero-based) in the wider diagnostic; this normal
run did not itself need the former 128-tuple boundary. The artificial 32768-tuple
test verifies continuation beyond that separate boundary.

### Acquisition rerun

The acquisition-stage condition labels are defined independently of the later
factorial labels: A is initial DSL, B learns only at cycle 0, C allows recursive
learning, D uses C's saved state with acquired roots inactive, and E flattens
acquired calls before learning.

| Acquisition condition | Archived definitions | Highest generation | Solved / 16 | Evaluation seconds |
|---|---:|---:|---:|---:|
| A | 0 | 0 | 8 | 19.530 |
| B | 2 | 1 | 8 | 16.110 |
| C | 16 | 1 | 6 | 29.712 |
| D | 16, inactive | 1 | 8 | 19.846 |
| E | 16 | 1 | 6 | 29.242 |

C acquired two definitions per cycle, but no accepted definition has an acquired
parent. Thus recursive acquisition did not reoccur in this corrected eight-cycle
trajectory. The earlier generation-2 observation belongs to the different,
prefix-limited trajectory and is not a result of this run. The recursion code
was not disabled. Learning still uses its declared 3000-pair and two-admission
budgets. Its input sample reached 512 entries at cycle 2 (zero-based).

### Fixed-library factorial rerun

These are the 16 definitions produced by this invocation, not the previous
16-definition archive. A/B use primitives only; C/D enable the new archive.
A/C use original ordering; B/D use contract-guided soft ordering. Each task
has the same 112-application and 6000-primitive-operation limits.

| Condition | Regression solved / 16 | Applications | Total task seconds | Changed-coordinate solved / 16 | Total task seconds |
|---|---:|---:|---:|---:|---:|
| A | 8 | 1014 | 19.419 | 8 | 19.437 |
| B | 8 | 904 | 16.767 | 8 | 17.153 |
| C | 6 | 1140 | 30.240 | 6 | 31.024 |
| D | 8 | 904 | 27.610 | 8 | 27.949 |

C/D executed acquired constructions 20/47 times on the regression set and
20/48 times on changed coordinates. Nevertheless, every solved task's acquired
ancestor count is zero. D's gain over C recovers two tasks that A and B already
solve. The solve interaction is +2, but this is not a solve beyond the initial
DSL and does not establish beneficial acquired-morphism use. D is also slower
than B. None of the eight tasks unsolved by A was solved in the 448-application
diagnostic (16 arm/task runs). This remains a budgeted non-result, not a proof
of nonexpressibility or of MORTRA's principle failing.

### Evidence and analysis

[The Actions artifact](https://github.com/corcondor/mortra/actions/runs/34908552962/artifacts/10374072207)
has ID `10374072207`, 61275536 bytes and service-reported SHA256
`30ac5e43b17c2c63768be81f876a5d54182cd8c299dad9aa4e9d674f67d49b63`.
Its extracted contents were also repackaged as
`reports/geometry-complete-revalidation-evidence.zip`, SHA256
`e6c68d83bb9e225dd459dc21d512ca8fd04b88cba25f71f475380bb0ab367f52`.
The package is not byte-identical to the service ZIP; it preserves the extracted
files. All 45 extracted files (1371033154 uncompressed bytes) were hash-compared
against the repackaged ZIP; `package-verification.json` records the check.
`reports/complete-enumeration-actions-34908552962.log` is the fresh
Actions log. `reports/complete-enumeration-artifact-metadata.json` preserves the
service metadata.

`reports/geometry-complete-audit/` contains the copied verification, environment,
frozen stage inputs and library provenance, plus read-only event aggregation.
The acquisition inventory covers all 25 registered operations across the
different archives; the selection inventory covers all 7 primitives and all
16 newly acquired operations. Zero-use operations remain in the inventory.
Failed predicate checks and refusal reasons are retained in the JSON summaries.
Conditional construction effects that fail their geometric nondegeneracy check
are not published as facts.

The read-only inventory commands were:

```
.venv/Scripts/python.exe scripts/audit_geometry_execution.py --run reports/complete-enumeration-actions-34908552962/semantic-geometry-f966f3efa4004be1b817c5fe08a412a86357f8e5-34908552962/semantic-feedback-normal/acquisition --output reports/geometry-complete-audit/acquisition
.venv/Scripts/python.exe scripts/audit_geometry_execution.py --run reports/complete-enumeration-actions-34908552962/semantic-geometry-f966f3efa4004be1b817c5fe08a412a86357f8e5-34908552962/semantic-feedback-normal/selection --output reports/geometry-complete-audit/selection
```

`executed-bindings.json` groups `selected_execution` records by cohort, arm,
task index, state and family and counts distinct input tuples.
`acquisition-executed-bindings.json` groups successful `certified_history`
records by stage, condition, task SHA, certificate source parent and family.
The parent is read from the output point's certificate, not guessed from term
syntax. These files are post-run analysis, never inputs to acquisition/selection.

Conclusion: the arbitrary candidate-prefix defect is corrected and continuing
training actually uses later bindings. Effective search coverage remains poor
under the fixed budget, and a learned-library capability gain is not established.
No results were added by hand and no solver/parser/proof rules were changed.
Old records have not been deleted; their full-space interpretations are marked
withdrawn rather than silently replaced by these fresh numbers.
