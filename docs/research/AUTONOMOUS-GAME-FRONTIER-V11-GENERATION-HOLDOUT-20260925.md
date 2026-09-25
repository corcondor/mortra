# Archived G0-G10 holdout audit: preregistration

This audit evaluates all 88 seed-generation entries of the MORTRA-performance
condition from Actions run 36080469660, source c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902.
There are 47 distinct (seed, genome hash) cases. No generation, mutation,
selection, or player changes are permitted. The original 18 source files,
and the previously validated holdout harness, remain unchanged.

## Sampling fixed before execution

- Seeds: 201, 302, 403, 504, 605, 706, 807, 908. Generations: G0 through G10.
- New task seed root: 2026092502; derive(root, seed, game_hash, 'generation-holdout').
- Request 500 distinct ordered start-target pairs per world, distance at least 4.
- Use the original reservoir sampler with bins 4-7, 8-15, 16-31, 32+;
  equal quotas and seeded redistribution of unavailable quota.
- Exclude the union of all same-genome Stage 1/2 selection candidate and
  initial-pool task pairs, and all same-genome tasks in the preceding
  final-world holdout audit (run 36085588461).
- If fewer than 500 remain, evaluate their census. Never pad or regenerate.
- A retained identical world has one identical task set and measurement across
  its generations. Such repetitions are not independent observations.
- Freeze every task set, source checksum and input artifact checksum before
  running any player. Oracle distances are evaluator-only.

## Unchanged execution

Execute frozen learn bytecode with original player seed and selection tasks.
At every original budget (1,2,4,...,8192), require exact reproduction of archived
learner fingerprints, transition matrix hashes, all task outcomes and recorded
solver outputs. Holdout evaluation uses that same frozen learner and a copied
opaque-label registry. It does not modify training, evaluation rules or budgets.
q=0.90, action cutoff=1e-7, solver defaults and action horizon=2048 are unchanged.

Run complete-graph diagnostics separately. Reproduce original selection
full-information outputs exactly, then evaluate the new holdout tasks using
the identical full-information core. Never feed oracle edges into training.

## Measures and interpretation

- S(B): task success fraction at each budget.
- B50/B80/B90: first observed crossing. Null is right censoring at 8192,
  not evidence of impossibility, and not an extrapolated budget.
- D: trapezoidal integral of 1-S over log2 budget. Larger D means a larger
  unsolved area; it can also reflect persistent failure. Trend signs use exact
  rational success counts rather than a tuned floating-point tolerance.
- Report every generation's selection and holdout curves, B thresholds, D,
  full-information success and full task-distance distribution.
- Compare G0 and G10 unconditionally. Count all ten increases/decreases/ties.
  Also describe the interval from the first originally selection-eligible world;
  do not replace the requested G0 comparison with this secondary comparison.
- Use original classification: full-information success below .8 is
  REASONER_LIMITED; otherwise learned below .8 is EXPLORATION_LIMITED;
  otherwise LEARNED_SUCCESS. These are protocol labels, not proofs of sole cause.
- Report per-task learned/full-information success contingency at every budget.
  Full information is not mathematically an upper bound on this core's success.
- Compute D separately on tasks solved by the full-information core and tasks
  it fails. This diagnoses, but does not eliminate, changing task composition.
- Report whether difficulty increases while full-information success does not
  decline, and whether increases persist on the full-information-solvable subset.
- Report 706/807/908 in full. Do not choose successful seeds or generations.
- Different worlds have different task populations. Distance distributions and
  common-bin selection-vs-holdout standardization are reported, not concealed.
- This is a within-performance-arm audit. It cannot alone estimate a causal
  advantage over random selection or prove universal hardening.

## Outputs and stopping

New reports/autonomous_game_frontier_v11_generation_holdout/ only. Preserve
all old artifacts. Save frozen bundles, provenance, RNG seeds, logs, individual
task results, complete curves, classification, oracle distances, generation
changes, summary tables and plots. Replay saved task 0 traces against the
unchanged engine as an integrity check, never search for a replacement example.
Stop after all archived cases and reporting; no outcome-conditioned tuning.
