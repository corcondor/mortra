# Capacity, Scheduling, and Matching: Frozen-Code Protocol

This is an experiment protocol, not a claim of capability improvement.
Read `docs/research/BOTTLENECK-CAP-INVENTORY-20260913.md` first. The inventory
was written before the measurement additions. Mathematical code stays at
`14d18a42c3a7c640a7c54c86c36b7238c419df56`.

## Conditions Frozen Before Learning

`configs/theory-bottleneck-study.json` defines11 fresh starts:
two domains times term-size limits9/12/14/18/36, then a separate fold run with
only the cycle cap increased from12000 to24000. Concept archive128,
active-concept target32, representations4, representation dimension24,
batch12, candidate threshold16000 and action-body time limit600s are fixed.
Seed20260913 is fixed. No candidate, answer, lemma or rule is injected.

The previous archive128/256 experiment is separate; it does NOT change the
expression-size bound. Do not conflate their conclusions.

The existing held-out generator freezes64 questions per domain with seed739182
before all learning. Existing exact solvers produce evaluation-only oracles.
The existing32-node per-proof-input restriction must leave both solved and
budget-exceeded tasks at K0. The task sequence and oracle are never read by the
learner. Large size bounds make held-out syntax reachable; every evaluation
records exact training-query overlap. Improvement on a repeated question must
not be called unseen-task transfer. These familiar identity families test
resource-bounded transfer, not unprecedented mathematics.

## Observation, Not a New Learner

`observe_theory_run.py` calls the frozen `run_theory_formation.main`. Wrappers
call original `Theory.actions`, `Theory.step`, `Domain.compose` exactly once
with unchanged arguments and return the original result. They record actions,
composition counts, active/unexpanded order, costs, real wall time, memory and
output-only checkpoints. All generated definitions, chosen conjectures,
proofs, rules and representations still come from frozen mathematical code.
Tests compare the entire deterministic state with and without observers.

State files at exactly1000 normal prover calls give the resource-normalised
comparison. This holds CALL COUNT constant, not symbolic operation count or
CPU time. Prover input nodes, matching inspections and actual wall time are
also reported; equal calls must not be described as equal computational work.
An additional11338-call checkpoint is predeclared for the fold scheduling
comparison because the prior12000-cycle run spent that many calls. A condition
that never reaches a checkpoint has no measured result at that budget.

Cycle1000/4000/12000 checkpoints and final states give diagnostic trajectories.
The engine's600s bound is retained; a larger-bound run stopped by time is
labelled censored, not a completed equal-cycle comparison. A900s process
watchdog preserves failure logs; a failed run is never silently continued.
Observer and serialization overhead are explicitly included in process wall
time and separately labelled where measured. Linux peak RSS is recorded.

## Read-Only Diagnostics

Both cap9 runs and the complete29-parent algebra diagnosis finish before the
first larger cap is executed. For every blocked parent, reconstruct compositions
using the active operands at its actual expansion cycle. Simplify using ONLY
rules already certified before that cycle. Verify semantic equality with the
original term and classify duplicates against the archive then available.
This diagnostic is never an acquisition and never feeds the learner.

Every remaining active, unexpanded concept gets its per-cycle position, age,
open queue, kind-priority options, chosen action, and spent budget recorded.
The scheduler assigns priority to computation kinds, not numeric scores to
individual concepts; report that distinction rather than invent a priority.
Frontier insertion events and first pre-step observations differ by one cycle
when insertion occurs in `actions()` before the step counter increments.

Post-run rule ablations execute on discarded copies: full, useful-only,
unused-only, none. Useful means actual later recorded reuse or actual full
held-out reuse, including an unbounded diagnostic to recover dependencies not
recorded before a blocked prover call. This hindsight filter never changes
normal policy. Disabling rule execution retains previously established
certificate truth; it is not theorem retraction.

Unprofiled answer timings are the primary latency measurement. Separate
discarded cProfile runs save function-level self/inclusive times. Another
profile observes the next24 existing actions from saved cycle1000 to include
generation. Return-frame counters measure accepted replacements, inspections,
and successful/failed root pattern attempts without changing rewrite output.
Inline scope checks do not expose a separate certificate-lookup timer. Mark
that portion unseparated; never invent a measurement. Inclusive profiles
overlap and must not be summed as disjoint phase totals.

The semantic candidate census measures generated expressions with existing
exact evaluation after the run. It does not claim the learner evaluated or
acquired every censused expression. Same-semantic-function rewrite rules may
have different executable patterns; duplicate classification does not license
deleting those rules.

## Reproduction

Install only `requirements-test.txt`. Run:

```text
python -m pytest tests/test_theory_bottleneck.py tests/test_persistent_learning_measurement.py tests/test_frontier_reconnection.py tests/test_theory_formation.py -q
```

The existing `worker-ci.yml` accepts suite `bottleneck-study`. Dispatch it from
the control branch with `target_ref` and `expected_sha` both the full mathematical
SHA above. It performs the standard q-directed test/acquisition/reuse/refusal
checks, theory tests, observer tests, and then this experiment. No production
or research mathematical code is changed. Both control and target SHAs,
commands, configs, seed, source seal, environment and all fresh results are
uploaded with failures. CI has a180-minute outer watchdog for the11 conditions.

Final reporting must separate actual autonomous mathematics, read-only
diagnostic replay, semantic acquisitions, external held-out results, and
resource overhead. If no capability extension occurs, report it explicitly.
No new retrieval, fairness, synthesis, representation or proof mechanism may be
implemented as part of this study; propose one only after the evidence exists.
