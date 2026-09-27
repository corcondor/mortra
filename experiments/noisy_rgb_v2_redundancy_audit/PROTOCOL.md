# Depth-2 ceiling + provisional redundancy audit

## Frozen scope

This is a diagnostic, not a new learning method. Do not launch fresh seeds,
V2.1, bucket sharing, adaptive-depth acquisition, or sensor-program search.
Do not change or cancel upstream development run 36309862254, execution
3e777cd5274a30e3119c125a932a6bbca98e1830. Wait until the whole run terminates.
Audit every available saved V2 condition, all 32 fixed seeds x 2 cameras,
retaining missing/incomplete conditions explicitly. No performance selection.
The first-condition claims in the request are hypotheses to reconcile with
saved files, not numbers to insert into outputs.

All acquisition, threshold, stability, depth-2/31-experiment merge, physics,
goal, camera, and evaluation code remains unchanged. New code lives only in
the post-freeze audit package. The gate checks this against the execution SHA.

## No new environment experience

No Sensor, Statistics sampling, noisy_rgb, noisy_batch, interactive step, or
learner execution is permitted. The artifact reader fetches selected ZIP
members using HTTP ranges, not the roughly 14GB raw archives. Check selected
members against their saved SHA-256 manifests and ZIP CRC. Record the GitHub
artifact digest without falsely claiming to have recomputed the full archive
digest from partial downloads. Original artifacts are never overwritten.

Saved snapshots do not contain a complete true transition/output table.
Therefore the evaluator constructs that table by statically evaluating the
frozen pure raw_step(s,a) on explicit immutable tuples and the deterministic
clean renderer/public-goal function. This is offline model semantics, not an
agent trajectory, a new stochastic exposure, or acquired evidence. Record
these static function evaluations separately; interactive actions/exposures
and learner updates remain zero. Never pass this table back to a learner.

## Structural depth audit

Let O(s) be the four clean 12x12 RGB views plus the public goal label. No
terminal API exists, so do not invent a terminal value. P0 equates O; recursively
P(d+1) equates (O(s), P_d(T_0(s)), ..., P_d(T_4(s))). Thus P2 is exactly equality
on epsilon, a, and a1a2: 31 experiments. Check P2 independently by exhaustive
enumeration of these words. Report |P0| through |P6| and the fixed-point
observation-preserving predictive quotient |P_infinity|. Also report the old
RGB-only quotient, since earlier ground-truth summaries omitted public labels.

For each distinct P_infinity class pair, compute the first refinement depth
where it separates and retain a shortest distinguishing word. Verify its
endpoint outputs differ and the preceding partition did not separate the
pair. Fixed-point computation yields an exact finite structural witness depth;
report counts beyond 2 and beyond 6 explicitly. No depth is added to the learner.

Important limits: this is a CLEAN-OUTPUT structural ceiling for a fixed test
bank, not a proof of equality/inequality of complete noisy RGB distributions,
not a finite-sample detection guarantee, and not an upper bound on every
history/transition-based learner. P2 need not itself be a congruence. A large
P2 does not eliminate finite-sample noise or scheduling/evidence bottlenecks.
Do not choose a numerical 'near enough' threshold after seeing results.

## Checkpoint redundancy audit

Audit every saved checkpoint and final snapshot. Restrict certificate evidence
to event_prefix_count and evidence_version of that checkpoint. Do not use a
later comparison to classify an earlier blocker. Reconcile exposure accounting
from frozen statistics indices, excluding the fixed 1,600 calibration sets.
Do not sample missing data or rerun comparisons to improve coverage.

For each provisional history and current candidate, record the 31 actual cached
RGB outcomes and public-label outcomes, certificate IDs, observed outgoing
availability, passive future counterexamples, and whether the existing pair
merge gate passes. Distinguish NOT_COMPARED from measured UNRESOLVED. For
NOT_COMPARED, additionally note whether the complete RGB schedule already exists
in saved statistics, without computing a new decision.

Use post-freeze truth to count provisional histories per predictive class,
represented versus unrepresented classes, same-class redundancy, distinct
classes sharing P2, same-class measured UNRESOLVED, spurious DIFFERENT,
unmeasured tests, public-label/edge gates, and eligible correct matches blocked
by another candidate under the current all-candidates rule. Report overlapping
flags and their joint contingency table rather than an invented causal ranking.
'Statistical rule only' is restricted to same-class pairs with all 31 tests
measured, no DIFFERENT, at least one UNRESOLVED, all public labels SAME, both
outgoing sets complete, and no passive contradiction. This does not claim noise
is the sole cause for every other candidate of the history.

Record tested-probe and outgoing-action counts, candidate evidence age, merge
reopenings, and completed probe-progress entries cleared by new promotions.
These are counts of bookkeeping events, not automatically wasted observations.
Report three separate diagnostic groupings: candidate-set signature, complete
outcome/gate pattern, and literal certificate IDs. Show true-class purity of
each grouping. Never treat a shared pattern as proof of safe merging.

## Reporting

Preserve per-history and per-pair compressed details, exact d* witnesses, static
truth tables, all source/input hashes, test logs, and summaries/plots. Aggregate
structural ceilings by world (32), not by treating the two cameras as independent
worlds. Redundancy totals use the latest acquired checkpoint per condition,
preferring 'final' on tied exposure counts; retain all checkpoint curves too.
Missing conditions are not zero-filled. The known first condition is reported
separately and is not the whole result. No fresh evaluation or new design is
launched automatically from this audit.
