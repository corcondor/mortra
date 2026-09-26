# Task-blind pretraining action selection: reproduction, then fresh64

This specification is committed before running the new reproduction or fresh
policies. It is not a claim of external preregistration. The supplied smoke is
a historical development experiment, not holdout evidence. No outcome-dependent
changes to algorithms, tasks, budgets, stopping, or analysis are permitted.

## Sources and scope

- Report checkout: `154f7a62988a52265b17c4dd0ad02839c9e32cc3`.
- Algorithm baseline: `24c44da50aac2c084a91fdd9f6754f0429da9350`.
- Original ZIP SHA256: `b483aeb976826ac993a17dde0e43b45e4fbf7b2c86776e22f24566f6f97ccf64`.
- Only `vendor/experiments/task_agent/pretraining.py` is installed into the
  canonical `experiments/task_agent/pretraining.py`, byte-for-byte. Its digest
  is `c0c8473c806e1a66ec6cbde2e9ced1afd3b4ae10b70d61b7f7c0b618e10c6177`.
- No supplied loader or alternative game module replaces canonical code.
  The unchanged ZIP is retained as evidence. Isolated test fixtures contain its
  original files, but canonical imports are checked not to use their vendor/.
- StructuralLearner updates, counts, dest_map, policy-specific node_visits,
  exploration, virtual_frontier, core, online, online_eval, q=0.90, source=1,
  tie-breaking, and final-step acceptance behavior remain unchanged.
- SingletonMemory retains its exception on progress/accepting calls. Initial
  training is task-blind. Only outcomes of executed actions reach the recorder.
- No source estimator, neural network, semantic feature, normalized readout,
  new exploration rule, oracle source, or self-extension mechanism is added.

## Mandatory exact reproduction gate

Runtime: Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2;
record compiler, platform, numerical-library build, and thread settings too.
Different builds are not assumed bit-identical. No tolerance is introduced.

A runs the untouched ZIP's README/reproduce_local.py in a new directory.
B runs its unchanged tests, evaluator, and runner through canonical imports.
Only import wiring changes in B: bootstrap is an in-memory no-op; the two
reference_loader class names alias canonical StructuralLearner and Engine.
These aliases are not installed in the repository. Test bodies are unchanged.
Canonical related existing tests run unchanged in a separate invocation.

Both routes compare seeds 73000000..73000007, methods structural/frontier_t0/
virtual_frontier, budgets 128/512/2048, and all 12 fixed stored tasks per world.
Required checks are 35 bundled tests, 8 structural512 models including ordered
dictionaries, 96 historical generic episodes (success/steps/exploration), 864
unique exact episode keys and all non-timing columns, 72 complete snapshots,
49,152 training trace rows, and the complete evaluation trace. Numerical trace
values are compared exactly too. Every mismatch is saved, not rounded away.
Training and evaluation traces are independently replayed by the supplied audit.
No fresh input generation or policy comparison runs if either route mismatches
or is incomplete. Tests alone never count as 864-row reproduction.

## Fresh input registration before comparison outcomes

Fixed candidate world seeds: 78000000..78000063, ascending, never substituted
after observing structure or performance. Check available registration histories
for seed and genome overlap and record the histories/digests used. A previously
used seed range is not fresh; a different unused range would require a separate
commit before any outcomes. A genome collision is recorded and stops fresh
execution without replacement.

Use canonical frozen designer.generate and Engine, without evolution, selection,
or difficulty filtering. All 64 genomes are saved first. Per world, generate
tasks once using the canonical 8192-step structural model: basic seed = world
seed+720000, branch seed = world seed+820000, three each of sequence/all_of/
condition_then/branch. Keep canonical 3..10 distance conditions, basic limit
50,000 and branch limit 100,000. Register all task specs, generation status,
failure category, source versions, and input hashes before running any arm.
The 8192-step reference model never enters any comparison learner.

