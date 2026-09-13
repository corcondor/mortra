# Fixed-capacity experience feedback

Fresh shared-CI outcomes are in [the results record](DSL-CORPUS-FEEDBACK-RESULTS-20260913.md).

## Scope and baseline

Baseline code: `76bf26b065df6c512bbf897f82afbf5e11fae988`.
Starting checkout: `f5fdada659a1a1dcabcb99171b3f3b1641b8c413` (report-only
changes after that code). Repository: `corcondor/mortra`; research branch:
`codex/theory-formation-20260913`. No solver, proof rule, mathematical
abstraction algorithm or scheduler ranking policy is added here.

The previously verified acquisition / semantic relation / certified edit /
execution / subsequent acquisition path remains. This change concerns which
execution samples that existing learner consumes, and when it is eligible.

## State and update rules

`Vocabulary.record` keeps the existing 512-row sample by default. The opt-in
`--refresh-corpus` condition replaces its oldest row on each new unique program.
The control refuses admissions after its first 512. Both record disposition.
Identity is the exact program digest, not semantic equivalence. A duplicate is
logged but does not change content, arrivals or learning eligibility. No random
historical mixing or evaluation-driven sample selection is performed.

Separate persisted quantities:

- `len(corpus)`: currently available sample count, at most the configured bound.
- `experience_count`: unique programs observed, including capacity refusals.
- `corpus_arrivals`: cumulative admissions, including FIFO replacements.
- `corpus_version`: actual sample content changes, including learner rewrites.
- `last_learn_arrivals`, `last_learn_version`, `last_learn_knowledge`: consumed
  learning inputs. Empty / rejected attempts consume inputs too.
- `last_synthesis_generation`: consumed corpus, usable definitions and certified
  operations, active concepts and existing execution-stream version.

The existing learning interval (32 admissions) is preserved. New usable
knowledge also permits reconsideration after an earlier attempt. A learner's
own equivalent rewrite and newly registered result are consumed at completion;
they are not new experience and do not immediately re-trigger learning.
Synthesis consumes its input before execution; genuinely new outputs can
therefore feed its next invocation. Merely advancing word/natural/composition
cursors does not invalidate that input. The existing scheduler still selects
among eligible operations by its prior least-visited / estimated-cost rules.

This scheduler uses seeded content hashes rather than a mutable random-number
generator. Resume retains the seed, all cursors and consumed-input versions.
The runner refuses a changed code seal, config, or refresh condition on resume.

## Storage, provenance and cost

Full experience bodies are **not** copied into an unbounded second archive.
Existing executed-program records remain the history. The admission journal
stores IDs, dispositions, sequence/cycle/version and an execution-record index
where available. Newly admitted concept computations carry their parents and
exact evaluation in the active sample. Negative learning attempts retain input
IDs and outcomes, not another full corpus snapshot.

On an accepted definition only, `source_evidence` references immutable source
row snapshots in `acquisition_evidence`. This covers syntactically used rows and
rows providing certified equivalent views. Snapshot IDs cover the complete row,
so later equivalent rewrites never silently replace an older proof's source.
Additional source snapshots are bounded by definitions budget times corpus
capacity. Definitions, relations, proofs and their dependencies are not evicted.
Discarded, unused bodies are not all retained; the journal makes this explicit.

The execution history, admission journal and deduplication index can still grow
within the run budget. This is not a claim of constant total memory. The runner
records `persistence.json` with serialization/write time and physical JSON file
sizes. `corpus_feedback.storage` separately measures compact encoded sample,
execution history, source evidence, journal, index, attempts and existing event
history. These views overlap with existing files; do not add them as unique RAM.

Costs include `corpus_feedback`, `corpus_proof_storage`, `corpus_input_matching`,
`corpus_eligibility`, existing acquisition/certification/edit/replay costs and
full process time. Eligibility time includes its nested input matching; do not
double-count nested timers. Per-corpus compression utility is not summed as a
cumulative learning benefit across different samples.

## Frozen comparison

