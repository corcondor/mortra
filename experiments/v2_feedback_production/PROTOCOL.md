# V2 production-loop feedback development comparison

Fixed before this run's outcomes. Known games, not fresh confirmation.
Base checkout: 90a7bba04ce8895869b6b2eb7b3dd7d8cae25207.
All prior code, reports and attachments remain unchanged.

## Frozen design

- Saved initial games 79020000..79020007 from report 36281122365.
- Every evaluation starts a fresh V2 StructuralLearner, runs 2500 real actions
  with TaskBlindSelector("virtual_frontier"), then exactly 5000 FeedbackPlayer
  actions. The original evaluator then runs 50 frozen trials with cap 100,
  50 random trials (original seed 999), and its original auxiliary-goal check.
- A=frozen, B=record_and_replan, C=record_replan_and_explore. Preserve ARMS,
  q=.90, source=1, readout, ties, terminal checks, critique, mutation and acceptance.
- The only arm extension compiles the existing FeedbackLoopAdapter.feedback
  body with ARMS[2] replaced by self.arm. No other AST node changes.
- No transfer probe environments, learned predictors, new goals or oracle paths.
  Attached transfer ZIP is contextual evidence only, SHA256
  96296dca277da954b20a946d7a6fa4b2ac45cf9e04c7392cfe71d8eb4dc99313.

## Execution gates and fixed run order

1. Existing tests unchanged plus new structural/instrumentation tests.
2. Install the original FeedbackLoopAdapter and execute the actual original
   run_self_design_loop for 5 iterations, seeds 79020000 and 79020004, targeted
   then random. No mocks. Mutation RNG seed equals the initial-game seed in all
   arms and both modes. This is a fixed evaluation choice, not outcome-tuned.
3. On both initial games compare the new thin C adapter to those original
   adapter evaluations: full initial/additional action traces, ordered learner
   snapshots, all frozen evaluation actions and all evaluation metrics.
4. Only if all gates pass, eight world jobs, each A/B/C in fixed order, each
   targeted then random, 20 iterations. Thus 48 series and 1008 evaluations.
   Initial evaluations are rerun as part of each series, not imported snapshots.
5. After ALL series complete, evaluate each of the 48 final games with the
   same C evaluator (fresh 2500+5000 learning actions, 50 frozen and 50 random
   trials). Do not send these results back to any selection process.

## Audit and interpretation

Each candidate evaluation records the game, initial training, additional
training, initial/final ordered learner snapshots, all frozen/random/auxiliary
actions, feedback metrics, resource times and exact operation counts. The
observer checks the same learner crosses the feedback/frozen boundary, no
frozen/random action is recorded, counts reflect only executed training
transitions, and reset does not create a transition. Critique/acceptance calls
must reference the actual returned evaluation objects. Replay recorded actions
and check all trial outcomes. Save proposed and retained games and decisions.

Report C-B, B-A, C-A per mode using paired world differences, all raw values,
success counts, capped cost (failure 100), original design metrics, accepted
edits and goal/start/game changes. Distinguish learning on an unchanged game
from success on a changed game, even if the goal stayed fixed. Do not use the
original function's "unsolvable" diagnostic label as an oracle statement.
Final series games differ: report common-C and random reevaluation separately;
do not infer game quality from each series' own success rate alone.

Count initial + additional + actual frozen + random + auxiliary actions;
also report verification replays separately, not as learning interactions.
CPU includes profiling overhead, fixed arm order and shared cloud workers:
diagnostic costs, not a strict speed benchmark. Record versions, source/input
hashes, commands, job attempt, peak process memory, errors and partial output.
No selective reruns, post-outcome parameter changes or early success stops.
Infrastructure interruption means incomplete, not a policy failure.

GitHub Actions: pinned Python 3.12.10; BLAS/OMP/MKL=1; max-parallel=4;
gate -> eight production jobs -> eight common-evaluation jobs -> aggregation.
The platform runtime ceiling is an infrastructure constraint, not a policy cap.
Stop after reporting this development comparison.
