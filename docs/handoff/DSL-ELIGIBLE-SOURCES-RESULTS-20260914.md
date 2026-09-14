# Bounded feedback and source eligibility: shared-CI results

## Verdict and preserved achievements

New experience beyond the 512-row boundary now produces acquired definitions,
certified semantic edits, and later executions. The fixed fresh cohort shows
no additional solved tasks and higher total costs. These are separate findings.

DSL self-expansion, recursive use of acquired definitions, and certified
semantic self-editing were already demonstrated in the earlier saved runs.
They remain established within their declared scopes. Repeating their basic
connection test is not the next research objective. In particular, no external
score gain does not mean the DSL failed to expand.

This experiment does not establish indefinite growth or better selection. The
new condition reaches its unchanged eight-definition budget at cycle 56.
Its maximum syntactic acquired-definition call depth is 1, versus 2 in the
control. This does not erase the earlier recursive-use result, but it is also
not a new depth-2 result in the new condition.

The original frozen-versus-refresh comparison is preserved in
[the FIFO results](DSL-CORPUS-FEEDBACK-RESULTS-20260913.md), Actions 34760174353.
It established refresh and re-entry into abstraction, but no post-capacity
definition acquisition. The present, separate code version addresses the
observed source-pair budget obstruction. Do not mix the two experiments.

## Reproducible identity