Task-generation-unavailable worlds stay in the fixed cohort. No replacement,
quota relaxation, or partial task sets are evaluated. Fewer than 64 fully
evaluated worlds means the fixed-64 confirmatory analysis is INCOMPLETE. All
evaluable worlds still receive conditional descriptive analysis with n/64 shown.

## Comparison

Each world/method starts empty at the same initial state and takes one continuous
2048-step training trajectory. Snapshots at 128, 512, 2048 are nested; do not
retrain per budget or leak later experience backward.

1. structural: original StructuralLearner.select_action.
2. frontier_t0: existing FrontierFieldPolicy(low_count_threshold=0).
3. virtual_frontier: existing VirtualFrontierPolicy(task_aware=False,
   task_source=False), singleton task memory and source one.

Every downstream trial uses the unchanged supplied evaluator: private deepcopy
of its budget snapshot, CachingSparsePlanner, OnlineTaskAgent, generic
VirtualFrontierPolicy, q=0.90, task/exploration caps4096. Its existing online
updates are allowed; experience is not shared across tasks. Same12 tasks/starts.
Maximum complete count: 64*3*3*12=6912. Maximum pretraining steps per world/arm:
2048, not128+512+2048. Preserve the original final-step rule and separately
report acceptance-memory versus reported-success discrepancies.

## Analysis fixed before fresh outcomes

512 is primary because the development pilot showed an effect there; it was
not chosen blind to pilot results. 128 and2048 are secondary and never replace it.
Failure cost4096; success costactual steps. Report success separately.

Primary per-world contrast:
`D_w = mean_t[C(virtual,w,512,t)-C(frontier_t0,w,512,t)]`.
Fixed secondary: virtual minus structural. Do not omit frontier_t0.
Independent unit is world, not task or budget. Report paired mean/median,
improved/equal/worse worlds, and every raw difference. Bootstrap20000 world
resamples, RNG seed78100000, percentile95% CI (linear quantiles), one common
resampling index matrix for all methods and budgets. CI wholly negative supports
lower mean task cost in the analyzed population; crossing zero means superiority
unconfirmed, not equivalence. If INCOMPLETE, all intervals are conditional
descriptive and cannot support the fixed64 confirmatory claim.

Report for each budget/method: success numerator/denominator, mean cappedcost,
initial accepting-path count (not a filter), learned state and attempted
state-action counts (not true coverage), B+sum(C_t), B/12+mean(C_t), and separately
B+mean(C_t) for training anew for a single task. Report prefix cumulative training
CPU, evaluationCPU, totalCPU, memory, all worsening tasks, worst regression,
and success differences. Never charge2048 trainingCPU to512. Never combine
environment actions andCPU with an arbitrary weighted score. Fixed method
order and shared-worker timing are diagnostics, not a rigorous speed benchmark.

## Execution, preservation, stopping

GitHubActions: reproduction gate, input registration, eight world-unit shards
(8worlds/shard, max-parallel4), aggregation. BLAS/OMP/MKL threads1. Save exact
commits, all input hashes/seeds/genomes/specs, all model snapshots/training traces,
evaluation actions/raw episodes, world-paired summaries, testXML/logs, every
reproduction mismatch, resource logs, original ZIP/digest, attempt metadata.
Run-specific output directories never replace original records.

Infrastructure interruption is incomplete, not a policy failure. No selective
rerun of completed worlds. Resume only unfinished units on identical code/inputs,
with original logs, attempt number, and cause retained. Audit duplicate/missing
keys, snapshot pollution, training task access, and terminal acceptance.
The first cloud run can contain only the reproduction gate: fresh jobs must
remain absent/blocked until exact reproduction passes. Fresh orchestration may
then be committed without changing this specification or any algorithm.

After results, stop. Fresh virtual beating both baselines with acceptable
success/regressions/compute makes it an adoption candidate. Beating structural
only does not establish virtual-specific benefit over frontier_t0. If not
reproduced, do not adopt or pivot to another model in this run. Any tuning is a
separately registered development experiment. Do not claim source learning,
general self-extension, or transfer to mathematics/images from this experiment.
