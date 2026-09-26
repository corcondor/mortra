# Virtual-frontier Task Agent: development mechanism protocol

Written before pilot outcomes. Base branch: research/task-agent-product-field-20260926.
Base SHA: 6f9fc5018dd067fa693afb3b4d3ad1cfa04485e6.

## Scope and freeze

Do not run the 70-world experiment. Do not modify the historical learner,
environments, tasks, execution planner, online loop, tests or registered outputs.
New exploration mechanisms and an instrumented development harness are additive.
The old task_conditioned_t0 comparison is not evidence of field conditioning.

The baseline frontier_t0 is the existing FrontierFieldPolicy(threshold=0), called
through the existing factory without rewriting it. Structural is canonical.

## Field definition

Reachable real nodes are (u,m), starting at the current learned product state.
A tried action uses its recorded modal successor and advances task memory at that
known observation. An action with action_visits[(u,a)] == 0 ends at its own
virtual node (u,m,a). No unknown successor is inspected or predicted. A visited
action without recorded evidence is an error, never an invented self-loop.

K_plus assigns probability 1/A to each action at a real node. Virtual rows are
zero: the virtual nodes terminate this computation. All real source entries are
zero. Virtual generic source is 1; task source is exp(task.progress(m)), using
the memory BEFORE the unknown action. q=0.90.

Both fields are computed by ONE sparse LU factorization with TWO right-hand sides.
Select the action with largest successor field; exact numeric ties use smallest
action index, as in the existing executor. No score coefficients are fitted.
If all frontier weights are exactly equal, the task field is a constant multiple
of the generic field. Reuse the generic argmax in that exact case, and log any
raw floating-point tie discrepancy separately, never as task conditioning.

task_signal_available means max(weight)-min(weight) > 1e-12. A field_changed
decision requires the SELECTED task action to differ from the generic
counterfactual at the SAME learned graph/current state/memory. Different numeric
field values alone are not evidence. With no reachable frontier, both versions
use the existing local count fallback and report no virtual-field decision.

## Development pilot, registered before outcomes

- First: archived smoke world 2101. Then sequentially 2202, 2303, 2505.
- Three tasks per type: SEQ, ALL, condition-then, BRANCH. 12/world, 48 total.
- Existing generators, offset 600000: basic seed 720000+world; branch 820000+world.
  Earlier task offsets were 0 and 200000. No outcome filtering or retries.
- Existing 8192 exploration trajectory generates task specifications. All policies
  start from a separate copy of its 512 snapshot. Evaluation can learn online.
- Four policies, fixed order: structural, frontier_t0, virtual_frontier,
  task_virtual_frontier. 192 primary episodes total, at most 4096 interactions
  each (execution plus exploration), exactly the existing online-loop convention.
- All task types and both initially reachable/unreachable tasks remain included.
- Every world's task list is saved before running its policies.
- No world mutations, source-weight tuning, q changes or planner changes.
- Task-off equivalence is tested separately; it is not a fifth primary policy.

## Telemetry and interpretation

Save episode outcomes, capped steps (failure=4096), exploration decisions,
virtual-field decisions, source variation, actual changed actions, tasks with at
least one changed action, generic counterfactual action switches over time,
virtual-node sum/mean/max, LU+solve time, residual, wall/CPU time, sampled RSS and
process high-water RSS (cumulative, NOT a per-episode peak). Save per-decision
sources' extrema, scores, selected/counterfactual actions and product memory.

Primary causal comparison is task_virtual_frontier vs virtual_frontier; only
source weighting differs. Frontier_t0 and structural are reference baselines.
Report paired per-world capped-step and success differences. Do not treat task
rows as independent statistical replications. No significance gate in this pilot.

## Gate, fixed before outcomes

Require unchanged historical tests, the synthetic same-graph/two-task action
test, exact task-off/generic ablation, real signal decisions >0, real changed
actions >0, and acceptable engineering costs. To make the requested terms
auditable, this DEVELOPMENT protocol conservatively defines near-zero signal
as <1% of task-aware exploration decisions; it blocks scaling. This is not a
performance success criterion. Engineering review bounds: <=20x total task-aware
wall time relative to frontier_t0, process high-water RSS <=1 GiB, field residual
<=1e-10. These are review gates, not algorithmic stopping rules or task failures.

All paired caps/successes, wall times and ratios are reported even if a gate fails.
Positive signal but zero changed actions means stop and inspect, not retune.
If the gate passes, freeze this commit/protocol and report before any large run.
The 70-world study must have a separately frozen protocol with world-level paired
inference; this pilot never starts it automatically.

## Provenance and execution

Execute on GitHub Actions. Artifact paths are unique per run. Save exact commit,
source hashes, frozen-path diff check, parameters, seeds, task hashes, tests XML,
raw episodes, mechanism JSONL, logs, per-world results and aggregate gate. A runner
timeout/resource interruption is RUN NOT COMPLETED, never evidence of task failure.
Historical reports remain untouched. No public website change is part of this task.