Plan: `configs/theory-corpus-feedback-evaluation.json`.
Normal input: `configs/theory-dsl-fold.json`, seed 20260913, 300 cycles,
300 internal seconds, capacity 512, library interval 32. Two 150-cycle halves
exercise save/resume. Normal input contains primitives, domain and budgets,
not desired definitions, relations, auxiliary quantities or target answers.

Primary comparison: `O-frozen-corpus` versus `B-edited` (FIFO). Both use the same
semantic editing and syntax-cache settings. Additional conditions are initial
knowledge, the 150-cycle FIFO checkpoint, the identical FIFO archive without
semantic editing, and that archive with only learned definition operations
disabled. The latter retains dependencies needed by certified operations.

The 48 regression tasks use seeds 917334/917335. The separate 48 tasks use
918061/918062, fixed before training and not used for development selection.
The harness freezes all value specifications and independent witnesses first;
only the specifications go to the normal synthesis entry. Evaluation does not
alter the archive. Definition/representation names are never injected as task
answers. Existing resource/size nonbinding checks and exact replay remain.

Boundary fixtures are artificial engineering tests, not autonomous discovery
evidence. Development cohort 917331 is also not an unseen evaluation.

## Reproduction

Use the formally declared `requirements-test.txt`, Python 3.12.

```sh
python -m pip install -r requirements-test.txt
python -m pytest tests/test_theory_formation.py tests/test_theory_dsl.py tests/test_theory_semantic_edit.py tests/test_theory_corpus.py scripts/test_library_compression.py scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_semantic_edit.py --plan configs/theory-corpus-feedback-evaluation.json --output build/dsl-corpus-feedback
```

The existing `Verify MORTRA Kernels` workflow runs this comparison in its DSL
verification line. Push the research branch or dispatch `dsl-feedback` with the
exact target SHA and `expected_sha`. No extra workflow is introduced. q-directed
tests/acquisition/reuse/refusal and prior DSL tests still run. The new comparison
replaces the prior repeated semantic-runtime experiment in that line; its old
plan and results remain reproducible. Run ID, source seal, exact commands,
configs, all outcomes, storage and verification are uploaded by the same job.

## Rejected prototype

Development V1 duplicated every unique experience body in `experience_archive`.
It completed but was rejected for storage design, not promoted as final code.
FIFO admitted 20,092 experiences beyond capacity and triggered 59 later learning
attempts; none acquired a later definition. The last attempts offered candidates
but all were excluded by the existing compositional contract. The final state
alone occupied 151,534,365 bytes. No corpus prefilter or candidate strategy was
added to manufacture a positive result.

Full V1 output is retained in the Windows report archive
`C:/Users/81808/.openclaw/reports/dsl-corpus-feedback-development-v1.zip`,
SHA256 `d2694b9e6a37377632fe378dd610ff1ebbe6fab0b6e54d195a35b9c078f30164`.
All 189 original files were checked against their ZIP entries before removing
large duplicate files. The adjacent manifest records each file hash. Its
verification record contains the actual uncommitted source seal; the recorded
Git HEAD alone is not its code identity. A separate saved prototype patch and
tests record that development version. Final results belong in a separate
results document, not in this historical prototype claim.

Development V2 completed under a frozen source seal in
`C:/Users/81808/.openclaw/reports/dsl-corpus-feedback-development-v2`.
It retained 24 acquisition-source snapshots (20,155 compact encoded bytes),
not 20,604 full experience snapshots. Both conditions filled at cycle 42.
FIFO admitted 20,092 later programs and ran 59 post-capacity abstractions;
post-capacity acquired definitions remained zero. The established three
definitions, three relations, 16 edited executions and subsequent acquisition
were preserved. Both primary conditions solved 12/24 development tasks.
Local regression tests briefly overlapped this development experiment; its
elapsed times are not used as the isolated primary performance comparison.
Boundary fixtures: 10 passed. Related development suite: 143 passed (the final
extra proof-retention assertion was then rechecked in the 10-test boundary run).
Console summarization was shortened after that terminal run; no learner or
evaluation policy changed. Shared CI supplies the final committed-code result.
