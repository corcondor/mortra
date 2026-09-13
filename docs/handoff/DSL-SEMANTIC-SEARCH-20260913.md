# Typed acquired composition and value-specified search

This document describes the first protocol at commit `2b21189a65e7978ea935a9cb2583688cba07363f`.
The current structural-only ablation and expanded cost accounting are specified
in [DSL-SYNTHESIS-COMPARISON-20260913.md](DSL-SYNTHESIS-COMPARISON-20260913.md).

This revision starts from `b47fdb1bb74513820cf491ac5906ed0ce510d5d7`.
The previous recorded implementation was `eb086d561cc12ad93799736148c1edd466afb588`.
Historical THEORY.md and NEXT.md status labels are unchanged.

## Defects addressed

The previous fold run's three structural definitions were wrappers around
existing recurrence calls. A natural-number input had become an unrestricted
rational hole. These wrappers earned canonical-JSON savings without introducing
a composition, and none was subsequently executed as a macro.

The typed primitive leaf is now abstracted as a whole typed input. Shared
disagreement pairs still use the same parameter. The structural learner excludes
one-operation aliases before scoring; it records excluded candidate IDs. The
same existing anti-unifier, matcher and expander are used.

Runtime argument pools are partitioned by the acquired signatures. Fresh words
and naturals enter these pools before call generation. Computation syntax, not
the already-evaluated scalar answer, is used for procedure-call deduplication.
Results are still checked by independent primitive execution. Distinct calls
with equal values are not counted as distinct mathematics.

The existing domain constructors now accept the vocabulary's type checker.
Normal synthesis composes previously executed acquired programs with these same
constructors, and rotates its choice of parent. This closes the missing route
from a represented observation to, for example, an algebraic expression using
that observation. The expression itself is selected by the generator, not in
this document or the config.

## A real synthesis task, not evaluation of a supplied expression

The normal entry accepts `--queries <json>` and optional
`--knowledge <normal-run/state.json>`. A query gives:

- the complete finite-model scope;
- one exact rational output value for each state;
- a candidate, depth and expression-size budget.

It does not supply a constructing expression or a route. Extra witness fields
and unsupported legality/goal requirements are refused. MORTRA must synthesize
a program which has the specified values on the complete model. The existing
`runtime_typed_planner` performs the enumeration; the adapter registers the
domain's constructors and the acquired typed operations.

The planner now supports value-sensitive goals, in addition to its existing
sort-only goals. It can use an exact semantic congruence as its duplicate key.
The adapter uses equality of complete finite functions, which is preserved by
the declared pure operations. It does not equate physical states merely because
their observations match. There is no implication for collision legality.

A generic round-robin mode interleaves attempted applications of constructors.
This prevents one binary Cartesian product from consuming the budget before
other constructors are visited. Default sort-only planner clients keep their
old ordering. All modes now enforce the state bound even after duplicate results.

The representation interpreter caches compiled exact rational data and repeated
pure observations. Integrity/scope checks still run on every use. These are
implementation caches, not learned knowledge. External queries start with cold
interpreter caches. Compile counts and cache hits are recorded separately from
acquisition and actual rational multiply-adds.

## Experiment protocol

`scripts/verify_theory_tasks.py` freezes 24 distinct finite value specifications
before training. It stores their constructing expressions in a separate
evaluator-only witness file, which is never passed to the normal entry.
The depth schedule is four depth-0 sources, four depth-2 sources, eight depth-4
sources and eight depth-6 sources. Duplicate specifications are rejected before
training. The inputs are external evaluation tasks, not MORTRA discoveries.

Each query has the same 512-state search bound, depth 5, program size 12 and
expanded size 64. A state count includes initial facts and attempted executable
applications. Equal state counts do not mean equal arithmetic or wall-time cost;
the output also records those costs.

The conditions are:

- A: initial signature only;
- B: the archive after the normal 150-cycle run plus resumed 150 cycles;
- C: that same archive with acquired operations disabled, without deleting
  referenced definitions or changing the query set.

All three use the same primitive input set and generic candidate policy. An
answer includes its synthesized program and an independent all-state replay.
Queries do not update the knowledge archive. Partial query outputs are saved
after each task, so a stopped process retains completed results.

The report separately lists newly solved tasks, lost solutions, search costs
on tasks solved in both A and B, acquisition costs, and the actual acquired
definition dependency chain. Passing infrastructure checks does not require
a positive scientific result.

The development task seed `917331` was inspected. It is not confirmatory data.
Before the final committed runs, two other seeds, `917332` and `917333`, were
fixed for confirmation. Both must be reported, including negative results;
neither may be chosen because it favors the learned archive.

## Reproduction

Install `requirements-test.txt` using Python 3.12.10. The existing
`worker-ci.yml` workflow's `dsl-feedback` mode runs the unchanged 351-test
q-directed suite, normal/reuse/refusal, Theory tests, DSL tests, the earlier
DSL experiment and both new confirmation task collections.

```bash
python -m pytest tests/test_theory_dsl.py tests/test_theory_formation.py -q
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917332 --output <fresh-output-332>
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917333 --output <fresh-output-333>
```

The harness saves exact commands, inputs, source hashes, task witnesses, normal
snapshots, query solutions/failures, per-task costs and raw-file SHA256 values.
Run IDs and confirmation outcomes must be read from completed Actions artifacts,
not inferred from these instructions.

## Preserved development failures

- `C:/Users/81808/.openclaw/reports/dsl-feedback-v2-before-tests.log`:
  three new regression failures against the prior implementation.
- `C:/Users/81808/.openclaw/reports/dsl-feedback-v2-task-pilot/`:
  A solved 12/24, B 11/24, C 12/24; the duplicate path overshot the intended
  state bound. This run is not an equal-budget capability comparison.
- `C:/Users/81808/.openclaw/reports/dsl-feedback-v2-fair-pilot/`:
  after enforcing the bound and interleaving, A solved 13/24, B 12/24, C 13/24.
  No previously unsolved task became solved. This negative result is retained.

There is no new mathematical domain, theorem prover, target-specific case,
source-level self-programmer, or evidence of general open-ended intelligence
in these changes. The new synthesis-task adapter and caches are developer
infrastructure. The acquired bodies and subsequent calls are runtime data.
