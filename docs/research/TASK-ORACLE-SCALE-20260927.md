# Oracle source replication and fresh 280-world diagnostic

This protocol is fixed before replication or fresh policy outcomes. It does not
introduce a learned source estimator. Both oracle arms are privileged diagnostics,
not deployable policies, and neither is claimed to be a mathematical upper bound.

## Frozen components

The Player, StructuralLearner, environment, generator, task generator, task
memory, known-path planner, q=0.90, tie handling, and online loop are imported
unchanged from commit 24c44da50aac2c084a91fdd9f6754f0429da9350. Source byte
equality is checked. The fresh70 registration helpers are also kept unchanged.
Only new files and user-supplied reference data are added.

## Mandatory replication gate

Reuse registration artifact fresh70-registration-36220511321 from run 36220511321.
Run all 65 task-generatable worlds, 12 tasks each, under all four conditions.
The five unavailable worlds remain recorded, not replaced. Match capped steps
and success flags against the user-supplied 780-row headroom and source files.
Any difference prevents the fresh experiment. Do not change formulas to fit
outcomes. If an engineering error or source mismatch occurs, retain it and report.
The user supplied run_oracle_headroom.py and run_oracle_source_linear_shard.py
before any experiment execution. Their bytes and SHA-256 are preserved. An AST
loader executes only the unmodified imports/class/function definitions and the
four original constants, not their original top-level /mnt/data batch loops.
The oracle functions are called unchanged by an adapter around the canonical
frozen OnlineTaskAgent. Exact row-level reproduction is mandatory.

## Fresh cohort, fixed before outcomes

- World seeds: 77000000 through 77000279 inclusive (280 worlds, no replacement).
- Same frozen generate(random.Random(seed)); no mutation, selection, or filtering.
- Same frozen train_snapshots; start each episode from the saved 512-step model.
- Task generation uses the 8192-step snapshot, basic seed world+720000,
  branch seed world+820000, and three tasks per type (12 total).
- All 280 genomes are fixed and hashed before policy outcomes. Each world's
  snapshot and full task set are saved before any policy evaluation for that world.
- Identical private initial learner copies, task, environment, and start for all
  four policies. Later experiences may differ as policies act differently.
- Max task/exploration steps are both the frozen 4096. Failure-capped steps are
  4096. The original last-step acceptance behavior is preserved.
- Use four conditions: generic, current_task, oracle_source, oracle_direct.
- Generic/current are unchanged VirtualFrontierPolicy conditions.
- Oracle distance uses the supplied exact BFS on the true world x updated task-memory graph.
  d(f) excludes the unknown action itself and includes the entire remaining task.
  The supplied code represents unreachable distance by 10**9 and maps distances
  >=10**8 to source zero. These original sentinels are retained, not tuned.
  The oracle closes the world from all initially learned states and initializes
  its task-product closure from every world state, exactly as supplied.
- Oracle source replaces ONLY the source on virtual terminal nodes with q**d(f).
  Known learned graph, uniform action kernel, sparse solver and argmax remain.
  No-virtual fallback remains the frozen local count policy.
- Direct oracle chooses the action with minimum remaining true task distance,
  then minimum action ID. It is used ONLY when the frozen agent asks to explore.
  The existing learned planner resumes when it finds an accepting support path.
- Neither oracle writes any true transitions into the learner. Only actual
  executed actions update the learner.
- No new semantic cutoff, learning threshold, q function, or tuning.

## Analysis

Primary diagnostic contrast: mean capped steps, oracle_source minus generic,
paired by world after averaging the 12 tasks. Also report current, direct oracle,
successes, medians, task-type strata, and all worse cases.

Report the ratio (generic-source)/(generic-direct) only when its denominator is
positive. It is a ratio of aggregate differences, not a causal attribution or
an average of per-task ratios. World bootstrap uses numpy default_rng(77100000),
20,000 resamples and percentile 95% intervals, jointly resampling four methods.
No outcome-derived success threshold is introduced. Previous 65 worlds are a
replication cohort, never pooled with fresh worlds in the primary report.

Task generation unavailability is not policy failure. No worlds are replaced.
If any of the 280 worlds lacks its full task set or execution, the full-cohort
analysis is INCOMPLETE. Report completed worlds/280 and their conditional
descriptive statistics separately. Engineering interruption or resource limits
are RUN INCOMPLETE, never a task failure. GitHub's external job limit is not a
mathematical stopping criterion.

## Outputs and scope

Save source/input SHA-256, branch/HEAD, config, RNG seeds, genomes, tasks,
snapshots, every episode/action trajectory, exploration telemetry, wall/CPU time,
process peak memory, reproduction differences, paired world/task tables and plots.
Preserve all partial records and failures. No outcome-driven algorithm revision.
This is a finite symbolic-state diagnostic, not raw perception, an autonomous
value learner, or evidence of general intelligence. Do not claim oracle knowledge
is available to a practical agent.
