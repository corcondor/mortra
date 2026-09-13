# Semantic editing: fresh shared-CI results

```text
cycle 14: acquired D0(u) = add(u, represented:R-b8f032907b167b70(word(A)))
  -> automatically discovered E-0ee03af3831c814e: D0(u) = u - F11
  -> QQ polynomial proof: all 24 states, 24 independent argument/state symbols
  -> cycle 18: D0(F22) rewritten to add(F22, neg(F11))
  -> executed: 0 representation calls, 0 matrix multiply-adds, 4 semantic nodes
  -> original-computation replay agrees; its costs are separately retained
  -> this executed expression occurs in D1's actual acquisition sources
cycle 20: acquired D1(u) = u - F11 from the equivalent corpus view
  -> cycle 26: acquired D2(u) = D1(F11 + u)
  -> automatically proved E-ceef534d5e1da6e4: D2(u) = u
  -> D2 remains archived, but is not an additional active search branch
```

The chain above is present in this run's `semantic-evidence.json`, not a proposed
example. D1 is a simpler implementation of D0, not a new mathematical function.
D2 is a projection theorem, not an additional nontrivial operation. Source
membership establishes actual use in abstraction, not counterfactual necessity.

**Outcome:** automatic definition analysis, certification, rewriting, and later
acquisition work. Fresh-task solved count does not improve. Editing reduces
candidate evaluations and measured arithmetic work, but its overhead increases
total query time against the identical archive with editing disabled.

## Identity and provenance

- Repository: `corcondor/mortra`.
- Branch: `codex/theory-formation-20260913`.
- Starting report commit: `004487f85197668c4b04745c22b59344afc2ceff`.
- Tested code: `d1e36278bd29f094ce98b73b57e058a6adcf054a`.
- Workflow file: existing `worker-ci.yml`, whose declared name is `Verify
  MORTRA Kernels`. GitHub's run UI reports `Verify MORTRA Worker Kernel`.
