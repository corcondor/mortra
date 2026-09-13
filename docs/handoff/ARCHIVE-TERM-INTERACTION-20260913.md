# Frozen-Code Archive and Term Interaction: Stage2

This preregisters a configuration-only follow-up, not a new capability claim.
No Python, mathematical primitive, prover, scheduler, retrieval policy or
workflow implementation changes. Mathematical SHA remains
`14d18a42c3a7c640a7c54c86c36b7238c419df56`.

## Why This Experiment

Fresh Actions34725274254 found no extra held-out capability when archive128
became256 at term_size9. Actions34726315203 found no extra capability when
term_size9 became12/14/18/36 at archive128. Neither alone tests the joint
archive256/term12 condition. This small interaction check precedes any new
mathematical mechanism. It must not become an indefinite capacity search.

## Fixed Before Any Learning

The existing `capacity-study` mode and its unchanged
`analyze_capacity_study.py` / `measure_persistent_learning.py` are reused.
The two existing capacity plan files now set term_size12 instead of9.
Their scope note identifies stage2; archive capacity remains their only
difference. For the original stage1 plans use control commit
`4c06d309105495debba6598210e6c42b8f215e69` or its immutable artifact, not the
current branch's stage2 config files.

Both domains run at each capacity, four fresh normal executions in total:

| Fixed quantity | Value |
| --- | --- |
| Mathematical target | full SHA above |
| Domain configs | `theory-ring`, `theory-fold-frames` |
| Archive capacities |128,256|
| Term size |12 AST nodes|
| Seed / held-out seed |20260913 /739182|
| Cycle ceiling / action-body time |12000 /600s|
| Candidate budget / batch / active target |16000 /12 /32|
| Representation count / dimension |4 /24|
| Held-out |same64 questions/domain;32-node prover-input bound|
| Snapshot cycles |0,10,25,50,100,250,500,1000,2000,4000,8000,12000|
| Evaluation repeats / causal replay limit |3 /4|

The prepare command fixes the pair, challenge, oracle and K0 results before
normal learning. K0 must contain both solved and budget-exceeded questions.
No resampling on failure. The learner uses the usual entry with sealed inputs;
it never receives the challenge or diagnostic results. Resumed snapshots retain
cumulative budgets. No process is restarted with altered inputs to repair a run.

Existing evaluations preserve per-task outcomes and source origin, theorem and
concept ancestry, representation-space counts, costs and ablations. In particular,
disable all high-only theorems and their proof descendants on discarded copies.
This tests whether additional acquisitions, not just the initial learned rules,
enable tasks the low condition could not solve. This is not theorem retraction.

## Interpretation and Stop Rule

Primary comparison: archive128 versus256 at term12 in this one fresh Actions run.
Secondary interaction: contrast that deterministic capability difference with
stage1's archive difference at term9. Require identical challenge hashes,
mathematical source seals, seeds and other budgets before comparing. Stage1 and
stage2 are different jobs: do not pool their wall times as a controlled timing
effect. Exact inspection/prover counters and per-task outcomes remain comparable
with their recorded conditions. A positive interaction requires new held-out
success attributable to the additional acquisitions, or a deeper verified
dependency chain; counts alone do not suffice.

The600s action-body timeout is retained. A run that stops before a checkpoint
is censored there, not a completed equal-cycle experiment. Reporting must separate
normal computation, proof/replay cost, evaluation, startup and snapshot overhead.
No source change is allowed during any test. Stop and report failed infrastructure
as a failed run; do not mix a repaired continuation into it.

After the four executions, classify the joint effect once. If negative, do not
launch larger capacities or additional seeds automatically. Return to the
evidence-backed minimal-change proposal; no index or solver is implemented here.

## Dispatch and Records

Use the existing workflow, from the stage2 control commit:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra --ref codex/theory-formation-20260913 -f verification_suite=capacity-study -f target_ref=14d18a42c3a7c640a7c54c86c36b7238c419df56 -f expected_sha=14d18a42c3a7c640a7c54c86c36b7238c419df56
```

The Actions run records control/target SHA, all commands, dependencies, fixed
plans, source seals, challenges, normal states, trajectories, replay, ablations
and fresh q-directed acquisition/reuse/refusal checks. No previously saved log
is used to pass this run. Stage1 results remain explicitly historical to stage2.
