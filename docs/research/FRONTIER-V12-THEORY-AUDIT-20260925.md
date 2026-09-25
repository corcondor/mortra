# Frontier v1.2 Theory and Mutation Reward Landscape Preregistration

Source: official run 36107649938, commit c060d5c9549eaae913bd7b9555ad2289ff96ff8c.
All 18 v1.1 protected files and all archived v1.2 source hashes must match.
No Player, proposal learner, reward, selection, generator, primitive, task sampler,
q, cutoff or evolution changes. No parent updates. Counterfactual candidates are
discarded after measurement; immutable evaluation records are archived for audit.

## Source gate

Restore all 32 saved runs, all 193 world bundles and completed holdout audits.
Verify hash manifests, UCB history replay, 88 Adaptive generation references,
selection values, holdout values, published aggregate values and task exclusion.
Stop before counterfactual measurements if any reproduction fails.
Read large artifacts sequentially, not as one in-memory dataset.

## Fixed measurement plan

Stage 0: source gate and unit tests. Stage 1: Adaptive seed 2101 worlds at G0,
G5 and G10, 14 primitives x 5 replicates each. Run the difficulty diagnostics and
full-information field diagnostics. Gate only correctness and output completeness.

Stage 2: all unique (seed,parent hash,context) among Adaptive G0..G10 from the eight
registered seeds 2101,2202,2303,2404,2505,2606,2707,2808. Always 10 replicates per
primitive. No outcome-based cap, retries, extra successful samples or tuning.
Identical parents at multiple generations share measurements, not independent
evidence. Restore each recorded pre-slot UCB distribution separately. G10 has no
actual next proposal: its post-run distribution is labelled hypothetical and
excluded from the primary comparison of actual proposals.

Mutation RNG is derive(parent hash,primitive,replicate,'reward-landscape-v1'),
consuming the frozen scheduler's initial uniform-family draw before forcing the
specified primitive. Evaluation retains the original world seed and frozen
prepare/train_candidate functions. No holdout is present in evaluation inputs.
All invalid/no-op/ineligible outcomes retain the frozen reward and consume their
single replicate. The fixed oracle/dense-matrix guards remain in force. External
resource or job interruption is RUN_NOT_COMPLETED, not a task failure.

## Estimands and ties

Operator means are finite 10-replicate estimates, not known true expectations.
Within-arm variance uses ddof=1, between estimated arm means ddof=0. SNR uses
machine epsilon, recorded in config. Also report the untruncated estimate
between variance minus mean within variance/replicates; small samples can inflate
apparent between-arm signal. Correlations with a constant vector are undefined,
not zero. Untried UCB scores are ranked as +infinity, tied. Top-1 regret is averaged
over proposal maximizer ties, with minimum/maximum regret also reported. Top-3
overlap is the expected overlap under independent uniform boundary tie breaking.

Actual pre-slot distributions are compared to operator estimates at their parent.
Primary summaries weight the eight seed means equally. Report distributions and
an exploratory percentile bootstrap of the eight seed clusters (10000 draws),
without a significance/pass threshold. Candidate/task/generation rows are not
treated as independent evolution experiments. Unweighted sample count is reported
as nominal ESS; dependence-adjusted information ESS is not identified.

Cross-world correlations use distinct parent pairs. Adjacent and distant relations
refer to actual generation references; these categories can overlap when a world
is retained. Same-world repetitions are not evidence of cross-world stability.

## Difficulty and selection

Analyze all saved unique worlds, selection and holdout separately. For task success
y_i and x_i=log2 B_i, D_j=sum (x_{i+1}-x_i)(1-(y_i+y_{i+1})/2).
Let k be first success, or right-censored at the last checkpoint. Then exactly:
D_j = capped first-success log budget - half first-hit interval
      + area of (ever-succeeded indicator - current-success indicator).
The last term vanishes for monotone tasks. Never infer beyond-budget thresholds.

Join candidate holdout values only where they already exist in saved frontier
audits. Label this selection-biased observed subset. Do not generate missing
candidate holdout values. Predict normal max-8 response or empirical resampling
only for complete eight-candidate (X,Y) pools. If absent, explicitly report
NOT ESTIMABLE. Compute E[max of 8 standard normals] by numerical integration.
The real selection also uses eligibility, an incumbent parent and tie criteria:
the normal formula is an approximation, not an identity of the algorithm.

## Fixed-field diagnostics

All 193 saved unique frontier worlds, each saved selection and holdout full-info
task. Reconstruct full-info K and replay original policy bytecode; assert saved
success, reasons, step counts and trajectory hashes. No new Player decisions are
substituted. The separately labelled linear solve uses sparse LU of I-.9K.
For complete deterministic graphs, K is row stochastic: spectral radius=1 and
nonnegative resolvent infinity norm=10; measure row-sum and solve residuals.

One deterministic BFS shortest path gives a single nonnegative term in the
Neumann path sum. Its falling below cutoff alone does not imply total-field or
planning failure. Above cutoff it is an exact-field lower bound, not a guarantee
for the finite-tolerance implemented policy. Keep the approximate implemented
field, exact linear solve, cutoff failures and post-start readout failures separate.

## Outputs and stopping

Preserve source manifests, registered seeds, each candidate outcome, estimated
operator landscape, all calibration snapshots, context counts/bonuses, pathology,
difficulty identities, selection-response missingness and field diagnostics.
Produce the requested 12 figures and Japanese report with facts, identities,
approximations, agreement, disagreement and claim boundaries separated.
Stop after Stage 2. No algorithm revisions based on audit outcomes.
