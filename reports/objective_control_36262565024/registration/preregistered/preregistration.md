# MORTRA contraction and objective-derived exploration readout pilot

Registered before new policy outcomes, 2026-09-27. Development/descriptive study,
not an independent confirmation: these worlds were previously evaluated.

## Frozen material

- Base branch head: 0fdcecd170c9994d36ff77ba09be9c6fbb8073f3.
- Frozen algorithms: 24c44da50aac2c084a91fdd9f6754f0429da9350.
- Inputs: registration artifact from Actions run 36220511321.
- Fixed worlds: 73000000 through 73000007 inclusive, the first eight registered
  seeds by index, without inspection-based substitution.
- Each world's saved 12 task specifications and budget-512 learner snapshot
  are reused byte-for-byte. No generation, mutation, task search, or retraining.
- Preserve unavailable worlds and engineering failures; do not relabel them as
  policy failures. Completion denominator is always eight fixed worlds.
- Execution planner, learner, world, task compiler, q=.90, stopping conditions,
  count fallback, and success boundary semantics remain unchanged.

## Algebraic verification, not performance treatments

For each initial learned product/frontier graph, verify:

1. With M=.9P, t=(I-M)^-1 1 and D=diag(t), the row sum of D^-1 M D is 1-1/t.
   Transform both source and field; recover the original field. This t includes
   artificial killing and is not called undiscounted task hitting time.
2. Check undiscounted applicability structurally. Only if every reachable real
   state has a path to a virtual terminal, repeat with P and actual expected
   first-frontier hitting time. Nonterminal recurrent classes are NOT APPLICABLE,
   never clamped or replaced by invented finite times.
3. Verify Doob action probabilities sum to one. Report floating-point mode
   disagreements separately; mathematically its argmax equals the old field
   argmax for uniform action weights and common q.
4. On applicable graphs, verify the generic undiscounted terminal field is one.

Numerical audit tolerance is 1e-9, not an action or semantic cutoff.

## Six exploration conditions

All consume the exact same frozen graph constructor. Its terminal sources are
unchanged: generic weight 1; task weight exp(progress before the unknown action).

- fixed_generic / fixed_task: import the original greedy field policy.
- doob_generic / doob_task: sample action a with probability
  mu(a|s)*.9*H(f(s,a))/H(s). No new temperature or coefficient is introduced.
- deadline_generic / deadline_task: on the known deterministic product graph,
  maximize terminal weight among frontiers reachable within the actual remaining
  interaction budget. Break equal utility by minimum known steps including the
  probe, then minimum first action ID. Recompute after each observation.

The last objective is explicitly a FRONTIER PROXY, not optimal task completion:
the unknown successor remains unknown. No shortest-path oracle on the true
world is used. Breadth-first search sees only learned edges. Unknown actions end
at their pre-existing virtual terminals. When no feasible frontier exists,
use the unchanged count fallback. The deadline readout does not consume q or H,
but the unchanged graph constructor computes reference fields and their CPU
cost remains included. The whole agent is NOT described as q-free.

The Doob objective admits a KL-control interpretation with cost ratio
c/lambda=-log(.9), but no claim is made that this is the benchmark's true task
objective. Choosing its mode is not a new treatment; sampling is.

## Pairing and repetitions

Maximum task/exploration steps: 4096, unchanged. All conditions get a private
copy of the same initial learner. Closed-loop observations may differ after
different actions. Every observed transition updates the original learner.

Deterministic conditions: one episode per task. Doob conditions: ten repeats.
Pair both Doob source conditions using seed
76000000 + world_index*10000 + task_id*100 + repeat.
There are at most 8*12*(4+2*10)=2304 episodes. No stopping on favorable results.

For every fixed-policy episode compare success, steps, capped steps, exploration
steps, replans, failure reason, and final acceptance against the saved historical
episode. Any mismatch stops that world's evaluation as an engineering failure.

## Endpoints and limitations

Report task success and failure-capped steps (failure=4096), separately. Average
stochastic repeats within task, then tasks within world. Report world-paired
difference and 95% percentile bootstrap interval using 20000 resamples and seed
76099999. With eight reused worlds these are descriptive, not confirmatory.
No post-hoc pass threshold, tuning, or algorithm changes after outcomes.

Retain source/input hashes, commands, numerical certificates, episode metrics,
full action/state trajectories, policy probabilities, remaining budgets, CPU,
wall time and cumulative process peak RSS. Resource exhaustion is RUN INCOMPLETE.
Display comparison plots derived from the actual records. Do not manufacture
play images. Existing results are never overwritten.
