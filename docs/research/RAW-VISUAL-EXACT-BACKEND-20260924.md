# Raw Visual: sequential execution of the frozen lazy backend

## Scope

MicroGame continues unchanged in Actions run 35975264733 at
`afca2779d549e505cf148e47182940991af2f8cd`. It is neither cancelled nor rerun.
The separate Raw Visual run changes execution/storage only. The reference,
`SweepResponseSymbolizer`, OLD, corrected symbol-world adapter, action operators,
belief update, quotient and planners remain unchanged.

The five Raw Visual cases reuse the exact train/heldout NPZ files already saved
by run 35975264733. Each train stream has 2500 actions and full 24 by 24 frames.
There is no resize, crop, feature selection/subsampling, history bound, or
approximate threshold grid. All 1,453,076 candidate feature specifications are
available from each full 2500-step training history, with missing history routed
exactly as in the reference.

## Gate before any full image fit

For each of seeds 201, 302, 403, 504 and 605, both targets (absolute/delta) are
fitted on the first 16 and first 32 training transitions. These are backend
validation datasets only. Their trees never initialize the full-data learners.
Every prefix retains all 576 pixel features and every lag in that prefix.

Required equality: selected features, thresholds, full BIC report, tree topology,
missing-history routing, all symbol assignments, leaf row sets and action means.
The global gate passes only after all 20 checks pass. A mismatch or unavailable
resource prevents the full Raw Visual stage. Sources and training hashes are
bound into the gate. These finite checks are not a proof of equality on every
possible input; the result explicitly states that no full-data reference fit ran.

## Full execution

The existing backend builds `HistoryColumns`/`ValidColumns`, not a dense N by F
matrix. Each feature is generated from trajectories when requested; ordered
action-conditioned sufficient-statistic sweeps evaluate every observed-value
midpoint. Existing reference rescoring and numerical safeguards are retained.
Raw observations and targets fit in memory; no memmap is needed for these arrays.
The roughly 32.7 GB feature-plus-validity allocation is never attempted.

The workflow allows one Raw Visual environment at a time. Each environment runs
in an isolated child process. The parent waits for exit before declaring the
environment released, so all child arrays are released by the operating system.
Per-environment peak memory, CPU, backend identity, prefix checks and process-exit
records are saved. Prefix-check CPU is reported separately from full fitting.

Backend label: `optimized_exact_equivalent`.

All 5 environments are attempted without algorithmic timeouts. A platform stop,
resource exhaustion or missing result is RUN NOT COMPLETED / RESOURCE UNAVAILABLE,
never a failed task. GitHub infrastructure limits can still interrupt execution;
no claim of mathematical impossibility follows from such an interruption.

This run does not retune algorithms in response to benchmark outcomes.
