# Frontier v1.1 Independent Evolution Replication

## Preregistration

New independent seeds: 1101,1202,1303,1404,1505,1606,1707,1808.
No old worlds, candidates, tasks, or selection histories are loaded. Only frozen
code and the previously fixed protocol are reused. No outcome-based parameter
adjustments and no experiment-level pass criterion are introduced.

The evolutionary implementation is the v1.1 source at
c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902. All 18 source hashes must match.
The wrapper executes the original run_seed bytecode with the sole configuration
difference being the seed list. It does not monkey-patch the player, generator,
mutation, fitness, selection, evaluation, or shared module globals.

Stage 2 conditions are unchanged: 32 initial candidates, a shared freshly drawn
G0 per seed across mortra/random/size_only, ten generations, eight mutation
slots per generation, 100 registered selection tasks per candidate,
checkpoints 1,2,4,...,8192, q=.90, cutoff=1e-7, action horizon 2048,
oracle cap 250000, dense-K guard 512 MiB. Mutation families, initial-world
eligibility and tie rules are unchanged. Selection tasks are registered by the
unchanged deterministic seed derivation, generated before each candidate is
played, and saved. No holdout outcomes are available during selection.

No extra G0 attempts are allowed if the frozen initial pool has no eligible
world. Resource interruption is RUN_NOT_COMPLETED, not a task failure. The
workflow infrastructure limit remains six hours per job as in the original.

## Holdout audit

Only after all eight seeds and all three conditions finish evolution, read
those new artifacts. Freeze 500 unused distance>=4 start-target pairs per
frontier world using the frozen four distance bins, reservoir sampling and
redistribution. Keep the prior holdout seed root 2026092502 and derivation
derive(root, new_seed, genome_hash, 'generation-holdout'). Only the new evolution
seed changes the random stream. Exclude the union of same-genome selection
pairs from this replication's initial pools and all candidates in all arms.
Do not read earlier experiments for exclusions or reuse.

If fewer than 500 eligible unused pairs exist, keep their census without
replacement, regeneration or padding; report the denominator. Empty sets are
unmeasured. Identical (seed, genome) instances share one task set across arms
and generations. They are not independent replicate observations.

Reproduce all new selection checkpoints using the original learner and then
evaluate the new holdout on that same learner with an isolated observation-ID
registry. Require exact fingerprints, K hashes, task results, solver outputs
and full-information selection diagnostics. Evaluate holdout full information
with a separate complete graph. Do not supply this graph to training.

## Five primary endpoints

1. Count seeds where holdout D increases from the first performance-eligible
   frontier generation to G10. Use valid + full-info>=.8 + learned>=.8 for all
   arms so the comparator is common. For MORTRA and size-only this is native
   selection eligibility. Also save random's native validity-only eligibility.
   A seed with no eligible generation is separately reported, not silently
   omitted; first eligibility at G10 yields a tie.
2. Among changed-world transitions with strictly increasing frozen selection
   D, report the fraction with increasing holdout D. Show numerator and
   denominator, ties/decreases, all changed transitions and missing outcomes.
   No minimum pass fraction is defined. If any denominator outcomes are
   unmeasured, report bounds rather than substituting failure.
3. Final holdout success by seed, condition, macro average and pooled counts.
4. Compare the three arms on those same endpoints, paired by new seed.
5. Report LEARNED_SUCCESS / EXPLORATION_LIMITED / REASONER_LIMITED using the
   frozen 80% classification, separately for final worlds, all generation
   entries and unique worlds. It is not an experiment pass criterion.

D remains the trapezoidal integral of 1-S over log2 budget. B50/80/90 are first
observed crossings, null if not reached by 8192. Holdout D trend signs use exact
rational success counts. The selection-D increase criterion uses the unchanged
fitness's strict floating-point comparison, with no new epsilon.

## Diagnostics and stopping

Save oracle distances/populations, all curves, B thresholds, per-task success,
full-information success, learned/full-info contingency and core-solvable D.
Full information is a diagnostic, not a guaranteed upper bound for the frozen
fixed-field core. Difficulty can include persistent failure. Missing distance
bins and sampling variation limit comparisons; do not claim significance of
every small empirical increase.

All outputs use a new replication directory and GitHub run. Preserve existing
reports. Save source snapshots, config, RNG seeds, manifests, evolution logs,
holdout logs, checksums, endpoint tables and plots. Verify saved task-zero traces
against the frozen engine. Stop after this replication and reporting. Never
retune the Player, generator or fitness after seeing outcomes.
