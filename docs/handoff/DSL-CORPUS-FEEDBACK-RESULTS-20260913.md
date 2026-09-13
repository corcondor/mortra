# Fixed-capacity feedback: shared-CI results

## Verdict

The bounded sample now refreshes and re-enters abstraction after becoming full.
No new DSL definition or DSL semantic relation was acquired from those later
abstraction attempts. No additional evaluation task was solved by FIFO refresh.
Costs increased. Thus the infrastructure repair passed, but continued useful
DSL growth and downstream capability improvement did not pass this experiment.

These are fresh Linux Actions results, not substituted Windows results.

## Reproducible identity

- Repository: `corcondor/mortra`.
- Branch: `codex/theory-formation-20260913`.
- Baseline code: `76bf26b065df6c512bbf897f82afbf5e11fae988`.
- Tested code: `7b37ea25ac174c5f860e33e73d9f0519bf5b3da2`.
- Workflow: `.github/workflows/worker-ci.yml`, job `q-directed-verification`.
- [Actions run 34760174353](https://github.com/corcondor/mortra/actions/runs/34760174353),
  attempt 1, job 103731507979, success.
- Job interval: 2026-09-13 13:33:33 to 13:58:38 UTC; 25m05s.
- [Artifact 10318464775](https://github.com/corcondor/mortra/actions/runs/34760174353/artifacts/10318464775),
  `q-directed-34760174353-1`, 233,021,850 bytes, 30-day retention.
- GitHub-reported artifact digest:
  `sha256:7091d7663623ebfbdb0139a8a1bd045f14ceb40c808000525b9886aaae0e49b2`.

The harness, target and workflow SHA all equal the tested code above. The
normal-run source seals stayed unchanged. A later documentation-only commit
does not replace this tested-code identity.

Runtime: Python 3.12.10, Linux x86_64, kernel 6.17.0-1022-azure, glibc 2.39,
runner image 20260907.300.1. Declared dependencies installed successfully:
SymPy 1.14.0, NumPy 1.26.4, pytest 8.4.1, python-flint 0.9.0, mpmath 1.3.0;
the complete installed list is in `environment.json`. No new dependency was
introduced for this repair.

Full commands, configs, source seals, per-task outputs and file hashes are in
`dsl-corpus-feedback/verification.json`. Its `passed: true` means reproduction,
scope, resource and isolation checks passed, not that learning improved.

## Tests and preserved checks

- Relevant q-directed suite: 351 passed, 0 failed, 0 skipped.
- Theory guards: 22 passed.
- DSL, semantic editing, corpus and library suite: 121 passed, including the
  10 new boundary fixtures. Counts describe separate invocations, not a claimed
  total of unique tests across all historical suites.
- q-directed normal acquisition, stored reuse and both collision-free refusal
  paths passed. The stored reuse still performs zero reacquisition and zero
  task-prover calls in its permitted scope.
- Existing DSL acquisition / reuse regression and fixed value-goal synthesis
  checks passed before the new comparison.
- All evaluation archives remained unchanged. Their acquisition/prover call
  counters are zero; independent mathematical replay is separately charged.
- Capacity, duplicate handling, empty-attempt consumption, re-eligibility,
  retained proof sources and deterministic save/resume passed. Fixtures are
  development tests, not autonomous mathematical discoveries.

## Fixed inputs

See [the protocol](DSL-CORPUS-FEEDBACK-20260913.md) and
`configs/theory-corpus-feedback-evaluation.json`. Both training conditions use
the same `theory-dsl-fold.json`, seed 20260913, capacity 512, interval 32,
300-cycle / 300-second bounds and semantic-edit/cache settings. Each starts
normally for 150 cycles and resumes to 300. Both stopped at the cycle budget.

`O` freezes the first 512 admissions. `B` uses FIFO. `A` is initial knowledge.
`T` is the FIFO 150-cycle checkpoint. `C` disables only semantic editing in B's
archive. `D` disables only learned-definition operations in that same archive.
No definitions, equations or auxiliary quantities were inserted during runs.
All 96 specifications were frozen before either normal learner started.

## What happened after the sample filled

| Measured quantity | Frozen O | FIFO B |
| --- | ---: | ---: |
| Cycle when sample first reached 512 | 42 | 42 |
| Final active sample | 512 | 512 |
| Unique executed programs observed | 2,160 | 20,604 |
| Admissions after first 512 | 0 | 20,092 |
| Capacity refusals | 1,648 | 0 |
| Duplicate dispositions | 34 | 1 |
| Abstraction attempts after capacity | 0 | 59 |
| Candidate offers in those attempts | 0 | 1,602 |
| Candidates reaching detailed evaluation in those attempts | 0 | 0 |
| Definitions acquired by those attempts | 0 | 0 |
| Total learned definitions / DSL semantic relations | 3 / 3 | 3 / 3 |
| Maximum learned-definition dependency depth | 2 | 2 |
| Existing DSL executed-program records | 2,092 | 20,536 |

The first full-sample journal entry has sequence 512, execution index 488,
cycle 42, version 515 and ID
`4a081268fecaa5b00682cf69f21452de9d0efe985d190904012f1b33defa6e0c`.
Version exceeds arrivals by three because three equivalent learner edits are
content changes, not additional experience.

FIFO's next abstraction ran at cycle 44, input version 594. It consumed a
512-row sample containing 79 post-capacity source IDs; it offered 13 candidates,
evaluated zero and accepted none. Every later attempt has its consumed input
IDs and outcome recorded. `post_capacity_chains` is empty: there is no acquired
definition from that material to connect to a subsequent call.

```text
cycle 42: sample = 512
  -> 20,092 later admissions, with FIFO retirement records
  -> 59 later abstraction attempts using refreshed samples
  -> 1,602 offers, 0 detailed evaluations, 0 accepted definitions
  -> no witnessed post-capacity acquisition-to-later-use edge
```

Candidate selection is now the observed stopping point, not the sample's
admission ceiling. Development V1/V2 showed candidate rejection by the
existing compositional contract. No corpus prefilter, new candidate strategy,
special definition, or changed admission criterion was added to obtain success.
The CI record directly confirms the zero detailed evaluations above.

## The established semantic chain still works

The following is from the fresh CI `ascii.txt` and `semantic-evidence.json`.
It occurred before capacity, so it is preservation of an established capability,
not evidence for continued learning after cycle 42.

```text
D0 [6e03302e5fc8a62d]: u + represented(R-b8f032907b167b70, word(A))
  -> E-0ee03af3831c814e: D0(u) = u - F11
  -> all_states_symbolic_polynomial_identity over QQ
     24 states, 24 independent argument/state symbols
  -> cycle 18: D0(F22) rewritten to F22 - F11
  -> 0 represented calls, 4 semantic nodes; independent replay retained
  -> one later acquisition uses this execution
```

Three definitions, three relations, 16 rewritten executions and one
equivalent-view acquisition remained. Twelve source-to-acquisition edges do
not mean twelve distinct acquired definitions. The scope is the declared
finite frame model; panel structure, collisions and physical fold legality
are not represented. Structural folding definitions remain unused.

## Evaluation

Regression uses seeds 917334/917335 (48 tasks). Fresh frozen evaluation uses
918061/918062 (48 tasks), not inspected for development tuning. The fresh
subset whose value functions were also unseen in training contains 32 tasks.

| Condition | Regression solved / 48 | Fresh solved / 48 | Semantically unseen fresh solved / 32 |
| --- | ---: | ---: | ---: |
| A initial | 20 | 23 | 7 |
| O frozen sample | 18 | 21 | 5 |
| T FIFO checkpoint | 18 | 21 | 5 |
| B FIFO final | 18 | 21 | 5 |
| C same archive, editing disabled | 18 | 21 | 5 |
| D same archive, learned-definition calls disabled | 18 | 21 | 5 |

O-to-B newly solved tasks: **0**; newly lost tasks: **0**, on both cohorts.
The identical-archive ablations passed their isolation checks. Initial DSL
size bounds were nonbinding. Every condition's median search count was 512,
the shared state budget; this median does not distinguish their costs.

Fresh 48-task cost totals below charge the stored active library once per
condition, not once for each 24-task seed. Definition and certificate storage
are included. An unsolved task has no solution-program bits.

| Condition | Candidate expansions | Normal interpreter work | Query seconds | Full process seconds | Program + active library bits |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 15,418 | 1,537,400 | 6.322 | 8.147 | 12,520 |
| O | 15,883 | 1,388,148 | 21.441 | 27.741 | 550,408 |
| T | 15,744 | 1,432,096 | 36.034 | 48.798 | 359,312 |
| B | 15,849 | 1,429,951 | 94.213 | 135.189 | 431,784 |
| C | 16,003 | 1,472,495 | 92.913 | 133.570 | 381,544 |
| D | 15,772 | 1,322,604 | 92.993 | 133.469 | 421,512 |

B explores 34 fewer candidates than O but performs more interpreter work and
takes much longer. This is not an efficiency improvement. The smaller stored
description is not a newly learned mathematical contraction: B acquired fewer
other certified operations under the same cycle allocation. Do not infer a
compression benefit from different active samples or add per-attempt utilities.

Other final Theory records also decreased: concepts 45 to 39, theorem records
81 to 50, observation bindings 9 to 7, procedure records 62 to 43, and downstream
use records 103 to 78. Bindings are not counted as distinct spaces. The existing
`future_search_reduced` check changed from true to false. Thus the infrastructure
verification passes while B's `all_minimum_criteria` is false. This negative
result is retained, not hidden by the top-level reproduction pass.

## Acquisition, matching, execution and storage costs

All figures below are fresh CI seconds. Nested timers must not be summed as
disjoint work. Full process totals include startup, loading, snapshots and I/O.

| Cost | O | B |
| --- | ---: | ---: |
| Training internal time, 300 cycles | 10.817 | 71.560 |
| Training two-process elapsed total | 14.971 | 89.881 |
| Corpus recording / replacement | 0.352 | 3.679 |
| Learning including equivalent-view matching | 1.857 | 12.704 |
| Semantic relation certification | 0.141 | 0.142 |
| Certified-space retrieval | 0.787 | 0.576 |
| Normal DSL execution | 1.181 | 27.438 |
| Independent primitive replay | 0.389 | 4.884 |
| Final-state serialization/writes, two training checkpoints | 1.375 | 9.275 |

B additionally spends 0.166s on eligibility checks, including part of its
0.106s input-fingerprint matching total. Input matching is not a free operation.
Training plus the fresh 48-task process totals are 42.712s for O and 225.070s
for B. The complete six-condition, 96-task comparison takes 1089.912s.

Compact encoded storage, not measured resident-memory bytes:

| Stored component | O bytes | B bytes |
| --- | ---: | ---: |
| Active sample (512 rows) | 376,309 | 354,159 |
| Existing executed-program history | 2,250,426 | 22,049,150 |
| Acquisition-source evidence (24 snapshots) | 20,155 | 20,155 |
| Admission journal | 470,016 | 5,619,157 |
| Deduplication IDs | 144,721 | 1,380,469 |
| Learning attempt records | 128,586 | 2,165,024 |

The existing event history separately holds 2,528,564 / 23,400,400 bytes and
overlaps with execution records. Pretty-printed final `state.json` files are
14,432,239 / 119,124,035 bytes. No unbounded second full experience archive was
introduced; nevertheless total historical state is not constant-size.
Query code still loads and hashes that historical state, and persistence keeps
the existing multiple output views. Those costs are included in full time.
Hashing and every individual I/O component were not separately profiled, so
this report does not assign all slowdown to a single measured cause.

## Evidence access and completion boundary

The complete artifact remains on GitHub. Selected evidence is also available at
`C:/Users/81808/.openclaw/reports/dsl-corpus-actions-34760174353`.
The whole ZIP download was slow and was not completed. HTTP ranges retrieved
139 selected files; ZIP CRCs and the available harness file hashes were checked.
`retrieval.json` records that limited audit. The GitHub artifact digest above
is **not** presented as a locally recomputed full-ZIP hash.

The change repairs general finite-sample feedback infrastructure. It does not
count as MORTRA inventing a new mathematical reduction algorithm. Experience
reached abstraction after capacity; useful subsequent acquisition did not.
The fixed held-out capability comparison did not improve. No post-evaluation
tuning, corpus-capacity sweep, new solver or additional research feature was
performed to change that outcome.
