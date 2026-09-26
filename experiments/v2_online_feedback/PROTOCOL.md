# V2 online feedback: fixed development protocol

This is an outcome-selected development experiment, not fresh confirmation.
The supplied seed 79020004 failure motivates it. No games are generated or edited.
The unit of comparison is each of the eight existing worlds, not each trial.

## Provenance

- Base executable: `5f8b36744a29327928c87d6db888f2f045dbea79`.
- Prior report commit: `724220d29f02b79633b0ba43adf57242ad922cb9`.
- Prior Actions run: `36273640831`.
- User ZIP SHA256: `9c100dacb9015747966068743fc3fa018cb097212b8170931b50b222779d32b2`.
- The original ZIP and four supplied files are preserved byte-for-byte under reference/.
- Source audit checks every frozen file against the base executable (explicit LF normalization for Git checkout line endings); actual byte hashes are also recorded.
- New branch: research/self-design-v2-online-feedback-20260927. The local directory suffix 20260928 is only a directory label; runtime timestamps and exact commits define provenance.

## Inputs and gates

Use seeds 79020000 through 79020007, virtual_frontier,
targeted/evaluations/evaluation_000 from the original artifacts.
Verify each original ZIP against its registered GitHub artifact SHA256.
Keep all 2500-step snapshots, original dictionary insertion order, actions and states.
No initial training is repeated for this experiment.

Run the supplied read-only audit unchanged on artifact 10917048485; every JSON value must match failure_audit.json.
The supplied script writes a literal backslash-n after its JSON file. Preserve that output and compare the valid JSON stdout, without editing the supplied script.

Before any new-policy outcome, run unchanged V2 and integration tests plus new adapter tests.
Reproduce all 400 historical self-play trial action/state sequences and outcomes using the frozen self-play AST with a supplied learned snapshot.
Differences stop execution. Historical psi arrays were not saved, so no historical bitwise field equality is claimed.

## Conditions

Fixed order per worker: A frozen, B record_and_replan, C record_replan_and_explore.
Each starts from a private deepcopy of the same saved snapshot and game.

- A: unchanged field/readout/ties and `trial % NUM_ACTIONS` fallback; do not update the model.
- B: same readout/fallback; record only actually executed (state,action,next_state) with the V2 recorder. Rebuild the original dense K and original q=.90 field when a state, tried action, dominant destination or observed goal set changes. Repeated counts alone do not affect the original support K.
- C: B plus existing task-blind virtual-frontier selector, source 1, exclusively at the original `best_a is None or best_val <= 1e-8` condition. Register current observation first. Retain the selector's own bookkeeping and SingletonMemory task-access assertions.

Exactly 5000 additional environment actions per arm. Reset after success or 100 actions.
Resets do not become graph transitions. Trial numbering continues across nested checkpoints 0/1000/5000.
Last rollout may end at the budget without success. Reset counts exclude initial placement and any unused reset after the final action.
If an input is initially accepting, stop as a protocol/input issue rather than invent zero-cost action handling; this is checked before revised conditions.

Each checkpoint uses a new independent frozen learner copy, original self-play, 50 trials, cap 100 actions.
Evaluation never updates training. No random baseline actions enter learning.
Public is_goal is permitted in task execution; selectors receive only the learner and current observation.
There are no oracle distances, hidden successor tables, full-graph expansion or new source estimation.
Keep MicroGame, StructuralLearner, q, solver, ties, critique, mutations and acceptance unchanged.

## Measurements and audit

Save every additional-learning action/state, all frozen evaluation trials, every checkpoint learner and psi, and all field recomputations.
Record frozen-evaluation success, mean capped cost (100 on failure), actual action counts, known states/pairs, known goals, first goal observed during additional play, first goal present in the learned model, resets, fallback/selector calls and training rollout success separately.
Initial known goal time is 0 if present in the saved model. First observed during additional play is separate, including in A which does not update its model.
Audit final counts against an independent replay of only actual executed transitions. Verify no reset edges, immutable games and unchanged evaluation learners.
Audit online cached psi against a fresh original solve at every checkpoint, bitwise, independently of discrete action agreement.

Report all seeds and C-B, B-A, C-A per checkpoint, including all negative differences and paired trial regressions.
These are descriptive paired comparisons over eight historical worlds. Do not call 400 trials independent worlds or set a post-outcome success threshold.
Count environment actions separately from CPU. Timings include Python monitoring overhead, fixed arm order and isolated world workers; no strong speed claim.
Online timing excludes checkpoint evaluation and serialization. Initial field construction is included in field CPU and full worker CPU, but not the incremental online-loop timer. Peak memory is process high-water usage, not a private per-arm allocation estimate.

## Execution and stopping

GitHub Actions: gates and input registration, then eight world workers (max parallel 4, BLAS/OMP/MKL 1), then complete/partial aggregation.
No automatic retries or replacement seeds. Infrastructure failure is RUN_NOT_COMPLETED, not policy failure. Preserve logs and partial traces.
Commit this protocol and all new implementation before any revised condition runs on the eight input worlds.
After this small comparison, report outcomes before any large loop comparison or 3D work.
Only if same-game improvement is actually observed may the identical feedback be connected as a separate evaluate_game adapter; no new critique, fitness or game rules may be introduced.

## Setup failures retained

- Local preparation attempt 1 stopped before fetching or running policies: the new sparse worktree did not materialize the prior report. Fix: read the pinned report Git object directly, rather than requiring a large report checkout. No source algorithm changed.
- Local development tests use tiny terminal-boundary fixtures; these are unit tests, not additional outcome worlds.
- Local snapshot gate attempt 1 stopped while deserializing the first game, before playback: JSON lists were compared directly with the engine's tuple-valued wall list. Fix: compare their exact JSON fingerprints; add a serialized-game round-trip test. No game values or rules changed.
- Snapshot gate attempt 2 exposed the historical writer's sorted JSON object keys. Canonicalize JSON object keys for fingerprints. Learner insertion order remains encoded and checked as ordered entry lists. Add round-trip tests with the actual sorted-key serialization format. This is input decoding, not an algorithm change.
