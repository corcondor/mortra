# Acquired DSL feedback: fresh Actions results

MORTRA acquired an executable definition, used it in a later generated program,
and acquired another definition from that execution which calls the first one.
This feedback chain occurred in the differential-ring experiment. The same
experiment did not demonstrate better performance on held-out problems.

## Evidence identity

- Repository: `corcondor/mortra`.
- Research branch: `codex/theory-formation-20260913`.
- Development starting commit: `02474f8f428f855eef8ec38a9cdc83e0571d6586`.
- Tested implementation: `eb086d561cc12ad93799736148c1edd466afb588`.
- Workflow: `.github/workflows/worker-ci.yml`, `Verify MORTRA Kernels`.
- Fresh successful [Actions run 34748694951](https://github.com/corcondor/mortra/actions/runs/34748694951), attempt 1.
- [Artifact 10315301524](https://github.com/corcondor/mortra/actions/runs/34748694951/artifacts/10315301524): `q-directed-34748694951-1`, 7,491,125 bytes.
- Artifact archive SHA256: `29ec0fa4dcc108282bad0b044b37b5355956db0018125b147ca7912ed9a597cb`.
- Target, harness and workflow SHA all equal the tested implementation above.
- Python 3.12.10; Linux x86_64; runner image `20260907.300.1`.
- Declared dependencies installed through `requirements-test.txt`. The artifact
  records the complete environment, including SymPy 1.14.0, NumPy 1.26.4,
  pytest 8.4.1, python-flint 0.9.0 and mpmath 1.3.0.

All numerical results below come from this Actions artifact, not historical
Windows logs. After downloading it, all 156 files listed in
`dsl-feedback/verification.json:artifact_sha256` matched their raw-file hashes.
The source-seal checks passed, and every normal subprocess finished successfully.
This is a reproducibility record, not a claim that hashes prove all possible
forms of absence of intervention.

## Actual feedback chain

The initial domain supplies variables `u,v`, constants `0,1`, addition,
multiplication, negation and differentiation. It supplies no learned body.
The following source computations, definition bodies, arguments and ordering
come from `theory-dsl-ring-evaluation.json` and the saved DSL corpus.

```text
DSL0 = {u,v,0,1,add,mul,neg,diff}
  -> v+(u+v) [cycle 6], v+(u+1), v+(u+u) [cycle 10]
  -> h(f0) = v+(u+f0) [cycle 11]
  -> DSL0 + {h}
  -> h(h(0)) [automatically generated and executed at cycle 13]
  -> 2*u + 2*v [exact agreement with primitive execution]
  -> g(f0) = h(h(f0)) [acquired at cycle 15]
```

Here `h` is definition 0, ID `a370030c8a3889a8`; `g` is definition 1,
ID `df323271cff949df`. Both have a scalar argument and scalar result.
Their scope is the declared rational differential-polynomial domain. Their
semantics are capture-free definitional expansion, not a newly assumed axiom.
The cycle-13 execution digest occurs in `g.acquisition_sources`; its earlier
definition reference occurs in `g.dependencies`. Thus the last edge is an
actual recorded dependency, not an explanatory reconstruction.

The original source-expression IDs for `h` are:

```text
8168f952c80cb44962d7062c59e447d7ffaf102b1bf958c7ca0b8f503abf3542
ac9a756c60e2ecab5533912fe37d7cb33dddd74e7efaac54661bbc636914d5d2
f7117a2de0b83c61919665911444e8716d6419879f0fafcf8339b27e99d4cb38
```

The persistent corpus also stores rewritten programs. For the computations
before cycle 11, their `primitive` fields preserve the source expressions;
their rewritten `program` fields must not be read as calls made before `h`
existed. The cycle-13 call is in the separate execution log.

This is simple arithmetic composition. It demonstrates an executable learned
vocabulary and a later dependent acquisition. It is not a new theorem, an
unprecedented algorithm, or evidence of advanced mathematical discovery.

## Separate judgments

| Requested property | Fresh result |
| --- | --- |
| Exact observable-space sharing | Passed for the finite fold-orientation domain: 3 spaces, 10 readout bindings, 3 closure acquisitions. |
| Automatic DSL extension | 8 structural definitions in the ring run; 3 in the fold run. Representation and recurrence operations are counted separately. |
| Later synthesis and execution using the extended DSL | Ring: 469 executed learned-definition programs. Fold: 672 acquired-representation calls and 1,272 acquired-recurrence calls. |
| Actual execution leading to a later definition that calls an earlier definition | Demonstrated in the ring run; maximum definition dependency depth 3. Not demonstrated in the fold run. |
| Definition-inclusive description reduction | Positive on each run's own training corpus; negative on the fixed external expression collection. |
| Previously unsolved to solved, or held-out proof-search improvement | Not demonstrated; this expression-evaluation collection is already evaluable by the initial interpreter. |

In particular, all three fold structural definitions have `reuse_count=0`.
Their acquisition is not counted as successful later macro use. Fold DSL
executions use the separately registered certified mathematical operations.
The machine-readable `dsl_growth` result indicates registration, not by itself
use or improved capability.

## Costs and scope

Both learning runs and both no-DSL normal runs use the same configured seed
20260913, 300-cycle limit, 300-second limit and domain-specific initial signature.
Each is split into 150 cycles and a resumed process. The initial-only condition
is the cycle-0 archive for the common held-out comparison, not a competing
300-cycle learner. The paired no-DSL normal run provides the same-budget
training comparison. Scheduler choices and resulting corpora can differ.

The next table reports the learned runs. Code bits use the existing canonical
JSON convention, with each definition body charged once. Archive bits include
the DSL record, shared-space record and observable bindings, including their
provenance. They are not a measure of mathematical intelligence.

| Quantity | Differential ring | Fold orientations |
| --- | ---: | ---: |
| Cycles | 300 | 300 |
| Structural definitions | 8 | 3 |
| Executed DSL programs | 469 | 1,944 |
| Maximum structural-definition depth | 3 | 1 |
| Primitive corpus bits | 2,178,592 | 480,848 |
| DSL corpus bits | 913,424 | 418,696 |
| Definition-body bits | 7,200 | 3,048 |
| Net training code bits saved | 1,257,968 | 59,104 |
| Full DSL/space/binding archive bits | 8,708,072 | 12,248,576 |
| Library acquisition seconds | 14.619303 | 2.963134 |
| Library candidate pairs examined | 24,000 | 20,926 |
| Library abstraction candidates | 134 | 36 |
| DSL expansion candidates examined | 7,326 | 365 |
| Typed planner states | Not used | 2,232 |
| Ordinary proof calls | 214 | 156 |
| Ordinary certification seconds | 0.271786 | 0.035992 |
| Recorded action-body seconds | 35.759423 | 18.467158 |

Fold costs separately include 3 closure calls (2.453001 seconds), 40 exact
space-membership checks (0.448582 seconds), 36 recurrence proof calls (8 failed,
0.364678 seconds), 70,092 matrix multiply-adds and 219,188 recurrence
multiply-adds in DSL execution. Ring DSL execution visits 9,733 primitive
semantic nodes. Independent shadow replay is charged separately in the raw
cost dictionaries. Action-body seconds exclude subprocess startup, snapshot
writing and held-out evaluation, and are not total CI wall time.

No-DSL normal-run action-body times were 38.783086 seconds for the ring and
5.708452 seconds for fold orientations. The larger fold archive therefore did
not yield overall speedup. Different exploration traces make these total times
unsuitable for claiming a per-task algorithmic speedup.

The exact-space certificate covers functions on all 24 declared orientations,
their declared generator actions and rational coefficients. Position, panel
history and collision legality are absent from that state description.
Equal rank alone never identifies two spaces; readout existence never grants
additional legality or goal guarantees.

## Held-out comparison and reuse

All 48 expression trees per domain and the evaluation arguments are frozen
before acquisition, using evaluation seed 739182. The evaluator uses discarded
archive copies and checks that they remain unchanged. A uses initial knowledge;
B uses acquired definitions; C disables their use on the same archive without
breaking references. All three correctly evaluate 48/48 expressions in each
domain. No solved-count gain is claimed.

Some independently frozen ring expressions happen to be rediscovered during
training: 36/48 ring expressions are absent from the B training corpus; all
48 fold expressions are absent. The artifact distinguishes these overlaps.
The collection was not modified after observing them.

| Fixed expression collection | Ring A | Ring B | Ring C | Fold A | Fold B | Fold C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Correct evaluations | 48 | 48 | 48 | 48 | 48 | 48 |
| Program bits | 64,080 | 62,992 | 64,080 | 83,264 | 83,264 | 83,264 |
| Definition bits charged for use | 0 | 7,200 | 0 | 0 | 3,048 | 0 |
| Matching checks | 0 | 3,144 | 0 | 0 | 1,035 | 0 |
| Median compression/search seconds | 0.0000157175 | 0.011346016 | 0.0000154895 | 0.0000176655 | 0.001584834 | 0.000017459 |
| Median execution seconds | 0.001024513 | 0.001125114 | 0.0012022455 | 0.0003450325 | 0.0003703395 | 0.000394403 |

On this collection, ring program shortening saves 1,088 bits before definition
cost but costs 6,112 additional bits after it. Fold costs 3,048 additional bits.
Matching overhead is measured and worsens the search/compression time. These
single-run timings are not statistically replicated performance estimates.

For acquired fold operations, the evaluator additionally checks:

- 40/40 representation calls at new action words of lengths 7, 11, 17 and 23;
  all 24 initial orientations agree with direct execution.
- 84/84 recurrence calls at pre-fixed integers 29, 47 and 71. Of these,
  76 are new procedure/argument pairs; 8 were encountered during training.
- Zero reacquisition calls and zero Task reproving calls during evaluation.
- 10/10 requests for unsupported collision-free legality refused.

The observation `q` for these checks is selected by the learner; only the word
and integer arguments are externally frozen. These are transfer to new inputs,
not proof that an independently specified unseen mathematical problem was solved.

## Fresh regression and reproducibility checks

- Existing q-directed relevant suite: 351 passed, 0 failed, 0 skipped.
- Existing Theory suite: 22 passed.
- New exact-sharing/DSL suite: 10 passed.
- Existing q-directed small normal, stored-reuse, collision-free refusal and
  reuse-only refusal runs: all passed on the same Actions target SHA.
- New normal acquisition, resume, expansion replay and held-out checks: passed.

The q-directed checks are fresh re-confirmation of existing functionality.
The space-sharing and DSL checks are new evidence for this implementation.
The same committed code also passed fresh reproduction from the clean detached
Windows worktree `C:/Users/81808/.openclaw/workspace/mortra-dsl-clean-eb086d5`.
That local evidence is separate and is not substituted for Actions output.

Reproduce through the existing verification line:

```bash
gh workflow run worker-ci.yml --ref codex/theory-formation-20260913 \
  -f verification_suite=dsl-feedback \
  -f target_ref=eb086d561cc12ad93799736148c1edd466afb588 \
  -f expected_sha=eb086d561cc12ad93799736148c1edd466afb588
```

The artifact's top-level `plan.json` and `verification.json` contain exact
q-directed commands. `dsl-feedback/verification.json:commands` contains all
ten exact normal-entry commands, including both resume paths. The new harness
command in the successful Actions job was:

```bash
python scripts/verify_theory_dsl.py \
  --config configs/theory-dsl-ring.json \
  --config configs/theory-dsl-fold.json \
  --output "$VERIFY_OUTPUT/dsl-feedback"
```

Selected raw-file SHA256 values inside the artifact:

```text
theory-dsl-ring-config.json
8254cc417c197e34e200ef2fa2785f81b839b3f98465eb705748488ecb2fb0eb
theory-dsl-fold-config.json
c07b9253ab3c986555cb670d2d50399eef2ae9cad3011257c057dbab59c13329
theory-dsl-ring-heldout.json
6084faa1ef0b4b644ba6b9c397e711ae168e96da11e60c3e408a8875f63d9882
theory-dsl-fold-heldout.json
892004efb6904b409dab5572fd77c972a3475ed103d6b6e223bd9d07cd591263
theory-dsl-ring-evaluation.json
ba27a052e8589d21602185bbba125cbd12bb598343b8fb4f744e9699b25153f0
theory-dsl-fold-evaluation.json
b94b354cb982539159c45dc82dc347289ac9dee490f467cbd65d1e2bf6547613
```

The download is preserved at
`C:/Users/81808/.openclaw/reports/dsl-feedback-actions-34748694951`.
GitHub artifact retention is 30 days. This result document is a later
documentation-only commit; it does not change the tested Python or input files.

## Remaining boundary

The implemented feedback loop is real but bounded. Acquired compositions change
the subsequent executable vocabulary and can depend on previous acquisitions.
Most executions still fully expand to the old primitive interpreter. The
training code savings do not include all proof/provenance storage and do not
imply fewer primitive operations. The fixed held-out collection neither
requires new mathematics nor shows net description improvement. Fold structural
macros were not used, although its mathematical representation operations were.

The next scientific question is whether the acquired procedures improve a
pre-fixed, nontrivial task collection rather than only the training corpus.
This run provides no positive answer to that question. No new solver,
task-specific body, public deployment, main merge or force push was used to
replace that missing result.
