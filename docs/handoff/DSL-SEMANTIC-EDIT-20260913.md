# Semantic editing protocol

Starting point: 004487f85197668c4b04745c22b59344afc2ceff, report commit
for the f5103c8 implementation. Previous results are not evidence of this run.
The historical THEORY.md/NEXT.md status labels remain historical.

## Mathematical contract

The normal learner analyzes acquired definitions, not a developer-provided g.
Each scalar argument is an arbitrary QQ-valued function on the entire declared
finite state set. Every argument/state pair has an independent symbol. Existing
Domain.evaluate interprets the instantiated primitive polynomial with these
symbolic sensors; SymPy checks every residual as a QQ polynomial. A pullback
permutes the symbols rather than treating an argument as one state-independent
number. No sample coincidence is promoted to a universal argument equation.
Non-scalar parameters and non-finite domains are explicitly unsupported by this
new certificate, not specialized to some word or natural number.

Candidate right-hand sides come from parameters, domain seeds, existing
subterms/definitions and an exact linear readout in their span. This is bounded
discovery, not a complete decision procedure for shortest equivalent programs.
Original definitions are immutable. Equations include scope, parameter types,
free variables, residuals and fingerprints of referenced mathematical content.
Mutable use counts are not certificate dependencies. These integrity seals are
not signatures or independent proof-kernel verification.

Execution chooses between certified alternatives by a cold arithmetic estimate
on the actual arguments, followed by description bits. This need not minimize
wall time or warm-cache cost. Projection aliases are omitted from active search
branches. Equivalent definitions retain all implementations in the archive,
with one older representative branch; its calls can still be rewritten.

## Abstraction modulo equations

babble, Cao et al. (POPL 2023), section 4.1 and Figure 9, distinguishes semantic
equivalence from definitional expansion. It searches equivalent corpus forms
before abstraction/selection: https://cnandi.com/docs/babble23-cr.pdf.
Read for this implementation; no performance claim is imported from the paper.

Here the existing anti-unifier runs on two bounded views: the original corpus
and a certified rewritten view. Neither is discarded before candidate ranking.
Each candidate's utility is measured on one copy of each original example,
never on duplicated equivalent examples. The pair budget is split between views.
This is not a full e-graph or equality-saturation implementation. Existing
local expansion round-trip checks and full primitive syntactic comparisons
remain. A semantic history separately records the justified change between
views, and later definitions record those equation dependencies.

## Execution and measurement

`primitive` remains the independent original-computation replay path. Candidate
size checking uses `execution_shape`, which traverses syntax but does not run
recurrence steps. Certified normal execution uses acquired matrices/readouts or
recurrence coefficients. Query replay retains the original computation, has
separate counters, and is still charged against the same total work budget.
No claimed speedup silently excludes replay, expansion, lookup or validation.
Arithmetic work counts are not bit complexity; scope/integrity checks and SymPy
linear algebra are included in wall time, not represented as hardware cycles.

## Frozen comparison

Plan: configs/theory-semantic-evaluation.json. Regression seeds 917334/917335
were seen in prior development. Fresh seeds **918041/918042** are fixed here
before measurement; they must not be used for tuning. All four cohorts are
generated before either learner runs. Separate witnesses never enter the solver.
Development-only harness seed: 917331. Both learners use the same 300-cycle
configuration and seed, and resume once halfway through. Acquired objects may
grow, but source/configuration are fixed throughout each run.

- A: initial language, certified execution path.
- L: old learner archive, legacy pre-evaluation replay path.
- F: same old archive, certified execution path (isolates removed duplicate work).
- B: semantic-edit learner archive, editing enabled.
- C: the identical B archive, editing and active-branch reduction disabled.

All conditions share query budgets. Macro expansion and matching, certification,
optimization, acquisition, independent replay and process times are recorded.
Library costs include original definitions plus equation certificates, not only
the shorter answer body. Success of the protocol is not success of learning:
negative solved-count or runtime results must remain visible. Report semantic
overlap with training after the run; do not select tasks using that overlap.

```bash
python -m pytest tests/test_theory_semantic_edit.py tests/test_theory_dsl.py \
  tests/test_theory_formation.py scripts/test_library_compression.py \
  scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_semantic_edit.py --output <fresh-directory>
```

The existing worker-ci.yml dsl-feedback verification line also retains the 351
baseline tests, normal/reuse/refusal, old 48-expression checks and old 48-task
regression. No new solver workflow or repository is introduced.

Development failure retained: dsl-edit-development-v1 stopped because mutable
representation usage metadata was fingerprinted as mathematical dependency.
v2 is a separately started run after that defect was corrected. The final
results must name their own source seal and Actions run rather than these logs.

Scope remains frame observations, not panel structure or collision-free origami.
Historical unused folding-structure definitions remain unused evidence, not
retroactively counted as representation or recurrence use.
