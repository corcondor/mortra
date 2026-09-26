# Preregistration: 70 fresh worlds, virtual-frontier task weighting

Registered on 2026-09-26 before generating these worlds or running outcomes.
The Git commit containing this document is the immutable registration timestamp.
This is a new study, not an extension of the development-pilot sample.

## Frozen implementation

Development algorithm commit: `24c44da50aac2c084a91fdd9f6754f0429da9350`.
Pilot report-only commit: `3b69e943531e7d3b182442e43a245f0cdbdcc65a`.
No historical file is modified. The new harness imports the exact pilot
`episode` function, which makes private deep copies of the starting learner.
Its unchanged online executor, execution planner, canonical StructuralLearner,
action ties, q=0.90, numerical tolerance, task semantics, virtual frontier
construction and task source `exp(task.progress(memory_before_unknown_action))`
remain frozen. Both execution and exploration caps remain 4096; failed episodes
cost 4096 steps. No old task_conditioned_t0 results enter this comparison.

Byte identity with the development commit is checked before tests, registration,
and policy evaluation. All 41 existing pilot tests and the new harness tests
must pass before world registration/evaluation. New tests use only synthetic
fixtures and an archived pilot world, never the 70 evaluation seeds.

## Sampling and immutable inputs

The exact world seed list is the 70 consecutive integers
`73000000, 73000001, ..., 73000069` (inclusive). This range is new to this study.
No seed is chosen by inspecting a generated world or a policy result.
The existing finite-program-v1.1 `designer.generate(random.Random(seed))`
is called once per seed. No mutation, evolution, difficulty filtering,
solvability filtering, or selection is performed. This samples the unselected
generator distribution, not the archived evolution-selected world distribution.
Claims cannot silently equate these populations.

Each genome and its file SHA-256/canonical game hash are saved before task
construction. Hash overlap with the eight archived worlds or within the fresh
cohort stops evaluation as a freshness violation; seeds are not replaced.
Generation engineering failure is retained as RUN INCOMPLETE, without replacement.
This stricter no-replacement rule also covers all structural/task failures.

For each world, call the frozen `train_snapshots` once for the unchanged
512/2048/4096/8192 checkpoints. Save the exact 512-step learner attributes,
including dictionary insertion order and transition counts. A JSON round trip
must preserve all learner attributes exactly. All policy tasks start with private
copies of this SAME snapshot; no task shares experience with another.
The 8192 snapshot is used by the task generator only, never passed to a policy.

Task generation is exactly the development-pilot protocol: three tasks each of
sequence, all_of, condition_then, and branch, 12 tasks per complete world.
Basic task seed = world seed + 720000. Branch seed = world seed + 820000.
The frozen basic generator's 50000 attempts and branch generator's 100000
attempts are unchanged, including 3-10 step subgoal constraints and branch
path-length contrasts. Duplicate task specs, if generated, are retained.
No task is filtered on accepting paths, exploration, source variation,
performance, or action changes. Save all returned task specs and their SHA-256.
ALL 70 worlds finish input registration before ANY policy outcome is evaluated.

If either generator cannot produce its full quota, retain the world as
`task_generation_unavailable`. Save returned specs from any successful generator,
the exception, and structural diagnostics, but do not run a reduced task set.
This is a benchmark-construction outcome, NOT a policy failure.
Categories: insufficient_reachable_states; no_eligible_3_10_step_target;
no_eligible_branch_construction; insufficient_branch_path_length_contrast;
other_deterministic_generator_failure. Diagnostics use the same 8192 learned
graph only after failure and do not extend attempts. A search-limit failure is
not a proof that the full environment admits no such task.

If fewer than 70 worlds have full registered task sets and complete paired
policy results, the 70-world confirmatory analysis is INCOMPLETE. Never redefine
its sample size. Completed task-generatable worlds may have a separate PARTIAL /
DESCRIPTIVE analysis labelled `analyzable worlds / 70 fixed worlds`; this is a
conditional population and cannot prove the original confirmatory claim.

## Policies and execution

Fixed order per task: structural, frontier_t0, virtual_frontier,
task_virtual_frontier. Runtime comparisons are engineering diagnostics subject
to fixed-order/caching effects. Four policy copies share no mutable state.
Fourteen shards each process five consecutive world seeds, sequentially within
a shard, at most four shards concurrently. A world is never selectively rerun.
Infrastructure errors preserve partial rows/telemetry and are RUN INCOMPLETE,
not failed agent episodes. A platform timeout is not a mathematical failure.

## Estimands and statistical analysis

One world, not one task, is the independent primary sampling unit. Let C(p,w,t)
be task steps if the frozen executor reports success, otherwise 4096.

Primary: D_w = mean_t[C(task_virtual_frontier,w,t)-C(virtual_frontier,w,t)].
Secondary: G_w = mean_t[C(virtual_frontier,w,t)-C(frontier_t0,w,t)].
Relative: R_w = D_w / mean_t C(virtual_frontier,w,t).
Negative values mean the first named policy uses fewer steps.

For D and G report mean, median, 95% world-bootstrap CI for the mean,
counts of negative/positive/exact-zero worlds and every raw world value.
For each paired contrast report per-world success-rate differences separately.
Task-level wins/losses/ties are descriptive only.

Bootstrap: 20000 draws of N worlds with replacement, NumPy default_rng seed
74000000, percentile .025/.975 with linear quantiles. Use the registered world
order. The same draw stream is used for each endpoint. No task-row bootstrap.
Partial descriptive CIs, if available, condition on the completed subset and
are explicitly not confirmatory 70-world intervals.

Practical equivalence is preregistered at +/-5% of each world's generic mean
capped cost, a five-percent operational tolerance chosen before outcomes.
Declare confirmatory practical equivalence iff all 70 worlds are complete and
the 95% bootstrap CI for mean R_w lies wholly inside [-0.05,+0.05].
A zero denominator makes R_w undefined and prevents an equivalence declaration;
do not drop it silently. Nonsignificance alone is NOT equivalence.
For directional primary benefit/harm the 95% D CI must lie below/above zero.
These are separate endpoints; multiple secondary diagnostics are not a new
combined pass/fail criterion. No post-hoc success threshold such as 7/8 seeds.

## Mechanism

Save per-world exploration decisions, source-variation decisions and fraction,
same-state generic-counterfactual action changes and fraction (both all decisions
and signal-present decisions), tasks/worlds with changes, virtual-node counts,
field residuals and solve time. Keep each per-decision JSONL row, including
generic and task-weighted scores/actions. Diverged trajectories are NOT the
counterfactual test. Zero-denominator fractions are null, not invented zeros.

Interpret separately: absent task information; available information with weak
behavioral effect; behavior changed with practically equivalent performance;
performance improved/harmed under the frozen world-level test. Report actual
fractions rather than selecting a convenient post-outcome "rare" threshold.
Inconclusive confidence intervals remain inconclusive.

## Preservation and stopping

Save registration, source SHA/hash, 70 seeds, genomes and hashes, task seeds/
specs/hashes, snapshot hashes, configuration, raw episodes, per-decision JSONL,
paired task/world tables, mechanisms, compute, aggregate report, test XML/log,
workflow logs and original artifact ZIP/digest. Process peak RSS is cumulative
within a shard, not isolated per-policy allocation. Preserve partial outputs.
Use new run-specific outputs; no historical output or source is overwritten.
After this study report results and stop. No tuning, outlier removal, selective
reruns, policy/source/budget/criterion changes, or replacements after outcomes.