- Fresh [Actions run 34756044403](https://github.com/corcondor/mortra/actions/runs/34756044403): success.
- Job `103720468477`: 2026-09-13 12:03:25--12:14:00 UTC, 635 seconds.
- [Artifact 10317702389](https://github.com/corcondor/mortra/actions/runs/34756044403/artifacts/10317702389): `q-directed-34756044403-1`.
- ZIP digest: `8ef0f2a348b5dc0f0b28b9285cfe317200c291c7e545ea8f3c429f7002f961d0`.
- GitHub artifact expiry: 2026-10-13 12:13:50 UTC. This report persists in git.
- Local downloaded evidence: `C:/Users/81808/.openclaw/reports/dsl-edit-actions-34756044403/q-directed-34756044403-1`.
- All 411 JSON hashes listed in the semantic experiment manifest were checked
  again after download; zero mismatches. This checks integrity, not intervention
  absence or a separate proof kernel.
- Raw comparison-harness SHA-256:
  `ce932d272b1e4dda5aedc69a863ea7f7be25ebbf40ddf357bff18cec4899dc38`.
  The separate source seal uses the repository's normalized-source convention.

The Actions target, harness, and workflow all name the tested SHA. Python is
3.12.10 on Linux x86_64 (Ubuntu runner image `20260907.300.1`), SymPy 1.14.0,
python-flint 0.9.0, NumPy 1.26.4, pytest 8.4.1. Full versions are in
`environment.json` and `dependencies.txt`. No previous Windows success log is
used as evidence of this Actions result.

Cancelled run 34755531986 and failed run 34755677777 remain separate records.
Their causes and fixes are in `DSL-SEMANTIC-EDIT-20260913.md`. Neither reached
the new held-out evaluation. The final code and inputs were unchanged during
the successful run. No code or selection was tuned using its fresh results.

## Changes and reuse of existing machinery

| File | Change |
| --- | --- |
| `math_os_prototype/theory_semantic_edit.py` | Bounded equation discovery, symbolic argument certification, immutable dependencies, cost-directed concrete rewriting, active alias filtering |
| `math_os_prototype/theory_domain.py` | Independent symbolic sensors through the existing finite scalar interpreter; explicit finite/symbolic replay accounting |
| `math_os_prototype/theory_vocabulary.py` | Original and certified equivalent corpus views, equation persistence, later calls, syntax-only sizing, separately charged independent replay |
| `math_os_prototype/theory_formation.py` | Opt-in semantic editing on the normal learner |
| `scripts/run_theory_formation.py` | Normal-run editing and execution-mode options, source/config seals |
| `scripts/verify_theory_semantic_edit.py` | Pre-frozen cohorts, five-condition normal-entry comparison and raw evidence |
| `tests/test_theory_semantic_edit.py` | 15 semantic, scope, cost, provenance and domain-regression tests |
| `configs/theory-semantic-evaluation.json` | Fixed regression/fresh seeds and conditions |
| `.github/workflows/worker-ci.yml` | New checks on the existing verification line; prior checks retained |
| `docs/handoff/DSL-SEMANTIC-EDIT-20260913.md` | Protocol, scope, literature basis and separate failed runs |

The implementation reuses library anti-unification, shared argument holes,
instantiation, utility and syntactic expansion checks; the existing typed
planner; exact space/certificate materialization; and the Domain interpreter.
The polynomial identity test and QQ linear solve are generic initial knowledge.
The definition bodies and equations listed here are runtime acquisitions.

[babble section 4.1](https://cnandi.com/docs/babble23-cr.pdf) informed the
separation between semantic equivalence and definitional expansion. This
implementation searches two bounded corpus views, not a full e-graph. It keeps
the original view and syntactic round-trip checks, plus separate equation
evidence. It does not assume shortest individual normal forms give the best
library. Cost estimates are cold arithmetic estimates, not guaranteed wall-time
optima; original definitions and alternative implementations remain stored.

## Fresh verification

The same Actions run passed:

- Existing 351 baseline tests; normal q-directed acquisition, stored reuse,
  collision-free refusal, and reuse-only refusal.
- 22 Theory tests and the retained normal experiments.
- 105 DSL/library tests, including 15 new tests, in 7.86 seconds.
- Existing 48-expression regression for both ring and fold domains: acquisition,
  later execution and next acquisition remain true; held-out net description
  reduction remains false and solved gain remains zero.
- Existing 48-task synthesis regression, retained separately.
- The new five-condition comparison, 261.559 seconds including both training
  runs and all four query cohorts.

The test groups overlap; do not add them as a unique total. Locally, the combined
focused command below passed 127 tests before the final push. That local result
is separate from the fresh Linux evidence above.

```bash
python -m pytest tests/test_theory_semantic_edit.py tests/test_theory_dsl.py \
  tests/test_theory_formation.py scripts/test_library_compression.py \
  scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_semantic_edit.py --output <fresh-directory>
```

Every spawned normal-entry command is stored as an argument array in
`dsl-semantic-edit/verification.json`. There are four training commands and
20 query commands. The training pattern is the following; `old` omits
`--semantic-edits`, and both conditions resume at the same halfway point:

```bash
python scripts/run_theory_formation.py --config <output>/config.json \
  --output <output>/edited-first --semantic-edits --cycles 150
python scripts/run_theory_formation.py --config <output>/config.json \
  --output <output>/edited-resumed --semantic-edits \
  --resume <output>/edited-first/state.json
python scripts/run_theory_formation.py --config <output>/config.json \
  --output <output>/918041-B-edited --execution-mode edited \
  --queries <output>/challenge-918041.json \
  --knowledge <output>/edited-resumed/state.json
```

The config, not a target definition, determines the final 300-cycle budget.
Full exact paths, source seals and independent witnesses are in the artifact.
To repeat the shared verification on this code:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra \
  --ref codex/theory-formation-20260913 \
  -f verification_suite=dsl-feedback \
  -f target_ref=d1e36278bd29f094ce98b73b57e058a6adcf054a \
  -f expected_sha=d1e36278bd29f094ce98b73b57e058a6adcf054a
```

## Acquired equations and subsequent use

D0 is `6e03302e5fc8a62d`, D1 is `85edc08a9734f568`, D2 is
`e0db91f1ebe4cd64`. `semantic-evidence.json` records 3 certified relations,
including 1 projection, 16 rewritten training executions, and 1 definition
acquired using the equivalent corpus view. All 16 rewritten executions omit
represented calls. Original replay is retained separately.

The report has 12 execution-to-next-acquisition records: 12 executed corpus
expressions match D1's actual abstraction sources. This means **one** later
definition uses these experiences, not 12 different new definitions. D1 has
16 matched sources in total: four prior expressions rewritten using the
equation and twelve already-edited execution results. The concrete cycle-18
F22 expression is among those twelve. This is distinct from merely sharing an
equation ID. It is not evidence that removing any single source prevents D1.

The argument proof quantifies each parameter at every declared state
independently. It is exact QQ polynomial equality in this complete 24-state
model, not equality only at F22 or on sampled arguments. Non-scalar arguments
and non-finite domains are unsupported by this new certificate and remain
unchanged. Legality, histories and collisions are not represented. Trusted
components include the interpreter, substitution, and SymPy; hashes do not
constitute an independent proof-kernel certificate.

## Training costs

Both runs use the same initial config, seed and 300-cycle budget. Times below
are measured seconds; acquisition subphase times are nested in the totals and
must not be added to them a second time.

| Measure | Old learner | Editing learner |
| --- | ---: | ---: |
| Training process total, including resume/load | 12.012 | 12.060 |
| Recorded learner total | 8.889 | 9.030 |
| Library acquisition | 1.145 | 1.492 |
| Equation discovery, excluding its certification | 0 | 0.149 |
| Equation certification | 0 | 0.110 |
| Execution rewrite selection | 0.001 | 0.054 |
| Independent original DSL replay | 0.778 | 0.737 |
| DSL execution | 1.332 | 1.225 |
| Definitions / maximum dependency depth | 3 / 2 | 3 / 2 |
| DSL execution records | 2184 | 2092 |

The editing run records 44 candidate relation checks, 1032 statewise polynomial
identity checks and 3 exact linear solves. Full operation and phase counters,
including the pre-existing closure and recurrence proofs, are in
`acquisition.*.costs`. Operation counts are not bit complexity. Source parsing,
library loading, integrity checking and interpreter overhead remain in process
wall time. Training is not free and this run does not show faster acquisition.

## Frozen fresh-task comparison

Seeds 918041 and 918042 each produce 24 tasks before either learner runs.
These tasks are distinct from developer-seen regression seeds 917334/917335.
They specify desired values, not answer programs or required learned definitions.
All tasks have independent initial-DSL witnesses kept outside solver input.
Each task has the same 512-state and 1,000,000-work budget in every condition.
Syntax limits were nonbinding in all conditions; no size refusals occurred.

- A: initial DSL, no acquisitions.
- L: old learner archive and old redundant pre-evaluation computation.
- F: the same old archive with that duplicate computation removed.
- B: editing learner archive, certified edits and active alias filtering.
- C: the identical B archive with only edit use/filtering disabled.

The following sums cover all 48 fresh tasks, including unsuccessful searches.
Candidate evaluations exclude six initial seed states per task. Query time
includes matching, expansion, execution, editing and independent answer replay.
Process time additionally includes launch, archive load and validation.

| Condition | Solved / 48 | Evaluated candidates | Explored states | Query seconds | Process seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 28 | 12092 | 12380 | 7.411 | 8.901 |
| L | 27 | 13245 | 13533 | 20.644 | 25.294 |
| F | 27 | 13245 | 13533 | 20.558 | 25.244 |
| B | 27 | 13084 | 13372 | 20.546 | 25.243 |
| C | 27 | 13244 | 13532 | 19.703 | 24.343 |

**B does not solve any task that C fails; neither does C solve one that B
fails.** B evaluates 160 fewer candidates, but query time increases by 0.842
seconds and process time by 0.900 seconds. These are single runs, not a
statistically established speedup or slowdown estimate. No timing-based
selection was changed after evaluation.

Across the 27 tasks solved by every condition, B explores 2620 states versus
C's 2780, with 6.655 versus 6.680 query seconds. This small common-task timing
difference does not overturn the full-cohort negative timing result.

After measurement, exact target-value comparison against both training archives
classifies 28/48 targets as semantically unseen. A solves 8/28; L/F/B/C each
solve 7/28. The other 20 targets overlap some training value, even though their
task files were fixed independently. No subset was selected or tuned using
this classification. There is no demonstrated generalization gain here.

## Work removal and description costs

| Condition | Normal work units | Independent replay units | Active library + solved programs, bits | Stored library + solved programs, bits |
| --- | ---: | ---: | ---: | ---: |
| A | 1215722 | 1444 | 13640 | 13736 |
| L | 1297701 | 1546 | 503472 | 503496 |
| F | 1194907 | 1546 | 503472 | 503496 |
| B | 1152679 | 1546 | 553632 | 553632 |
| C | 1213908 | 1546 | 503136 | 553376 |

Library cost is charged once across the two cohorts, not twice. Program bits
include solved programs only, so A's additional solved task must be considered
when comparing A with learned conditions. The stored column counts the complete
archive even in C, where equations are not active. B and C retain the same
539512-bit library; B's solved program bodies total 14120 bits versus C's
13864. Equation evidence costs 50240 bits. This is not net compression.

L to F removes 930 measured original recurrence action steps from the query
path while preserving answers and independent replay. Normal work drops by
102794 units. The size check no longer executes the recurrence. The dedicated
101-step regression also verifies zero original action steps during sizing and
certified execution, and 101 steps during deliberately independent replay.
This is not a claim that all original computations vanish from the experiment:
training and answer audits still replay and are separately charged.

B performs 564 certified query rewrites, with 1692 equation matching checks
and 1.265 seconds of edit selection. Representation calls drop from C's 3047
to B's 2475; macro expansions drop from 3667 to 1129. Active definition
branches drop from 3 to 1 without deleting archived implementations. Normal
work drops by 61229 units, but these savings do not offset total overhead.
All 48 queries in each learned condition have zero acquisition/prover calls,
unchanged archives and separately recorded final-answer checks.

## Regression and limits

The developer-seen 48 synthesis tasks remain separate: A solves 20/48 and
L/F/B/C each solve 18/48. B versus C evaluates 17557 versus 17731 candidates,
but takes 29.711 versus 27.855 process seconds. No B/C solved gains or losses
occur. The old 48-expression checks are still checks of evaluation/compression,
not unseen program synthesis evidence.

The implemented improvement is **certified self-editing of acquired procedures**,
including later use and abstraction. It is not a demonstrated increase in
held-out solving ability. The remaining overhead and unchanged/worse solved
counts stay recorded. The comparison does not isolate editing from alias
branch filtering inside B; they are the declared combined intervention.

The previously unused fold-structure definitions remain unused. Frame
representations and recurrence execution are not relabelled as panel-structure
use. No physical collision, general origami, modular-form, or new-formula
capability is claimed. No new solver, hand-authored target equation, expected
definition, or held-out answer was supplied during these runs.