- Repository: `corcondor/mortra`.
- Branch: `codex/theory-formation-20260913`.
- Tested code: `f9b829c110cb3f87ae7499c3756328ea6aa61a6d`.
- Original requested baseline: `76bf26b065df6c512bbf897f82afbf5e11fae988`.
- FIFO implementation: `7b37ea25ac174c5f860e33e73d9f0519bf5b3da2`.
- Workflow: `.github/workflows/worker-ci.yml`, `q-directed-verification` job.
- [Actions run 34763094186](https://github.com/corcondor/mortra/actions/runs/34763094186),
  attempt 1, job 103739222356, success.
- Job: 2026-09-13 14:35:19 to 15:11:32 UTC, 36m13s.
- [Artifact 10320220437](https://github.com/corcondor/mortra/actions/runs/34763094186/artifacts/10320220437):
  `q-directed-34763094186-1`, 348,522,552 bytes, 30-day retention.
- GitHub-reported artifact digest:
  `sha256:ec1f634745813f05ed721442b5f2b505e0427089ca5b0f024465086161e18955`.

Workflow, harness and target SHAs are identical. Code/input seals and every
read-only evaluation archive check passed. No mid-run candidate, equation,
definition, auxiliary value or answer was added. This report is a later
documentation-only change, not a new tested code identity.

Python 3.12.10 on Linux x86_64, kernel 6.17.0-1022-azure, glibc 2.39; runner
image 20260907.300.1. Declared dependencies include SymPy 1.14.0, NumPy 1.26.4,
pytest 8.4.1, python-flint 0.9.0 and mpmath 1.3.0. Full versions and commands
are in `environment.json` and `dsl-eligible-sources/verification.json`.

## Tests and fixed comparison

Fresh CI invocations passed: 351 q-directed related tests, 22 Theory guards,
and 125 DSL/library/semantic/corpus tests. These are separate suite counts,
not an asserted count of unique tests across invocations. The last suite
includes artificial boundary and source-eligibility fixtures, not mathematical
discoveries. q-directed acquisition, stored reuse, collision-free refusal and
reuse-only refusal all passed. Permitted stored reuse still incurs zero
reacquisition and zero Task-prover calls. Existing DSL and synthesis regressions
also ran successfully.

The [protocol](DSL-ELIGIBLE-SOURCES-20260913.md) describes the generic, opt-in
source filter. It removes sources that cannot satisfy the existing abstraction
contract before spending the pair budget; it changes no target mathematics.
No capacity sweep or new solver/prover was introduced.

```sh
python -m pip install -r requirements-test.txt
python -m pytest tests/test_theory_formation.py tests/test_theory_dsl.py tests/test_theory_semantic_edit.py tests/test_theory_corpus.py scripts/test_library_compression.py scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_semantic_edit.py --plan configs/theory-eligible-sources-evaluation.json --output build/dsl-eligible-sources
```

The workflow separately runs the declared q-directed and Theory invocations.
Its `dsl-feedback` dispatch accepts the exact `target_ref` and `expected_sha`;
research source pushes also trigger the same job. No duplicate CI was started.

Both learners: `theory-dsl-fold.json`, seed 20260913, 512-row FIFO sample,
32-admission learning interval, 3,000-pair budget, eight definition slots,
300 cycles and 300 internal seconds. Each starts for 150 cycles and resumes.
Both stop at the cycle budget; the definition limit separately stops further
abstraction in the new condition. Cache and semantic-edit settings match.

Conditions: A is initial knowledge; O is FIFO with the old source pool; B adds
eligible-source preprocessing; C disables semantic editing in B's archive;
D disables only learned-definition operations in that same archive.
All 96 value-goal tasks were frozen before either learner started. Regression
seeds are 917334/917335; fresh seeds are 919071/919072. Witnesses are stored
separately and never supplied as solver programs. All evaluation acquisition
and prover counters are zero; independent replay is separately charged.

## Post-capacity experience and acquisition

| Quantity | O: unfiltered sources | B: eligible sources |
| --- | ---: | ---: |
| First full sample cycle | 42 | 42 |
| Final active sample rows | 512 | 512 |
| Total admitted unique programs | 20,604 | 31,173 |
| Admissions after the first 512 | 20,092 | 30,661 |
| Duplicate dispositions | 1 | 14 |
| Post-capacity abstraction attempts | 59 | 3 |
| Offers / detailed evaluations after capacity | 1,602 / 0 | 144 / 120 |
| Acquired definitions after capacity | 0 | 3 |
| Total definitions / semantic relations | 3 / 3 | 8 / 7 |
| Acquired-definition call depth | 2 | 1 |

B's first full sample has sequence 512, execution index 488, version 517.
The version includes five learner rewrites; these are not new admissions.
At cycle 44, abstraction consumes version 619 with 102 admitted post-capacity
sources. Both equivalent corpus views retain 45 eligible source positions,
and compare all 990 pairs per view within the unchanged budget. Forty
candidates reach detailed evaluation; one is accepted.

Post-capacity acquisitions occur at cycles 44, 50 and 56, after 614, 766 and
940 cumulative admissions. Their IDs are `95f4c39b7bc58240`,
`0c30f7d354a7b120` and `66aae815146d3815`. Each has scalar argument `f0`,
scalar result, and the declared exact finite-frame scope over QQ.

The following chain is from CI's admission journal, acquisition evidence,
semantic certificate, and execution record. `R` abbreviates the *runtime
acquired* observation binding `R-b8f032907b167b70`; `Fij` are frame entries.

```text
cycle 42, execution 583: add(R(word(A,C)), F11)
  -> admission 607; oldest sample retired; active size remains 512
cycle 44: common structure becomes D5(u) = add(R(word(A,C)), u)
  -> E-b5b556440501f36e proves D5(u) = u - F31
     all 24 states, independent arbitrary QQ argument per state
cycle 48: generator produces D5(F22)
  -> certified edit to F22 - F31
  -> 4 semantic nodes; 0 represented calls in normal execution
  -> independent original replay: 144 model-node evaluations, separately charged
  -> no later acquisition sourced from this particular execution
```

The first two post-capacity definitions have four later edited calls each,
at cycles 48/66 and 54/71 respectively. The third has no observed later-use
edge. Eight *source-to-definition* records do not mean eight definitions.
Post-capacity raw macro calls are zero because the observed calls are edited
before normal execution. This is actual use of the acquired equality, not
execution of the unedited macro. These aliases are not new mathematical
functions or a new mathematical reduction algorithm.

The established earlier chain also remains: D0(u) = u + R(A) is certified as
u - F11, its edited execution at cycle 18 is a source of one later acquisition.
There are 29 semantic-use records overall. Source evidence is retained despite
sample eviction. Panel structure, collisions and physical legality are not
represented here; folding structural definitions remain unused.

## Evaluation: no fresh capability gain

| Condition | Regression solved / 48 | Fresh solved / 48 | Semantically unseen fresh solved / 31 |
| --- | ---: | ---: | ---: |
| A initial | 20 | 23 | 7 |
| O unfiltered | 18 | 22 | 7 |
| B eligible | 18 | 22 | 7 |
| C editing disabled | 18 | 22 | 7 |
| D definition calls disabled | 18 | 22 | 7 |

Fresh O-to-B gain: 0 tasks; loss: 0 tasks. Fresh D-to-B gain and loss are
also zero. Against initial knowledge, B gains zero and loses one fresh task
(919071/external-14). All size bounds are nonbinding and resource checks pass.
The fresh cohort differs from the previous report's 918061/918062 cohort;
the earlier 21/48 and the current 22/48 are NOT a longitudinal improvement.

On the already-seen regression cohort, B gains 917334/external-20 relative
to O and D, but loses 917335/external-17. Thus equal aggregate scores conceal
both directions. Neither is a fresh generalization gain. No outcome was used
to modify the running experiment or tune the active vocabulary.

Fresh 48-task totals, with active library cost counted once per condition:

| Condition | Candidate expansions including seeds | Normal work | Query seconds | Complete query process seconds | Solution + active library bits |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 14,099 | 1,403,572 | 5.760 | 7.595 | 9,744 |
| O | 14,736 | 1,328,285 | 93.552 | 135.426 | 430,456 |
| B | 15,108 | 1,545,618 | 138.632 | 202.237 | 563,992 |
| C | 15,214 | 1,429,165 | 136.673 | 198.982 | 443,112 |
| D | 14,710 | 1,231,926 | 136.546 | 198.762 | 535,520 |

Independent replay work is 1,053 in A and 1,018 in each learned condition.
B uses 372 more candidate expansions than O and takes 66.811 more complete
process seconds. B's editing saves 106 expansions against C, but normal work
and total time are higher. Rewrite matching checks rise from 2,109 in O to
26,810 in B. There is no overall efficiency gain to report.

## Training and memory costs

All times below are fresh CI seconds. Nested timers are not additive.

| Cost | O | B |
| --- | ---: | ---: |
| Training internal time | 70.672 | 115.823 |
| Complete two-process training | 88.974 | 141.683 |
| Sample recording/replacement | 3.652 | 5.608 |
| Abstraction, including source preprocessing and equivalent-view matching | 12.475 | 12.104 |
| Semantic relation certification | 0.139 | 0.349 |
| Normal DSL execution | 27.361 | 53.147 |
| Independent primitive replay | 4.838 | 8.856 |
| Checkpoint serialization/writes | 9.380 | 13.669 |

B scans 10,316 source positions and excludes 9,863; no duplicate eligible
source occurs in this normal run. It compares 8,760 pairs and evaluates 192
candidates overall, versus O's 194,926 pairs and six detailed evaluations.
B stops acquiring at eight definitions, so its slightly smaller abstraction
time is not an equal-work speedup. Input matching costs 0.101 / 0.150s, included
within eligibility's 0.157 / 0.222s. Proof-source storage costs 0.002 / 0.005s.
Full training plus fresh query processes total 224.399s / 343.920s.
The complete five-condition, 96-task harness takes 1,739.566s.

Compact encoded bytes, not resident RAM measurements:

| Component | O | B |
| --- | ---: | ---: |
| 512-row active sample | 354,159 | 355,397 |
| Existing executed-program history | 22,049,274 | 33,526,255 |
| Acquired proof sources (24 / 60 snapshots) | 20,155 | 52,411 |
| Admission journal | 5,619,157 | 8,537,516 |
| Deduplication IDs | 1,380,469 | 2,088,592 |
| Abstraction attempt records | 2,174,615 | 201,065 |

Existing event history additionally occupies 23,400,527 / 35,557,743 bytes
and overlaps execution records. Pretty-printed final states occupy
119,142,515 / 177,788,963 bytes. Bounded learning samples are not constant
total historical memory. Every retained acquired source and the sample bound
passed checks. No full experience archive was added, and compression utilities
from different samples were not summed into a cumulative benefit.

## Read-only development diagnosis, not fresh evaluation

While CI was running, the already-seen development task 917332/external-13
was replayed with observational wrappers around the existing typed planner.
The original source seal was checked. The wrappers delegated to the unchanged
planner and executors, then asserted equality with the earlier recorded
program, solved flag, work, states, semantic rewrite trace and archive digest.
This diagnostic did not change CI code, candidate order, budget or cohort.

With B's archive and learned operations enabled, all 495 attempted applications
(plus 17 seeds) are at dependency depth 1. Learned definitions consume 132
attempts: 93 semantic duplicates, 39 new values. The remaining operations
consume 363 attempts. Total work is below the separate work bound, but the
512-state budget is exhausted before any depth-2 application.

With the same archive and only definition operations disabled, the planner
performs 381 depth-1 and 20 depth-2 applications, then solves at 418 states.
The first trace has 122 derived facts and 17 seeds; the second has 108 derived
facts and 17 seeds. The diagnostic JSON field `new_facts` includes seeds;
it must not be read as a count of newly derived facts.

This follows the actual scheduling structure in `runtime_typed_planner.py`:
`by_sort` is a snapshot for one outer iteration; newly produced facts cannot
serve as arguments until all remaining initial-argument streams finish.
Round-robin fairness is per operation, not per abstraction depth or semantic
family. Additional operations can therefore consume the bounded search before
the next composition layer. Some of their values are genuinely new, so this
is not justification for deleting all learned definitions.

The diagnostic's times are instrumented and not performance evidence. Its
Windows output is `C:/Users/81808/.openclaw/reports/definition-search-competition`;
summary SHA256 is
`a3b6a52ace5598702ac27aeeee65665050f3a4ab7870ccbc6393b7b12a2af7a6`.
The traced B/D files are hashed respectively as
`94badd3b63748bb31c2b79bfca5ef81e45f2e7180d2c647e12f610a4f77701ff` and
`3fe0db2a441c55fc80cde10878854eb4a376de70e776887b7e132dc9ca0cb535`.

## Next unresolved question

The 512-admission obstruction is repaired. The next experiment should not
ask whether an acquired definition can enter the DSL again. It should test
whether MORTRA selects an active vocabulary from its preserved certified
archive using training-only evidence of downstream utility across computations.
Description savings, mathematical state reduction and measured search savings
must remain separate. A smaller call tree is not automatically cheaper search.

This report changes no selection policy. A future general selection experiment
must preserve inactive definitions and their dependencies, record selection
costs, use no evaluation outcomes for its choices, and compare all-active,
selected and initial-language conditions under identical budgets. It needs
fresh evaluation data: all cohorts in this report are now observed.

The observed next limitations are active-vocabulary/scheduling competition,
the eight-definition archive budget, and historical-state retrieval/persistence
costs. The data do not isolate a missing prover or prove that the representation
language is exhausted. The cumulative-intelligence goal remains open.

Selected fresh evidence is stored locally at
`C:/Users/81808/.openclaw/reports/dsl-eligible-sources-actions-34763094186`.
The range retrieval obtained 123 entries and 5,771,376 compressed bytes; ZIP CRC
and available harness hashes passed. `retrieval.json` records this limited
audit. The full remote ZIP was not downloaded and its GitHub-reported digest
was not locally recomputed. The artifact contains all normal inputs, outputs,
certificates, acquisition sources, commands and failures, including negative
scientific results despite the green infrastructure check.
