# Frontier v1.1: Fixed-World Holdout Preregistration

This audit uses exactly the 24 final Stage 2 worlds from GitHub Actions run
36080469660, source c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902.
No generation, mutation, selection, Player changes or cross-world transfer runs.
The complete old source manifest is checked against that commit.

## Before Evaluation

Task RNG root is 2026092501. The seed for each case is
derive(root, world_seed, game_hash, 'holdout-tasks'). The condition is not part of
this derivation, so identical worlds in a seed receive identical holdouts.
Each original Stage 1/2 result and initial-pool task list is read. All task pairs
previously evaluated under the same exact world genome are excluded, not merely
the final selected 100. Artifact and genome hashes are recorded.

All 24 task sets, the seeds, source hashes and manifest are persisted by a
separate preparation job before any Player executes a holdout. Generation of
evaluation tasks is permitted; generation or editing of worlds is not.

Use the original four shortest-distance bins: 4-7, 8-15, 16-31, 32+.
Generate up to 500 distinct unused reachable pairs per world with distance>=4.
Use the original reservoir scheme, a quota of 125 per bin, and randomly redistribute
unfilled quotas. Enumerate all available pairs if fewer than 500 exist. Do not
duplicate tasks or replace the world. Before new evaluation, the archived
population already shows that random/302 has at most 315 remaining pairs.
An empty remainder is NO_UNUSED_TASKS, not a Player failure.

## Identical Training and Reasoning

Execute the original v1.1 learn function bytecode with an evaluation callback.
The callback first evaluates the original selection tasks with the original
seed/labels and asserts equality of learner fingerprint, K, task results,
recorded trajectory hashes and solver outputs at every original checkpoint.
Then it evaluates holdout tasks using the same frozen learner and a copy of the
opaque-label registry. The copy matters: allocating IDs for new task states must
not alter subsequent training ID assignment. No evaluation transition is learned.
The original exploration state is never reset by either evaluation.

Budget, checkpoints, q=.90, cutoff=1e-7, solver defaults, action readout and the
2048-action evaluation horizon remain exactly as in the source experiment.
The objective is task reuse within one world, not transfer between worlds.
Original-checkpoint mismatch is an audit/reproduction error and stops that case;
it is not interpreted as evidence against MORTRA's capabilities.

## Measurements and Interpretation

Primary outputs: S_selection(B), S_holdout(B), their difference at 8192,
B80_selection and B80_holdout (unreached thresholds censored), and both D values.
Report every world, not only worlds exceeding 80%. Report actual task counts,
per-bin counts and rates, both pooled and equal-world aggregate success,
CPU, process peak memory, fingerprints, source/data hashes and recorded task zero.

Exclusion and quota redistribution may change the distance-bin mixture. Also
report the success gap standardized to the selection weights on common bins.
Report the selection probability mass omitted when a bin has no unused tasks.
Do not estimate missing-bin performance or treat a raw gap as pure overfitting.
This is a descriptive eight-seed audit; no post-hoc significance or pass threshold.

High final-world holdout success supports reuse on previously unselected tasks
within those worlds. Auditing only final worlds cannot independently verify the
entire evolutionary hardening trajectory on holdout tasks. No algorithm is tuned
after outcomes. Stop after these 24 audits and their report.
