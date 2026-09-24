# Frozen integrated predictive comparison

## Scope

This is evaluation and CI plumbing, not a change to the frozen algorithms.
The byte manifest in `configs/integrated-predictive-source-sha.json` comes from
the working-tree freeze `integrated_predictive_world_model_20260924-160455`.
OLD adaptive refinement remains SHA-256
`b7810586055e74af7e7f07e89d911ce27ece84b9ed9dfc1845e565e795a9db9f`.
Git attributes preserve the frozen source bytes across operating systems.

Use the existing `worker-ci.yml` workflow, suite `integrated-predictive`, with
the research commit supplied as both `target_ref` and `expected_sha`.
The workflow never merges to the default branch or deploys the website.

## Inputs and comparisons

The 100 finite and 20 partial-observation cases reuse the complete original
training streams. The five MicroGame cases reuse all 800 saved actions and
re-render raw frames once with the frozen renderer and seed. These are
reconstructed shared raw frames, not previously saved image bytes.
The five legacy visual cases use one 2500-step collector each. No past success
metrics or hidden-state labels are included in packaged training streams.

The preparation job creates train/held-out NPZ files exactly once. All three
conditions consume those files with hash checks. Learners receive only numeric
observations, opaque actions and episode boundaries. The evaluator opens
hidden-state traces only after the fits. Independent held-out uniform-action
streams are generated using predeclared seeds, never a fitted policy.

World-model and memory evaluations use identical saved experience. Complete
systems choose their own actions; their subsequent observations may differ.
Their reset conditions, noise schedules, action sets, objectives and external
interaction budgets are paired. Complete-system results never feed learning.

The complete OLD finite/MicroGame condition is the historical FULL fixed-field
variant (q=.90), not the separate certified-compute ablation. The legacy raw
visual condition retains its test-time prototype updates across trials. Its
world-model-only evaluation uses frozen prototypes. NEW uses the frozen
observed-prefix operator model and existing belief reachability/identification,
not the canceled exact minimal-machine/version-space experiment.

## Measurements and boundaries

- Finite/partial partition metrics share the same external true
  observation-preserving predictive quotient and the same denominators.
- False merge is over-merged pairs divided by truly different pairs; false
  split is over-split pairs divided by truly same pairs. Predictive violation
  is over-merged pairs divided by model-equal pairs. It is not independent
  evidence of false merge.
- MSE is next raw observation error on predictions actually made. Missing
  predictions and coverage are separate. Unknown is never filled with a guess.
- Raw images have noisy, time-dependent observations. Hidden simulator-state
  identity is only a false-merge/split diagnostic, not a proved minimal image
  quotient. A predictive-quotient violation rate is therefore N/A for raw images.
- Same-observation ambiguity uses exact numeric equality, not an invented
  image similarity threshold. Continuous noise can yield zero such pairs.
- Recursive/full-history equality is reported with UNKNOWN and empty-belief
  counts. Agreement alone does not establish memory quality or completeness.
- Action residuals concern observed empirical operators only. A zero residual
  does not prove correctness on unseen environmental transitions.
- The external neutral evaluator uses one least-fixed-point implementation
  for every exported model. Its singleton deterministic case gives graph
  reachability and shortest distance. Guarantees are model-relative; actual
  environment success is reported separately, including success at reset.
- NEW goal-state readouts are introduced after training using observed task
  labels. Mixed task labels cannot certify a whole state as a goal.
- Reference and sweep must agree exactly on the full training and held-out
  symbol assignments, selected features, thresholds, BIC, and leaf means before
  sweep results are used. Reference-check CPU is explicitly charged separately.
- The frozen reference counts action-conditioned response means in BIC; it
  does not separately charge tree predicates or missing routing. This is an
  implementation limitation, not corrected during this comparison.
- Finite observation IDs are scalar numeric features. Their ordinal predicate
  bias is not concealed as a universal perceptual invariance result.

## Capacity and incomplete runs

All historical budgets and full available lags are retained. Before running a
paired case, the runner measures available physical memory and the reference
feature allocation. If the allocation alone exceeds that memory, the case is
`RESOURCE UNAVAILABLE - NOT RUN`. This is not an algorithmic failure or an
impossibility result. No timeout is added to an algorithm. GitHub's own platform
termination remains an external interruption and is `RUN NOT COMPLETED`.

For 2500 transitions, 576 raw dimensions and 5 actions, the unchanged reference
requires 32,694,210,000 bytes for X and its validity mask alone. Actual runner
capacity is recorded rather than inferred from the local computer.

Twenty finite/partial batches and ten independent image jobs preserve per-case
progress and output. A slow image check cannot block a finite case in its batch.
The final artifact contains inputs, frozen source, command lines, metrics,
CSV tables, operator audits, test results and partial-case status. Pipeline job
success does not mean the scientific experiment passed or even fully completed.

## No retuning

No algorithm, threshold, feature family, benchmark seed, or history limit is
changed in response to formal results. Harness tests use separate synthetic
examples. Resource failures, reference mismatches and unknown outcomes remain
visible. This comparison does not claim a fresh blind benchmark: the existing
environments have been used during prior development.
