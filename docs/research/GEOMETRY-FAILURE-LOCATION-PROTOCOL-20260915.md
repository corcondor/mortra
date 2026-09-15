# Geometry failure-location protocol

This experiment diagnoses existing failures; it changes no solver, parser,
scheduler, candidate generator, proof rule, acquired definition or goal.
Baseline: 1e1f61e41f938db61bfdccf785e9df7f15762fe5. The unfinished untracked
geometry_finite_reuse.py in the other worktree is absent here and is not used.

## Fixed normal execution

Use scripts/run_theory_formation.py with
configs/theory-geometry-failure-location.json. Read only the C archive acquired
by Actions 34908552962, verified by ZIP/member hashes, as initial knowledge.
Old execution outcomes are not used as new success evidence. All four existing
conditions run again: A primitive/ordinary, B primitive/contract-order,
C learned/ordinary, D learned/contract-order. The two cohorts each contain 16
previously inspected tasks. Each task has 112 applications; A-unsolved regression
tasks additionally get separate A/D runs with 448 applications. These are not
new held-out tasks. The existing entry revalidates the fixed library and seals
source/config. Acquisition and policy learning remain off.

## Separate diagnostic analysis

After the normal run, replay its saved events without changing that run.
Developer-written witness constructions are diagnostic inputs only. They never
enter normal execution, training, library selection, or success counts.
For each witness step record exact coordinates, preconditions, goal checks,
presence/co-presence of inputs in retained states, candidate scan/order/selection,
execution/refusal, and whether its output was retained. Coordinate equivalence
does not imply identical proof provenance. A missing particular witness route
does not prove every possible route is absent.

For duplicate-output refusals, independently replay the selected acquired
composition on the recorded parent. Count new intermediate points discarded by
the refusal, whether they satisfy goals, and whether they match witness inputs.
Do not silently treat these points as normal retained states or repair the run.
Record all analysis execution costs separately from autonomous search costs.

## Competing hypotheses and limits

1. Candidate exclusion: required legal binding is absent from its declared
   complete grammar. Distinguish this from an unconsumed iterator at cutoff.
2. Budget allocation: required binding exists, but was not scanned/selected;
   compare identical inputs across four conditions and 112/448 budgets.
3. State composition: necessary points were reached on different branches but
   never coexisted in a retained state. This is not proof that merging is safe.
4. Output loss: a refused macro computed useful intermediates but retained none.
5. Verification: a point satisfying all exact goal conditions was reached but
   refused. Separate construction preconditions from goal nondegeneracy.
6. Acquired library mismatch: legal acquired calls do not establish useful
   results under observed tasks. Call frequency is not benefit.

Unused backward-proof code is a call-path observation, not a causal result.
No backward-search implementation or new ranking heuristic will be introduced
in this experiment. A negative bounded run is not an impossibility theorem.

## Evidence

Keep commands, SHA, dependency versions, source/config seals, normal outputs,
raw event log, diagnostic inputs/results and timing. Summarize per task as well
as in aggregate. No rerun may overwrite an earlier failed run.
